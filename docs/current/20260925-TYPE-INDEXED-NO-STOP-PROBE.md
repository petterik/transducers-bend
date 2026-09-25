# Type-indexed no-stop feasibility probe (2026-09-25)

This is an isolated experiment. It does not change the public transducer API or the `../bend` checkout. The [Bend fixture](../../experiments/affine_xf/no_stop_indexed_probe.bend) and [candidate compiler patch](../../experiments/affine_xf/no_stop_indexed_compiler.patch) are sufficient to reproduce it against the current `bendlang/main` checkout.

## Question and result

Can one generic source driver serve both stopping and non-stopping reductions, while the compiler removes stop checks only when the type proves they are impossible? **Yes for these two source shapes, with a small compiler candidate, but the compiler rule is not production ready.** The total Array and independent branching-tree folds compile without a stop tag or branch in their recursive loop. The stopping instantiations retain their checks. The total paths run approximately as fast as direct handwritten folds on this machine.

`Flow<K,S>` has `Ready{state:S}` and `Halted{permit:K,state:S}`. A reducer that may stop uses `K=Unit`. A total reducer uses `K=Empty`; checked live code cannot make its `Halted` value. The source's public `drive_array`/`drive_tree` returns only `S`, the opaque accumulator. `Flow` is internal to its recursive loop and inspection callback. This proves the absence of a **stop variant**, not that an arbitrary source visits every item or that its callback is otherwise well behaved. A generic source cannot forge a `Halted` value without a `K`, but it could still end its traversal early and return its accumulator.

Stock Bend lays out every declared variant even when a live field is an empty datatype, so merely using `Empty` leaves the branch and tag in generated C. The candidate patch does three general things: omit a variant with a live field whose datatype has zero constructors; omit its unreachable match arm (including the now-redundant default); and reinsert a tag when a specialized one-arm value crosses into a generic multi-arm function. It recognizes datatype shape, not `Flow`, `Empty`, transducers, Array, or a source name. The last two rules are essential: the first draft crashed on the generic function boundary, and the next draft returned `99` instead of `42` for a match with a default arm. The [default-arm regression](../../experiments/affine_xf/no_stop_default_arm.bend) now catches that error. A separate [zero-constructor datatype](../../experiments/affine_xf/no_stop_zero_adt.bend) checks that the rule does not depend on the name `Empty`.

## Evidence

The native timings below are medians of 12 executions per cell, randomized across compilers and modes, one thread, with source construction outside the timed region. They are microseconds on this desktop and should be treated as directionally useful rather than a stable release benchmark. The Array has 2^18 leaves; the branching tree has 2^16 leaves. The total and direct folds do the same `inc` and sum work.

| Source | Compiler | Direct | Indexed total | Total/direct |
| --- | --- | ---: | ---: | ---: |
| Array | stock | 2134 | 2177.5 | 1.020 |
| Array | candidate | 2150.5 | 2140.5 | 0.995 |
| Branching tree | stock | 157.5 | 179.5 | 1.140 |
| Branching tree | candidate | 160 | 157 | 0.981 |

A prior 12-run sample gave Array 1944.5/2022.5 µs (stock direct/total) and 1967/1962.5 µs (candidate), and tree 144/168 µs (stock) and 145/146 µs (candidate). The change is consistent in direction; absolute times drift between samples. The stopping path still carries its tag and branch. Generated C for the combined fixture shrank from 171,468 to 168,755 bytes. That is a whole-program size measurement, not an isolated estimate of the fold's code size.

The [semantics fixture](../../experiments/affine_xf/no_stop_indexed_semantics.bend) covers both sources, initial stop, a finite budget, and a nested source that preserves downstream stop (the `mapcat`-like case). The [affine fixture](../../experiments/affine_xf/no_stop_indexed_affine.bend) moves an owned Array accumulator through the total fold. Stock and candidate agree in value mode, generated JavaScript, and native code. The candidate also passes `tests/run.py` in full: 40/40 JS/native cases, source rejection, code-shape checks, and bounded laws. A generic attempt to construct `Halted{Unit{},state}` for arbitrary `K` was rejected by the checker (`expected K; observed Unit`). Twelve randomized compiler invocations each showed no repeatable compile-time penalty: fixture medians 226.5 ms stock versus 225.2 ms candidate; existing `mapcat_public` medians 314.1 versus 314.8 ms. Those process timings include Bun startup.

## Boundary and next decision

The experiment validates the *direction*, not a public API change. The patch needs a compiler-wide layout and ABI audit: every conversion between specialized and generic representations, default matches, boxed values, arrays of such values, foreign boundaries, and zero-arm datatypes must be handled. A narrowly lucky benchmark cannot license a representation rewrite for all Bend programs. The current candidate only recognizes a field whose instantiated type is directly a zero-constructor datatype; it does not infer every indirectly uninhabited type.

Separately, the public `Reducer`/`Xf` types must carry a stopping capability through `start`, `step`, composition, `take`, `mapcat`, and completion. A custom or unknown reducer must keep the stopping representation. `take(0)` must stop before any source item. Only after that capability propagation and compiler audit should we benchmark the actual `transduce`/`into` calls against direct Bend. Until then, the existing public API remains unchanged and correct, with its measured stop-check cost.
