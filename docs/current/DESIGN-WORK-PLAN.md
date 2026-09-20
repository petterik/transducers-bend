---
created_at: 2026-09-20T19:31:00+02:00
status: current
---

# Transducer architecture work plan

Status: partially implemented, reviewed 2026-09-20. The
[implementation review](../review/IMPLEMENTATION-REVIEW.md) found that several
checkpoints below are probes, not completion of their work packages. The
[repair and completion plan](IMPLEMENTATION-REPAIR-PLAN.md) details the next
worksets and the proposed compositional keep design. The original acceptance
criteria below remain applicable. [PRIORITIES.md](PRIORITIES.md) contains the
original impact, effort, and value ranking.

## Objective and boundaries

Make ordinary, independently written reducer transformations compose efficiently
with source-owned traversals. Support new operations without registering them in
the compiler. Preserve owned state, ordering, initialization, stopping, completion,
and checked-operation behavior. Aim for parity with equivalent direct Bend over
a stated workload matrix; do not replace that objective with merely removing
callback records.

Keep the existing reducer lifecycle as the semantic starting point. Public
signatures and library representation may change when that simplifies the design.
Do not change valid semantics to satisfy an optimization, restrict source folds
to states produced by one initializer, or erase distinct downstream stop state.

Compiler prototypes stay in isolated copies. Do not edit the sibling compiler or
`bend2/bend.ts` as an incidental part of library experimentation. Stage any eventual
upstream changes separately. Historical performance reports remain evidence for
their recorded revisions; they do not prove correctness of a replacement.

## Dependency order

```text
0  Correctness boundary and regression gate
↓
1  Semantic extension probes and performance expectations
↓
2  Static composition and a minimal API prototype
↓
3  Typed regions with scoped facts
↓
4  Local representation elimination
↓
5  Proved and profitable loop/tree optimization
↓
6  Stabilize the public API
↓
7  Promotion and upstream packaging
```

This is a dependency order, not a requirement to finish an entire framework
before trying a useful slice. Package 3 begins with a small design during package
2; implement only enough to support the first rewrite in package 4. API probes
begin in package 1. Correctness checks, code-generation inspection, and focused
measurements accompany every implementation step. Full performance acceptance
follows semantic acceptance of the revision being measured.

## 0. Establish a correct compiler baseline

Status: completed conservatively. The candidate now refuses the unproved tree
rewrite, and `tree_entry_control.bend` is part of the source-shape gate. Tree
performance remains open for package 5.

**Purpose:** prevent known wrong code from contaminating architectural or timing
conclusions.

**Work:**

- Reconstruct the candidate and reproduce `review/tree-entry-control.bend` using
  `review/check_tree_entry.py`. Preserve the recorded failing evidence and hashes.
- Move or integrate that probe into the maintained compiler regression gate.
  Compare full control/state where practical, not just a final sum.
- Refuse tree rewrites wherever their preconditions or input-state relations are
  unproved. Address both unguarded callback substitution and tag rewriting; simply
  deleting the tag rewrite is insufficient. Remove the unjustified application,
  rather than adding a user flag or a special case for the reproducer.
- Keep original tree traversal and continuation lowering on refused paths. A
  fallback at a raw FID entry is not acceptable without a frame-layout proof.
- Update code-shape assertions to describe the deliberate refusal. Record any
  loss of tree parity as unresolved; a correctness fallback is not completion of
  the performance objective.

**Likely files:** `bench/compiler/guarded_loop.inc.ts`, integration in
`prepare_guarded.py`, `test_source_shapes.py`, the review probe, and regression
fixtures. Check the scalar summary's `pc`/`fast` use as part of the change.

**Acceptance:** the probe returns `[9, 1000, 2000, 1017]` in JS/native, the existing
library suite passes, and refusal tests cover independently supplied Stop,
continuing-zero state, downstream Stop, and ordinary initialized states. Include
shared callers so the standard transduction cannot lend facts to a generic fold.
No claim that the remaining optimizer is fully proved follows from these checks.

## 1. Challenge the abstraction with independent extensions

Status: completed as the first public semantic probe. `keep` and
`partition_all` run through the independent tree source, including affine
values, partial completion, both stopping orders, zero width, and fresh state.
The remaining operations in this package are future extension probes.

**Purpose:** determine which general compiler behavior is actually needed before
building more optimization machinery.

**Work:**

- Write down the contracts for `keep` and a minimal non-overlapping
  `partition_all`. Keep consumes `A -> Maybe<B>` and emits only Some. Partitioning
  owns its buffer, emits full groups, flushes a partial group on completion if
  downstream is open, and discards pending output after downstream Stop.
- Specify positive group-width configuration, including the handling of zero,
  before implementation. Prefer representing a valid positive width in the
  configuration boundary if practical; do not silently normalize zero to one or
  leave a nonprogressing case. Compare the type/configuration choices in a small
  design note rather than imposing a new general validation subsystem.
- Implement these as ordinary reducer adapters in an experiment module first.
  Use existing templates and runtime settings. Preserve affine element ownership;
  do not require Data just to put elements into a non-overlapping group.
- Apply them through list/range and an independently implemented source. Reuse
  the existing external tree example, or add a structurally different ordered
  source only where it exercises a missing boundary. No changes to the library
  registry or compiler recognition should be needed for the extension.
- Exercise scalar and affine collection consumers. Use compatible element types:
  partition emits groups, so a scalar consumer must explicitly consume groups.
  Do not hide an incompatible pipeline with a conversion shim.
- Create small direct-Bend references with equivalent ownership and lifecycle.
  Describe which allocations are required and which boundary costs should vanish.

**Required cases:** empty inputs; initial stop; full and partial groups;
`take → partition_all`; `partition_all → take`; nested buffering; stopping during
completion; consumer-originated stop; fresh state per invocation; type-changing
keep; affine values; and preservation of encounter order.

**Acceptance:** the new semantics work through the existing protocol on the
correct baseline without compiler changes for their names or combinations. Tests
and an annotated code-generation sample identify residual overhead. If the
protocol fails, revise it explicitly before optimizing around the failure.

**Deliverable:** extension experiment, semantic fixtures, and a compact table of
expected removable overhead versus necessary storage. Public feature breadth is
not the goal of this package.

## 2. Make static composition systematic

Status: partial implementation. The eager migration is now systematic across
built-ins and the external tree, and an isolated compiler prototype memoizes
normalized static terms with scoped diagnostics. It preserves the full suite and
reduces repeated evaluator work, but the eager Array fixture still retains three
Reducer records and one Reduction record. The public delayed recipe remains while
the reduced Array static-head/driver blocker is investigated.

**Purpose:** remove dependence on incidental callback spelling or delayed recipe
construction, while preserving the clean code/settings distinction.

**Work:**

- Inspect `static_fun`, `specialize`, and template elaboration using reduced
  probes for direct matcher callbacks, forwarding lambdas, nested descriptions,
  type metadata, and repeated recipe use.
- Choose a shared static representation/memoization boundary using existing
  compiler structures. Specify what identifies a specialization and prevents
  cross-instantiation reuse. Bound work and code growth explicitly.
- Preserve call-by-value evaluation, single evaluation of dynamic expressions,
  checked failures, erased/live argument distinctions, and affine use. Unknown,
  foreign, unsafe, or parallel computations cannot be evaluated speculatively.
- Normalize equivalent known callback forms where justified. Preserve ordinary
  calls where expansion would create unnecessary code growth.
- Prototype one source binding and one consumer-independent transformation
  definition using current templates. Try removing `Unit -> Reducer` delays,
  delayed metadata, and the duplicate static list driver for their documented
  compiler-related reasons. Keep any form that has a genuine semantic purpose;
  record the reduced blocker if removal is not supported.
- Add optional diagnostics for unresolved static heads and exhausted budgets.
  These explain optimizer decisions; they are not public pipeline settings.

**Acceptance:** representative and extension descriptions resolve without
runtime callback records at the measured boundaries; bare and forwarded callback
forms have equivalent intended lowering; deep/repeated compositions remain
bounded. Strictness/failure and ownership regressions pass. The same source
implementation serves its callers without a second optimizer-oriented driver.
Any unmet item remains explicit rather than being hidden by increasing fuel.

**Decision:** propose a new staging feature only if a concrete reduced example
shows why current templates cannot express the desired boundary cleanly.

## 3. Give optimization facts an explicit scope

Status: first local constructor fact prototype complete in an isolated compiler;
the general typed-region and summary API remain open. The prototype is recorded
in [SCOPED-FACTS.md](SCOPED-FACTS.md). It attaches exact constructor provenance
to emitted values, rebinds it across the two fused-call paths, specializes only
unboxed all-static scalar fields, and falls back for dynamic or boxed fields.
The focused fixture reports positive selection and dynamic-field rejection, and
the full 20-file suite passes in both output orders. This is a useful local
rewrite boundary, not a claim that joins, recursion, or continuation facts are
implemented.

**Purpose:** make the authorization for a rewrite inspectable and testable.

**Work:**

- Write a short internal design for a bounded typed region over existing typed
  terms/ANF. Specify stable value identities, branch/join structure, calls,
  constructor fields, live/erased types, and ownership. Build a small addition to
  the compiler, not a second whole-program intermediate representation by default.
- Represent each useful summary with input preconditions, output relations,
  unchanged fields, and relevant failure/effect restrictions. A guarded expression
  must not be usable as an unconditional fast implementation by omission.
- Map formal inputs to actual arguments at each use. Bind facts to those values
  and dominated program points. At joins retain only facts supported by all
  incoming paths. Equal storage layouts never imply equal semantic facts.
- Retain original control flow when analysis is inconclusive. Opaque calls must
  keep their order and conditional execution; invalidate affected facts while
  retaining independent facts that remain justified.
- Specify boundaries before continuation/FID lowering. Facts that cross a
  continuation require explicit modeling of its entries; otherwise stop analysis
  there. Separate this first local region from later recursive proofs.

**Acceptance:** a small non-transducer program exercises the first positive
rewrite. Negative cases include same-layout unrelated values, failed
preconditions, multiple callers, changed generic instantiations, and branch-local
checked arithmetic. A summary is not usable merely because it was previously
emitted or found in a call graph.

## 4. Eliminate local representation overhead

Status: first general constructor-match rewrite demonstrated in an isolated
compiler. [LOCAL-REPRESENTATION.md](LOCAL-REPRESENTATION.md) records a tagged
two-constructor fixture where an exact static arm fact removes the generic arm
branch and shrinks native C by 85 bytes, with equal JS/native output and UBSan
coverage. The rule is general and does not name a transducer. The existing
keep/partition probe still retains necessary buffering and has not yet shown a
visible Maybe wrapper elimination; that is the next slice.

**Purpose:** extend optimization beyond scalar filter/take/sum patterns.

**Work:**

- Start with constructor/projection elimination, known-call exposure, and local
  scalar replacement. Reuse existing layout and ownership lowering where it
  already performs the work; do not add a duplicate mechanism.
- Use keep's temporary Maybe as a first extension target. Then simplify the
  configuration/control wrappers around buffered state without deleting the
  buffer itself. Preserve owned values and cleanup on every exit.
- Optimize justified regions around opaque callbacks and boxed buffers. Refusal
  of one operation must not erase all independent local optimization opportunities.
- Inspect native and JS paths separately. A missing JS constructor or C marker
  alone is not evidence about native hot-path allocation or execution frequency.

**Acceptance:** the named local overhead disappears in the relevant fixtures,
without adding transducer names, fixed state positions, or a required count/tag
pattern. Required buffer/output storage remains correct. Equivalent renamed or
refactored helpers exercise the same rule. Preserve existing map-chain parity,
and report residual costs in extension/direct comparisons.

## 5. Recover loop and tree performance soundly

Status: the established map/list loop gate remains complete for the current
isolated candidate, and the extension/direct checkpoint is now recorded in
[`EXTENSION-PARITY.md`](EXTENSION-PARITY.md). Early `keep` and bounded
partitioning are near the provisional target; full `keep` and full partitioning
remain slower and open. Tree specialization remains refused and short-loop
policy remains experimental. `bench/compiler/PROFITABILITY.md` records the
separate two-session List matrix and its open boundaries.

**Purpose:** regain useful parity results without relying on invalid assumptions.

**Work:**

- For tail recursion, prove entry preconditions and preservation along every
  relevant back edge, including paths that stop before another callback.
- For tree traversal, model leaf/base behavior, left-return/right-input state
  flow, stopping, and independently supplied initial state. Do not infer this
  from the number of recursive AST visits.
- Apply a guarded fast region only where its actual preconditions hold. Preserve
  generic semantics for other callers. Prefer specialization before continuation
  lowering; never route an unverified continuation frame through root dispatch.
- Reuse sound parts of the existing scalar analysis and tests. Remove obsolete
  structural recognizers as their responsibilities move into general analysis.
- Keep profitability separate: branch selection, inlining, code size, and loop
  versioning may vary by backend. Do not assume branchless code or longer loops
  are always better. Preserve compiler resource limits and deterministic refusal.

**Acceptance:** full state/control comparisons cover entry, transition, return,
and shared-caller cases. Run checked-failure/order tests and applicable native
sanitizer checks. Then measure predictable/mixed predicates, empty/zero/one/short
and long sources, early/full traversal, and cheap/expensive callbacks against
equivalent direct Bend. Unproved or unprofitable cases remain generic and explicit
performance gaps remain open.

## 6. Stabilize the library surface

Status: acceptance fixture complete. `tests/api_surface.bend` reuses one
type-changing `keep` declaration with `count` and `into_list` over range, list,
and the external tree source. The current positional configuration is retained
as the simplest form supported by Bend's type syntax; no second compatibility
API is introduced. Further named configuration records require a separate type
design.

**Purpose:** users describe transformations, settings, consumer, and source once.

**Work:**

- Select the simplest successful template-based composition from earlier probes.
  Hide repeated result-type plumbing and derive the pipeline configuration type.
- Supply clear typed configuration construction instead of positional tuple
  reconstruction. Keep static code separate from runtime settings and fresh state.
- Publish keep/partition-all only after their contracts and extension tests pass.
  Document that partition buffers are real state and that filtering affine values
  differs from consuming optional selection.
- Replace provisional signatures and examples coherently. Avoid retaining two
  semantic implementations merely for compatibility inside this experiment.

**Acceptance:** one reusable, type-changing transformation runs with two
compatible consumers and multiple sources. Callers do not repeat stages, derive
internal state types, or apply compiler-specific recipe tricks. Existing semantics
and measured lowering survive the API simplification.

## 7. Validate and prepare promotion

Status: candidate and reference validation are recorded in
`FINAL-VALIDATION.md`. The host-CPU List gate passes and no maintained
wrong-code failure remains; GPU execution, full upstream project gates, and
tree promotion remain outstanding.

**Purpose:** produce reviewable, independently justified language contributions.

**Work:**

- Run relevant compiler regressions/type checks, the library suite, extension
  conformance, and the permanent wrong-code regressions throughout development.
- For final acceptance, record compiler/library/toolchain identities, code growth,
  compile cost, and paired retained timings using the established methodology.
  Include original/reference and candidate lanes where they answer correctness
  or regression questions. Historical instructions to defer baseline comparisons
  during an earlier experiment do not define this new validation plan.
- Judge direct-Bend parity only with equivalent source ownership, stopping,
  outputs, and callback work. Use calibrated measurements for short reductions;
  timer-resolution equality is not acceptance evidence. Add the extension cases
  to the matrix and state any tolerances before interpreting results.
- Run device-specific gates for shared transformations and any device lowering
  change. Clearly distinguish host-only candidates from validated GPU behavior.
  Report unavailable infrastructure as outstanding, not passing.
- Package static specialization, local representation work, and optional backend
  control-flow work as separate reviewable changes. Include minimized ordinary
  Bend examples alongside transducer examples.
- Refresh README, implementation status, extension guidance, and handoff docs
  around the actual accepted revision. Preserve old reports as historical data.

**Acceptance:** each proposed compiler change has a stated semantic scope,
positive and refusal tests, code-growth limits, and relevant backend evidence.
No known correctness failure remains. Performance claims identify their matrix.
Full promotion waits for required project gates; broad language features require
their own proposal. Completion of this package means ready for review, not an
automatic merge, release, or deployment.

## Deferred work and decision rules

IO/process drivers, parallel folds, general runtime pipeline construction, and
large new staging features are separate designs. More library operations follow
the proven extension path; they should not trigger compiler-specific additions.
Mechanized proofs are useful for stable rules with a faithful model, but a formal
model that omits templates or continuation lowering cannot establish those parts.

When a probe exposes a wall, first revise the model or state the unsupported
scope. Do not add a transformation-specific fast path, weaken its expected
semantics, or silently change the source contract. A correct fallback establishes
safety, not performance success. Conversely, removing real buffering is not a
requirement for successful fusion.

Package 0's conservative repair is complete. Packages 1, 5, 6, and 7 are partial;
packages 2–4 have investigation evidence but their planned general compiler
implementation is incomplete. See IMPLEMENTATION-REPAIR-PLAN.md for concrete
remaining work and acceptance criteria. The host-CPU List matrix does not close
the static-composition, scoped-fact, representation, or configured-API work.
