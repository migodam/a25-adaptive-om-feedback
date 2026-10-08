"""Parent-run numerical tests only, inside a charged active_ledger context.

FGP is guarded but is not numerically executed by this suite. Reference tests
report explicit skips if the parent's isolated Clarabel installation is absent.
"""
from dataclasses import replace
import importlib.util
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from a24 import contracts
from a24.contracts import mass_pack, mass_unpack
from a24.material_updates import material_gradient, material_gradient_adjoint
from a25.budget import BudgetExceeded
from a25.prox import (ProxFailure, ProxProblem, certificate, solve_prox, tv_value)
from a25.socp_reference import (_acceptance, _feasible_envelope, _reference_settings,
                                assemble_socp, difference_matrix, solve_socp_reference)


class A25ProxTests(unittest.TestCase):
    def setUp(self):
        self.book = contracts.get_ledger()
        self.book.check()
        self.book.counts['a25_solver_unit_test_cases'] += 1
        self.addCleanup(self.book.check)
        self.config = {'prox_algorithm': 'extended_pdhg', 'prox_max_iter': 2000,
                       'prox_tolerance': 1e-6, 'prox_check_every': 10,
                       'prox_material_scale': 1., 'prox_raise_on_failure': True}

    def problem(self, chi_v=None, chi_b=None, weight=.05, shape=(2,), volume=1., **config):
        if chi_v is None:
            chi_v = np.array([0.+.1j, 1.+.3j])
        if chi_b is None:
            chi_b = np.full(len(chi_v), .1+.04j)
        return ProxProblem(mass_pack(np.asarray(chi_v), volume),
                           mass_pack(np.asarray(chi_b), volume), weight, shape, volume,
                           {**self.config, **config}, 'unit:case:L')

    def assert_certificate(self, result):
        meta = result.metadata
        self.assertTrue(result.converged, meta)
        self.assertLessEqual(meta['kkt_residual'], 1e-6)
        self.assertLessEqual(meta['normalized_gap'], 1e-6)
        self.assertLessEqual(meta['feasibility'], 1e-10)
        expected = .99/(2.*np.sqrt(len(meta['grid_shape'])))
        self.assertEqual(meta['certificate_tau'], expected)
        self.assertEqual(meta['certificate_sigma'], expected)
        self.assertIn('cost', meta)
        self.assertFalse(meta['post_solve_primal_projection'])

    def require_reference(self):
        if importlib.util.find_spec('clarabel') is None:
            self.skipTest('Independent Clarabel 0.11.1 reference NOT_RUN: dependency absent')

    def test_zero_tv_box_solution_and_counting_for_all_pdhg_modes(self):
        for algorithm in ('old_pdhg', 'extended_pdhg', 'accelerated_pdhg'):
            problem = self.problem(np.array([-2.-.2j, 5.+.9j]), weight=0.,
                                   prox_algorithm=algorithm)
            before = self.book.counts['material_box_projections']
            result = solve_prox(problem, budget=self.book)
            np.testing.assert_array_equal(mass_unpack(result.x, 1.), [-.5+0.j, 4.+.5j])
            self.assertEqual(result.metadata['iterations'], 0)
            self.assertGreater(self.book.counts['material_box_projections'], before)
            self.assert_certificate(result)

    def test_joint_two_cell_closed_form_and_physical_error_bound(self):
        problem = self.problem()
        result = solve_prox(problem, budget=self.book)
        difference = (1.-.1/np.linalg.norm([1., .2]))*np.array([1., .2])
        low, high = np.array([.5, .2])-.5*difference, np.array([.5, .2])+.5*difference
        expected = np.array([low[0]+1j*low[1], high[0]+1j*high[1]])
        np.testing.assert_allclose(mass_unpack(result.x, 1.), expected, atol=5e-6, rtol=0.)
        error = float(np.linalg.norm(result.x-mass_pack(expected, 1.)))
        self.assertLessEqual(error, result.metadata['primal_error_bound_mass']+1e-11)
        self.assert_certificate(result)

    def test_fused_two_cell_solution(self):
        result = solve_prox(self.problem(weight=1.), budget=self.book)
        np.testing.assert_allclose(mass_unpack(result.x, 1.), np.full(2, .5+.2j),
                                   atol=5e-6, rtol=0.)
        self.assert_certificate(result)

    def test_active_box_solution_from_known_joint_kkt(self):
        expected = np.array([3.5+.1j, 4.+.3j])
        direction = np.array([.5, .2])
        dual = .2*direction/np.linalg.norm(direction)
        dt_dual = np.array([-dual[0], dual[0], -dual[1], dual[1]])
        problem = self.problem(weight=.2)
        problem = replace(problem, v=mass_pack(expected, 1.)+dt_dual+[0., .4, 0., 0.])
        result = solve_prox(problem, budget=self.book)
        np.testing.assert_allclose(mass_unpack(result.x, 1.), expected, atol=5e-6, rtol=0.)
        self.assertLessEqual(np.max(mass_unpack(result.x, 1.).real), 4.)
        self.assert_certificate(result)

    def test_fixed_certificate_cannot_be_shrunk_by_large_internal_sigma(self):
        problem = self.problem(np.array([0.+0.j, 1.+0.j]), chi_b=np.zeros(2, complex),
                               weight=.01)
        p = np.zeros((2, 1, 2))
        info = certificate(problem, problem.v, p, budget=self.book)
        self.assertGreater(info['kkt_components']['dual_fixed_point'], 1e-6)
        # The misleading residual is small merely because the divisor is huge.
        misleading = problem.weight/(1e9*np.sqrt(2.))
        self.assertLess(misleading, 1e-6)
        self.assertEqual(info['certificate_sigma'], .99/2.)

    def test_acceleration_changes_optimizer_steps_but_not_certificate_steps(self):
        problem = self.problem(weight=.8, prox_algorithm='accelerated_pdhg',
                               prox_max_iter=1, prox_check_every=1, prox_raise_on_failure=False)
        result = solve_prox(problem, budget=self.book)
        initial_step = .99/2.
        expected_theta = 1./np.sqrt(1.+2.*initial_step)
        self.assertAlmostEqual(result.warm_state.theta, expected_theta)
        self.assertAlmostEqual(result.warm_state.tau, initial_step*expected_theta)
        self.assertAlmostEqual(result.warm_state.sigma, initial_step/expected_theta)
        self.assertEqual(result.metadata['certificate_sigma'], initial_step)
        self.assertFalse(result.converged)

    def test_warm_continuation_matches_two_fixed_steps_and_keeps_cumulative_cap(self):
        problem = self.problem(np.array([0.+.05j, 1.+.1j, .5+.45j, 2.+.3j]),
                               weight=.8, shape=(2, 2), prox_max_iter=1,
                               prox_check_every=1, prox_raise_on_failure=False)
        first = solve_prox(problem, budget=self.book)
        problem_two = replace(problem, config={**problem.config, 'prox_max_iter': 2})
        continued = solve_prox(problem_two, first.warm_state, self.book)
        cold = solve_prox(problem_two, budget=self.book)
        np.testing.assert_allclose(continued.x, cold.x, atol=2e-13, rtol=0.)
        np.testing.assert_allclose(continued.warm_state.p, cold.warm_state.p, atol=2e-13, rtol=0.)
        self.assertEqual(continued.metadata['iterations'], 1)
        self.assertEqual(continued.metadata['objective_total_iterations'], 2)
        self.assertTrue(continued.metadata['optimizer_momentum_resumed'])
        exhausted = solve_prox(problem_two, continued.warm_state, self.book)
        self.assertEqual(exhausted.metadata['iterations'], 0)
        self.assertFalse(exhausted.converged)

    def test_weight_change_reprojects_dual_resets_momentum_and_preserves_inputs(self):
        problem = self.problem(weight=.8, prox_algorithm='accelerated_pdhg',
                               prox_max_iter=1, prox_check_every=1, prox_raise_on_failure=False)
        first = solve_prox(problem, budget=self.book)
        old_x, old_p = first.warm_state.x.copy(), first.warm_state.p.copy()
        changed = replace(problem, weight=.01)
        result = solve_prox(changed, first.warm_state, self.book)
        self.assertFalse(result.metadata['same_objective_continuation'])
        self.assertFalse(result.metadata['optimizer_momentum_resumed'])
        self.assertEqual(result.metadata['objective_prior_iterations'], 0)
        self.assertLessEqual(np.max(np.linalg.norm(result.warm_state.p.reshape(2, -1), axis=1)),
                             result.metadata['dual_ball_radius']+1e-14)
        np.testing.assert_array_equal(first.warm_state.x, old_x)
        np.testing.assert_array_equal(first.warm_state.p, old_p)

    def test_warm_owner_and_background_incompatibilities_fail(self):
        problem = self.problem(prox_max_iter=1, prox_raise_on_failure=False)
        first = solve_prox(problem, budget=self.book)
        with self.assertRaisesRegex(ValueError, 'FOREIGN_CASE'):
            solve_prox(replace(problem, owner_id='other:case:R'), first.warm_state, self.book)
        with self.assertRaisesRegex(ValueError, 'INCOMPATIBLE'):
            solve_prox(replace(problem, background=problem.background+.01), first.warm_state, self.book)

    def test_numerical_failure_keeps_result_state_and_counts(self):
        problem = self.problem(weight=.8, prox_max_iter=1)
        before = self.book.counts['a25_prox_failures']
        with self.assertRaises(ProxFailure) as caught:
            solve_prox(problem, budget=self.book)
        self.assertFalse(caught.exception.result.converged)
        self.assertEqual(caught.exception.meta['iterations'], 1)
        self.assertIn('cost', caught.exception.meta)
        self.assertEqual(caught.exception.warm_state.owner_id, problem.owner_id)
        self.assertEqual(self.book.counts['a25_prox_failures'], before+1)

    def test_local_wall_cap_failure_without_sleep_or_clocking_owner_budget(self):
        calls = [0]

        def local_clock():
            calls[0] += 1
            return 100. if calls[0] == 1 else 103.

        problem = self.problem(weight=.8, prox_raise_on_failure=False)
        # Replace only this module's time binding. Ledger clocks stay real.
        with patch('a25.prox.time', SimpleNamespace(perf_counter=local_clock)):
            result = solve_prox(problem, budget=self.book)
        self.assertFalse(result.converged)
        self.assertEqual(result.metadata['stop_reason'], 'WALL_LIMIT')
        self.assertEqual(result.metadata['iterations'], 0)

    def test_owner_budget_stop_propagates_without_fallback(self):
        with patch.object(self.book, 'check', side_effect=BudgetExceeded('synthetic budget stop')):
            with self.assertRaises(BudgetExceeded):
                solve_prox(self.problem(), budget=self.book)

    def test_frozen_tolerances_caps_old_control_and_fgp_guard(self):
        for config in ({'prox_tolerance': 2e-6}, {'prox_material_scale': 2.},
                       {'prox_feasibility_tolerance': 2e-10}, {'prox_max_iter': 20001},
                       {'prox_wall_limit_seconds': 2.1},
                       {'prox_algorithm': 'old_pdhg', 'prox_max_iter': 2001},
                       {'prox_algorithm': 'fgp'}):
            with self.assertRaises(ValueError):
                solve_prox(self.problem(**config), budget=self.book)
        first = solve_prox(self.problem(weight=0.), budget=self.book)
        with self.assertRaisesRegex(ValueError, 'COLD_START'):
            solve_prox(self.problem(weight=0., prox_algorithm='old_pdhg'),
                       first.warm_state, self.book)

    def test_independent_sparse_difference_and_real_adjoint_two_and_three_dimensions(self):
        rng = np.random.default_rng(251008083)
        for shape in ((3, 4), (2, 3, 2)):
            n = int(np.prod(shape))
            D = difference_matrix(shape, self.book)
            x, p = rng.normal(size=2*n), rng.normal(size=shape+(len(shape), 2))
            np.testing.assert_allclose(D@x, material_gradient(x, shape).reshape(-1),
                                       atol=1e-13, rtol=0.)
            np.testing.assert_allclose(D.T@p.reshape(-1), material_gradient_adjoint(p, shape),
                                       atol=1e-13, rtol=0.)
            self.assertAlmostEqual(float((D@x)@p.reshape(-1)), float(x@(D.T@p.reshape(-1))),
                                   places=12)

    def test_independent_socp_epigraph_sign_and_physical_tv_scaling(self):
        shape, volume = (2, 1, 1), .008
        problem = self.problem(np.array([0.+.1j, 1.+.3j]), weight=.02,
                               shape=shape, volume=volume)
        data = assemble_socp(problem, self.book)
        gradient = np.asarray(data.difference@(problem.v-problem.background)).reshape(2, -1)
        t = np.linalg.norm(gradient, axis=1)
        z = np.concatenate((problem.v, t))
        slack = data.b-data.A@z
        soc = slack[8:].reshape(2, 7)
        np.testing.assert_allclose(soc[:, 0], t, atol=1e-14, rtol=0.)
        np.testing.assert_allclose(soc[:, 1:], gradient, atol=1e-14, rtol=0.)
        self.assertAlmostEqual(data.coefficient*np.sum(t),
                               tv_value(problem.v-problem.background, shape, volume), places=13)
        objective = .5*float(z@(data.P@z))+float(data.q@z)+.5*float(problem.v@problem.v)
        self.assertAlmostEqual(objective, problem.weight*tv_value(
            problem.v-problem.background, shape, volume), places=13)

    def test_certificate_envelope_handles_roundoff_and_leaves_raw_arrays_unchanged(self):
        expected = np.array([3.5+.1j, 4.+.3j])
        direction = np.array([.5, .2])
        dual = .2*direction/np.linalg.norm(direction)
        p = np.zeros((2, 1, 2)); p[0, 0] = dual*(1.+8.*np.finfo(float).eps)
        x = mass_pack(expected, 1.); x[1] += 8.*np.finfo(float).eps
        dt_dual = np.array([-dual[0], dual[0], -dual[1], dual[1]])
        problem = replace(self.problem(weight=.2),
                          v=mass_pack(expected, 1.)+dt_dual+[0., .4, 0., 0.])
        data = assemble_socp(problem, self.book)
        raw_x, raw_p = x.copy(), p.copy()
        envelope = _feasible_envelope(data, x, p, self.book)
        np.testing.assert_array_equal(x, raw_x)
        np.testing.assert_array_equal(p, raw_p)
        self.assertEqual(envelope['status'], 'FEASIBLE_NUMERICAL_ENVELOPE')
        self.assertFalse(envelope['raw_output_changed'])
        self.assertGreater(envelope['primal_correction_mass_l2'], 0.)
        self.assertLessEqual(np.linalg.norm(x-mass_pack(expected, 1.)),
                             envelope['primal_error_bound_mass'])

    def test_almost_solved_needs_strict_raw_certificate_and_cap_status_never_passes(self):
        keys = ('explicit_box_dual_stationarity', 'epigraph_dual_stationarity',
                'box_dual_feasibility', 'soc_dual_feasibility', 'dual_ball_feasibility',
                'soc_primal_feasibility', 'box_complementarity', 'soc_complementarity',
                'tv_complementarity')
        cert = {'kkt_residual': 1e-12, 'normalized_gap': 1e-12, 'feasibility': 0.,
                'kkt_components': dict.fromkeys(keys, 1e-12)}
        accepted, meta = _acceptance('AlmostSolved', cert, True)
        self.assertTrue(accepted)
        self.assertEqual(meta['acceptance_reason'], 'strict_external_reference_certificate')
        bad = {**cert, 'kkt_residual': 1e-8,
               'kkt_components': {**cert['kkt_components'], 'explicit_box_dual_stationarity': 1e-8}}
        self.assertFalse(_acceptance('AlmostSolved', bad, True)[0])
        self.assertFalse(_acceptance('MaxIterations', cert, True)[0])
        self.assertFalse(_acceptance('Solved', cert, False)[0])

    def test_explicit_reference_refinement_tightens_internals_only(self):
        problem = self.problem()
        profile, default = _reference_settings(problem, 200, 4.)
        self.assertEqual(profile, 'default')
        self.assertEqual(default['tol_feas'], 1e-11)
        tight_problem = replace(problem, config={**problem.config, 'reference_refinement': True})
        profile, tight = _reference_settings(tight_problem, 200, 4.)
        self.assertEqual(profile, 'tight_accuracy')
        self.assertLess(tight['tol_feas'], default['tol_feas'])
        self.assertLess(tight['tol_gap_abs'], default['tol_gap_abs'])
        self.assertEqual(tight['max_iter'], 200)
        self.assertEqual(tight['time_limit'], 4.)
        self.assertEqual(tight_problem.config['prox_tolerance'], 1e-6)

    def test_independent_reference_matches_closed_form_and_pd_prox(self):
        self.require_reference()
        problem = self.problem()
        result = solve_prox(problem, budget=self.book)
        reference = solve_socp_reference(problem, self.book, comparison=result)
        self.assertTrue(reference.converged, reference.metadata)
        self.assertTrue(reference.metadata['raw_primal_preserved'])
        self.assertTrue(reference.metadata['raw_dual_preserved'])
        self.assertTrue(reference.metadata['objective_agreement_passed'])
        self.assertTrue(reference.metadata['robust_primal_distance_agreement'])
        self.assertIn('legacy_certificate', reference.metadata)
        self.assertEqual(reference.metadata['clarabel_version'], '0.11.1')
        self.assertLessEqual(reference.metadata['feasibility'], 1e-10)

    def test_active_box_reference_retains_raw_multiplier_certificate(self):
        self.require_reference()
        expected = np.array([3.5+.1j, 4.+.3j])
        direction = np.array([.5, .2])
        dual = .2*direction/np.linalg.norm(direction)
        dt_dual = np.array([-dual[0], dual[0], -dual[1], dual[1]])
        problem = replace(self.problem(weight=.2),
                          v=mass_pack(expected, 1.)+dt_dual+[0., .4, 0., 0.])
        reference = solve_socp_reference(problem, self.book)
        self.assertTrue(reference.converged, reference.metadata)
        exact_mass = mass_pack(expected, 1.)
        self.assertLessEqual(float(np.linalg.norm(reference.x-exact_mass)),
                             reference.metadata['robust_primal_error_bound_mass'])
        exact_objective = (.5*float((exact_mass-problem.v)@(exact_mass-problem.v))+
                           problem.weight*np.linalg.norm(direction))
        self.assertLessEqual(abs(reference.metadata['objective']-exact_objective), 1e-10)
        self.assertGreater(reference.upper_dual[1], .39)
        self.assertLessEqual(reference.metadata['kkt_components']['explicit_box_dual_stationarity'], 1e-6)
        self.assertFalse(reference.metadata['post_solve_primal_projection'])

    def test_reference_iteration_failure_keeps_raw_status(self):
        self.require_reference()
        reference = solve_socp_reference(self.problem(), self.book, max_iter=1)
        self.assertFalse(reference.converged)
        self.assertIn(reference.metadata['solver_status'], ('MaxIterations', 'InsufficientProgress'))
        self.assertIn('cost', reference.metadata)


if __name__ == '__main__':
    raise SystemExit('Run only in the parent charged A25 active_ledger context.')
