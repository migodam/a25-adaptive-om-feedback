# A25 learning implementation handoff

Implementation only: no physical labels, numerical tests, health timings or
training were executed by this worker. A24 is unchanged. The parent owns
closure admission, science interpretation, model freezing and all receipts.

## Interfaces

- `TorchReference.from_npz(path, book=..., config=..., device='cpu')` loads
  `chi_b, eb, yb, Db, G, S, incident, Ug, Vg, volume, grid, descriptor`; accepts
  the dataset export's `L_b` and frozen `step`. It factors the known-background
  matrix once, counts preparation, and stores no inverse. Optional equal-size
  disjoint `D_indices/D_blocks` support the package local primitive.
  Portable A25 caches require `closure_provenance`: admitted builder/rank,
  probe seed, source/protocol, exact background descriptor, basis identity and
  no truth/oracle use. TASK_R32 checks four material/eight receiver probes.
  Checkpoints bind the complete descriptor and exact CPU copies of Ug/Vg;
  loading rejects changed factors with unchanged metadata, without hashes.
- `TorchRelativeModel(reference, 'L'|'R')(mass, recover_current=True)` returns
  mass/chi/h/data/w/field/current/margins. `jvp`, `adjoint`, `vjp_complex` and
  `data_gradient` use real material mass coordinates and the exact discrete
  adjoint of that forward map. They retain higher derivatives.
- `build_model('N0'|'N1'|'N2'|'N3', references, normalizer=..., config=...,
  blocks=3)` consumes `[B,Q,S]` complex128 observations, background ID strings,
  and an explicit `[B,2N]` float64 `initial_mass`. N0 has four stages;
  N1/N2/N3 accept three primary or four control stages. Result includes shared
  full material, current, data, stage materials and optional consistency.
- `ParentDataset.from_npz(path, role='train'|'validation', parent_ids=...)`
  uses the dataset agent's guarded loader. Required legal preprocessing keys
  are `initial_mass`, `lambda`, and `initial_wall`. It rejects failed rows and
  parent-condition omissions; it never removes bad parents.
- `fit_normalizer`, `benchmark_health`, `select_update_budget`, `train_one`
  are libraries accepting the parent's active `book`. Selection uses costs
  for all eight primary jobs plus three four-block/64-parent controls.

## Frozen implementation choices

Physics tensors are complex128/float64; CNNs are float32. CPU/CUDA only.
General non-Hermitian solves, strict singular-value guards, no jitter,
pseudoinverse, Hermitian shortcut or fallback. Guard decisions and reporting
may detach; state-dependent gradient features never detach. Autograd reverse
hooks count operation invocations; exact resource charges come from inclusive
central receipts, not invented LU counts for Torch's internal backward.

Canonical L/R current is `cb + Rb*w`. Its measured data agree with `yb+Db*w`.
The closure field can differ from `incident+G*current`; report the field
discrepancy and `Rmat=current-chi*(incident+G*current)`. No approximate current
is promoted to an exact material-consistent state.

N1/N2/N3 have identical ten source-symmetric feature channels and identical
two-level U-shaped material CNNs (base width32, 128 bottleneck), so trainable
parameter counts match exactly. N1 versus N2 changes only L versus R closure.
N3 uses L features with a learned material recurrence, without the explicit
fixed data-gradient step. CNN increments scale by .25 times the frozen
train-only material RMS. The certified common TV initializer is supplied by
the dataset layer; TV also enters the common loss and is not a certified
proximal operation inside learned blocks.

N0 follows SOM-Net Fig2/Algorithm1: truncated receiver-SVD deterministic
current (rank15), four distinct current CNNs, exact G-field update, source
shared material ratio, and S-current data. Lossy input has four channels.
Its two-level U-shaped backbone uses widths64/128/256, double 3x3
conv+BN+ReLU, 2x2 pooling/transposed convolutions, skip concatenations and a
1x1 output. Width256 at the bottom is an inference from an unlabeled figure.
Shared certified initial material, known lossy background, 8 sources,
24x24 grid, normalized current units, small dataset and matched loss weights
are adaptations. This is not author code or an official reproduction.
Source: https://arxiv.org/pdf/2209.03567 (page4); local PDF/text retained in
`Gaussian/delegated/a12_literature`. No official source/license established.

All arms have equal supervision rights: material1, data.1, current.1,
SSIM.05 and observation-derived common TV lambda. Data divides by background
data norm squared; material/current divide by train-only RMS squared. SSIM
uses relative-permittivity real/imag channels with fixed domain ranges4.5/.5.
TV uses the increment `chi-chi_b`, joint real/imag full-grid forward
differences with Neumann terminal zeros, and `sqrt(volume)*sum(cell norms)`.
The differentiable surrogate uses smoothing1e-12 and subtracts its constant
zero-state offset; evaluation reports the exact unsmoothed physical TV.
AdamW1e-3,
weight decay1e-5, four independent parents/one condition each, clipping1,
validation every100, deterministic seed schedule, one host Torch thread.
Normalization uses all selected training rows, common L features at their
certified initialization, deterministic-current inputs and training-label
RMS scales; neither validation nor test is read to fit it.

## Parent-only commands

After closure admission and cache availability, from the A25 repository:

```sh
PYTHONPATH=src "/Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/.venv_nn/bin/python" -B -m a25.training --mode health --root . --config configs/a25/campaign.json --cache weak=data/background/weak.npz --cache ring=data/background/ring.npz --device cpu --job learning-health-cpu-01 --out results/a25/learning/health_cpu --repeats 2
```

This benchmarks known-background health only (one paid warm-up plus two paid
updates per topology), not accuracy. Parent supplies remaining CPU/GPU
allowances to `select_update_budget`, freezes its JSON, then admits training.
The CLI `train` mode additionally requires `--method`, `--train-size`, and
`--cost-selection`; it opens train/validation only. Parent must retain
preprocessing costs in inference timing and select/freeze every model before
opening locked test truth. No partial cheap run substitutes for the fixed
500/1000/2000 schedule.

## Verification scope

`tests/test_a25_torch.py` contains tiny-grid NumPy/Torch forward identities,
real packing, source-shared symmetry, JVP/adjoint identity, finite differences,
higher-gradient verification, singular-core rejection, parameter matching,
paper backbone shape, parent sampling and cost-only selection boundaries.
It deliberately requires a charged active ledger; the parent runs it.

## Locked evaluation

`run_locked(root, cfg, book, device='cuda')` reads the parent's
`results/a25/learning/MODEL_FREEZE.json` (override: `locked_freeze_record`),
checks `_freeze_allowed`, and requires all eleven completed, validation
selected checkpoints from `TRAINED_MODELS.json` to match its exact path set.
Relative checkpoint paths survive transfer; no new hash is computed.
`learning/LOCKED_OPEN.json` is exclusively reserved before either locked
split loads. The marker is immutable even if evaluation fails; no second
test opening, retraining or checkpoint/rank choice occurs here.
Cold online reads receive that validated freeze context. Noiseless quality
uses `||full_data-observed||/||observed-yb||`; the total-observed denominator
is retained separately as `full_data_total_relative_residual`. Zero
differential norm stays undefined and cannot satisfy the noiseless gate.

Outputs under `learning/locked_evaluation`: `cases.csv`, `timing.csv`,
`parent_summary.json`, `paired_bootstrap.json`, `checkpoint_setup.json`,
`summary.json`, and per-model/split image-array NPZs. All 2816 cases retain
failures/missing states. Fields carry model/depth/train size, family,
structural-versus-contrast OOD label, parent, background, amplitude and noise.
Native full-state audits at predicted material use unchanged NumPy A24
Physics2D, separately count every LU/RHS/G/S action, and never feed the model.
Reported TV/objective uses exact unsmoothed joint full-grid increment TV.
Parent means and 2000 paired parent bootstrap intervals refuse incomplete
coverage; scientific gates remain the parent's decision.

The fixed timing subset is first ID parent per public family, ring background,
amplitude1.2,20dB, primary 64-parent N0/N1/N2/N3. Warm/cold modes rerun actual
CPU certified initialization with fresh material and TV warm state. Cold mode
rereads ONLINE observation arrays, checkpoint and background arrays, constructs
fresh model/factors, and resets material state. OS disk caching is uncontrolled;
this is process-state cold timing, never a physical disk-cold claim. Cached
image timing starts with device inputs prepared and includes host image return;
complete timing adds preprocessing/input transfer/setup. Offline evaluator
tensor export and native full-state audit are separate. Original cached
initialization times remain descriptive, not free inference preprocessing.
The evaluation phase is capped at900 seconds plus the central cumulative
CPU/GPU limits. Interrupted image arrays and explicit NOT_RUN rows survive.
No numerical evaluation was executed by this worker.
