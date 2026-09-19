# Automatic guarded scalar specialization

**Follow-up:** [promotion review](PROMOTION.md) adds 3.2 million adversarial state
comparisons and local upstream coverage. It also demonstrates a fallback-heavy
performance regression from outlining, so this pass is not ready to default-enable.

The first milestone is implemented: an isolated compiler now derives the winning
scalar transition from the unchanged public map/filter/take/sum pipeline. This is
**automatic discovery and lowering**, not another handwritten transition or C
helper-name matcher. Production `transduce.bend` and the sibling compiler are
unchanged. This is an experimental native CPU pass, not a promotion decision.

## Implementation

`prepare_guarded.py` verifies the original compiler SHA256, copies `main.ts`,
`comp.ts`, `bend.ts`, `base.bend`, and `effs/`, then integrates the implementation
in `comp.ts`. `guarded_scalar.inc.ts` is the implementation source fragment, not
an independently executable module. `bend.ts` is never edited. The old
`prepare.py` still prepares the unsuccessful C-text selection experiment.

The new pass runs at the existing native-helper boundary, after the original
helper has been emitted. Its analysis consumes typed Bend terms and layouts:

1. Interpret a bounded, acyclic scalar region. A call gets a fresh environment
   keyed by compiler binding identities; lambda/let bindings and erased type
   arguments stay in their proper scope. This does not route calls through the
   inline emitter that previously produced the unbound-binder failure.
2. Record path conditions and scalar output expressions. Layouts supply tag
   ranges; Nat has its bounded 48-bit domain. Match guards justify predecessor
   operations. Reconstructing a successor is accepted only when interval facts
   prove no overflow. Unknown operations reject the entire candidate.
3. Derive unchanged outputs by comparing each output expression with input
   expressions on **all** paths. No configuration/state field names or positions
   are built into that decision.
4. Search pairs of state tests already present in the region, keeping a separate
   two-constructor, fieldless decision input. Join equivalent expressions into
   conditional updates. Derive an output Boolean as a zero test of an updated
   scalar only when the equality holds on every applicable original path.
   There is no inference from a Control-like record to a positive count.
5. Check Nat totality again on the joined expressions under the proposed guards.
   Emit the guarded selections, with the untouched helper behind a noinline/cold
   fallback. Restate the derived unchanged outputs after a successful fallback
   **and on the fast path**, preserving Clang's loop-state knowledge.

For the public pipeline, this produces the positive-count/continuing-inner guard,
selected decrement and wrapping U32 addition, and outer-stop-from-updated-count
shape established by the ablation. Mapping and predicate evaluation remain outside
this helper, in their original locations. Arbitrary zero and stopped states still
use the original helper. The outer and inner control tags remain distinct.

The initial arithmetic allowlist contains wrapping U32 addition and proven Nat
predecessor/successor operations. Scalar copies, constructor assembly and tag/Nat
matches are supported. Boxed layouts, ownership conversions, indirect/foreign or
recursive calls, parallel work, floating-point operations, unsupported intrinsics,
open matches and unproven checked arithmetic are refused. Unsupported callbacks
are not speculated. Even a discarded let value must be analyzed; its possible
failure cannot be erased merely because its result is unused.

Bounds per candidate: 12 input words, eight output words, 16 helper-call levels,
3,000 extraction/simplification visits, 256 constructor results, 32 final paths,
256 nodes per constructed expression, eight candidate tests, and 60,000 visits
for the guarded search/simplification phase. A successful candidate gets one
fallback and one small wrapper; the current gate requires two guards, at least
two scalar selections and a derived zero-test output. These are deliberately
narrow shape limits, not a general optimizer framework or a profitability proof.

The generated preprocessor guard leaves the original helper on Metal/CUDA.
JavaScript emission is unchanged. GPU execution has not been validated.

## Performance

Apple Clang 17, `-O3`, sequential CPU, GPU off, runtime predicate thresholds.
Ten retained samples per full/early range variant after discarded warmups,
forward/reverse order. Full batches perform 32 reductions of two million values;
early batches perform one million take(32) reductions with varying starts.
All columns within a row use the same workload. Times are median milliseconds.

| Range workload | Original compiler | Automatic pass | Handwritten |
| --- | ---: | ---: | ---: |
| Mixed full | 319.5 | **96** | 95 |
| Predictable full | 50 | **36** | 34 |
| Mixed early | 139 | **104** | 103.5 |
| Predictable early | 25.5 | **18** | 17.5 |

[Full-range samples](automatic-results.json) and
[early-stop samples](automatic-early-results.json) record compiler/generated-C
hashes and retained artifacts. These results reproduce the successful ablation's
code shape through automatic compilation. They do not establish a universal
percentage advantage; differences of 0.5–2 ms approach measurement granularity.

The [composition comparison](automatic-composition-results.json), six samples per
variant, measured mixed full-list reduction at **14.5 ms**, versus handwritten
14 ms and the ordinary eager pipeline 127 ms. Predictable full-list reduction was
10/10/117 ms respectively. Mixed early-list reduction was 40/40/129 ms, including
construction/disposal of the list. The existing ordinary-filtering type-kind
caveat in [COMPOSITION.md](../COMPOSITION.md) still applies.

Three transducer maps measured 14 ms, one map 13 ms, handwritten 13.5 ms, and three
ordinary List.map passes 117.5 ms. **The entire timed-function assembly is identical
for three maps, one map, and the original compiler's three-map program.** The
small timing variation is not evidence of a lost fusion optimization.

Additional six-sample checks: [huge early ranges and expensive mapping](automatic-extra-results.json)
measured automatic/handwritten at 18/19 ms and 11/11 ms; a
[runtime no-match filter](automatic-no-match-results.json) measured 36/34 ms.
Checksums passed their independent oracle in every batch. These extra reports
compare automatic and handwritten code; they do not contain fresh original-compiler
controls. Timed runs were sequential, with no concurrent test/compile jobs.

## Validation

- The unchanged library suite passes **16/16** on JS and native CPU, including
  source/lifecycle counts, completion, ownership rejection, generic zero state,
  arithmetic boundaries and composed maps.
- Each of the four full/early mixed/predictable benchmark programs compares
  200,000 complete states against its original fallback, including both Boolean
  decisions, both inner tags, zero/one/two/three/max Nat, U32 wrap boundaries and
  seeded random states. Normal and UBSan builds pass. Every timed batch is also
  checked against the independent Python oracle.
- `fixtures/reordered.bend` deliberately changes names, argument/field order and
  inner tag order. Its automatically selected helper passes 200,000 full-state
  comparisons against both the original fallback and an independent C oracle,
  under UBSan. This exercises nested helper scopes as well as layout independence.
- Replacing addition in that fixture with an unsupported multiplication callback
  refuses the optimization. Instrumented generated C verifies exact callback
  execution counts over 200,000 states, including rejected, zero and stopped
  cases; all output fields match the oracle. UBSan passes.
- An arbitrary Nat-successor callback refuses the optimization. Dynamically
  rejected max-Nat inputs succeed without running it; accepted max-Nat inputs
  fail identically to the original compiler, including exit status and output.
- Strict TypeScript checking of isolated `comp.ts` and `bend.ts` passes with
  locally cached TypeScript 5.9.3 and Node typings, plus a declaration for the
  existing Bun `ImportMeta.require` API. This is not the full upstream gate.

[Additional compiler validation results](automatic-validation.json) retain the
compiler hash and fixture artifacts. Benchmark reports retain generated source,
C, binaries, differential harnesses and assembly in their artifact directories.

## Reproduction

From the library root, using the sibling fork rather than `~/.bend`:

```sh
python3 bench/compiler/prepare_guarded.py
# Use the printed /absolute/temporary/path/main.ts below.
python3 tests/run.py --bend-main /absolute/temporary/path/main.ts
python3 bench/compiler/test_guarded.py --bend-main /absolute/temporary/path/main.ts
python3 bench/compiler/ablate.py --automatic-compiler /absolute/temporary/path/main.ts --samples 5
python3 bench/compiler/ablate.py --automatic-compiler /absolute/temporary/path/main.ts --early --samples 5
python3 bench/composition.py --bend-main /absolute/temporary/path/main.ts --samples 3
# With --output report.json on the preceding composition run:
python3 bench/compiler/test_guarded.py --bend-main /absolute/temporary/path/main.ts --composition-report report.json
```

`ablate.py --automatic-compiler` compiles the unchanged pipeline with that
compiler; it does **not** install any handwritten replacement. The original and
handwritten controls still use the pinned sibling compiler. Only the differential
test harness identifies the workload's helper signature. The compiler pass does
not inspect generated C for recognition. Set `BEND_GUARDED_TRACE=1` to inspect
conservative analysis refusals.

Run performance measurements sequentially, apart from tests or compilation jobs.

## Remaining promotion gates

The demonstrated target is now automatic, but this remains a small, conservative
prototype. Testing is not a formal compiler proof. A production change still needs
an upstream compiler review/regression gate, adversarial tests of the expression
joining and field summaries, a broader workload/platform matrix, and a decision
about cold outlining when fallback is frequent. GPU/CUDA validation and a general
profitability policy are outside this milestone. The Source/Reduction API needs
no change to obtain the demonstrated result.
