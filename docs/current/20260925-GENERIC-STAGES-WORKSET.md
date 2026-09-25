---
created_at: 2026-09-25T13:36:00+02:00
updated_at: 2026-09-25T13:36:00+02:00
status: experimental
---

# Generic affine transducer stages

The experimental value API now supplies generic `map`, `map_with`, `take`,
`mapcat`, `keep`, `filter`, and `remove` constructors. Each returns an affine
`Xf` with a closed reducer recipe in its type and only runtime configuration
in its value. `shifted` and `taking_u32` delegate to these constructors.
No compiler case recognizes any of these stage names.

The public spelling for a type-changing stage is presently
`V.map(~U32, ~Nat, ~U32.to_nat)`. The callback must be closed template syntax,
and Bend currently cannot infer omitted leading type arguments from that
callback. `take` likewise needs `~A` when built independently of a source.
This is a real API gap relative to `map(f)` or `take(n)`, not a missing
constructor. It calls for a language-level inference design before changing
the compiler again.

The [`rank2_generic_stages.bend`](../../experiments/affine_xf/rank2_generic_stages.bend)
probe composes five different stages, exercises a type-changing map, a
runtime `map_with` setting, `mapcat` stopping mid-fragment, `keep`, `take(0)`,
and both filtering polarities. The emitted JS contains no runtime `Reducer`
record. Both JS and native yield
`([3n], 0, 4, 3n, [2, 11, 1], [4n, 2n])`.
The [`probe_auto_inference.py`](../../experiments/affine_xf/probe_auto_inference.py)
suite passes all ten positive fixtures in both lanes and eight expected
checker rejections.

Two limitations are deliberate. `filter` and `remove` inherit the existing
`T.filter` restriction to `Data` elements because their predicate reads an
element that may then be forwarded. The general `map`/`keep`/`mapcat`
constructors can handle affine elements when their callbacks consume them.
And an explicitly reusable `+x` callback does not have the type `A -> B`;
the probe uses `~(x => maybe_nat(x))` when adapting one. The first attempted
direct call produced an indirect `~?AUTO` diagnostic, which merits better
error reporting, but it was not a fusion failure.

The next workset should make source and destination selection easier without
adding collection-specific compiler paths. It should first define a coherent
explicit witness API, then test whether implicit resolution can be specified
without ambiguous instances or hidden work. It should keep performance and
machine-code comparisons separate from the semantic result above.
