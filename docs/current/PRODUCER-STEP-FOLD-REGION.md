---
created_at: 2026-09-25T07:35:41+02:00
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

1. Add a typed region builder over the checked specialized definitions. Inline
   only checked static helper calls within a strict budget; preserve stable
   identities, branch paths, types, quantities, and call summaries.
2. Add a conservative totality/effect gate. Reject recursive callback cycles,
   foreign/dynamic/parallel/unsafe calls, unknown intrinsics, and potentially
   trapping operations unless their safety is proved from the checked
   arguments. Keep source recursion separate from callback recursion.
3. First run the analyzer without rewriting. It should explain why the
   existing map producer is `Emit`, why filter is `Emit | Skip`, and why
   retention, unknown consumers, nontrivial effects, and over-budget helpers
   are refused.
4. Compose the resulting region with only the checked full fold. Synthesize a
   source-recursive helper and pass it through `Bend.def_check`; install it
   only after successful checking.
5. Add positive tests for map → filter → fold with order-sensitive output,
   step counts, empty input, all rejected, and at least one accepted item.
   Add negative tests for retained intermediate lists, reordered effects or
   traps, recursive callbacks, wrong tail identity, multiple emissions,
   affine values, unknown helpers, and exhausted analysis budget.
6. Verify both JS and native semantics, inspect generated C for eliminated
   intermediate-list construction, and measure allocation requests separately
   from native microsecond timing. Compare the fused result with both the
   materialized source form and handwritten fused Bend. Include compile time
   and generated-code size.

The slice is successful only if the emitted C shows the producer list is gone,
the allocation traffic drops accordingly, the order-sensitive fixtures pass,
all refusal cases preserve fallback behavior, and the result stays within the
code-size/compile-time budget. If recognizing a second equivalent helper
implementation requires another function-name exception, stop: the checked
region extractor is not general enough yet.

## Current evidence and next decision

The existing map/filter fixture passes on the unmodified compiler and the
FoldRegion candidate on JS and native. It verifies output order, count,
empty input, and all-rejected behavior. The candidate currently records zero
fusion and refuses with `producer-body-shape`, as it should for an unsupported
shape. No performance claim follows from this negative result.

The next workset is an analyzer-only prototype and adversarial tests for its
proof boundary. Rewriting and benchmarking follow only after the analyzer
extracts the intended `Emit | Skip` relation without a name-based special case.
