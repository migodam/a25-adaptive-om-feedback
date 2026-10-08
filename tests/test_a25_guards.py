"""Mechanical guards only; parent runs these inside the charged CLI job."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
import numpy as np

from a25.budget import (BudgetLedger, BudgetExceeded, budget_history, charged_job,
                        owned_file_lock, write_json, SHARED_GPU_LOCK)
from a25.dataset import generate_manifest, public_manifest, load_dataset, FAMILIES
from a24.contracts import ForbiddenAccess
from a25.metrics import parent_equal, paired_parent_bootstrap


class DurableBudgetTests(unittest.TestCase):
    def test_receipts_restore_cpu_max_and_cuda_host_and_gpu_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            for job, device, wall, cpu, gpu, status in [
                    ("failed", "cpu", 8., 3., 0., "FAILED"),
                    ("cuda", "cuda", 12., 2., 12., "COMPLETE")]:
                write_json(Path(directory)/"results/a25/jobs"/job/"job_receipt.json",
                    dict(job=job, device=device, wall_seconds=wall, process_cpu_seconds=cpu,
                         gpu_occupation_seconds=gpu, status=status, durable_reservations={"new_full_forward_labels": 1}))
            old = Path(directory)/"results/jobs/old/job_receipt.json"
            write_json(old, {"process_cpu_seconds": 9999.})
            history = budget_history(directory)
            self.assertEqual(history["cpu_seconds"], 10.)
            self.assertEqual(history["gpu_seconds"], 12.)
            self.assertEqual(history["reservations"]["new_full_forward_labels"], 2)

    def test_accepted_job_and_unknown_interruption_cannot_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            with charged_job(directory, "first", config={"cpu_stop_reserve_seconds": 0}) as book:
                book.reserve("new_clean_labels", 456)
            receipt = Path(directory)/"results/a25/jobs/first/job_receipt.json"
            frozen = receipt.read_bytes()
            with self.assertRaises(BudgetExceeded):
                with charged_job(directory, "first"):
                    pass
            self.assertEqual(receipt.read_bytes(), frozen)
            write_json(Path(directory)/"results/a25/jobs/unknown/job_manifest.json", {"status": "STARTED"})
            with self.assertRaises(BudgetExceeded):
                with charged_job(directory, "next"):
                    pass

    def test_reservation_aliases_share_one_global_cap(self):
        book = BudgetLedger(enforce=False, prior_reservations={"new_full_forward_labels": 455})
        book.reserve("new_clean_labels", 456)
        with self.assertRaises(BudgetExceeded):
            book.reserve("new_labels", 456)
        self.assertEqual(book.reservations["new_full_forward_labels"], 1)

    def test_cpu_wall_cap_and_cuda_monitor_does_not_double_charge_wait(self):
        book = BudgetLedger(enforce=False)
        book.started_wall -= 5
        receipt = book.receipt()
        self.assertGreaterEqual(receipt["charged_cpu_seconds"], 5.)
        monitor = BudgetLedger(device="cuda", gpu_host_only=True, enforce=False)
        monitor.started_wall -= 100
        receipt = monitor.receipt()
        self.assertEqual(receipt["gpu_occupation_seconds"], 0.)
        self.assertLess(receipt["charged_cpu_seconds"], 5.)
        self.assertGreaterEqual(receipt["raw_monitor_wall_seconds"], 100.)

    def test_foreign_lock_is_never_removed(self):
        self.assertEqual(SHARED_GPU_LOCK.as_posix(), "D:/AI/A20_OPM_IMAGING/runs/gpu.lock")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"gpu.lock"
            with owned_file_lock(path, owner_id="one", job="test"):
                foreign = b'{"pid":999,"owner_id":"foreign"}'
                path.write_bytes(foreign)
            self.assertEqual(path.read_bytes(), foreign)
            with self.assertRaises(BudgetExceeded):
                with owned_file_lock(path, owner_id="two", job="test2"):
                    pass


class DatasetBoundaryTests(unittest.TestCase):
    def test_balanced_nested_independent_parents_and_exact_ood_design(self):
        manifest = generate_manifest({"master_seed": 251008})
        self.assertEqual(len(manifest["parents"]), 112)
        self.assertEqual(len(set(r["parent_id"] for r in manifest["parents"])), 112)
        self.assertEqual(set(FAMILIES), {"shell", "asymmetric_piecewise", "smooth", "mixed_scale"})
        self.assertEqual(len(manifest["train32"]), 32)
        self.assertTrue(set(manifest["train32"]) <= set(manifest["train64"]))
        for family in FAMILIES:
            train = [r for r in manifest["parents"] if r["family"] == family and r["split"] == "train"]
            self.assertEqual(len(train), 16)
            self.assertEqual(sum(r["parent_id"] in manifest["train32"] for r in train), 8)
            ood = [r for r in manifest["parents"] if r["family"] == family and r["split"] == "locked_ood"]
            self.assertEqual(len(ood), 4)
            self.assertEqual(sum(r["ood_type"] == "structural_combination" for r in ood), 2)
            self.assertEqual(sum(r["ood_type"] == "contrast" for r in ood), 2)
            for row in ood:
                self.assertEqual(row["amplitudes"], [1.5, 1.8] if row["ood_type"] == "contrast" else [.3, 1.2])
        self.assertEqual(manifest, generate_manifest({"master_seed": 251008}))
        self.assertFalse(any("geometry" in r for r in public_manifest(manifest)["parents"]))

    def test_test_truth_closed_before_read(self):
        with self.assertRaises(ForbiddenAccess):
            load_dataset("data/locked/locked_id.npz", role="evaluation")
        frozen = {"status": "FROZEN", "model_selection_frozen": True, "checkpoints": ["model.pt"]}
        with self.assertRaises(ForbiddenAccess):
            load_dataset("data/locked/locked_id.npz", role="train", freeze_record=frozen)

    def test_online_archive_rejects_mixed_truth_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"online.npz"
            np.savez(path, data=np.zeros((1,32,8),complex), chi=np.ones((1,576),complex))
            with self.assertRaises(ForbiddenAccess):
                load_dataset(path, role="online")

    def test_remote_source_scope_never_packages_private_or_closed_truth(self):
        path = Path(__file__).resolve().parents[1]/"tools/a25_remote.py"
        spec = importlib.util.spec_from_file_location("a25_remote_guard_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ["src/a25/allowed.py", "tools/tool.py", "private/key.json", "data/locked/locked_id.npz"]:
                p = root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text("fixture")
            members = module.deployment_members(root, "source")
            self.assertEqual({p.relative_to(root).as_posix() for p in members}, {"src/a25/allowed.py", "tools/tool.py"})
            with self.assertRaises(module.TransportError):
                module.deployment_members(root, "evaluation")


class ParentAggregationTests(unittest.TestCase):
    def test_equal_parents_not_variant_counts_and_missing_rows_remain_missing(self):
        rows = [{"parent_id": 1, "score": 1., "status": "OK"}] * 2
        rows += [{"parent_id": 2, "score": 3., "status": "OK"}] * 4
        result = parent_equal(rows, "score", expected_variants=None)
        self.assertEqual(result["parent_equal_mean"], 2.)
        result = parent_equal(rows, "score", expected_parent_ids=[1,2,3], expected_variants=None)
        self.assertIsNone(result["parent_equal_mean"])
        self.assertFalse(result["coverage_complete"])

    def test_paired_bootstrap_is_parent_resampling_and_retains_failure(self):
        rows = [{"parent_id": p, "case_id": f"{p}_{i}", "score": .9, "status": "OK"}
                for p in [1,2] for i in range(8)]
        reference = [{**r, "score": 1.} for r in rows]
        result = paired_parent_bootstrap(rows, reference, "score")
        self.assertEqual(result["samples"], 2000)
        self.assertAlmostEqual(result["point_estimate"], .1)
        rows[0]["status"] = "FAILED"
        failed = paired_parent_bootstrap(rows, reference, "score")
        self.assertIsNone(failed["ci95"])
        self.assertIn(1, failed["undefined_or_failed_parents"])


if __name__ == "__main__":
    unittest.main()
