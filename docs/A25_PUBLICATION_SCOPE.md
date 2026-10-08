# A25 public Release scope

The packaging helper uses only saved evidence. It performs no simulation,
training, test opening, upload or scientific gate decision. The parent owns
publication after local review. Code availability is not an experiment result.

`tools/a25_package.py --job <new-job-id> --config configs/a25/nn_blocking_wait.json`
runs under a CPU `charged_job` and the active accounting ledger. Imports,
selection, text sanitization, credential scan, ZIP writing and cleanup belong
to that paid attempt. It requires the locked-test opening marker to be absent.
Run it from the repository with the frozen interpreter and `PYTHONPATH=src`.

The helper creates `release_assets/<job>/` containing:

- `A25_REPRODUCTION_DATA.zip`: Phase0 input/reference NPZs; development image
  and state NPZs, saved histories/preparations/metrics; the 16 clean and 32
  online A24 B0 inputs for historical parents 2401–2404; any saved eight
  amplitude1.8 clean inputs; `data/train.npz`, `data/validation.npz`, the weak
  and ring background caches; public generation manifest/geometry/summary;
  and this scope document. Historical development truth is already exposed.
  Optional metadata includes root `REPRODUCING_A25.md` and
  `SOURCE_MANIFEST_A25.json`. The explicit optional directory
  `results/a25/development/prospective_regime_validation/` may contribute
  `METRICS.csv`, `TASK_AUDIT.csv`, `HISTORIES.json`, `PREPARATIONS.json`,
  `PROVENANCE.json`, `SUMMARY.json`, `CHECKPOINT_METRICS.csv`, `EXPOSURE.json`,
  `FAILURES.json`, `ACTIONS.jsonl`, and saved NPZ state/image arrays in
  that directory or its `images`, `states`, `state_arrays`, `arrays` subdirectories.
  These prospective no-NN outputs reuse existing validation labels, create
  no new labels and do not open locked ID/OOD. Absent outputs are not claimed.
- `A25_COMPLETE_ACTION_LEDGERS.zip`: actual per-job COST/FAILURE JSONL files,
  root merged ledgers, available B0 ledgers, and sanitized receipts, job
  manifests/checkpoints, configs and environment metadata. It preserves all
  available records, including failed attempts and transport costs. It does
  not deduplicate or reinterpret their numerical/counter fields.
- `PACKAGE_MANIFEST.json`: exact archive byte sizes, member counts, original
  and public member byte sizes, JSONL record counts, completed-job cutoff,
  absent optional files and the path of the paid packaging receipt.
- `PUBLICATION_SCAN.json`: scan result and safe file/line/rule context.
  Matched credential values are never included in diagnostic output.

The packaging job's terminal `job_receipt.json` exists only after its paid
context exits. It must be sanitized and published separately alongside the
manifest. The ledger ZIP is an explicit snapshot of completed jobs before
packaging; it must not claim to contain its own future terminal receipt.
The local original receipt and all original ledgers remain unchanged.

Every archive enables ZIP64 and stays at or below 2,000,000,000 bytes. If
needed, the helper creates independent `.part001.zip`, `.part002.zip`, etc.
Extract all parts into the same directory. A single member too large for
the asset cap is rejected explicitly; no evidence is silently omitted.
The archive manifest records actual byte sizes and uses no content hashes.

JSON and JSONL text metadata use `a25.reporting.Sanitizer`; numerical leaves
are restored exactly from the original records. JSONL is processed one line
at a time. NPZ files are copied byte for byte. The paid scan inspects public
text, NPZ string metadata without unpickling, and explicitly allowlisted
A25 Python/Markdown source text. It rejects actual token formats, private-key
blocks and literal credential assignments. Detector-pattern literals can
produce a safe false-positive context record without blocking a whole source
path; actual-looking values receive no exemption based on file extension.

Excluded paths are `data/locked/**`, `data/online/locked_*` including their
per-case directories, `private/**`, `.git`, virtual environments, raw run
stdout/stderr, credentials, paper PDFs, binary model checkpoints, duplicated
transport variants and every file outside the explicit allowlist. Locked
ID/OOD observations, truth, actual noise and labels remain unopened and are
not read, copied, scanned, archived or released. Train/validation and known
backgrounds can reproduce health and permitted learning inputs; this Release
does not expose a blind benchmark or establish unseen-scene performance.

The parent completed paid packaging in `public-release-package-retry-002`:
`A25_REPRODUCTION_DATA.zip` has 182,083,281 bytes and 2,379 members;
`A25_COMPLETE_ACTION_LEDGERS.zip` has 50,873,059 bytes and 292 members.
The publication scan passed with zero rejected findings. Thirteen filename
aliases on the case-insensitive filesystem refer to the same physical files;
the archive preserves each actual filename and records those aliases without
content hashing. The first packaging failure remains charged and retained.

These are local packaging facts. Anonymous Release availability is established
separately by the parent's explicit paid publication/verification stages.
