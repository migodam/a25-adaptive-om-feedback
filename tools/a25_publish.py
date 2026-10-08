"""Explicit paid A25 GitHub publication stages; never invoked automatically."""
from __future__ import annotations

import time

PROCESS_WALL, PROCESS_CPU = time.perf_counter(), time.process_time()

import argparse
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request


TARGET = "migodam/a25-adaptive-om-feedback"
REMOTE = "a25"
GIT_URL = "https://github.com/" + TARGET + ".git"
TAG = "a25-v0.1.0"
BRANCH = "main"
MAX_GIT_BYTES = 100_000_000
REPORT = "A25_RESEARCH_REPORT_ZH.md"
NOTES = """A25: adaptive source-anchored OM feedback

This Release contains the frozen protocol, implementation, Chinese research
report, saved development and prospective validation evidence, reproduction
data, and sanitized action ledgers with completed receipts.

Scientific HOLD and neural-network NOT_RUN remain separate from publication.
GPU health/profiling is not scientific neural training or unseen-scene evidence.
Locked ID/OOD data remain unopened and excluded. No new experiment is performed
by publication. See A25_FINAL_RESEARCH_DECISION.md for the parent's conclusions.
"""


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _timeout(book, requested):
    book.check()
    _, _, charged_cpu = book.elapsed()
    remaining = book.cpu_limit - book.prior_cpu - charged_cpu - book.cpu_reserve
    if remaining <= 1:
        book.check()
        raise RuntimeError("PUBLICATION_TIME_RESERVE_REACHED")
    return max(1., min(float(requested), remaining))


class Actions:
    def __init__(self, root, book):
        self.root, self.book = root, book

    def run(self, arguments, *, label, timeout=60, input_bytes=None, accepted=(0,), anonymous=False):
        self.book.check()
        environment = dict(os.environ)
        environment.update(GIT_TERMINAL_PROMPT="0", GH_PROMPT_DISABLED="1", GH_PAGER="cat")
        if anonymous:
            environment.update(GIT_ASKPASS="", SSH_ASKPASS="")
        with self.book.span("publication_subprocess_" + label, publication_subprocess_actions=1):
            try:
                if anonymous:
                    # A fresh non-repository directory and disabled global/system
                    # configuration prevent inherited helpers or URL rewrites.
                    with tempfile.TemporaryDirectory(prefix="a25-anonymous-git-") as empty:
                        for key in list(environment):
                            if key in {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT"} or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
                                environment.pop(key, None)
                        environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                                           GIT_CONFIG_NOSYSTEM="1", GIT_CEILING_DIRECTORIES=empty)
                        result = subprocess.run(arguments, cwd=empty, env=environment,
                            input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=_timeout(self.book, timeout), check=False)
                else:
                    result = subprocess.run(arguments, cwd=self.root, env=environment,
                        input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        timeout=_timeout(self.book, timeout), check=False)
            except subprocess.TimeoutExpired:
                raise RuntimeError("PUBLICATION_SUBPROCESS_TIMEOUT:" + label) from None
            except OSError:
                raise RuntimeError("PUBLICATION_SUBPROCESS_UNAVAILABLE:" + label) from None
        self.book.check()
        if result.returncode not in accepted:
            # Raw command/output never enters public logs or exceptions.
            raise RuntimeError("PUBLICATION_SUBPROCESS_FAILED:" + label + ":exit" + str(result.returncode))
        return result

    def git(self, *arguments, **kwargs):
        return self.run(["git", *arguments], **kwargs)

    def api(self, endpoint, *, label, absent=False, method=None, payload=None):
        command = ["gh", "api", endpoint]
        input_bytes = None
        if method:
            command.extend(["--method", method])
        if payload is not None:
            command.extend(["--input", "-"])
            input_bytes = json.dumps(payload, allow_nan=False).encode()
        result = self.run(command, label=label, input_bytes=input_bytes,
                          accepted=(0, 1) if absent else (0,))
        if result.returncode:
            if absent and b"HTTP 404" in result.stderr:
                return None
            raise RuntimeError("GITHUB_API_NOT_A_CONFIRMED_404:" + label)
        try:
            return json.loads(result.stdout)
        except ValueError:
            raise RuntimeError("GITHUB_API_JSON_REQUIRED:" + label) from None

    def anonymous_get(self, url, *, label, maximum=5_000_000, byte_range=None):
        headers = {"User-Agent": "A25-publication-verification", "Accept": "application/vnd.github+json"}
        if byte_range:
            headers["Range"] = byte_range
        request = urllib.request.Request(url, headers=headers, method="GET")
        with self.book.span("publication_anonymous_" + label, publication_anonymous_GETs=1):
            try:
                with urllib.request.urlopen(request, timeout=_timeout(self.book, 30)) as response:
                    status = response.status
                    body = response.read(maximum + 1)
                    metadata = {"url": url, "status": status, "bytes_read": len(body),
                                "authorization_header_sent": False,
                                "requested_range": byte_range,
                                "content_type": response.headers.get("Content-Type"),
                                "content_range": response.headers.get("Content-Range")}
            except urllib.error.HTTPError as exc:
                raise RuntimeError("ANONYMOUS_HTTP_FAILED:" + label + ":status" + str(exc.code)) from None
            except (urllib.error.URLError, TimeoutError, OSError):
                raise RuntimeError("ANONYMOUS_GET_FAILED:" + label) from None
        self.book.check()
        if status not in {200, 206} or (len(body) > maximum and byte_range is None):
            raise RuntimeError("ANONYMOUS_RESPONSE_INVALID:" + label)
        # Presigned redirect URLs and response bodies are not recorded.
        return body[:maximum], metadata


def _head(actions):
    head = actions.git("rev-parse", "HEAD", label="head").stdout.decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", head):
        raise RuntimeError("EXPLICIT_GIT_COMMIT_ID_REQUIRED")
    return head


def _origin(actions):
    result = actions.git("remote", "get-url", "origin", label="origin_read", accepted=(0, 2, 128))
    return result.stdout if result.returncode == 0 else None


def _ensure_remote(actions):
    names = actions.git("remote", label="remote_names").stdout.decode().splitlines()
    if REMOTE not in names:
        actions.git("remote", "add", REMOTE, GIT_URL, label="add_a25_remote")
    actual = actions.git("remote", "get-url", REMOTE, label="a25_remote_read").stdout.decode().strip()
    push_url = actions.git("remote", "get-url", "--push", REMOTE, label="a25_push_url_read").stdout.decode().strip()
    if actual != GIT_URL or push_url != GIT_URL:
        raise RuntimeError("EXISTING_A25_REMOTE_URL_MISMATCH; never change origin or another remote")


def _package(root, assets):
    assets = Path(assets)
    if not assets.is_absolute():
        assets = root / assets
    assets = assets.resolve()
    if assets.parent != root / "release_assets":
        raise RuntimeError("EXPLICIT_LOCAL_PACKAGE_DIRECTORY_REQUIRED")
    manifest = json.loads((assets / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    scan = json.loads((assets / "PUBLICATION_SCAN.json").read_text(encoding="utf-8"))
    if (manifest.get("status") != "LOCAL_PACKAGE_READY_NOT_UPLOADED" or scan.get("status") != "PASSED"
            or scan.get("rejected_findings") or manifest.get("test_data_included") is not False
            or manifest.get("locked_paths_read") is not False):
        raise RuntimeError("SUCCESSFUL_CLOSED_PACKAGE_SCAN_REQUIRED")
    rows = manifest.get("assets", [])
    if not rows or len({row["filename"] for row in rows}) != len(rows):
        raise RuntimeError("EXACT_PACKAGE_ASSET_LIST_REQUIRED")
    for row in rows:
        name = row["filename"]
        if not re.fullmatch(r"A25_(?:REPRODUCTION_DATA|COMPLETE_ACTION_LEDGERS)(?:\.part\d{3})?\.zip", name):
            raise RuntimeError("A25_PACKAGE_ASSET_NAME_REQUIRED")
        path = assets / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != row["exact_bytes"]:
            raise RuntimeError("PACKAGE_ASSET_SIZE_OR_IDENTITY_MISMATCH:" + name)
        if not 0 < row["exact_bytes"] <= 2_000_000_000:
            raise RuntimeError("PACKAGE_ASSET_SIZE_LIMIT")
    if not {"REPRODUCTION_DATA", "COMPLETE_ACTION_LEDGERS"} <= {
            "REPRODUCTION_DATA" if "REPRODUCTION_DATA" in row["filename"] else "COMPLETE_ACTION_LEDGERS" for row in rows}:
        raise RuntimeError("BOTH_PUBLIC_RELEASE_ARCHIVES_REQUIRED")
    return assets, manifest


def _forbidden(name):
    parts = PurePosixPath(name).parts
    return (".." in parts or any(part in {"private", ".git", "data", "runs", "release_assets", "transport_variants"}
            or part.startswith(".venv") for part in parts)
            or "HISTORIES.json" in parts or name.startswith("results/a25/jobs/")
            or bool(re.search(r"(?i)credential|secret|password|private", PurePosixPath(name).name))
            or name.endswith((".npz", ".pt", ".prof", ".log", ".zip", ".tar.gz", ".pyc"))
            or (name.endswith(".pdf") and "/figures/" not in name)
            or name == "COST_LEDGER.jsonl")


def _candidates(root):
    paths = {path for pattern in ("*.md", "requirements*.txt", "*.toml") for path in root.glob(pattern)}
    for name in (".gitignore", "ENVIRONMENT.json", "SOURCE_MANIFEST.json", "SOURCE_MANIFEST_A25.json",
                 "FAILURE_LEDGER.jsonl", "results/a25/A25_GATE_DECISION.json",
                 "publication/A25_TERMINAL_RECEIPTS.json"):
        if (root / name).is_file():
            paths.add(root / name)
    for directory, suffixes in (("src", {".py"}), ("tools", {".py"}), ("tests", {".py"}),
                                ("configs/a25", {".json"}), ("docs", {".md"}),
                                ("research", {".md", ".csv", ".json"}),
                                ("results/a25/development", {".csv", ".json"}),
                                ("results/a25/report", {".csv", ".json", ".png", ".svg", ".pdf"}),
                                ("results/a25/learning", {".json"})):
        base = root / directory
        if not base.exists():
            continue
        if base.is_symlink():
            raise RuntimeError("PUBLIC_SOURCE_SYMLINK_REJECTED")
        for path in base.rglob("*"):
            name = path.relative_to(root).as_posix()
            if _forbidden(name):
                continue
            if path.is_file() and path.suffix in suffixes:
                paths.add(path)
    selected = []
    for path in sorted(paths):
        name = path.relative_to(root).as_posix()
        if not _forbidden(name) and not path.is_symlink() and path.stat().st_size <= MAX_GIT_BYTES:
            selected.append(name)
    return selected


def _scan_text(content, name, scan_line, audit):
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        if Path(name).suffix not in {".png", ".pdf"}:
            raise RuntimeError("UNEXPECTED_BINARY_PUBLIC_BLOB:" + name) from None
        return
    suffix = Path(name).suffix
    concrete_credential_lines = None
    if suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            raise RuntimeError("PUBLIC_PYTHON_SOURCE_INVALID:" + name) from None
        concrete_credential_lines = set()
        sensitive = re.compile(r"(?i)api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|secret[_-]?key")
        for node in ast.walk(tree):
            pairs = []
            if isinstance(node, ast.Assign):
                pairs = [(target.id, node.value) for target in node.targets if isinstance(target, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                pairs = [(node.target.id, node.value)]
            elif isinstance(node, ast.Dict):
                pairs = [(key.value, value) for key, value in zip(node.keys, node.values)
                         if isinstance(key, ast.Constant) and isinstance(key.value, str)]
            elif isinstance(node, ast.keyword) and node.arg:
                pairs = [(node.arg, node.value)]
            for key, value in pairs:
                if sensitive.search(key) and isinstance(value, ast.Constant) and isinstance(value.value, str):
                    concrete_credential_lines.update(range(value.lineno, getattr(value, "end_lineno", value.lineno) + 1))
    for number, line in enumerate(text.splitlines(), 1):
        local = {"rejected_findings": [], "pattern_literal_contexts": []}
        scan_line(line, name=name, number=number, suffix=suffix, audit=local)
        for finding in local["rejected_findings"]:
            if (concrete_credential_lines is not None and finding["rule"] == "literal_credential_assignment"
                    and number not in concrete_credential_lines):
                finding["context"] = "source_nonliteral_credential_expression"
                local["pattern_literal_contexts"].append(finding)
            else:
                audit["rejected_findings"].append(finding)
        audit["pattern_literal_contexts"].extend(local["pattern_literal_contexts"])


def _receipts(root, current_job, sanitize):
    rows = []
    for directory in sorted((root / "results/a25/jobs").iterdir()):
        if directory.name == current_job or directory.is_symlink() or not directory.is_dir():
            continue
        path = directory / "job_receipt.json"
        if path.is_file():
            value = json.loads(path.read_text(encoding="utf-8"))
            rows.append(sanitize(value))
    return rows


def _commit(root, actions, job, publication, sanitize, scan_line, write_json):
    receipts = _receipts(root, job, sanitize)
    write_json(publication / "A25_TERMINAL_RECEIPTS.json",
               {"completed_receipts": receipts, "active_publication_job_excluded": job,
                "own_future_terminal_receipt_included": False})
    tracked = actions.git("ls-files", "-z", label="tracked_names").stdout.decode().split("\0")
    forbidden = [name for name in tracked if name and _forbidden(name)]
    # Index removal never opens or deletes private/locked working-tree data.
    for start in range(0, len(forbidden), 100):
        actions.git("rm", "--cached", "--ignore-unmatch", "--", *forbidden[start:start + 100], label="untrack_release_only")
    candidates = _candidates(root)
    ignored = actions.git("check-ignore", "--stdin", "-z", label="ignore_filter",
                          input_bytes="\0".join(candidates).encode() + b"\0", accepted=(0, 1)).stdout.decode().split("\0")
    candidates = [name for name in candidates if name not in set(ignored)]
    for start in range(0, len(candidates), 100):
        actions.git("add", "--", *candidates[start:start + 100], label="stage_public_files")
    staged = actions.git("diff", "--cached", "--name-only", "--diff-filter=ACMRT", "-z", label="staged_names").stdout.decode().split("\0")
    audit = {"rejected_findings": [], "pattern_literal_contexts": [], "matched_values_disclosed": False}
    for name in (name for name in staged if name):
        if _forbidden(name) or name not in candidates:
            raise RuntimeError("STAGED_FILE_OUTSIDE_PUBLIC_ALLOWLIST:" + name)
        content = actions.git("show", ":" + name, label="scan_staged_blob").stdout
        if len(content) > MAX_GIT_BYTES:
            raise RuntimeError("STAGED_PUBLIC_BLOB_TOO_LARGE:" + name)
        _scan_text(content, name, scan_line, audit)
    write_json(publication / "STAGED_SCAN.json", audit)
    if audit["rejected_findings"]:
        raise RuntimeError("STAGED_CREDENTIAL_SCAN_REJECTED; values withheld")
    changed = actions.git("diff", "--cached", "--quiet", label="staged_change_check", accepted=(0, 1)).returncode == 1
    if changed:
        actions.git("commit", "-m", "A25: publish frozen protocol and saved research evidence", label="commit", timeout=120)
    return {"status": "PUBLIC_COMMIT_CREATED" if changed else "PUBLIC_COMMIT_ALREADY_CURRENT",
            "commit": _head(actions), "staged_files_scanned": len([name for name in staged if name]),
            "excluded_index_paths": len(forbidden), "future_receipt_included": False}


def _completed_stage(root, stage, head):
    path = root / "publication" / (stage.upper() + ".json")
    if not path.is_file():
        raise RuntimeError("COMPLETED_PUBLICATION_STAGE_REQUIRED:" + stage)
    record = json.loads(path.read_text(encoding="utf-8"))
    job = record.get("job")
    if not isinstance(job, str) or Path(job).name != job:
        raise RuntimeError("EXPLICIT_PUBLICATION_JOB_REQUIRED")
    receipt = root / "results/a25/jobs" / job / "job_receipt.json"
    if (record.get("commit") != head or not receipt.is_file()
            or json.loads(receipt.read_text(encoding="utf-8")).get("status") != "COMPLETE"):
        raise RuntimeError("CURRENT_HEAD_COMPLETED_PUBLICATION_STAGE_REQUIRED:" + stage)


def _push(actions):
    head = _head(actions)
    _completed_stage(actions.root, "commit", head)
    owner = actions.api("user", label="gh_owner")
    if owner.get("login") != "migodam":
        raise RuntimeError("AUTHORIZED_GITHUB_OWNER_REQUIRED")
    _ensure_remote(actions)
    repo = actions.api("repos/" + TARGET, label="repo_preflight", absent=True)
    if repo is None:
        repo = actions.api("user/repos", label="create_public_a25_repo", method="POST",
                           payload={"name": TARGET.split("/", 1)[1], "private": False,
                                    "description": "A25 adaptive OM feedback: frozen protocol, saved evidence and qualified research conclusions"})
    if repo.get("full_name") != TARGET or repo.get("private") is not False:
        raise RuntimeError("EXACT_PUBLIC_A25_REPOSITORY_REQUIRED")
    actions.git("push", REMOTE, "HEAD:refs/heads/" + BRANCH, label="push_main", timeout=180)
    actions.api("repos/" + TARGET, label="set_default_main", method="PATCH", payload={"default_branch": BRANCH})
    return {"status": "A25_MAIN_PUSHED", "commit": head, "repository": "https://github.com/" + TARGET}


def _remote_ids(actions, patterns):
    result = actions.git("-c", "credential.helper=", "-c", "core.askPass=", "-c", "http.extraHeader=",
                         "ls-remote", GIT_URL, *patterns, label="anonymous_remote_refs", anonymous=True)
    return {line.split()[1]: line.split()[0] for line in result.stdout.decode().splitlines() if len(line.split()) == 2}


def _release(root, actions, job, assets, manifest, publication, sanitize, scan_line, write_json):
    _ensure_remote(actions)
    head = _head(actions)
    _completed_stage(root, "push", head)
    refs = _remote_ids(actions, ["refs/heads/main", "refs/tags/" + TAG, "refs/tags/" + TAG + "^{}"])
    if refs.get("refs/heads/main") != head:
        raise RuntimeError("RELEASE_REQUIRES_PUSHED_HEAD_MAIN")
    remote_tag = refs.get("refs/tags/" + TAG + "^{}", refs.get("refs/tags/" + TAG))
    if remote_tag is not None and remote_tag != head:
        raise RuntimeError("EXISTING_A25_TAG_POINTS_TO_DIFFERENT_COMMIT; no force movement")
    local = actions.git("rev-parse", "--verify", "refs/tags/" + TAG + "^{commit}", label="local_tag", accepted=(0, 128))
    if local.returncode == 0 and local.stdout.decode().strip() != head:
        raise RuntimeError("EXISTING_LOCAL_A25_TAG_POINTS_TO_DIFFERENT_COMMIT")
    if local.returncode:
        actions.git("tag", TAG, head, label="create_a25_tag")
    if remote_tag is None:
        actions.git("push", REMOTE, "refs/tags/" + TAG + ":refs/tags/" + TAG, label="push_a25_tag")
    notes = publication / "A25_RELEASE_NOTES.md"
    notes.write_text(NOTES, encoding="utf-8")
    release = actions.api("repos/" + TARGET + "/releases/tags/" + TAG, label="release_preflight", absent=True)
    command = ["gh", "release", "create" if release is None else "edit", TAG, "--repo", TARGET,
               "--title", "A25 v0.1.0: saved evidence and reproducible protocol", "--notes-file", str(notes)]
    command.extend(["--verify-tag"] if release is None else ["--target", head])
    actions.run(command, label="release_create_or_edit")
    receipts = _receipts(root, job, sanitize)
    selected = [row for row in receipts if row.get("stage") in {
        "public_release_packaging", "report", "publication_commit", "publication_push"}]
    if not {"public_release_packaging", "report", "publication_commit", "publication_push"} <= {
            row.get("stage") for row in selected if row.get("status") == "COMPLETE"}:
        raise RuntimeError("COMPLETED_PACKAGE_REPORT_COMMIT_PUSH_RECEIPTS_REQUIRED")
    if not any(row.get("job") == manifest["job"] and row.get("status") == "COMPLETE" for row in selected):
        raise RuntimeError("THIS_PACKAGE_TERMINAL_RECEIPT_REQUIRED")
    receipt_file = publication / "publication_receipts.json"
    write_json(receipt_file, {"completed_receipts": selected, "active_release_job_excluded": job,
                            "own_future_terminal_receipt_included": False})
    files = [assets / row["filename"] for row in manifest["assets"]]
    files.extend([assets / "PACKAGE_MANIFEST.json", assets / "PUBLICATION_SCAN.json", receipt_file])
    audit = {"rejected_findings": [], "pattern_literal_contexts": []}
    for path in files:
        if path.suffix != ".zip":
            _scan_text(path.read_bytes(), path.name, scan_line, audit)
    if audit["rejected_findings"]:
        write_json(publication / "RELEASE_METADATA_SCAN.json", audit)
        raise RuntimeError("RELEASE_METADATA_SCAN_REJECTED; values withheld")
    actions.run(["gh", "release", "upload", TAG, "--repo", TARGET, "--clobber", *map(str, files)],
                label="upload_exact_a25_assets", timeout=600)
    return {"status": "A25_RELEASE_UPLOADED_PENDING_ANONYMOUS_VERIFICATION", "commit": head,
            "tag": TAG, "release_url": "https://github.com/" + TARGET + "/releases/tag/" + TAG,
            "uploaded_assets": [{"filename": path.name, "exact_bytes": path.stat().st_size} for path in files],
            "own_future_terminal_receipt_included": False}


def _verify(root, actions, assets, manifest, publication):
    head = _head(actions)
    repo_url = "https://github.com/" + TARGET
    report_url = repo_url + "/blob/" + head + "/" + REPORT
    raw_url = "https://raw.githubusercontent.com/" + TARGET + "/" + head + "/" + REPORT
    evidence = []
    _, item = actions.anonymous_get(repo_url, label="repo_page")
    evidence.append(item)
    _, item = actions.anonymous_get(report_url, label="chinese_report_page")
    evidence.append(item)
    raw, item = actions.anonymous_get(raw_url, label="raw_chinese_report")
    evidence.append(item)
    text = raw.decode("utf-8")
    if "A25" not in text or not re.search(r"[\u4e00-\u9fff]", text):
        raise RuntimeError("DIRECT_CHINESE_A25_MARKDOWN_REQUIRED")
    repo_body, item = actions.anonymous_get("https://api.github.com/repos/" + TARGET, label="repo_api")
    evidence.append(item)
    repo = json.loads(repo_body)
    if repo.get("full_name") != TARGET or repo.get("private") is not False or repo.get("default_branch") != BRANCH:
        raise RuntimeError("ANONYMOUS_PUBLIC_MAIN_REPOSITORY_MISMATCH")
    refs = _remote_ids(actions, ["refs/heads/main", "refs/tags/" + TAG, "refs/tags/" + TAG + "^{}"])
    if refs.get("refs/heads/main") != head or refs.get("refs/tags/" + TAG + "^{}", refs.get("refs/tags/" + TAG)) != head:
        raise RuntimeError("ANONYMOUS_MAIN_TAG_HEAD_MISMATCH")
    release_body, item = actions.anonymous_get("https://api.github.com/repos/" + TARGET + "/releases/tags/" + TAG, label="release_api")
    evidence.append(item)
    release = json.loads(release_body)
    if release.get("tag_name") != TAG or release.get("draft") is not False:
        raise RuntimeError("ANONYMOUS_A25_RELEASE_MISMATCH")
    available = {row["name"]: row for row in release.get("assets", [])}
    expected = {row["filename"]: row["exact_bytes"] for row in manifest["assets"]}
    for path in (assets / "PACKAGE_MANIFEST.json", assets / "PUBLICATION_SCAN.json", publication / "publication_receipts.json"):
        expected[path.name] = path.stat().st_size
    if set(available) != set(expected):
        raise RuntimeError("EXACT_PUBLIC_RELEASE_ASSET_SCOPE_REQUIRED")
    downloads = []
    for name, size in expected.items():
        row = available.get(name)
        if not row or row.get("size") != size:
            raise RuntimeError("PUBLIC_RELEASE_ASSET_SIZE_OR_NAME_MISMATCH:" + name)
        url = row["browser_download_url"]
        if not url.startswith(repo_url + "/releases/download/" + TAG + "/"):
            raise RuntimeError("ASSET_DOWNLOAD_OUTSIDE_EXACT_A25_RELEASE")
        body, item = actions.anonymous_get(url, label="asset_" + ("zip_header" if name.endswith(".zip") else "metadata"),
                                         maximum=4 if name.endswith(".zip") else 5_000_000,
                                         byte_range="bytes=0-3" if name.endswith(".zip") else None)
        if name.endswith(".zip") and body != b"PK\x03\x04":
            raise RuntimeError("ANONYMOUS_ACTUAL_ZIP_HEADER_REQUIRED:" + name)
        downloads.append({"filename": name, "exact_api_bytes": size, "zip_header_verified": name.endswith(".zip"), **item})
    decision = json.loads((root / "results/a25/A25_GATE_DECISION.json").read_text(encoding="utf-8"))
    learning = json.loads((root / "results/a25/learning/NOT_RUN_DECISION.json").read_text(encoding="utf-8"))
    return {"status": "ANONYMOUS_PUBLICATION_VERIFIED", "verified_utc": _utc(), "commit": head,
            "repository_url": repo_url, "report_url": report_url, "raw_markdown_url": raw_url,
            "release_url": repo_url + "/releases/tag/" + TAG, "tag": TAG, "evidence": evidence,
            "assets": downloads, "main_and_tag_equal_local_HEAD": True,
            "credential_or_authorization_headers_used_for_verification": False,
            "scientific_status": decision.get("status", "UNAVAILABLE"),
            "scientific_status_source": "results/a25/A25_GATE_DECISION.json",
            "neural_training_status": learning.get("status", "UNAVAILABLE"),
            "neural_status_source": "results/a25/learning/NOT_RUN_DECISION.json",
            "scientific_acceptance_inferred": False,
            "locked_ID_OOD": "UNOPENED", "new_experiments_performed": False,
            "own_future_terminal_receipt_included": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("commit", "push", "release", "verify"), required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--assets", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--config", default="configs/a25/campaign.json")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root / "tools"))
    from a24.contracts import active_ledger
    from a25.budget import charged_job, write_json
    from a25.reporting import Sanitizer
    from a25_package import _safe_metadata, _scan_line, _checked
    config_path = root / args.config
    _checked(root, config_path)
    if config_path.relative_to(root).parts[:2] != ("configs", "a25"):
        raise RuntimeError("CAMPAIGN_CONFIG_ALLOWLIST_REQUIRED")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    with charged_job(root, args.job, device="cpu", config=config,
                     metadata={"stage": "publication_" + args.stage, "repository": TARGET}) as book, active_ledger(book):
        book.started_wall = min(book.started_wall, PROCESS_WALL)
        book.started_cpu = min(book.started_cpu, PROCESS_CPU)
        if (root / "results/a25/learning/LOCKED_OPEN.json").exists():
            raise RuntimeError("THIS_PUBLICATION_SCOPE_REQUIRES_UNOPENED_LOCKED_TEST")
        assets, manifest = _package(root, args.assets)
        publication = root / "publication"
        publication.mkdir(exist_ok=True)
        actions, sanitizer = Actions(root, book), Sanitizer(root)
        sanitize = lambda value: _safe_metadata(value, sanitizer)
        original_origin = _origin(actions)
        with book.span("publication_stage_" + args.stage, publication_stages=1):
            if args.stage == "commit":
                result = _commit(root, actions, args.job, publication, sanitize, _scan_line, write_json)
            elif args.stage == "push":
                result = _push(actions)
            elif args.stage == "release":
                result = _release(root, actions, args.job, assets, manifest, publication, sanitize, _scan_line, write_json)
            else:
                result = _verify(root, actions, assets, manifest, publication)
        if _origin(actions) != original_origin:
            raise RuntimeError("SHARED_ORIGIN_CHANGED")
        result.update(origin_preserved=True, publication_stage=args.stage, job=args.job,
                      source_package=assets.relative_to(root).as_posix())
        write_json(publication / ("VERIFIED.json" if args.stage == "verify" else args.stage.upper() + ".json"), result)
        write_json(root / "results/a25/jobs" / args.job / "result.json", sanitize(result))
        print(json.dumps({key: result[key] for key in ("status", "commit", "publication_stage", "origin_preserved")}, allow_nan=False))


if __name__ == "__main__":
    main()
