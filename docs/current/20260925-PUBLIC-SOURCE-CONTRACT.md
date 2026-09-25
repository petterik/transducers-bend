---
created_at: 2026-09-25T14:24:00+02:00
updated_at: 2026-09-25T14:37:00+02:00
status: experimental
---

# Source companion contract

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

The compiler candidate now accepts `into([], xf, xs)`, a bare `[]` source,
and a bare custom constructor source. It first infers the stage and other
inferable arguments, then uses a constructor's unique declaring type to select
that owner's companion. The checked target element type instantiates at most
one template parameter on the method; the ordinary checker validates the
literal's fields and the method's result. This deliberately rejects more
complex methods instead of guessing an element type or scanning imported
adapters. `companion_literals.bend` checks all three forms on JS and native.
