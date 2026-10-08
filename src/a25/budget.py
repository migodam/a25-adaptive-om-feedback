"""Durable A25 resource accounting; accepted attempts are never reset."""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import json
import math
import os
import time
import uuid

from a20.costs import CostBook, BudgetExceeded, plain

CPU_LIMIT_SECONDS = 7200.0
GPU_LIMIT_SECONDS = 14400.0
MAX_NEW_LABELS = 456
SHARED_GPU_LOCK = Path("D:/AI/A20_OPM_IMAGING/runs/gpu.lock")
TERMINAL_STATUSES = frozenset({"COMPLETE", "FAILED", "BUDGET_STOP", "INTERRUPTED"})


def _category(category):
    return "new_full_forward_labels" if str(category) in {"new_labels", "new_clean_labels"} else str(category)


def write_json(path, value):
    """Atomic, flushed metadata replacement (never used to replace a receipt)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temp.open("x", encoding="utf-8") as handle:
        json.dump(plain(value), handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _number(row, key):
    value = row.get(key)
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise BudgetExceeded("INVALID_ACCEPTED_RESOURCE_RECEIPT:" + key)
    return float(value)


def budget_history(root):
    """Restore only A25 attempts, including failures and reservations.

    A dangling started manifest blocks new work: its unknown interruption tail
    cannot be silently replaced by zero or a last checkpoint.
    """
    jobs = Path(root) / "results/a25/jobs"
    total_cpu = total_gpu = 0.0
    reservations = Counter()
    receipts, unresolved = [], []
    for directory in sorted(jobs.glob("*")):
        if not directory.is_dir():
            continue
        manifest, receipt = directory / "job_manifest.json", directory / "job_receipt.json"
        if not receipt.exists():
            if manifest.exists():
                unresolved.append(directory.name)
            continue
        try:
            row = json.loads(receipt.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BudgetExceeded("UNREADABLE_ACCEPTED_RECEIPT:" + directory.name) from exc
        if row.get("status") not in TERMINAL_STATUSES or row.get("job") != directory.name:
            raise BudgetExceeded("NONTERMINAL_OR_MISMATCHED_RECEIPT:" + directory.name)
        wall, process = _number(row, "wall_seconds"), _number(row, "process_cpu_seconds")
        device = row.get("device")
        if device not in {"cpu", "cuda"}:
            raise BudgetExceeded("INVALID_RECEIPT_DEVICE")
        cpu = max(wall, process) if device == "cpu" else process
        gpu = _number(row, "gpu_occupation_seconds") if device == "cuda" else 0.0
        if "charged_cpu_seconds" in row and abs(_number(row, "charged_cpu_seconds") - cpu) > 1e-6:
            raise BudgetExceeded("RECEIPT_CPU_CHARGE_MISMATCH")
        local = Counter({str(k): int(v) for k, v in row.get("durable_reservations", {}).items()})
        if any(v < 0 for v in local.values()):
            raise BudgetExceeded("INVALID_RESERVATION_RECEIPT")
        # Durable action reservations survive a receipt written just before a
        # flush boundary. Never sum the same local reservation twice.
        ledger = directory / "COST_LEDGER.jsonl"
        if ledger.exists():
            with ledger.open(encoding="utf-8") as handle:
                for line in handle:
                    try:
                        action = json.loads(line)
                    except ValueError as exc:
                        raise BudgetExceeded("TRUNCATED_DURABLE_LEDGER:" + directory.name) from exc
                    if action.get("event") == "RESERVED":
                        category = str(action["category"])
                        local[category] = max(local[category], int(action["job_used"]))
        for category, count in local.items():
            reservations[_category(category)] += count
        total_cpu += cpu
        total_gpu += gpu
        receipts.append(row)
    return {"cpu_seconds": total_cpu, "gpu_seconds": total_gpu,
            "reservations": dict(reservations), "receipts": receipts,
            "unresolved_jobs": unresolved}


@contextmanager
def owned_file_lock(path, *, owner_id, job):
    """Compatible with the A20 shared JSON file lock; release only our bytes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"pid": os.getpid(), "started_utc":
                         time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                         "owner_id": str(owner_id), "job": str(job)}, sort_keys=True).encode()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise BudgetExceeded("EXISTING_JOB_LOCK; inspect owner, never silently delete") from exc
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        yield (path, payload)
    finally:
        # A changed/foreign lock is retained for inspection, never deleted.
        if path.exists() and path.read_bytes() == payload:
            path.unlink()


class BudgetLedger(CostBook):
    """CostBook-compatible spans plus inclusive cumulative A25 limits."""
    def __init__(self, path=None, *, device="cpu", prior_cpu=0.0, prior_gpu=0.0,
                 prior_reservations=None, cpu_limit=CPU_LIMIT_SECONDS,
                 gpu_limit=GPU_LIMIT_SECONDS, cpu_reserve=15.0, gpu_reserve=30.0,
                 metadata=None, checkpoint_path=None, enforce=True,
                 started_wall=None, started_cpu=None, gpu_host_only=False):
        if device not in {"cpu", "cuda"}:
            raise ValueError("A25_CPU_OR_CUDA_REQUIRED")
        if not 0 < float(cpu_limit) <= CPU_LIMIT_SECONDS or not 0 < float(gpu_limit) <= GPU_LIMIT_SECONDS:
            raise ValueError("A25_BUDGET_CANNOT_BE_EXPANDED")
        self.accounting_device = device
        self.gpu_host_only = bool(gpu_host_only)
        if self.gpu_host_only and device != "cuda":
            raise ValueError("GPU_HOST_OVERHEAD_REQUIRES_CUDA_ACCOUNTING")
        super().__init__(path, device="cpu" if self.gpu_host_only else device, prior_cpu=prior_cpu, prior_gpu=prior_gpu,
                         cpu_limit=cpu_limit, gpu_limit=gpu_limit,
                         cpu_reserve=cpu_reserve, gpu_reserve=gpu_reserve,
                         metadata=metadata, enforce=False)
        if started_wall is not None:
            self.started_wall = float(started_wall)
        if started_cpu is not None:
            self.started_cpu = float(started_cpu)
        self._budget_enforce = bool(enforce)
        self.prior_reservations = Counter()
        for category, count in (prior_reservations or {}).items():
            self.prior_reservations[_category(category)] += int(count)
        self.reservations = Counter()
        self.checkpoint_path = None if checkpoint_path is None else Path(checkpoint_path)
        self._last_checkpoint = -float("inf")
        self._owned_locks = []
        self.owner_id = self.metadata.get("owner_id")
        self.deadline = self.started_wall + max(0.0, self.cpu_limit - self.cpu_reserve - self.prior_cpu)
        if device == "cuda" and not self.gpu_host_only:
            self.deadline = self.started_wall + max(0.0, self.gpu_limit - self.gpu_reserve - self.prior_gpu)
        elif self.gpu_host_only:
            self.deadline = float("inf")

    def check_owner(self, owner_id):
        if self.owner_id is not None and str(owner_id) != str(self.owner_id):
            raise BudgetExceeded("FOREIGN_BUDGET_OWNER")
        for path, payload in self._owned_locks:
            if not path.exists() or path.read_bytes() != payload:
                raise BudgetExceeded("JOB_LOCK_OWNERSHIP_LOST")

    def elapsed(self):
        wall = max(0.0, time.perf_counter() - self.started_wall)
        process = max(0.0, time.process_time() - self.started_cpu)
        return wall, process, max(wall, process) if self.accounting_device == "cpu" else process

    def check(self):
        self.check_owner(self.owner_id)
        wall, process, cpu = self.elapsed()
        if self.checkpoint_path is not None and wall - self._last_checkpoint >= 1.0:
            write_json(self.checkpoint_path, self.receipt())
            self._last_checkpoint = wall
        if self._budget_enforce:
            if self.prior_cpu + cpu >= self.cpu_limit - self.cpu_reserve:
                raise BudgetExceeded("A25_CUMULATIVE_CPU_LIMIT")
            if self.accounting_device == "cuda" and not self.gpu_host_only and self.prior_gpu + wall >= self.gpu_limit - self.gpu_reserve:
                raise BudgetExceeded("A25_CUMULATIVE_GPU_OCCUPATION_LIMIT")
        # The inherited memory checks remain active; inherited CPU-only
        # process accounting is disabled in favor of the rule above.
        super().check()

    def append(self, row):
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(plain(row), allow_nan=False) + "\n")
                handle.flush()
                if row.get("event") == "RESERVED":
                    os.fsync(handle.fileno())
        self.events += 1

    def reserve(self, category, limit=MAX_NEW_LABELS):
        self.check()
        category, limit = str(category), int(limit)
        category = _category(category)
        if category == "new_full_forward_labels" and limit > MAX_NEW_LABELS:
            raise ValueError("A25_LABEL_CAP_CANNOT_BE_EXPANDED")
        used = self.prior_reservations[category] + self.reservations[category]
        if used >= limit:
            raise BudgetExceeded("CUMULATIVE_ACTION_CAP:" + category)
        self.reservations[category] += 1
        self.append({"event": "RESERVED", "category": category,
                     "job_used": self.reservations[category], "used": used + 1,
                     "limit": limit, "status": "RESERVED", **self.metadata})

    def receipt(self):
        row = {**self.metadata, **super().receipt()}
        wall, process, cpu = self.elapsed()
        row.update(wall_seconds=wall, process_cpu_seconds=process,
                   charged_cpu_seconds=cpu,
                   device=self.accounting_device,
                   gpu_occupation_seconds=wall if self.accounting_device == "cuda" and not self.gpu_host_only else 0.0,
                   gpu_host_only=self.gpu_host_only,
                   raw_monitor_wall_seconds=wall if self.gpu_host_only else None,
                   durable_reservations=dict(self.reservations),
                   prior_cpu_seconds=self.prior_cpu, prior_gpu_seconds=self.prior_gpu,
                   cpu_limit_seconds=self.cpu_limit, gpu_limit_seconds=self.gpu_limit,
                   cpu_accounting_rule="max(wall,processCPU) on CPU; processCPU on CUDA",
                   gpu_accounting_rule="entire CUDA job occupied wall")
        return row


@contextmanager
def charged_job(root, job, *, device="cpu", config=None, metadata=None,
                shared_lock_path=None, gpu_host_only=False):
    """Start a new paid attempt; retries use new IDs and inherit all costs."""
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    root, job = Path(root).resolve(), str(job)
    if not job or Path(job).name != job or job in {".", ".."}:
        raise ValueError("SIMPLE_JOB_ID_REQUIRED")
    config = dict(config or {})
    if device not in {"cpu", "cuda"}:
        raise ValueError("A25_CPU_OR_CUDA_REQUIRED")
    cpu_limit = float(config.get("cpu_budget_seconds", config.get("cpu_limit_seconds", CPU_LIMIT_SECONDS)))
    gpu_limit = float(config.get("gpu_budget_seconds", config.get("gpu_limit_seconds", GPU_LIMIT_SECONDS)))
    if not 0 < cpu_limit <= CPU_LIMIT_SECONDS or not 0 < gpu_limit <= GPU_LIMIT_SECONDS:
        raise ValueError("A25_BUDGET_CANNOT_BE_EXPANDED")
    owner = "a25:" + job + ":" + uuid.uuid4().hex
    with owned_file_lock(root / "runs/a25-accounting.lock", owner_id=owner, job=job) as accounting_lock:
        history = budget_history(root)
        if history["unresolved_jobs"]:
            raise BudgetExceeded("UNACCOUNTED_INTERRUPTED_JOBS:" + ",".join(history["unresolved_jobs"]))
        directory = root / "results/a25/jobs" / job
        if directory.exists():
            raise BudgetExceeded("JOB_ID_ALREADY_EXISTS; terminal receipts are immutable")
        directory.mkdir(parents=True)
        manifest = {**(metadata or {}), "job": job, "device": device, "owner_id": owner,
                    "status": "STARTED", "started_utc":
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "prior_cpu_seconds": history["cpu_seconds"],
                    "prior_gpu_seconds": history["gpu_seconds"],
                    "prior_reservations": history["reservations"]}
        write_json(directory / "job_manifest.json", manifest)
        book = BudgetLedger(directory / "COST_LEDGER.jsonl", device=device,
                            prior_cpu=history["cpu_seconds"], prior_gpu=history["gpu_seconds"],
                            prior_reservations=history["reservations"],
                            cpu_limit=cpu_limit, gpu_limit=gpu_limit,
                            cpu_reserve=config.get("cpu_stop_reserve_seconds", 15.0),
                            gpu_reserve=config.get("gpu_stop_reserve_seconds", 30.0),
                            metadata={**(metadata or {}), "job": job, "owner_id": owner},
                            checkpoint_path=directory / "job_checkpoint.json",
                            started_wall=started_wall, started_cpu=started_cpu,
                            gpu_host_only=gpu_host_only)
        book._owned_locks = [accounting_lock]
        status, error = "COMPLETE", None
        try:
            if device == "cuda" and not gpu_host_only:
                path = SHARED_GPU_LOCK if shared_lock_path is None else Path(shared_lock_path)
                if os.name == "nt" and path.as_posix().lower() != SHARED_GPU_LOCK.as_posix().lower():
                    raise BudgetExceeded("A25_REQUIRES_A20_SHARED_GPU_LOCK")
                with owned_file_lock(path, owner_id=owner, job=job) as gpu_lock:
                    book._owned_locks.append(gpu_lock)
                    book.check()
                    yield book
                    book.check()
                    book._owned_locks.pop()
            else:
                book.check()
                yield book
                book.check()
        except BaseException as exc:
            status = "BUDGET_STOP" if isinstance(exc, BudgetExceeded) else "FAILED"
            error = type(exc).__name__ + ": " + str(exc)
            raise
        finally:
            receipt = book.receipt()
            receipt.update(status=status, error=error, receipt_version=1,
                           ended_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            path = directory / "job_receipt.json"
            # Never replace a terminal receipt even if another caller interferes.
            if path.exists():
                raise BudgetExceeded("TERMINAL_RECEIPT_ALREADY_EXISTS")
            write_json(path, receipt)


Ledger = BudgetLedger
job_lock = owned_file_lock
