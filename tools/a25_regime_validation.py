"""Paid, preregistered no-NN regime check; never opens either locked split.

Run only after parent review:
  python tools/a25_regime_validation.py --job prospective-regime-validation-001

Numerical imports and all data/physics work occur inside charged_job. The
proposal loop is a25.campaign.trajectory itself. Completed progress is retained
on failure solely for archival; the wrapper never resumes/changes an optimizer.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
from dataclasses import replace
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
METHODS = ("L", "F", "TASK_R32")
PARENTS = tuple(range(250065, 250081))
ROLE = "previously unused validation parents, prospective no-NN regime check; NOT locked validation"


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _validated_plan(root, path):
    plan = _json(path)
    fixed = {"status": "PREREGISTERED_BEFORE_OUTPUT", "role": ROLE,
             "background": "weak", "amplitude": 1.2, "methods": list(METHODS),
             "parent_ids": list(PARENTS), "noise_snr_db": [None, 20],
             "blocks": 12, "checkpoints": [3, 6, 12], "tv_multiplier": .1,
             "solver": "extended_pdhg", "relative_gain_threshold": .1,
             "bootstrap_samples": 2000, "bootstrap_seed": 251934,
             "max_job_wall_seconds": 300., "epilogue_reserve_seconds": 15.,
             "task_audit_at_K12": True,
             "device": "cpu", "online_archive": "data/online/validation.npz",
             "offline_archive": "data/validation.npz",
             "output_directory": "results/a25/development/prospective_regime_validation"}
    for key, value in fixed.items():
        if plan.get(key) != value:
            raise ValueError("PREREGISTERED_REGIME_FIELD_MISMATCH:" + key)
    manifest = _json(root / "data/manifest.json")
    if (manifest["manifest_id"] != plan["manifest_id"] or
            manifest["splits"]["validation"] != list(PARENTS)):
        raise ValueError("VALIDATION_MANIFEST_WHITELIST_MISMATCH")
    families = {str(p["parent_id"]): p["family"] for p in manifest["parents"]
                if p["split"] == "validation"}
    if families != plan["parent_families"] or any(
            list(families.values()).count(family) != 4 for family in manifest["families"]):
        raise ValueError("ALL_SIXTEEN_FOUR_FAMILY_PARENTS_REQUIRED")
    source = _json(root / plan["hypothesis_source"])
    if source["hypothesis"] != plan["source_hypothesis"]:
        raise ValueError("PREEXISTING_HYPOTHESIS_CHANGED")
    base = _json(root / plan["base_config"])
    runtime = plan["frozen_runtime"]
    scoped = {"methods", "checkpoints", "prox_algorithm", "algorithm",
              "prox_wall_limit_seconds", "training_enabled"}
    if any(base.get(key) != value for key, value in runtime.items() if key not in scoped):
        raise ValueError("FROZEN_RUNTIME_DIFFERS_FROM_MATCHED_CAMPAIGN")
    for key, value in manifest["generation_config"].items():
        if key in runtime and runtime[key] != value:
            raise ValueError("ARCHIVED_PHYSICS_CONFIGURATION_MISMATCH:" + key)
    if (runtime["grid"] != 24 or runtime["blocks"] != 12 or
            runtime["max_half_step_retry"] != 1 or runtime["methods"] != list(METHODS)):
        raise ValueError("FROZEN_TRAJECTORY_REQUIRED")
    decision = _json(root / "results/a25/development/phase0/DECISION.json")
    if decision.get("status") != "HEALTHY" or decision.get("solver") != plan["solver"]:
        raise ValueError("CERTIFIED_PUBLIC_OPTIMIZER_REQUIRED")
    for name in ("TRAINED_MODELS.json", "MODEL_FREEZE.json", "LOCKED_OPEN.json"):
        if (root / "results/a25/learning" / name).exists():
            raise ValueError("SCIENTIFIC_NN_OR_LOCKED_STATE_REQUIRES_FRESH_REVIEW")
    return plan, runtime


def _bounded_ledger(base, plan, BudgetExceeded, ForbiddenAccess):
    class LocalWallLimit(BudgetExceeded):
        pass

    class BoundedLedger:
        def __init__(self):
            self.deadline = min(base.deadline, base.started_wall +
                                plan["max_job_wall_seconds"] - plan["epilogue_reserve_seconds"])

        def __getattr__(self, name):
            return getattr(base, name)

        def check(self):
            base.check()
            if time.perf_counter() >= self.deadline:
                raise LocalWallLimit("PROSPECTIVE_REGIME_WALL_STOP_WITH_EPILOGUE_RESERVE")

        @contextmanager
        def span(self, label, **counters):
            self.check()
            with base.span(label, **counters) as row:
                yield row
            self.check()

        def snapshot(self):
            self.check()
            return base.snapshot()

        def reserve(self, *args, **kwargs):
            raise ForbiddenAccess("NO_NEW_LABEL_RESERVATIONS_IN_PROSPECTIVE_REUSE")

    return BoundedLedger()


def _expected_rows(plan):
    rows = {}
    for parent in PARENTS:
        for noise in plan["noise_snr_db"]:
            case = f"p{parent}_weak_a1_{'clean' if noise is None else 'snr20'}"
            for method in METHODS:
                for k in range(1, 13):
                    rows[(case, method, k)] = {
                        "case_id": case, "parent_id": parent,
                        "family": plan["parent_families"][str(parent)], "background": "weak",
                        "amplitude": 1.2, "noise_db": noise, "method": method, "K": k,
                        "tv_multiplier": .1, "role": ROLE, "status": "NOT_RUN",
                        "delta_nrmse": None, "material_nrmse": None,
                        "quality_target_hit": None, "accepted": None,
                    }
    return rows


def _emit(path, book, kind, payload):
    from a20.costs import plain
    row = plain({"event": kind, "elapsed_job_s": time.perf_counter() - book.started_wall,
                 "job": book.metadata["job"], **payload})
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        handle.flush()
    book.counts["prospective_regime_trace_actions"] += 1


def _online_index(root, plan, physics, book):
    import numpy as np
    from a25.dataset import load_dataset, geometry_descriptor
    with book.span("prospective_validation_online_archive_load"):
        arrays = load_dataset(root / plan["online_archive"], role="online", allow_failed=True)
        if str(arrays["manifest_id"]) != plan["manifest_id"]:
            raise ValueError("OBSERVATION_MANIFEST_MISMATCH")
        if json.loads(str(arrays["geometry_descriptor"])) != geometry_descriptor(physics):
            raise ValueError("SOURCE_RECEIVER_CELL_ORDER_MISMATCH")
        index = {}
        for i, parent in enumerate(arrays["parent_id"]):
            if (int(parent) not in PARENTS or str(arrays["background_id"][i]) != "weak" or
                    float(arrays["amplitude"][i]) != 1.2):
                continue
            case = str(arrays["case_id"][i])
            if case in index:
                raise ValueError("DUPLICATE_VALIDATION_CONDITION:" + case)
            noise = float(arrays["noise_db"][i])
            ni = 0 if np.isnan(noise) else 1
            expected = f"p{int(parent)}_weak_a1_{'clean' if ni == 0 else 'snr20'}"
            if (case != expected or (ni == 1 and noise != 20.) or
                    str(arrays["split"][i]) != "validation" or
                    str(arrays["family"][i]) != plan["parent_families"][str(int(parent))] or
                    arrays["noise_seed"][i].tolist() != [251008, 251, int(parent), 0, 1, ni]):
                raise ValueError("FROZEN_CONDITION_METADATA_MISMATCH:" + case)
            # Drop every archived supervised/preprocessing field. Recompute the
            # certified shared initializer with the declared TV multiplier .1.
            index[case] = {"data": arrays["data"][i].copy(), "sigma": float(arrays["sigma"][i]),
                           "status": str(arrays["status"][i]), "parent_id": int(parent)}
        return index


def _trajectory(model, obs, x0, lam, warm0, prep, runtime, book, owner,
                states, history, trace):
    """Use the frozen campaign loop, preserving completed prefixes on errors.

    The backend does not expose a callback. On failure only, read its own
    traceback frame's states/history for archival. No proposal is recomputed,
    accepted, resumed or given any new information by this diagnostic path.
    """
    from a25.campaign import trajectory
    failed = None
    try:
        saved_states, saved_history, _ = trajectory(model, obs, x0, lam, warm0, prep,
                                                   runtime, book, runtime["prox_algorithm"], owner)
        states.extend(saved_states); history.extend(saved_history)
    except BaseException as exc:
        failed = exc
        frame = exc.__traceback__
        while frame is not None:
            if frame.tb_frame.f_code is trajectory.__code__:
                local = frame.tb_frame.f_locals
                states.extend(copy.deepcopy(local.get("states", [])))
                history.extend(copy.deepcopy(local.get("history", [])))
                iteration = local.get("iteration")
                if iteration is not None and (not history or history[-1]["iteration"] != iteration):
                    history.append({"iteration": iteration, "status": "FAILED",
                                    "accepted": False, "trials": copy.deepcopy(local.get("trials", [])),
                                    "failure_meta": getattr(exc, "meta", None), "error": repr(exc)})
                break
            frame = frame.tb_next
    for record in history:
        for trial in record.get("trials", []):
            trace("proposal", {"case_id": obs.case_id, "method": owner.split(":")[-1],
                               "iteration": record["iteration"], **trial})
        if record.get("status") == "FAILED":
            trace("proposal_failure", {"case_id": obs.case_id, "method": owner.split(":")[-1], **record})
    if failed is not None:
        raise failed
    return states


class _OfflineScorer:
    """Labels never enter reference/cache/model/initializer/proposal calls."""
    def __init__(self, root, plan):
        self.root, self.plan = root, plan
        self.expected_geometry = None
        self._targets = None

    def target(self, case, book):
        import numpy as np
        if self._targets is None:
            with book.scope("offline_regime_scoring"), book.span("prospective_validation_offline_labels_load"):
                with np.load(self.root / self.plan["offline_archive"], allow_pickle=False) as archive:
                    if str(archive["manifest_id"]) != self.plan["manifest_id"]:
                        raise ValueError("OFFLINE_MANIFEST_MISMATCH")
                    if (self.expected_geometry is None or
                            json.loads(str(archive["geometry_descriptor"])) != self.expected_geometry):
                        raise ValueError("OFFLINE_SOURCE_RECEIVER_CELL_ORDER_MISMATCH")
                    cases, parents = archive["case_id"], archive["parent_id"]
                    split, backgrounds, amplitudes = archive["split"], archive["background_id"], archive["amplitude"]
                    selected = [i for i, parent in enumerate(parents) if int(parent) in PARENTS and
                                str(split[i]) == "validation" and str(backgrounds[i]) == "weak" and
                                float(amplitudes[i]) == 1.2]
                    chi, current, clean = archive["chi"], archive["current"], archive["clean"]
                    if (chi.dtype != np.complex128 or chi.shape != (len(cases), 576) or
                            current.dtype != np.complex128 or current.shape != (len(cases), 576, 8) or
                            clean.dtype != np.complex128 or clean.shape != (len(cases), 32, 8)):
                        raise ValueError("ARCHIVED_FULL_GRID_COMPLEX128_LABELS_REQUIRED")
                    if len(selected) != len({str(cases[i]) for i in selected}):
                        raise ValueError("DUPLICATE_OFFLINE_VALIDATION_CONDITION")
                    self._targets = {str(cases[i]): {"chi": chi[i].copy(), "current": current[i].copy(),
                                                      "clean": clean[i].copy()} for i in selected}
                    expected = {f"p{parent}_weak_a1_{suffix}" for parent in PARENTS
                                for suffix in ("clean", "snr20")}
                    if set(self._targets) != expected:
                        raise ValueError("ALL_OFFLINE_VALIDATION_CONDITIONS_REQUIRED")
        return self._targets[case]


def _summaries(rows, plan, book):
    from a25.metrics import parent_equal, paired_parent_bootstrap
    table, comparisons = [], []
    with book.span("prospective_regime_parent_bootstrap", bootstrap_replicates=2000):
        for k in plan["checkpoints"]:
            by_method = {m: [r for r in rows if r["method"] == m and r["K"] == k] for m in METHODS}
            for method, selected in by_method.items():
                for metric in ("delta_nrmse", "material_nrmse"):
                    item = parent_equal(selected, metric, expected_parent_ids=PARENTS, expected_variants=2)
                    # No official successful-parent-only mean.
                    item.pop("available_parent_descriptive_mean", None)
                    table.append({"method": method, "K": k, **item})
            for method, reference in (("F", "L"), ("TASK_R32", "F")):
                item = paired_parent_bootstrap(by_method[method], by_method[reference], "delta_nrmse",
                                              expected_parent_ids=PARENTS, expected_variants=2,
                                              seed=plan["bootstrap_seed"], samples=2000)
                comparisons.append({"method": method, "reference": reference, "K": k, **item})
    primary = next(x for x in comparisons if x["method"] == "F" and x["K"] == 12)
    threshold, point = plan["relative_gain_threshold"], primary["point_estimate"]
    ci = primary["ci95"]
    point_status = "HOLD_INCOMPLETE_PAIRS" if point is None else "PASS" if point >= threshold else "FAIL"
    interval = ("UNDEFINED_INCOMPLETE_PAIRS" if ci is None else
                "ENTIRELY_AT_OR_ABOVE_TARGET" if ci[0] >= threshold else
                "ENTIRELY_BELOW_TARGET" if ci[1] < threshold else "CROSSES_TARGET")
    return {"parent_equal": table, "paired_comparisons": comparisons,
            "hypothesis_point_target_status": point_status, "ci95_vs_target": interval,
            "primary": primary, "existing_gates_changed": False}


def run(root, plan, runtime, base_book):
    import numpy as np
    from a24.contracts import active_ledger, online_config, OnlineObservation, ForbiddenAccess
    from a24.physics import Physics2D
    from a24.relative_feedback import ReferenceCache
    from a24.cases import backgrounds
    from a24.pilot import prepare_background, task_audit
    from a25.budget import BudgetExceeded, write_json
    from a25.campaign import initialize, build_models, augmented_metrics, write_csv
    output = root / plan["output_directory"]
    output.mkdir(parents=True, exist_ok=False)  # Never replace a prior scientific attempt.
    (output / "arrays").mkdir()
    book = _bounded_ledger(base_book, plan, BudgetExceeded, ForbiddenAccess)
    rows, histories, failures = _expected_rows(plan), [], []
    task_rows = {row["case_id"]: {key: row[key] for key in
                 ("case_id", "parent_id", "family", "background", "amplitude", "noise_db", "method", "K", "role", "status")}
                 for row in rows.values() if row["method"] == "TASK_R32" and row["K"] == 12}
    setup, stop = {}, None
    action_path = output / "ACTIONS.jsonl"
    trace = lambda kind, payload: _emit(action_path, base_book, kind, payload)
    write_json(output / "PREREGISTRATION.json", plan)
    write_json(output / "EXPOSURE.json", {"role": ROLE, "parent_ids": list(PARENTS),
                "validation_becomes_development_evidence": True, "locked_id_ood": "CLOSED",
                "scientific_nn_training": "NOT_RUN", "new_fullwave_labels": 0,
                "previous_label_cost_job": "independent-dataset-generation-001"})
    write_json(output / "PROVENANCE.json", {
        "protocol_id": plan["protocol_id"], "role": ROLE, "parent_ids": list(PARENTS),
        "parent_families": plan["parent_families"], "manifest_id": plan["manifest_id"],
        "hypothesis_source": plan["hypothesis_source"], "data_split": "validation",
        "online_archive": plan["online_archive"], "offline_archive": plan["offline_archive"],
        "background": "weak", "amplitude": 1.2, "noise_snr_db": [None, 20],
        "methods": list(METHODS), "tv_multiplier": .1, "K": 12,
        "checkpoints": plan["checkpoints"], "solver": plan["solver"],
        "randomness": plan["randomness"], "bootstrap_samples": 2000,
        "new_fullwave_labels": 0, "label_provenance": plan["label_provenance"],
        "truth_access": "offline scoring after each completed/failed trajectory only",
        "source_optimizer": "a25.campaign.trajectory; no update/prox/backend changes",
        "validation_becomes_development_evidence": True,
        "scientific_nn_training": "NOT_RUN", "locked_id_ood": "CLOSED",
        "physical_scope": plan["physical_scope"], "timing_scope": plan["timing_scope"],
        "max_job_wall_seconds": 300., "epilogue_reserve_seconds": 15.})
    write_csv(output / "METRICS.csv", list(rows.values()))
    scorer = _OfflineScorer(root, plan)
    try:
        with active_ledger(book):
            begin = time.perf_counter()
            physics = Physics2D(grid=runtime["grid"], book=book, config=online_config(runtime))
            setup["geometry_s"] = time.perf_counter() - begin
            from a25.dataset import geometry_descriptor
            scorer.expected_geometry = geometry_descriptor(physics)
            background = backgrounds(physics.points, runtime)["weak"]
            begin = time.perf_counter()
            cache = ReferenceCache(physics, background, book=book, config=online_config(runtime))
            prep = prepare_background(cache, book, runtime)
            setup["shared_background_s"] = time.perf_counter() - begin
            physics._evaluation_yb = cache.yb
            models, setup["methods"] = build_models(cache, runtime, book)
            observations = _online_index(root, plan, physics, book)
            for parent in PARENTS:
                for ni, noise in enumerate(plan["noise_snr_db"]):
                    case = f"p{parent}_weak_a1_{'clean' if noise is None else 'snr20'}"
                    observed = observations.get(case)
                    if observed is None or observed["status"] != "OK":
                        for key, row in rows.items():
                            if key[0] == case:
                                row.update(status="INPUT_MISSING_OR_FAILED")
                        trace("input_failure", {"case_id": case, "status": "INPUT_MISSING_OR_FAILED"})
                        continue
                    obs = OnlineObservation(observed["data"], observed["sigma"], case)
                    begin = time.perf_counter()
                    try:
                        x0, lam, warm, initial = initialize(cache, obs, prep, runtime, book,
                                                          plan["solver"], case, .1)
                    except BudgetExceeded:
                        raise
                    except Exception as exc:
                        failure = {"phase": "common_initialization", "case_id": case,
                                   "error": repr(exc), "meta": getattr(exc, "meta", None)}
                        failures.append(failure); trace("failure", failure)
                        for key, row in rows.items():
                            if key[0] == case:
                                row.update(status="COMMON_INITIALIZATION_FAILED", error=repr(exc))
                        continue
                    initial_s = time.perf_counter() - begin
                    order = list(METHODS)
                    shift = (parent + ni) % len(order)
                    order = order[shift:] + order[:shift]
                    for method in order:
                        book.check()
                        if method not in models:
                            for k in range(1, 13):
                                rows[(case, method, k)].update(status="SETUP_FAILED")
                            continue
                        states, history = [], []
                        owner = case + ":" + method
                        arm_error = None
                        try:
                            _trajectory(models[method], obs, x0, lam, replace(copy.deepcopy(warm), owner_id=owner),
                                        prep, runtime, book, owner, states, history, trace)
                        except BaseException as exc:
                            arm_error = exc
                            failure = {"phase": "trajectory", "case_id": case, "method": method,
                                       "error": repr(exc), "meta": getattr(exc, "meta", None),
                                       "completed_attempts": len(states)}
                            failures.append(failure); trace("failure", failure)
                        histories.append({"case_id": case, "parent_id": parent, "method": method,
                                          "initial": initial, "lambda": lam, "history": history,
                                          "completed_attempts": len(states)})
                        # Retain partial online estimates before any label access.
                        if states:
                            for record in states:
                                rows[(case, method, record["iteration"])].update(
                                    status="OFFLINE_AUDIT_PENDING", accepted=record["accepted"],
                                    online_s=initial_s + record["online_s"], common_initialization_s=initial_s)
                            payload = dict(K=np.asarray([s["iteration"] for s in states]),
                                           chi=np.stack([s["chi"] for s in states]),
                                           accepted=np.asarray([s["accepted"] for s in states]),
                                           online_s=np.asarray([s["online_s"] for s in states]),
                                           role=np.asarray(ROLE), case_id=np.asarray(case), method=np.asarray(method))
                            path = output / "arrays" / f"{case}_{method}_online.npz"
                            if isinstance(arm_error, BudgetExceeded):
                                # Serialization only in the declared stop reserve;
                                # final inclusive receipt charges this I/O too.
                                started_wall, started_cpu = time.perf_counter(), time.process_time()
                                np.savez_compressed(path, **payload)
                                base_book.append({"event": "partial_estimate_stop_reserve_export",
                                    "wall_seconds": time.perf_counter() - started_wall,
                                    "process_cpu_seconds": time.process_time() - started_cpu,
                                    "case_id": case, "method": method, "science_updates": 0})
                            else:
                                with base_book.span("prospective_online_estimate_archive"):
                                    np.savez_compressed(path, **payload)
                        if arm_error is not None:
                            for k in range(len(states) + 1, 13):
                                rows[(case, method, k)].update(status="TRAJECTORY_FAILED", error=repr(arm_error))
                            if isinstance(arm_error, BudgetExceeded):
                                raise arm_error
                            if not isinstance(arm_error, Exception):
                                raise arm_error
                        for record in states:
                            try:
                                target = scorer.target(case, book)
                                begin = time.perf_counter()
                                with book.scope("offline_regime_scoring"), book.span("prospective_fullwave_prediction_audit",
                                                                                    estimate_audits=1):
                                    full = physics.full_state(record["chi"])
                                    metrics = augmented_metrics(physics, target["chi"], record["chi"], background,
                                                                full, obs, target["clean"], runtime)
                                    den = float(np.linalg.norm(target["current"]))
                                    metrics["full_current_label_nrmse"] = (float(np.linalg.norm(
                                        full.current - target["current"]) / den) if den > 0 else None)
                                row = rows[(case, method, record["iteration"])]
                                row.update(metrics, status="OK", full_audit_s=time.perf_counter() - begin,
                                           current_rank=models[method].actual_rank)
                                if record["iteration"] in plan["checkpoints"]:
                                    with book.span("prospective_checkpoint_archive"):
                                        np.savez_compressed(output / "arrays" / f"{case}_{method}_K{record['iteration']}.npz",
                                            chi=record["chi"], truth=target["chi"], background=background,
                                            prediction=full.data, data=obs.data, clean=target["clean"],
                                            full_current=full.current, truth_current=target["current"],
                                            sigma=np.asarray(obs.sigma), role=np.asarray(ROLE))
                            except BudgetExceeded:
                                raise
                            except Exception as exc:
                                rows[(case, method, record["iteration"])].update(status="OFFLINE_AUDIT_FAILED", error=repr(exc))
                                failure = {"phase": "offline_audit", "case_id": case, "method": method,
                                           "K": record["iteration"], "error": repr(exc)}
                                failures.append(failure); trace("failure", failure)
                        if method == "TASK_R32" and len(states) == 12 and plan["task_audit_at_K12"]:
                            try:
                                with book.scope("offline_regime_task_audit"):
                                    metrics = task_audit(models[method], models["F"], states[-1]["chi"], obs, runtime, book)
                                task_rows[case].update(status="OK", **metrics)
                            except BudgetExceeded:
                                raise
                            except Exception as exc:
                                task_rows[case].update(status="FAILED", error=repr(exc))
                                failure = {"phase": "offline_task_audit", "case_id": case,
                                           "method": method, "K": 12, "error": repr(exc)}
                                failures.append(failure); trace("failure", failure)
                        write_csv(output / "METRICS.csv", list(rows.values()))
                        write_json(output / "HISTORIES.json", histories)
                        write_csv(output / "TASK_AUDIT.csv", list(task_rows.values()))
    except BaseException as exc:
        stop = exc
        failure = {"phase": "job_stop", "error": repr(exc), "type": type(exc).__name__}
        failures.append(failure); trace("job_stop", failure)
    finally:
        for row in rows.values():
            if row["status"] in {"NOT_RUN", "OFFLINE_AUDIT_PENDING"}:
                prefix = "NOT_RUN" if row["status"] == "NOT_RUN" else "OFFLINE_AUDIT_NOT_RUN"
                row["status"] = prefix + ("_BUDGET_OR_WALL_CAP" if isinstance(stop, BudgetExceeded) else "_INCOMPLETE")
        for row in task_rows.values():
            if row["status"] == "NOT_RUN":
                row["status"] = "NOT_RUN_BUDGET_OR_WALL_CAP" if isinstance(stop, BudgetExceeded) else "NOT_RUN_INCOMPLETE"
        flat = list(rows.values())
        try:
            # Local15s epilogue is intentional; cumulative global caps remain
            # enforced by the original ledger. A stopped pair never gets filtered.
            summary = _summaries(flat, plan, base_book)
        except BudgetExceeded as exc:
            summary = {"hypothesis_point_target_status": "HOLD_SUMMARY_BUDGET_STOP",
                       "primary": None, "error": repr(exc), "existing_gates_changed": False}
            if stop is None:
                stop = exc
        except Exception as exc:
            summary = {"hypothesis_point_target_status": "HOLD_SUMMARY_ERROR",
                       "primary": None, "error": repr(exc), "existing_gates_changed": False}
            failures.append({"phase": "parent_summary", "error": repr(exc)})
            if stop is None:
                stop = exc
        images_complete = all(row["status"] == "OK" for row in flat)
        tasks_complete = all(row["status"] == "OK" for row in task_rows.values())
        complete = images_complete and tasks_complete
        summary.update(status="COMPLETE" if complete and stop is None else "INCOMPLETE",
                       role=ROLE, expected_conditions=32, expected_parent_clusters=16,
                       expected_metric_rows=1152, observed_ok_rows=sum(r["status"] == "OK" for r in flat),
                       full_method_matrix_complete=complete, image_rows_complete=images_complete,
                       task_audit_K12_complete=tasks_complete, failures=failures,
                       metric_status_counts={status: sum(r["status"] == status for r in flat)
                                             for status in sorted({r["status"] for r in flat})},
                       task_status_counts={status: sum(r["status"] == status for r in task_rows.values())
                                           for status in sorted({r["status"] for r in task_rows.values()})},
                       scientific_nn_training="NOT_RUN", locked_id_ood="CLOSED", new_fullwave_labels=0,
                       reused_labels_paid_previously=True, physical_scope=plan["physical_scope"],
                       setup=setup, job_wall_before_final_archive_s=time.perf_counter() - base_book.started_wall)
        write_csv(output / "METRICS.csv", flat)
        write_csv(output / "CHECKPOINT_METRICS.csv", [r for r in flat if r["K"] in plan["checkpoints"]])
        write_csv(output / "TASK_AUDIT.csv", list(task_rows.values()))
        write_json(output / "HISTORIES.json", histories)
        write_json(output / "FAILURES.json", failures)
        write_json(output / "SUMMARY.json", summary)
        write_json(output / "PREPARATIONS.json", setup)
        write_json(root / "results/a25/jobs" / base_book.metadata["job"] / "result.json", summary)
        elapsed = time.perf_counter() - base_book.started_wall
        if elapsed > plan["max_job_wall_seconds"]:
            trace("wall_cap_overshoot", {"elapsed_s": elapsed, "cap_s": plan["max_job_wall_seconds"],
                                         "native_operations_are_cooperatively_bounded": True})
            if stop is None:
                stop = BudgetExceeded("PROSPECTIVE_REGIME_WALL_CAP_EXCEEDED")
            summary.update(status="WALL_CAP_EXCEEDED", wall_cap_passed=False,
                           measured_wall_before_receipt_s=elapsed,
                           wall_cap_overshoot_s=elapsed - plan["max_job_wall_seconds"])
            write_json(output / "SUMMARY.json", summary)
            write_json(root / "results/a25/jobs" / base_book.metadata["job"] / "result.json", summary)
    if stop is not None:
        raise stop
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    parser.add_argument("--config", default="configs/a25/regime_validation.json")
    args = parser.parse_args(argv)
    from a25.budget import charged_job, write_json
    with charged_job(ROOT, args.job, device="cpu",
                     config={"cpu_budget_seconds": 7200., "gpu_budget_seconds": 14400.},
                     metadata={"stage": "prospective_no_nn_regime_validation", "role": ROLE,
                               "new_fullwave_labels": 0}) as book:
        try:
            plan, runtime = _validated_plan(ROOT, ROOT / args.config)
            write_json(ROOT / "results/a25/jobs" / args.job / "config.json", plan)
            result = run(ROOT, plan, runtime, book)
            print(json.dumps({"status": result["status"], "role": ROLE,
                              "primary": result.get("primary"),
                              "point_target": result["hypothesis_point_target_status"],
                              "output": plan["output_directory"]}, allow_nan=False))
        except BaseException:
            (ROOT / "results/a25/jobs" / args.job / "ERROR.log").write_text(
                traceback.format_exc(), encoding="utf-8")
            raise


if __name__ == "__main__":
    main()
