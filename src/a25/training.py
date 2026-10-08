"""Metered A25 health benchmark and matched, parent-grouped training.

The caller owns closure admission, GPU ownership, scientific gates, and the
final model freeze.  Training opens train/validation only.  Test truth cannot
enter this API.  Cost-based update selection never reads a quality metric.
"""
from __future__ import annotations

import time
_IMPORT_WALL, _IMPORT_CPU = time.perf_counter(), time.process_time()

import argparse
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from a24.contracts import ForbiddenAccess, NumericalFailure
from .budget import charged_job, write_json
from .dataset import load_dataset
from .networks import (FeatureNormalizer, build_model, assert_parameter_match,
                       som_channels)
from .torch_physics import TorchReference, require_device


def configure_torch(seed, device):
    require_device(device)
    torch.set_num_threads(1)
    torch.manual_seed(int(seed))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(int(seed))
    # Deterministic batch schedules and kernels; no AMP in complex physics.
    torch.use_deterministic_algorithms(True)
    if torch.backends.cudnn.is_available():
        torch.backends.cudnn.benchmark = False


def load_references(paths, *, book, config, device="cpu"):
    references = {str(key): TorchReference.from_npz(path, book=book, config=config, device=device)
                  for key, path in sorted(paths.items())}
    if any(ref.closure_provenance["background_id"] != key for key, ref in references.items()):
        raise ForbiddenAccess("PORTABLE_CACHE_BACKGROUND_ID_MISMATCH")
    return references


def checkpoint_cache_factors(references):
    """Exact small factor snapshots, saved on CPU alongside learned weights."""
    return {key: {name: getattr(ref, name).detach().cpu().clone() for name in ("Ug", "Vg")}
            for key, ref in references.items()}


def validate_checkpoint_references(payload, references):
    if payload.get("reference_descriptors") != {key: ref.descriptor for key, ref in references.items()}:
        raise ForbiddenAccess("CHECKPOINT_BACKGROUND_APERTURE_DESCRIPTOR_MISMATCH")
    factors = payload.get("reference_cache_factors")
    if not isinstance(factors, dict) or set(factors) != set(references):
        raise ForbiddenAccess("CHECKPOINT_EXACT_CLOSURE_FACTORS_REQUIRED")
    for key, ref in references.items():
        saved = factors[key]
        if not isinstance(saved, dict) or set(saved) != {"Ug", "Vg"}:
            raise ForbiddenAccess("CHECKPOINT_EXACT_CLOSURE_FACTORS_REQUIRED")
        for name in ("Ug", "Vg"):
            expected, actual = getattr(ref, name), saved[name]
            if (not isinstance(actual, torch.Tensor) or actual.dtype != expected.dtype
                    or actual.shape != expected.shape
                    or not torch.equal(actual.to(device=expected.device), expected)):
                raise ForbiddenAccess("CHECKPOINT_EXACT_CLOSURE_FACTOR_MISMATCH:" + key + ":" + name)


def load_trained_model(path, references, *, config, device="cpu"):
    """Rebuild only from checkpoint topology and exactly matching backgrounds."""
    payload = torch.load(Path(path), map_location=device, weights_only=True)
    metadata = payload["metadata"]
    validate_checkpoint_references(payload, references)
    local = deepcopy(config)
    local.setdefault("training", {})["material_width"] = int(metadata["width"])
    model = build_model(metadata["method"], references, config=local,
                        blocks=int(metadata["blocks"])).to(device)
    if model.parameter_count != int(payload["parameter_count"]):
        raise ValueError("CHECKPOINT_PARAMETER_COUNT_MISMATCH")
    model.load_learned_state_dict(payload["state_dict"])
    model.normalizer.provenance = payload["normalizer_provenance"]
    model.eval()
    return model


class ParentDataset:
    def __init__(self, arrays, *, role, parent_ids=None):
        if role not in {"train", "validation"}:
            raise ForbiddenAccess("TRAINING_ACCEPTS_ONLY_TRAIN_AND_VALIDATION")
        required = {"chi", "data", "current", "background_id", "parent_id",
                    "initial_mass", "lambda", "initial_wall", "split"}
        if required - set(arrays):
            raise ValueError("INCOMPLETE_LEARNING_DATASET")
        if set(map(str, np.asarray(arrays["split"]).reshape(-1))) != {role}:
            raise ForbiddenAccess("DATASET_ROLE_SPLIT_MISMATCH")
        if "status" in arrays and np.any(np.asarray(arrays["status"]) != "OK"):
            raise NumericalFailure("FAILED_INITIALIZATION_CANNOT_BE_FILTERED")
        self.arrays, self.role = arrays, role
        all_parents = np.asarray(arrays["parent_id"], dtype=np.int64).reshape(-1)
        self.parents = np.array(sorted(set(map(int, all_parents)) if parent_ids is None
                                       else set(map(int, parent_ids))), dtype=np.int64)
        if not len(self.parents) or set(self.parents) - set(all_parents):
            raise ValueError("REGISTERED_NONEMPTY_PARENT_SUBSET_REQUIRED")
        self.indices = np.flatnonzero(np.isin(all_parents, self.parents))
        self.by_parent = {int(parent): np.flatnonzero(all_parents == parent)
                          for parent in self.parents}
        lengths = {len(self.by_parent[int(parent)]) for parent in self.parents}
        if len(lengths) != 1:
            raise ValueError("ALL_PARENT_CONDITIONS_MUST_BE_PRESENT")
        if any(np.asarray(arrays[key]).shape[0] != len(all_parents) for key in required):
            raise ValueError("ALIGNED_DATASET_ROWS_REQUIRED")
        if arrays["chi"].dtype != np.complex128 or arrays["data"].dtype != np.complex128 or arrays["current"].dtype != np.complex128:
            raise ValueError("COMPLEX128_DATASET_REQUIRED")
        if arrays["initial_mass"].dtype != np.float64:
            raise ValueError("FLOAT64_CERTIFIED_INITIALIZER_REQUIRED")

    @classmethod
    def from_npz(cls, path, *, role, parent_ids=None):
        return cls(load_dataset(path, role=role), role=role, parent_ids=parent_ids)

    def batch(self, indices, device):
        indices = np.asarray(indices, dtype=int)
        if not np.isin(indices, self.indices).all():
            raise ForbiddenAccess("ROW_OUTSIDE_REGISTERED_PARENT_SUBSET")
        return {"data": torch.tensor(self.arrays["data"][indices], dtype=torch.complex128, device=device),
                "chi": torch.tensor(self.arrays["chi"][indices], dtype=torch.complex128, device=device),
                "current": torch.tensor(self.arrays["current"][indices], dtype=torch.complex128, device=device),
                "initial_mass": torch.tensor(self.arrays["initial_mass"][indices], dtype=torch.float64, device=device),
                "lambda": torch.tensor(self.arrays["lambda"][indices], dtype=torch.float64, device=device).reshape(-1),
                "background_id": list(map(str, self.arrays["background_id"][indices])),
                "parent_id": self.arrays["parent_id"][indices].astype(int).tolist(),
                "initial_wall": np.asarray(self.arrays["initial_wall"][indices], dtype=float).reshape(-1)}


class ParentSampler:
    """Same seed/train size gives the same schedule in every method/depth."""
    def __init__(self, dataset, seed, batch=4):
        if dataset.role != "train" or len(dataset.parents) < int(batch):
            raise ValueError("FOUR_INDEPENDENT_TRAIN_PARENTS_REQUIRED")
        self.dataset, self.batch = dataset, int(batch)
        self.rng = np.random.default_rng(np.random.SeedSequence([int(seed), len(dataset.parents), 25]))

    def next(self):
        parents = self.rng.choice(self.dataset.parents, size=self.batch, replace=False)
        return np.array([self.rng.choice(self.dataset.by_parent[int(parent)]) for parent in parents], dtype=int)


def ssim_material(chi, target, grid):
    predicted = torch.stack((1. + chi.real, chi.imag), dim=1).reshape(-1, 2, grid, grid)
    expected = torch.stack((1. + target.real, target.imag), dim=1).reshape_as(predicted)
    window = min(7, grid if grid % 2 else grid - 1)
    if window < 1:
        raise ValueError("NONEMPTY_IMAGE_FOR_SSIM_REQUIRED")
    mean_p = F.avg_pool2d(predicted, window, stride=1)
    mean_t = F.avg_pool2d(expected, window, stride=1)
    var_p = F.avg_pool2d(predicted.square(), window, stride=1) - mean_p.square()
    var_t = F.avg_pool2d(expected.square(), window, stride=1) - mean_t.square()
    covariance = F.avg_pool2d(predicted * expected, window, stride=1) - mean_p * mean_t
    ranges = predicted.new_tensor([4.5, .5]).reshape(1, 2, 1, 1)
    c1, c2 = (.01 * ranges).square(), (.03 * ranges).square()
    score = ((2 * mean_p * mean_t + c1) * (2 * covariance + c2)
             / ((mean_p.square() + mean_t.square() + c1) * (var_p + var_t + c2)))
    return score.mean(dim=(1, 2, 3))


def tv_material(delta_chi, grid, volume=1.0):
    """Full-grid joint Re/Im Neumann TV in the frozen physical mass scale.

    A fixed differentiable surrogate subtracts its constant zero-state offset;
    reported scientific objectives use the exact unsmoothed TV separately.
    """
    image = delta_chi.reshape(-1, grid, grid)
    dx = F.pad(image[:, 1:, :] - image[:, :-1, :], (0, 0, 0, 1))
    dy = F.pad(image[:, :, 1:] - image[:, :, :-1], (0, 1, 0, 0))
    squared = dx.real.square() + dx.imag.square() + dy.real.square() + dy.imag.square()
    return float(volume) ** .5 * ((squared + 1e-12).sqrt() - 1e-6).sum(dim=(1, 2))


def matched_loss(result, batch, model, *, config=None):
    config = dict(config or {})
    weights = {"material": 1., "data": .1, "current": .1, "ssim": .05, "tv": .01}
    weights.update(config.get("training", {}).get("loss_weights", {}))
    material = (result.chi - batch["chi"]).abs().square().mean(-1) / model.normalizer.material_scale.square()
    current = (result.current - batch["current"]).abs().square().mean(dim=(-2, -1)) / model.normalizer.current_scale.square()
    data_den = torch.stack([model.references[key].yb_norm2 for key in batch["background_id"]])
    data = (result.data - batch["data"]).abs().square().sum(dim=(-2, -1)) / data_den
    ssim = 1. - ssim_material(result.chi, batch["chi"], model.grid)
    background = torch.stack([model.references[key].chi_b for key in batch["background_id"]])
    tv = tv_material(result.chi - background, model.grid, model.volume)
    # Dataset lambda is frozen from observation/background; same rows in all arms.
    lambdas = batch["lambda"]
    total = (weights["material"] * material + weights["data"] * data
             + weights["current"] * current + weights["ssim"] * ssim
             + lambdas * (weights["tv"] / .01) * tv).mean()
    if not torch.isfinite(total):
        raise NumericalFailure("NONFINITE_MATCHED_LEARNING_LOSS")
    return total, {"material": material.mean(), "data": data.mean(), "current": current.mean(),
                   "ssim_loss": ssim.mean(), "tv": tv.mean(), "total": total}


def fit_normalizer(references, dataset, *, config, book, device="cpu", batch=4):
    if dataset.role != "train":
        raise ForbiddenAccess("NORMALIZER_CAN_ONLY_READ_TRAIN")
    normalizer = FeatureNormalizer().to(device)
    # The statistics come from common L features at certified initial materials.
    # No target material/current enters the feature tensor.
    probe = build_model("N1", references, normalizer=normalizer, config=config)
    probe.eval()
    fsum = torch.zeros(10, dtype=torch.float64, device=device)
    fsquare = torch.zeros_like(fsum)
    ssum = torch.zeros(4, dtype=torch.float64, device=device)
    ssquare = torch.zeros_like(ssum)
    fcount = scount = 0
    material_square = current_square = material_count = current_count = 0
    with book.span("train_only_normalizer_fit", normalization_rows=len(dataset.indices)), torch.no_grad():
        for start in range(0, len(dataset.indices), batch):
            book.check()
            indices = dataset.indices[start:start + batch]
            values = dataset.batch(indices, device)
            features, _, _ = probe.feature_batch(values["data"], values["background_id"],
                                                  values["initial_mass"], values["initial_mass"])
            fsum += features.sum((0, 2, 3))
            fsquare += features.square().sum((0, 2, 3))
            fcount += features.shape[0] * probe.n
            for key, local in probe._groups(values["background_id"], device).items():
                reference = references[key]
                reference.prepare_observable(int(config.get("training", {}).get("som_observable_rank", 15)))
                observation = values["data"].index_select(0, local)
                current = reference.observable_right @ ((reference.observable_left.mH @ observation)
                                                         / reference.observable_singular[:, None])
                channels = som_channels(current, values["initial_mass"].index_select(0, local), reference)
                ssum += channels.sum((0, 2, 3))
                ssquare += channels.square().sum((0, 2, 3))
                scount += channels.shape[0] * probe.n
                book.counts["normalization_deterministic_current_source_rhs"] += len(local) * probe.s
            material_square += float(values["chi"].abs().square().sum())
            current_square += float(values["current"].abs().square().sum())
            material_count += values["chi"].numel()
            current_count += values["current"].numel()
    normalizer.fit_statistics(fsum, fsquare, fcount, ssum, ssquare, scount,
                              material_scale=(material_square / material_count) ** .5,
                              current_scale=(current_square / current_count) ** .5,
                              parent_ids=dataset.parents, role="train")
    return normalizer


def _optimizer(model, config):
    training = config.get("training", {})
    return torch.optim.AdamW(model.parameters(), lr=float(training.get("lr", 1e-3)),
                             weight_decay=float(training.get("weight_decay", 1e-5)))


def one_update(model, optimizer, batch, *, config, book):
    model.train()
    optimizer.zero_grad(set_to_none=True)
    with book.span("learning_optimizer_update", optimizer_updates=1,
                   optimizer_parent_images=len(batch["data"])):
        result = model(batch["data"], batch["background_id"], initial_mass=batch["initial_mass"])
        loss, components = matched_loss(result, batch, model, config=config)
        with book.span("torch_learning_backward", autograd_backward_calls=1):
            loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(),
                                              float(config.get("training", {}).get("grad_clip", 1.)),
                                              error_if_nonfinite=True)
        optimizer.step()
        if config.get('batched_parameter_finiteness', False):
            flags = torch.stack([torch.isfinite(parameter).all() for parameter in model.parameters()])
            finite = bool(flags.all())
        else:
            finite = not any(not torch.isfinite(parameter).all() for parameter in model.parameters())
        if not finite:
            raise NumericalFailure("NONFINITE_LEARNED_PARAMETERS")
    return {key: float(value.detach()) for key, value in components.items()}, float(norm.detach())


def validate(model, dataset, *, config, book, device="cpu", batch_size=4):
    if dataset.role != "validation":
        raise ForbiddenAccess("MODEL_SELECTION_VALIDATION_ONLY")
    model.eval()
    rows = []
    with book.span("learning_validation", validation_images=len(dataset.indices)), torch.no_grad():
        for start in range(0, len(dataset.indices), batch_size):
            book.check()
            batch = dataset.batch(dataset.indices[start:start + batch_size], device)
            result = model(batch["data"], batch["background_id"], initial_mass=batch["initial_mass"],
                           report_consistency=True)
            material = (result.chi - batch["chi"]).abs().square().sum(-1).sqrt()
            denominator = batch["chi"].abs().square().sum(-1).sqrt()
            errors = material / denominator.clamp_min(torch.finfo(torch.float64).tiny)
            loss, _ = matched_loss(result, batch, model, config=config)
            consistency = torch.zeros(len(errors), dtype=torch.float64, device=device)
            for key, indices in model._groups(batch["background_id"], device).items():
                consistency = consistency.index_copy(0, indices, result.diagnostics[key]["Rmat"])
            for i, parent in enumerate(batch["parent_id"]):
                rows.append({"parent_id": int(parent), "nrmse": float(errors[i]),
                             "Rmat": float(consistency[i]), "batch_loss": float(loss),
                             "initial_wall_seconds": float(batch["initial_wall"][i])})
    parent = {int(value): [row for row in rows if row["parent_id"] == int(value)] for value in dataset.parents}
    score = float(np.mean([np.mean([row["nrmse"] for row in values]) for values in parent.values()]))
    return {"role": "validation", "parent_mean_nrmse": score,
            "parent_count": len(parent), "case_count": len(rows), "rows": rows,
            "preprocessing_accounting": "cached training initialization already paid; inference includes initial_wall"}


def _health_batch(references, *, size, device):
    keys = sorted(references)
    chosen = [keys[index % len(keys)] for index in range(size)]
    data = torch.stack([references[key].yb for key in chosen])
    chi = torch.stack([references[key].chi_b for key in chosen])
    current = torch.stack([references[key].cb for key in chosen])
    initial = torch.stack([torch.cat((references[key].chi_b.real, references[key].chi_b.imag))
                           * references[key].sqrt_volume for key in chosen])
    return {"data": data, "chi": chi, "current": current, "initial_mass": initial,
            "lambda": torch.full((size,), .01, dtype=torch.float64, device=device),
            "background_id": chosen, "parent_id": list(range(size)),
            "initial_wall": np.zeros(size)}


def benchmark_health(references, *, config, book, device="cpu", repeats=2,
                     include_controls=True):
    """Known background only; timing/finite-gradient health is not accuracy."""
    if int(repeats) < 1 or int(repeats) > 5:
        raise ValueError("BOUNDED_HEALTH_REPEATS_REQUIRED")
    seed = int(config.get("master_seed", 251008))
    configure_torch(seed, device)
    batch = _health_batch(references, size=int(config.get("training", {}).get("parent_batch", 4)), device=device)
    topologies = [("N0", 4), ("N1", 3), ("N2", 3), ("N3", 3)]
    if include_controls:
        topologies.extend((kind, 4) for kind in ("N1", "N2", "N3"))
    rows = []
    counts = {}
    with book.span("learning_health_benchmark", health_benchmarks=1):
        for kind, blocks in topologies:
            book.check()
            configure_torch(seed, device)
            model = build_model(kind, references, config=config, blocks=blocks).to(device)
            optimizer = _optimizer(model, config)
            if kind != "N0":
                counts.setdefault(blocks, {})[kind] = model.parameter_count
            # Warm-up is included in the resource receipt but excluded from rate estimates.
            one_update(model, optimizer, batch, config=config, book=book)
            wall, cpu = [], []
            for _ in range(repeats):
                book.synchronize()
                start_wall, start_cpu = time.perf_counter(), time.process_time()
                one_update(model, optimizer, batch, config=config, book=book)
                book.synchronize()
                wall.append(time.perf_counter() - start_wall)
                cpu.append(time.process_time() - start_cpu)
            model.eval()
            with torch.no_grad():
                book.synchronize()
                start_wall, start_cpu = time.perf_counter(), time.process_time()
                result = model(batch["data"], batch["background_id"], initial_mass=batch["initial_mass"],
                               report_consistency=True)
                book.synchronize()
                eval_wall = (time.perf_counter() - start_wall) / len(batch["data"])
                eval_cpu = (time.process_time() - start_cpu) / len(batch["data"])
                if not torch.isfinite(result.mass).all():
                    raise NumericalFailure("HEALTH_NONFINITE_OUTPUT")
            rows.append({"method": kind, "blocks": blocks, "parameter_count": model.parameter_count,
                         "update_wall_seconds": max(wall), "update_cpu_seconds": max(cpu),
                         "validation_wall_seconds_per_image": eval_wall,
                         "validation_cpu_seconds_per_image": eval_cpu,
                         "samples_wall_seconds": wall, "samples_cpu_seconds": cpu,
                         "status": "HEALTH_ONLY", "normalizer": "unfitted health constants"})
            del optimizer, model, result
    for depth, local in counts.items():
        if set(local) != {"N1", "N2", "N3"} or max(local.values()) / min(local.values()) - 1 > .05:
            raise NumericalFailure("MATCHED_CAPACITY_HEALTH_FAILED")
    return {"status": "HEALTH_ONLY", "device": str(device), "rows": rows,
            "matched_parameter_counts": counts, "known_background_only": True,
            "scientific_accuracy_evaluated": False,
            "initialization_cost_in_rate": False,
            "preprocessing_rule": "health uses known background; deployment must charge certified TV initialization"}


def select_update_budget(health, *, config, cpu_available, gpu_available):
    """Largest eligible update count fitting all eight primary + three controls."""
    training = config.get("training", {})
    if list(training.get("eligible_updates", [500, 1000, 2000])) != [500, 1000, 2000]:
        raise ValueError("FROZEN_UPDATE_CHOICES_REQUIRED")
    rows = {(row["method"], int(row["blocks"])): row for row in health["rows"]}
    jobs = [(kind, 4 if kind == "N0" else 3) for _ in (32, 64)
            for kind in ("N0", "N1", "N2", "N3")]
    jobs.extend((kind, 4) for kind in ("N1", "N2", "N3"))
    if any(key not in rows for key in jobs):
        raise ValueError("COMPLETE_TOPOLOGY_COST_BENCHMARK_REQUIRED")
    validation_images = int(training.get("validation_images", 128))
    every = int(training.get("validation_every", 100))
    factor = float(training.get("cost_safety_factor", 1.3))
    candidates = []
    for updates in (500, 1000, 2000):
        cpu = wall = 0.
        for key in jobs:
            row = rows[key]
            cpu += updates * row["update_cpu_seconds"] + (updates // every) * validation_images * row["validation_cpu_seconds_per_image"]
            wall += updates * row["update_wall_seconds"] + (updates // every) * validation_images * row["validation_wall_seconds_per_image"]
        cpu *= factor
        wall *= factor
        cpu_charge = max(cpu, wall) if health["device"] == "cpu" else cpu
        gpu_charge = wall if str(health["device"]).startswith("cuda") else 0.
        candidates.append({"updates": updates, "projected_cpu_seconds": cpu_charge,
                           "projected_gpu_seconds": gpu_charge,
                           "fits": cpu_charge <= float(cpu_available) and gpu_charge <= float(gpu_available)})
    fitting = [row for row in candidates if row["fits"]]
    return {"status": "COST_SELECTED" if fitting else "INSUFFICIENT_BUDGET",
            "updates": max(row["updates"] for row in fitting) if fitting else None,
            "complete_jobs": len(jobs), "safety_factor": factor, "candidates": candidates,
            "selection_basis": "cost only; no training/validation/test quality"}


def train_one(kind, references, train_data, validation_data, *, updates, config,
              out, book, seed=None, blocks=None, normalizer=None, device="cpu"):
    if updates not in {500, 1000, 2000}:
        raise ValueError("COST_SELECTED_500_1000_OR_2000_UPDATES_REQUIRED")
    if set(train_data.parents) & set(validation_data.parents):
        raise ForbiddenAccess("TRAIN_VALIDATION_PARENT_OVERLAP")
    if len(train_data.parents) not in {32, 64} or len(validation_data.parents) != 16:
        raise ValueError("FROZEN_PARENT_COUNTS_REQUIRED")
    seed = int(config.get("master_seed", 251008) if seed is None else seed)
    configure_torch(seed, device)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "training_manifest.json").exists():
        raise ForbiddenAccess("TRAINING_ATTEMPT_ALREADY_EXISTS; new charged attempt required")
    if normalizer is None:
        normalizer = fit_normalizer(references, train_data, config=config, book=book, device=device)
    if not bool(normalizer.fitted) or set(normalizer.provenance.get("parent_ids", [])) != set(map(int, train_data.parents)):
        raise ForbiddenAccess("MATCHING_TRAIN_ONLY_NORMALIZER_REQUIRED")
    configure_torch(seed, device)
    model = build_model(kind, references, normalizer=deepcopy(normalizer), config=config, blocks=blocks).to(device)
    sampler = ParentSampler(train_data, seed, int(config.get("training", {}).get("parent_batch", 4)))
    optimizer = _optimizer(model, config)
    manifest = {"status": "TRAINING", "method": model.kind, "blocks": model.blocks,
                "train_parents": train_data.parents.tolist(), "validation_parents": validation_data.parents.tolist(),
                "updates": updates, "seed": seed, "parameter_count": model.parameter_count,
                "model_metadata": model.metadata, "normalizer_provenance": normalizer.provenance,
                "reference_descriptors": {key: ref.descriptor for key, ref in references.items()},
                "test_truth_opened": False, "batch_rule": "four distinct parents, one uniformly chosen condition each",
                "sampler_seed": [seed, len(train_data.parents), 25], "supervision_rights": "same material/data/current/SSIM/TV"}
    write_json(out / "training_manifest.json", manifest)
    history, validation_history = [], []
    best, best_step = float("inf"), None
    every = int(config.get("training", {}).get("validation_every", 100))
    with book.span("matched_learning_train", training_attempts=1):
        for step in range(1, updates + 1):
            book.check()
            indices = sampler.next()
            values = train_data.batch(indices, device)
            components, gradient_norm = one_update(model, optimizer, values, config=config, book=book)
            history.append({"step": step, "parent_ids": values["parent_id"],
                            "row_indices": indices.tolist(), "gradient_norm_before_clip": gradient_norm, **components})
            if step % every == 0:
                score = validate(model, validation_data, config=config, book=book, device=device)
                validation_history.append({"step": step, **score})
                if score["parent_mean_nrmse"] < best:
                    best, best_step = score["parent_mean_nrmse"], step
                    with book.span("learning_checkpoint_write", checkpoint_writes=1):
                        temporary = out / "best.pt.tmp"
                        torch.save({"state_dict": model.learned_state_dict(), "metadata": model.metadata,
                                    "step": step, "seed": seed, "parameter_count": model.parameter_count,
                                    "normalizer_provenance": model.normalizer.provenance,
                                    "reference_descriptors": {key: ref.descriptor for key, ref in references.items()},
                                    "reference_cache_factors": checkpoint_cache_factors(references),
                                    "selection_role": "validation", "validation_score": best}, temporary)
                        temporary.replace(out / "best.pt")
                write_json(out / "progress.json", {"status": "TRAINING", "step": step,
                           "best_step": best_step, "best_validation_nrmse": best})
    if best_step is None:
        raise NumericalFailure("NO_REGISTERED_VALIDATION_CHECKPOINT")
    manifest.update(status="TRAINED_VALIDATION_SELECTED", best_step=best_step, best_validation_nrmse=best,
                    completed_updates=updates, checkpoint=str(out / "best.pt"))
    write_json(out / "training_manifest.json", manifest)
    write_json(out / "training_history.json", history)
    write_json(out / "validation_history.json", validation_history)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="Parent-authorized metered A25 learning only")
    parser.add_argument("--mode", choices=("health", "train"), required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--config", default="configs/a25/campaign.json")
    parser.add_argument("--cache", action="append", required=True, help="background_id=NPZ")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--job", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--method", choices=("N0", "N1", "N2", "N3"))
    parser.add_argument("--train-size", type=int, choices=(32, 64), default=64)
    parser.add_argument("--blocks", type=int, choices=(3, 4))
    parser.add_argument("--cost-selection", help="Frozen cost-only update selection JSON")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    config = json.loads((root / args.config).read_text(encoding="utf-8"))
    paths = dict(value.split("=", 1) for value in args.cache)
    paths = {key: root / value for key, value in paths.items()}
    with charged_job(root, args.job, device=args.device, config=config,
                     metadata={"stage": "learning_" + args.mode}) as book:
        # Include this standalone module's imports in the resource receipt.
        book.started_wall = min(book.started_wall, _IMPORT_WALL)
        book.started_cpu = min(book.started_cpu, _IMPORT_CPU)
        configure_torch(config.get("master_seed", 251008), args.device)
        references = load_references(paths, book=book, config=config, device=args.device)
        if args.mode == "health":
            result = benchmark_health(references, config=config, book=book, device=args.device, repeats=args.repeats)
            write_json(root / args.out / "health.json", result)
        else:
            if not args.method or not args.cost_selection:
                parser.error("train requires --method and --cost-selection")
            selection = json.loads((root / args.cost_selection).read_text(encoding="utf-8"))
            if selection.get("status") != "COST_SELECTED" or selection.get("updates") not in {500, 1000, 2000}:
                raise ForbiddenAccess("FROZEN_COST_ONLY_UPDATE_ADMISSION_REQUIRED")
            manifest = json.loads((root / "data/manifest.json").read_text(encoding="utf-8"))
            train_data = ParentDataset.from_npz(root / "data/train.npz", role="train",
                                                parent_ids=manifest["train" + str(args.train_size)])
            validation_data = ParentDataset.from_npz(root / "data/validation.npz", role="validation")
            result = train_one(args.method, references, train_data, validation_data,
                               updates=int(selection["updates"]), config=config, out=root / args.out,
                               book=book, blocks=args.blocks, device=args.device)
    print(json.dumps({key: value for key, value in result.items() if key not in {"rows", "candidates"}}, default=str))


if __name__ == "__main__":
    main()
