# Execution plan: transducers at handwritten fused Bend speed

## Required outcome

The user's target is **transducers as fast as an equivalent manually written,
direct fused Bend traversal**. Merely removing intermediate lists, beating the
old transducer implementation, or discovering a safe fallback is insufficient.

Implement compiler improvements and validate the unchanged public transducer
pipeline against that target. Begin with sequential native CPU map/filter/take
over ranges; then validate the other existing sources and operations. That first
milestone is not a claim that all transducers or backends have reached parity.
Do not declare the overall target met while known relevant cases remain slower.

Keep immediate `transduce`, closed callbacks and runtime configuration. Do not
work on ergonomics, lazy execution, eduction, arbitrary captures, new buffered
operators or a generic collection interface. Existing semantics remain required.

This is a living execution plan. Commands below are run from the transduce-bend
repository root. The isolated compiler experiment and the public parity harness
are checked in here; production promotion and broader source/backend coverage
are still open.

The first candidate-only audit is now complete. The demonstrated range controls
pass the provisional timing gate, and three-map list composition reaches timer-level
parity. The September
20 isolated loop extension now closes the mixed full list gap for the demonstrated
scalar-state pipeline: it permits one boxed recursive source argument, proves the
source match structurally, and applies the typed scalar transition under a guarded
clone. The original list driver remains the fallback. Five-sample candidate timings
and the proof boundary are recorded in [COMPOSITION](bench/COMPOSITION.md) and
[AUTOMATIC](bench/compiler/AUTOMATIC.md). This is still an experimental host-CPU
milestone; the balanced acceptance matrix, other boxed sources/states and device
validation remain open. String now has an explicit positive source-shape gate;
Array-tree traversal and boxed reducer state have explicit conservative refusal
gates. The calibrated range gate is now complete for the two sequential
runtime-threshold controls: both rows pass the provisional 1.05 upper-interval
limit, with the worst upper bound at 0.972. This is candidate-only evidence for
the demonstrated U32 range shape, not a universal range or backend claim.

`bench/fusion_parity.py` now provides the first named public-list matrix. It
compiles an unchanged transducer lane and an independently written direct Bend
lane with the same source construction, callbacks, configuration and cleanup,
then checks both against a Python oracle. The current matrix covers zero and
one-element inputs, three composed maps, a U32→Nat→U32 type-changing mapper,
mixed full and early stopping, dynamic short source/count/threshold modes, and
expensive callbacks. It records generated artifacts and hashes; rows that
measure zero milliseconds are correctness gates only and are not performance
evidence.

The runner now supports independent sessions, minimum batch-duration checks and
a deterministic paired bootstrap for median transducer/direct ratios. A smoke
run with 256 reductions per sample kept the mixed-full batch above 113 ms and
reported a 95% ratio interval of 0.983–1.009; this is a protocol check, not the
required 20-block/two-session acceptance result.

The first full list acceptance run is retained in
[fusion-parity-results.json](bench/fusion-parity-results.json). It used 20
blocks in two sessions, 320 reductions per batch and an observed minimum of
100 ms. Every row's upper 95% ratio bound was at most 1.036, so the provisional
1.05 engineering gate passed for this candidate-only host-CPU matrix. This is
not yet a claim for arrays, GPU/CUDA, or the production compiler.

The calibrated range acceptance snapshot is retained in
[range-parity-results.json](bench/range-parity-results.json). It used 20 blocks
in each of two sessions, balanced order, fourfold repetition and an observed
minimum of 169 ms. Cheap full and cheap early runtime-threshold rows had upper
95% ratio bounds of 0.965 and 0.972 respectively. Both pass the same provisional
1.05 gate, with checked Python-oracle outputs and 80 paired observations per row.

## Performance acceptance rules

During development, measure these two lanes using the same candidate backend,
optimization flags, inputs, arithmetic, result and ownership/cleanup contract:

| Lane | Program | Compiler |
| --- | --- | --- |
| candidate_transducer | Existing public library pipeline | Candidate |
| candidate_direct | Equivalent handwritten fused Bend | Candidate |

Compare the transducer directly with the handwritten fused reference. Never obtain
parity by making the handwritten program slower. The original compiler is a final
regression comparator after the candidate implementation is complete; it is not
part of the development loop. Faster than the direct reference is acceptable,
after verifying the work is equivalent.

Use a provisional engineering gate of at most 5% overhead per case, with the
upper bound of a 95% paired-bootstrap interval on median time ratios at or below
1.05 against each direct lane. Record the bootstrap seed and method. This is an
explicit measurement tolerance, not a redefinition of exact equality. Investigate
consistent overhead even inside the tolerance when code inspection exposes its
cause. Report worst rows; do not hide a failure in a geometric mean.

Use at least 20 retained sample blocks in each of two separate sessions for final
acceptance. In each block run both prebuilt lanes in balanced rotating order;
discard warmups consistently. Calibrate repetitions so the smallest timed batch
lasts at least 100 ms. Use varying runtime input and checked results to prevent
constant folding/hoisting of the work. Report raw batch times and normalized time
per reduction. Recalibrate noisy cases; an inconclusive interval is not a pass.
Do not subtract an empty-loop baseline or invent an absolute-time waiver to hide
short-call overhead. Record same-binary repeatability controls and machine load.

Keep correctness tests for arbitrary valid internal states separate from public
API timings. A handwritten public reduction need not expose internal control
tags; it must match observable results, callback/failure behavior and cleanup.
Internal helper comparisons must preserve every returned field, including states
not reachable through ordinary initialization.

## Step 1 — Capture the starting point and prepare the candidate compiler

Read, in this order:

1. `FUSION.md` for scope and ownership constraints.
2. `bench/compiler/SHORT-LOOPS.md` for the latest failed profitability policies.
3. `bench/compiler/AUTO-LOOP.md` for the implemented loop pass and proof boundary.
4. `bench/compiler/ABLATION.md` for the controlled evidence behind its code shape.
5. `bench/compiler/prepare_guarded.py`, `guarded_scalar.inc.ts` and
   `guarded_loop.inc.ts` for the actual integration.

Inspect `git status --short` in both repositories. Preserve unrelated changes.
Record the candidate revision/status, source hashes, Bun/Clang versions, machine
and runtime flags. Create a persistent shell variable for an isolated artifact
root:

```sh
FUSION_RUN=$(mktemp -d /tmp/bend-fusion-parity.XXXXXX)
export BEND_NO_TELEMETRY=1
export CLANG_MODULE_CACHE_PATH="$FUSION_RUN/clang-cache"
python3 bench/compiler/prepare_guarded.py --loop --output-dir "$FUSION_RUN/entry"
python3 bench/compiler/prepare_guarded.py --loop --source-gate --output-dir "$FUSION_RUN/source-gate"
```

Save the absolute FUSION_RUN path in the work log; tool shells may not retain
variables. Reassign it explicitly when using a new shell. The preparation script
requires empty destination directories and a pinned original `comp.ts` hash.
If the hash check fails, inspect/rebase integration against the actual changes;
do not just replace EXPECTED to bypass the check.

The script reads `../bend/bend2` directly. Snapshot the candidate compiler inputs
and verify their hashes before/after every benchmark set. Do not time two
candidate directories from different unrecorded sibling revisions. Keep the
unchanged sibling compiler available for the final regression run only.

Run candidate library semantics before optimization work:

```sh
python3 tests/run.py --bend-main "$FUSION_RUN/entry/main.ts"
python3 bench/compiler/test_auto_loop.py --bend-main "$FUSION_RUN/entry/main.ts" --output "$FUSION_RUN/entry-fixtures.json"
```

Deliverable: a starting-state manifest and reproducible isolated compiler paths.
Gate: resolve unexpected correctness failures before collecting performance data.

## Step 2 — Reproduce the existing long wins and short failures

These are existing candidate-only commands. Run timed processes sequentially, with no other
benchmarks or compiler builds competing for the machine:

```sh
python3 bench/compiler/ablate.py --automatic-loop --automatic-compiler "$FUSION_RUN/entry/main.ts" --samples 5 --output "$FUSION_RUN/entry-full.json"
python3 bench/compiler/ablate.py --automatic-loop --automatic-compiler "$FUSION_RUN/entry/main.ts" --early --samples 5 --output "$FUSION_RUN/entry-early.json"
python3 bench/compiler/short_loop_sweep.py --report "$FUSION_RUN/entry-full.json" --full --stable --independent --variants entry source_gate --output "$FUSION_RUN/short-independent.json"
python3 bench/compiler/short_loop_sweep.py --report "$FUSION_RUN/entry-full.json" --full --stable --independent --known-budget 32 --variants entry constant_region callsite_const --output "$FUSION_RUN/short-known-state.json"
```

Retain the artifact directories printed by each command. JSON from old runs can
reference deleted temporary files; regenerate rather than editing those paths.

Important: `short_loop_sweep.py` is a C harness calling emitted helpers. Its
policies include generated-C diagnostics; it does **not** currently benchmark a
handwritten Bend public-API reference. Use it to reproduce counterexamples, not
as the final parity gate. `ablate.py` includes direct Bend, but does not currently
provide the complete balanced-block protocol above.

Deliverable: fresh reports reproducing at least one long win and one short
regression. If the old regression does not reproduce, document the difference
and repeat controlled measurements before selecting a different failing case.

## Step 3 — Run and extend the public-API parity harness

`bench/fusion_parity.py` is the first implementation of this step. It currently
uses a generated Bend template rather than a separate fixture directory, and
does not use patched generated C as a timed implementation.

The runner accepts the candidate compiler, output/artifact directory, selected
cases, sample blocks and repetitions. Compile both lanes before timing.
Preserve generated Bend, C, native binaries and assembly.
Write source/compiler/library hashes, checksums, samples, ratios and uncertainty
to JSON. Make each failing row individually rerunnable.

Implement the direct reference independently in Bend using ordinary recursion,
map/predicate calls and scalar state. `bench/range.bend: direct` is a starting
point, not permission to copy the optimized transducer helper. It must not call
T.transduce, T.step or the candidate optimizer's generated implementation.
Check the reference itself against an independent Python oracle. Share callback
definitions between direct and library lanes so neither receives cheaper work.

For public take(0), initialize/finish normally but invoke no mapper/predicate.
Make source bounds, filter settings and counts identical. Preserve U32 wrapping,
Nat failure behavior, source order and any observable finalizer behavior. Keep
allocation/output and unused-source cleanup equivalent in later collection cases.

Initial CPU matrix, one thread and GPU disabled:

| Dimension | Required coverage |
| --- | --- |
| Maps | Identity; one map; three composed maps; one type-changing case |
| Source length | 0, 1, 2, 4, 8, 32; 2,000,000; dynamic mixtures of small lengths |
| Filter | Accept all, reject all, predictable partial, mixed outcomes |
| Take | 0, 1, 32, consume all; known and runtime-varying counts |
| State/configuration | Known count with dynamic source length; independent runtime variation |
| Callback cost | Cheap operations and expensive map with early stopping |
| Range bounds | Nonzero offsets; checked near-limit cases outside large timed runs |

Use a named curated matrix, not the full Cartesian product. Include the known
failing combinations from Step 2. Derive varying length, budget, selectivity and
offset from disjoint seed bits as the independent sweep does. Preserve runtime
variability across reductions and verify generated code still performs the work.

The current deliverable is a table of per-case ratios to direct Bend and
preserved artifacts. The calibrated list and range controls now pass the
provisional gate. Next, extend the same protocol to the source shapes that are
currently conservative fallbacks, starting with Array-tree traversal and boxed
reducer state, then cover String and the remaining existing adapters. This
harness identifies the actual parity gaps; success against original helpers
cannot substitute for this table.

## Step 4 — Reduce one parity gap and identify its cause

Choose the smallest stable public-API failure, preferring known take count with
dynamic short source length. Keep a long mixed case and map-chain case as controls.

1. Copy the failing generated Bend programs into minimal reproducer fixtures.
   Remove unrelated definitions/dimensions one at a time; remeasure after each
   reduction. Keep runtime input, independent checksum and the same computation.
2. Save candidate transducer/direct C and assembly.
   Use the same Clang flags. Collect inline/loop optimization remarks with
   `-Rpass=inline -Rpass-missed=inline -Rpass=loop-vectorize
   -Rpass-missed=loop-vectorize` where supported.
3. Find the timed reduction body, then record remaining callback calls, wrapper
   allocations, state packing/unpacking, loop-carried fields, guards, stack spills,
   runtime polling and source arithmetic. Follow called helpers; counting text
   occurrences of a constructor is not an allocation profile.
4. Form one falsifiable explanation: for example, an entry wrapper blocks an
   inline, or an opaque fallback hides a preserved field. State the predicted
   code change and affected timings before testing it.
5. Make one isolated diagnostic change and compare the reproducer plus controls.
   Generated-C edits may test a hypothesis but must be labelled diagnostic.
   Smaller assembly alone is not an explanation or a performance result.

Decision table:

| Finding | Next implementation location/direction |
| --- | --- |
| Static callback/description remains in hot execution | Review `static_fun`/`specialize` in sibling `comp.ts`; implement the experiment through an isolated patch, preserving strictness and work bounds |
| Wrappers/transfers survive despite known flat state | Inspect existing layout/ownership lowering before adding another representation; target the demonstrated escape or transfer boundary |
| Entry cloning/guarding changes inlining or loop optimization | Inspect `gl_call_name`, `gl_finish`, native keys and clone boundaries in `guarded_loop.inc.ts` |
| Scalar transition retains redundant work | Inspect the scoped expressions and preserved-field summaries in `guarded_scalar.inc.ts` |
| Internal stress case fails but public case is already at parity | Keep the internal regression as a compiler gate; choose another actual public parity gap rather than reporting failure or success from the wrong baseline |

Deliverable: a short causal report with reproducer, before/after artifacts and
measurements. If no hypothesis survives, continue diagnosis; do not guess another
source-length threshold or resume a broad rewrite without evidence.

## Step 5 — Implement one general correction in the isolated compiler

Edit the experiment's checked-in integration/includes so preparation reproduces
the correction. Do not leave the only implementation in a temporary comp.ts.
Keep the public library unchanged unless evidence demonstrates a representation
obstacle that cannot reasonably be fixed in lowering; explain any proposed
library change against the direct-Bend target before expanding scope.

Use typed bindings/layouts/operations for recognition. Never recognize library
function names, numeric tag conventions or fixed record positions. Bound analysis
and cloning; unsupported cases retain original behavior. A fallback that is still
slower than direct Bend remains an open parity case, not task completion.

Write down and test these obligations for the actual correction:

- Runtime expressions evaluate once, in the original order, including unused
  expressions that can fail. Closed code is reusable; owned runtime values are not.
- Rejected branches do not newly execute callbacks or checked arithmetic.
- Every valid generic state retains its semantics. Entry assumptions apply only
  to guarded clones and are proved preserved for relevant back edges.
- Shared helpers and native caches do not leak one caller's assumptions to others.
- Stop origin, finalization, owned cleanup and runtime polling remain correct.
- Unknown, boxed or device cases outside the proof domain are refused safely.

Add a positive fixture that exercises the new optimization and the smallest
negative fixture that would become wrong if its precondition were omitted.
Also include renamed/reordered bindings and shared-callee coverage. Do not count
a test where the pass never fires as validation of its optimized behavior.

## Step 6 — Validate correctness before final timing

Prepare a fresh candidate directory after every compiler revision. Reuse these
existing checks; adapt brittle emitted-symbol matching transparently if a valid
code-shape change requires it. Never delete a check simply to obtain a pass.

```sh
python3 bench/compiler/prepare_guarded.py --loop --output-dir "$FUSION_RUN/candidate"
python3 tests/run.py --bend-main "$FUSION_RUN/candidate/main.ts"
python3 bench/compiler/test_auto_loop.py --bend-main "$FUSION_RUN/candidate/main.ts" --output "$FUSION_RUN/candidate-fixtures.json"
python3 bench/compiler/adversarial.py --bend-main "$FUSION_RUN/candidate/main.ts" --output "$FUSION_RUN/candidate-adversarial.json"
python3 bench/compiler/test_guarded.py --bend-main "$FUSION_RUN/candidate/main.ts" --output "$FUSION_RUN/candidate-scalar.json"
```

Here `candidate` means a newly prepared compiler containing Step 5, not an existing
directory to overwrite. Use a revision suffix for subsequent attempts. If the
candidate intentionally enables source gating, pass the corresponding flag to
the preparation and fixture commands; do not enable it merely to satisfy a test.

Generate a fresh candidate full-range ablate report, then run:

```sh
python3 bench/compiler/ablate.py --automatic-loop --automatic-compiler "$FUSION_RUN/candidate/main.ts" --samples 5 --output "$FUSION_RUN/candidate-full.json"
python3 bench/compiler/test_loop_version.py --report "$FUSION_RUN/candidate-full.json" --automatic-loop --output "$FUSION_RUN/candidate-driver.json"
python3 bench/compiler/test_loop_version.py --report "$FUSION_RUN/candidate-full.json" --automatic-loop --inject-failure --output "$FUSION_RUN/candidate-failures.json"
python3 bench/composition.py --samples 5 --output "$FUSION_RUN/composition-original.json"
python3 bench/compiler/check_map_parity.py --bend-main "$FUSION_RUN/candidate/main.ts" --composition-report "$FUSION_RUN/composition-original.json" --output "$FUSION_RUN/candidate-map-parity.json"
python3 bench/compiler/upstream_local.py --bend-main "$FUSION_RUN/candidate/main.ts" --output "$FUSION_RUN/candidate-upstream.json"
```

Map assembly equality is an established control. If code generation changes its
spelling, investigate equivalence and performance rather than masking a slowdown.
Upstream compatibility is not a substitute for optimization-firing tests or the
official project gates. Use UBSan and existing full-state/trace comparisons;
extend them for any newly accepted region. If polling structure changes, include
polling-boundary tests. Preserve checker rejection of invalid affine programs.

## Step 7 — Reach parity across the matrix, then broaden coverage

Run the candidate-transducer versus candidate-direct matrix under the acceptance
protocol. For each failed row,
return to Step 4; retain already passing controls. Do not stop after fixing the
first short case. Record compile time, generated/native size and analysis/clone
counts so runtime gains do not conceal uncontrolled compiler growth.

Once range/map/filter/take CPU parity passes, add equivalent direct Bend references
for list/array/string traversal and existing count, affine collection, cat/mapcat
and custom stopping consumers. Use existing fixtures and `bench/wordscan/run.py`
as starting points. Use representative compositions rather than claiming every
possible callback is exhaustively tested. For each source compare both cheap
and expensive work, early and full consumption, and identical source lifecycle.

For mapcat distinguish callback fragment construction from composition overhead.
An eager fragment-producing callback may fail while building a later element;
a handwritten streaming producer that skips that failure is not an equivalent
reference. If fragment elimination is needed, prove it for the accepted producer
subset. Do not silently weaken semantics or omit existing operations to pass.

Recheck existing parallel-batch performance with equivalent direct batches.
Single-stream take must not become per-worker take. Validate actual supported
GPU hardware separately before claiming device parity; CPU results and device
fallback compilation are insufficient. Report backend milestones separately.

## Step 8 — Integrate and hand off evidence

After the affected scope passes correctness and performance gates, port the
minimal automatic change into a clean compiler branch/worktree. Inspect applicable
repository instructions before editing there. Run the compiler's required local
typecheck/regression/size gates and supported device tests. Infrastructure failures
are recorded as incomplete gates, not passes. Recheck that final integrated
artifacts match tested artifacts or rerun affected validation and measurements.

Deliver one reviewable change with:

1. The concrete residual overhead and why the rewrite removes it safely.
2. Reproduction commands, pinned identities and durable benchmark sources.
3. Candidate-transducer versus candidate-direct per-case timing tables with
   uncertainty and worst regressions.
4. Positive/negative semantic tests and proof boundaries.
5. Compile/code-size changes, unsupported cases and remaining backend gaps.
6. An explicit outcome: scope at handwritten parity, scope still slower, or
   scope not measured. Only after the candidate is complete, run the original
   compiler as a final compatibility/regression comparison. Do not call the
   overall task done from a partial milestone.

Do not pursue a numerical claim of 100% compiler correctness. The required result
is demonstrated direct-Bend parity with a bounded, reviewable, semantics-preserving
implementation and candidly stated coverage.
