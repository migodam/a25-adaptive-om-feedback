"""A25 numerical extensions of the frozen A24 constrained material TV prox.

No physics/model/prior parameter is selected here.  Certificate steps and
tolerances stay at A24 values even when optimizer steps change.  Every call
requires an owner-checked, charged ledger (explicitly or through active_ledger).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from numbers import Integral
from typing import Mapping
import time

import numpy as np

from a24 import contracts
from a24.contracts import NumericalFailure
from a24.material_updates import (
    _D, _DT, _bounds, _cell_norm, _cell_volume, _coefficient, _count,
    _diagnostics, _grid_shape, _mass_vector, _project_box, _project_dual,
    material_gradient, material_gradient_adjoint, tv_value,
)
from .budget import BudgetExceeded


TOLERANCE = 1e-6
FEASIBILITY_TOLERANCE = 1e-10
MATERIAL_SCALE = 1.0
MAX_ITERATIONS = 20_000
MAX_WALL_SECONDS = 2.0


@dataclass(frozen=True)
class ProxProblem:
    """Inputs in [sqrt(V) Re chi; sqrt(V) Im chi] mass coordinates.

    ``owner_id`` identifies the case/method history, not the ledger job lock.
    The seventh positional argument is this warm-state owner identifier.
    ``algorithm`` overrides config prox_algorithm/algorithm only when supplied.
    """
    v: np.ndarray
    background: np.ndarray
    weight: float
    grid_shape: tuple
    volume: float
    config: Mapping = field(default_factory=dict)
    owner_id: str | None = None
    algorithm: str | None = None


@dataclass(frozen=True)
class ProxWarmState:
    x: np.ndarray
    p: np.ndarray
    v: np.ndarray
    background: np.ndarray
    weight: float
    grid_shape: tuple
    volume: float
    physical_box: tuple
    owner_id: str | None
    algorithm: str
    extrapolated: np.ndarray
    tau: float
    sigma: float
    theta: float
    dual_extrapolated: np.ndarray | None = None
    fgp_t: float = 1.0
    objective_iterations: int = 0
    objective_wall_seconds: float = 0.0


@dataclass
class ProxResult:
    x: np.ndarray
    warm_state: ProxWarmState
    metadata: dict

    @property
    def converged(self):
        return bool(self.metadata['converged'])

    @property
    def meta(self):
        return self.metadata

    @property
    def cost(self):
        return self.metadata.get('cost', {})

    def __iter__(self):
        """Allow x, meta unpacking; warm state remains explicit on the result."""
        yield self.x
        yield self.metadata


class ProxFailure(NumericalFailure):
    def __init__(self, result):
        self.result = result
        self.meta = result.metadata
        super().__init__('A25_TV_PROX_' + self.meta['stop_reason'] + ':' +
                         str(self.meta['iterations']))

    @property
    def warm_state(self):
        return self.result.warm_state


def _resolve_book(budget):
    book = contracts.get_ledger() if budget is None else getattr(budget, 'book', budget)
    for name in ('check', 'span', 'snapshot', 'delta'):
        if not callable(getattr(book, name, None)):
            raise TypeError('CHARGED_LEDGER_REQUIRED:' + name)
    if not hasattr(book, 'counts'):
        raise TypeError('CHARGED_LEDGER_COUNTERS_REQUIRED')
    _check_book(book)
    return book


def _check_book(book):
    # Job lock ownership is deliberately unrelated to a case's warm owner.
    if callable(getattr(book, 'check_owner', None)):
        owner = getattr(book, 'owner_id', getattr(book, 'metadata', {}).get('owner_id'))
        book.check_owner(owner)
    book.check()


def _algorithm(problem):
    config = problem.config or {}
    raw = problem.algorithm or config.get('prox_algorithm', config.get('algorithm',
                                                                      'accelerated_pdhg'))
    aliases = {
        'old': 'old_pdhg', 'pdhg_old': 'old_pdhg', 'old_pdhg': 'old_pdhg',
        'legacy': 'old_pdhg', 'legacy_pdhg': 'old_pdhg',
        'extended': 'extended_pdhg', 'pdhg_extended': 'extended_pdhg',
        'extended_pdhg': 'extended_pdhg', 'fixed_pdhg': 'extended_pdhg',
        'accelerated': 'accelerated_pdhg', 'pdhg_accelerated': 'accelerated_pdhg',
        'accelerated_pdhg': 'accelerated_pdhg', 'accelerated_cp': 'accelerated_pdhg',
        'fgp': 'fgp', 'dual_fgp': 'fgp',
    }
    if raw not in aliases:
        raise ValueError('UNREGISTERED_PROX_ALGORITHM:' + str(raw))
    algorithm = aliases[raw]
    if algorithm == 'fgp' and config.get('fgp_authorized') is not True:
        raise ValueError('FGP_REQUIRES_EXPLICIT_PARENT_AUTHORIZATION')
    return algorithm


def _settings(problem, algorithm):
    config = dict(problem.config or {})
    tolerance = float(config.get('prox_tolerance', TOLERANCE))
    feasibility = float(config.get('prox_feasibility_tolerance', FEASIBILITY_TOLERANCE))
    scale = float(config.get('prox_material_scale', config.get('material_scale', MATERIAL_SCALE)))
    if (tolerance != TOLERANCE or feasibility != FEASIBILITY_TOLERANCE or
            scale != MATERIAL_SCALE):
        raise ValueError('A24_CERTIFICATE_TOLERANCES_AND_MATERIAL_SCALE_ARE_FROZEN')
    cap = 2000 if algorithm == 'old_pdhg' else MAX_ITERATIONS
    max_iter = config.get('prox_max_iter', cap)
    every = config.get('prox_check_every', 10)
    if (isinstance(max_iter, bool) or not isinstance(max_iter, Integral) or
            not 1 <= max_iter <= cap):
        raise ValueError('PROX_ITERATION_CAP:' + str(cap))
    if isinstance(every, bool) or not isinstance(every, Integral) or every < 1:
        raise ValueError('POSITIVE_INTEGER_PROX_CHECK_INTERVAL_REQUIRED')
    wall = float(config.get('prox_wall_limit_seconds', MAX_WALL_SECONDS))
    if not np.isfinite(wall) or not 0 < wall <= MAX_WALL_SECONDS:
        raise ValueError('PROX_WALL_CAP_TWO_SECONDS')
    return config, int(max_iter), int(every), wall


def _prepared(problem):
    if not isinstance(problem, ProxProblem):
        raise TypeError('PROX_PROBLEM_REQUIRED')
    shape = _grid_shape(problem.grid_shape)
    n = int(np.prod(shape))
    volume = _cell_volume(problem.volume)
    v = _mass_vector(problem.v, n, 'v').copy()
    background = _mass_vector(problem.background, n, 'background').copy()
    weight = float(problem.weight)
    if not np.isfinite(weight) or weight < 0:
        raise ValueError('FINITE_NONNEGATIVE_PROXIMAL_WEIGHT_REQUIRED')
    lo, hi, physical_box = _bounds(n, volume, problem.config or {})
    coefficient = _coefficient(shape, volume)
    alpha = weight*coefficient
    scale = MATERIAL_SCALE*np.sqrt(n*volume)
    if (not np.isfinite(alpha) or not np.isfinite(scale) or scale <= 0 or
            not np.isfinite(scale**2) or scale**2 <= 0):
        raise NumericalFailure('MATERIAL_PROX_SCALE_OUTSIDE_FLOAT64_RANGE')
    return shape, n, volume, v, background, weight, lo, hi, physical_box, coefficient, alpha, scale


def certificate(problem, x, p, budget=None):
    """The unchanged A24 diagnostic, always at fixed reference steps.

    This function does no optimizer updates and does not change x or p.
    Independent references should also report their explicit box-dual KKT:
    A24's exact-active-bound stationarity can reject a near-bound IPM point.
    """
    book = _resolve_book(budget)
    algorithm = _algorithm(problem)
    _settings(problem, algorithm)
    shape, n, volume, v, bg, _, lo, hi, _, c, alpha, scale = _prepared(problem)
    x = _mass_vector(x, n, 'certificate_x')
    raw_p = np.asarray(p)
    if np.iscomplexobj(raw_p) or raw_p.shape != shape+(len(shape), 2):
        raise ValueError('REAL_MATERIAL_DUAL_SHAPE_REQUIRED')
    p = np.asarray(raw_p, dtype=np.float64)
    if not np.all(np.isfinite(p)):
        raise ValueError('FINITE_MATERIAL_DUAL_REQUIRED')
    step = .99/(2.*np.sqrt(len(shape)))
    return _enrich_certificate(_diagnostics(x, p, v, bg, shape, volume, alpha, c,
                                           lo, hi, step, step, scale, MATERIAL_SCALE, book),
                               scale, step)


def _enrich_certificate(info, scale, reference_step):
    info = dict(info)
    components = info['kkt_components']
    gap = info['primal_dual_gap']
    info.update(
        certificate_tau=reference_step, certificate_sigma=reference_step,
        certificate_step_policy='fixed_A24_reference_steps',
        primal_stationarity_mass_l2=components['primal_stationarity']*scale,
        primal_stationarity_physical_rms=components['primal_stationarity']*MATERIAL_SCALE,
        dual_fixed_point_mass_l2=components['dual_fixed_point']*scale,
        dual_feasibility_mass_l2=components['dual_feasibility']*scale,
        primal_error_bound_mass=(float(np.sqrt(2.*gap)) if gap >= 0 else None),
        primal_error_bound_physical_rms=(float(np.sqrt(2.*gap)/scale)*MATERIAL_SCALE
                                         if gap >= 0 else None),
        primal_error_bound_assumptions='feasible primal and dual; floating point roundoff excluded',
    )
    return info


def _accepted(info):
    values = (info['kkt_residual'], info['normalized_gap'], info['feasibility'])
    return (all(np.isfinite(value) for value in values) and
            info['kkt_residual'] <= TOLERANCE and info['normalized_gap'] <= TOLERANCE and
            info['feasibility'] <= FEASIBILITY_TOLERANCE)


def _validate_warm(problem, state, shape, n, volume, background, physical_box):
    if not isinstance(state, ProxWarmState):
        raise TypeError('PROX_WARM_STATE_REQUIRED')
    if state.owner_id != problem.owner_id:
        raise ValueError('FOREIGN_CASE_OR_METHOD_WARM_STATE')
    if (tuple(state.grid_shape) != shape or state.volume != volume or
            tuple(state.physical_box) != tuple(physical_box) or
            not np.array_equal(state.background, background)):
        raise ValueError('INCOMPATIBLE_PROX_WARM_STATE_GEOMETRY_BACKGROUND_OR_BOX')
    _mass_vector(state.x, n, 'warm_x')
    _mass_vector(state.v, n, 'warm_v')
    _mass_vector(state.extrapolated, n, 'warm_extrapolated')
    if (np.iscomplexobj(state.p) or np.shape(state.p) != shape+(len(shape), 2) or
            not np.all(np.isfinite(state.p))):
        raise ValueError('FINITE_REAL_WARM_DUAL_REQUIRED')
    if (not isinstance(state.objective_iterations, Integral) or state.objective_iterations < 0 or
            not np.isfinite(state.objective_wall_seconds) or state.objective_wall_seconds < 0):
        raise ValueError('VALID_CUMULATIVE_WARM_COST_REQUIRED')
    if (not np.isfinite(state.tau) or state.tau <= 0 or not np.isfinite(state.sigma) or
            state.sigma <= 0 or not np.isfinite(state.theta) or not 0 < state.theta <= 1):
        raise ValueError('VALID_WARM_OPTIMIZER_STEPS_REQUIRED')
    if state.dual_extrapolated is not None:
        if (np.iscomplexobj(state.dual_extrapolated) or
                np.shape(state.dual_extrapolated) != np.shape(state.p) or
                not np.all(np.isfinite(state.dual_extrapolated))):
            raise ValueError('FINITE_REAL_FGP_EXTRAPOLATED_DUAL_REQUIRED')
    if not np.isfinite(state.fgp_t) or state.fgp_t < 1:
        raise ValueError('VALID_FGP_MOMENTUM_REQUIRED')


def _core(problem, warm_state, book, started):
    algorithm = _algorithm(problem)
    config, max_iter, every, wall_limit = _settings(problem, algorithm)
    shape, n, volume, v, bg, weight, lo, hi, box, c, alpha, scale = _prepared(problem)
    norm_bound = 2.*np.sqrt(len(shape))
    reference_step = .99/norm_bound
    tau = sigma = reference_step
    theta = 1.
    fgp_t = 1.
    objective_prior_iterations = 0
    objective_prior_wall = 0.
    same_objective = resume_momentum = False
    if warm_state is None:
        x = _project_box(v.copy(), lo, hi, book)
        p = np.zeros(shape+(len(shape), 2), dtype=np.float64)
        extrapolated = x.copy()
        dual_extrapolated = p.copy()
    else:
        if algorithm == 'old_pdhg':
            raise ValueError('OLD_A24_CONTROL_REQUIRES_COLD_START')
        _validate_warm(problem, warm_state, shape, n, volume, bg, box)
        same_objective = (warm_state.weight == weight and np.array_equal(warm_state.v, v))
        resume_momentum = same_objective and warm_state.algorithm == algorithm
        x = _project_box(np.asarray(warm_state.x).copy(), lo, hi, book)
        p = _project_dual(np.asarray(warm_state.p).copy(), alpha, book)
        _count(book, 'a25_warm_start_calls')
        if same_objective:
            objective_prior_iterations = int(warm_state.objective_iterations)
            objective_prior_wall = float(warm_state.objective_wall_seconds)
        if resume_momentum:
            tau, sigma, theta = warm_state.tau, warm_state.sigma, warm_state.theta
            extrapolated = np.asarray(warm_state.extrapolated).copy()
            dual_extrapolated = (p.copy() if warm_state.dual_extrapolated is None else
                                 np.asarray(warm_state.dual_extrapolated).copy())
            fgp_t = warm_state.fgp_t
        else:
            extrapolated = x.copy()
            dual_extrapolated = p.copy()

    def diagnose():
        return _enrich_certificate(_diagnostics(x, p, v, bg, shape, volume, alpha, c,
                                               lo, hi, reference_step, reference_step,
                                               scale, MATERIAL_SCALE, book),
                                   scale, reference_step)

    info = diagnose()
    converged = _accepted(info)
    iterations = 0
    stop_reason = 'CONVERGED' if converged else 'ITERATION_LIMIT'
    deadline = started + max(0., wall_limit-objective_prior_wall)
    remaining = max(0, max_iter-objective_prior_iterations)
    last_checked_iteration = 0
    for _ in range(remaining if not converged else 0):
        _check_book(book)
        if time.perf_counter() >= deadline:
            stop_reason = 'WALL_LIMIT'
            break
        if algorithm == 'fgp':
            # Smooth dual ascent, with ||grad(-dual)|| Lipschitz <= 4d.
            q = _project_box(v-_DT(dual_extrapolated, shape, book), lo, hi, book)
            previous_dual = p
            p = _project_dual(dual_extrapolated+(.99/norm_bound**2)*_D(q-bg, shape, book),
                              alpha, book)
            x = _project_box(v-_DT(p, shape, book), lo, hi, book)
            next_t = .5*(1.+np.sqrt(1.+4.*fgp_t**2))
            dual_extrapolated = p+((fgp_t-1.)/next_t)*(p-previous_dual)
            fgp_t = next_t
            extrapolated = x.copy()
        else:
            p = _project_dual(p+sigma*_D(extrapolated-bg, shape, book), alpha, book)
            previous = x
            x = _project_box((previous-tau*_DT(p, shape, book)+tau*v)/(1.+tau), lo, hi, book)
            if algorithm == 'accelerated_pdhg':
                # CP Algorithm 2, gamma=1 for .5||x-v||^2 + I_box.
                theta = 1./np.sqrt(1.+2.*tau)
                tau *= theta
                sigma /= theta
            extrapolated = x+theta*(x-previous)
        iterations += 1
        _count(book, 'material_prox_iterations')
        _count(book, 'a25_prox_iterations')
        if iterations % every == 0 or iterations == remaining:
            info = diagnose()
            last_checked_iteration = iterations
            converged = _accepted(info)
            if converged:
                stop_reason = 'CONVERGED'
                break
    if last_checked_iteration != iterations:
        info = diagnose()
        converged = _accepted(info)
        if converged:
            stop_reason = 'CONVERGED'
    elapsed = time.perf_counter()-started
    # Never accept convergence first observed beyond the declared inclusive cap.
    if elapsed+objective_prior_wall > wall_limit:
        converged = False
        stop_reason = 'WALL_LIMIT'
    _check_book(book)
    state = ProxWarmState(
        x=x.copy(), p=p.copy(), v=v, background=bg, weight=weight,
        grid_shape=shape, volume=volume, physical_box=tuple(box), owner_id=problem.owner_id,
        algorithm=algorithm, extrapolated=extrapolated.copy(), tau=float(tau),
        sigma=float(sigma), theta=float(theta), dual_extrapolated=dual_extrapolated.copy(),
        fgp_t=float(fgp_t), objective_iterations=objective_prior_iterations+iterations,
        objective_wall_seconds=objective_prior_wall+elapsed,
    )
    meta = {**info, 'status': 'CONVERGED' if converged else 'NOT_CONVERGED',
            'converged': bool(converged), 'stop_reason': stop_reason, 'algorithm': algorithm,
            'iterations': iterations, 'max_iter': max_iter, 'wall_limit_seconds': wall_limit,
            'elapsed_seconds': elapsed, 'objective_prior_iterations': objective_prior_iterations,
            'objective_prior_wall_seconds': objective_prior_wall,
            'objective_total_iterations': state.objective_iterations,
            'objective_total_wall_seconds': state.objective_wall_seconds,
            'warm_start': warm_state is not None, 'same_objective_continuation': same_objective,
            'optimizer_momentum_resumed': resume_momentum, 'owner_id': problem.owner_id,
            'tolerance': TOLERANCE, 'feasibility_tolerance': FEASIBILITY_TOLERANCE,
            'physical_material_scale': MATERIAL_SCALE, 'physical_mass_scale': float(scale),
            'weight': weight, 'dual_ball_radius': float(alpha), 'tv_physical_coefficient': float(c),
            'grid_shape': list(shape), 'volume': volume, 'physical_box': box.tolist(),
            'difference_operator_norm_upper_bound': float(norm_bound),
            'tau': float(tau), 'sigma': float(sigma), 'theta': float(theta),
            'tau_sigma_norm_bound_squared': float(tau*sigma*norm_bound**2),
            'array_bytes_estimate': int(8*(12*len(x)+8*p.size+5*n)),
            'normalization': 'material_scale * sqrt(number_of_cells * cell_volume)',
            'prior_changed': False, 'post_solve_primal_projection': False}
    if not converged:
        _count(book, 'material_prox_failures')
        _count(book, 'a25_prox_failures')
    return ProxResult(x, state, meta), config


def solve_prox(problem: ProxProblem, warm_state: ProxWarmState | None = None,
               budget=None) -> ProxResult:
    """Solve the frozen objective, returning primal, warm state, certificate/cost.

    Modes: old_pdhg (cold 2000 cap), extended_pdhg, accelerated_pdhg (20000
    cap), and explicitly parent-authorized fgp.  Same-objective continuations
    share the iteration/wall allowance; changing numerical modes cannot reset
    it. Different outer objectives reset optimizer momentum but reuse x,p.
    Failures raise ProxFailure by default and carry result/meta/warm_state.
    Owner-budget exhaustion propagates BudgetExceeded and is never recovered.
    """
    started = time.perf_counter()
    if not isinstance(problem, ProxProblem):
        raise TypeError('PROX_PROBLEM_REQUIRED')
    book = _resolve_book(budget)
    before = book.snapshot()
    result = None
    try:
        with book.span('a25_material_tv_prox', material_prox_calls=1, a25_prox_calls=1) as row:
            result, config = _core(problem, warm_state, book, started)
            row.update(result_status=result.metadata['status'],
                       stop_reason=result.metadata['stop_reason'],
                       algorithm=result.metadata['algorithm'], iterations=result.metadata['iterations'],
                       kkt_residual=result.metadata['kkt_residual'],
                       normalized_gap=result.metadata['normalized_gap'],
                       feasibility=result.metadata['feasibility'])
            if not result.converged and config.get('prox_raise_on_failure', True):
                raise ProxFailure(result)
    except ProxFailure:
        raise
    except BudgetExceeded as exc:
        exc.meta = {'status': 'OWNER_BUDGET_EXCEEDED', 'converged': False,
                    'elapsed_seconds': time.perf_counter()-started, 'cost': book.delta(before)}
        raise
    finally:
        if result is not None:
            elapsed = time.perf_counter()-started
            total = result.metadata['objective_prior_wall_seconds']+elapsed
            if total > result.metadata['wall_limit_seconds']:
                if result.converged:
                    book.counts['material_prox_failures'] += 1
                    book.counts['a25_prox_failures'] += 1
                result.metadata.update(status='NOT_CONVERGED', converged=False,
                                       stop_reason='WALL_LIMIT')
            result.metadata.update(elapsed_seconds=elapsed, objective_total_wall_seconds=total,
                                   cost=book.delta(before))
            result.warm_state = replace(result.warm_state, objective_wall_seconds=total)
    _check_book(book)
    if not result.converged and config.get('prox_raise_on_failure', True):
        raise ProxFailure(result)
    return result


def prox_tv_box(v, background, weight, grid_shape, volume, config, book=None):
    """Thin legacy-shaped bridge. Use solve_prox directly for warm states."""
    result = solve_prox(ProxProblem(v, background, weight, grid_shape, volume, config),
                        budget=book)
    return result.x, result.metadata
