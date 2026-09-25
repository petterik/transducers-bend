---
created_at: 2026-09-25T16:25:24+02:00
status: production-ready-with-supported-compiler
---

# Public Data Vec contract

`vec.bend` now provides a growable, ordered `Vec<T: Data>` backed by Bend's
flat Array representation. `vec_maybe.bend` provides a filler-free
`VecMaybe<T: Data>` with optional slots. `xf.bend` exposes four-argument
`transduce` and three-argument `into`; both Vec types implement destination
and source companions.
The supported compiler is the fork branch `codex/transducer-companions` at
`2eae5f28`, based on `bendlang/main`. Stock `bendlang/main` does not yet
insert companion adapters, so these public entry points require that branch.
The older `transduce.bend` API remains available.

## API and invariants

- `Vec.empty(~T, filler)` creates an empty Vec with capacity one. The caller
  supplies a valid `T` to fill unused slots; only indices below `length`
  belong to the logical collection.
- `Vec.with_capacity(~T, requested, filler)` returns `Some{vec}` with capacity
  rounded to a power of two, or `None{}` when `requested > 2^23`. Zero and
  one both yield capacity one. The limit is conservative for nontrivial
  shared fillers under Bend's native Array runtime.
- `Xf.into(vec, xf, source)` appends transformed values in encounter order.
  Dynamic growth doubles capacity. If Bend cannot allocate the next Array,
  its normal runtime error terminates the run; collection never silently
  truncates a successful `into`.
- `Vec.get` returns `Maybe<T>` and `Vec.set` returns `Updated` or `Invalid`.
  Both check logical length and physical Array size. `Vec.get_unchecked`
  and `Vec.set_unchecked` omit bounds checks for a caller who has established
  `index < vec.length`; invalid indices have Bend Array's index-wrapping
  behavior. The unchecked write returns the displaced element.
- Vec source traversal reads the logical prefix in order, stops immediately
  on downstream `Stop`, and never visits beyond physical Array size. A
  constructed Vec can be consumed by `transduce` or `into`.
- `VecMaybe.empty(~T)` and `VecMaybe.with_capacity(~T, requested)` provide
  the same ordered collection workflow without a filler. The latter uses
  the same 2^23 initial-capacity limit. `VecMaybe.get` returns an optional
  item; `VecMaybe.set` returns the previous optional slot on success. A Vec
  made through these operations has `Some` in every initialized slot.
  Traversal consumes each slot with `Array.swap(..., None{})`, avoiding a
  retained copy of the value being yielded.

Both collections are `Type` even when `T` is `Data`, so the owner remains
affine. Bend
currently exposes datatype constructors across modules. Directly fabricating
a Vec record with inconsistent fields is outside this contract; callers must
use the constructors and collection operations. The checked operations prevent an
out-of-range index from wrapping on a malformed record, but cannot establish
whether its purported logical prefix was actually initialized. A fast
`Vec<T: Type>` for arbitrary affine elements is not provided; its optional
slot prototype remains in `experiments/`.

The companion compiler needs a typed source value. A literal String or
custom-collection constructor may require a small typed helper before an
`into` or `transduce` call. No compiler rule for literal elaboration was added.
Collecting into List prepends, following Clojure's `conj` ordering; Vec
preserves encounter order.

## Verification and performance

The public API is exercised on native and JS with List, Array, Range, String,
Vec, and an independently defined source. Tests cover mixed `comp5` stages,
`keep`, `mapcat`, early and initial stopping, growth, composite `Data`,
`String`, checked and unchecked indices, replacement, and rejected capacity.
The repository's full test gate passes 37/37 cases, including code-shape and
mapper-count checks.

Paired native samples use 200,000 elements, Clang `-O3`, one thread, 12
randomized sessions for construction and 24 for indexing. Values are
consumed after the construction clock read. These figures describe this
machine and compiler build, not a universal speed guarantee. Rows from
separate sessions should be compared by their paired ratio:

| Operation | Direct Array median | Public Vec median | Paired Vec/Array ratio |
| --- | ---: | ---: | ---: |
| Reserved `U32` construction | 253 µs | 259 µs | 1.08 |
| Dynamic `U32` construction | 253 µs preallocated baseline | 470 µs | 1.79 |
| Reserved distinct `String` construction | 726 µs | 717 µs | 0.99 |
| Filler-free `U32` construction | 327 µs | 653 µs | 2.15 |
| Filler-free distinct `String` construction | 722 µs | 906 µs | 1.25 |
| 200,000 indexed reads, unchecked | 30 µs | 30 µs | 1.00 |
| 200,000 indexed writes, unchecked | 61 µs | 61 µs | 1.00 |
| 200,000 indexed reads, checked | 30 µs | 82 µs | 2.70 |
| 200,000 indexed writes, checked | 61 µs | 85 µs | 1.39 |

The direct Array construction baseline is preallocated; dynamic Vec copies
the live Array when it doubles. Indexing lanes made nine timed runtime heap
requests each, regardless of path. Full timing samples, allocation counts,
and compiler/fixture hashes are in
`experiments/affine_xf/vec-public-final-200k-results.json`,
`vec-public-string-200k-results.json`, and
`vec-public-index-mutation-200k-results.json`. Filler-free results are in
`vec-public-dual-200k-results.json` and
`vec-public-dual-string-200k-results.json`.

This release is scoped to `Data` elements and the supported fork compiler.
The remaining affine-Vec and stock-compiler work are separate language and
representation projects, not defects hidden behind the public Data Vec API.
