---
created_at: 2026-09-25T13:41:00+02:00
updated_at: 2026-09-25T13:44:00+02:00
status: experimental
---

# Generic-stage performance and template-inference hardening

The isolated candidate still runs on bendlang/main `2f50df1e`. Generic stage
constructors use its name-independent template inference and static callback
specialization; neither compiler pass recognizes transducer functions.

The first confidence pass found an error-handling flaw in the inference
prototype. It called `term_infer` speculatively on each runtime argument and
caught every checker error as though the argument simply needed an expected
type. An inferable application can instantiate templates and mutate the
checked book before it fails. Swallowing that failure could hide the actual
error and leave partial compiler state. The pass now skips only syntax forms
that the checker explicitly cannot infer without a goal (such as a lambda,
constructor, or bare literal). Errors from inferable terms propagate. The
new [`auto_bad_stage_callback_rejected.bend`](../../experiments/affine_xf/auto_bad_stage_callback_rejected.bend)
probe previously reported a generic `~?AUTO` mismatch for a `+x` callback;
it now reports the actual `@+x` versus affine `@_` function-type mismatch.
All ten positive fixtures pass in JS/native, nine expected checker refusals
pass, and the full suite passes 33/33. This narrows one side-effect hazard;
it is not a complete proof that all speculative inference is safe. A fuller
compiler review should inspect successful speculative instantiations and
failure rollback before upstreaming the rule.

The benchmark now has a generic-stage lane using
`comp2(map_with(...), take(...))` alongside the equivalent old convenience
stages, static recipe, and direct Bend loop. It prebuilds the same two-million
item List, times the same sum, randomizes lane order, uses Clang `-O3`, and
checks answers and timed allocation counts. Raw runs are
[`24 sessions`](../../experiments/affine_xf/auto-api-generic-2m-results.json)
and [`48 clean sessions`](../../experiments/affine_xf/auto-api-generic-2m-clean-results.json).

| Run | Generic stage median | Current static median | Paired generic/static median | 95% bootstrap interval | Timed heap calls, generic/static |
| --- | ---: | ---: | ---: | ---: | ---: |
| 24 sessions | 2259 µs | 2274 µs | 1.067 | 0.942–1.231 | 14 / 9 |
| 48 clean sessions | 2293.5 µs | 2140.5 µs | 1.041 | 0.985–1.138 | 14 / 9 |

The generic stages have the same fixed five additional timed allocation
requests as the earlier affine API and no per-element allocation slope.
Their native timing is encouraging but variable; neither run establishes a
strict five-percent parity bound. The observed direct-loop lane happened to
be slower than both static lanes in these runs, which is a property of this
workload and generated code, not a general transducer speed claim.

## Source and destination boundary

The independent pair source and Bag destination still work through
`Source<A,X,Drive>` and `Destination<B,D,Q>` witnesses. The pair probe now
uses the new generic `map` constructor, so this is not a special-case
`mapped()` path. The adapters are ordinary existing Bend companion
definitions, `SamplePair.source` and `Bag.destination`; no new syntax was
needed to define them. These witnesses give a coherent, explicit contract today:
one value owns the collection, while its type carries closed fold or
insertion code. They do not deliver the desired raw
`transduce(xf, rf, init, custom_coll)` or `into(custom_dest, xf, coll)`
spelling. Raw `X` does not identify its `Drive`, and raw `D` does not identify
its insertion reducer.

There are three plausible next choices:

1. Keep explicit witnesses for custom collections. This is simple and
   already correct, but callers write an adapter at each use.
2. Add a type-directed instance mechanism. A promising minimal convention is
   a checked companion `X.source(x)` and `D.destination(d)` owned by each
   nominal collection type. From a checked raw argument type, elaboration
   would select that one companion, verify its `Source` or `Destination`
   result type, and call the current explicit witness core. It must reject a
   missing or ambiguous companion, never guess an element type from a stage,
   and retain explicit witnesses for alternate element views. List and other
   built-ins would need their canonical companions in the language library.
   This reaches the desired four-argument API, but requires a general
   type-directed elaboration rule and module-ownership/coherence review.
3. Give collection names special treatment in the compiler. This is locally
   quick but does not scale to independent user types and would obscure the
   optimization boundary.

The recommended next design step is option 2, with option 1 as the working
API until its rules are specified and tested. Do not add a collection-name
registry. Keep List `transduce`/`into` as convenient specializations for now;
their implementations already delegate to the generic witness core. The
compiler prototype should remain isolated until its inference side effects,
error behavior, and performance are reviewed independently of the library.
