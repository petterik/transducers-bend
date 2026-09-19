# transduce-bend

An experimental Bend library for composing pure data transformations without intermediate stage collections. The initial implementation covers priorities #1 and #2: an owned reducer protocol, static composition, and sequential list transduction with map/filter/take.

## Example

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
  T.transduce(~U32, ~U32, ~pipeline(~U32, ~T.sum()),
    (2, (2n, 0)), [1, 2, 3, 4, 5])
# 7: increment, keep values above 2, take two, sum.
```

Stages read from the outside inward. Templates supply closed operation code; ordinary arguments carry runtime values. In the example `(2, (2n, 0))` supplies the filter threshold, take count, and sum's initial accumulator. The state type and all lifecycle callbacks are derived from the single reducer description.

## API

`Reducer<A, R>` is a static description with a configuration type, an owned state type, and three operations: start, step, and finish. Pass descriptions as `~` arguments. Ordinary runtime closures are not reused.

| Operation | Purpose | Runtime configuration |
| --- | --- | --- |
| `sum()` | U32 sum, wrapping according to U32 arithmetic | Initial U32 accumulator |
| `reducing(~A, ~S, ~R, ~step, ~finish)` | Adapt an ordinary reduction and finalizer | Initial state S |
| `identity(~A, ~R, ~down)` | Use downstream unchanged | Downstream configuration |
| `map(~A, ~B, ~R, ~f, ~down)` | Transform A to B | Downstream configuration |
| `map_with(~A, ~B, ~R, ~C, ~f, ~down)` | Transform using runtime Data configuration C | `(local, downstream)` |
| `filter(~A, ~R, ~C, ~predicate, ~down)` | Retain Data elements satisfying `predicate(config, element)` | `(local, downstream)` |
| `take(~A, ~R, ~down)` | Limit values reaching this stage | `(Nat count, downstream)` |
| `transduce(~A, ~R, ~recipe, config, xs)` | Execute over an owned `List<A>` | Supplied explicitly |

A predicate without configuration can use `Unit` for C. Mapping may change types and produce affine elements. Conventional filtering requires Data elements because it inspects and retains them. Accumulators may be affine.

Composition is nesting reducer adapters or declaring a reusable template, as above. There is no separate runtime `compose` function. `transduce` currently receives a complete reducer description; the initial accumulator is part of the consumer's configuration rather than another independent argument.

Custom consumers can construct `Reducer{C, S, start, step, finish}` directly. Both start and step return `Continue{state}` or `Stop{state}`. Completion runs once even when initialization stops. `reducing` supplies Continue automatically; construct a reducer directly when the consumer must stop early. See [the tests](tests/) for consumer stopping, affine state, type changes, and custom completion adapters.

The sequential driver stops transformation immediately when it observes Stop. This includes `take(0)` at initialization. Releasing an unused owned list tail may still take time. Future strategies may permit bounded speculative pure work; that does not change the ordering or values of results.

## Compiler and verification

This library depends on the [petterik/bend fork, branch `petter/transducers-sept-19`](https://github.com/petterik/bend/tree/petter/transducers-sept-19), which contains the required `bend2/comp.ts` specialization change (commit `b1f9c936`). Use that branch in the sibling `../bend` checkout, or select its compiler with `--bend-main`. The ordinary compiler can run the library semantically, but retains callback construction overhead; the code-generation test intentionally requires the specialization. This is an experimental source-checkout dependency, not a published Bend requirement/version.

```sh
python3 tests/run.py
python3 bench/run.py
```

Both scripts accept `--bend-main /path/to/bend/bend2/main.ts`. They require Python 3, Bun, and a native compiler; the older historical experiment additionally uses Node. They build in temporary directories and do not install dependencies.

The test runner compares emitted JS and native output against each Bend file's `#|` expectations, verifies rejection of affine filtering, checks elimination of callback records, and instruments generated JS to verify mapper counts. Bend reports template specializations as “unsafe annotations”; the library adds no explicit `@unsafe`. Passing these tests is not a formal proof of the implementation.

## Current limits

Range sources, `into_list`, public buffered/flattening operations, parallel collection drivers, and IO drivers are not implemented. Existing sequential pipelines can run inside caller-defined parallel batches; see [CPU/GPU measurements](bench/PARALLEL.md). The completion suite contains test-only buffering adapters to validate the protocol. No allocation-free guarantee is made: JS still constructs state/control objects, and native layout/reuse depends on the compiler.

- [CPU threads and Metal GPU performance](bench/PARALLEL.md)
- [Implementation status, validation, and performance](IMPLEMENTATION.md)
- [Library design](DESIGN.md)
- [Confidence review](CONFIDENCE.md)
- [Implementation priorities](PRIORITIES.md)
- [Historical implementation experiment](experiments/static_reducer/README.md)
