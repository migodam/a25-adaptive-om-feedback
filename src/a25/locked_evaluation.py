"""One-opening, frozen-model evaluation with separately charged full audits.

No rank, checkpoint, architecture or hyperparameter is selected here.  The
parent's freeze precedes test truth, and the immutable opening reservation
survives failures.  Process-state cold timing does not claim a cold OS cache.
"""
from __future__ import annotations

import csv
import gc
import json
import os
from pathlib import Path, PurePosixPath
import time
from types import SimpleNamespace

import numpy as np
import torch

from a24.contracts import ForbiddenAccess, NumericalFailure, OnlineObservation, online_config
from a24.physics import Physics2D
from .budget import BudgetExceeded, write_json
from .campaign import initialize
from .dataset import _freeze_allowed, load_dataset
from .metrics import material_metrics, paired_parent_bootstrap, parent_equal
from .training import load_references, load_trained_model


SPLITS = ("locked_id", "locked_ood")
IMAGE_METRICS = ("full_chi_nrmse", "delta_nrmse", "support_iou", "edge_nrmse")


def required_models():
    names = {f"{kind}_train{size}_b{4 if kind == 'N0' else 3}"
             for size in (32, 64) for kind in ("N0", "N1", "N2", "N3")}
    return names | {f"{kind}_train64_b4" for kind in ("N1", "N2", "N3")}


def model_id(record):
    kind, depth = str(record["method"]), int(record["blocks"])
    size = len(record["train_parents"])
    return f"{kind}_train{size}_b{depth}"


def _checkpoint_relative(path):
    text = str(path).replace("\\", "/")
    parts = PurePosixPath(text).parts
    if ".." in parts:
        raise ForbiddenAccess("CHECKPOINT_PATH_TRAVERSAL")
    prefix = "results/a25/learning/"
    if prefix not in text:
        raise ForbiddenAccess("CHECKPOINT_OUTSIDE_FROZEN_LEARNING_DIRECTORY")
    return prefix + text.split(prefix, 1)[1]


def validate_freeze_record(freeze, records):
    """Metadata only; never reads test truth or selects among checkpoints."""
    if not _freeze_allowed(freeze):
        raise ForbiddenAccess("TEST_TRUTH_CLOSED_BEFORE_MODEL_FREEZE")
    if not isinstance(records, list) or len(records) != 11:
        raise ForbiddenAccess("ALL_ELEVEN_FROZEN_MODELS_REQUIRED")
    identities = [model_id(record) for record in records]
    if len(set(identities)) != 11 or set(identities) != required_models():
        raise ForbiddenAccess("MATCHED_MODEL_MATRIX_INCOMPLETE_OR_DUPLICATE")
    if any(record.get("status") != "TRAINED_VALIDATION_SELECTED" for record in records):
        raise ForbiddenAccess("UNFINISHED_MODEL_IN_FREEZE")
    checkpoints = freeze["checkpoints"]
    entries = list(checkpoints.values()) if isinstance(checkpoints, dict) else checkpoints
    selected = set()
    for entry in entries:
        if isinstance(entry, dict):
            entry = entry.get("checkpoint", entry.get("path"))
        if not isinstance(entry, str):
            raise ForbiddenAccess("EXPLICIT_FROZEN_CHECKPOINT_PATH_REQUIRED")
        selected.add(_checkpoint_relative(entry))
    expected = {_checkpoint_relative(record["checkpoint"]) for record in records}
    if len(entries) != 11 or selected != expected:
        raise ForbiddenAccess("FREEZE_CHECKPOINT_SET_MISMATCH")
    if len({int(record["completed_updates"]) for record in records}) != 1:
        raise ForbiddenAccess("UNMATCHED_COMPLETED_UPDATE_COUNTS")
    return {identity: record for identity, record in zip(identities, records)}


def claim_locked_open(path, *, freeze_path, book):
    """Exclusive immutable reservation; never remove or overwrite it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"status": "OPEN_RESERVED", "freeze_record": str(freeze_path),
               "job": book.metadata.get("job"), "owner_id": book.metadata.get("owner_id"),
               "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "policy": "one frozen test opening; failed/interrupted attempts remain exposed"}
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ForbiddenAccess("LOCKED_TEST_ALREADY_OPENED; marker is immutable") from exc
    book.append({"event": "LOCKED_TEST_OPEN_RESERVED", **payload})


def exact_increment_tv(chi, background, *, grid, volume):
    image = (np.asarray(chi) - np.asarray(background)).reshape(grid, grid)
    dx, dy = np.zeros_like(image), np.zeros_like(image)
    dx[:-1, :] = image[1:, :] - image[:-1, :]
    dy[:, :-1] = image[:, 1:] - image[:, :-1]
    return float(np.sqrt(volume) * np.sqrt(abs(dx) ** 2 + abs(dy) ** 2).sum())


def _check_deadline(book, deadline):
    book.check()
    if time.perf_counter() >= deadline:
        raise BudgetExceeded("LOCKED_EVALUATION_PHASE_LIMIT_900_SECONDS")


def _case(arrays, index, identity):
    row = {"model_id": identity, "method": identity.split("_", 1)[0],
           "train_parents": int(identity.split("_train", 1)[1].split("_", 1)[0]),
           "blocks": int(identity.rsplit("_b", 1)[1]), "status": "NOT_RUN", "error": None}
    for key in ("case_id", "parent_id", "background_id", "split", "variant_id", "family",
                "ood_type", "amplitude", "noise_db", "sigma"):
        value = np.asarray(arrays[key])[index]
        if np.asarray(value).dtype.kind in "US":
            value = str(value)
        elif key == "parent_id":
            value = int(value)
        else:
            value = float(value)
            if not np.isfinite(value):
                value = None
        row[key] = value
    row["initial_wall_seconds"] = float(np.asarray(arrays["initial_wall"])[index])
    for metric in IMAGE_METRICS:
        row[metric] = None
    return row


def _validate_split(arrays, manifest, split):
    expected = set(map(int, manifest["splits"][split]))
    if len(expected) != 16 or len(arrays["data"]) != 128:
        raise ForbiddenAccess("LOCKED_SPLIT_REQUIRES_SIXTEEN_PARENTS_EIGHT_CONDITIONS")
    parents = np.asarray(arrays["parent_id"], dtype=int)
    if set(parents) != expected or set(map(str, arrays["split"])) != {split}:
        raise ForbiddenAccess("LOCKED_SPLIT_MANIFEST_MISMATCH")
    if len(set(map(str, arrays["case_id"]))) != 128:
        raise ForbiddenAccess("DUPLICATE_LOCKED_CASES")
    public = {int(row["parent_id"]): row for row in manifest["parents"]}
    for parent in expected:
        indices = np.flatnonzero(parents == parent)
        if len(indices) != 8 or len(set(map(str, arrays["variant_id"][indices]))) != 8:
            raise ForbiddenAccess("INCOMPLETE_PARENT_CONDITIONS")
        if set(map(str, arrays["family"][indices])) != {str(public[parent]["family"])}:
            raise ForbiddenAccess("PARENT_FAMILY_MANIFEST_MISMATCH")


def _predict(model, arrays, index, *, device, book):
    """Observation/preprocessing only: no truth/current label in model inputs."""
    input_started = time.perf_counter()
    observation = torch.tensor(arrays["data"][index:index + 1], dtype=torch.complex128, device=device)
    initial = torch.tensor(arrays["initial_mass"][index:index + 1], dtype=torch.float64, device=device)
    key = str(arrays["background_id"][index])
    book.synchronize()
    input_seconds = time.perf_counter() - input_started
    snapshot = book.snapshot()
    book.synchronize()
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    with book.span("locked_cached_network_image", locked_network_images=1), torch.no_grad():
        result = model(observation, [key], initial_mass=initial)
    # Returning the actual material image to the host belongs to image time.
    chi = result.chi[0].cpu().numpy()
    book.synchronize()
    wall, cpu = time.perf_counter() - started_wall, time.process_time() - started_cpu
    transfer_start = time.perf_counter()
    with book.scope("offline_locked_tensor_export"):
        values = {"chi": chi, "data": result.data[0].cpu().numpy(),
                  "current": result.current[0].cpu().numpy(), "field": result.states[0].field.cpu().numpy()}
    transfer_seconds = time.perf_counter() - transfer_start
    if not all(np.isfinite(value).all() for value in values.values()):
        raise NumericalFailure("NONFINITE_LOCKED_NETWORK_OUTPUT")
    return values, {"cached_image_seconds": wall, "cached_image_cpu_seconds": cpu,
                    "input_transfer_seconds": input_seconds,
                    "offline_output_transfer_seconds": transfer_seconds,
                    "network_operator_counts": book.delta(snapshot)["counts"]}


def _full_audit(predicted, arrays, index, physics, background, *, config, book):
    before = book.snapshot()
    start = time.perf_counter()
    # This is strictly offline, after the model has returned its material.
    with book.scope("offline_locked_full_audit"), book.span("locked_full_Maxwell_audit", locked_full_audits=1):
        native = physics.full_state(predicted["chi"])
        current_field = physics.incident + physics.green(predicted["current"])
        forcing = predicted["chi"][:, None] * current_field
        sigma = float(arrays["sigma"][index])
        metrics = material_metrics(predicted["chi"], arrays["chi"][index], background,
                    grid=physics.grid, volume=physics.volume, data=native.data,
                    observed=arrays["data"][index], sigma=sigma, current=predicted["current"],
                    canonical_current=native.current, amplitude=float(arrays["amplitude"][index]))
        current_norm = np.linalg.norm(predicted["current"])
        metrics["Rmat"] = float(np.linalg.norm(predicted["current"] - forcing) / current_norm) if current_norm > 0 else None
        force_norm = np.linalg.norm(forcing)
        metrics["current_equation_relative_residual"] = float(np.linalg.norm(predicted["current"] - forcing) / force_norm) if force_norm > 0 else None
        field_norm = np.linalg.norm(current_field)
        metrics["field_closure_discrepancy"] = float(np.linalg.norm(predicted["field"] - current_field) / field_norm) if field_norm > 0 else None
        metrics["full_solver_backward_residual"] = native.residual
        metrics["exact_increment_TV"] = exact_increment_tv(predicted["chi"], background,
                                                   grid=physics.grid, volume=physics.volume)
        model_residual = np.linalg.norm(predicted["data"] - arrays["data"][index])
        yb = physics._locked_yb[str(arrays["background_id"][index])]
        metrics.update(_data_residual_metrics(native.data, arrays["data"][index], yb))
        background_norm2 = float(np.linalg.norm(yb) ** 2)
        metrics["model_data_normalized_squared_residual"] = float(model_residual ** 2 / background_norm2)
        metrics["full_data_normalized_squared_residual"] = float(np.linalg.norm(native.data - arrays["data"][index]) ** 2 / background_norm2)
        metrics["exact_physical_objective"] = .5 * metrics["full_data_normalized_squared_residual"] + float(arrays["lambda"][index]) * metrics["exact_increment_TV"]
        region = config["quality_region"]
        data_ok = (metrics["full_data_white_residual"] <= float(region["noisy_white_residual_max_factor"]) * np.sqrt(2 * physics.q * physics.s)
                   if sigma > 0 else (metrics["full_data_relative_residual"] is not None
                       and metrics["full_data_relative_residual"] <= float(region["noiseless_relative_residual_max"])))
        quality = (metrics["full_chi_nrmse"] <= float(region["full_chi_nrmse_max"])
                   and metrics["delta_nrmse"] <= float(region["delta_nrmse_max"]) and data_ok)
        metrics.update(quality_target_hit=bool(quality), quality_status="QUALITY_REACHED" if quality else "QUALITY_FAILED")
    metrics.update(offline_audit_seconds=time.perf_counter() - start,
                   offline_audit_operator_counts=book.delta(before)["counts"])
    return metrics, native.data


def _data_residual_metrics(data, observed, yb):
    """Quality uses differential observed data; total-data ratio is descriptive."""
    data, observed, yb = map(np.asarray, (data, observed, yb))
    if data.shape != observed.shape or yb.shape != observed.shape:
        raise ValueError("MATCHED_BACKGROUND_RECEIVER_SOURCE_DATA_REQUIRED")
    residual = float(np.linalg.norm(data - observed))
    differential = float(np.linalg.norm(observed - yb))
    total = float(np.linalg.norm(observed))
    ratio = residual / differential if differential > 0 and np.isfinite(differential) else None
    total_ratio = residual / total if total > 0 and np.isfinite(total) else None
    return {"full_data_relative_residual": ratio,
            "full_data_differential_relative_residual": ratio,
            "full_data_total_relative_residual": total_ratio,
            "full_data_relative_residual_denominator": "observed-minus-known-background",
            "observed_differential_data_norm": differential}


def _write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({key for row in rows for key in row})
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})


def _timing_indices(arrays, manifest):
    output = []
    families = sorted({str(row["family"]) for row in manifest["parents"] if row["split"] == "locked_id"})
    for family in families:
        parent = min(int(row["parent_id"]) for row in manifest["parents"]
                     if row["split"] == "locked_id" and str(row["family"]) == family)
        chosen = np.flatnonzero((arrays["parent_id"] == parent)
                    & (arrays["background_id"] == "ring")
                    & np.isclose(arrays["amplitude"], 1.2)
                    & np.isclose(arrays["noise_db"], 20.))
        if len(chosen) != 1:
            raise ForbiddenAccess("FROZEN_TIMING_SUBSET_NOT_UNIQUE")
        output.append(int(chosen[0]))
    return output


def _initializer_id_solver(initializer_id):
    prefix, suffix = "A25-", "-tv1-original-bgstep"
    if not initializer_id.startswith(prefix) or not initializer_id.endswith(suffix):
        raise ForbiddenAccess("FROZEN_CERTIFIED_INITIALIZER_ID_REQUIRED")
    return initializer_id[len(prefix):-len(suffix)]


def _read_background_npz(path, book):
    with book.span("locked_background_preprocessor_read"):
        with np.load(path, allow_pickle=False) as archive:
            values = {key: archive[key].copy() for key in archive.files}
    for key in ("J", "step", "data_norm2", "beta", "initializer_id"):
        if key not in values:
            raise ForbiddenAccess("PAID_PORTABLE_INITIALIZER_PREPARATION_REQUIRED")
    return values


def _complete_timing(root, model, checkpoint, arrays, index, physics, references,
                     background_arrays, *, mode, config, book, device, deadline,
                     freeze_record=None):
    """One fresh material state/TV solve; optional fresh arrays/model process state."""
    _check_deadline(book, deadline)
    key = str(arrays["background_id"][index])
    snapshot = book.snapshot()
    book.synchronize()
    start, cpu = time.perf_counter(), time.process_time()
    preprocess = 0.
    read_start = time.perf_counter()
    if mode == "cold_process_complete":
        # Read ONLINE siblings only; locked truth is never opened a second time.
        online = _read_online_timing(root, freeze_record)
        matches = np.flatnonzero(online["case_id"] == arrays["case_id"][index])
        if len(matches) != 1:
            raise ForbiddenAccess("ONLINE_TIMING_CASE_MISMATCH")
        j = int(matches[0])
        local = {"data": online["data"][j:j + 1], "initial_mass": online["initial_mass"][j:j + 1],
                 "background_id": online["background_id"][j:j + 1]}
        references = load_references({name: root / "data/background" / (name + ".npz")
                                     for name in ("weak", "ring")}, book=book, config=config, device=device)
        model = load_trained_model(checkpoint, references, config=config, device=device)
        prepared = _read_background_npz(root / "data/background" / (key + ".npz"), book)
    else:
        local = {"data": arrays["data"][index:index + 1], "initial_mass": arrays["initial_mass"][index:index + 1],
                 "background_id": arrays["background_id"][index:index + 1]}
        prepared = background_arrays[key]
    read_seconds = time.perf_counter() - read_start
    cache = SimpleNamespace(physics=physics, chi_b=np.asarray(prepared["chi_b"]), yb=np.asarray(prepared["yb"]))
    prep = {"J": np.asarray(prepared["J"]), "step": float(prepared["step"]),
            "data_norm2": float(prepared["data_norm2"]), "beta": float(prepared["beta"])}
    initializer_id = str(prepared["initializer_id"])
    if initializer_id != str(arrays["initializer_id"]):
        raise ForbiddenAccess("TIMING_INITIALIZER_PROVENANCE_MISMATCH")
    solver = _initializer_id_solver(initializer_id)
    before_initial = time.perf_counter()
    with book.scope("online_certified_preprocessing"):
        x, lam, _, certificate = initialize(cache,
                OnlineObservation(np.asarray(local["data"][0]), float(arrays["sigma"][index]), str(arrays["case_id"][index])),
                prep, config, book, solver, str(arrays["case_id"][index]) + ":" + mode)
    preprocess = time.perf_counter() - before_initial
    _check_deadline(book, deadline)
    local["initial_mass"] = np.asarray(x, dtype=np.float64)[None]
    predicted, image_timing = _predict(model, local, 0, device=device, book=book)
    book.synchronize()
    # Current/data/field export exists for the offline evaluator, not deployment.
    total = time.perf_counter() - start - image_timing["offline_output_transfer_seconds"]
    process = time.process_time() - cpu
    counts = book.delta(snapshot)["counts"]
    audit, _ = _full_audit(predicted, arrays, index, physics, prepared["chi_b"], config=config, book=book)
    return {"mode": mode, "status": "OK", "complete_image_seconds": total,
            "complete_image_cpu_seconds": process, "certified_initialization_seconds": preprocess,
            "file_read_and_model_cache_setup_seconds": read_seconds,
            "image_only_seconds": image_timing["cached_image_seconds"],
            "complete_operator_counts": counts, "initializer_id": initializer_id,
            "initializer_converged": bool(certificate["converged"]), "lambda": float(lam),
            "initializer_certificate": certificate,
            "offline_audit_seconds": audit["offline_audit_seconds"],
            "quality_target_hit": audit["quality_target_hit"],
            "full_chi_nrmse": audit["full_chi_nrmse"], "delta_nrmse": audit["delta_nrmse"],
            "disk_cache_condition": "OS cache uncontrolled; no physical disk-cold claim",
            "state_reset": "fresh material/TV warm state; fresh model/arrays/background factors in cold_process_complete"}


def _read_online_timing(root, freeze_record):
    # The same record was fully validated against all eleven checkpoints before
    # opening.  Online siblings remain subject to the dataset's freeze guard.
    if not _freeze_allowed(freeze_record):
        raise ForbiddenAccess("COLD_TEST_INPUT_CLOSED_BEFORE_MODEL_FREEZE")
    return load_dataset(Path(root) / "data/online/locked_id.npz", role="online",
                        freeze_record=freeze_record, allow_failed=True)


def _statistics(rows, manifest, book):
    summaries, comparisons = [], []
    with book.span("locked_parent_equal_statistics", locked_bootstrap_samples=2000):
        for split in SPLITS:
            parents = manifest["splits"][split]
            grouped = {identity: [row for row in rows if row["model_id"] == identity and row["split"] == split]
                       for identity in sorted(required_models())}
            for identity, cases in grouped.items():
                for metric in (*IMAGE_METRICS, "full_data_relative_residual", "current_consistency_nrmse", "Rmat", "quality_target_hit"):
                    summaries.append({"model_id": identity, "split": split,
                                      **parent_equal(cases, metric, expected_parent_ids=parents)})
            pairs = []
            for size in (32, 64):
                for reference in ("N1", "N3", "N0"):
                    pairs.append((f"N2_train{size}_b3", f"{reference}_train{size}_b{4 if reference == 'N0' else 3}",
                                  "closure" if reference == "N1" else "generic_recurrence" if reference == "N3" else "method_anchor"))
            pairs.extend((f"{kind}_train64_b{4 if kind == 'N0' else 3}",
                          f"{kind}_train32_b{4 if kind == 'N0' else 3}", "sample_size") for kind in ("N0", "N1", "N2", "N3"))
            pairs.extend((f"{kind}_train64_b4", f"{kind}_train64_b3", "depth_control") for kind in ("N1", "N2", "N3"))
            for candidate, reference, kind in pairs:
                for metric in IMAGE_METRICS:
                    comparisons.append({"candidate": candidate, "reference": reference, "comparison": kind, "split": split,
                        **paired_parent_bootstrap(grouped[candidate], grouped[reference], metric,
                              expected_parent_ids=parents, seed=int(manifest["master_seed"]), samples=2000,
                              relative=metric != "support_iou", higher_is_better=metric == "support_iou")})
    return summaries, comparisons


def run_locked(root, cfg, book, device="cuda"):
    root, config = Path(root).resolve(), dict(cfg)
    directory = root / "results/a25/learning"
    freeze_path = root / config.get("locked_freeze_record", "results/a25/learning/MODEL_FREEZE.json")
    with book.span("locked_freeze_metadata_read"):
        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
        records = json.loads((directory / "TRAINED_MODELS.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "data/manifest.json").read_text(encoding="utf-8"))
    registered = validate_freeze_record(freeze, records)
    checkpoints = {identity: root / _checkpoint_relative(record["checkpoint"])
                   for identity, record in registered.items()}
    if any(not checkpoint.is_file() for checkpoint in checkpoints.values()):
        raise ForbiddenAccess("FROZEN_CHECKPOINT_FILE_MISSING")
    allocation = min(900., float(config.get("resource_allocations", {}).get("gpu_evaluation", 900.)))
    if allocation <= 0:
        raise BudgetExceeded("NO_LOCKED_EVALUATION_ALLOCATION")
    deadline = time.perf_counter() + allocation
    _check_deadline(book, deadline)
    claim_locked_open(directory / "LOCKED_OPEN.json", freeze_path=freeze_path, book=book)
    out = directory / "locked_evaluation"
    out.mkdir(parents=True, exist_ok=False)
    (out / "images").mkdir()
    datasets, rows, timing, setup, pending_images = {}, [], [], [], {}
    stop_error = None
    try:
        for split in SPLITS:
            with book.span("locked_truth_first_and_only_load"):
                datasets[split] = load_dataset(root / "data/locked" / (split + ".npz"), role="evaluation",
                                               freeze_record=freeze, allow_failed=True)
            _validate_split(datasets[split], manifest, split)
        with book.scope("offline_locked_audit_setup"):
            physics = Physics2D(int(config["grid"]), book=book, config=online_config(config))
        cache_paths = {key: root / "data/background" / (key + ".npz") for key in ("weak", "ring")}
        references = load_references(cache_paths, book=book, config=config, device=device)
        background_arrays = {key: _read_background_npz(path, book) for key, path in cache_paths.items()}
        physics._locked_yb = {key: array["yb"] for key, array in background_arrays.items()}
        subset = _timing_indices(datasets["locked_id"], manifest)
        for identity in sorted(registered):
            _check_deadline(book, deadline)
            before = book.snapshot()
            start = time.perf_counter()
            model = load_trained_model(checkpoints[identity], references, config=config, device=device)
            setup.append({"model_id": identity, "checkpoint_load_seconds": time.perf_counter() - start,
                          "operator_counts": book.delta(before)["counts"]})
            for split, arrays in datasets.items():
                count, n = len(arrays["data"]), physics.n
                images = {"chi": np.full((count, n), np.nan + 1j * np.nan),
                          "truth": np.asarray(arrays["chi"]).copy(),
                          "chi_b": np.stack([background_arrays[str(key)]["chi_b"] for key in arrays["background_id"]]),
                          "model_data": np.full_like(arrays["data"], np.nan + 1j * np.nan),
                          "full_data": np.full_like(arrays["data"], np.nan + 1j * np.nan),
                          "case_id": np.asarray(arrays["case_id"]).copy(),
                          "status": np.full(count, "NOT_RUN", dtype="U40")}
                image_path = out / "images" / (identity + "_" + split + ".npz")
                pending_images[image_path] = images
                for index in range(count):
                    _check_deadline(book, deadline)
                    row = _case(arrays, index, identity)
                    if str(arrays["status"][index]) != "OK":
                        row.update(status="INITIALIZATION_FAILED", error="retained dataset initialization failure")
                    else:
                        try:
                            predicted, image_time = _predict(model, arrays, index, device=device, book=book)
                            row.update(image_time)
                            images["chi"][index], images["model_data"][index] = predicted["chi"], predicted["data"]
                            _check_deadline(book, deadline)
                            metrics, data = _full_audit(predicted, arrays, index, physics,
                                    background_arrays[str(arrays["background_id"][index])]["chi_b"], config=config, book=book)
                            row.update(metrics, status="OK")
                            images["full_data"][index] = data
                        except BudgetExceeded as exc:
                            row.update(status="AUDIT_NOT_RUN_BUDGET" if np.isfinite(images["chi"][index]).all()
                                       else "NOT_RUN_BUDGET", error=type(exc).__name__ + ": " + str(exc))
                            images["status"][index] = row["status"]
                            rows.append(row)
                            raise
                        except Exception as exc:
                            row.update(status="FORWARD_OR_AUDIT_FAILED", error=type(exc).__name__ + ": " + str(exc))
                            book.append({"event": "LOCKED_CASE_FAILURE", **row})
                    images["status"][index] = row["status"]
                    rows.append(row)
                with book.span("locked_actual_image_arrays_export", locked_image_array_exports=1):
                    with image_path.open("xb") as handle:
                        np.savez(handle, **images)
                pending_images.pop(image_path)
            if identity in {"N0_train64_b4", "N1_train64_b3", "N2_train64_b3", "N3_train64_b3"}:
                arrays = datasets["locked_id"]
                for index in subset:
                    for mode in ("warm_complete", "cold_process_complete"):
                        base = _case(arrays, index, identity)
                        base["mode"] = mode
                        if str(arrays["status"][index]) != "OK":
                            timing.append({**base, "status": "INITIALIZATION_FAILED"})
                            continue
                        try:
                            value = _complete_timing(root, model, checkpoints[identity], arrays, index,
                                      physics, references, background_arrays, mode=mode, config=config,
                                      book=book, device=device, deadline=deadline, freeze_record=freeze)
                            timing.append({**base, **value})
                        except BudgetExceeded:
                            raise
                        except Exception as exc:
                            timing.append({**base, "status": "TIMING_FAILED", "error": type(exc).__name__ + ": " + str(exc)})
            del model
            gc.collect()
    except BudgetExceeded as exc:
        stop_error = type(exc).__name__ + ": " + str(exc)
    except Exception as exc:
        stop_error = type(exc).__name__ + ": " + str(exc)
    # Preserve every remaining case as NOT_RUN; no partial mean can pass.
    delivered = {(row["model_id"], row["split"], row["case_id"]) for row in rows}
    for identity in sorted(registered):
        for split, arrays in datasets.items():
            for index in range(len(arrays["data"])):
                base = _case(arrays, index, identity)
                if (identity, split, base["case_id"]) not in delivered:
                    base.update(status="NOT_RUN_BUDGET_OR_FAILURE", error=stop_error)
                    rows.append(base)
    summaries, comparisons = [], []
    if stop_error is None:
        try:
            _check_deadline(book, deadline)
            summaries, comparisons = _statistics(rows, manifest, book)
        except BudgetExceeded as exc:
            stop_error = type(exc).__name__ + ": " + str(exc)
    # Epilogue output uses the parent's reserved shutdown allowance. Its time
    # remains in the inclusive central receipt, even after a budget stop.
    for image_path, images in pending_images.items():
        with image_path.open("xb") as handle:
            np.savez(handle, **images)
        book.counts["locked_partial_image_array_exports"] += 1
    _write_csv(out / "cases.csv", rows)
    _write_csv(out / "timing.csv", timing)
    write_json(out / "parent_summary.json", summaries)
    write_json(out / "paired_bootstrap.json", comparisons)
    write_json(out / "checkpoint_setup.json", setup)
    expected = 11 * 2 * 128
    valid = sum(row["status"] == "OK" for row in rows)
    result = {"status": "EVALUATED" if len(rows) == expected and valid == expected and stop_error is None else "PARTIAL_OR_FAILED",
              "expected_cases": expected, "delivered_cases": len(rows), "valid_cases": valid,
              "quality_failed_cases": sum(row.get("quality_target_hit") is False for row in rows),
              "missing_or_failed_cases": expected - valid, "error": stop_error,
              "scientific_gates": "PARENT_REVIEW_REQUIRED", "rank_or_model_selection_used_test": False,
              "locked_open_marker": str(directory / "LOCKED_OPEN.json"), "output": str(out),
              "bootstrap_samples": 2000, "bootstrap_status": "COMPUTED" if comparisons else "NOT_RUN",
              "timing_status": "RECORDED" if timing else "NOT_RUN",
              "disk_cache_condition": "OS cache uncontrolled; only process/material/model state was reset",
              "inference_time_rule": "cached image time separate from complete CPU TV+model time; full audits separate"}
    write_json(out / "summary.json", result)
    return result
