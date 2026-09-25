---
created_at: 2026-09-25
status: implemented-and-locally-validated
---

# Opaque accumulator source protocol

## Contract

The source drives the fold. It owns the collection, calls a closed step for
each item in encounter order, inspects the resulting accumulator to know
whether to continue, and returns that same accumulator type. It never starts
or completes a reducer. Public `transduce` handles start and completion once.

`Source<A, X, Drive>` now indexes a drive generic in an opaque accumulator
`S`, a step `S -> A -> S`, and an inspection `S -> Checked<S>`. Inspection
consumes and returns `S` because Bend values can be affine. `Checked` means
“feed another item” or “return this accumulator”; it is a decision about
traversal, not a `Stop` value returned by the source. The source's result type
is always `S`. Its type does not mention `Control`.

At the reducer boundary, `S` is instantiated as `Control<State>`. Only the
reducer can construct its `Stop`. A source checked for every abstract `S`
cannot synthesize `Stop` as a value of `S`; the negative fixture
[`opaque_source_reject.bend`](../../experiments/affine_xf/opaque_source_reject.bend)
is rejected by Bend. The type does not prove that a source visits every item
or honors `Checked`; an ill-behaved source could return its incoming `S`
without traversing. Those are source laws, exercised by conformance tests,
not consequences of parametricity alone.

The source must **not unwrap** a reduced accumulator. If `take` stops inside
an inner `mapcat` fragment, the inner drive returns that `Control` unchanged.
The outer source receives it from `cat_source_step` and stops before mapping
another fragment. Clojure's `preserving-reduced` adds a wrapper because its
inner `reduce` removes one `reduced` layer; our drive removes none. The
[`mapcat_stop_propagation.bend`](../../tests/mapcat_stop_propagation.bend)
gate instruments the fragment mapper and confirms exactly two fragments for
`take(3)` over two-item fragments.

List, Array, Range, String, Vec, VecMaybe, and an independent pair source now
implement the opaque protocol. The older `T.reducible`/`over_*` API and its
`Control` folds remain available; this work does not change their semantics.
No compiler change is needed for the new protocol on the supported fork.
Older isolated `experiments/affine_xf/rank2_*` source witnesses record the
previous `Source` signature and are historical snapshots; use the current
gate and benchmark below for this contract.

## Validation and performance

`python3 tests/run.py` passes 40/40 fixtures in JS and native, including
affine values, initial and mid-fragment stopping, completion, source
rejection, core Range/Array/String sources, code shape, and callback-count
gates. The benchmark is reproducible
with [`measure_opaque_source.py`](../../experiments/affine_xf/measure_opaque_source.py),
using two million List items, a 2^20-element Array, Clang `-O3`, and 64
shuffled local sessions against Bend fork commit `20ff80e4`.
[Raw samples](../../experiments/affine_xf/opaque-source-perf-results.json)
record microseconds and paired ratios.

| Fold | Median paired ratio to handwritten direct |
| --- | ---: |
| Custom pair `mapcat` | 0.88, with noisy List timings; treat as near direct rather than a speedup claim |
| Public List `map` | 1.01 |
| Public Array `map` | 1.08 |
| Generic List source with always-ready total step | 0.97 |
| Generic Array source with always-ready total step | 1.09 |

The Array total path is the important limit. Its generated C still carries
and tests a `Checked` tag at leaves and branches. The existing specialized
total Array fold in the [no-stop investigation](20260925-NO-STOP-SPECIALIZATION-INVESTIGATION.md)
ran at handwritten speed. Making the generic source type opaque is a semantic
improvement, not an automatic no-stop specialization. A future optimization
must remove the status branch when the inspector is statically always-ready,
or select a separately typed total drive with an agreement guarantee. This
work makes neither claim for the current public `Xf.transduce` path.

## Confidence boundary

The type prevents a parametric source from fabricating a reducer-specific
`Stop`. It cannot enforce source traversal laws, and it does not make a
stopping reducer total. A generic source may see a `Halted` inspection result
and return the carried accumulator; it may not unwrap or replace that
accumulator. The tests establish behavior for the supplied adapters on the
supported compiler and machine, not a proof for arbitrary custom sources.
