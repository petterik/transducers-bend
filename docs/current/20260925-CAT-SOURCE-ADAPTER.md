---
created_at: 2026-09-25T22:27:13+02:00
status: implemented
---

# Source adapters for cat

`cat` now accepts a zero-field `SourceAdapter<B, X, Drive>` supplied by the
fragment type's owner. List, Array, Range, and String expose `.adapter`; a
custom source can do the same beside its `.source` companion. The stage still
receives and consumes raw fragments. For example:

```bend
comp2(map(~U32, ~List<U32>, ~fragment),
  cat(T.List.adapter(~U32)))
```

The adapter records the same static drive previously spelled as a long lambda
at each `cat` call. It does not add a fragment wrapper or alter stop and
completion handling. `cat_drive` exposes the old explicit-drive form for
sources without an adapter. `mapcat` still accepts an explicit drive; composing
`map` with adapter-based `cat` gives the shorter general path.

This is deliberately a library change. The compiler's existing companion
lookup works when a source is a direct argument to `transduce`, but it cannot
infer a drive from an arbitrary mapper's return type. A probe using a source
function argument also failed to infer the hidden higher-order drive. A
nominal adapter argument succeeded without broadening template inference.

The List, Array, Range, String, and custom Pair adapter paths are checked on
both JS and native. The composed map/cat fixture checks a List-producing
mapper and the existing `mapcat` path remains in the full suite. A zero-field
adapter is still a runtime value in generated JavaScript; the current evidence
establishes semantics and a smaller call site, not a new performance claim.
