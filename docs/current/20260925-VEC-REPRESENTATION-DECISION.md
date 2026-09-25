---
created_at: 2026-09-25T15:49:34+02:00
status: experimental-decision
---

# Vec representation decision and release boundary

## Goal

Provide an ordered, indexed `into` destination with performance close to
direct Bend Array code. It must preserve transducer semantics, including
early stopping and ownership. The result should be useful for values beyond
`U32`.

## Equal-capacity experiment

The previous comparison mixed growth and traversal costs. A new paired native
experiment gives both `Data` Vecs capacity 262,144 before inserting 200,000
values. It also measures construction with the resulting collection live
after the clock read; consuming the output afterwards verifies its contents.
Eight randomized sessions, one native thread, and Clang `-O3` produced:

| Construction path | Median µs | Timed allocation requests |
| --- | ---: | ---: |
| Direct preallocated Array | 242.5 | 10 |
| `VecFill<U32>` with caller filler | 261.5 | 15 |
| `VecData<U32>` with `Maybe<&2,U32>` slots | 650.5 | 15 |

The paired median construction ratios to direct Array are 1.13 and 2.71,
respectively. When traversal is also timed, the reserved `VecData` takes
1,403 µs versus 299 µs for `VecFill`. The difference is chiefly work per
element, not extra heap requests. Eight sessions are useful directional
evidence, not a stable cross-machine performance guarantee. Full timings,
allocation counts, and hashes are in
`experiments/affine_xf/vec-reserved-retained-200k-results.json`.

The public fast path should use `Array<T>` slots with a caller-provided filler
for `T: Data`. This is a *scoped* contract: the filler must be a valid `T`, is
owned by Vec, and is never returned as an initialized element. A filler-free
`Data` Vec is feasible but materially slower. It is worth retaining as a
prototype until there is evidence users need it as a separate API. Neither
form solves arbitrary affine `T: Type` yet. The existing affine Vec builds
individual `None` leaves and is about 20 times slower than direct Array in
the 200,000-element build-and-sum measurement.

Both `Data` representations work with a composite `Quad` type and with
`String` values in a small native test. That proves basic type correctness,
not cost for large or deeply shared values. A pointer-bearing benchmark and
memory measurement are still needed before claiming broad performance.

## Required before a public Vec

1. Replace `reserve(depth, filler)` with a requested **element count**, rounded
   up to capacity, and specify what happens for zero or impossible requests.
   Check growth before U32 arithmetic wraps and before Array's native limit.
2. Make the invariant `length <= capacity == Array.size(slots)` reliable.
   Bend currently permits a different module to construct the public record
   with inconsistent fields. `Array.get` and `Array.swap` wrap their index, so
   checked `get`/`set` cannot be safe on a forged record. Either hide the
   representation in the language or validate the invariant at the public
   boundary; do not advertise unconditional safe indexing until then.
3. Verify source traversal, indexed access, growth, and stopping for
   pointer-bearing `Data`, including shared fillers. Add exact boundary tests
   around capacity doubling and the native Array allocation limit.
4. Measure construction, traversal, and peak memory separately for a range
   of lengths and nontrivial values. Compare against equivalent direct Array
   code. The retained-output timing here is a starting point.
5. Only then move the implementation from `experiments/` into the public
   library. The `into` companion already works with the experimental type;
   no new compiler rule has been needed for Vec.

The source-level `VecFill` prototype is not yet a production collection.
The significant unresolved design choice is how to make its representation
invariant enforceable without adding a Vec-specific compiler feature.
