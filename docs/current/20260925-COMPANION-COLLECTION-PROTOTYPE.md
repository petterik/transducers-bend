---
created_at: 2026-09-25T14:12:00+02:00
updated_at: 2026-09-25T14:53:00+02:00
status: experimental
---

# Type-directed collection adapter prototype

An isolated compiler candidate now demonstrates one spelling for both List
and an independent custom source:

```python
Auto.transduce(xf, rf, init, coll)
Auto.into(dest, xf, coll)
```

The [`rank2_companion_api.bend`](../../experiments/affine_xf/rank2_companion_api.bend)
functions are ordinary wrappers around the existing witness-based core.
They expect `Source<A,X,Drive>` and `Destination<B,D,Q>` values. When a caller
supplies a raw owned collection, the candidate first infers its checked
nominal type, then inserts a companion call whose result is checked against
that expected witness type. The selected method is the sole method with the
expected name owned by the collection's defining module, such as
`SamplePair.source` or `Bag.destination`. There is no collection-name table
and no search through arbitrary imported functions. An extension with the
same simple method name in another module is ignored.

The target protocol opts in by defining `Source.allow_companion() -> Unit` or
`Destination.allow_companion() -> Unit`; the isolated compiler checks this
exact zero-argument signature. For a nominal type owned by Base, whose module
cannot import the transducer protocol, the protocol's own module may define
one canonical extension such as `rank2_sources.List.source` or
`rank2_rf_values.List.destination`. The source method may itself have erased
template parameters, inferred from the raw List's checked type. This is a
general rule: an unrelated marked `Wrapped` type and `Raw.wrapped` method
pass the same JS/native probe; an unmarked or malformed target marker is
rejected.

The [`rank2_companion_raw.bend`](../../experiments/affine_xf/rank2_companion_raw.bend)
probe passes raw List and `SamplePair` values through `Auto.transduce`, a
raw List destination and source through `Auto.into`, and a raw Pair into a
custom Bag. It includes a type-changing `U32 -> Nat` stage, completion of
the Bag once, and inferable function-call arguments such as `make_list()`.
JS and native agree; emitted JS has no runtime `Reducer` record. Six negative
fixtures reject a missing method, wrong return type, repeated affine input,
orphan method, absent opt-in marker, and malformed marker. The prior AUTO
suite still passes ten positive fixtures in JS/native and nine refusals;
the full suite passes 33/33.

The native List benchmark compares the same shift/take calculation in the
existing inferred List API and the companion-selected entry point. Its two
48-session, two-million-item runs are stored as
[`first`](../../experiments/affine_xf/companion-api-2m-results.json) and
[`repeat`](../../experiments/affine_xf/companion-api-2m-confirm-results.json).

| Run | Paired companion / existing List median | 95% bootstrap interval | Timed heap requests: both |
| --- | ---: | ---: | ---: |
| First | 0.995 | 0.932–1.003 | 14 |
| Repeat | 0.998 | 0.967–1.000 | 14 |

These runs show no extra timed allocations and no measurable slowdown from
adapter selection on this List workload. The other lanes vary enough across
runs that this is not a blanket performance result for every source.

## Limits and integration decision

This prototype converts inferable live values and calls. A bare constructor
such as `[]` or `SamplePair{1, 2}` still needs a typed binding or factory
call before it can be used in the raw position; contextual literal inference
is a separate problem. The prototype API lives in `Auto` to keep the prior
List entry points and their benchmark fixtures reproducible. A production
library could expose these same functions as its public `transduce` and
`into` once the elaboration rule is settled.

The Base extension rule covers List. A non-Base library type such as the
current `T.Range` cannot define an owner method returning `Source` while
`Source` lives in a module that imports `T`: that would form an import cycle.
The clean integration is to move the generic source contract into the
transducer core, then define `Range.source` beside Range and `List.source`
there. For third-party types whose owner module cannot be edited, keep the
explicit witness API; adding an orphan-instance registry would require
separate coherence rules.

The isolated compiler rule is promising but **not ready for bendlang/main**.
It needs a checker-side-effect audit, contextual-literal design, compile-time
cost measurement, and tests for nested generic calls and module boundaries.
The opt-in and method naming conventions also need language-level review
before they become public semantics. No change was made to `../bend`.

While testing, we found an independent bendlang/main JS display bug:
[`imported_bag_show_probe.bend`](../../experiments/affine_xf/imported_bag_show_probe.bend)
computes an imported `Bag` value, but JS hangs when printing that nominal
result; native prints it correctly. It reproduces on the compiler without
companion conversion. The conversion probe returns a scalar summary of its
Bag so JS/native execution can be checked separately from that printer bug.
The bug no longer reproduces on bendlang/main `3276efac`: JS and native both
print `rank2_auto_sources.Bag{[9], 1}` in the same probe. It was independent
of the companion implementation.
