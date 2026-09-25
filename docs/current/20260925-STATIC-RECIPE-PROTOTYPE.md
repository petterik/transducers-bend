---
created_at: 2026-09-25T12:01:00+02:00
updated_at: 2026-09-25T12:16:00+02:00
status: active
---

# Affine static-provider prototype and confidence pass

## Question

Can an affine `Xf` carry owned runtime settings while a general, extensible
compile-time mechanism composes its stage code into the closed reducer recipe
that the current source fold optimizes well? This must work for stages outside
the transducer library, without compiler cases for stage names. The desired
public call remains `transduce(xf, rf, init, coll)`; an explicit source witness
is acceptable in the first compiler experiment.

## Confidence pass

The recommendation is conditional, not a claim that a compiler feature is
already straightforward. Its most important loopholes and proof gates are:

| Loophole | Why it matters | Required gate or remedy |
| --- | --- | --- |
| An erased code index contains an ordinary reducer-transformer function | The composed `Xf` probe still passes a callback on every item | A stage must provide *template code* that forms a closed reducer before the fold, not merely an erased reference to ordinary code |
| The compiler recognizes specific stage or source names | New transducers and third-party adapters would need compiler edits | The lowering rule operates on a typed static-code interface and has no `map`, `take`, `List`, or user-stage branch |
| A runtime capture is evaluated twice or dropped | Violates affine ownership and may change observable behavior | Consume the `Xf` once and move each owned setting into the resulting reducer configuration exactly once |
| A stage's static provider disagrees with an ordinary implementation | Two separate implementations can typecheck yet behave differently | Make the static provider the stage's semantics; use the ordinary reducer path only as a temporary semantic control |
| A dynamic choice between unlike stage compositions is treated as statically known | One type-level recipe cannot describe a runtime-varying pipeline without a sum or dynamic fallback | Specialize statically known compositions; require explicit sum handling or fall back to the ordinary reducer path for dynamic choices |
| Specialization explodes compile time or output size | Runtime wins can be lost in large programs | Bound expansion, cache by checked static code and types, and measure build time and emitted size as the stage count grows |
| Captured mapping functions are assumed free | Affine ownership does not make an unknown runtime function inlineable | Start with closed stage code plus data settings; later test closure conversion of runtime captures and define a slower fallback where necessary |
| Source/destination lookup is conflated with recipe lowering | Implicit lookup would leave the callback handoff unchanged | Prove lowering with explicit adapters first; design implicit reducible/insertion resolution separately |

The first compiler-feature recommendation changed during this pass. An
ordinary *closed lambda* can forward its own binder into a `~` template call.
That lets current Bend express a consumer-polymorphic stage provider in an
erased type index, and a dependent configuration function can carry the
stage's runtime settings. The isolated static-callback pass compiles such a
provider into the existing closed source fold. The generic ordinary
reducer-transformer code index from the earlier workset did not do this: it
left an ordinary callback handoff in the loop. A direct matched plan is also
unnecessary for this representation.

The next compiler target is therefore narrower: infer and specialize these
*existing* closed template arguments from typed affine values at calls to
generic functions. It must be a name-independent rule, not a compiler case
for `Xf` or a stage name. A new static-stage syntax is not justified by the
current evidence.

## Performance control

[`custom_shift.bend`](../../experiments/affine_xf/custom_shift.bend) is a
stage outside the transducer library that owns a runtime offset. Its static
provider composes with `take`, which owns a runtime limit. The paired native
benchmark is
[`static_recipe_bench.bend`](../../experiments/affine_xf/static_recipe_bench.bend).
It prebuilds the List and times only the fold; a separate instrumented build
counts heap requests inside that region. Results against the isolated
static-callback compiler are stored for
[`200k`](../../experiments/affine_xf/static-recipe-shift-200k-results.json)
and [`2m`](../../experiments/affine_xf/static-recipe-shift-2m-results.json):

| Items | Direct median | Existing closed recipe | Staged affine recipe | Rank-2 static `Xf` | Ordinary composed reducer | Rank-2/current paired median [bootstrap 95%] | Timed heap requests: current/rank-2/generic |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 200,000 | 184µs | 202µs | 201µs | 210µs | 3,398µs | 0.998 [0.985, 1.040] | 9 / 14 / 1,200,018 |
| 2,000,000 | 3,495µs | 2,126.5µs | 2,227.5µs | 2,113.5µs | 34,202.5µs | 0.957 [0.885, 1.029] | 9 / 14 / 12,000,018 |

Both staged representations have five fixed timed heap requests beyond the
existing closed recipe and no measured per-item allocation slope. The rank-2
path is close to the existing recipe in these matched sessions. At 200k it
still trails the direct loop; the 2m ranking reverses. This supports the
representation as a way to retain the *current* fast path, not a claim of
universal handwritten-loop parity. The ordinary composed path is about
16–17 times slower than the existing recipe here. These ratios are
workload-specific and the larger run varies noticeably. Reproduce with
[`measure_static_recipe.py`](../../experiments/affine_xf/measure_static_recipe.py).

## Rank-2 static providers in current Bend

[`rank2_static_provider.bend`](../../experiments/affine_xf/rank2_static_provider.bend)
indexes an affine `Xf` by a closed reducer provider `P`. Its only live field
is `configure`, with the dependent type: for **any** result type and
downstream reducer, consume the downstream initial configuration and return
the configuration required by `P` applied to that reducer. Thus the owned
offset and take limit are captured at construction, while the consumer is
chosen later. The same factory runs with `sum` and `count`, over List and
Range. The source loop is the existing static fold.

[`rank2_static_compose.bend`](../../experiments/affine_xf/rank2_static_compose.bend)
constructs shift and take values independently, then composes their provider
indices and owned configuration functions through one generic `compose`.
There is no stage-name case in that combinator. The checker rejects reusing
one resulting affine `Xf`. The typed variant in
[`rank2_static_typed.bend`](../../experiments/affine_xf/rank2_static_typed.bend)
composes a `U32 → Nat` map with `take`, showing that the representation is not
limited to same-type stages. All positive fixtures pass JS/native on upstream
and the isolated compiler; on the latter, emitted reducers vanish and there
is no generic callback handoff. Run
[`probe_rank2_static_provider.py`](../../experiments/affine_xf/probe_rank2_static_provider.py)
for the positive and expected-rejection gates.

This is a substantial feasibility result, but the call sites still repeat
`~P` (and the reducer and type witnesses). The composition call also repeats
its provider indices. A normal rank-2 `run` field cannot hide this: the
checker correctly rejects its attempt to use a runtime-erased `R` as closed
template syntax. Dynamic selection between different stage compositions,
runtime mapping functions, and implicit source/destination lookup remain
open. The separate `configure` field is the stage's source of truth in this
model; an ordinary reducer transformer is needed only as a semantic control
during migration, avoiding permanent duplicate stage definitions.

## Next compiler experiment

Prototype **implicit template-argument inference** on an isolated copy of
`bendlang/main`. Start with a generic call whose first affine argument has
type `Xf<A, B, P>` and infer the closed `A`, `B`, and `P` template arguments
by matching the parameter type against that argument's checked type. Do not
recognize `Xf` by name: the rule should match ordinary parameterized types
and fail explicitly when the solution is ambiguous, open, or not closed.
Initially leave the reducer as an explicit closed `~down` and the source
adapter explicit. This makes the inference proof independent of static
reducer alias resolution and protocol lookup. If that passes, infer the
downstream reducer from a closed call-site expression, then handle inert
local aliases and the desired `transduce(xf, rf, init, coll)` spelling.

The rule must preserve one evaluation of each runtime argument and one
consumption of `xf`; typecheck the specialized body normally; bound and cache
instances; and reject runtime-varying code indices. Test stage composition,
type-changing map, List/Range/custom adapters, early stop, completion,
JS/native, allocation slope, compile time, and generated size. Finally add
source/destination protocol selection and make `into` delegate to this same
transduce core. Keep the current explicit-template library path as a
performance and correctness control throughout.
