---
created_at: 2026-09-25T10:26:47+02:00
status: planned
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
2. **Prototype the representation.** Try a consuming reducer transformer
   with `map` and `take(runtime_n)`, including a type-changing map. If Bend's
   current higher-order/template rules leave a per-item runtime closure or
   prevent extensible composition, try a closed static recipe plus owned
   runtime settings. Record the exact compiler/type boundary; do not add a
   special case for either transducer name.
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
