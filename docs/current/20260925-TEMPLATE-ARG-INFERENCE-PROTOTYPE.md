---
created_at: 2026-09-25T12:38:00+02:00
updated_at: 2026-09-25T12:44:00+02:00
status: experimental
---

# Closed template arguments inferred from affine values

## Result

An isolated compiler candidate accepts a List call shaped exactly like
`transduce(xf, rf, init, coll)`. The `xf` and `rf` arguments are independently
constructed, single-use values. Their checked types carry the closed reducer
provider and consumer code, while their live fields carry owned runtime
configuration. The compiler infers six omitted template arguments, then runs
the ordinary checker and specialization path. JS and native return the same
independent results, and the emitted static fold has neither a runtime
`Reducer` record nor a per-item callback handoff.

This is an API and compiler feasibility result for **List**. It does not yet
select a source adapter from an arbitrary collection type, define `into`, or
prove that every reducer can be expressed with the typed `Rf` wrapper.

## Mechanism

[`prepare_infer_candidate.py`](../../experiments/affine_xf/prepare_infer_candidate.py)
builds an isolated candidate from the pinned `bendlang/main` compiler plus
the existing static-callback experiment. It adds one generic parser/checker
rule. An omitted trailing `~` argument becomes `~?AUTO`. The checker compares
the parameter type with the checked type of a runtime argument and solves a
hole only when it occurs structurally in matching parameterized types. It
continues through arguments until every hole is solved. It then checks the
inferred terms in the original empty template context, instantiates the
definition, and checks the runtime call normally.

The rule contains no `Xf`, `Rf`, transducer, reducer, or collection name.
[`auto_unrelated_type.bend`](../../experiments/affine_xf/auto_unrelated_type.bend)
uses it on an unrelated user-defined generic type. An internal hole is
identified by node identity, so user-written holes with similar text cannot
masquerade as inference variables. Matching has a 512-step bound; ordinary
template depth and key-size bounds still apply.

[`rank2_rf_values.bend`](../../experiments/affine_xf/rank2_rf_values.bend)
defines the prototype API. `Rf<B,R,Q,Init>` owns a live `prepare` function and
indexes closed reducer code `Q`; it consumes `init` once to construct `Q`'s
configuration. `Xf<A,B,P>` similarly owns a live configuration function and
indexes a consumer-polymorphic, closed reducer provider `P`. At the call to
`transduce`, the checked `Xf` type determines `A,B,P`, and the checked `Rf`
type determines `R,Q,Init`. The source fold sees the composed closed reducer
`P(R,Q)`. [`rank2_auto_rf.bend`](../../experiments/affine_xf/rank2_auto_rf.bend)
exercises both a custom offset stage with `take` and a type-changing stage,
using sum and count consumers.

## Confidence gates

[`probe_auto_inference.py`](../../experiments/affine_xf/probe_auto_inference.py)
passes seven positive fixtures on JS and native and checks emitted code shape.
It also confirms expected rejection for ambiguous inference, an open provider,
an incompatible consumer input type, an incompatible `into` destination,
and attempted reuse of affine `xf` or `rf` values. Partial and fully omitted
template argument lists both work.
The unrelated generic-type fixture guards against a transducer-specific
implementation. The repository's full 33-case JS/native/code-shape suite also
passes against this candidate.

Type discovery checks an argument to learn its type, but does not emit or
evaluate that argument. The ordinary call check still accounts for affine
usage and checks each runtime argument against the specialized parameter
type. The test suite and reuse rejections support this ownership claim; a
production implementation would need an explicit compiler review of checker
side effects and instance caching before upstreaming.

The rule defers a runtime argument whose type cannot synthesize, such as a
leading `[9]` in `into([9], xf, coll)`. Once later arguments solve the holes,
the ordinary call check validates that earlier argument at its expected
type. This permits Clojure-order `into` without guessing a list element type.
An incompatible destination element is still rejected. The rule refuses
non-structural equations, mismatched generic constructors, open inferred
terms, and cases where no later argument uniquely determines every hole.
These are safe incompleteness, not a fallback to runtime dispatch. It does
not attempt higher-order unification or infer arbitrary user code from a
result type. There is no measured timing for this exact call spelling yet;
the previous rank-2 static-provider benchmark is the performance control,
and code shape alone is not a timing claim.

## Remaining work and decision

The same rule now removes explicit type/provider arguments from composition.
The List `into(dest, xf, coll)` prototype delegates to `transduce` with a
prepending reducer: a nonempty destination preserves its tail, a type-changing
stage works, and `take(0)` leaves it untouched. These cases pass on JS and
native in [`rank2_auto_api.bend`](../../experiments/affine_xf/rank2_auto_api.bend).
Next exercise Range and an independent source adapter, plus a custom
destination. Check stop and
completion semantics and compare timing, allocations, compile time, and code
size against the explicit-template path. Implicit lookup for raw custom
collection types is a separate language-design question; this prototype
should use explicit protocol witnesses internally until that boundary is
proved.

The compiler feature is promising because a small, name-independent rule
turns independently built affine values into closed specialized code. It
should remain isolated until the broader API, semantics, and performance
gates pass. Reproduce the current result with:

```sh
python3 experiments/affine_xf/prepare_infer_candidate.py \
  --output-dir /tmp/transduce-auto-candidate
python3 experiments/affine_xf/probe_auto_inference.py \
  --bend-main /tmp/transduce-auto-candidate/main.ts
python3 tests/run.py --bend-main /tmp/transduce-auto-candidate/main.ts
```
