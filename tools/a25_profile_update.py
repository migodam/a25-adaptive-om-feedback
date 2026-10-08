"""Paid, known-background N2 profiling; no scientific training or new labels."""
from __future__ import annotations

import time

IMPORT_WALL, IMPORT_CPU = time.perf_counter(), time.process_time()

import argparse
import cProfile
import csv
import json
import os
from pathlib import Path
import pstats

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_key, "1")

from a24.contracts import active_ledger, ForbiddenAccess
from a25.budget import charged_job, write_json
from a25.cuda_runtime import configure_host_wait
from a25.networks import build_model
from a25.training import (configure_torch, load_references, _health_batch,
                          _optimizer, one_update)


def _write_stats(path, stats, *, sort_by):
    """Preserve actual pstats function paths and both time columns."""
    index = 3 if sort_by == "cumulative" else 2
    ordered = sorted(stats.stats.items(), key=lambda row: (-row[1][index], row[0]))[:60]
    fields = ("rank", "filename", "line", "function", "primitive_calls", "total_calls",
              "self_seconds", "cumulative_seconds", "self_seconds_per_call",
              "cumulative_seconds_per_primitive_call")
    with Path(path).open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for rank, ((filename, line, function), (primitive, total, own, cumulative, _)) in enumerate(ordered, 1):
            writer.writerow({"rank": rank, "filename": filename, "line": line,
                             "function": function, "primitive_calls": primitive,
                             "total_calls": total, "self_seconds": own,
                             "cumulative_seconds": cumulative,
                             "self_seconds_per_call": own / total if total else 0.,
                             "cumulative_seconds_per_primitive_call": cumulative / primitive if primitive else 0.})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    parser.add_argument("--config", required=True,
                        help="Admitted config; use configs/a25/nn_blocking_wait.json")
    parser.add_argument("--device", choices=("cuda",), required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    root = args.root.resolve()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("nn_physics_admitted") is not True:
        raise ForbiddenAccess("PHYSICS_CLOSURE_NOT_ADMITTED")
    if config.get("selected_nn_closure") != "TASK_R32":
        raise ForbiddenAccess("PROFILE_REQUIRES_ADMITTED_TASK_R32")
    if int(config.get("training", {}).get("parent_batch", 4)) != 4:
        raise ForbiddenAccess("PROFILE_REQUIRES_FROZEN_BATCH_FOUR")

    # Set the process-local policy before any CUDA operation or charged_job's
    # GPU synchronization, exactly as in the existing GPU entry point.
    runtime = configure_host_wait(config.get("cuda_host_wait", "default"))
    directory = root / "results/a25/jobs" / args.job
    outputs = {"summary": "PROFILE_UPDATE.json", "raw_profile": "update.prof",
               "cumulative": "pstats_cumulative_top60.csv", "self": "pstats_self_top60.csv",
               "receipt": "job_receipt.json"}
    with charged_job(root, args.job, device=args.device, config=config,
                     metadata={"stage": "learning_profile", "method": "N2", "blocks": 3,
                               "known_background_only": True}) as book, active_ledger(book):
        # Imports and CUDA policy setup remain in this attempt's inclusive cost.
        book.started_wall = min(book.started_wall, IMPORT_WALL)
        book.started_cpu = min(book.started_cpu, IMPORT_CPU)
        write_json(directory / "config.json", config)
        write_json(directory / "RUNTIME.json", runtime)
        configure_torch(config["master_seed"], args.device)
        references = load_references({key: root / "data/background" / (key + ".npz")
                                      for key in ("weak", "ring")}, book=book, config=config,
                                     device=args.device)
        with book.span("profile_known_background_setup"):
            batch = _health_batch(references, size=4, device=args.device)
            model = build_model("N2", references, config=config, blocks=3).to(args.device)
            optimizer = _optimizer(model, config)

        warm_snapshot = book.snapshot()
        book.synchronize()
        warm_wall, warm_cpu = time.perf_counter(), time.process_time()
        with book.span("profile_one_warmup", profile_warmup_updates=1):
            warm_components, warm_norm = one_update(model, optimizer, batch, config=config, book=book)
        book.synchronize()
        warm = {"wall_seconds": time.perf_counter() - warm_wall,
                "cpu_seconds": time.process_time() - warm_cpu,
                "components": warm_components, "gradient_norm_before_clip": warm_norm,
                "operator_delta": book.delta(warm_snapshot)}

        measured_snapshot = book.snapshot()
        book.synchronize()
        measured_wall, measured_cpu = time.perf_counter(), time.process_time()
        profile = cProfile.Profile()
        profile.enable()
        try:
            with book.span("profile_one_measured_update", profile_measured_updates=1):
                components, norm = one_update(model, optimizer, batch, config=config, book=book)
        finally:
            profile.disable()
        sync_start = time.perf_counter()
        book.synchronize()
        final_sync_seconds = time.perf_counter() - sync_start
        measured = {"wall_seconds": time.perf_counter() - measured_wall,
                    "cpu_seconds": time.process_time() - measured_cpu,
                    "final_synchronization_seconds": final_sync_seconds,
                    "components": components, "gradient_norm_before_clip": norm,
                    "operator_delta": book.delta(measured_snapshot)}
        with book.span("profile_result_write"):
            profile.dump_stats(str(directory / outputs["raw_profile"]))
            stats = pstats.Stats(profile)
            _write_stats(directory / outputs["cumulative"], stats, sort_by="cumulative")
            _write_stats(directory / outputs["self"], stats, sort_by="self")
            summary = {"status": "PROFILE_HEALTH_ONLY", "method": "N2", "blocks": 3,
                       "batch_size": 4, "device": args.device, "warmup_updates": 1,
                       "profiled_updates": 1, "parameter_count": model.parameter_count,
                       "normalizer": "unfitted known-background health constants",
                       "known_background_only": True, "new_labels_generated": 0,
                       "scientific_training_started": False, "test_truth_opened": False,
                       "runtime": runtime, "warmup": warm, "measured": measured,
                       "reference_descriptors": {key: ref.descriptor for key, ref in references.items()},
                       "profile_scope": "one_update including existing guards, accounting, backward and optimizer",
                       "timing_scope": "instrumented update plus final GPU synchronization; not an unprofiled training rate",
                       "outputs": outputs}
            write_json(directory / outputs["summary"], summary)
        print(json.dumps({"status": summary["status"], "job": args.job,
                          "outputs": {key: str(directory / value) for key, value in outputs.items()}}))


if __name__ == "__main__":
    main()
