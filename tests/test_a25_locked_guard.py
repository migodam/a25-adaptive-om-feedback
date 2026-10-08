"""Metadata-only locked-opening guards; no held test truth is touched."""
from pathlib import Path
from copy import deepcopy
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import torch

from a24.contracts import ForbiddenAccess, get_ledger
from a25.locked_evaluation import (required_models, validate_freeze_record, claim_locked_open,
                                  exact_increment_tv, _data_residual_metrics, _read_online_timing)
from a25.torch_physics import validate_closure_provenance
from a25.training import checkpoint_cache_factors, validate_checkpoint_references


class LockedGuardTests(unittest.TestCase):
    def test_all_models_and_exact_checkpoint_set_required(self):
        book = get_ledger()
        with book.span("locked_freeze_guard_unit_test"):
            records = []
            for name in sorted(required_models()):
                kind = name.split("_", 1)[0]
                size = int(name.split("_train", 1)[1].split("_", 1)[0])
                blocks = int(name.rsplit("_b", 1)[1])
                records.append({"method": kind, "blocks": blocks, "train_parents": list(range(size)),
                                "status": "TRAINED_VALIDATION_SELECTED", "completed_updates": 500,
                                "checkpoint": "results/a25/learning/" + name + "/best.pt"})
            freeze = {"status": "FROZEN", "model_selection_frozen": True,
                      "checkpoints": [row["checkpoint"] for row in records]}
            self.assertEqual(set(validate_freeze_record(freeze, records)), required_models())
            with self.assertRaises(ForbiddenAccess):
                validate_freeze_record({**freeze, "status": "TRAINING"}, records)
            with self.assertRaises(ForbiddenAccess):
                validate_freeze_record(freeze, records[:-1])
            with self.assertRaises(ForbiddenAccess):
                validate_freeze_record({**freeze, "checkpoints": freeze["checkpoints"][:-1]}, records)

    def test_open_reservation_survives_and_denies_second_open(self):
        book = get_ledger()
        with book.span("locked_one_open_guard_unit_test"), tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "LOCKED_OPEN.json"
            claim_locked_open(marker, freeze_path="MODEL_FREEZE.json", book=book)
            original = marker.read_bytes()
            with self.assertRaises(ForbiddenAccess):
                claim_locked_open(marker, freeze_path="MODEL_FREEZE.json", book=book)
            self.assertEqual(marker.read_bytes(), original)

    def test_exact_tv_includes_terminal_edges_and_known_background(self):
        book = get_ledger()
        with book.span("locked_exact_tv_unit_test"):
            background = np.full(64, 2. + .1j)
            self.assertEqual(exact_increment_tv(background, background, grid=8, volume=1. / 64), 0.)
            predicted = background.copy()
            predicted[-1] += 1.
            self.assertAlmostEqual(exact_increment_tv(predicted, background, grid=8, volume=1. / 64), .25)

    def test_cold_online_reader_requires_and_passes_frozen_context(self):
        with get_ledger().span("locked_cold_online_freeze_unit_test"):
            freeze = {"status": "FROZEN", "model_selection_frozen": True,
                      "checkpoints": ["results/a25/learning/frozen/best.pt"]}
            with patch("a25.locked_evaluation.load_dataset", return_value={}) as loader:
                with self.assertRaises(ForbiddenAccess):
                    _read_online_timing(Path("/unused"), None)
                loader.assert_not_called()
                _read_online_timing(Path("/unused"), freeze)
                loader.assert_called_once_with(Path("/unused/data/online/locked_id.npz"),
                    role="online", freeze_record=freeze, allow_failed=True)

    def test_noiseless_quality_residual_uses_differential_data(self):
        with get_ledger().span("locked_differential_residual_unit_test"):
            observed = np.asarray([[101. + 0j]], dtype=np.complex128)
            yb = np.asarray([[100. + 0j]], dtype=np.complex128)
            metrics = _data_residual_metrics(observed + .1, observed, yb)
            self.assertAlmostEqual(metrics["full_data_relative_residual"], .1)
            self.assertAlmostEqual(metrics["full_data_total_relative_residual"], .1 / 101.)
            self.assertGreater(metrics["full_data_relative_residual"], .05)
            self.assertLess(metrics["full_data_total_relative_residual"], .05)
            self.assertIsNone(_data_residual_metrics(yb + .1, yb, yb)["full_data_relative_residual"])

    def test_task_closure_provenance_binds_admitted_construction(self):
        with get_ledger().span("a25_closure_provenance_guard_unit_test"):
            descriptor = {"background": [[.1, .04]], "precision": "complex128"}
            config = {"master_seed": 251008, "selected_nn_closure": "TASK_R32",
                      "source_commit": "frozen-source-commit", "protocol_id": "A25-NN-frozen-v1"}
            provenance = {"builder": "TASK_R32", "rank": 32, "probe_seed": 251545,
                          "source_commit": config["source_commit"], "protocol_id": config["protocol_id"],
                          "background_id": "weak", "background_descriptor": descriptor,
                          "basis_identity": "A25-frozen-background-weak-TASK_R32",
                          "independent_material_probes": 4, "independent_receiver_probes": 8,
                          "truth_or_oracle_used": False}
            actual = validate_closure_provenance(provenance, descriptor, rank=32, config=config)
            self.assertEqual(actual, provenance)
            self.assertIsNot(actual, provenance)
            with self.assertRaises(ValueError):
                validate_closure_provenance({}, descriptor, rank=32, config=config)
            for key, wrong in (("builder", "R32"), ("probe_seed", 241008),
                               ("source_commit", "different-source"), ("protocol_id", "A25-other"),
                               ("basis_identity", "different-basis"), ("truth_or_oracle_used", True),
                               ("independent_material_probes", 8), ("rank", 16),
                               ("background_descriptor", {"background": [[2., .1]]})):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    validate_closure_provenance({**provenance, key: wrong}, descriptor, rank=32, config=config)

    def test_checkpoint_rejects_changed_factors_with_same_provenance(self):
        with get_ledger().span("a25_exact_cache_factor_binding_unit_test"):
            reference = SimpleNamespace(descriptor={"closure_provenance": {"basis_identity": "fixed"}},
                         Ug=torch.tensor([[1. + .2j]], dtype=torch.complex128),
                         Vg=torch.tensor([[.5 - .1j]], dtype=torch.complex128))
            references = {"weak": reference}
            payload = {"reference_descriptors": {"weak": deepcopy(reference.descriptor)},
                       "reference_cache_factors": checkpoint_cache_factors(references)}
            validate_checkpoint_references(payload, references)
            self.assertEqual(payload["reference_cache_factors"]["weak"]["Ug"].device.type, "cpu")
            payload["reference_cache_factors"]["weak"]["Ug"][0, 0] += .01
            with self.assertRaises(ForbiddenAccess):
                validate_checkpoint_references(payload, references)
