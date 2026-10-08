# A25 accounting and data interfaces

Status: implementation prepared; no labels, tests, training or remote jobs were executed by this worker. Numerical and scientific admission belongs to the parent.

The worker owns `src/a25/budget.py`, `dataset.py`, `metrics.py`, `tools/a25_remote.py`, and `tests/test_a25_guards.py`. Inherited A24 source and evidence were not changed.

## Resource contract

`with charged_job(root, job, device='cpu', config=config, metadata={...}) as book:` creates a new paid attempt under `results/a25/jobs/<job>/`. CPU-only charge is `max(inclusive wall, process CPU)`; CUDA charge is host process CPU plus independently charged whole-job GPU occupied wall. The cumulative limits are 7,200 CPU seconds and 14,400 GPU seconds. Defaults retain 15 CPU seconds and 30 GPU seconds for stopping; these reserves are configurable within the hard caps.

Only A25 receipts are restored. Accepted successful and failed receipts are immutable; retries require a new job ID. A started manifest without a terminal receipt blocks new work because its interruption tail is unknown. Checkpoints do not silently convert an unknown tail into zero. Action reservations are restored from the maximum durable local receipt/ledger counts. `new_clean_labels`, `new_labels` and `new_full_forward_labels` share one cumulative cap of 456, including failed generation attempts.

The book supports inherited physics `span`, `scope`, `check`, `snapshot`, `delta`, `counts`, `walls`, and `reserve`. Reservations, manifests, checkpoints and receipts are flushed and fsynced; ordinary action rows are flushed. A checkpoint is refreshed approximately once per second during checks. Nested span walls are exclusive diagnostics; resource totals use inclusive job measurements.

Job lock identity and case warm-state identity are distinct. `book.check_owner(book.metadata['owner_id'])` verifies the job owner and held lock bytes. The material solver checks its own case-specific `ProxProblem.owner_id`.

The exact shared remote file lock is `D:/AI/A20_OPM_IMAGING/runs/gpu.lock`. It uses exclusive file creation and JSON owner metadata compatible with A20. A foreign or changed lock is retained, never automatically removed.

The foreground local GPU monitor uses `charged_job(...device='cuda',gpu_host_only=True)`: it charges actual monitor process CPU, reports raw waiting wall separately, and charges zero GPU seconds. Remote child and exclusive controller/import/stop tails have independent immutable receipts, imported locally before a subsequent job. This avoids charging blocked SSH waiting as a second CPU-only job or duplicating GPU wall.

## Manifest and NPZ contract

`generate_dataset(root, config, book, solver=selected_solver)` persists the complete generator manifest before generating any labels. `data/locked/generator_manifest.json` holds all predetermined geometry parameters; `data/manifest.json` exposes only split, family, OOD type, contrast allocation and nested parent IDs. Both are immutable.

There are 112 independent parents: 64 train, 16 validation, 16 ID test, 16 OOD test. The four families are shell, asymmetric piecewise, smooth (two Gaussian bumps), and mixed scale (shell, Gaussian and segment). Each split is balanced over families; train32 selects eight predetermined parents per family from train64. Every OOD family has two structural-combination parents at amplitudes 0.3/1.2 and two ID-geometry contrast parents at 1.5/1.8. There are 448 full-state labels (two backgrounds and two contrasts per parent) and 896 observations (clean and 20 dB variants sharing each label). Eight development labels remain reserved separately by the parent campaign.

The exact native cell, source and receiver ordering is saved in `data/geometry.json` and the portable background archives. Complex arrays use complex128; material mass coordinates use float64; sources are always the last array axis. Noise is generated once with independent Gaussian real/imaginary variance `sigma²/2`; actual noise vectors are cached under the closed generator directory, excluded from online input archives.

Consolidated labelled files are `data/train.npz`, `data/validation.npz`, and `data/locked/{locked_id,locked_ood}.npz`. Online-only siblings live at `data/online/{split}.npz` and omit material truth, clean targets, current labels and actual noise. Labelled NPZs contain:

- `chi[M,N]`, `current[M,N,8]`, `data[M,32,8]`, `clean[M,32,8]`.
- `initial_mass[M,2N]`, `lambda[M]`, `initial_wall[M]`, `sigma[M]`.
- Per-observation `parent_id`, `background_id`, `split`, `variant_id`, `case_id`, `family`, `ood_type`, `amplitude`, `noise_db`, and `status`.
- Scalar Unicode `geometry_descriptor`, `initializer_id`, and `manifest_id`.

Initializations use the parent's selected certified TV solver, original background Jacobian step and shared TV rule. An uncertified initialization stays as an explicit failed row with NaN initialization fields; its parent appears in `bad_initial_parents`. The training loader rejects failed datasets instead of removing parents. Cached preprocessing saves training preparation, but inference must recompute/time it or explicitly report the measured separate `initial_wall`.

Portable `data/background/{weak,ring}.npz` exports contain `chi_b`, `eb`, `yb`, `Db`, `G`, `S`, `incident`, `L_b`, `Ug`, `Vg`, `J`, `step`, `beta`, `data_norm2`, `volume`, `grid`, coordinate arrays and JSON descriptors. `L_b` is an already paid background matrix, not a new inverse solve. Return factors use the explicitly admitted `selected_nn_closure` and the same background-dependent seed as the non-NN closure admission.

`load_dataset(...role='evaluation',freeze_record=...,allow_failed=True)` opens locked truth only after a record with `status='FROZEN'`, `model_selection_frozen=True` and nonempty checkpoints. Training and validation roles cannot open test truth even with that record. The parent evaluator additionally verifies all 11 exact checkpoint selections and creates an exclusive one-open marker. Canonical freeze path: `results/a25/learning/MODEL_FREEZE.json`.

## Remote commands

Use the existing external/ignored private SSH config and A22 transport helper. Their contents and connection values are never printed or archived. Remote root is `D:/AI/A25_ADAPTIVE_OM_FEEDBACK`; interpreter is `D:/python/python.exe`.

`python -B tools/a25_remote.py preflight --transport-helper <helper.py> --private-config <private.json>` performs only an environment, queue and lock query. Every invocation is a charged local action.

`push --scope source` sends public source/runtime configuration. `push --scope train` adds train/validation, online-only observations, manifest and background cache. `push --scope accounting` transfers accepted A25 receipts. `push --scope evaluation --freeze-record <MODEL_FREEZE.json>` is a separate post-freeze truth release. No scope copies private files or credentials.

`run --stage health|train|locked --job a25-<unique-id> --device cuda --config configs/a25/nn_admitted.json --timeout 10800` invokes the parent's GPU driver. Health, training and locked evaluation remain separate explicitly invoked stages. The controller bounds elapsed GPU occupancy and measured child/host CPU, records failures and interruption costs, checks the shared queue, and only releases an observed child-owned lock after confirmed exit and queue clearance.

`pull` retrieves A25 results and logs. Accepted receipts cannot change; divergent non-receipt traces are retained as separate variants. Source/config/data archives reject private paths, escapes and symlinks. No SHA256 checks are introduced.

## Metrics and verification

`material_metrics` accepts already charged evaluator arrays and performs no physics solves. It reports full/delta material errors, real/imaginary delta errors, support IoU, edge error, physical violations, full-data residuals and supplied-current consistency. Undefined reference norms remain undefined.

`parent_equal` averages variants within each independent parent, then parents equally. Its A25 default requires all eight observation variants. Missing/failed parents do not become a passing aggregate. `paired_parent_bootstrap` resamples paired parent means with exactly 2,000 draws and retains incomplete coverage; this worker makes no numerical interpretation.

Guard tests were written for cumulative restoration, failed attempts, receipt immutability, interrupted jobs, label aliases/cap, owner locks, GPU-monitor wait accounting, balanced nested families/OOD allocation, closed truth, deployment scope, and parent aggregation. They must be executed through the parent's charged CLI; implementation alone is not validation.
