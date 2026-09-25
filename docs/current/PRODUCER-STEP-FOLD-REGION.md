---
created_at: 2026-09-25T07:35:41+02:00
updated_at: 2026-09-25T09:19:50+02:00
status: current
---

# Producer-step/fold region design

## Decision this design supports

The current checked FoldRegion experiment removes an intermediate list when a
checked producer emits exactly one value for each source element and a checked
tail fold immediately consumes it. The map/filter boundary test showed where
that rule stops: a producer step can emit zero values, and a helper call hides
the branch that decides whether the value is emitted.

The next experiment should recognize a small typed control-flow region and
compose it with a fold. It must not add a compiler rule for `List.filter`,
`filter.put`, or a transducer name. The optimizer should discover the behavior
from checked definitions, preserve fallback code whenever its proof is
incomplete, and validate every synthesized helper with `Bend.def_check`.

This is a design for the next **private compiler experiment**, not a public
reducible-source API or a claim that arbitrary transducer pipelines already
fuse.

## Prioritized choices

Effort here means semantic and maintenance complexity. Value includes how much
uncertainty the option removes before an upstream compiler change is proposed.

| Option | Impact | Effort | Value | Decision |
| --- | --- | --- | --- | --- |
| Add a special case for `List.filter.put` | Small: fixes one currently observed shape | Medium: must prove helper arguments, branches, quantities, and recursive tail | Low: invites another exception for each library implementation | Reject |
| Add a typed per-item producer/fold region | High: can represent map, conditional emission, and the fold independently of library names | High: checked bindings, branch paths, evaluation safety, type and ownership proofs | Highest: tests whether the compiler can recover composition structure generally | Do next |
| Change `List.filter` or add a public `Reducible` interface first | Potentially broad API benefit | Very high: commits source lifecycle, effects, stopping, and ownership contracts | Uncertain before the compiler boundary is known | Defer |
| Benchmark the unchanged map/filter fallback | Low: measures materialization, not the proposed rewrite | Low | Low for the fusion question | Defer until a positive rewrite exists |

## Proposed region

Use a small checked control-flow graph local to one source item and one fold
state. It is an analysis/lowering representation over Bend's existing checked
terms, not a replacement for the compiler's whole-program IR.

Each value in the region carries:

- a stable identity tied to the opened checked binding (never just its C layout
  or printed name);
- its checked type, including the live/erased and quantity information needed
  by Bend's checker;
- its producer or call site and the branch conditions under which it exists.

The initial node vocabulary is deliberately small:

```text
Bind(value, checked-pure-expression, next)
Branch(checked-boolean, then-region, else-region)
Call(checked-function, typed-arguments, result, next)
Exit(Emit(value) | Skip)
```

`Bind` gives a computed value one identity, so a mapped result used by both a
predicate and the fold is evaluated once. `Branch` retains the real checked
condition and both paths. The first lowering accepts only exits that mean
“emit one value” or “emit nothing for this input.” It composes `Emit(x)` with
the fold step and turns `Skip` into the unchanged fold state.

The region also records an effect/totality summary for every moved operation.
For the first experiment, any unknown, effectful, potentially trapping, or
unproved recursive callback rejects the whole candidate. Pure-looking is not
enough: moving the fold step for item 1 ahead of producer work for item 2 can
change behavior if either side has effects, can fail, or can diverge. The
current `fold_region_safe_function` gate establishes only a conservative
subset of purity; it does not prove termination, and its intrinsic whitelist
must not be treated as a totality proof.

## Composition rule

The semantic target for the first slice is an ordered source traversal with a
checked per-item producer relation `P : Input -> Skip | Emit(Output)` and a
checked full-fold step `F : Accumulator -> Output -> Accumulator`:

```text
for each input x in source order:
  P(x) = Skip       => keep accumulator unchanged
  P(x) = Emit(y)    => accumulator = F(accumulator, y)
```

The source's empty case returns the initial accumulator. The output sequence
must have the same order as materializing the original producer and folding
that list. In the map/filter test, the region is derived by exposing checked
helper calls: bind the mapped value, test the predicate, then either skip or
pass the same mapped value to the fold. The analysis should accept any checked
helper that reduces to this relationship, subject to the proof gates; it must
not require a helper with a particular name or declaration site.

The private lowering may synthesize a direct recursive helper over the
original source. It must preserve single evaluation of the source and initial
accumulator, preserve branch conditions, and carry the fold state through the
source recursion. Bend's checker remains the final authority for the generated
helper's types and affine use. A checker success does not replace the separate
semantic proof that skipped/retained values and callback order are correct.

## Required proof gates

The optimizer may rewrite only when it proves all of these facts:

1. **Source traversal:** the producer recursively consumes exactly the source
   tail once, has a terminating empty case for finite input, and emits values
   in the same order as the original list it constructs. Unknown source
   adapters remain unchanged.
2. **Per-item relation:** all branches for one source item resolve to either
   one `Emit(value)` or `Skip`. The recursive tail result is the same on both
   paths. Multiple emits, mutation, hidden buffered state, or a branch whose
   tail differs are outside this first slice.
3. **Fold relation:** the consumer is a full left fold with the same initial
   state and a checked `step(accumulator, value)` call. Early stop and
   completion/flush behavior are not inferred from an ordinary return value.
4. **Evaluation safety:** every expression whose order changes—including the
   producer body, stage callbacks, fold step, source expression, and initial
   accumulator—is proven effect-free, total, and non-trapping, or the rewrite
   is refused. The source and initial accumulator must each be evaluated once;
   their order relative to producer work must be preserved or proven
   unobservable. Recursive user callbacks are rejected unless a later
   compiler fact proves termination. An unrecognized intrinsic is not
   presumed safe.
5. **Ownership:** the original source item, mapped value, skipped value,
   accumulator, and any retained output obey their checked quantities. The
   synthesized helper is rechecked. If the step retains an emitted value, that
   value remains available through the accumulator exactly as before.
6. **Failure behavior:** no candidate may remove or move an observable effect,
   panic/trap, or unknown operation. If the compiler cannot establish that the
   two evaluation schedules are observationally equivalent, it keeps the
   original materializing program.
7. **Resource bounds:** inlining/region construction has a fixed node and call
   depth budget. Budget exhaustion is a refusal, not partial extraction.

The existing map/fold rule should use the same gates. In particular, its
current acceptance of recursive callbacks and potentially trapping intrinsics
needs adversarial review before the generalized region is considered
sound. Its current restriction to a variable or constant initial accumulator
is a conservative guard; it does not by itself establish that evaluating the
source expression before the initial accumulator preserves the original
program's behavior. This follow-up is part of the implementation, not an
assumption that `Bend.def_check` establishes effect or termination
equivalence.

## What this generalizes to—and what it does not

For stateless one-or-zero-output operations, the region composes naturally:

- `map(f)` is `Bind(y, f(x)); Emit(y)`;
- `filter(p)` is `Branch(p(x), Emit(x), Skip)`;
- `keep(f)` can lower to a checked option match with `Emit(value)` and
  `Skip`, when the payload's ownership permits it;
- `remove(p)` is the complementary branch.

That gives a useful extension test without adding compiler vocabulary for
those operations. New library implementations that lower to the same checked
region should share the rule.

This region does **not** yet define the complete semantics needed for every
transducer. `take` needs state and a stop signal; `partition_all` needs owned
buffer state and completion-time emission; `mapcat` can emit multiple values
per input; IO sources need cancellation and resource cleanup. Before supporting
those, extend the typed control-flow model with explicit stage state,
`Continue`/`Stop`, repeated downstream yields, and completion. Do not fake
these behaviors as `Skip | Emit` or infer them from library names. The map /
filter experiment is the smallest test of the representation, not evidence
that partitioning or arbitrary sources are already covered.

## Implementation sequence and acceptance

1. **Complete.** Add a typed region builder over the checked specialized definitions. Inline
   only checked static helper calls within a strict budget; preserve stable
   identities, branch paths, types, quantities, and call summaries.
2. **Complete for the initial supported subset.** Add a conservative totality/effect gate. Reject recursive callback cycles,
   foreign/dynamic/parallel/unsafe calls, unknown intrinsics, and potentially
   trapping operations unless their safety is proved from the checked
   arguments. Keep source recursion separate from callback recursion.
3. **Complete.** Run the analyzer without rewriting and confirm it recovers
   the map `Emit` and filter `Emit | Skip` stages without operation-name
   recognition.
4. **Complete for map → filter → full fold.** Compose the region with the
   checked fold, synthesize a source-recursive helper, recheck it with
   `Bend.def_check`, and keep the fallback on any refusal.
5. **Partial.** Positive tests now cover order-sensitive output, step counts,
   empty input, all rejected values, retained outputs, and a type-changing
   Nat-to-U32 map before filter. Negative tests cover
   recursive callbacks, Nat overflow risk, unsafe/unknown callbacks, and
   unknown consumers. Still needed are a second independent producer shape,
   evaluation-order/trap counterexamples, wrong-tail/multiple-output cases,
   and an explicit lowering-budget refusal fixture.
6. **Measured; compiler work remains.** JS/native semantics pass. A 300,000-item
   native benchmark now compares upstream, static-callback-only, FoldRegion,
   and handwritten code. Separate instrumented builds count dynamic
   allocations, and paired timing binaries use the microsecond clock. The
   FoldRegion path removes timed List construction but keeps one heap request
   per source item; generated C identifies that request as a closure capturing
   the tail, accumulator, and mapped value. See the results below.

The slice is successful only if the emitted C shows the producer list is gone,
the allocation traffic drops accordingly, the order-sensitive fixtures pass,
all refusal cases preserve fallback behavior, and the result stays within the
code-size/compile-time budget. If recognizing a second equivalent helper
implementation requires another function-name exception, stop: the checked
region extractor is not general enough yet.

## Current evidence and next decision

The checked region now composes the tested map → Boolean filter → full fold
without a library-name rule. It extracts the map stage as `Emit` and the
filter stage as `Emit | Skip`, then synthesizes a source-recursive helper and
installs it only after `Bend.def_check` succeeds. The analyzer reports
`1:0:1:0 > 1:1:1:1` (binds, branches, emits, skips); the map/filter suite
records 36 successful rewrites and 8 checked helpers. A second fixture checks
that emitted values can be retained in the fold accumulator.

The candidate passed 33/33 suite cases across JS/native semantics,
code-generation, and refusal assertions. The semantic cases check order,
count, empty input, all rejected values, retained values, and a
type-changing Nat-to-U32 stage. Totality tests
refuse recursive callbacks and `Nat.add`/`Nat.mul` without proofs; a guarded
`U32.shln` callback fuses, and audited `U32.div`/`U32.mod` zero-divisor results
remain accepted.

For a stronger measurement, the same 300,000-item workload runs through three
compiler builds: raw upstream, static-callback specialization alone, and the
FoldRegion candidate. It compares materialized `mapped_values → List.filter →
List.foldl`, the public transducer `map → filter → reducing` pipeline, and a
handwritten fused loop. The input is runtime-sized and constructed before the
timer. Sixteen sessions randomize the nine compiler/lane runs; instrumented C
builds are separate from timing builds. The raw report includes samples,
compiler hashes, code sizes, and bootstrap intervals:
[`fold-region-map-filter-results.json`](../../bench/compiler/fold-region-map-filter-results.json).

| Compiler | Materialized µs | Public transducer µs | Handwritten µs | Materialized / handwritten |
| --- | ---: | ---: | ---: | ---: |
| Raw `bendlang/main` | 2,016 | 8,278 | 345.5 | 5.77x |
| Static-callback only | 1,999 | 344.5 | 346 | 5.77x |
| FoldRegion candidate | 1,179 | 332.5 | 341 | 3.50x |

The FoldRegion/materialized ratio against static-callback-only is 0.598
([0.572, 0.619]), a 40% timing reduction. The FoldRegion candidate remains
3.50x slower than handwritten code (paired ratio 95% interval [3.44, 3.65]).
On this workload, the candidate transducer and handwritten timings are
statistically consistent: transducer/handwritten is 1.003 [0.962, 1.028].
The static-only compiler already shows parity, at 1.003 [0.957, 1.031];
FoldRegion does not materially change that lane. The large transducer
improvement therefore comes from checked static-callback specialization,
while the new FoldRegion pass improves the separately materialized pipeline.

Allocation counters explain the remaining difference. During one timed
materialized traversal, raw and static-only each make 450,009 heap allocation
requests, including 450,000 dynamic List Cons cells. FoldRegion makes 300,009
requests and constructs zero timed List Cons cells. The handwritten loop makes
nine fixed requests and constructs no timed List Cons cells. Generated C confirms
that the one-per-input allocation in the fused helper is a closure: it stores
the source tail, accumulator, and mapped value, then calls `CLO_APPLY` to run
the extracted Boolean branch. Thus the List is gone, but the synthesized
branch is not yet direct control flow.

The generated C is 153,618 bytes upstream, 117,025 with static callbacks, and
114,525 with FoldRegion; JS is 26,381, 22,723, and 22,325 bytes. One build took
0.119/0.118/0.134 seconds for Bend compilation and 0.288/0.220/0.215 seconds
for Clang `-O3`, respectively. These are single compile observations; the raw
report records them as size/build context, not stable performance estimates.

The next compiler experiment should optimize a checked, immediately-applied
match (`App(Mat, value)`) into the same control flow as a directly matched
function parameter. This rule must be general to checked match closures, not
recognize `filter` or FoldRegion helper names. It should evaluate the condition
once, keep values live only on the paths that use them, preserve affine
ownership, and fall back on any unproved case. Re-measure the same fixture and
require the per-item closure allocation to disappear before testing an
independently written producer shape. Keep the region limited to stateless
`Emit | Skip`; `take`, buffered partitioning, completion, and early stop still
need explicit state and lifecycle nodes.

## Reproduction

Prepare the static-callback control and the full FoldRegion candidate from the
pinned upstream checkout, then rerun the matched benchmark:

```sh
python3 bench/compiler/prepare_static.py --output-dir /tmp/transduce-static-control
python3 bench/compiler/prepare_fold_region.py --output-dir /tmp/transduce-fold-region
python3 bench/compiler/measure_fold_region_map_filter.py \
  --upstream-main ../bend/bend2/main.ts \
  --static-main /tmp/transduce-static-control/main.ts \
  --fold-region-main /tmp/transduce-fold-region/main.ts \
  --items 300000 --sessions 16 \
  --output bench/compiler/fold-region-map-filter-results.json
```
