---
created_at: 2026-09-25T15:49:34+02:00
status: superseded-by-public-vec
---

# Vec representation decision and release boundary

This was the feasibility decision before the public API. See
`docs/current/20260925-VEC-PUBLIC-CONTRACT.md` for the shipped contract and
final validation.

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

The fast path should use `Array<T>` slots with a caller-provided filler for
`T: Data`. This is a *scoped* contract: the filler must be a valid `T`, is
owned by Vec, and is never returned as an initialized element. A filler-free
`Data` Vec is feasible, but its cost depends on the element type. It should
remain available for evaluation because not every output has a natural filler.
Neither form solves arbitrary affine `T: Type` yet. The existing affine Vec builds
individual `None` leaves and is about 20 times slower than direct Array in
the 200,000-element build-and-sum measurement.

Both `Data` representations work with a composite `Quad` type and with
`String` values in a small native test. A second retained-output benchmark
collected 200,000 distinct decimal strings with preallocated capacity:

| Construction path | Median µs | Paired ratio to direct Array |
| --- | ---: | ---: |
| Direct preallocated Array | 727.0 | 1.00 |
| `VecFill<String>` | 735.5 | 1.019 |
| `VecData<String>` | 924.5 | 1.271 |

The string source was made before the clock read; the result was consumed
after it. All lanes returned the same total character count. Timed allocation
requests were 10, 13, and 13. This is evidence that pointer-bearing values
can work efficiently, though it covers one string shape and no peak-memory
measurement. Full samples and hashes are in
`experiments/affine_xf/vec-string-200k-results.json`.

The filler-free source was then changed to consume each initialized slot with
`Array.swap(..., None{})` instead of duplicating it with `Array.get`. Native
and JS still agree on growth, order, and `take(0)`/`take(2)`; both also pass
the String test. In a separate 12-session measurement, the String
`VecData`/`VecFill` construction ratio changed from 1.247 to 1.220. The
timing intervals overlap, so this is not evidence of a meaningful speedup.
The whole-program runtime allocation count dropped by 200,000 for the
String `VecData` lane, consistent with avoiding one retained copy per item.
The timed allocation count stayed at 13. The before/after runs were not
interleaved, so absolute times should not be compared. New samples are in
`vec-swap-200k-results.json` and `vec-string-swap-200k-results.json`.

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
   code. The retained-output U32 and String timings are starting points.
5. Only then move the implementation from `experiments/` into the public
   library. The `into` companion already works with the experimental type;
   no new compiler rule has been needed for Vec.

The source-level `VecFill` prototype is not yet a production collection.
The significant unresolved design choice is how to make its representation
invariant enforceable without adding a Vec-specific compiler feature.

## Count-based reservation probe

Both Data prototypes now have `reserve_items(requested)` alongside their
older depth-based `reserve`. The new call rounds a requested element count to
the next power of two, keeping capacity one for requests zero and one. It
returns `None` above 2^23 instead of overflowing U32 arithmetic or calling
`Array.new` at a depth where nontrivial shared fillers produce a runtime
error. Native and JS agree on counts 0–5 and the 2^23 boundary, and on
actual four-slot reservations for `U32` and `String`.

This is only a constructor probe. Dynamic `push` can still grow past that
limit; raw `reserve(depth)` is still exposed; and `None` does not explain the
rejected request. A public API needs one consistent checked-capacity policy
for construction *and* growth. Silent truncation would violate `into`.
