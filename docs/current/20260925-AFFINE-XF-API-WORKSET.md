---
created_at: 2026-09-25T10:26:47+02:00
updated_at: 2026-09-25T11:40:00+02:00
status: active
---

# Affine transducer API workset

## Goal and boundary

Make the public API approach Clojure's `transduce(xf, rf, init, coll)` and
`into(dest, xf, coll)` while preserving Bend's affine ownership, correct
stopping/completion, support for custom sources and destinations, and the
measured speed of the current statically specialized transducer path.
These calls are target API sketches, not syntax the current library already
supports. This workset tests the representation before committing to a Bend
language feature or replacing the current library API.

Only `bendlang/bend:main` is a compiler target. Compiler experiments remain
isolated from the sibling upstream checkout until their correctness and
performance gates pass. The current static-callback candidate and handwritten
Bend loops are the performance controls.

## Decisions already made

- An `Xf` value is affine: one call to `transduce` or `into` consumes it. A
  top-level factory `def` can create a fresh value for each run. An ordinary
  zero-argument lambda value is itself affine and is not a reusable factory.
- Constructing an `Xf` captures stage code and runtime settings such as
  `take(n)`; it does not start a reduction or allocate a partition buffer.
  The run starts stage state after the downstream reducer is initialized.
- A source is reduced in its defined order. The source and destination are
  chosen by their protocols, not by transducer-specific compiler names.
- `transduce(xf, rf, init, coll)` is the core eager operation. It calls
  completion exactly once, including after early stop. Ordinary binary
  reducing functions get identity completion; a full reducer may define a
  different completion.
- `into(dest, xf, coll)` delegates to `transduce`, supplying the destination's
  insertion reducer and `dest` as the initial value. List insertion prepends,
  following Clojure's collection-specific ordering; `into([], map(inc),
  [1, 2, 3])` yields `[4, 3, 2]`. There is no implicit List reversal.
- `partition_all` remains a useful chunk-producing operation even when
  materializing its output is measurably slower than a specialized fold.
  Perfect parity with a loop that never constructs observable chunks is not
  a prerequisite for this API.

## Priorities

Effort measures semantic complexity, proof burden, API commitments, and
maintenance. It does not estimate typing time or lines of code.

| Order | Work | Impact | Effort | Value now |
| --- | --- | --- | --- | --- |
| P0 | Specify `Xf`, reducer, source, and destination lifecycles | High: prevents state leakage and ambiguous completion | Medium | Very high |
| P0 | Prototype a single-use `Xf` carrying static stage code and runtime settings | Critical: decides whether the API preserves the fast path | High: higher-order typing and specialization | Highest |
| P0 | Prove call-site specialization of affine `xf` and `rf` values | Critical: current Bend rejects the proposed ordinary-value call shape | High: checked identities, runtime captures, and ownership | Highest |
| P0 | Make `into` call one `transduce` core, using explicit protocol witnesses internally | High: tests both custom ends without duplicating execution logic | Medium | Very high |
| P0 | Verify semantics, generated code, allocations, and matched timing | Critical: catches an elegant but expensive abstraction | Medium | Highest |
| P1 | Design implicit source/destination instance lookup for the exact public spelling | Critical for raw custom collections | High: language and compiler rules | High after the P0 prototype |
| Later | Improve `partition_all` fusion, add an Array builder, or implement `sequence`/pipeline syntax | Useful breadth or ergonomics | High and independent of this API proof | Lower now |

## Work sequence

1. **Write the executable contract.** Define `Xf<A, B>` as a single-use
   transformation from downstream reduction over `B` to source reduction over
   `A`, allowing zero, one, or many downstream steps per source item. Specify
   runtime configuration, initialization, `Continue`/`Stop`, and completion.
   Preserve the current rule that a stopped downstream reducer receives no
   more inputs. Distinguish an unstarted `Xf` from the active state it creates
   inside one run.
2. **Prototype the representation and call boundary.** Try a consuming reducer
   transformer with `map` and `take(runtime_n)`, including a type-changing map.
   The first probe below shows that an ordinary `xf` or `rf` parameter cannot
   simply enter the current closed-template driver. Test a name-independent
   call-site specialization that makes statically known affine code available
   to that driver while binding runtime settings once. If this is not sound
   or bounded, try a closed static recipe plus owned runtime settings and
   identify the language sugar needed for the target spelling. Do not add a
   compiler case for `map` or `take` by name.
3. **Exercise both protocols.** Use List and range plus one independently
   written source. Use List plus one independently written destination.
   Explicit source/destination witnesses are acceptable inside this prototype.
   Implement `into` as a call to the same `transduce` entry point, not a
   second driver. Confirm List's prepend order with a nonempty destination.
4. **Try to break the lifecycle.** Cover empty input, initial and downstream
   stopping, `take` with a runtime limit, completion exactly once, a partial
   `partition_all` chunk, an affine element, and an `Xf` factory called twice
   with no state shared between runs. A test must reject trying to use one
   stored `Xf` twice. Constructing an unused `Xf` must not start source or
   stage work.
5. **Measure against controls.** On the pinned `bendlang/main` snapshot,
   compare the new List pipeline with the existing static-recipe transducer
   and equivalent handwritten Bend. Use the microsecond clock, paired native
   runs, independent output checks, and separately instrumented allocation
   builds. Inspect emitted JS/C for dynamic reducer records and per-item
   closures. Record compile time and generated-code size as well as runtime.
6. **Decide the language boundary.** If the explicit-protocol prototype is
   sound and fast, specify the smallest compile-time instance mechanism that
   selects source reduction and destination insertion from raw collection
   types, including custom types. If the prototype regresses, isolate whether
   `Xf`, source dispatch, or destination dispatch causes it before adding
   implicit lookup or changing the public API.

## Acceptance and stop conditions

The workset succeeds as an API feasibility proof when List, range, and custom
source tests agree with independent results on JS/native; both destinations
receive the right order; all stopping and completion tests pass; and the new
stateless List path has no per-item allocation introduced by the API. Its
native timing target is the existing transducer goal: the upper 95% ratio to
equivalent handwritten Bend is at most 1.05 on the matched stateless workload.
The `partition_all` case is a semantic gate, not a direct-loop timing gate.

If a first-class `Xf` fails these gates, keep the measured current API intact
and document the failing boundary. A static recipe or a small language feature
may still deliver the desired public spelling, but its own generated code and
ownership behavior must be measured before adoption. Do not add a fixed
registry of collection names: custom source and destination implementations
are part of the objective.

This workset should end with the prototype, semantic and performance report,
the recommended compiler/language boundary, and a clear go/no-go decision for
the exact public API. It does not require implementing implicit instance
resolution, a growable Array destination, `sequence`, or new pipeline syntax.

## First feasibility checkpoint — 2026-09-25

The reproducible probe lives in
[`experiments/affine_xf`](../../experiments/affine_xf). It was run against
the local `bendlang/main` checkout at `2f50df1ed36fcc3ebe6c75a2046e94001a44645d`
and the isolated static-callback candidate built from the same commit.

The type-polymorphic `Xf<A, B>` can be expressed as a value holding an
`@-R: Type -> Reducer<B, R> -> Reducer<A, R>` function. A `map` implementation
can consume a downstream reducer, unpack its three callbacks, and build a new
reducer. When that entire application is supplied as *closed template syntax*
to the existing List driver, both JS and native return the independent result
`9`; the static-callback candidate emits no JS `Xf` or `Reducer` records.
This is a positive result for a static representation, not yet for the target
ordinary-value API.

Two negative fixtures locate the missing feature. A normal `xf` parameter
cannot be supplied inside the driver's `~` argument: Bend reports that `xf`
is a variable, not compile-time syntax. A normal reducing-function parameter
cannot be called and passed along the recursive List tail: Bend reports that
`rf` is consumed more than once. These are type/checker boundaries, not
performance observations. The proposed public spelling therefore needs a
general way to specialize known affine `xf` and `rf` arguments at a call site,
or a language-level surface that resolves them to closed code while carrying
runtime settings separately. Implicit source/destination selection alone
would not solve this.

Reproduce with:

```sh
python3 experiments/affine_xf/probe.py \
  --bend-main /tmp/transduce-affine-xf-static/main.ts \
  --expect-static-erasure
python3 experiments/affine_xf/probe.py \
  --bend-main ../bend/bend2/main.ts
```

The next narrow compiler test is call-site specialization on a statically
known affine `rf` in a simple fold, then on a known `xf` value with one runtime
setting. It must preserve one evaluation of captures, support a custom
producer, reject unknown/dynamic heads, and stay under a fixed expansion
budget. Only after this boundary passes should the broader `into`/source/
destination slice be implemented.

## Second feasibility checkpoint — 2026-09-25

The isolated [`prepare_alias_candidate.py`](../../experiments/affine_xf/prepare_alias_candidate.py)
adds one bounded checker experiment to the same static-callback compiler: at
an explicit `~` call, it resolves a local alias only if its initializer is an
inert syntactic value (a reference, lambda, literal, or constructor of such
values). It then checks the resolved argument in Bend's usual empty template
context. A call used to construct the alias is deliberately refused: dropping
the now-unused local could otherwise skip an unsafe or diverging computation.
Unknown parameters and closures that capture runtime values are also refused.

[`probe_alias.py`](../../experiments/affine_xf/probe_alias.py) passes on JS and
native: a locally named `rf` folds to `6`; a locally constructed `Xf` maps and
sums to `9` with no emitted JS `Xf` or `Reducer` records; a `take` recipe with a
runtime `Nat` limit returns `5`; and an independent two-element source adapter
returns `5`. Five negative cases retain the expected checker refusals,
including an ordinary `rf` parameter, ordinary `xf` parameter, runtime
capture, unknown template head, and computed `xf` alias. The candidate starts
from `bendlang/main` at `2f50df1e`; no sibling checkout was changed. Rebuild
and run it with:

```sh
python3 experiments/affine_xf/prepare_alias_candidate.py \
  --output-dir /tmp/affine-alias-candidate
python3 experiments/affine_xf/probe_alias.py \
  --bend-main /tmp/affine-alias-candidate/main.ts
```

This is a narrow positive result for *static aliases*, not the requested
`transduce(xf, rf, init, coll)` API. The successful `Xf` has no runtime capture;
the runtime `take` limit is deliberately supplied separately as reducer
configuration. The ordinary value-parameter cases still fail, and no timing or
allocation comparison has been made for this candidate. The next decision is
whether to implement a general, ownership-preserving partial specialization
of a known `Xf` constructor that retains its runtime configuration exactly
once, or make static recipe plus owned configuration the explicit language
boundary. The current alias rule alone cannot settle that choice.

## Third feasibility checkpoint — 2026-09-25

The independent [`type_indexed_plan.bend`](../../experiments/affine_xf/type_indexed_plan.bend)
stores a closed map function as an erased type index and a runtime `Nat` limit
as the owned `Plan` value. It runs on unmodified `bendlang/main` and the
static-callback candidate, returning `5` on JS/native. The static-callback
candidate emits no runtime `Reducer` record for this small example. This
demonstrates a plausible *code in the type, settings in the value* split, but
the `run` call must repeat `~f` explicitly; Bend does not infer a template
argument from `Plan<f>` for the target public spelling.

The [`rank2_type_indexed_plan.bend`](../../experiments/affine_xf/rank2_type_indexed_plan.bend)
probe tries the same split for a general reducer-transforming function. Both
compiler builds reject it at `Config`: the type checker cannot reduce the
dependent configuration type through an opaque template code index, so it
cannot establish that `0` is the downstream configuration. This is a failed
*construction strategy*, not a proof that type-indexed transducers are
impossible. In fact,
[`rank2_config_plan.bend`](../../experiments/affine_xf/rank2_config_plan.bend)
works on JS/native when the plan stores its downstream configuration at the
dependent `Config` type. The static-callback candidate again erases runtime
`Reducer` records. That plan is tied to the chosen `sum` consumer, however,
whereas the desired `Xf` must be constructed independently of any consumer.
It also repeats its closed code at `run`.

These results make the next type-design question concrete: how can an `Xf`
carry only its own runtime settings while exposing enough *static* information
about the configuration/state transformation for an arbitrary downstream
reducer? Explicit configuration/state type witnesses, a different reducer
signature, or a more capable specialization mechanism may answer it. Reproduce
these probes with:

```sh
python3 experiments/affine_xf/probe_type_index.py \
  --bend-main ../bend/bend2/main.ts
python3 experiments/affine_xf/probe_type_index.py \
  --bend-main /tmp/affine-alias-candidate/main.ts \
  --expect-static-erasure
```

**Decision at this checkpoint:** keep the measured template-based library path intact.
Neither local-alias substitution nor the type-indexed plans prove the
ordinary-value API or consumer-independent rank-2 composition. The next
experiment should make reducer configuration and state types explicit in the static recipe's
signature, then test whether one owned `Xf` value can hold runtime settings
without repeating stage code at the call site. If that requires arbitrary
whole-program specialization, prefer a small language elaboration rule that
separates static code from owned settings rather than adding transducer-name
cases to the compiler. Semantic and performance gates from this workset still
apply before adopting any new API.

## Fourth feasibility checkpoint — 2026-09-25

[`explicit_reducer_types.bend`](../../experiments/affine_xf/explicit_reducer_types.bend)
makes a reducer's configuration `C` and state `S` explicit type parameters.
Its owned `Xf<A, B, f>` carries a runtime `take` limit, while the map function
`f` is an erased type index. The `Xf` is constructed before choosing the
downstream reducer. The same driver works with sum, List prepend into a
nonempty destination (`[3, 2, 9]`), and a type-changing `U32 -> Nat` map.
Zero limit, empty input, and initial downstream stop also agree on JS/native
on upstream and the isolated compiler. Reusing one owned `Xf` is rejected.

The exact callback projection matters. When `step2` took a reducer *and an
item* and returned the resulting control, emitted JS constructed an `R2`
record in the per-item path. Changing it to return the reducer's step
*function*, then applying that function, lets the existing static-callback
pass erase every `R2` record. Upstream still emits two `R2` constructor sites;
the static candidate emits zero across all six positive examples. It emits one `Xf`
constructor at run setup, not in the item loop. Run the shape and correctness
gate with:

```sh
python3 experiments/affine_xf/probe_explicit_types.py \
  --bend-main /tmp/transduce-affine-xf-static/main.ts \
  --expect-static-erasure
```

The paired native benchmark
[`explicit_reducer_bench.bend`](../../experiments/affine_xf/explicit_reducer_bench.bend)
compares the explicit `Xf`, the current `T.take`/`T.map`, and a direct
map/take/sum loop, using the same prebuilt List and a runtime limit equal to
its length. The timer wraps only the fold. Separate instrumented builds count
heap allocations inside that region. Results against the plain static-callback
candidate are retained at
[`200k`](../../experiments/affine_xf/explicit-types-static-200k-results.json)
and [`2m`](../../experiments/affine_xf/explicit-types-static-2m-results.json):

| Inputs | Direct median | Current median | Explicit median | Explicit/current paired median [bootstrap 95%] | Timed heap calls, each |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 200,000 | 178µs | 201.5µs | 200µs | 1.000 [0.990, 1.005] | 9 |
| 2,000,000 | 3,497.5µs | 3,035µs | 2,323µs | 0.843 [0.696, 0.978] | 9 |

The explicit representation introduces no per-item heap requests in this
workload and is close to the current transducer. At 200k both transducer
paths trail the direct loop; at 2m both lead it.
These are workload-specific measurements, not proof of a general crossover.
The benchmark uses randomized paired mode order, 128 sessions at 200k and 32
at 2m, microsecond timing, and an independent arithmetic checksum. The stored
report now also includes the composed and staged variants described below.
For example, reproduce the larger run with:

```sh
python3 experiments/affine_xf/measure_explicit_types.py \
  --bend-main /tmp/transduce-affine-xf-static/main.ts \
  --items 2000000 --sessions 32 \
  --output /tmp/explicit-types-recheck.json
```

This experiment proves that explicit reducer types can clear the opaque
`Config` type-checking boundary and preserve the current fusion mechanism.
It does **not** provide a composable first-class `Xf` API: `run` still asks the
caller to repeat `~f` and name the downstream reducer and its type witnesses.
The next work is to design how stage composition carries those witnesses and
how the compiler infers closed static code from the consumed value's type at
the public `transduce(xf, rf, init, coll)` call. If that inference cannot be
specified generally and boundedly, retain the explicit static recipe/config
split as the honest API boundary rather than introducing a special compiler
path for transducer names.

## Fifth feasibility checkpoint — 2026-09-25

[`config_functor_probe.bend`](../../experiments/affine_xf/config_functor_probe.bend)
shows that an affine value can hold an owned runtime configuration function
while its type records how that function changes an arbitrary downstream
configuration type. Those type-level transformations compose. The larger
[`composable_xf_probe.bend`](../../experiments/affine_xf/composable_xf_probe.bend)
adds a state-type transformation and generic reducer code composition: a
separately constructed map and take compose into one owned `Xf`, then run with
sum. Upstream and the static-callback candidate return `5` on JS/native. The
candidate emits no `R2` reducer records. Reproduce with
[`probe_composable.py`](../../experiments/affine_xf/probe_composable.py).

That positive *typing and semantics* result fails the performance gate.
Adding the composed lane to the same benchmark gives the following matched
results on the static-callback candidate:

| Inputs | Composed median | Composed/current paired median [bootstrap 95%] | Timed heap calls, composed | Timed heap calls, current |
| ---: | ---: | ---: | ---: | ---: |
| 200,000 | 1,619µs | 7.967 [7.745, 8.110] | 400,013 | 9 |
| 2,000,000 | 16,925µs | 5.511 [5.354, 6.599] | 4,000,013 | 9 |

The generated JS makes the cause visible: its item loop creates a callback
closure for the ordinary `take_step` helper. The native allocation probe
independently finds about two extra heap requests per item. Eliminating the
`R2` wrapper therefore does not fuse the inner callback. This representation
cannot be adopted as the fast path as it stands, regardless of its attractive
type-level composition. The result does not refute composable first-class
transducers in general; it identifies the ordinary callback handoff as the
specific missing optimization.

The handoff is isolated in
[`callback_handoff.bend`](../../experiments/affine_xf/callback_handoff.bend): a
recursive loop supplies a known closure to an ordinary helper, and both
compiler builds emit that closure in the item loop. The next compiler
experiment should specialize a *checked helper definition* on the known
callback, then call the specialized helper with dynamic state and input. That
keeps a pattern match in a function body, where Bend already compiles it
directly. Merely inserting a match-valued function into the caller risks
emitting another closure for its application. The rule must be bounded and
name-independent, preserve one evaluation of captured runtime values, and
reject unknown heads. Only if it removes the measured per-item allocations
should it be tried on `take_step` and the composed `Xf`; then redo all semantic
and paired performance gates. If this cannot be made local and general, keep
composition in closed `~` recipes and evaluate language elaboration for the
desired public call separately.

## Sixth feasibility checkpoint — 2026-09-25

[`staged_value_elaboration.bend`](../../experiments/affine_xf/staged_value_elaboration.bend)
hand-elaborates the same composed affine value into two parts: it consumes the
value once to obtain its owned runtime configuration, then runs a closed
`T.map`/`T.take` reducer recipe through the existing static driver. JS/native
return `5`; emitted JS has no per-item callback closure. The matched native
benchmark finds:

| Inputs | Staged median | Staged/current paired median [bootstrap 95%] | Timed heap calls, staged | Timed heap calls, current |
| ---: | ---: | ---: | ---: | ---: |
| 200,000 | 200µs | 0.995 [0.973, 1.005] | 12 | 9 |
| 2,000,000 | 2,550µs | 0.831 [0.756, 0.943] | 12 | 9 |

The three extra allocations are a fixed cost of constructing and consuming
the composed configuration, not a cost per item. These timings support staged
values as an API representation, subject to broader source, stage, ownership,
and lifecycle checks. The exact public call still needs a way to infer and
assemble the *closed template recipe* from the consumed `Xf`; the hand-written
fixture repeats that recipe.

The same hand elaboration drives a `Range` through `T.over_range` in
[`staged_range_elaboration.bend`](../../experiments/affine_xf/staged_range_elaboration.bend).
It checks a partial take, zero take, empty range, and limit past the end on
JS/native. This supports source independence for the staged recipe, though it
does not solve automatic source protocol selection.

[`staged_generic_elaboration.bend`](../../experiments/affine_xf/staged_generic_elaboration.bend)
checks an important alternative: apply the composed type-indexed reducer code
directly inside closed `~` syntax, instead of spelling `T.map` and `T.take`.
It returns the correct value, but emitted JS still constructs a callback in
the item loop. Closed syntax alone does not turn an ordinary higher-order
reducer transformer into a static template transformer. A general API cannot
obtain the fast path merely by substituting the current `code` index.

The design choice is now sharper. Prefer a language-level representation of
*composable template code with owned runtime settings*, or a general
elaboration rule that can produce such code from a staged value. That rule
must let user-defined stages participate without naming `map`, `take`, or
particular source types in the compiler. A checked helper-cloning optimization
may still improve ordinary higher-order Bend code, but it is no longer a
prerequisite for testing this staged API path. Do not promote either probe to
the public library until generic composition and source/destination protocol
selection are expressible without hand-written recipe duplication.

## Seventh feasibility checkpoint — 2026-09-25

[`staged_custom_ends.bend`](../../experiments/affine_xf/staged_custom_ends.bend)
uses a source and a destination defined wholly outside `transduce.bend`. The
source is an ordered pair; the destination owns a nonempty List and prepends
insertions. Its completion increments a counter. The single `T.transduce`
core produces `[3, 2, 9]` with limit two, `[2, 9]` with limit one, and `[9]`
with limit zero; each result records exactly one completion. JS and native
agree on upstream and the static-callback candidate. Together with the Range
probe, this supports the source/destination *protocol* and lifecycle design.
It does not supply implicit protocol lookup or automatic stage elaboration.

Run the combined gate with:

```sh
python3 experiments/affine_xf/probe_composable.py \
  --bend-main ../bend/bend2/main.ts
python3 experiments/affine_xf/probe_composable.py \
  --bend-main /tmp/transduce-affine-xf-static/main.ts \
  --expect-static-erasure
```

The current result is a **no-go for exposing the exact four-argument API as
a fast general API today**. The owned configuration and independent ends work,
but the only generic composition we can currently express hands a callback
through `take_step` on each item: about two heap requests per item and
5.5–8 times the current transducer timing in the measured List workload.
Hand-staging the identical value into a closed `~` recipe restores the fast
loop, but every call repeats the recipe and its type witnesses. That is a
probe, not a usable public abstraction. The 200k staged path also misses the
workset's strict 1.05 upper-ratio target against the direct loop; the 2m
ranking reverses. Do not claim general direct-loop parity from these data.

The next language design should focus on a *static recipe representation*.
Its minimum contract is:

1. Constructing and composing stages builds an affine value containing only
   owned runtime settings; static stage code and type transformations live in
   erased metadata. A user-defined stage can provide the same metadata.
2. At `transduce(xf, rf, init, coll)`, consume `xf` once, extract settings
   once, and elaborate its static composition against the chosen downstream
   reducer into a closed reducer recipe. Elaboration must happen before the
   source loop, with a bounded expansion rule and ordinary type checking of
   the result. Stage names are library definitions, not compiler cases.
3. Separately select the source fold from `coll`'s type and insertion from
   `dest`'s type for `into(dest, xf, coll)`. Keep `into` a wrapper around the
   same `transduce` core. These two protocol lookups cannot substitute for
   step 2; they solve a different problem.

There are three credible next paths, in priority order:

| Path | Expected value | Cost and risk | Recommendation |
| --- | --- | --- | --- |
| Language-level composable static recipes, with explicit witnesses first | Makes the desired affine API and arbitrary stages possible while retaining the measured closed loop | New typing/elaboration rules; must specify erasure, expansion bounds, and code-size behavior | Prototype a tiny map/take language feature in an isolated compiler branch |
| Keep closed recipes plus owned configuration as the library API | Already correct and fast for the measured stages and sources | Repeats recipe and type witnesses; does not deliver the requested Clojure-like call | Keep as the working fallback and performance control |
| General checked-helper specialization for ordinary callbacks | Could speed this probe and unrelated higher-order Bend | Type specialization across erased state parameters, ownership, and code growth are unproved; helper cloning alone did not close the staged-code gap | Investigate independently only with a small, sound rule and a measured win |

Hard-coding `map`, `take`, or source names in the compiler would be a fourth
path, but it violates the extension goal and should not be pursued. The next
compiler probe must first show a *user-defined* stage composed with another
stage and elaborated without a per-item callback. Then validate a
type-changing map, completion and stopping, JS/native, allocation slope,
native timing, compile time, and code size. Until that proof exists, keep the
current library interface and compiler candidate unchanged.
