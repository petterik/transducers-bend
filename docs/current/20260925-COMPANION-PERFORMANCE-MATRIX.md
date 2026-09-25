---
created_at: 2026-09-25T14:51:00+02:00
updated_at: 2026-09-25T14:51:00+02:00
status: measured
---

# Companion API performance and semantics matrix

The compiler is `petterik/bend:codex/transducer-companions` at `2eae5f28`,
based on upstream `3276efac`. `companion_semantics_matrix.bend` checks
`keep`, `mapcat`, both positions of `take`, retained List outputs, ordered
Array traversal, a custom `SamplePair` source, and Range on JS and native.
The `probe_companion.py` ownership and negative fixtures also pass, as does
the 33-test transducer suite.

`companion_matrix_bench.bend` compares public `Auto.transduce` / `Auto.into`
against equivalent handwritten folds. For `keep` and `mapcat`, a third lane
uses a manually assembled static reducer recipe, separating API overhead
from the fragment-building semantics. The independent `Counted` source wraps
a List and supplies its own `Source` method. Retained output is consumed after
building so Clang cannot drop it. Array direct and generic lanes both visit
the same tree and add one to each element. Two take-order lanes each emit the
same even number of values; the separate semantics fixture checks the odd
boundary where stopping occurs inside a `mapcat` fragment.

The 32-session native run uses two million List inputs and a 2²⁰-element
Array, Clang `-O3`, one thread, shuffled paired lanes, microsecond timing,
and separately instrumented timed heap requests. Full samples are in
`companion-matrix-2m-full-results.json`.

| Workload | Generic / direct paired median | 95% bootstrap interval | Timed allocation requests, direct / generic |
| --- | ---: | ---: | ---: |
| keep → sum | 1.013 | 1.001–1.032 | 9 / 9 |
| mapcat → sum | 2.315 | 2.027–2.566 | 9 / 4,000,009 |
| retained keep → List → sum | 0.991 | 0.969–1.008 | 1,000,009 / 1,000,009 |
| Array source → sum | 1.089 | 1.078–1.093 | 2,097,159 / 2,097,159 |
| take after mapcat | 1.285 | 1.252–1.343 | 9 / 2,000,012 |
| take before mapcat | 1.284 | 1.255–1.320 | 9 / 2,000,012 |
| custom List-owning source | 1.018 | 0.988–1.042 | 9 / 9 |

The generic `keep` lane is effectively at handwritten speed, and the custom
source and retained List lanes show no proportional adapter overhead. The
`mapcat` generic lane is close to its manually assembled static recipe
(paired ratio 0.956, interval 0.870–0.985), but both allocate a two-element
List for every input. The direct sum can add the two values without building
that fragment. This is a real semantic/library cost, not evidence that the
general companion rule failed to fuse. Both take orders have the same
allocation traffic in this even-output benchmark and near-equal timing.

Array source traversal is about nine percent slower than an equivalent direct
recursive traversal, despite identical timed allocation counts. The common
roughly two allocations per Array leaf are in the underlying traversal, not
the adapter alone. This lane is a candidate for a future general loop/control
optimization, but this result alone does not justify an Array-specific
compiler rewrite. More source shapes and retained Array values should be
tested before changing the compiler.

Exploratory runs used earlier fixture revisions; only the comparable final
matrix is retained. No claim here extends to partitioning, whose chunk
materialization has a different contract.

## Next ordered destination: Vec

Prototype a `Vec<T>` with an owned `Array<Maybe<T>>`, logical length, and
capacity. It starts empty, appends in insertion order, and doubles capacity
when full. It should provide indexed `get`/`swap`/`set` with explicit ownership
and serve as both `Destination` and `Source`; `into(Vec.empty(), xf, coll)`
would then have ordered output without requiring a bare-literal compiler rule.
Benchmark push, indexed mutation, traversal, and transducer collection
against List and handwritten loops, including growth boundaries and retained
outputs.

The first feasibility check is construction of empty slots for an affine
element type. `Array.new` requires `Data`; a generic `Vec<T>` may have to build
the empty half of its tree structurally on growth. Also define what `get`
returns for an affine element: likely a moved value plus the updated Vec, or a
swap with a replacement. Capacity and logical length stay distinct, so an
arbitrary-length Vec need not pretend to be a plain power-of-two Array.
