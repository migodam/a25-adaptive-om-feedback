"""Manifest-first independent parents, immutable labels and closed test truth."""
from __future__ import annotations

from pathlib import Path
import json
import os
import time
import uuid
import numpy as np

from a24.contracts import ForbiddenAccess
from .budget import BudgetExceeded, MAX_NEW_LABELS, write_json

FAMILIES = ("shell", "asymmetric_piecewise", "smooth", "mixed_scale")
SPLIT_COUNTS = {"train": 64, "validation": 16, "locked_id": 16, "locked_ood": 16}
LOCKED_SPLITS = frozenset({"locked_id", "locked_ood"})
ONLINE_KEYS = frozenset({"data", "clean", "sigma", "noise", "noise_seed", "initial_mass",
    "lambda", "initial_wall", "initializer_id", "parent_id", "background_id", "split",
    "variant_id", "case_id", "amplitude", "noise_db", "status", "manifest_id",
    "geometry_descriptor", "label_id", "ood_type", "family"}) - {"clean", "noise"}


def _immutable_json(path, value):
    path = Path(path)
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ForbiddenAccess("FROZEN_MANIFEST_MISMATCH")
        return
    write_json(path, value)


def _write_npz(path, arrays):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ForbiddenAccess("IMMUTABLE_DATA_FILE_EXISTS")
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temporary.open("xb") as handle:
        np.savez_compressed(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_npz(path):
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key].copy() for key in archive.files}


def generate_manifest(config):
    """Offline generator manifest; all geometry draws precede any labels."""
    seed = int(config.get("master_seed", 251008))
    rows, next_id = [], 250001
    splits = {}
    for si, (split, count) in enumerate(SPLIT_COUNTS.items()):
        ids = []
        for fi, family in enumerate(FAMILIES):
            for local in range(count // 4):
                parent_id = next_id
                next_id += 1
                rng = np.random.default_rng(np.random.SeedSequence([seed, 250, si, fi, local]))
                ood_type = ("structural_combination" if local < 2 else "contrast") if split == "locked_ood" else "ID"
                ood = ood_type == "structural_combination"
                angle = float(rng.uniform(-np.pi, np.pi))
                if ood:
                    direction = float(rng.uniform(-np.pi, np.pi))
                    center = (float(rng.uniform(.17, .22)) * np.array([np.cos(direction), np.sin(direction)])).tolist()
                    scale = float(rng.uniform(1.12, 1.28))
                    ratio = float(rng.uniform(.52, .68))
                else:
                    center = rng.uniform(-.12, .12, 2).tolist()
                    scale = float(rng.uniform(.78, 1.04))
                    ratio = float(rng.uniform(.82, 1.18))
                descriptor = {"center": center, "rotation": angle, "scale": scale,
                              "axis_ratio": ratio, "shell_radius": float(rng.uniform(.14, .19)),
                              "shell_width": float(rng.uniform(.035, .055)),
                              "disk_radius": float(rng.uniform(.065, .10)),
                              "disk_weight": float(rng.uniform(.45, .8)),
                              "second_shell_weight": float(rng.uniform(.45, .75)),
                              "rectangle_width": float(rng.uniform(.17, .25)),
                              "rectangle_height": float(rng.uniform(.19, .29)),
                              "subtype": int(rng.integers(0, 2)),
                              "gaussian_centers": rng.uniform(-.13, .13, (3, 2)).tolist(),
                              "gaussian_widths": rng.uniform(.05, .095, 3).tolist(),
                              "gaussian_weights": rng.uniform(.4, .9, 3).tolist(),
                              "segment_offset": float(rng.uniform(-.06, .06))}
                rows.append({"parent_id": parent_id, "split": split, "family": family,
                             "parent_seed": [seed, 250, si, fi, local], "geometry": descriptor,
                             "ood_type": ood_type, "amplitudes": [1.5, 1.8] if ood_type == "contrast" else [.3, 1.2]})
                ids.append(parent_id)
        splits[split] = ids
    train32 = []
    for family in FAMILIES:
        train32.extend([r["parent_id"] for r in rows if r["split"] == "train" and r["family"] == family][:8])
    amplitudes = [float(x) for x in config.get("amplitudes", [.3, 1.2])]
    if len(amplitudes) != 2 or amplitudes != [.3, 1.2]:
        raise ValueError("FROZEN_TWO_AMPLITUDES_REQUIRED")
    noise = config.get("noise_snr_db", [None, 20])
    if list(noise) != [None, 20]:
        raise ValueError("FROZEN_NOISE_VARIANTS_REQUIRED")
    return {"manifest_id": str(config.get("protocol_id", "A25-ADAPTIVE-20261008-v1")) + ":parents-v1",
            "master_seed": seed, "parents": rows, "splits": splits,
            "train32": train32, "train64": splits["train"],
            "families": list(FAMILIES), "backgrounds": ["weak", "ring"],
            "amplitudes": amplitudes, "noise_snr_db": [None, 20],
            "parent_count": 112, "full_state_label_count": 448,
            "observation_count": 896, "development_label_reserve": 8,
            "label_cap_including_failed_attempts": MAX_NEW_LABELS,
            "noise_rule": "independent Gaussian real and imaginary variance sigma^2/2",
            "geometry_order": "native A2 cell rows; unchanged source and receiver order",
            "ood_rule": "eight structural-combination parents at .3/1.2; eight ID-geometry contrast parents at1.5/1.8",
            "generation_config": {k: config[k] for k in ("grid", "side", "wavenumber", "sources", "receivers",
                "source_radius", "receiver_radius", "background_weak", "background_ring", "ring_radius_inner",
                "ring_radius_outer", "perturbation_complex_phase", "source_commit") if k in config},
            "initializer_config": {k: config[k] for k in ("prox_tolerance", "prox_max_iter", "prox_check_every",
                "prox_wall_seconds", "prox_material_scale", "prox_feasibility_tolerance", "step_rule", "tv_rule",
                "selected_nn_closure") if k in config}}


def public_manifest(manifest):
    output = {key: value for key, value in manifest.items() if key != "parents"}
    output["parents"] = [{key: row[key] for key in ("parent_id", "split", "family", "ood_type", "amplitudes")}
                         for row in manifest["parents"]]
    return output


def parent_material(points, row, config):
    """Deterministic rasterization of a previously persisted parent draw."""
    parameters = row["geometry"]
    xy = np.asarray(points, dtype=float)[:, :2] - np.asarray(parameters["center"])
    c, s = np.cos(parameters["rotation"]), np.sin(parameters["rotation"])
    x = (c * xy[:, 0] + s * xy[:, 1]) / parameters["scale"]
    y = (-s * xy[:, 0] + c * xy[:, 1]) / (parameters["scale"] * parameters["axis_ratio"])
    radius = np.hypot(x, y)
    outer, width = parameters["shell_radius"], parameters["shell_width"]
    family, structural = row["family"], row["ood_type"] == "structural_combination"
    shell = ((radius <= outer) & (radius >= outer - width)).astype(float)
    def gaussian(index):
        gx, gy = parameters["gaussian_centers"][index]
        return parameters["gaussian_weights"][index] * np.exp(
            -((x-gx)**2+(y-gy)**2)/(2*parameters["gaussian_widths"][index]**2))
    if family == "shell":
        value = shell
        if structural:
            shifted = np.hypot(x-.10, y+.055)
            value = np.maximum(value, parameters["second_shell_weight"] *
                               ((shifted >= outer*.65-width) & (shifted <= outer*.65)))
        elif parameters["subtype"]:
            value = np.maximum(value, parameters["second_shell_weight"] *
                               ((radius >= outer + .045) & (radius <= outer + .045 + width)))
        else:
            value = np.maximum(value, parameters["disk_weight"] * (radius <= parameters["disk_radius"]))
    elif family == "smooth":
        value = gaussian(0) + gaussian(1)
        if structural:
            value += gaussian(2)
    elif family == "mixed_scale":
        segment = (abs(y-parameters["segment_offset"]) <= width/3) & (abs(x) <= .22)
        value = np.maximum(shell, gaussian(0))
        value = np.maximum(value, .6*segment)
        if structural:
            value = np.maximum(value, gaussian(1))
            value = np.maximum(value, .5*((abs(x+.055)<=width/3)&(abs(y)<=.23)))
            shifted = np.hypot(x+.09,y-.06)
            value = np.maximum(value,.6*((shifted>=outer*.6-width)&(shifted<=outer*.6)))
    elif family == "asymmetric_piecewise":
        w, h = parameters["rectangle_width"], parameters["rectangle_height"]
        if not parameters["subtype"]:
            value = ((x >= -w) & (x <= -.025) & (abs(y) <= h / 2)).astype(float)
        else:
            vertical = (x >= -w) & (x <= -w + width) & (abs(y) <= h / 2)
            horizontal = (x >= -w) & (x <= .07) & (y >= -h / 2) & (y <= -h / 2 + width)
            value = (vertical | horizontal).astype(float)
        value = np.maximum(value, parameters["disk_weight"] *
                           (np.hypot(x - .12, y - .065) <= parameters["disk_radius"]))
        if structural:
            value = np.maximum(value,.7*((abs(x-.085)<=width)&(y>=-.23)&(y<=-.07)))
            value = np.maximum(value,.5*(np.hypot(x+.04,y+.18)<=parameters["disk_radius"]*.7))
    else:
        raise ValueError("UNKNOWN_FROZEN_FAMILY")
    if value.max() > 0:
        value = value / value.max()
    phase = complex(*config.get("perturbation_complex_phase", [1., .2]))
    if abs(phase) == 0 or phase.imag < 0:
        raise ValueError("PASSIVE_NONZERO_MATERIAL_PHASE_REQUIRED")
    return value.astype(np.complex128) * phase / abs(phase)


def geometry_descriptor(physics):
    return {"grid": int(physics.grid), "points": np.asarray(physics.points).tolist(),
            "source_points": np.asarray(physics.vie.tx).tolist(),
            "receiver_points": np.asarray(physics.vie.rx).tolist(),
            "sources": int(physics.s), "receivers": int(physics.q),
            "volume": float(physics.volume), "wavenumber": float(physics.k),
            "precision": "complex128/float64", "source_axis": -1,
            "current_normalization": "sqrt(cell_area)*physical_current"}


def export_background_cache(path, cache, model=None, *, prep=None, initializer_id="", closure_provenance=None):
    """Portable arrays from already charged background work; no inverse solve."""
    physics = cache.physics
    arrays = {"chi_b": np.asarray(cache.chi_b, dtype=np.complex128), "eb": cache.eb,
              "yb": cache.yb, "Db": cache.Db, "G": physics.G, "S": physics.S,
              "incident": physics.incident, "L_b": cache.state_b.L,
              "volume": np.asarray(physics.volume), "grid": np.asarray(physics.grid),
              "points": physics.points, "source_points": physics.vie.tx,
              "receiver_points": physics.vie.rx,
              "descriptor": np.asarray(json.dumps(cache.descriptor, sort_keys=True)),
              "geometry_descriptor": np.asarray(json.dumps(geometry_descriptor(physics), sort_keys=True)),
              "initializer_id": np.asarray(initializer_id),
              "closure_provenance": np.asarray(json.dumps(closure_provenance or {}, sort_keys=True))}
    if model is not None:
        arrays.update(Ug=np.asarray(model.Ug), Vg=np.asarray(model.Vg))
    else:
        arrays.update(Ug=np.empty((physics.n, 0), dtype=np.complex128),
                      Vg=np.empty((physics.n, 0), dtype=np.complex128))
    if prep is not None:
        arrays.update(J=prep["J"], step=np.asarray(prep["step"]),
                      data_norm2=np.asarray(prep["data_norm2"]), beta=np.asarray(prep["beta"]))
    with cache.book.span("portable_background_cache_export"):
        path = Path(path)
        if path.exists():
            saved = _read_npz(path)
            if set(saved) != set(arrays) or any(not np.array_equal(saved[k], arrays[k]) for k in arrays):
                raise ForbiddenAccess("FROZEN_BACKGROUND_CACHE_MISMATCH")
        else:
            _write_npz(path, arrays)
    return arrays


def _freeze_allowed(freeze_record):
    if freeze_record is None:
        return False
    if isinstance(freeze_record, (str, Path)):
        try:
            freeze_record = json.loads(Path(freeze_record).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
    return (isinstance(freeze_record, dict) and freeze_record.get("status") == "FROZEN"
            and bool(freeze_record.get("model_selection_frozen", False))
            and bool(freeze_record.get("checkpoints")))


def load_dataset(path, *, role="train", freeze_record=None, allow_failed=False):
    path = Path(path)
    if ("locked" in {p.lower() for p in path.parts} or path.stem in LOCKED_SPLITS
            or path.stem.startswith(('locked_id_','locked_ood_'))):
        if role not in {'evaluation','online'} or not _freeze_allowed(freeze_record):
            raise ForbiddenAccess("TEST_INPUT_CLOSED_BEFORE_MODEL_FREEZE")
    arrays = _read_npz(path)
    if "split" in arrays and set(map(str, np.atleast_1d(arrays["split"]))) & set(LOCKED_SPLITS):
        if role not in {"evaluation", "online"} or not _freeze_allowed(freeze_record):
            raise ForbiddenAccess("TEST_INPUT_CLOSED_BEFORE_MODEL_FREEZE")
    if role == "online" and set(arrays) - ONLINE_KEYS:
        raise ForbiddenAccess("TRUTH_OR_UNKNOWN_KEY_IN_ONLINE_DATASET")
    if role not in {"train", "validation", "online", "evaluation", "offline_generator"}:
        raise ValueError("EXPLICIT_DATASET_ROLE_REQUIRED")
    if set(arrays) - (ONLINE_KEYS | {"chi", "current", "clean"}):
        raise ForbiddenAccess("UNKNOWN_DATASET_KEY")
    if "data" in arrays:
        data = arrays["data"]
        if data.ndim != 3 or data.shape[1:] != (32, 8) or data.dtype != np.complex128:
            raise ValueError("COMPLEX128_M_RECEIVER_SOURCE_DATA_REQUIRED")
        m = len(data)
        if arrays.get("parent_id", np.empty(0)).shape != (m,):
            raise ValueError("ONE_PARENT_ID_PER_OBSERVATION_REQUIRED")
        if "chi" in arrays:
            n = arrays["chi"].shape[-1]
            if arrays["chi"].shape != (m, n) or arrays["chi"].dtype != np.complex128:
                raise ValueError("COMPLEX128_M_N_MATERIAL_REQUIRED")
            if arrays.get("current", np.empty(0)).shape != (m, n, 8):
                raise ValueError("CURRENT_SOURCE_LAST_REQUIRED")
        if arrays.get("initial_mass", np.empty(0)).ndim != 2 or len(arrays["initial_mass"]) != m:
            raise ValueError("REAL_MASS_INITIALIZATION_PER_OBSERVATION_REQUIRED")
        if arrays["initial_mass"].dtype != np.float64:
            raise ValueError("FLOAT64_INITIAL_MASS_REQUIRED")
    if "status" in arrays and not allow_failed and np.any(arrays["status"] != "OK"):
        raise RuntimeError("FAILED_INITIALIZATIONS_RETAINED; do not filter parents")
    return arrays


def _consolidate(root, split, manifest_id, book):
    root = Path(root)
    label_root = root / "data" / ("locked" if split in LOCKED_SPLITS else "labels") / split
    online_root = root / "data/online" / split
    rows = []
    for path in sorted(online_root.glob("*.npz")):
        online = _read_npz(path)
        label = _read_npz(label_root / (str(online["label_id"]) + ".npz"))
        online.pop("label_id")
        rows.append({**online, "chi": label["chi"], "current": label["current"], "clean": label["clean"]})
    if not rows:
        return 0
    scalar_keys = {"geometry_descriptor", "initializer_id", "manifest_id"}
    arrays = {key: rows[0][key] if key in scalar_keys else np.stack([r[key] for r in rows])
              for key in rows[0]}
    destination = root / "data" / ("locked" if split in LOCKED_SPLITS else "") / (split + ".npz")
    online_destination = root / "data/online" / (split + ".npz")
    with book.span("consolidated_dataset_export"):
        for path, payload in ((destination, arrays), (online_destination,
                {k: v for k, v in arrays.items() if k in ONLINE_KEYS})):
            if path.exists():
                saved = _read_npz(path)
                if set(saved) != set(payload) or any(not np.array_equal(saved[k], payload[k], equal_nan=True)
                                                    if saved[k].dtype.kind in "fc" else not np.array_equal(saved[k], payload[k])
                                                    for k in payload):
                    raise ForbiddenAccess("CONSOLIDATED_FROZEN_DATA_MISMATCH")
            else:
                _write_npz(path, payload)
    return len(rows)


def generate_dataset(root, config, book, solver="pdhg", *, splits=None, initializer=None):
    """Parent-authorized charged generation; 448 labels, 896 observations.

    Existing immutable per-label files are resumed without regenerating their
    full states. Failed initializations remain explicit rows, never removed.
    """
    from a24.physics import Physics2D
    from a24.relative_feedback import ReferenceCache, RelativeFeedbackModel
    from a24.contracts import online_config, OnlineObservation
    from a24.cases import backgrounds, noisy_observation
    from a24.pilot import prepare_background
    from .campaign import initialize

    root = Path(root)
    selected_closure = config.get("selected_nn_closure")
    if selected_closure == "TASK_R32":
        rank = 32
    elif isinstance(selected_closure, str) and selected_closure in {"R16", "R24", "R32"}:
        rank = int(selected_closure[1:])
    elif isinstance(selected_closure, dict) and selected_closure.get("kind") == "R":
        rank = int(selected_closure["rank"])
        if rank not in {16, 24, 32}:
            raise ForbiddenAccess("EXPLICIT_ADMITTED_NN_CLOSURE_REQUIRED")
    else:
        raise ForbiddenAccess("EXPLICIT_ADMITTED_NN_CLOSURE_REQUIRED")
    manifest = generate_manifest(config)
    selected = list(SPLIT_COUNTS) if splits is None else list(splits)
    if set(selected) - set(SPLIT_COUNTS):
        raise ValueError("UNKNOWN_DATASET_SPLIT")
    initializer_id = "A25-" + str(solver) + "-tv1-original-bgstep"
    manifest["initializer_id"] = initializer_id
    with book.span("manifest_before_any_label"):
        _immutable_json(root / "data/locked/generator_manifest.json", manifest)
        _immutable_json(root / "data/manifest.json", public_manifest(manifest))
    physics = Physics2D(grid=int(config.get("grid", 24)), book=book, config=online_config(config))
    descriptor = json.dumps(geometry_descriptor(physics), sort_keys=True)
    with book.span("frozen_geometry_manifest"):
        _immutable_json(root / "data/geometry.json", json.loads(descriptor))
    caches = {}
    for name, chi_b in backgrounds(physics.points, config).items():
        cache = ReferenceCache(physics, chi_b, book=book, config=online_config(config))
        prep = prepare_background(cache, book, config)
        if selected_closure == "TASK_R32":
            from .campaign import task_weighted
            model = task_weighted(cache, config, book)
        else:
            model = RelativeFeedbackModel(cache, "R", rank=rank,
                                          seed=int(config.get("control_seed", 241008)) + int(cache.chi_b.real.max() > 1),
                                          config=online_config(config))
        closure_provenance = {"builder": selected_closure, "rank": rank,
            "probe_seed": int(config["master_seed"]) + 537 if selected_closure == "TASK_R32" else
                int(config.get("control_seed", 241008)) + int(cache.chi_b.real.max() > 1),
            "source_commit": config["source_commit"], "protocol_id": config["protocol_id"],
            "background_id": name, "background_descriptor": cache.descriptor,
            "basis_identity": "A25-frozen-background-" + name + "-" + str(selected_closure),
            "independent_material_probes": 4 if selected_closure == "TASK_R32" else None,
            "independent_receiver_probes": 8 if selected_closure == "TASK_R32" else None,
            "truth_or_oracle_used": False}
        export_background_cache(root / "data/background" / (name + ".npz"), cache, model,
                                prep=prep, initializer_id=initializer_id, closure_provenance=closure_provenance)
        caches[name] = (cache, prep)
    failures = []
    for parent in manifest["parents"]:
        split = parent["split"]
        if split not in selected:
            continue
        for bi, name in enumerate(manifest["backgrounds"]):
            cache, prep = caches[name]
            for ai, amplitude in enumerate(parent["amplitudes"]):
                book.check()
                label_id = f"p{parent['parent_id']}_{name}_a{ai}"
                label_root = root / "data" / ("locked" if split in LOCKED_SPLITS else "labels") / split
                label_path = label_root / (label_id + ".npz")
                if label_path.exists():
                    with book.span("existing_label_load"):
                        label = _read_npz(label_path)
                    if str(label["manifest_id"]) != manifest["manifest_id"] or str(label["geometry_descriptor"]) != descriptor:
                        raise ForbiddenAccess("EXISTING_LABEL_PROVENANCE_MISMATCH")
                else:
                    book.reserve("new_full_forward_labels", MAX_NEW_LABELS)
                    with book.scope("offline_generator"):
                        chi = cache.chi_b + amplitude * parent_material(physics.points, parent, config)
                        state = physics.full_state(chi)
                    label = {"chi": np.asarray(chi, dtype=np.complex128), "clean": state.data.copy(),
                             "current": state.current.copy(), "manifest_id": np.asarray(manifest["manifest_id"]),
                             "geometry_descriptor": np.asarray(descriptor)}
                    with book.span("immutable_full_state_label_export"):
                        _write_npz(label_path, label)
                for ni, noise_db in enumerate(manifest["noise_snr_db"]):
                    case_id = label_id + ("_clean" if noise_db is None else "_snr20")
                    online_path = root / "data/online" / split / (case_id + ".npz")
                    if online_path.exists():
                        saved = _read_npz(online_path)
                        if str(saved["initializer_id"]) != initializer_id or str(saved["manifest_id"]) != manifest["manifest_id"]:
                            raise ForbiddenAccess("EXISTING_INITIALIZATION_PROVENANCE_MISMATCH")
                        if str(saved["status"]) != "OK":
                            failures.append({"case_id": case_id, "parent_id": parent["parent_id"], "status": str(saved["status"])})
                        continue
                    noise_seed = [int(config["master_seed"]), 251, parent["parent_id"], bi, ai, ni]
                    rng = np.random.default_rng(np.random.SeedSequence(noise_seed))
                    data, sigma, noise = noisy_observation(label["clean"], cache.yb, noise_db, rng)
                    start = time.perf_counter()
                    status = "OK"
                    try:
                        if initializer is None:
                            result = initialize(cache, OnlineObservation(data, sigma, case_id), prep,
                                                config, book, solver, case_id)
                            x, lam = result[:2]
                            metadata = result[-1]
                        else:
                            result = initializer(cache, data, sigma, case_id, book)
                            x, lam, metadata = result["initial_mass"], result["lambda"], result
                        if not metadata.get("converged", False):
                            raise RuntimeError("UNCERTIFIED_COMMON_INITIALIZATION")
                        x = np.asarray(x, dtype=np.float64)
                        if x.shape != (2 * physics.n,) or not np.isfinite(x).all():
                            raise ValueError("INVALID_INITIAL_MASS")
                    except BudgetExceeded:
                        raise
                    except Exception as exc:
                        status = "INITIALIZATION_FAILED"
                        x, lam = np.full(2 * physics.n, np.nan), float("nan")
                        failures.append({"case_id": case_id, "parent_id": parent["parent_id"],
                                         "status": status, "error": type(exc).__name__ + ": " + str(exc)})
                        book.append({"event": "dataset_initialization_failure", **failures[-1]})
                    elapsed = time.perf_counter() - start
                    with book.span("immutable_noise_realization_export"):
                        noise_path = root / "data/locked/noise" / split / (case_id + ".npz")
                        noise_payload = {"noise": np.asarray(noise, dtype=np.complex128),
                                         "noise_seed": np.asarray(noise_seed, dtype=np.int64)}
                        if noise_path.exists():
                            saved_noise = _read_npz(noise_path)
                            if any(not np.array_equal(saved_noise[k], v) for k, v in noise_payload.items()):
                                raise ForbiddenAccess("CACHED_NOISE_REALIZATION_MISMATCH")
                        else:
                            _write_npz(noise_path, noise_payload)
                    online = {"data": np.asarray(data, dtype=np.complex128), "sigma": np.asarray(sigma),
                              "noise_seed": np.asarray(noise_seed, dtype=np.int64),
                              "initial_mass": x, "lambda": np.asarray(lam), "initial_wall": np.asarray(elapsed),
                              "initializer_id": np.asarray(initializer_id), "parent_id": np.asarray(parent["parent_id"], dtype=np.int64),
                              "background_id": np.asarray(name), "split": np.asarray(split),
                              "family": np.asarray(parent["family"]), "ood_type": np.asarray(parent["ood_type"]),
                              "variant_id": np.asarray(f"{name}:a{ai}:n{ni}"), "case_id": np.asarray(case_id),
                              "amplitude": np.asarray(amplitude), "noise_db": np.asarray(np.nan if noise_db is None else noise_db),
                              "status": np.asarray(status), "manifest_id": np.asarray(manifest["manifest_id"]),
                              "geometry_descriptor": np.asarray(descriptor), "label_id": np.asarray(label_id)}
                    with book.span("cached_noise_and_initialization_export"):
                        _write_npz(online_path, online)
    counts = {split: _consolidate(root, split, manifest["manifest_id"], book) for split in selected}
    result = {"status": "FAILED_INITIALIZATION" if failures else "COMPLETE", "observations": counts,
              "failed_initializations": failures, "bad_initial_parents": sorted({r["parent_id"] for r in failures}),
              "manifest_id": manifest["manifest_id"], "train32": manifest["train32"], "train64": manifest["train64"],
              "label_budget": MAX_NEW_LABELS, "initialization_inference_cost":
              "cached preprocessing only; recompute at inference or report separate measured initial_wall"}
    with book.span("dataset_generation_report"):
        write_json(root / "results/a25/dataset/GENERATION.json", result)
    return result
