"""Parent-invoked, paid packaging of explicit public A25 saved evidence."""
from __future__ import annotations

import time

PROCESS_WALL, PROCESS_CPU = time.perf_counter(), time.process_time()

import argparse
import ast
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import sys
import zipfile


MAX_ASSET_BYTES = 2_000_000_000
CHUNK = 1 << 20
EXPERIMENTS = ("frozen_optimizer_repair", "tv_multiplier_0p1", "amplitude_1p8")
EXPERIMENT_METADATA = ("HISTORIES.json", "PREPARATIONS.json", "METRICS.csv",
                       "TASK_AUDIT.csv", "PARENT_EQUAL_SUMMARY.csv", "NN_CLOSURE_ADMISSION.json")
PROSPECTIVE_METADATA = ("METRICS.csv", "TASK_AUDIT.csv", "HISTORIES.json",
                        "PREPARATIONS.json", "PROVENANCE.json", "SUMMARY.json",
                        "CHECKPOINT_METRICS.csv", "EXPOSURE.json", "FAILURES.json", "ACTIONS.jsonl", "PARENT_REVIEW.json")
PHASE_METADATA = ("DECISION.json", "DECISION_INITIAL.json", "INDEPENDENT_REFERENCE.json",
                  "REFERENCE_REFINEMENT_001.json", "SOLVER_COMPARISON.csv")
JOB_METADATA = ("job_receipt.json", "job_manifest.json", "job_checkpoint.json",
                "config.json", "environment.json", "ENVIRONMENT.json", "RUNTIME.json", "result.json",
                "PROFILE_UPDATE.json", "pstats_self_top60.csv", "pstats_cumulative_top60.csv")
LEARNING_METADATA = ("NN_SOURCE_FREEZE.json", "MODEL_FREEZE.json", "TRAINED_MODELS.json",
                     "NOT_RUN_DECISION.json", "COST_SELECTED_UPDATES.json", "GPU_HEALTH.json",
                     "HEALTH_INDEX_PROVENANCE.json")
TOKEN_RULES = {
    "openai_token": re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "google_api_key": re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{15,}"),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
}
CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
    r"password|passwd|secret[_-]?key|aws_secret_access_key)[\"']?\s*[:=]\s*"
    r"(?:[\"'](?P<quoted>[^\"'\r\n]+)[\"']|(?P<bare>[^\s,;\]}]+))")


def _checked(root, path, *, directory=False, required=True):
    """No symlink, outside-root, private tree or locked-data access."""
    path = Path(path)
    relative = path.relative_to(root)
    parts = relative.parts
    if ".." in parts:
        raise RuntimeError("PUBLIC_PATH_TRAVERSAL_REJECTED")
    if any(part.lower() in {"private", ".git", ".venv", ".venv_nn", "transport_variants"}
           or part.lower().startswith(".venv") for part in parts):
        raise RuntimeError("NONPUBLIC_PATH_REJECTED:" + relative.as_posix())
    if re.search(r"(?i)credential|secret|password|private|(?:^|_)ssh(?:_|\.)", path.name):
        raise RuntimeError("PRIVATE_METADATA_FILENAME_REJECTED")
    if parts[:2] == ("data", "locked") or (parts[:2] == ("data", "online")
            and any(part.startswith("locked_") for part in parts[2:])):
        raise RuntimeError("LOCKED_DATA_PATH_REJECTED")
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError("SYMLINK_REJECTED:" + relative.as_posix())
    if not path.exists() and not required:
        return None
    exists_as_expected = path.is_dir() if directory else path.is_file()
    if not exists_as_expected or not path.resolve().is_relative_to(root):
        raise RuntimeError("PUBLIC_FILE_REQUIRED:" + relative.as_posix())
    return path


def _select(root, job):
    """Only these exact files/patterns may enter either archive."""
    reproduction, ledgers, optional_missing = set(), set(), []

    def add(target, relative, required=False):
        path = root / relative
        checked = _checked(root, path, required=False)
        if checked is None:
            if required:
                raise RuntimeError("REQUIRED_PUBLIC_INPUT_MISSING:" + relative)
            optional_missing.append(relative)
            return
        target.add(checked)

    def glob(target, directory, pattern, required=False):
        base = _checked(root, root / directory, directory=True, required=False)
        paths = sorted(base.glob(pattern)) if base is not None else []
        if required and not paths:
            raise RuntimeError("REQUIRED_PUBLIC_GROUP_EMPTY:" + directory + "/" + pattern)
        for path in paths:
            target.add(_checked(root, path))

    for name in ("data/train.npz", "data/validation.npz", "data/online/train.npz", "data/online/validation.npz", "data/manifest.json", "data/geometry.json",
                 "data/background/weak.npz", "data/background/ring.npz",
                 "docs/A25_PUBLICATION_SCOPE.md"):
        add(reproduction, name, required=True)
    add(reproduction, "results/a25/dataset/GENERATION.json", required=True)
    phase = "results/a25/development/phase0"
    glob(reproduction, phase + "/inputs", "*.npz", required=True)
    glob(reproduction, phase + "/reference", "*.npz", required=True)
    for name in PHASE_METADATA:
        add(reproduction, phase + "/" + name)
    for experiment in EXPERIMENTS:
        directory = "results/a25/development/" + experiment
        for name in EXPERIMENT_METADATA:
            add(reproduction, directory + "/" + name,
                required=experiment == "frozen_optimizer_repair" and name == "HISTORIES.json")
        for child in ("images", "states", "state_arrays"):
            glob(reproduction, directory + "/" + child, "*.npz",
                 required=experiment == "frozen_optimizer_repair" and child == "images")
    prospective = "results/a25/development/prospective_regime_validation"
    for name in PROSPECTIVE_METADATA:
        add(reproduction, prospective + "/" + name)
    glob(reproduction, prospective, "*.npz")
    for child in ("images", "states", "state_arrays", "arrays"):
        glob(reproduction, prospective + "/" + child, "*.npz")
    for name in ("REPRODUCING_A25.md", "SOURCE_MANIFEST_A25.json"):
        add(reproduction, name)
    for background in ("weak", "ring"):
        for parent in range(2401, 2405):
            for amplitude in ("0.3", "1.2"):
                stem = f"{background}_{parent}_{amplitude}"
                add(reproduction, "results/b0/data/offline/" + stem + ".npz", required=True)
                for noise in ("zero", "snr20"):
                    add(reproduction, "results/b0/data/online/" + stem + "_" + noise + ".npz", required=True)
            add(reproduction, f"results/a25/development/extra_clean/{background}_{parent}_1.8.npz")
    for name in ("PAIRED_PARENT_BOOTSTRAP.json", "PAIRED_TV_AND_REGIME.json", "REGIME_HYPOTHESIS_FREEZE.json"):
        add(reproduction, "results/a25/development/" + name)

    for name in ("COST_LEDGER.jsonl", "FAILURE_LEDGER.jsonl"):
        add(ledgers, name, required=True)
        add(ledgers, "results/b0/" + name)
    jobs = _checked(root, root / "results/a25/jobs", directory=True)
    completed_jobs = []
    for directory in sorted(jobs.iterdir()):
        if directory.name == job or not directory.is_dir():
            continue
        if directory.is_symlink():
            raise RuntimeError("SYMLINK_JOB_DIRECTORY_REJECTED")
        _checked(root, directory, directory=True)
        if not (directory / "job_receipt.json").exists():
            raise RuntimeError("UNRESOLVED_JOB_NOT_PUBLICATION_READY:" + directory.name)
        completed_jobs.append(directory.name)
        for name in ("COST_LEDGER.jsonl", "FAILURE_LEDGER.jsonl", *JOB_METADATA):
            add(ledgers, directory.relative_to(root).as_posix() + "/" + name)
    for name in ("ENVIRONMENT.json", "SOURCE_MANIFEST.json", "results/a25/A25_GATE_DECISION.json",
                 "results/a25/report/ARTIFACT_AUDIT.json"):
        add(ledgers, name)
    glob(ledgers, "configs/a25", "*.json")
    for name in LEARNING_METADATA:
        add(ledgers, "results/a25/learning/" + name)
    attempts = _checked(root, root / "results/a25/learning/health_attempts", directory=True, required=False)
    if attempts is not None:
        for directory in sorted(attempts.iterdir()):
            if directory.is_dir() and not directory.is_symlink():
                for name in ("GPU_HEALTH.json", "COST_SELECTED_UPDATES.json"):
                    add(ledgers, directory.relative_to(root).as_posix() + "/" + name)
    aliases=[]
    def deduplicate_physical_aliases(paths):
        # macOS/Windows can resolve ENVIRONMENT.json and environment.json to
        # one file. Preserve its actual directory spelling, not two aliases.
        # This is filesystem identity only; no numerical/content hash is used.
        groups={}
        for path in sorted(paths):
            info=path.stat()
            groups.setdefault((path.relative_to(root).as_posix().casefold(),info.st_dev,info.st_ino),[]).append(path)
        output=[]
        for group in groups.values():
            if len(group)==1:
                output.append(group[0]);continue
            actual_names={path.name for path in group[0].parent.iterdir()}
            chosen=next((path for path in group if path.name in actual_names),group[0])
            output.append(chosen)
            for path in group:
                if path!=chosen:
                    aliases.append({'kept':chosen.relative_to(root).as_posix(),
                                    'alias':path.relative_to(root).as_posix(),
                                    'reason':'same filesystem device and inode; actual filename preserved; no hash'})
        return sorted(output)
    return (deduplicate_physical_aliases(reproduction),deduplicate_physical_aliases(ledgers),
            completed_jobs,sorted(set(optional_missing)),aliases)


def _restore_numbers(original, sanitized):
    """Sanitizer operates on text metadata; every numerical leaf survives."""
    if isinstance(original, (int, float, bool)) or original is None:
        return original
    if isinstance(original, dict):
        clean = sanitized if isinstance(sanitized, dict) else {}
        return {str(key): _restore_numbers(value, clean.get(str(key), "[REDACTED]"))
                for key, value in original.items()}
    if isinstance(original, list):
        clean = sanitized if isinstance(sanitized, list) else ["[REDACTED]"] * len(original)
        return [_restore_numbers(value, clean[index]) for index, value in enumerate(original)]
    return sanitized


def _safe_metadata(value, sanitizer):
    return _restore_numbers(value, sanitizer(value))


def _prepare(root, selected, stage, sanitizer, book):
    entries = []
    for path in selected:
        book.check()
        name = path.relative_to(root).as_posix()
        source_bytes = path.stat().st_size
        records = None
        if path.suffix == ".npz":
            public = path
        else:
            public = stage / name
            public.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".jsonl":
                records = 0
                with path.open(encoding="utf-8") as source, public.open("x", encoding="utf-8", newline="\n") as destination:
                    for line_number, line in enumerate(source, 1):
                        if not line.strip():
                            destination.write("\n")
                            continue
                        try:
                            value = json.loads(line)
                            safe = _safe_metadata(value, sanitizer)
                            destination.write(json.dumps(safe, ensure_ascii=False, allow_nan=False) + "\n")
                        except (ValueError, TypeError) as exc:
                            raise RuntimeError(f"PUBLIC_JSONL_INVALID:{name}:line{line_number}") from None
                        records += 1
                        if records % 4096 == 0:
                            book.check()
            elif path.suffix == ".json":
                value = json.loads(path.read_text(encoding="utf-8"))
                with public.open("x", encoding="utf-8", newline="\n") as destination:
                    json.dump(_safe_metadata(value, sanitizer), destination, ensure_ascii=False,
                              indent=2, allow_nan=False)
                    destination.write("\n")
            else:
                with path.open(encoding="utf-8") as source, public.open("x", encoding="utf-8", newline="\n") as destination:
                    for line in source:
                        destination.write(sanitizer(line))
        entries.append({"name": name, "path": public, "source_bytes": source_bytes,
                        "public_bytes": public.stat().st_size, "jsonl_records": records,
                        "text_metadata_sanitized": path.suffix != ".npz"})
    return entries


def _placeholder(value):
    value = value.strip().rstrip(",")
    return (not value or value.upper() in {"NONE", "NULL", "FALSE", "TRUE", "[REDACTED]", "[REDACTED_TOKEN]"}
            or value.startswith(("<", "${", "$ENV", "os.environ", "os.getenv", "args.", "config.", "re.compile"))
            or bool(re.fullmatch(r"(?:X+|\*+|YOUR_[A-Z_]+|EXAMPLE_[A-Z_]+)", value)))


def _scan_line(line, *, name, number, suffix, audit):
    matches = [(rule, match) for rule, pattern in TOKEN_RULES.items() for match in pattern.finditer(line)]
    for match in CREDENTIAL_ASSIGNMENT.finditer(line):
        value = match.group("quoted") or match.group("bare")
        if not _placeholder(value):
            matches.append(("literal_credential_assignment", match))
    for rule, match in matches:
        value = match.group(0)
        # Regex/metavariable syntax is evidence of a detector/example literal.
        # An actual-looking token or key block never becomes exempt merely
        # because its file happens to be Python or Markdown.
        literal = (suffix in {".py", ".md"} and rule == "literal_credential_assignment"
                   and bool(re.search(r"[\\\[\]{}]", value))
                   and ("re.compile" in line or 'r"' in line or "r'" in line or "regex" in line.lower()))
        safe_name = name
        for pattern in TOKEN_RULES.values():
            safe_name = pattern.sub("<WITHHELD_FORMAT>", safe_name)
        record = {"file": safe_name, "line": number, "rule": rule,
                  "context": "detector_pattern_literal" if literal else "actual_format_or_literal_value",
                  "matched_value_disclosed": False}
        audit["pattern_literal_contexts" if literal else "rejected_findings"].append(record)


def _scan_npz(path, name, audit, book):
    """Inspect string metadata only; never unpickle or transform numerical arrays."""
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            book.check()
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts or info.is_dir() or member.suffix != ".npy":
                raise RuntimeError("NONSTANDARD_PUBLIC_NPZ_MEMBER:" + name)
            with archive.open(info) as source:
                magic = source.read(8)
                if len(magic) != 8 or magic[:6] != b"\x93NUMPY":
                    raise RuntimeError("INVALID_PUBLIC_NPY_HEADER:" + name)
                version = tuple(magic[6:8])
                length_size = 2 if version == (1, 0) else 4
                if version not in {(1, 0), (2, 0), (3, 0)}:
                    raise RuntimeError("UNSUPPORTED_PUBLIC_NPY_VERSION:" + name)
                length_bytes = source.read(length_size)
                length = struct.unpack("<H" if length_size == 2 else "<I", length_bytes)[0]
                if length > CHUNK:
                    raise RuntimeError("PUBLIC_NPY_HEADER_TOO_LARGE:" + name)
                header = ast.literal_eval(source.read(length).decode("utf-8" if version == (3, 0) else "latin1"))
                dtype = header["descr"]
                if not isinstance(dtype, str) or "O" in dtype:
                    raise RuntimeError("OBJECT_OR_STRUCTURED_PUBLIC_ARRAY_REJECTED:" + name)
                kind = re.fullmatch(r"([<>=|])([US])(\d+)", dtype)
                if kind is None:
                    audit["numerical_array_members_unmodified"] += 1
                    continue
                audit["string_array_members_scanned"] += 1
                credential_member = bool(re.search(r"(?i)(?:api[_-]?key|access[_-]?token|"
                    r"auth[_-]?token|client[_-]?secret|password|passwd|secret[_-]?key)", member.stem))
                encoding = ("utf-32-be" if kind[1] == ">" else "utf-32-le") if kind[2] == "U" else "utf-8"
                number = 0
                tail = ""
                while block := source.read(CHUNK):
                    book.check()
                    number += 1
                    text = tail + block.decode(encoding, errors="replace")
                    _scan_line(text, name=name + ":" + info.filename, number=number, suffix=".npy", audit=audit)
                    if credential_member and any(not _placeholder(value) for value in text.split("\0") if value.strip()):
                        audit["rejected_findings"].append({"file": name, "line": number,
                            "rule": "credential_named_string_array", "context": "nonempty_literal_value",
                            "matched_value_disclosed": False})
                    tail = text[-1024:]


def _scan(root, entries, audit, book):
    for entry in entries:
        book.check()
        _scan_line(entry["name"], name="<PUBLIC_MEMBER_NAME>", number=0, suffix=".path", audit=audit)
        if entry["path"].suffix == ".npz":
            _scan_npz(entry["path"], entry["name"], audit, book)
        else:
            with entry["path"].open(encoding="utf-8") as source:
                for number, line in enumerate(source, 1):
                    _scan_line(line, name=entry["name"], number=number,
                               suffix=entry["path"].suffix, audit=audit)
                    if number % 4096 == 0:
                        book.check()
        audit["public_members_scanned"] += 1
    # Explicit publication source-text allowlist, not an unrestricted walk.
    source_paths = set(root.glob("*.md")) | set((root / "docs").glob("*.md"))
    for directory, pattern in (("src/a25", "*.py"), ("tools", "a25*.py"), ("tests", "test_a25*.py")):
        base = _checked(root, root / directory, directory=True, required=False)
        if base is not None:
            source_paths.update(base.rglob(pattern))
    for path in sorted(source_paths):
        book.check()
        _checked(root, path)
        name = path.relative_to(root).as_posix()
        with path.open(encoding="utf-8") as source:
            for number, line in enumerate(source, 1):
                _scan_line(line, name=name, number=number, suffix=path.suffix, audit=audit)
                if number % 4096 == 0:
                    book.check()
        audit["source_text_files_scanned"] += 1


def _zip_bound(entry):
    size = entry["public_bytes"]
    # Conservative deflate bound and ZIP64/name/central-directory allowance.
    return size + (size >> 12) + (size >> 14) + (size >> 25) + 512 + 2 * len(entry["name"].encode("utf-8"))


def _archive(entries, out, basename, *, limit, book):
    groups, group, size = [], [], 256
    for entry in entries:
        bound = _zip_bound(entry)
        if bound + 256 > limit:
            raise RuntimeError("SINGLE_PUBLIC_MEMBER_EXCEEDS_ASSET_LIMIT:" + entry["name"])
        if group and size + bound > limit:
            groups.append(group)
            group, size = [], 256
        group.append(entry)
        size += bound
    if group:
        groups.append(group)
    assets = []
    for index, members in enumerate(groups, 1):
        name = basename + (f".part{index:03d}" if len(groups) > 1 else "") + ".zip"
        path = out / name
        temporary = out / (name + ".incomplete")
        rows = []
        with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as archive:
            for entry in members:
                book.check()
                info = zipfile.ZipInfo(entry["name"])
                info.compress_type = zipfile.ZIP_STORED if entry["path"].suffix == ".npz" else zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                info.file_size = entry["public_bytes"]
                copied = 0
                with entry["path"].open("rb") as source, archive.open(info, "w", force_zip64=True) as destination:
                    while chunk := source.read(CHUNK):
                        book.check()
                        destination.write(chunk)
                        copied += len(chunk)
                if copied != entry["public_bytes"]:
                    raise RuntimeError("PUBLIC_SOURCE_CHANGED_DURING_PACKAGE:" + entry["name"])
                stored = archive.getinfo(entry["name"])
                rows.append({key: entry[key] for key in ("name", "source_bytes", "public_bytes", "jsonl_records", "text_metadata_sanitized")}
                            | {"zip_uncompressed_bytes": stored.file_size, "zip_compressed_bytes": stored.compress_size})
        exact_size = temporary.stat().st_size
        if exact_size > limit:
            raise RuntimeError("PUBLIC_ASSET_LIMIT_EXCEEDED:" + name)
        temporary.replace(path)
        assets.append({"filename": name, "exact_bytes": exact_size, "member_count": len(rows),
                       "uncompressed_member_bytes": sum(row["zip_uncompressed_bytes"] for row in rows),
                       "members": rows, "ZIP64_enabled": True})
    return assets


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--config", default="configs/a25/nn_blocking_wait.json")
    parser.add_argument("--asset-limit-bytes", type=int, default=MAX_ASSET_BYTES)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not 1_000_000 <= args.asset_limit_bytes <= MAX_ASSET_BYTES:
        raise ValueError("ASSET_LIMIT_MUST_NOT_EXCEED_2GB")
    config_path = root / args.config
    if config_path.relative_to(root).parts[:2] != ("configs", "a25"):
        raise RuntimeError("PUBLIC_CONFIG_ALLOWLIST_REQUIRED")
    _checked(root, config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    sys.path.insert(0, str(root / "src"))
    from a24.contracts import active_ledger
    from a25.budget import charged_job, write_json
    from a25.reporting import Sanitizer
    with charged_job(root, args.job, device="cpu", config=config,
                     metadata={"stage": "public_release_packaging", "locked_inputs_opened": False}) as book, active_ledger(book):
        book.started_wall = min(book.started_wall, PROCESS_WALL)
        book.started_cpu = min(book.started_cpu, PROCESS_CPU)
        if (root / "results/a25/learning/LOCKED_OPEN.json").exists():
            raise RuntimeError("THIS_PUBLICATION_SCOPE_REQUIRES_UNOPENED_LOCKED_TEST")
        out = root / "release_assets" / args.job
        out.mkdir(parents=True, exist_ok=False)
        stage = out / ".public_staging"
        stage.mkdir()
        sanitizer = Sanitizer(root)
        audit = {"status": "SCAN_STARTED", "rejected_findings": [], "pattern_literal_contexts": [],
                 "public_members_scanned": 0, "source_text_files_scanned": 0,
                 "string_array_members_scanned": 0, "numerical_array_members_unmodified": 0,
                 "credential_values_disclosed": False, "private_paths_read": False,
                 "locked_paths_read": False}
        assets = []
        try:
            with book.span("public_package_allowlist"):
                reproduction, ledgers, completed_jobs, missing, filesystem_aliases = _select(root, args.job)
            with book.span("public_package_metadata_sanitization"):
                repro_entries = _prepare(root, reproduction, stage, sanitizer, book)
                ledger_entries = _prepare(root, ledgers, stage, sanitizer, book)
            with book.span("public_package_credential_scan"):
                _scan(root, repro_entries + ledger_entries, audit, book)
                audit["status"] = "REJECTED" if audit["rejected_findings"] else "PASSED"
                audit["sanitizer_redactions"] = dict(sanitizer.redactions)
                write_json(out / "PUBLICATION_SCAN.json", audit)
                if audit["rejected_findings"]:
                    raise RuntimeError("PUBLICATION_SCAN_REJECTED; values withheld, inspect safe context records")
            with book.span("public_reproduction_zip", public_reproduction_members=len(repro_entries)):
                assets.extend(_archive(repro_entries, out, "A25_REPRODUCTION_DATA", limit=args.asset_limit_bytes, book=book))
            with book.span("public_action_ledger_zip", public_ledger_members=len(ledger_entries)):
                assets.extend(_archive(ledger_entries, out, "A25_COMPLETE_ACTION_LEDGERS", limit=args.asset_limit_bytes, book=book))
            manifest = {"status": "LOCAL_PACKAGE_READY_NOT_UPLOADED", "job": args.job,
                        "filesystem_aliases":filesystem_aliases,
                        "asset_limit_bytes": args.asset_limit_bytes, "assets": assets,
                        "total_exact_asset_bytes": sum(row["exact_bytes"] for row in assets),
                        "total_member_count": sum(row["member_count"] for row in assets),
                        "completed_job_cutoff": completed_jobs,
                        "packaging_terminal_receipt": "results/a25/jobs/" + args.job + "/job_receipt.json",
                        "packaging_receipt_policy": "terminal receipt is generated on charged_job exit; publish it separately after sanitization",
                        "historical_development_parents": [2401, 2402, 2403, 2404],
                        "optional_prospective_evidence": "saved validation-label no-NN outputs; no new labels or locked ID/OOD",
                        "test_data_included": False, "locked_paths_read": False,
                        "numerical_arrays_changed": False, "ledger_numeric_counter_values_changed": False,
                        "ledger_records_removed_or_deduplicated": False,
                        "raw_process_logs_included": False, "outside_allowlist_files_included": False,
                        "text_metadata_sanitizer": "a25.reporting.Sanitizer with original numerical leaves restored",
                        "optional_files_absent": missing,
                        "multipart_policy": "each part is an independent ZIP; extract all parts into the same reproduction directory",
                        "single_oversized_member_policy": "reject rather than omit or publish an oversized asset"}
            write_json(out / "PACKAGE_MANIFEST.json", manifest)
            write_json(root / "results/a25/jobs" / args.job / "result.json",
                       {"status": manifest["status"], "output": out.relative_to(root).as_posix(),
                        "asset_count": len(assets), "exact_asset_bytes": manifest["total_exact_asset_bytes"]})
        finally:
            # Intermediate copies are not Release assets. Originals stay local.
            shutil.rmtree(stage)
        print(json.dumps({"status": manifest["status"], "output": out.relative_to(root).as_posix(),
                          "assets": [row["filename"] for row in assets]}, allow_nan=False))


if __name__ == "__main__":
    main()
