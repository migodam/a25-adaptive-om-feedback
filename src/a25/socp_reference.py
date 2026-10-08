"""Independent sparse SOCP reference for the frozen constrained TV prox.

The sparse forward-difference matrix is assembled independently of A24's
array operator. Clarabel's raw primal/dual outputs are never snapped or
projected. Its explicit box-dual KKT is distinguished from A24's exact-active
bound diagnostic. Dependencies are imported only inside charged calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata as import_metadata
from math import prod
from numbers import Integral
import time

import numpy as np

from a24.contracts import NumericalFailure
from .budget import BudgetExceeded
from .prox import (FEASIBILITY_TOLERANCE, MATERIAL_SCALE, TOLERANCE,
                   ProxProblem, ProxResult, _check_book, _resolve_book, certificate)


CLARABEL_VERSION = '0.11.1'
REFERENCE_MAX_ITERATIONS = 200
REFERENCE_MAX_WALL_SECONDS = 5.0
STRICT_REFERENCE_STATIONARITY_TOLERANCE = 1e-11
STRICT_REFERENCE_GAP_TOLERANCE = 1e-10


@dataclass
class SOCPData:
    difference: object
    P: object
    q: np.ndarray
    A: object
    b: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    v: np.ndarray
    background: np.ndarray
    grid_shape: tuple
    volume: float
    coefficient: float
    alpha: float
    mass_scale: float
    cone_sizes: tuple


@dataclass
class ReferenceResult:
    x: np.ndarray | None
    p: np.ndarray | None
    lower_dual: np.ndarray | None
    upper_dual: np.ndarray | None
    epigraph: np.ndarray | None
    raw_soc_dual: np.ndarray | None
    metadata: dict

    @property
    def converged(self):
        return bool(self.metadata.get('converged', False))

    @property
    def meta(self):
        return self.metadata

    @property
    def cost(self):
        return self.metadata.get('cost', {})


class ReferenceFailure(NumericalFailure):
    def __init__(self, result):
        self.result = result
        self.meta = result.metadata
        super().__init__('SOCP_REFERENCE_' + self.meta['status'])


def _shape(shape):
    value = tuple(shape)
    if (not value or any(isinstance(n, bool) or not isinstance(n, Integral) or n < 1
                         for n in value)):
        raise ValueError('POSITIVE_INTEGER_REFERENCE_GRID_REQUIRED')
    return tuple(int(n) for n in value)


def _raw_vector(value, n, name):
    raw = np.asarray(value)
    if np.iscomplexobj(raw) or raw.shape != (n,) or not np.all(np.isfinite(raw)):
        raise ValueError('FINITE_REAL_REFERENCE_VECTOR_REQUIRED:' + name)
    return np.asarray(raw, dtype=np.float64).copy()


def _difference_matrix(shape, book):
    from scipy import sparse
    shape = _shape(shape)
    n, d = prod(shape), len(shape)
    strides = tuple(prod(shape[axis+1:]) for axis in range(d))
    rows, columns, values = [], [], []
    for cell, index in enumerate(np.ndindex(shape)):
        if cell % 128 == 0:
            _check_book(book)
        for axis in range(d):
            if index[axis]+1 == shape[axis]:
                continue
            neighbor = cell+strides[axis]
            for channel in range(2):
                row = cell*(2*d)+axis*2+channel
                rows.extend((row, row))
                columns.extend((cell+channel*n, neighbor+channel*n))
                values.extend((-1., 1.))
    book.counts['a25_reference_difference_assemblies'] += 1
    return sparse.coo_matrix((values, (rows, columns)), shape=(n*2*d, 2*n),
                             dtype=np.float64).tocsc()


def difference_matrix(grid_shape, budget=None):
    """Public independent D with rows [cell, direction, Re/Im]."""
    book = _resolve_book(budget)
    with book.span('a25_reference_difference_assembly'):
        return _difference_matrix(grid_shape, book)


def _assemble(problem, book):
    from scipy import sparse
    if not isinstance(problem, ProxProblem):
        raise TypeError('PROX_PROBLEM_REQUIRED')
    shape = _shape(problem.grid_shape)
    n, d = prod(shape), len(shape)
    volume = float(problem.volume)
    weight = float(problem.weight)
    if not np.isfinite(volume) or volume <= 0 or not np.isfinite(weight) or weight < 0:
        raise ValueError('POSITIVE_VOLUME_AND_NONNEGATIVE_WEIGHT_REQUIRED')
    config = dict(problem.config or {})
    if (float(config.get('prox_tolerance', TOLERANCE)) != TOLERANCE or
            float(config.get('prox_feasibility_tolerance', FEASIBILITY_TOLERANCE)) !=
            FEASIBILITY_TOLERANCE or
            float(config.get('prox_material_scale', config.get('material_scale', MATERIAL_SCALE))) !=
            MATERIAL_SCALE):
        raise ValueError('A24_CERTIFICATE_TOLERANCES_AND_MATERIAL_SCALE_ARE_FROZEN')
    v = _raw_vector(problem.v, 2*n, 'v')
    bg = _raw_vector(problem.background, 2*n, 'background')
    box = np.array([config.get('real_lower', -.5), config.get('real_upper', 4.),
                    config.get('imag_lower', 0.), config.get('imag_upper', .5)], dtype=float)
    if not np.all(np.isfinite(box)) or box[0] >= box[1] or box[2] >= box[3]:
        raise ValueError('FINITE_ORDERED_REFERENCE_BOX_REQUIRED')
    lo = np.sqrt(volume)*np.concatenate((np.full(n, box[0]), np.full(n, box[2])))
    hi = np.sqrt(volume)*np.concatenate((np.full(n, box[1]), np.full(n, box[3])))
    coefficient = volume**((d-1)/d)/np.sqrt(volume)
    alpha, scale = weight*coefficient, MATERIAL_SCALE*np.sqrt(n*volume)
    if (not np.isfinite(alpha) or not np.isfinite(scale) or scale <= 0 or
            not np.isfinite(scale**2) or scale**2 <= 0):
        raise NumericalFailure('REFERENCE_SCALE_OUTSIDE_FLOAT64_RANGE')
    D = _difference_matrix(shape, book)
    m = 2*n
    P = sparse.diags(np.concatenate((np.ones(m), np.zeros(n))), format='csc')
    q = np.concatenate((-v, np.full(n, alpha)))
    box_A = sparse.hstack((sparse.vstack((-sparse.eye(m), sparse.eye(m)), format='csc'),
                           sparse.csc_matrix((2*m, n))), format='csc')
    soc_size = 1+2*d
    row = np.arange(n)
    top = sparse.coo_matrix((-np.ones(n), (row*soc_size, row)),
                            shape=(n*soc_size, n)).tocsc()
    Dcoo = D.tocoo()
    soc_rows = (Dcoo.row//(2*d))*soc_size+1+Dcoo.row%(2*d)
    soc_x = sparse.coo_matrix((-Dcoo.data, (soc_rows, Dcoo.col)),
                              shape=(n*soc_size, m)).tocsc()
    soc_A = sparse.hstack((soc_x, top), format='csc')
    bg_gradient = np.asarray(D@bg).reshape(n, 2*d)
    soc_b = np.zeros((n, soc_size), dtype=np.float64)
    soc_b[:, 1:] = -bg_gradient
    A = sparse.vstack((box_A, soc_A), format='csc')
    b = np.concatenate((-lo, hi, soc_b.reshape(-1)))
    book.counts['a25_reference_socp_assemblies'] += 1
    return SOCPData(D, P, q, A, b, lo, hi, v, bg, shape, volume, coefficient,
                    alpha, scale, (2*m,)+(soc_size,)*n)


def assemble_socp(problem, budget=None):
    """Return matrices for .5 z'Pz+q'z, Az+s=b and SOC epigraphs.

    Variables are z=[x;t]. Add .5||v||^2 to the conic solver's objective.
    Cones: Nonnegative(4N), followed by N SecondOrder(1+2d).
    """
    book = _resolve_book(budget)
    with book.span('a25_reference_socp_assembly'):
        return _assemble(problem, book)


def _norm(value):
    return float(np.linalg.norm(value))


def _reference_settings(problem, max_iter, remaining):
    profile = (problem.config or {}).get('reference_refinement', False)
    if profile in (False, None, 'none', 'default'):
        profile = 'default'
    elif profile in (True, 'tight', 'tight_accuracy'):
        profile = 'tight_accuracy'
    else:
        raise ValueError('UNREGISTERED_REFERENCE_REFINEMENT_PROFILE')
    values = {'max_iter': int(max_iter), 'time_limit': max(0., remaining),
              'tol_gap_abs': 1e-10, 'tol_gap_rel': 1e-10,
              'tol_feas': 1e-11, 'tol_ktratio': 1e-10,
              'max_threads': 1, 'verbose': False}
    if profile == 'tight_accuracy':
        values.update(tol_gap_abs=1e-12, tol_gap_rel=1e-12, tol_feas=1e-13,
                      tol_ktratio=1e-12, iterative_refinement_enable=True,
                      iterative_refinement_reltol=1e-14,
                      iterative_refinement_abstol=1e-14,
                      iterative_refinement_max_iter=20)
    return profile, values


def _acceptance(solver_status, cert, wall_ok):
    """Backend status never substitutes for the independently evaluated KKT.

    Parent-approved policy: AlmostSolved can count only when stricter external
    residuals pass, rather than using Clarabel's reduced-accuracy thresholds.
    Caps/errors remain failures even if their last point looks promising.
    """
    base = (wall_ok and all(np.isfinite(cert[k]) for k in
                           ('kkt_residual', 'normalized_gap', 'feasibility')) and
            cert['kkt_residual'] <= TOLERANCE and
            cert['normalized_gap'] <= TOLERANCE and
            cert['feasibility'] <= FEASIBILITY_TOLERANCE)
    stationarity_keys = ('explicit_box_dual_stationarity', 'epigraph_dual_stationarity',
                         'box_dual_feasibility', 'soc_dual_feasibility',
                         'dual_ball_feasibility', 'soc_primal_feasibility')
    complementarity_keys = ('box_complementarity', 'soc_complementarity', 'tv_complementarity')
    components = cert['kkt_components']
    strict = (base and cert['feasibility'] <= STRICT_REFERENCE_STATIONARITY_TOLERANCE and
              cert['normalized_gap'] <= STRICT_REFERENCE_GAP_TOLERANCE and
              all(np.isfinite(components[k]) and components[k] <=
                  STRICT_REFERENCE_STATIONARITY_TOLERANCE for k in stationarity_keys) and
              all(np.isfinite(components[k]) and components[k] <=
                  STRICT_REFERENCE_GAP_TOLERANCE for k in complementarity_keys))
    accepted = bool((solver_status == 'Solved' and base) or
                    (solver_status == 'AlmostSolved' and strict))
    reason = ('strict_external_reference_certificate' if accepted and solver_status == 'AlmostSolved'
              else 'solver_solved_and_external_certificate' if accepted else
              'REFERENCE_STATUS_OR_EXTERNAL_CERTIFICATE_FAILED')
    return accepted, {'acceptance_reason': reason,
                      'strict_external_reference_certificate_passed': bool(strict),
                      'almost_solved_accepted_by_external_certificate': bool(
                          accepted and solver_status == 'AlmostSolved'),
                      'reference_external_stationarity_tolerance':
                          STRICT_REFERENCE_STATIONARITY_TOLERANCE,
                      'reference_external_gap_complementarity_tolerance':
                          STRICT_REFERENCE_GAP_TOLERANCE}


def _reference_certificate(data, x, t, lower_dual, upper_dual, soc_dual, book):
    n, d = prod(data.grid_shape), len(data.grid_shape)
    scale, alpha = data.mass_scale, data.alpha
    zeta, w = soc_dual[:, 0], soc_dual[:, 1:]
    p = -w
    book.counts['a25_reference_gradient_actions'] += 1
    gradient = np.asarray(data.difference@(x-data.background)).reshape(n, 2*d)
    lengths = np.linalg.norm(gradient, axis=1)
    book.counts['a25_reference_gradient_adjoint_actions'] += 1
    g = np.asarray(data.difference.T@p.reshape(-1)).reshape(-1)
    stationarity = x-data.v+g-lower_dual+upper_dual
    lower_slack, upper_slack = x-data.lower, data.upper-x
    box_excess = np.maximum(np.maximum(-lower_slack, -upper_slack), 0.)
    dual_ball_excess = np.maximum(np.linalg.norm(p, axis=1)-alpha, 0.)
    box_dual_excess = np.concatenate((np.maximum(-lower_dual, 0.),
                                      np.maximum(-upper_dual, 0.)))
    cone_excess = np.maximum(np.maximum(np.linalg.norm(w, axis=1)-zeta, -zeta), 0.)
    primal_soc_excess = np.maximum(np.maximum(lengths-t, -t), 0.)
    box_comp = float(np.sum(np.abs(lower_dual*lower_slack))+
                     np.sum(np.abs(upper_dual*upper_slack)))
    soc_comp = float(np.sum(np.abs(zeta*t+np.sum(w*gradient, axis=1))))
    tv_comp = float(alpha*np.sum(lengths)-np.sum(p*gradient))
    # Diagnostic quadratic minimizer only. Raw Clarabel x and p stay unchanged.
    book.counts['material_box_projections'] += 1
    book.counts['material_box_diagnostic_projections'] += 1
    qmin = np.minimum(np.maximum(data.v-g, data.lower), data.upper)
    difference = x-qmin
    stable_gap = float(.5*np.dot(difference, difference)+
                       np.dot(difference, qmin-data.v+g)+tv_comp)
    objective = float(.5*np.dot(x-data.v, x-data.v)+alpha*np.sum(lengths))
    components = {
        'explicit_box_dual_stationarity': _norm(stationarity)/scale,
        'epigraph_dual_stationarity': _norm(zeta-alpha)/scale,
        'box_dual_feasibility': _norm(box_dual_excess)/scale,
        'soc_dual_feasibility': _norm(cone_excess)/scale,
        'dual_ball_feasibility': _norm(dual_ball_excess)/scale,
        'soc_primal_feasibility': _norm(primal_soc_excess)/scale,
        'box_complementarity': box_comp/scale**2,
        'soc_complementarity': soc_comp/scale**2,
        'tv_complementarity': abs(tv_comp)/scale**2,
    }
    box_max = float(np.max(box_excess))
    dual_max = float(np.max(dual_ball_excess))
    exact_feasible = box_max == 0. and dual_max == 0.
    return p.reshape(data.grid_shape+(d, 2)), {
        'objective': objective, 'primal_objective': objective,
        'epigraph_objective': float(.5*np.dot(x-data.v, x-data.v)+alpha*np.sum(t)),
        'dual_objective': objective-stable_gap, 'primal_dual_gap': stable_gap,
        'normalized_gap': abs(stable_gap)/scale**2,
        'kkt_residual': max(components.values()), 'kkt_components': components,
        'feasibility': box_max/(np.sqrt(data.volume)*MATERIAL_SCALE),
        'feasibility_mass_max': box_max, 'dual_feasibility_max': dual_max,
        'tv': float(data.coefficient*np.sum(lengths)),
        'primal_stationarity_mass_l2': _norm(stationarity),
        'primal_stationarity_physical_rms': _norm(stationarity)/np.sqrt(n*data.volume),
        'box_complementarity_mass_squared': box_comp,
        'soc_complementarity_mass_squared': soc_comp,
        'exact_primal_dual_feasibility_for_gap_bound': exact_feasible,
        'primal_error_bound_mass': (float(np.sqrt(2.*stable_gap))
                                    if exact_feasible and stable_gap >= 0 else None),
        'raw_primal_preserved': True, 'raw_dual_preserved': True,
        'post_solve_primal_projection': False,
    }


def _feasible_envelope(data, x, p, book):
    """Certificate-only feasible points; never alter either solver's output.

    The TV radius in the objective stays alpha. The virtual dual projection
    uses a slightly interior radius to absorb norm/projection roundoff. A
    separately reported conservative arithmetic allowance protects the gap
    square root. This is a floating point certificate, not interval arithmetic.
    """
    n, d = prod(data.grid_shape), len(data.grid_shape)
    raw_p = np.asarray(p, dtype=np.float64).reshape(n, 2*d)
    xf = np.minimum(np.maximum(x, data.lower), data.upper)
    book.counts['material_box_projections'] += 2
    book.counts['material_box_diagnostic_projections'] += 2
    book.counts['material_dual_projections'] += 1
    book.counts['material_dual_diagnostic_projections'] += 1
    if data.alpha == 0.:
        pf = np.zeros_like(raw_p)
    else:
        safety_radius = data.alpha*(1.-64.*np.finfo(float).eps)
        if safety_radius <= 0.:
            pf = np.zeros_like(raw_p)
        else:
            pf = raw_p/np.maximum(1., np.linalg.norm(raw_p, axis=1)/safety_radius)[:, None]
    book.counts['a25_reference_envelope_gradient_actions'] += 1
    book.counts['a25_reference_envelope_adjoint_actions'] += 1
    gradient = np.asarray(data.difference@(xf-data.background)).reshape(n, 2*d)
    g = np.asarray(data.difference.T@pf.reshape(-1)).reshape(-1)
    qmin = np.minimum(np.maximum(data.v-g, data.lower), data.upper)
    difference = xf-qmin
    quadratic = float(.5*np.dot(difference, difference))
    box_term = float(np.dot(difference, qmin-data.v+g))
    tv_term = float(data.alpha*np.sum(np.linalg.norm(gradient, axis=1)))
    pairing = float(np.sum(pf*gradient))
    gap = quadratic+box_term+tv_term-pairing
    # Gamma_k style arithmetic margin, deliberately overestimating the number
    # of scalar operations in these local/sparse products and reductions.
    k_eps = 128.*max(1, n*(2*d+2))*np.finfo(float).eps
    roundoff = (k_eps/(1.-k_eps) if k_eps < .5 else float('inf'))*(
        abs(quadratic)+abs(box_term)+abs(tv_term)+abs(pairing)+data.mass_scale**2)
    correction = _norm(np.asarray(x)-xf)
    feasible = bool(np.all(xf >= data.lower) and np.all(xf <= data.upper) and
                    np.all(np.linalg.norm(pf, axis=1) <= data.alpha))
    usable = (feasible and np.isfinite(gap) and np.isfinite(roundoff) and gap >= -roundoff)
    error_bound = correction+float(np.sqrt(2.*(max(0., gap)+roundoff))) if usable else None
    return {'status': 'FEASIBLE_NUMERICAL_ENVELOPE' if usable else 'ENVELOPE_FAILED',
            'certificate_only': True, 'raw_output_changed': False,
            'primal_correction_mass_l2': correction,
            'dual_correction_mass_l2': _norm(raw_p-pf),
            'dual_radius_relative_safety': 64.*np.finfo(float).eps,
            'primal_dual_gap': float(gap), 'gap_roundoff_allowance': float(roundoff),
            'primal_error_bound_mass': error_bound,
            'bound_assumptions': 'feasible virtual points, original strongly convex objective; conservative floating point allowance, not interval certification'}


def _comparison(data, result, reference_x, reference_meta, book):
    if result is None:
        return {'objective_agreement_status': 'NOT_REQUESTED',
                'objective_agreement_passed': None}
    if not isinstance(result, ProxResult):
        raise TypeError('REFERENCE_COMPARISON_REQUIRES_PROX_RESULT')
    state = result.warm_state
    n = prod(data.grid_shape)
    state_lo = np.sqrt(data.volume)*np.concatenate((np.full(n, state.physical_box[0]),
                                                    np.full(n, state.physical_box[2])))
    state_hi = np.sqrt(data.volume)*np.concatenate((np.full(n, state.physical_box[1]),
                                                    np.full(n, state.physical_box[3])))
    if (tuple(state.grid_shape) != data.grid_shape or state.volume != data.volume or
            state.weight*data.coefficient != data.alpha or
            not np.array_equal(state.v, data.v) or
            not np.array_equal(state.background, data.background) or
            not np.array_equal(state_lo, data.lower) or not np.array_equal(state_hi, data.upper)):
        raise ValueError('REFERENCE_COMPARISON_OBJECTIVE_MISMATCH')
    x = _raw_vector(result.x, len(data.v), 'comparison_x')
    gradient = np.asarray(data.difference@(x-data.background)).reshape(prod(data.grid_shape), -1)
    objective = float(.5*np.dot(x-data.v, x-data.v)+data.alpha*np.sum(np.linalg.norm(gradient, axis=1)))
    normalized_error = abs(objective-reference_meta['objective'])/data.mass_scale**2
    feasible = bool(np.all(x >= data.lower) and np.all(x <= data.upper))
    distance = _norm(x-reference_x)
    pgap = result.metadata.get('primal_dual_gap')
    rgap = reference_meta['primal_dual_gap']
    error_bound = None
    if (reference_meta['exact_primal_dual_feasibility_for_gap_bound'] and feasible and
            pgap is not None and np.isfinite(pgap) and pgap >= 0 and rgap >= 0):
        error_bound = float(np.sqrt(2.*pgap)+np.sqrt(2.*rgap))
    comparison_envelope = _feasible_envelope(data, x, result.warm_state.p, book)
    reference_bound = reference_meta['certificate_envelope']['primal_error_bound_mass']
    comparison_bound = comparison_envelope['primal_error_bound_mass']
    robust_allowance = (reference_bound+comparison_bound if
                        reference_bound is not None and comparison_bound is not None else None)
    return {'objective_agreement_status': 'PASS' if normalized_error <= TOLERANCE else 'FAIL',
            'objective_agreement_passed': bool(normalized_error <= TOLERANCE),
            'objective_agreement_tolerance': TOLERANCE,
            'objective_agreement_normalized_error': float(normalized_error),
            'comparison_primal_objective': objective, 'comparison_converged': result.converged,
            'comparison_primal_feasible': feasible, 'primal_distance_mass': distance,
            'primal_distance_physical_rms': distance/np.sqrt(prod(data.grid_shape)*data.volume),
            'primal_distance_gap_bound_mass': error_bound,
            'comparison_certificate_envelope': comparison_envelope,
            'robust_primal_distance_allowance': robust_allowance,
            'robust_primal_distance_agreement': bool(robust_allowance is not None and
                                                     distance <= robust_allowance),
            'dual_vector_equality_required': False}


def solve_socp_reference(problem: ProxProblem, budget=None, comparison: ProxResult | None = None,
                         *, max_iter=REFERENCE_MAX_ITERATIONS,
                         wall_limit_seconds=REFERENCE_MAX_WALL_SECONDS) -> ReferenceResult:
    """Cold independent Clarabel 0.11.1 reference, with inclusive charged cost.

    Raw explicit-box-dual KKT determines reference certification. The old A24
    fixed-step certificate is separately retained, including exact-active-bound
    stationarity failures; no raw primal snapping or dual feasibility repair.
    ``AlmostSolved`` requires the separately declared strict external reference
    certificate (1e-11 stationarity/feasibility, 1e-10 gap/complementarity).
    Cap/error statuses never count. This does not relax production tolerances.
    Explicit config reference_refinement=True/'tight_accuracy' tightens internal
    accuracy only, retaining max_iter<=200 and inclusive wall<=5 seconds. There
    is no automatic retry/refinement; the parent owns a new charged attempt.
    """
    started = time.perf_counter()
    if (isinstance(max_iter, bool) or not isinstance(max_iter, Integral) or
            not 1 <= max_iter <= REFERENCE_MAX_ITERATIONS):
        raise ValueError('REFERENCE_ITERATION_CAP_200')
    wall_limit_seconds = float(wall_limit_seconds)
    if (not np.isfinite(wall_limit_seconds) or
            not 0 < wall_limit_seconds <= REFERENCE_MAX_WALL_SECONDS):
        raise ValueError('REFERENCE_WALL_CAP_FIVE_SECONDS')
    book = _resolve_book(budget)
    before = book.snapshot()
    result = None
    try:
        with book.span('a25_socp_reference', a25_reference_calls=1) as row:
            import_started = time.perf_counter()
            try:
                import clarabel
            except ImportError as exc:
                raise NumericalFailure('CLARABEL_REFERENCE_NOT_INSTALLED') from exc
            version = import_metadata.version('clarabel')
            if version != CLARABEL_VERSION:
                raise NumericalFailure('CLARABEL_REFERENCE_VERSION_REQUIRED:' + CLARABEL_VERSION)
            import_seconds = time.perf_counter()-import_started
            _check_book(book)
            assembly_started = time.perf_counter()
            with book.span('a25_socp_reference_assembly'):
                data = _assemble(problem, book)
            assembly_seconds = time.perf_counter()-assembly_started
            deadline = started+wall_limit_seconds
            remaining = deadline-time.perf_counter()
            refinement_profile, settings_record = _reference_settings(problem, max_iter, remaining)
            if remaining <= 0:
                result = ReferenceResult(None, None, None, None, None, None,
                    {'status': 'WALL_LIMIT_BEFORE_SOLVE', 'converged': False,
                     'reference_certified': False, 'iterations': 0})
            else:
                settings = clarabel.DefaultSettings()
                for name, value in settings_record.items():
                    setattr(settings, name, value)
                cones = [clarabel.NonnegativeConeT(data.cone_sizes[0])]
                cones.extend(clarabel.SecondOrderConeT(size) for size in data.cone_sizes[1:])
                setup_started = time.perf_counter()
                with book.span('a25_socp_reference_setup'):
                    solver = clarabel.DefaultSolver(data.P, data.q, data.A, data.b, cones, settings)
                setup_seconds = time.perf_counter()-setup_started
                owner_errors = []
                local_wall_stop = [False]

                def stop_callback(_):
                    try:
                        _check_book(book)
                    except Exception as exc:
                        owner_errors.append(exc)
                        return True
                    if time.perf_counter() >= deadline:
                        local_wall_stop[0] = True
                        return True
                    return False

                solver.set_termination_callback(stop_callback)
                _check_book(book)
                with book.span('a25_socp_reference_solve', a25_reference_solver_calls=1):
                    solution = solver.solve()
                if owner_errors:
                    raise owner_errors[0]
                _check_book(book)
                n, d = prod(data.grid_shape), len(data.grid_shape)
                raw = _raw_vector(solution.x, 3*n, 'clarabel_x_and_t')
                raw_dual = _raw_vector(solution.z, 4*n+n*(1+2*d), 'clarabel_z')
                x, t = raw[:2*n], raw[2*n:]
                lower_dual, upper_dual = raw_dual[:2*n], raw_dual[2*n:4*n]
                soc_dual = raw_dual[4*n:].reshape(n, 1+2*d)
                p, cert = _reference_certificate(data, x, t, lower_dual, upper_dual, soc_dual, book)
                cert['certificate_envelope'] = _feasible_envelope(data, x, p, book)
                cert['robust_primal_error_bound_mass'] = cert['certificate_envelope']['primal_error_bound_mass']
                with book.span('a25_reference_legacy_certificate'):
                    legacy = certificate(problem, x, p, budget=book)
                comparison_started = time.perf_counter()
                paired = _comparison(data, comparison, x, cert, book)
                if comparison is not None:
                    book.counts['a25_reference_comparison_gradient_actions'] += 1
                elapsed = time.perf_counter()-started
                solver_status = str(solution.status)
                certified, acceptance = _acceptance(solver_status, cert,
                                                    not local_wall_stop[0] and
                                                    elapsed <= wall_limit_seconds)
                agreement = paired['objective_agreement_passed']
                converged = (certified and agreement is not False and
                             paired.get('robust_primal_distance_agreement', True))
                result = ReferenceResult(x, p, lower_dual, upper_dual, t, soc_dual,
                    {**cert, **paired, **acceptance,
                     'status': 'CONVERGED' if converged else 'NOT_CONVERGED',
                     'converged': bool(converged), 'reference_certified': bool(certified),
                     'solver_status': solver_status, 'algorithm': 'independent_sparse_socp_clarabel',
                     'iterations': getattr(solution, 'iterations', None),
                     'solver_reported_seconds': float(solution.solve_time),
                     'setup_seconds': setup_seconds,
                     'comparison_seconds': time.perf_counter()-comparison_started,
                     'settings': settings_record, 'clarabel_version': version,
                     'legacy_certificate': legacy,
                     'legacy_common_certificate_passed': bool(
                         legacy['kkt_residual'] <= TOLERANCE and
                         legacy['normalized_gap'] <= TOLERANCE and
                         legacy['feasibility'] <= FEASIBILITY_TOLERANCE),
                     'legacy_exact_active_bound_caveat': True,
                     'local_wall_stop': bool(local_wall_stop[0]),
                     'grid_shape': list(data.grid_shape), 'volume': data.volume,
                     'weight': float(problem.weight), 'dual_ball_radius': data.alpha,
                     'tv_physical_coefficient': data.coefficient,
                     'physical_material_scale': MATERIAL_SCALE,
                     'physical_mass_scale': data.mass_scale,
                     'owner_id': problem.owner_id, 'tolerance': TOLERANCE,
                     'feasibility_tolerance': FEASIBILITY_TOLERANCE,
                     'prior_changed': False, 'warm_start': False})
            result.metadata.update(import_seconds=import_seconds, assembly_seconds=assembly_seconds,
                                   wall_limit_seconds=wall_limit_seconds, max_iter=int(max_iter),
                                   reference_refinement=refinement_profile,
                                   settings=settings_record)
            row.update(result_status=result.metadata['status'],
                       solver_status=result.metadata.get('solver_status'),
                       iterations=result.metadata['iterations'],
                       reference_certified=result.metadata.get('reference_certified', False))
            if not result.converged:
                book.counts['a25_reference_failures'] += 1
                if (problem.config or {}).get('reference_raise_on_failure', False):
                    raise ReferenceFailure(result)
    except BudgetExceeded as exc:
        exc.meta = {'status': 'OWNER_BUDGET_EXCEEDED', 'converged': False,
                    'elapsed_seconds': time.perf_counter()-started, 'cost': book.delta(before)}
        raise
    except NumericalFailure as exc:
        if result is None:
            exc.meta = {'status': 'REFERENCE_UNAVAILABLE_OR_FAILED', 'converged': False,
                        'elapsed_seconds': time.perf_counter()-started, 'cost': book.delta(before)}
        raise
    finally:
        if result is not None:
            elapsed = time.perf_counter()-started
            if elapsed > wall_limit_seconds:
                if result.converged:
                    book.counts['a25_reference_failures'] += 1
                result.metadata.update(status='WALL_LIMIT', converged=False,
                                       reference_certified=False)
            result.metadata.update(elapsed_seconds=elapsed,
                                   cost=book.delta(before))
    _check_book(book)
    if not result.converged and (problem.config or {}).get('reference_raise_on_failure', False):
        raise ReferenceFailure(result)
    return result


solve_reference = solve_socp_reference
