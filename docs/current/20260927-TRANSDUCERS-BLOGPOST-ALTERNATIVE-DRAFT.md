---
created_at: 2026-09-27
status: alternative-part-one-draft
---

# Transducers in Bend: from a generic transformation to a SIMD loop

## What is this?

Bend had just come out, and I wanted to see whether I could add transducers to it. I wanted to write transformations at the level of `map`, `filter`, and `reduce`, compose them freely, and have the compiler turn the result into something as fast as a C loop.

The question was roughly: can I write `coll.map(int).filter(even).reduce(+, 0)` without paying for intermediate collections, boxed values, or a callback at every item?

Rust already has a compelling answer with [iterator adapters](https://doc.rust-lang.org/std/iter/trait.Iterator.html): `map`, `filter`, `flat_map`, `fold`, and `collect` compose around an iterator. I came to the problem from Clojure, so I call my version *transducers*. I am not claiming to have invented fusion. I wanted to find out what it would take to get this style of programming to work well in Bend, including Bend's ownership and proof system.

## TL;DR

Here is the small program I kept coming back to:

```bend
# Clojure: (transduce (map inc) + 0 xs)
def transducer(xs: Array<U32>) -> U32:
  X.transduce(X.map(~U32, ~U32, ~U32.inc), X.sum_rf(), 0, xs)
```

For comparison, the timed part of the [handwritten C control](../../bench/public_array_map_inc_sum.c) is:

```c
uint32_t sum = 0;
for (size_t i = 0; i < count; ++i) sum += values[i] + UINT32_C(1);
free(values);
```

The input Array has 1,048,576 `U32` values. Each program builds its input before starting the clock; traversal and disposal are inside the timed interval. On my M3 Max, 36 shuffled, paired sessions gave medians of **76 µs for Bend, 80.5 µs for C, and 80 µs for Rust's iterator chain**. They returned the same wrapping `U32` checksum. The differences at this scale are too small to make a language ranking from them. They tell me that this particular high-level Bend pipeline has reached the same practical speed as the two controls. The [fixture](../../bench/public_array_map_inc_sum.bend), [Rust control](../../bench/public_array_map_inc_sum.rs), and [raw samples](../../bench/public-array-map-inc-sum-20260927.json) are in the repository.

The result I found most satisfying was in the compiler output. Clang 17 reported four-wide vectorization for the Bend traversal loop. This is an excerpt from the assembly for the exact fixture:

```asm
ldp     q4, q5, [x8, #-32]
ldp     q6, q7, [x8], #64
sub.4s  v0, v4, v0
sub.4s  v1, v5, v1
add.4s  v0, v1, v0
```

The surrounding instructions invert the accumulators before the `sub.4s`, giving the wrapping `+ 1` behavior, and later reduce the vector lanes. The generated C is still Bend runtime C, with Array ownership and disposal around the loop. The native loop has no per-item transducer object or boxed `U32`; the measured interval did make **nine** heap allocation calls in total, so “zero allocations” would be inaccurate.

There is no compiler rule named after `map`, `filter`, or transducers. The library arranges the work so general compiler rules can see a static callback, a known source traversal, and an impossible stop case. The rest of this post is how I got there.

## Note to Bend devs

This is an experiment in my Bend fork. It includes compiler changes that may or may not fit upstream Bend. Please take, change, or ignore any of them as you see fit. Thank you for making a language interesting enough to try this in. ❤️

## Why transducers

[Clojure introduced transducers in 1.7](https://clojure.org/news/2015/06/30/clojure-17), rather than 1.9 as I initially remembered. A transducer describes a transformation independently of the collection it reads and the result it builds. `(map inc)` takes no collection. It transforms a reducing function into another reducing function. `(filter even?)` does the same, sometimes calling the downstream function and sometimes skipping it. Clojure's [reference](https://clojure.org/reference/transducers) explains the reduction lifecycle in terms of initialization, stepping, completion, and early termination.

For example:

```clojure
(comp (map inc) (filter even?) (mapcat range))
```

That composition reads left to right when it processes an item. The source supplies an item, `map` changes it, `filter` may drop it, and `mapcat` may supply several items to the final reducing function. No intermediate sequence is required by the transducer contract. A particular transformation can still allocate something observable: if a mapping function itself constructs a List, that List still exists unless another optimization removes it.

The reuse is the attractive part. A new source can feed every existing transducer. A new transducer works with every existing source and destination. A new destination can receive the results of every composition. The implementations multiply in usefulness without multiplying `List.map`, `Array.map`, `Vec.map`, and so on.

Bend also gives me a place to state laws. I have checked local laws for `map` and `filter`, an inductive List map/fold law, and a no-stop List driver law. Those laws apply to the functions they mention across calls; they do **not** yet prove the whole public `transduce` API correct for every source or prove the generated C correct. I will return to the exact boundary below.

## Differences from Clojure

In Clojure, `(map inc)` returns a function that accepts a reducing function. Applying it creates the reducing function used for that run. My Bend `X.map(...)` returns an owned `Xf` value containing a **static reducer recipe** and any runtime settings. When `X.transduce` consumes that value, it applies the recipe to the final reducer, starts the resulting reducer, drives the source, and finishes it. So my earlier thought that the Bend transducer was “already initialized” was imprecise: its transformation is chosen, but its reduction state is initialized for this run. Construct a new `Xf` to run it again.

Clojure may obtain the initial accumulator by calling the reducing function with no arguments. My Bend API always takes an explicit initial value. A reducer still has `start`, `step`, and `finish`, because a stateful transducer such as `partition_all` may have something to flush at completion.

Clojure wraps a result in `reduced` to request early termination. I represent that request with `Control<K, S>`, whose cases are `Continue{state}` and `Stop{permit, state}`. `K` matters: a reducer that cannot stop uses `K = Empty`, so it cannot construct a valid `Stop` value. A reducer such as `take` uses an inhabited permit. This is a property of the composed reducer's *type*, rather than a flag checked by each transducer.

My current source interface is another difference. It is an owned, **push-style driver**: the source knows how to traverse itself and calls a supplied step. It is neither Clojure's per-collection `reduce` method nor Rust's `Iterator::next` interface. I initially considered describing it as an iterator returning owned items, but that would describe a possible next design, not this implementation.

## How to use transducers

The public operation is `X.transduce(xf, rf, initial, source)`. The source is an Array, List, Range, String, Vec, or another type with a `.source` companion. `rf` says how to accumulate outputs. `xf` says how to transform each input before it reaches that reducer.

Here is the lifecycle, with the implementation details stripped down:

```text
configuration = xf.configure(rf.prepare(initial))
state         = composed_reducer.start(configuration)
state         = source.drive(composed_reducer.step, inspect_stop, state)
result        = composed_reducer.finish(state)
```

The real [`transduce_from`](../../xf.bend) calls `configure`, `prepare`, `T.start`, the source's static `Drive`, and `T.finish_control` in that order. It also passes an `inspect` callback so a source can check for a stop **before** reading the next item. An initially stopping transducer, such as `take(0)`, need not touch the first element.

`X.into(destination, xf, source)` builds a result using the destination's reducer and delegates to `transduce`. Here is an ordered example:

```bend
# Clojure: (into [] (map inc) [1 2 3])
X.into(Vec.empty(~U32, 0),
  X.map(~U32, ~U32, ~U32.inc), numbers())
```

In the [checked example](../../tests/blogpost_examples.bend), `numbers()` returns `[1, 2, 3]` and the Vec contains `[2, 3, 4]` in that order. I use Vec because the current List destination prepends, which would reverse this example's order.

Clojure also has `sequence`, which computes transformed elements incrementally. I have not implemented that API. It would need a way to suspend a transformation after producing an output and resume it later, including one-to-many transformations and completion. The present source driver is eager.

### Could a pull iterator be a better source interface?

Possibly. The current source signature is powerful but large: a source receives a step callback, an inspect callback, an opaque accumulator, and type parameters for the stop permit and state. Each source implements its own traversal loop. A pull interface like `next(owned_source) -> None | Some(item, remaining_source)` could put one generic reduction loop in the library. Every source would implement `next` once; other consumers could reuse it without asking the source to implement another fold. That is a real simplification of the *surface and reuse story*, and it is why Rust's design is appealing.

It is not yet an established improvement in this fork. The pull form has to preserve affine ownership, early stop before the next read, finalization, and nested fragments used by `cat`. For `Array<U32>`, it must also let the compiler recover the bounded contiguous walk that makes SIMD possible. An `Option` and an iterator state passed through every iteration might specialize away; I would want to implement and measure that before claiming it does. A pull `next` could be a useful lower-level source protocol even if `transduce` remains a push-style consumer built on top of it.

## Bending Bend to my will

I started with `transduce`, `map`, and `filter` on List and Array. Three pieces matter: a reducer that consumes outputs, a transducer that wraps that reducer, and a source that supplies inputs. I will use those words consistently; the library's `Xf` type is what I mean by *transducer*.

At the reducer level, `map` changes one input and delegates to the downstream step:

```bend
# Clojure: the reducing function made by (map f)
def map(~A: Type, ~B: Type, ~R: Type, ~f: A -> B,
  ~down: Reducer<B, R>) -> Reducer<A, R>:
  Reducer{Permit(B, R, down), Config(B, R, down), State(B, R, down),
    initial => start(B, R, down, initial),
    state => x => step(B, R, down, state, f(x)),
    state => finish(B, R, down, state)}
```

`filter` tests an input and forwards it only when the predicate is true. This is its decision point in [`transduce_core.bend`](../../transduce_core.bend):

```bend
# Clojure: the reducing function made by (filter predicate)
def filter_choose(~A: Data, ~R: Type, ~down: Reducer<A, R>,
  keep: Bool, state: State(A, R, down), x: A) ->
  Control<Permit(A, R, down), State(A, R, down)>:
  match keep:
    case True{}: step(A, R, down, state, x)
    case False{}: Continue{state}
```

The `filter` reducer calls this with `predicate(x)` and delegates initialization and completion to `down`, just as `map` does. Neither transducer knows whether its source is a List or an Array. Importantly, both pass through the downstream stop permit: neither stops on its own, but either composed with `take` must still be able to stop.

The public [`X.map`](../../xf.bend) is a small wrapper around that reducer recipe:

```bend
# Clojure: (map f)
def map(~A: Type, ~B: Type, ~f: A -> B) -> Xf<A, B,
  (R => down => T.map(~A, ~B, ~R, ~f, ~down))>:
  Xf{R => down => config => config}
```

The long return type says: give me a result type `R` and a reducer `down` for `B`; I can make a reducer for `A`. `X.compose` nests those recipes. At run time, the `configure` function supplies values such as a `take` count or a separator. For simple `map`, there is no extra runtime setting, so it returns the downstream configuration unchanged. This split between a closed recipe and owned settings is how I keep generic composition available to the compiler without requiring a heap-allocated closure per item.

The heart of the real `X.compose` definition is `Outer(R, Inner(R, down))`. For each input, `Outer` runs first and may call `Inner`, which may call the final reducer. It configures the inner transducer first, then the outer one, so both get the runtime state they need. That is what makes `X.comp2(X.map(...), X.filter(...))` one reducer chain rather than a mapped collection followed by a filtered collection.

I first imagined each collection implementing something like `.reduce(rf, init)`. The present API instead implements `Type.source(value)`. Here is the actual Array companion, abbreviated only by omitting the separate adapter for `cat`:

```bend
# Clojure: the collection supplied to (transduce xf rf init xs)
def Array.source(~A: Data, xs: Array<A>) ->
  Source<A, Array<A>, (K => S => advance => inspect => ys => state =>
    source_array(~A, ~K, ~S, ~advance, ~inspect, ys, state))>:
  Source{xs}
```

This is an ordinary library definition; I did not need a new language construct to write it. `Source{xs}` owns the Array. Its type carries the particular traversal function, `Drive`. The Array drive now calls `Array.walk`, a Bend Base operation that owns the Array and walks from index zero for its derived size. Affine Array elements use a separate structural source, since indexed `Array.get` cannot hand an owned element out while leaving the Array valid.

The language change was about *using* that companion implicitly. I wanted the call site above to pass `xs` directly, while `transduce` expects `Source<...>`. Bend has no general trait or protocol mechanism for this. I added a narrow checked conversion: when a nominal expected type opts in with `Source.allow_companion()`, the checker derives the method name `.source` from `Source`, looks for an owner method such as `Array.source`, and inserts that call. For Base-owned types, the protocol module may supply the method because Base cannot import this library. The same mechanism handles `Destination` for `into`.

In the compiler's [`companion_method`](../../../bend/bend2/bend.ts) the essential lookup is:

```ts
const suffix = simple[0].toLowerCase() + simple.slice(1);
const own = a.k + "." + suffix;
const own_def = book.tlds[own];
if (own_def?.$ === "Def" && own_def.v !== null) return own;
```

The full rule checks the opt-in marker, the actual and expected nominal types, and the fallback extension location. Then normal type checking checks the inserted method's result. It does not search every method or silently convert arbitrary structural values.

There was a second, related type-checker change. Calls such as `X.transduce(...)` have many leading static `~` arguments for `A`, `B`, the reducer recipe, source drive, and so on. Explicit `~?AUTO` placeholders let the checker solve those arguments from the **types of later runtime arguments**. It matches nominal type structure with a bounded search; it does not execute runtime values or solve arbitrary equations. Together, companion conversion and `~?AUTO` let a readable public call become a fully instantiated static call. This is the point where the compiler knows the exact source drive and reducer recipe.

### Compiler: specialize the callback recipe

Knowing those types did not initially mean getting a tight loop. The source still appeared to call a computed reducer function. If that function became a runtime value, each item would pay for the abstraction.

I added a bounded [`specialize` pass](../../../bend/bend2/comp.ts) that runs on checked terms before native code emission. When the function being called was *computed* but its head can be resolved statically, the pass opens the known lambda and applies it to the argument. Conceptually, it turns this:

```text
source_step(state, item)
  where source_step = map(inc, sum_step).step
```

into this:

```text
sum_step(state, inc(item))
```

That is explanatory pseudocode; the actual Bend reducer is the `Reducer{start, step, finish}` record shown above. The pass deliberately leaves ordinary named calls as calls. It has a rewrite budget, stops at dynamic or unsafe computations, and binds a dynamic argument once if substituting it could duplicate an owned value. Those limits matter in Bend: an optimization cannot change whether a value is consumed once or twice.

This rule is generic. It works because the library passes the reducer construction statically, not because the compiler recognizes `X.map`. In a separate retained List-chunk experiment, static callback specialization made the pipeline **4.8–5.5×** faster than the unspecialized compiler. That number is for a different workload, recorded in the [ablation report](20260924-TRANSDUCER-FUSION-ABLATION.md); it is not the speedup of the million-element Array test. Nor does this pass make every intermediate collection disappear. If a program creates and retains a chunk List, that List is still a result of the program.

### Compiler: remove the Array index mask where the walk proves bounds

After the reducer callbacks fused, the flat Array test was still about twice as slow as C in an earlier run: **352 µs for Bend versus 178 µs for C** under that run's conditions. I traced it to `Array.get`. Its index is masked to preserve Bend's wraparound behavior. That is correct for a general call, but our traversal starts at zero and stops at the Array size. Clang saw a masked read, not an obvious contiguous stream.

I added [`Array.walk`](../../../bend/bend2/base.bend) to the fork's Base library and changed the Array source to use it. It derives the size, starts at index zero, owns the next index and remaining count, and calls `inspect` before every read. The compiler recognizes this particular generic walk. At entry it checks that the *whole span* fits in the Array; within that span it emits a direct offset. If someone calls the lower-level loop with an invalid span, the emitted code falls back to the ordinary masked `blk_at` read.

The relevant generated C for the benchmark contains:

```c
u64 _walk_size_0 = 1ull << (blk_cls(_checked_1) - 0);
bool _walk_bounded_0 = (u64)_index_0 <= _walk_size_0
  && (u64)_remaining_0 <= _walk_size_0 - (u64)_index_0;
Term _at_1 = (_walk_bounded_0
  ? ((u32)_index_0 << 0)
  : blk_at(_checked_1, _index_0, 0));
```

The check is outside the loop. The public walk begins with `index = 0` and `remaining = size`. Each iteration increases the first and decreases the second, so their sum stays equal to the size. If an iteration remains, its index is in range. This is a source and compiler invariant argument, not a machine-checked theorem about the C emitter. The existing block lookup, keep, disposal, and element layout handling remain. [Tests and the exact lowering](20260927-ARRAY-WALK-INTEGRATION.md) cover boxed and multiword elements, shared storage, stopping positions, malformed lower-level calls, and Metal execution.

The generated C still contains runtime plumbing and a guard for malformed use. Clang 17 could nevertheless see the regular loop. On the integrated million-item fixture the median became **76 µs**. The earlier 352/178 comparison and the later 76/80.5 comparison are different runs, so I use them to explain the direction and mechanism, not to calculate a precise end-to-end speedup from one controlled pair. A second `map → filter → sum` fixture measured **188.5 µs Bend, 199 µs C, 195.5 µs Rust iterators** in 36 paired sessions. See the [integrated report](20260927-ARRAY-WALK-INTEGRATION.md) for flags and samples.

### Compiler: eliminate impossible stop paths

I also wanted total pipelines to avoid checking after every element whether they should stop. The reducer representation makes that question visible in the type:

```bend
# Clojure: a reducing function with no possible (reduced ...) result
type Control<-K: Data, -S: Type> is Type:
  Continue{state: S}
  Stop{permit: K, state: S}
```

`T.sum()` uses `K = Empty`. `T.map` and `T.filter` carry their downstream reducer's permit unchanged. Compose either with `sum`, and `Stop` would require an `Empty` value, which cannot exist. Compose with `take`, and the stop branch remains possible. The compiler has a general rule for a constructor with a live field of an empty datatype: it cannot be selected in a well-typed value of that instantiation. Clang can then remove redundant checks that remain in the generated C. This is not a transducer-specific branch deletion.

I have a checked [no-stop List driver law](../../proofs/no_stop_control_law.bend), but no reliable standalone percentage gain for this rule. An earlier apparent roughly 10% timing difference moved with native code placement. I would rather show the impossible type and the compiled loop than attach a number that the measurements do not support.

## How do these changes affect existing Bend programs?

I ran the fork against the 16 local Bend runtime benchmarks and five checker benchmarks, comparing the version before `Array.walk` with the version containing it. All builds succeeded and all printed results matched. On the M3 Max, three one-thread CPU runs per case showed most median ratios close to 1.0. One apparent speedup had **byte-identical generated C**, so I do not credit the compiler change for it. The eight-thread CPU pass also matched all outputs, with median ratios from 0.984 to 1.017; five paired Metal runs per case matched outputs, with ratios from 0.996 to 1.011. The [regression report](20260927-UPSTREAM-LOCAL-REGRESSION.md) has the raw runs and limitations.

For the new path itself, 64 library cases passed, as did 1470 compiler cases and a Metal execution fixture. Those checks and the bounds argument are useful evidence. They are not a proof that every Bend program keeps identical performance or that the whole compiler is verified.

## Showcase

The small Array pipeline isolates the compiler mechanism. I also built Bullet Cathedral to see what the same ideas look like in a larger deterministic simulation and renderer. That introduces scene data structures, collision work, five implementations, source-size questions, and a different proof boundary. I am keeping those measurements and tradeoffs in [Part 2](20260927-BULLET-CATHEDRAL-BLOGPOST-DRAFT.md).

## Conclusion

I can define a transformation once, compose it with others, and use it with different sources and destinations. For the flat Array examples, Bend's checked generic code becomes a bounded walk that Clang vectorizes, with performance in the same range as the matched C and Rust iterator programs. Rust shows that this programming style already works well elsewhere; this experiment shows one way to make it work in Bend.

The source interface is the part I would revisit. Its push driver makes traversal and early stop explicit and gave me a good path to a fast `Array.walk`. A pull iterator returning owned items may give a smaller, more reusable source contract. I have not yet shown that it preserves the same code generation or covers the same ownership and completion cases. That is a worthwhile next experiment, rather than a claim about the present implementation.

I also value what I can state and check in Bend. The current [proofs](../../proofs/README.md) cover local reducer behavior, List fusion laws, and one no-stop law. They do not prove the entire public API or the native backend. Even with that boundary, being able to connect a high-level composition, checked laws, generated C, assembly, and measured runtime in one experiment is exactly what I hoped to learn.
