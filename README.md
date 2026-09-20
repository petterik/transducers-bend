# transduce-bend

An experimental Bend library for composing pure data transformations without intermediate stage collections. It provides an owned reducer protocol, extensible source-owned reduction, map/filter/keep/take/partition-all/mapcat, and sum/count/ordered-list consumers. Built-in sources are lists, balanced arrays, finite ranges, and strings; other modules can add sources without changing this library.

## Example

The equivalent of `(transduce (map inc) + 0 (range 10))` is:

```python
import Base
import ./transduce.bend as T

def inc(x: U32) -> U32:
  (x + 1 : U32)

def main() -> U32:
  T.transduce(
    ~T.over_range(~U32, ~T.map(~U32, ~U32, ~U32, ~inc, ~T.sum())),
    0, T.range(10))
# 55
```

`range(10)` describes `[0, 10)` without building a list. `over_range` binds a source reduction implementation to the pipeline at compile time. `transduce` takes that description, runtime configuration, and source data; it derives their types from the description. Sum is a consumer (`sum()`), with its initial accumulator supplied as configuration (`0`). Each call supplies its pipeline once.

Source selection is explicit and static, because Bend has no traits or automatic instance resolution. The source data remains an ordinary runtime value. Lists and arrays pass directly through `over_list` and `over_array`; strings pass directly through `over_string`:

```python
T.transduce(~T.over_list(~U32, ~U32, ~T.sum()), 0, [1, 2, 3])  # 6
T.transduce(~T.over_string(~Nat, ~T.count(~Char)), Unit{}, "abc")  # 3n
T.transduce(~T.over_array(~U32, ~U32,
  ~T.mapcat(~U32, ~U32, ~U32, ~(x => [x]), ~T.sum())),
  0, [1 : U32*4n])  # 4
```

A reusable pipeline can add filtering and stopping:

```python
import Base
import ./transduce.bend as T

def above(threshold: U32, x: U32) -> Bool:
  U32.is_gt(x, threshold)

# Describe the transformation once, independently of its consumer.
def pipeline(~R: Type, ~down: T.Reducer<U32, R>) -> T.Reducer<U32, R>:
  T.map(~U32, ~U32, ~R, ~(x => (x + 1 : U32)),
    ~T.filter(~U32, ~R, ~U32, ~above,
      ~T.take(~U32, ~R, ~down)))

def main() -> U32:
  T.transduce(~T.over_list(~U32, ~U32, ~pipeline(~U32, ~T.sum())),
    (2, (2n, 0)), [1, 2, 3, 4, 5])
# 7: increment, keep values above 2, take two, sum.
```

Stages read from the outside inward. Templates supply closed operation code; ordinary arguments carry runtime values. In the example `(2, (2n, 0))` supplies the filter threshold, take count, and sum's initial accumulator. The state type and all lifecycle callbacks are derived from the single reducer description.

The same pipeline works with a generated source and different consumers:

```python
# Each expression can replace the main body above (adjust its return type).
T.transduce(~T.over_range(~U32, ~pipeline(~U32, ~T.sum())),
  (2, (2n, 0)), T.range_between(1, 6))                         # 7
T.transduce(~T.over_range(~List<U32>, ~pipeline(~List<U32>, ~T.into_list(~U32))),
  (2, (2n, Unit{})), T.range_between(1, 6))                    # [3, 4]
T.transduce(~T.over_range(~Nat, ~pipeline(~Nat, ~T.count(~U32))),
  (2, (2n, Unit{})), T.range_between(1, 6))                    # 2n
```

These examples execute in [tests/range.bend](tests/range.bend). `into_list` is a consumer description, so it also plugs into the list driver and accepts affine elements. It prepends during traversal and reverses once on completion; output storage and reversal remain real costs.

## API

`Reducer<A, R>` is a static description with a configuration type, an owned state type, and three operations: start, step, and finish. Pass descriptions as `~` arguments. Ordinary runtime closures are not reused.

| Operation | Purpose | Runtime configuration |
| --- | --- | --- |
| `sum()` | U32 sum, wrapping according to U32 arithmetic | Initial U32 accumulator |
| `count(~A)` | Count consumed elements as Nat, including affine elements | `Unit{}`; starts at zero |
| `into_list(~A)` | Collect affine or Data elements in encounter order | `Unit{}`; starts empty |
| `reducing(~A, ~S, ~R, ~step, ~finish)` | Adapt an ordinary reduction and finalizer | Initial state S |
| `identity(~A, ~R, ~down)` | Use downstream unchanged | Downstream configuration |
| `map(~A, ~B, ~R, ~f, ~down)` | Transform A to B | Downstream configuration |
| `cat(~B, ~R, ~down)` | Flatten each list-valued input into downstream B values | Downstream configuration |
| `mapcat(~A, ~B, ~R, ~f, ~down)` | Map each A to a list of B values and flatten it | Downstream configuration |
| `keep(~A, ~B, ~R, ~f, ~down)` | Consume A and emit each optional B returned by `f` | Downstream configuration |
| `map_with(~A, ~B, ~R, ~C, ~f, ~down)` | Transform using runtime Data configuration C | `(local, downstream)` |
| `filter(~A, ~R, ~C, ~predicate, ~down)` | Retain Data elements satisfying `predicate(config, element)` | `(local, downstream)` |
| `take(~A, ~R, ~down)` | Limit values reaching this stage | `(Nat count, downstream)` |
| `partition_all(~A, ~R, ~down)` | Group consecutive inputs into non-overlapping lists and flush a final partial group | `(Nat width, downstream configuration)`; zero stops during initialization |
| `transduce(~reduction, config, source)` | Initialize, run the bound source fold, complete once | Consumer/pipeline configuration |
| `over_list(~A, ~R, ~recipe)` | Bind a pipeline to owned `List<A>` traversal | Passed to transduce |
| `over_array(~A, ~R, ~recipe)` | Bind a pipeline to ordered balanced `Array<A>` traversal | Passed to transduce |
| `over_range(~R, ~recipe)` | Bind a U32 pipeline to Range traversal | Passed to transduce |
| `over_string(~R, ~recipe)` | Bind a Char pipeline to String traversal | Passed to transduce |
| `range(end)` | Describe U32 values in `[0, end)`, step 1 | End bound |
| `range_between(begin, end)` | Describe U32 values in `[begin, end)`, step 1 | Both bounds |

Ranges are ascending and half-open; `begin >= end` is empty. Both bounds are U32, so the largest possible end is 4294967295 and that value itself cannot be emitted. Bounds never wrap. No input list is built: the driver maintains a decreasing Nat budget and produces a value only while the reducer is continuing. Steps other than 1 and descending ranges are not supported. `count` uses checked Nat arithmetic, not U32 wrapping; the current compiler's maximum Nat is 281474976710655, with overflow reported as a runtime error.

Array traversal follows the leaves of Bend's balanced array tree from left to right. It reads the source structurally, so it does not repeatedly descend with `Array.get` or build an intermediate list. String traversal yields Bend `Char` elements, not UTF-8 bytes or grapheme clusters. It does not build an intermediate character list.

A predicate without configuration can use `Unit` for C. Mapping may change types and produce affine elements. Conventional filtering requires Data elements because it inspects and retains them. Accumulators may be affine.

Composition is nesting reducer adapters or declaring a reusable template, as above. There is no separate runtime `compose` function. An `over_*` adapter binds the complete reducer description to a source implementation; the initial accumulator is part of the consumer's configuration rather than another independent argument.

The stable composition boundary is one reusable typed declaration. For example,
`tests/api_surface.bend` declares a single `U32 -> Maybe<Nat>` pipeline and
uses it with `count` and `into_list` over range, list, and an external tree.
Callers provide only the source adapter, downstream consumer, and runtime
configuration; they do not construct `Reducer`/`Reduction` records or repeat a
source-specific fold.

Custom consumers can construct `Reducer{C, S, start, step, finish}` directly. Both start and step return `Continue{state}` or `Stop{state}`. Completion runs once even when initialization stops. `reducing` supplies Continue automatically; construct a reducer directly when the consumer must stop early. See [the tests](tests/) for consumer stopping, affine state, type changes, and custom completion adapters.

The sequential list and array drivers stop transformation immediately when they observe Stop. This includes `take(0)` at initialization. Releasing unused owned source data may still take time. Future strategies may permit bounded speculative pure work; that does not change the ordering or values of results.

## Adding a source

A source implements an ordered stopping fold, receiving closed step code and an owned `Control<S>` and returning the final control without calling completion. A small adapter binds that fold and the user's reducer with `reducible`, producing a static `Reduction` description. `transduce` has no source cases or registry.

[The extension guide](docs/foundation/EXTENDING.md) describes the contract and reusable conformance checks. [examples/tree.bend](examples/tree.bend) supplies an independent affine tree source; callers use it without repeating their pipeline:

```python
T.transduce(~Tree.over_tree(~U32, ~U32, ~T.sum()),
  0, Tree.Branch{Tree.Leaf{1}, Tree.Leaf{2}})  # 3
```

## Compiler and verification

This library depends on the [petterik/bend fork, branch `petter/transducers-sept-19`](https://github.com/petterik/bend/tree/petter/transducers-sept-19), which contains the required `bend2/comp.ts` specialization change (commit `b1f9c936`). Use that branch in the sibling `../bend` checkout, or select its compiler with `--bend-main`. The ordinary compiler can run the library semantically, but retains callback construction overhead; the code-generation test intentionally requires the specialization. This is an experimental source-checkout dependency, not a published Bend requirement/version.

```sh
python3 tests/run.py
python3 bench/run.py
python3 bench/range.py
```

These scripts accept `--bend-main /path/to/bend/bend2/main.ts`. They require Python 3, Bun, and a native compiler; the older historical experiment additionally uses Node. They build in temporary directories and do not install dependencies.

The test runner compares emitted JS and native output against each Bend file's `#|` expectations, verifies rejection of affine filtering, checks elimination of callback records, and instruments generated JS to verify source/mapper counts. It includes 18,750 bounded law checks per backend. [Laws and invariants](docs/foundation/LAWS.md) distinguish tested properties, mathematical reasoning, and outstanding formal proof work. Bend reports template specializations as “unsafe annotations”; the library adds no explicit `@unsafe`. Passing these tests is not a formal proof of the implementation.

## Current limits

`partition_all` is the first public buffered transformation: it owns a group
buffer, flushes one partial group during completion, and honors downstream
stopping. Arbitrary buffered transformations, parallel collection drivers, and
IO drivers are not implemented. `cat` and `mapcat` are streaming list-fragment
reducers; fragment construction remains a real cost. Existing sequential
pipelines can run inside caller-defined parallel batches; see [CPU/GPU
measurements](bench/PARALLEL.md) and the [array mapcat benchmark](bench/wordscan/README.md).
No allocation-free guarantee is made: JS still constructs state/control objects,
and native layout/reuse depends on the compiler.

- [CPU threads and Metal GPU performance](bench/PARALLEL.md)
- [Generated range performance](bench/RANGE.md)
- [Current design and work plan](docs/current/DESIGN-WORK-PLAN.md)
- [Implementation repair plan](docs/current/IMPLEMENTATION-REPAIR-PLAN.md)
- [Adversarial implementation review](docs/review/IMPLEMENTATION-REVIEW.md)
- [Laws, invariants, and proof status](docs/foundation/LAWS.md)
- [Implementation status, validation, and performance](docs/foundation/IMPLEMENTATION.md)
- [Library design](docs/foundation/DESIGN.md)
- [Confidence review](docs/foundation/CONFIDENCE.md)
- [Implementation priorities](docs/current/PRIORITIES.md)
- [Historical implementation experiment](experiments/static_reducer/README.md)
