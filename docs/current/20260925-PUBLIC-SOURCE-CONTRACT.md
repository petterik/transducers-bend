---
created_at: 2026-09-25T14:24:00+02:00
updated_at: 2026-09-25T14:51:00+02:00
status: superseded-by-opaque-source-protocol
---

# Source companion contract

This records the original reducer-indexed `Source` contract. The current
[opaque accumulator protocol](20260925-OPAQUE-SOURCE-PROTOCOL.md) replaces its
`Drive` type while keeping the same owner-scoped companion lookup.

`Source<A,X,Drive>` now lives in `transduce.bend`, beside the ordered folds.
`Range.source` owns the Range adapter. `List.source` and `Array.source` are
core-owned extensions for Base types, which cannot import this library. A
custom type can define its own `Type.source` and own its input. The compiler
looks only for that method; if the owner cannot define one, a caller passes an
explicit `Source` witness. This keeps a third-party adapter possible without
inventing a global instance registry or arbitrary import-order precedence.

`Array.source` consumes the balanced tree from left to right and preserves
stopping. `companion_core_sources.bend` runs List-independent Range and Array
calls through the same public `transduce(xf,rf,init,coll)` spelling, on JS and
native. The existing negative fixtures still reject orphan methods, missing
methods, invalid return types, and reuse of an affine source.

The destination contract remains `Destination<B,D,Q>` beside `Rf`. A raw
destination with an owner method `Type.destination` is converted when the
expected witness is known. `into` delegates to `transduce` exactly once. A
List destination prepends as Clojure's List `conj` does. Thus callers seeking
input order should choose an ordered destination.

## Array destination boundary

Bend's current `Array<T>` has no empty value or append operation. It is a
nonempty, power-of-two balanced tree. Consequently, a general `into` that may
produce zero, one, or an arbitrary number of elements cannot return a plain
`Array<T>` without defining what capacity, padding, overflow, and valid length
mean. A useful ordered destination is a separate growable collection, likely
an owned buffer plus length, or a builder that finishes to an array-like view.
That choice requires its own contract and measurements; `Array.source` needs
none of it and is available now. The current List destination intentionally
reverses insertion order.

Bare literals such as `into([], xf, xs)` are deliberately outside this
compiler rule. A typed destination value, or a helper with a typed List
parameter, gives the checker the element type without adding contextual
constructor inference to Bend. This keeps the compiler change easier to
explain and review.
