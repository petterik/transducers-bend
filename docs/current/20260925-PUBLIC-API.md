---
created_at: 2026-09-25
status: canonical-public-api
---

# Public transducer API

This is the single entry point for **using and extending** transduce-bend.
Read this file before reading implementation code. The supported entry points
are `xf.bend` for stages and reduction, `transduce_core.bend` for source and
stage extension protocols, and `vec.bend` / `vec_maybe.bend` for ordered
collections. Bend imports are file-scoped: importing `xf.bend` does not
re-export Vec or the core protocol. The code files also contain helpers that
Bend makes visible but that are **not** the supported API listed here.

The supported compiler is the `codex/transducer-no-stop` branch of
`petterik/bend`; its checked companion conversion lets a raw source or
destination value be passed to `transduce` or `into`. The repository's
`README.md` has the pinned commit and setup commands.

## First use

```bend
import Base
import ./xf.bend as X
import ./vec.bend as Vec

def inc(x: U32) -> U32:
  U32.inc(x)

def numbers() -> List<U32>:
  [1, 2, 3]

def main() -> U32:
  values = X.into(Vec.empty(~U32, 0),
    X.map(~U32, ~U32, ~inc), numbers())
  X.transduce(X.map(~U32, ~U32, ~inc), X.sum_rf(), 0, values)
# 12
```

The imports above are relative to a file in the repository root. From a
`tests/` file, use `../xf.bend` and `../vec.bend`. `into` appends to Vec in
encounter order. `transduce` consumes the resulting Vec as a source without
an explicit adapter. A stage value owns its settings and is used once; call
its constructor again to run the same transformation on another source.

## Reduction and composition

| Call | Meaning |
| --- | --- |
| `X.transduce(xf, rf, initial, source)` | Drive `source`, complete once, and return the reducer result. |
| `X.into(destination, xf, source)` | Collect into `destination`; it delegates to `transduce`. |
| `X.comp2(a,b)`, `X.comp3(a,b,c)`, `X.comp4(a,b,c,d)`, `X.comp5(a,b,c,d,e)` | Run stages left to right. Nest these to compose more than five. |
| `X.compose(a,b)` | Two-stage synonym for `comp2`. |
| `X.sum_rf()` | Sum `U32` outputs; initial value is a `U32`. |
| `X.count_nat_rf()` | Count `Nat` outputs; initial value is `Unit{}`. |

Types usually infer from the input, stage, and reducer, but stage type
parameters still appear explicitly, as in `X.map(~U32, ~U32, ~inc)`. A typed
source or destination helper can supply context where a literal such as `[]`
does not. The reducer controls early stopping; the source merely drives items
until the reducer asks it to stop.

## All public stages

`A` and `B` below denote input and output types. `Data` is Bend's reusable
kind, which includes user-defined reusable records; `Type` also permits
affine values. Callbacks marked `~` are static template callbacks, so they
can specialize without a per-item runtime closure.

| Stage | Result and behavior | Constraint |
| --- | --- | --- |
| `X.map(~A, ~B, ~f)` | Apply `f: A -> B`. | `A, B: Type` |
| `X.map_indexed(~A, ~B, ~f)` | Apply `f: Nat -> A -> B` with zero-based index. | `A, B: Type` |
| `X.map_with(~A, ~B, ~C, ~f, setting)` | Apply `f: C -> A -> B` with owned runtime setting. | `C: Data`; `A, B: Type` |
| `X.filter(~A, ~predicate)` | Keep inputs for which predicate is true. | `A: Data` |
| `X.remove(~A, ~predicate)` | Keep inputs for which predicate is false. | `A: Data` |
| `X.keep(~A, ~B, ~f)` | Apply `f: A -> Maybe<B>` and emit `Some` values. | `A, B: Type` |
| `X.keep_indexed(~A, ~B, ~f)` | Indexed `keep`, with zero-based `Nat` index. | `A, B: Type` |
| `X.dedupe(~A, ~equal)` | Remove adjacent duplicates using supplied equality. | `A: Data` |
| `X.interpose(~A, separator)` | Insert separator between outputs, never at ends. | `A: Data` |
| `X.take(~A, n)` | Emit at most `n` items, then stop the source. | `A: Type`; `n: Nat` |
| `X.drop(~A, n)` | Discard the first `n` items. | `A: Type`; `n: Nat` |
| `X.take_nth(~A, n)` | Emit positions `0, n, 2n, ...`; zero emits nothing but still traverses. | `A: Type`; `n: Nat` |
| `X.take_while(~A, ~predicate)` | Stop before the first failed predicate. | `A: Data` |
| `X.drop_while(~A, ~predicate)` | Drop the initial matching run only. | `A: Data` |
| `X.partition_all(~A, width)` | Ordered `List<A>` chunks, including one partial tail unless downstream stopped; zero stops initially. | `A: Type`; `width: Nat` |
| `X.partition_by(~A, ~K, ~key, ~equal)` | Ordered `List<A>` groups of adjacent equal keys. | `A, K: Data` |
| `X.windows(~A, width)` | Full overlapping `List<A>` windows; no partial tail; zero stops initially. | `A: Data` |
| `X.windows2(~A)` | Full adjacent `(A & A)` windows. | `A: Data` |
| `X.windows3(~A)` | Full adjacent `(A & A & A)` windows. | `A: Data` |
| `X.cat(adapter)` | Flatten raw reducible fragments using their adapter. | Fragment has an adapter. |
| `X.mapcat(~A, ~B, ~X, ~Drive, ~f)` | Map to raw fragments and drive each directly. | Explicit closed source drive. |
| `X.cat_drive(~B, ~X, ~Drive)` | Flatten with an explicit drive instead of an adapter. | Explicit closed source drive. |

For ordinary map-and-flatten, use `X.comp2(X.map(...),
X.cat(adapter))`. `mapcat` and `cat_drive` expose the lower-level drive when
an adapter is unavailable. `cat` preserves a stop inside a fragment. A
mapper that constructs a List or Vec still pays that construction cost.

`partition_all` uses a List buffer and allocates observable chunks. It also
supports affine elements. Earlier Array-chunk measurements on the supported
compiler did not justify replacing this default with Array/Vec buffering.
For common overlapping widths two and three, tuple windows avoid constructing
a List per window.

## Built-in sources, destinations, and fragment adapters

| Collection | Raw source for `transduce`/`into` | Destination for `into` | Adapter for `cat` |
| --- | --- | --- | --- |
| `List<A>` | Yes, encounter order | Yes, **prepends**, so output order reverses | `T.List.adapter(~A)` |
| `Array<A>` | Yes, indexed order | No general append destination | `T.Array.adapter(~A)` |
| `T.Range` | Yes; make with `T.range(end)` or `T.range_between(begin,end)` | No | `T.Range.adapter()` |
| `String` | Yes, emits `Char` | No | `T.String.adapter()` |
| `Vec.Vec<A>` | Yes, logical prefix in order | Yes, appends in order | `Vec.adapter(~A)` |
| `VecMaybe.VecMaybe<A>` | Yes, logical prefix in order | Yes, appends in order | No built-in adapter yet |

Import `./transduce_core.bend as T` for Range or built-in fragment adapters,
`./vec.bend as Vec` for Vec, and `./vec_maybe.bend as VecMaybe` for VecMaybe.
An adapter is needed only when `cat` receives fragments *from another stage*;
direct `transduce(xf, rf, init, vec)` and `into(vec, xf, source)` find the
owner companion automatically. For example:

```bend
X.transduce(X.comp2(
  X.map(~U32, ~List<U32>, ~fragment),
  X.cat(T.List.adapter(~U32))), X.sum_rf(), 0, numbers())
```

Use `Vec.empty(~A, filler)` when a reusable filler is available;
`Vec.with_capacity(~A, requested, filler)` returns `Maybe<Vec<A>>` for a
checked initial reservation. `VecMaybe.empty(~A)` avoids choosing a filler,
with an optional slot and branch per element. Both fast collections require
`A: Data`; they support reusable composite values, not arbitrary affine
`Type` values. `Vec.push/get/set` and the analogous VecMaybe operations are
public. Prefer checked `get/set` for untrusted indexes. Do not fabricate
collection records directly, even though Bend currently exposes their
constructors.

## Extension points

**New source.** Implement an owner method `YourType.source(value)` returning
`T.Source<Item, YourType, Drive>`. `Drive` is a static function of the shape
`K => S => advance => inspect => value => state => state`. It owns the
collection, calls `advance(state, item)` for each item, and calls `inspect`
before the first item and between items. `inspect` returns `T.Ready` or
`T.Halted`; on `Halted`, stop invoking `advance` and return its state. The
source itself returns only `S`; it cannot manufacture a reducer's stop.
This complete one-item source also supplies a `cat` adapter:

```bend
import Base
import ./xf.bend as X
import ./transduce_core.bend as T

type One<-A: Type> is Type:
  One{value: A}

def one_checked(~A: Type, ~K: Data, ~S: Type,
  ~advance: S -> A -> S, value: A, checked: T.Checked<K, S>) -> S:
  match checked:
    case T.Halted{permit, state}: state
    case T.Ready{state}: advance(state, value)

def one_drive(~A: Type, ~K: Data, ~S: Type,
  ~advance: S -> A -> S, ~inspect: S -> T.Checked<K, S>,
  one: One<A>, s: S) -> S:
  match one:
    case One{value}:
      one_checked(~A, ~K, ~S, ~advance, value, inspect(s))

def One.source(~A: Type, one: One<A>) -> T.Source<A, One<A>,
  (K => S => advance => inspect => v => s =>
    one_drive(~A, ~K, ~S, ~advance, ~inspect, v, s))>:
  T.Source{one}

def One.adapter(~A: Type) -> T.SourceAdapter<A, One<A>,
  (K => S => advance => inspect => v => s =>
    one_drive(~A, ~K, ~S, ~advance, ~inspect, v, s))>:
  T.SourceAdapter{}

def one_three() -> One<U32>:
  One{3}

def pair() -> List<One<U32>>:
  [One{3}, One{4}]

def main() -> U32 & U32:
  (X.transduce(X.map(~U32, ~U32, ~U32.inc),
     X.sum_rf(), 0, one_three()),
   X.transduce(X.cat(One.adapter(~U32)), X.sum_rf(), 0, pair()))
# (4, 7)
```

`tests/support/vec_pair_source.bend` demonstrates a two-item source that
checks for stopping between its values.
For a source whose owner cannot define a companion, pass an explicit
`T.Source{value}` with the drive type spelled at the call site.

**New `cat` fragment type.** In the fragment's module, add a zero-field
`T.SourceAdapter<Item, YourType, Drive>` using the same `Drive` as its
source. Pass it to `X.cat(adapter)`. The adapter does not wrap each fragment.
The List, Array, Range, and String adapters are in `transduce_core.bend`;
Vec's is in `vec.bend`. A custom example is alongside the PairSource source.

**New destination.** Implement `YourType.destination(value)` returning
`X.Destination<Item, YourType, Reducer>`. It contains the owned value and an
`X.Rf` whose `prepare` function turns that value into the reducer's initial
configuration. The reducer's `step` adds one output and its `finish` returns
the final collection. An append-only destination normally has a total
`T.Reducer` with `Empty` as its stop permit. `Vec.destination` and
`List.destination` are working examples. `into` supplies the destination
reducer to `transduce` exactly once.

A minimal custom destination has this shape (it prepends, like List):

```bend
import Base
import ./xf.bend as X
import ./transduce_core.bend as T

type Bag<-A: Type> is Type:
  Bag{items: List<A>}

def bag_step(~A: Type, bag: Bag<A>, x: A) -> T.Control<Empty, Bag<A>>:
  match bag:
    case Bag{items}:
      T.Continue{Bag{x <> items}}

def bag_reducer(~A: Type) -> T.Reducer<A, Bag<A>>:
  T.Reducer{Empty, Bag<A>, Bag<A>,
    bag => T.Continue{bag},
    bag => x => bag_step(~A, bag, x),
    bag => bag}

def Bag.destination(~A: Type, bag: Bag<A>) ->
  X.Destination<A, Bag<A>, bag_reducer(~A)>:
  X.Destination{bag, X.Rf{initial => initial}}

def empty_bag() -> Bag<U32>:
  Bag{[]}

def numbers() -> List<U32>:
  [1, 2, 3]

def main() -> Bag<U32>:
  X.into(empty_bag(), X.map(~U32, ~U32, ~U32.inc), numbers())
# Bag{[4, 3, 2]}
```

**New final consumer.** Return `X.Rf<Item, Result, Q, Init>` with a
`prepare: Init -> T.Config(Item, Result, Q)` and `Q` a `T.Reducer`. Pass it
to `X.transduce`. `X.sum_rf` and `X.count_nat_rf` show total consumers.

**New stage.** Return an `X.Xf<Input, Output, P>`. `P` is a static recipe
that accepts a downstream `T.Reducer<Output, Result>` and returns a
`T.Reducer<Input, Result>`. Its `configure` function carries any runtime
settings to that reducer; the stage owns those settings. `X.map` is the
smallest working example, and `X.take` shows a stopping stage. When a stage
changes the reducer's stop permit or has completion work, implement the
`start`, `step`, and `finish` functions in its own module using `T.Control`
and `T.Checked` as needed. Stage implementations may import the core
protocol; application code should normally stay with `X`.

## What is internal

`transduce_core.bend` contains protocol types **and** many implementation
helpers such as `source_list_loop`, `partition_step`, and
`windows_after_step`. `xf.bend` contains a few helpers such as
`transduce_from`, `into_from`, and `list_prepend`. Their visibility is a Bend
module property, not a promise of API stability. The low-level
`transduce.bend` and `xf_legacy.bend` modules remain for old experiments and
are not part of this public contract. For callers, start with `X.into` or
`X.transduce`; import the core module only for Range, built-in fragment
adapters, or implementing an extension point.
