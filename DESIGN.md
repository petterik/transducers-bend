# transduce-bend

Status: proposed library design, grounded in small compilation experiments against Bend 2.0.16. The public Bend signatures and complete lifecycle implementation remain to be validated. No compiler or language changes are assumed.

## Purpose

Provide composable, pure data transformations that execute without intermediate collections between stages. Consumers can accumulate a scalar or build an output collection. Sources can be existing collections or producers that generate values as needed.

The performance target is an efficient direct traversal with comparable semantics, not a universal promise of zero allocation or zero unnecessary work. Preserve room for batching and parallel execution without committing to a chunk size.

The project lives independently of Bend. An awkward design should be revised here before requesting language features or modifying the compiler.

## User model

There are four parts:

- A source supplies input values.
- A transformation describes how inputs become outputs.
- A reducer consumes outputs into owned state and eventually returns a result.
- `transduce` coordinates initialization, traversal, stopping, and completion.

A pipeline's stages read in input-to-output order. Conceptual notation, not executable Bend syntax:

```text
pipeline = compose(map(increment), filter(greater_than(threshold)), take(count))
transduce(pipeline, sum, 0, source)
into_list(pipeline, source)
```

For input `[1, 2, 3, 4, 5]`, threshold `2`, and count `2`, these return `7` and `[3, 4]` respectively. `take` counts values reaching its position: filtering first takes the first matching values; taking first filters only the selected prefix.

`transduce` does not inherently collect a sequence. It feeds outputs directly into a reducer. `into_list` is a convenience over the same lifecycle, using prepend followed by one reversal to preserve order without repeated append. Its output allocation and final reversal are explicit costs, not eliminated by fusion.

## Initial scope

Implement composition, `map`, `filter`, `take`, identity, `transduce`, and `into_list`. Supply a list driver, a finite range driver, and simple sum/count/list consumers.

The range source represents a finite range as state, not a prebuilt list. Define it as an ascending half-open U32 interval `[start, end)`, empty when `start >= end`; use a structurally decreasing Nat budget or equivalent checker-accepted bound. Do not silently wrap at the numeric limit.

Defer buffered stages, flattening, arbitrary stream protocols, IO drivers, parallel drivers, and runtime-selected pipeline structures. The core protocol must accommodate completion and stopping, but v1 need not implement every future stage.

## Representation in Bend

Separate static operation code from runtime values:

- Operation code is supplied through closed `~` template arguments.
- Runtime configuration and evolving state are explicit values passed through the traversal.
- Reducer state is affine (`Type`), so it can contain owned accumulators and other non-copyable values.
- A transformation wraps downstream state in its own state where necessary. Composition nests these wrappers; there is no universal state map or dynamically typed container.

For example, mapping need not add state when its function is closed; configured mapping holds configuration. Filtering with a runtime threshold holds that threshold alongside downstream state. Taking holds a remaining count and downstream state. Each invocation creates fresh execution state.

A template argument cannot capture caller-local runtime values. The library therefore needs configured callback forms whose configuration is an explicit argument, rather than pretending `~(x => compare(x, local_threshold))` is legal. Initial reusable configuration is `Data`; richer stateful callbacks may thread affine state later.

Templates may refer only to templates declared above them. Define primitive adapters before their composed adapters and drivers. Generated specializations may increase code size and compile time; measure both.

A pipeline is initially a statically composed family of operations, not a reusable runtime record containing callable closures. Ordinary Bend closures are callable once. The implementation must demonstrate a usable declaration/composition pattern with templates; the pseudocode above is a semantic sketch, not a promise that Bend supports that builder syntax.

### Element ownership

`map` consumes an input and produces an output; it can support affine elements.

A conventional `filter(predicate)` needs to inspect and then retain the same element. In v1 its input must be `Data`, consistent with Bend's current `List.filter`. The predicate must not consume an affine element and then attempt to return that consumed value. A future ownership-preserving selection operation could consume an element and return an optional retained or transformed element; that is outside v1.

`take` and the traversal protocol need no intrinsic element-copying capability. Collection drivers should not require the entire input to be reusable merely because one stage examines reusable elements.

## Reducer lifecycle

The semantic protocol is:

```text
Control<S> = Continue(S) | Stop(S)
start(configuration, initial_accumulator) -> Control<S>
step(S, input) -> Control<S>
finish(S) -> result
```

These describe separately specialized operations and types, not runtime function fields. A transformation adapts all three operations of its downstream reducer. Its output type must match the downstream input type. The accumulator and final result may differ.

Execution proceeds as follows:

1. Initialize the complete reducer chain, from the consumer outward.
2. If initialization returns `Stop`, obtain no source elements and go to completion.
3. Otherwise, obtain the next input and invoke `step` once.
4. If `step` returns `Continue`, repeat; if it returns `Stop`, obtain no further inputs in the sequential driver.
5. On exhaustion or stopping, invoke the outer `finish` exactly once. Each initialized wrapper invokes its downstream `finish` exactly once.

The source driver must structurally recurse on its list tail or finite production budget. Generic arbitrary `next` callbacks do not by themselves establish termination to Bend's checker.

Initialization is essential. `take(0)` must return `Stop` during initialization, including when it appears after mapping or filtering. Drivers must check that result before asking a generated source for an element. Passing an already-computed list as an argument cannot undo the work that constructed it.

Once a particular reducer reports `Stop`, no further `step` calls may be made to that reducer. Wrappers propagate a downstream stop immediately. A consumer may itself stop early; stopping is not exclusive to `take`.

### Completion and the origin of stopping

Stopping a stage's upstream input does not necessarily close its downstream consumer. A future buffering stage makes this distinction observable:

```text
source -> take(3) -> partition_all(2) -> collect
```

After three inputs, taking stops upstream. Completion should still flush the final one-element partition downstream.

Conversely:

```text
source -> partition_all(2) -> take(1) -> collect
```

Once downstream taking stops, the partition stage must not emit further outputs, including during completion.

Each wrapper must therefore retain whether its downstream reducer is still accepting inputs. A wrapper's own stopping condition is distinct from a downstream `Stop`. Both return `Stop` upstream, but wrapper state preserves the distinction. A buffering wrapper may flush only while downstream is open, must stop flushing immediately if downstream stops, and must then finish downstream exactly once. Unemitted buffered values are released.

No global boolean meaning simply “the run stopped” can replace this per-wrapper information. Completion order follows the wrapper chain. The rule must also work for nested buffered stages and an initially stopped downstream reducer.

V1 has no buffered transformations, but acceptance tests must exercise the lifecycle using a small test reducer/wrapper that emits on completion. This prevents accepting an interface that cannot support the intended extension.

## Sources and ownership at termination

List and range drivers share reducer semantics but may have different structural traversals. Do not convert all sources into lists or impose a universal heap-allocated iterator solely to share a loop.

For a prebuilt owned list, stopping avoids further transformation work but may still require releasing its unused tail. Native Bend recursively releases owned structures. Thus `take(k)` need not make total runtime O(k) when supplied an already-built O(n) input.

For a range, stopping avoids generating remaining values. Maintaining bounded pipeline state does not imply bounded memory for the input or collected output.

The initial drivers consume their source. Returning an unconsumed remainder is not part of v1; supporting resumable processing later requires an explicit API contract. Resource-owning IO sources must eventually specify cleanup and handle return, rather than relying on ordinary dropping as an effectful close operation.

## Execution strategy and effects

V1 uses an ordered sequential driver: no lookahead, no calls to an upstream stage after stopping is observed, and no speculative mapper calls. This is a property of that driver, not the definition of every future execution strategy.

Future batched or parallel strategies may perform extra pure work. They must preserve the pipeline's logical result, ordering, state boundaries, and completion semantics. Any lookahead must be bounded by a documented strategy parameter or policy. Do not choose a fixed chunk size before measuring.

Stateful stages cannot simply be restarted independently on every chunk. `take(n)` means n outputs globally, not n per worker. Parallel combination of reductions requires an associative operation and identity under the actual numeric semantics; an ordinary sequential reducer provides no such guarantee. Floating-point sums, in particular, must not be reassociated silently.

A sequential accumulator can erase the benefits of Bend's explicit parallel array traversal. Parallel execution is a separate later design task: fuse within independent branches, then combine where the reducer and transformation semantics permit it.

Transformation callbacks are pure. IO sequencing belongs to explicitly effectful drivers or consumers outside v1. The library must not execute embedded effects as speculative transformation work. User-visible instrumentation is not a supported way to observe a pure pipeline's evaluation schedule.

## Performance expectations

The design removes intermediate collections between stages by construction. It does not yet promise allocation-free control/state wrappers, complete inlining, constant stack/continuation space for every consumer, or superior speed on every workload.

Inspect generated C and JS, then measure native behavior. Compare:

- Existing materialized collection composition.
- A handwritten fused traversal with equivalent semantics and source ownership.
- The library pipeline.

Measure output correctness, operation counts, wall time, allocation traffic and peak live memory where instrumentation supports them, compilation time, and generated code size. Do not label process RSS as precise live Bend heap usage or extrapolate native memory behavior from JS garbage collection.

Use prebuilt and generated inputs, cheap and expensive mapping, selective and nonselective filtering, early and full consumption, and both scalar and list results. Time compilation and source construction separately from execution where applicable. A later parallel benchmark must compare against an existing parallel traversal, not only a sequential baseline.

## Validation and implementation order

Before freezing the API:

1. Demonstrate identity and composed mapping with changing element types and an affine accumulator.
2. Demonstrate mapping, runtime-configured filtering, and runtime-count taking with one traversal.
3. Demonstrate initialization stopping, consumer stopping, and correct completion propagation, including both buffered examples above.
4. Run the same pipeline over a list and a finite range without materializing the range.
5. Demonstrate ordered `into_list`, repeated runs with independent state, and ownership rejection for an invalid affine filter.
6. Inspect generated code and compare with handwritten baselines. Revise the representation if state/control allocation or template ergonomics defeat the purpose.

Semantic cases include empty input; identity; zero/one/oversized take; consecutive takes; all/no elements passing a filter; transformation order; initial and mid-run consumer stop; completion exactly once; downstream stop during a completion flush; and numeric range boundaries.

Use Bend files with expected `#|` output for executable examples and checks. Specify list-equivalence laws for the supported pure, terminating subset. Proof of result equivalence does not prove absence of allocation or establish a runtime bound.

Do not add `@unsafe` to bypass an implementation problem. The current CLI also counts template specializations in its “unsafe annotations” diagnostic; record that diagnostic and assess the trust boundary rather than describing successful compilation as a complete formal correctness proof.

## What remains open

The exact public signatures and composition notation, generic configuration packaging, and elimination of state/control allocation require implementation experiments. The complete buffered lifecycle has been reasoned through but not executed in the current probe. A generic source abstraction and parallel scheduling are intentionally deferred.

These questions are explicit acceptance gates, not assumed solved. The first milestone is a small library whose ergonomics and generated behavior survive those gates; only then should the API expand.
