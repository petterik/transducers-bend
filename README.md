# transduce-bend

A Bend library for composing pure data transformations without intermediate stage collections. It provides an owned reducer protocol, extensible source-owned reduction, map/filter/keep/take/partition-all/mapcat, and sum/count/ordered-list consumers. Built-in sources are lists, balanced arrays, finite ranges, and strings; other modules can add sources without changing this library.

## Public transducer API

[`xf.bend`](xf.bend) exposes Clojure-ordered
`transduce(xf, rf, initial, source)` and `into(destination, xf, source)`.
Stages compose with `comp2` through `comp5`. A stage value owns its runtime
settings and is used once; wrap a stage constructor in a zero-argument function
when it needs to be recreated. A source supplies its own reduction loop through
a `.source` companion, and a destination supplies a reducer through `.destination`.
Lists, Arrays, finite ranges, strings, `Vec`, and `VecMaybe` are built in.

```python
import Base
import ./xf.bend as Xf
import ./transduce_core.bend as T

def inc(x: U32) -> U32:
  U32.inc(x)

def main() -> U32:
  Xf.transduce(Xf.comp2(
    Xf.map(~U32, ~U32, ~inc), Xf.take(~U32, 5n)),
    Xf.sum_rf(), 0, T.range(10))
# 15
```

The compiler selects source and destination companions. This requires the
[`codex/transducer-no-stop` branch](https://github.com/petterik/bend/tree/codex/transducer-no-stop)
of the `petterik/bend` fork, based on `bendlang/main`. The tested commit is
`1b4f641b9fea9b48fee37fc10b0a07977bba6e7d`. Put both repositories in
the same parent directory so the library's scripts find `../bend`:

```sh
git clone https://github.com/petterik/bend.git bend
git -C bend checkout codex/transducer-no-stop
git clone https://github.com/petterik/transducers-bend.git transduce-bend
cd transduce-bend
python3 tests/run.py
python3 tests/public_differential.py
bun experiments/affine_xf/check_no_stop_cache.ts
```

The branch adds checked companion selection and a general
uninhabited-match-arm optimization. Fresh sibling clones at the pinned
compiler commit passed the three commands above on this machine.
The associated reducer permit in
[`transduce_core.bend`](transduce_core.bend) is `Empty` for a total pipeline
and `Unit` for a pipeline that can stop. Sources remain generic and return an
opaque accumulator; they cannot fabricate a downstream stop. `take` and
`partition_all` can stop, while `map`, `filter`, `keep`, and `mapcat` inherit
the downstream permit. `mapcat` drives the reducible fragment returned by its
mapping function and preserves a stop from the middle of that fragment.

`into(List, ...)` prepends, following Clojure's `conj` order. For encounter
order, collect into [`Vec`](vec.bend) or [`VecMaybe`](vec_maybe.bend).
`Vec<T: Data>` is backed by Bend Array and uses a caller-provided filler for
unused capacity; `VecMaybe<T: Data>` stores optional slots when no filler is
available. Both are sources and destinations. `Vec.with_capacity` and
`VecMaybe.with_capacity` return `None` above the conservative 2²³-element
initial-reservation limit; dynamic growth follows Bend Array's runtime limits.
The constructors of both Vec types are currently visible across modules, so
callers should use their functions rather than fabricate inconsistent records.

`partition_all` produces ordered List chunks and allocates those chunks. A
consumer that retains chunks must pay that cost, and even a consuming fold may
not remove it. `mapcat` over a List-producing callback similarly allocates the
fragment; a custom source can emit values directly. See the
[public mapcat test](tests/mapcat_public.bend) and the
[no-stop integration report](docs/current/20260925-NO-STOP-PUBLIC-INTEGRATION.md).

For an owned List map-and-sum, the public transducer ran at approximately
handwritten fused-fold speed in local native measurements. At 65,536 items,
the medians were 68 µs for a direct Bend fold, 66 µs for `transduce`, and
252 µs for `List.map` followed by `List.foldl`. The direct and public paths
made the same number of timed native allocation calls; `List.map` made one
extra call per item. Timing varies by compiled layout and machine state, so
these are local results, not a universal speed guarantee. See the
[public List comparison](docs/current/20260925-PUBLIC-LIST-MAP-FOLD.md) for
the fixture, raw samples, other sizes, and limitations.

## Legacy reducer API

The original explicit reducer API remains in [`transduce.bend`](transduce.bend)
for historical examples and benchmarks. The earlier value API is
[`xf_legacy.bend`](xf_legacy.bend). The [legacy API guide](docs/archive/20260925-LEGACY-REDUCER-API.md)
records their spelling; new pipelines should use `xf.bend`.

## Compiler and verification

The public value API targets the `codex/transducer-no-stop` branch of the
`petterik/bend` fork, based on `bendlang/bend:main`. It includes
checked template inference, owner companions, bounded static callback
specialization, and conservative unreachable-match-arm elimination. `bench/compiler/prepare_static.py` remains a historical,
isolated experiment against upstream; it does not change `../bend`.

```sh
python3 tests/run.py
python3 tests/public_differential.py
bun experiments/affine_xf/check_no_stop_cache.ts
python3 experiments/affine_xf/measure_opaque_source.py \
  --bend-main ../bend/bend2/main.ts --output /tmp/opaque-source.json
```

`tests/run.py` uses the supported sibling compiler branch by default. The
regular run keeps code-shape gates enabled and currently passes 47 JS/native
fixtures; `--semantic-only` skips only those code-shape gates. These scripts
require Python 3, Bun, and a native compiler. They build in temporary
directories and do not install dependencies.

The test runner compares emitted JS and native output against each Bend file's `#|` expectations, verifies rejection of affine filtering, checks elimination of callback records, and instruments generated JS to verify source/mapper counts. It includes 18,750 bounded law checks per backend. [Laws and invariants](docs/foundation/20260919-LAWS.md) distinguish tested properties, mathematical reasoning, and outstanding formal proof work. Bend reports template specializations as “unsafe annotations”; the library adds no explicit `@unsafe`. Passing these tests is not a formal proof of the implementation.

## Current limits

`partition_all` is the first public buffered transformation: it owns a group
buffer, flushes one partial group during completion, and honors downstream
stopping. Arbitrary buffered transformations, parallel collection drivers, and
IO drivers are not implemented. The legacy `cat` consumes List fragments, while
public `mapcat` drives any fragment type with a supplied opaque-accumulator fold; fragment construction remains a real
cost when the callback builds a collection. Existing sequential
pipelines can run inside caller-defined parallel batches; see [CPU/GPU
measurements](bench/PARALLEL.md) and the [array mapcat benchmark](bench/wordscan/README.md).
No allocation-free guarantee is made: JS still constructs state/control objects,
and native layout/reuse depends on the compiler.
On this machine, a public total Array fold matches handwritten native code.
An independent branching fold also matches direct code in one layout, while
mirroring call order can shift about 12% between the public and prototype
paths. See the [Branch layout reassessment](docs/current/20260925-BRANCH-LAYOUT-REASSESSMENT.md);
there is no established transducer-specific Branch penalty.
CLI value mode, generated JS, and native code all handle explicit `Source`
witnesses and raw collections on the tested compiler branch. The
[integration report](docs/current/20260925-NO-STOP-PUBLIC-INTEGRATION.md)
records the measurements and reproduction steps.

The repository is licensed under [MIT](LICENSE).

- [CPU threads and Metal GPU performance](bench/PARALLEL.md)
- [Generated range performance](bench/RANGE.md)
- [Current design and work plan](docs/current/20260920-DESIGN-WORK-PLAN.md)
- [Implementation repair plan](docs/current/20260920-IMPLEMENTATION-REPAIR-PLAN.md)
- [Adversarial implementation review](docs/review/20260920-IMPLEMENTATION-REVIEW.md)
- [Laws, invariants, and proof status](docs/foundation/20260919-LAWS.md)
- [Implementation status, validation, and performance](docs/foundation/20260919-IMPLEMENTATION.md)
- [Library design](docs/foundation/20260919-DESIGN.md)
- [Confidence review](docs/foundation/20260919-CONFIDENCE.md)
- [Implementation priorities](docs/current/20260919-PRIORITIES.md)
- [Historical implementation experiment](experiments/static_reducer/README.md)
