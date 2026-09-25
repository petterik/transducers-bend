---
created_at: 2026-09-25T12:38:00+02:00
updated_at: 2026-09-25T12:53:00+02:00
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

This is an API and compiler feasibility result, with one generic execution
core for List, Range, and an independent source adapter. Raw custom
collections still require an explicit source witness, and raw custom
destinations require a destination witness. The typed `Rf` wrapper has not
been shown to express every desirable reducer.

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
passes eight positive fixtures on JS and native and checks emitted code shape.
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
result type. Timing for the exact call spelling is reported below. Code shape
alone is not a timing claim.

## Generic source and destination contracts

The same inference rule removes explicit type/provider arguments from
`compose(xf, xg)`. The List `into(dest, xf, coll)` prototype delegates to the
same transduce core with a prepending reducer: a nonempty destination
preserves its tail, a type-changing stage works, and `take(0)` leaves it
untouched. These cases pass on JS and native in
[`rank2_auto_api.bend`](../../experiments/affine_xf/rank2_auto_api.bend).

[`rank2_sources.bend`](../../experiments/affine_xf/rank2_sources.bend)
defines `Source<A,X,Drive>`. Its closed `Drive` index accepts any reducer and
folds owned `X` while preserving `Control`; the live field owns that `X`.
There is one `transduce_from(xf, rf, init, source)` core. The List
`transduce(xf, rf, init, xs)` entry point wraps its source and delegates to
that core. [`rank2_auto_sources.bend`](../../experiments/affine_xf/rank2_auto_sources.bend)
adds a two-element source without touching compiler or library source cases,
and uses Range through the same core. A type-changing `Xf` works with the
custom source. `Destination<B,D,Q>` owns an existing destination and its
insertion consumer; `into_from(dest, xf, source)` calls `transduce_from`.
List `into(dest, xf, xs)` wraps both ends and delegates. The independent Bag
destination confirms that completion runs once after both one-item and
initially stopped reductions. JS and native agree, and emitted JS has no
runtime `Reducer` record.

Raw `transduce(xf, rf, init, custom_coll)` and
`into(custom_dest, xf, custom_coll)` remain unsolved. A raw `X` type alone does
not carry a closed `Drive` provider; choosing one requires an implicit
instance rule or a source witness. Likewise, an arbitrary destination type
does not identify its insertion consumer. The explicit witnesses prove the
protocol boundary without claiming that implicit lookup already exists.

## Matched performance experiment

[`auto_api_bench.bend`](../../experiments/affine_xf/auto_api_bench.bend)
prebuilds a List, then times the same sum of a custom shift followed by
`take`. It compares a direct loop, the existing closed transducer recipe, the
prior explicit rank-2 representation, the inferred List API, and the generic
source API. [`measure_auto_api.py`](../../experiments/affine_xf/measure_auto_api.py)
compiles one C program with Clang `-O3`, randomizes lane order per session,
checks answers independently, and counts timed heap requests in a separate
instrumented build. The clock reports microseconds. Stored runs are
[`200k`](../../experiments/affine_xf/auto-api-200k-results.json),
[`2m`](../../experiments/affine_xf/auto-api-2m-results.json), and a
[`2m repeat`](../../experiments/affine_xf/auto-api-2m-confirm-results.json).

| Items / sessions | Direct median | Current static | Explicit rank-2 | API List | API source | API List / current paired median [bootstrap 95%] | Timed heap requests: current / API |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 200k / 24 | 191.5µs | 233µs | 221µs | 215.5µs | 216µs | 0.961 [0.868, 1.044] | 9 / 14 |
| 2m / 24 | 3466.5µs | 2017.5µs | 2173µs | 2532µs | 2343.5µs | 1.191 [1.084, 1.339] | 9 / 14 |
| 2m / 48 | 3296µs | 2187.5µs | 2202µs | 2317.5µs | 2268.5µs | 1.038 [0.950, 1.155] | 9 / 14 |

All API lanes have the prior rank-2 representation's five extra fixed heap
requests and no per-item allocation slope at either input size. The two 2m
runs disagree materially about timing, despite paired randomized lanes. The
current evidence does **not** establish the planned ≤1.05 upper confidence
bound against the existing static path or handwritten code. It does show
that the inferred API avoided the ordinary composed reducer's large
per-item allocation cost. The combined benchmark generated 147,648 bytes of
C and took about 0.15 seconds for Bend code generation plus 0.24 seconds for
Clang in these runs; these absolute figures are not a controlled code-size or
compile-time comparison to a smaller API.

The diagnostic build of the same candidate emits three specialized List
loops for the current recipe, API List, and API source. Each loop has a flat
call to `map_with_step` and a direct recursive jump; none has a closure call
in its emitted loop segment. Inspection of the generated C shows the same
List match, stop check, element step, and tail iteration structure in all
three. This makes an extra *dynamic callback* in the API loop unlikely. It
does not establish identical optimized machine code or explain the observed
timing spread. Reproduce this inspection by building the candidate with
`prepare_infer_candidate.py --diagnostics` and compiling
`auto_api_bench.bend` with `BEND_CALLSITE_REPORT` set to an output JSON path.

## Decision after this prototype

The representation and generic source/destination contracts pass the semantic
and allocation feasibility gates. Keep them experimental. Before adopting the
compiler rule, compare optimized machine code and rerun a more stable timing
experiment to distinguish code-placement effects from workload noise.
Then specify a small, coherent implicit instance mechanism for raw custom
sources and destinations, including ambiguity and coherence rules. Avoid a
collection-name registry in the compiler. The template-inference feature also
needs a checker-side-effect review and a broader conformance suite before
upstreaming.

The compiler feature is promising because a small, name-independent rule
turns independently built affine values into closed specialized code.
Reproduce the current result with:

```sh
python3 experiments/affine_xf/prepare_infer_candidate.py \
  --output-dir /tmp/transduce-auto-candidate
python3 experiments/affine_xf/probe_auto_inference.py \
  --bend-main /tmp/transduce-auto-candidate/main.ts
python3 tests/run.py --bend-main /tmp/transduce-auto-candidate/main.ts
```
