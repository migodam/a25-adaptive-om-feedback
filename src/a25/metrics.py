"""Image diagnostics and equal-parent paired uncertainty; no physics calls."""
from __future__ import annotations

from collections import defaultdict
import numpy as np


def _relative(numerator, denominator):
    denominator = float(np.linalg.norm(denominator))
    if denominator == 0 or not np.isfinite(denominator):
        return None
    value = float(np.linalg.norm(numerator) / denominator)
    return value if np.isfinite(value) else None


def _gradient(value, grid):
    image = np.asarray(value).reshape((int(grid), int(grid)))
    return np.stack([np.diff(image, axis=axis, append=np.take(image, [-1], axis=axis))
                     for axis in (0, 1)])


def material_metrics(chi, truth, chi_b, *, grid, volume=1.0, data=None,
                     observed=None, sigma=0.0, current=None, canonical_current=None,
                     G=None, incident=None, support_threshold=.1, amplitude=None,
                     real_lower=-.5, real_upper=4.0, imag_lower=0.0, imag_upper=.5):
    """Every state/data/current argument is supplied by a charged evaluator."""
    chi, truth, background = (np.asarray(x, dtype=np.complex128) for x in (chi, truth, chi_b))
    if chi.shape != truth.shape or chi.shape != background.shape or chi.shape != (int(grid)**2,):
        raise ValueError("MATCHED_FULL_GRID_MATERIAL_REQUIRED")
    if not all(np.isfinite(x).all() for x in (chi, truth, background)):
        raise ValueError("NONFINITE_MATERIAL_METRIC_INPUT")
    delta, estimate = truth - background, chi - background
    result = {"material_nrmse": _relative(chi - truth, truth),
              "full_chi_nrmse": _relative(chi - truth, truth),
              "delta_nrmse": _relative(estimate - delta, delta),
              "delta_real_nrmse": _relative((estimate - delta).real, delta.real),
              "delta_imag_nrmse": _relative((estimate - delta).imag, delta.imag),
              "edge_nrmse": _relative(_gradient(estimate - delta, grid), _gradient(delta, grid))}
    scale = float(abs(amplitude)) if amplitude is not None else float(np.max(abs(delta)))
    threshold = float(support_threshold) * scale
    actual_support, predicted_support = abs(delta) > threshold, abs(estimate) > threshold
    union = int(np.count_nonzero(actual_support | predicted_support))
    result["support_iou"] = (float(np.count_nonzero(actual_support & predicted_support) / union)
                              if union else 1.0)
    violation = np.maximum.reduce([real_lower - chi.real, chi.real - real_upper,
                                   imag_lower - chi.imag, chi.imag - imag_upper,
                                   np.zeros(len(chi))])
    result.update(physical_violation_fraction=float(np.mean(violation > 1e-10)),
                  max_physical_violation=float(np.max(violation)),
                  passive=bool(np.all(chi.imag >= imag_lower - 1e-10)),
                  material_mass_error=float(np.sqrt(volume) * np.linalg.norm(chi - truth)))
    if data is not None and observed is not None:
        data, observed = np.asarray(data), np.asarray(observed)
        if data.shape != observed.shape:
            raise ValueError("MATCHED_DATA_REQUIRED")
        residual = data - observed
        result["full_data_relative_residual"] = _relative(residual, observed)
        result["full_data_white_residual"] = (float(np.sqrt(2.) * np.linalg.norm(residual) / sigma)
                                               if sigma > 0 else None)
    if current is not None:
        current = np.asarray(current)
        if canonical_current is not None:
            canonical_current = np.asarray(canonical_current)
            if current.shape != canonical_current.shape:
                raise ValueError("MATCHED_SOURCE_ORDER_CURRENT_REQUIRED")
            result["current_consistency_nrmse"] = _relative(current - canonical_current, canonical_current)
        if G is not None and incident is not None:
            exciting = np.asarray(incident) + np.asarray(G) @ current
            if current.shape != exciting.shape or current.shape[0] != len(chi):
                raise ValueError("CURRENT_SOURCE_LAST_REQUIRED")
            forcing = chi[:, None] * exciting
            result["current_equation_relative_residual"] = _relative(current - forcing, forcing)
    return result


def parent_equal(rows, metric, *, expected_parent_ids=None, parent_key="parent_id", expected_variants=8):
    """Incomplete/failed parents stay visible and do not become a passing mean."""
    grouped = defaultdict(list)
    for row in rows:
        grouped[int(row[parent_key])].append(row)
    ids = sorted(grouped) if expected_parent_ids is None else sorted(set(map(int, expected_parent_ids)))
    values, failures = {}, {}
    for parent in ids:
        group = grouped.get(parent, [])
        invalid = [r for r in group if r.get("status", "OK") != "OK" or
                   r.get(metric) is None or not np.isfinite(r[metric])]
        identifiers = [r.get("case_id", r.get("variant_id")) for r in group]
        missing = (expected_variants is not None and len(group) != int(expected_variants))
        duplicate = bool(group) and all(x is not None for x in identifiers) and len(set(identifiers)) != len(group)
        if not group or invalid or missing or duplicate:
            values[parent] = None
            failures[parent] = ("MISSING_PARENT" if not group else "MISSING_OR_DUPLICATE_VARIANTS"
                                if missing or duplicate else len(invalid))
        else:
            values[parent] = float(np.mean([float(r[metric]) for r in group]))
    available = [v for v in values.values() if v is not None]
    complete = bool(ids) and len(available) == len(ids)
    return {"metric": metric, "parent_values": values, "failed_parents": failures,
            "expected_parents": len(ids), "complete_parents": len(available),
            "coverage_complete": complete,
            "parent_equal_mean": float(np.mean(available)) if complete else None,
            "available_parent_descriptive_mean": float(np.mean(available)) if available else None}


def paired_parent_bootstrap(rows, reference_rows, metric, *, expected_parent_ids=None,
                            seed=251008, samples=2000, relative=True, higher_is_better=False,
                            expected_variants=8):
    """Resample paired independent parents, after averaging their variants."""
    if int(samples) != 2000:
        raise ValueError("FROZEN_BOOTSTRAP_2000_REQUIRED")
    left = parent_equal(rows, metric, expected_parent_ids=expected_parent_ids, expected_variants=expected_variants)
    right = parent_equal(reference_rows, metric, expected_parent_ids=expected_parent_ids, expected_variants=expected_variants)
    ids = sorted(set(left["parent_values"]) | set(right["parent_values"]))
    values, undefined = [], []
    for parent in ids:
        value, reference = left["parent_values"].get(parent), right["parent_values"].get(parent)
        if value is None or reference is None or (relative and reference == 0):
            undefined.append(parent)
            continue
        difference = value - reference if higher_is_better else reference - value
        values.append(difference / abs(reference) if relative else difference)
    complete = bool(ids) and not undefined
    output = {"metric": metric, "samples": 2000, "seed": int(seed),
              "paired_parents": len(values), "expected_parents": len(ids),
              "undefined_or_failed_parents": undefined, "coverage_complete": complete,
              "relative": bool(relative), "point_estimate": None, "ci95": None}
    if complete:
        values = np.asarray(values, dtype=float)
        rng = np.random.default_rng(int(seed))
        sampled = values[rng.integers(0, len(values), size=(2000, len(values)))].mean(axis=1)
        output.update(point_estimate=float(values.mean()),
                      ci95=[float(x) for x in np.quantile(sampled, [.025, .975])])
    return output


image_metrics = material_metrics
bootstrap_parent_equal = paired_parent_bootstrap
