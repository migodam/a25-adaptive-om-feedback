# A25 constrained-TV numerical implementation

Owned files: `src/a25/prox.py`, `src/a25/socp_reference.py`,
`tests/test_a25_prox.py`, and this directory. A24 source, its failure artifacts,
physics, experiment drivers, gates and configuration are not modified here.
The worker writes code and performs static parsing only. Numerical tests and
experiments are run by the parent in A25 charged jobs.

## Public interfaces

```python
from a25.prox import ProxProblem, solve_prox

problem = ProxProblem(v, background, weight, grid_shape, volume,
                      config, owner_id)  # seventh positional argument
result = solve_prox(problem, warm_state=None, budget=book)
# result.x, result.warm_state, result.metadata, result.converged, result.cost

from a25.socp_reference import solve_socp_reference
reference = solve_socp_reference(problem, budget=book, comparison=result)
# reference.x, reference.p, reference.lower_dual, reference.upper_dual,
# reference.epigraph, reference.raw_soc_dual, reference.metadata
```

`ProxResult` also permits `(x, metadata)` unpacking. The thin A25
`prox_tv_box(..., book=book)` bridge has the A24-shaped signature but does not
expose persistent state; trajectory code should use `solve_prox` directly.
`ProxFailure` preserves `.result`, `.meta`, and `.warm_state`. Configure
`prox_raise_on_failure=False` to retain explicit failure results. Owner budget
exhaustion always propagates `BudgetExceeded`; it is not a solver fallback.
The independent reference returns explicit failures by default; set
`reference_raise_on_failure=True` for `ReferenceFailure` with result/meta.

The parent-provided `BudgetLedger` supports spans, checks, counters,
snapshots/deltas and terminal receipts. The solver calls
`check_owner(book.owner_id)` for job-lock ownership. A separate
`ProxProblem.owner_id` identifies the case/method history and must match the
warm state. The case ID is never passed as the job-lock owner. A shared
initializer state may be copied and explicitly re-owned by the parent before
forking equal initialization into different arms.

## Frozen problem and certificates

The material vector is `sqrt(volume) * [Re chi; Im chi]` in C cell order.
For cubic cells in dimension `d`, the physical TV coefficient is
`volume**((d-1)/d) / sqrt(volume)`. The problem is exactly

`0.5 * ||x-v||² + weight * coefficient * sum_i ||D_i(x-background)||₂ + I_box(x)`.

The joint norm contains both material channels and all outgoing spatial
directions. Final boundary rows are zero (Neumann). The physical absolute
material box defaults to Re[-0.5,4], Im[0,0.5], multiplied by sqrt(volume).
TV acts on the difference from the known background. There is no new prior,
ridge, material-coordinate conversion, or post-solve primal projection.
`weight` is already the outer step times physical TV lambda; callers must not
multiply the step twice. A single cell volume assumes equal side lengths;
anisotropic-cell spacing is outside this unchanged contract.

The production certificate is imported from frozen A24 and always uses
`tau_cert = sigma_cert = .99 / (2*sqrt(d))`. Internal accelerated steps never
enter its residual normalization. KKT and normalized gap remain 1e-6,
physical box feasibility remains 1e-10, and physical material scale remains
1.0. Attempts to change these values are refused. Metadata retains all A24
components and adds mass stationarity norm, physical RMS stationarity,
fixed certificate steps, and the strongly convex feasible-gap primal-error
bound. This bound is conditional on feasible primal/dual points and declared
floating point roundoff; a gap tolerance is not an equally sized norm-error
tolerance. Primal and dual vectors are not compared by equality across
different solvers because the primal is unique and the dual need not be.

## Numerical modes and state

Config `prox_algorithm` (also `algorithm`) selects `old_pdhg`,
`extended_pdhg`, `accelerated_pdhg`, or conditional `fgp`. Short aliases
`old`, `extended`, and `accelerated` are accepted. Old PDHG is a cold A24
control with at most 2,000 iterations. Extended/accelerated PDHG have a
20,000-iteration ceiling. All use an inclusive two-second ceiling, which can
be shortened but not expanded. Check interval defaults to ten.

Extended PDHG retains A24's fixed steps and extrapolation. Accelerated PDHG
uses Chambolle–Pock Algorithm 2, with gamma=1 for the exact quadratic plus
box: theta=(1+2*tau)^(-1/2), tau*=theta, sigma/=theta. This preserves the
operator-product bound. It does not promise faster convergence of the frozen
dual residual. The parent's recorded comparison found accelerated PDHG
unsuitable for most tested inputs; no worker success claim supersedes that
evidence.

FGP is implemented with the same original objective: projected smooth-dual
ascent with Lipschitz bound 4d and analytic primal recovery
`clip(v-D* p)`. It requires the explicit parent configuration
`fgp_authorized=True`; the test suite does not numerically run FGP. The parent
owns any conditional invocation and its budget.

Warm state includes x,p, objective inputs, geometry/background/box, owner,
optimizer extrapolation and steps, and cumulative objective iterations/wall.
Different outer objectives preserve feasible primal/dual seeds but reset
optimizer momentum and the per-objective allowance. A smaller dual radius is
explicitly projected and counted. An unchanged objective resumes scheduling
and cumulative allowance. Changing optimizer mode cannot reset the allowance
for that same objective. All incoming arrays are copied; solver calls do not
mutate caller inputs or previously returned states. Geometry/background/box
or owner incompatibility is an explicit error. Old control rejects warm starts.

## Independent SOCP and raw-output policy

Clarabel version 0.11.1 is required and imported only within a charged call.
No installation or fallback solver is performed here. SciPy constructs a
sparse difference matrix independently from cell/edge indices, rather than
calling A24's D/D*. Variables are `[x;t]`, objective P has ones on material
coordinates and zeros on epigraph coordinates, and q is `[-v;alpha]`.
The solver's objective lacks the constant `0.5*||v||²`; comparison includes it.
Cones are Nonnegative(4N) for lower/upper bounds and N SOC(1+2d) for
`(t_i, D_i(x-background))`. The dual material-TV vector is the negative
SOC vector-dual, so stationarity is
`x-v+D* p-lower_dual+upper_dual=0`.

The reference reports raw explicit box-dual stationarity, epigraph
stationarity, primal/dual cone feasibility, box/SOC/TV complementarity,
physical box violation, stable gap, objective agreement, and independent
primal distance. Raw x,p and multipliers remain untouched. A24's diagnostic
is separately evaluated: its stationarity identifies only exactly active
bounds, so a near-bound interior-point output can fail that component even
when the explicit multiplier certificate is accurate. This fact is retained
in metadata rather than hidden by snapping the output.

Default reference settings are max_iter=200, inclusive wall<=5 seconds,
gap tolerances 1e-10, feasibility 1e-11, kappa ratio 1e-10, one solver thread.
Imports, matrix assembly, setup, solving, certificates and comparisons count
inside the inclusive wall. Solver-reported time is retained separately.
Clarabel's numerical KKT regularization does not add a material ridge to P.
A termination callback checks the parent's budget and local wall; exceptions
are recovered after the callback and propagated without continuing numerical
diagnostics past owner-budget exhaustion.

The initial implementation accepted only `Solved`; the parent preserved the
first rejected tiny attempt and approved an explicit policy interpretation:
`AlmostSolved` is not automatic acceptance but may pass **only** its raw
strict external reference certificate. Stationarity and cone/box feasibility
must be <=1e-11; gap and complementarity must be <=1e-10. The original status,
strict pass flag, and `strict_external_reference_certificate` acceptance
reason remain visible. Cap/error statuses are never accepted. This policy
does not loosen the frozen production solver/gate tolerances.

### Feasible certificate envelope

Raw interior-point dual balls can exceed their radius by rounding. Taking
sqrt(raw gap) unconditionally would not provide a feasible-dual error bound.
The reference therefore reports a separate **certificate-only** virtual
feasible envelope: box projection of a copied x, projection of a copied p to
an interior radius alpha*(1-64*machine_epsilon), and a stable original-objective
gap with a recorded conservative arithmetic allowance. The allowance uses a
gamma_k-style operation-count margin, not formal interval arithmetic. All
projections/products are counted. The returned raw outputs are unchanged.

The envelope's primal-error allowance adds the raw-to-virtual primal distance
to sqrt(2*safe gap). A comparison obtains envelopes for both independent raw
reference and PDHG state, returning `robust_primal_distance_allowance` and
its agreement flag. The reference is accepted from its **raw** KKT/feasibility
certificate, never from these projected diagnostic values. Envelope failure
does not become a manufactured bound.

### Explicit bounded refinement

The parent recorded a reference failure with epigraph stationarity
1.16656e-11 against the unchanged 1e-11 strict threshold. That attempt and its
UNHEALTHY decision remain preserved. For a new parent-owned charged attempt,
set `reference_refinement=True` or `'tight_accuracy'`. This changes internal
gap tolerances to 1e-12, feasibility to 1e-13, kappa ratio to 1e-12, iterative
refinement abs/rel tolerances to 1e-14, and refinement iteration ceiling to 20.
External thresholds, original objective/box, max 200 interior-point iterations
and five-second inclusive wall remain unchanged. There is no automatic retry.
The selected settings/profile are returned in metadata.

## Tests and evidence separation

The parent must execute `tests/test_a25_prox.py` inside
`contracts.active_ledger(book)` using an A25 charged job. The 21 tests cover:
analytic box/fused/joint and active-box solutions; immutable inputs and
warm-state compatibility/cumulative caps; acceleration formulas and the
fixed-step certificate trap; local/global deadline behavior; tolerance and
FGP authorization guards; independently assembled 2D/3D D and its real
adjoint; SOCP signs and physical TV scaling; a rounded raw-point envelope;
strict AlmostSolved acceptance/bad-certificate rejection; explicit internal
refinement; actual Clarabel comparisons and cap failure. Missing Clarabel
causes explicit reference-test skips, not successful reference validation.

The parent preserved a first test failure where an active-box primal-value
assertion demanded 1e-8 accuracy that the objective/gap tolerance did not
guarantee. The test now checks the valid envelope-derived norm bound and
known-optimum objective error <=1e-10, while retaining raw multipliers/KKT.
This repairs the test's unsupported accuracy claim without changing gates.

Numerical optimizer certification is distinct from Maxwell identity checks,
reconstruction quality, task thresholds, independent parent-level evidence,
3D confirmation and physical time-to-image. Old A24 failures and all parent
attempt receipts remain unchanged. The parent owns the scientific conclusion.

## Primary references

- Chambolle–Pock, Algorithm 2 and uniformly convex acceleration:
  https://optimization-online.org/wp-content/uploads/2010/06/2646.pdf
- Beck–Teboulle, constrained TV dual recovery and FGP, Sections 4.1–4.2:
  https://www.math.tau.ac.il/~teboulle/papers/tlv.pdf
- Clarabel quadratic conic format and raw results:
  https://clarabel.org/stable/python/getting_started_py/
- Clarabel settings and iterative refinement:
  https://clarabel.org/stable/api_settings/
- Clarabel budget termination callback:
  https://clarabel.org/stable/examples/py/example_callback/

Static validation: both initial module AST parses passed in 0.004107 seconds;
the final three-file AST parse passed in 0.013682 seconds and counted 21 test
methods. No solver or numerical test execution is performed by this worker.
