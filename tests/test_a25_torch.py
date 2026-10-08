"""Tiny, charged A25 identities. Run only inside the parent's active ledger."""
from __future__ import annotations

import unittest
import numpy as np
import torch

from a24.contracts import NumericalFailure, get_ledger, mass_pack as np_mass_pack, pack as np_pack
from a24.physics import Physics2D
from a24.relative_feedback import ReferenceCache, RelativeFeedbackModel
from a25.torch_physics import TorchReference, TorchRelativeModel, mass_pack, pack_data, require_device
from a25.networks import FeatureNormalizer, build_model, assert_parameter_match, symmetric_features
from a25.training import ParentDataset, ParentSampler, select_update_budget, tv_material, matched_loss


class TorchPhysicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = get_ledger()
        torch.set_num_threads(1)
        cls.config = {"core_relative_sigma_min": 1e-10, "core_condition_cap": 1e10,
                      "training": {"material_width": 4, "main_blocks": 3}}
        with cls.book.span("a25_tiny_torch_fixture", tiny_fixture_builds=1):
            cls.physics = Physics2D(8, book=cls.book, config=cls.config)
            cls.chi_b = np.full(cls.physics.n, .1 + .04j, dtype=np.complex128)
            cls.cache = ReferenceCache(cls.physics, cls.chi_b, cls.book, cls.config)
            cls.reference = TorchReference.from_cache(cls.cache, rank=3, seed=241008,
                                                     book=cls.book, config=cls.config)
            cls.rng = np.random.default_rng(251008)
            cls.chi = cls.chi_b + .12 + .03 * cls.rng.random(cls.physics.n) + .02j

    def _mass(self):
        return torch.tensor(np_mass_pack(self.chi, self.physics.volume), dtype=torch.float64)

    def test_numpy_identity_and_real_packing(self):
        with self.book.span("a25_torch_numpy_identity"):
            for kind in ("L", "R"):
                old = RelativeFeedbackModel(self.cache, kind, rank=3, seed=241008, config=self.config)
                expected = old.forward(self.chi)
                model = TorchRelativeModel(self.reference, kind)
                actual = model(self._mass())
                for name in ("data", "w", "field"):
                    np.testing.assert_allclose(getattr(actual, name).detach().numpy(), getattr(expected, name),
                                               rtol=1e-11, atol=1e-12)
                np.testing.assert_allclose(pack_data(actual.data).numpy(), np_pack(expected.data), atol=1e-12)
                canonical = self.cache.state_b.current + self.cache.solve_ref(expected.w)
                np.testing.assert_allclose(actual.current.numpy(), canonical, rtol=1e-11, atol=1e-12)
                np.testing.assert_allclose((self.reference.S @ actual.current).numpy(), expected.data,
                                           rtol=1e-11, atol=1e-12)

    def test_jvp_and_strict_discrete_adjoint(self):
        with self.book.span("a25_torch_discrete_adjoint"):
            for kind in ("L", "R"):
                model = TorchRelativeModel(self.reference, kind)
                mass = self._mass().requires_grad_()
                state = model(mass, recover_current=False)
                direction = torch.tensor(self.rng.standard_normal(2 * self.physics.n), dtype=torch.float64)
                load = torch.tensor(self.rng.standard_normal(2 * self.physics.q * self.physics.s), dtype=torch.float64)
                tangent = model.jvp(mass, direction, state)
                pullback = model.adjoint(mass, load, state)
                self.assertAlmostEqual(float(torch.dot(tangent, load)), float(torch.dot(direction, pullback)), delta=1e-10)
                automatic = torch.autograd.grad(torch.dot(pack_data(state.data), load), mass, create_graph=True)[0]
                torch.testing.assert_close(pullback, automatic, rtol=1e-10, atol=1e-11)
                epsilon = 1e-6
                plus = pack_data(model(mass + epsilon * direction, recover_current=False).data)
                minus = pack_data(model(mass - epsilon * direction, recover_current=False).data)
                torch.testing.assert_close(tangent, (plus - minus) / (2 * epsilon), rtol=1e-6, atol=1e-8)

    def test_state_gradient_retains_higher_derivative(self):
        with self.book.span("a25_torch_higher_gradient"):
            model = TorchRelativeModel(self.reference, "R")
            mass = self._mass().requires_grad_()
            observation = self.reference.yb * (1.03 + .01j)
            state = model(mass, recover_current=False)
            gradient = model.data_gradient(mass, observation, state)
            direct = torch.autograd.grad(.5 * (state.data - observation).abs().square().sum()
                                         / self.reference.yb_norm2, mass, create_graph=True)[0]
            torch.testing.assert_close(gradient, direct, rtol=1e-10, atol=1e-11)
            direction = torch.tensor(self.rng.standard_normal(2 * self.physics.n) * .01, dtype=torch.float64)
            hessian_direction = torch.autograd.grad(torch.dot(gradient, direction), mass)[0]
            epsilon = 1e-5
            plus = mass.detach() + epsilon * direction
            minus = mass.detach() - epsilon * direction
            finite = (model.data_gradient(plus, observation) - model.data_gradient(minus, observation)) / (2 * epsilon)
            torch.testing.assert_close(hessian_direction, finite, rtol=2e-6, atol=1e-8)

    def test_source_symmetric_features(self):
        with self.book.span("a25_source_symmetry"):
            permutation = np.array([3, 0, 6, 1, 7, 2, 5, 4])
            arrays = {key: getattr(self.reference, key).detach().numpy().copy()
                      for key in ("chi_b", "eb", "yb", "Db", "G", "S", "incident", "Ug", "Vg")}
            for key in ("eb", "yb", "incident"):
                arrays[key] = arrays[key][:, permutation]
            permuted = TorchReference(arrays, volume=self.physics.volume, grid=self.physics.grid,
                                      book=self.book, config=self.config, fixed_step=float(self.reference.step))
            first, second = TorchRelativeModel(self.reference, "R"), TorchRelativeModel(permuted, "R")
            mass = self._mass()[None]
            observation = self.reference.yb[None] * 1.02
            initial = mass.clone()
            s1, s2 = first(mass), second(mass)
            g1 = first.data_gradient(mass, observation, s1)
            g2 = second.data_gradient(mass, observation[:, :, permutation], s2)
            f1 = symmetric_features(self.reference, mass, g1, s1, initial)
            f2 = symmetric_features(permuted, mass, g2, s2, initial)
            torch.testing.assert_close(f1, f2, rtol=1e-11, atol=1e-12)

    def test_singular_core_is_rejected(self):
        with self.book.span("a25_singular_core_counterexample"):
            arrays = {key: getattr(self.reference, key).detach().numpy().copy()
                      for key in ("chi_b", "eb", "yb", "Db", "G", "S", "incident")}
            arrays.update(Ug=np.eye(self.physics.n, 1, dtype=np.complex128), Vg=np.eye(self.physics.n, 1, dtype=np.complex128))
            reference = TorchReference(arrays, volume=self.physics.volume, grid=self.physics.grid, book=self.book,
                                       config=self.config, fixed_step=float(self.reference.step))
            model = TorchRelativeModel(reference, "R")
            mass = mass_pack(reference.chi_b + 1., reference.volume)
            with self.assertRaises(NumericalFailure):
                model(mass)

    def test_parameter_match_and_paper_topology(self):
        with self.book.span("a25_network_topology_check"):
            models = [build_model(kind, {"weak": self.reference}, config=self.config)
                      for kind in ("N1", "N2", "N3")]
            counts = assert_parameter_match(models)
            self.assertEqual(len(set(counts.values())), 1)
            n0 = build_model("N0", {"weak": self.reference}, config=self.config)
            self.assertEqual(len(n0.stages), 4)
            self.assertEqual(n0.stages[0].encoder1.body[0].out_channels, 64)
            self.assertEqual(n0.stages[0].encoder2.body[0].out_channels, 128)
            self.assertEqual(n0.stages[0].bottom.body[0].out_channels, 256)
            self.assertEqual(n0.stages[0].encoder1.body[0].in_channels, 4)
            self.assertIsNot(n0.stages[0], n0.stages[1])

    def test_mps_and_validation_normalization_are_rejected(self):
        with self.book.span("a25_learning_boundary_check"):
            with self.assertRaises(ValueError):
                require_device("mps")
            normalizer = FeatureNormalizer()
            with self.assertRaises(ValueError):
                normalizer.fit_statistics(torch.zeros(10), torch.ones(10), 1,
                                          torch.zeros(4), torch.ones(4), 1,
                                          material_scale=1., current_scale=1., parent_ids=[1], role="validation")


class TrainingContractTests(unittest.TestCase):
    def test_tv_uses_increment_full_neumann_grid_and_mass_scale(self):
        from types import SimpleNamespace
        book = get_ledger()
        with book.span("a25_tv_boundary_and_background_test"):
            grid, volume = 8, 1. / 64
            ring = torch.zeros((1, grid, grid), dtype=torch.complex128)
            ring[:, 2:6, 2:6] = 2. + .1j
            ring[:, 3:5, 3:5] = .1 + .04j
            delta = torch.zeros_like(ring)
            self.assertEqual(float(tv_material(delta, grid, volume)), 0.)
            delta[:, -1, -1] = 1.
            delta.requires_grad_()
            tv = tv_material(delta, grid, volume)
            self.assertAlmostEqual(float(tv), 2. * volume ** .5, delta=3e-7)
            derivative = torch.autograd.grad(tv.sum(), delta)[0]
            self.assertAlmostEqual(float(derivative[0, -1, -1].real), 2. * volume ** .5, delta=1e-10)
            normalizer = FeatureNormalizer()
            background = ring.flatten(1)[0]
            model = SimpleNamespace(grid=grid, volume=volume, normalizer=normalizer,
                                    references={"ring": SimpleNamespace(chi_b=background,
                                                yb_norm2=torch.tensor(1., dtype=torch.float64))})
            result = SimpleNamespace(chi=background[None], current=torch.zeros((1, 64, 8), dtype=torch.complex128),
                                     data=torch.zeros((1, 32, 8), dtype=torch.complex128))
            batch = {"chi": result.chi, "current": result.current, "data": result.data,
                     "background_id": ["ring"], "lambda": torch.tensor([.01], dtype=torch.float64)}
            _, components = matched_loss(result, batch, model)
            self.assertEqual(float(components["tv"]), 0.)

    def test_parent_schedule_is_shared_without_row_split(self):
        book = get_ledger()
        with book.span("a25_parent_schedule_test"):
            parents = np.repeat(np.arange(32), 2)
            arrays = {"parent_id": parents, "split": np.full(64, "train"),
                      "background_id": np.full(64, "weak"), "chi": np.ones((64, 16), complex),
                      "data": np.ones((64, 32, 8), complex), "current": np.ones((64, 16, 8), complex),
                      "initial_mass": np.zeros((64, 32), dtype=np.float64),
                      "lambda": np.ones(64) * .01, "initial_wall": np.zeros(64)}
            dataset = ParentDataset(arrays, role="train")
            first, second = ParentSampler(dataset, 251008), ParentSampler(dataset, 251008)
            for _ in range(5):
                i1, i2 = first.next(), second.next()
                np.testing.assert_array_equal(i1, i2)
                self.assertEqual(len(set(parents[i1])), 4)

    def test_update_admission_uses_complete_cost_only(self):
        book = get_ledger()
        with book.span("a25_cost_only_selection_test"):
            rows = [{"method": kind, "blocks": depth, "update_wall_seconds": 1.,
                     "update_cpu_seconds": .9, "validation_wall_seconds_per_image": .001,
                     "validation_cpu_seconds_per_image": .001}
                    for kind, depth in [("N0", 4), ("N1", 3), ("N2", 3), ("N3", 3),
                                        ("N1", 4), ("N2", 4), ("N3", 4)]]
            health = {"device": "cpu", "rows": rows}
            selected = select_update_budget(health, config={}, cpu_available=7200, gpu_available=0)
            self.assertEqual(selected["updates"], 500)
            self.assertEqual(selected["complete_jobs"], 11)
            rejected = select_update_budget(health, config={}, cpu_available=100, gpu_available=0)
            self.assertIsNone(rejected["updates"])
            self.assertEqual(rejected["status"], "INSUFFICIENT_BUDGET")


if __name__ == "__main__":
    unittest.main()
