---
created_at: 2026-09-25T10:26:47+02:00
updated_at: 2026-09-25T10:36:52+02:00
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
