# Initial implementation: priorities #1–#3

## Public lifecycle extension: keep and partition-all

The semantic extension probe now includes `keep` and `partition_all`. `keep`
consumes an input and emits the optional value returned by its callback, so it
can support affine inputs without the inspect-then-retain restriction of
`filter`. `partition_all` owns a list buffer, emits complete groups during the
source fold, flushes one partial group during completion while downstream is
open, and discards pending output after downstream stops. Width zero stops during
initialization.

`tests/keep_partition.bend` exercises both operations through the independent
tree source, plus affine function values and a reducer that consumes buffered
groups. The full library suite now has 19 positive files and still runs on JS and
native CPU. This is semantic evidence only; no compiler recognizer was added for
either operation and buffered storage remains a real cost.

## Static composition probe

`bench/compiler/STATIC-COMPOSITION.md` records the controlled eager-binding
experiment. A local direct-reducer binding works for representative scalar,
configured, stopping, and buffered pipelines, but replacing the public delayed
recipe breaks the independent tree adapter and retains records in the Array
fixture. The delayed recipe remains until a general compiler staging boundary
can cover built-ins and extensions together.

## Scoped facts boundary

`bench/compiler/SCOPED-FACTS.md` and `test_scoped_facts.py` add a same-layout
exceptional caller to the guarded-loop experiment. The candidate must retain a
guarded loop and its generic fallback while matching the original JS/native
result. This validates the current loop boundary; it does not yet provide the
general typed summary representation needed to re-enable tree specialization.

## Priority #3 follow-up

The library now includes balanced-array, range, string, and list reduction implementations plus `into_list`, `count`, and streaming `cat`/`mapcat`. `transduce(~reduction, config, source)` receives a static `Reduction` description from `over_list`, `over_array`, `over_range`, `over_string`, or a third-party adapter. The description derives input/configuration/output types and binds the pipeline once. There is no closed source enum or registry. [examples/tree.bend](examples/tree.bend) independently adds an affine tree; [EXTENDING.md](EXTENDING.md) documents the public `reducible` binding helper and source-owned stopping-fold contract.

The range is ascending with unit step, empty for reversed/equal bounds. It checks bounds before subtraction and structurally decreases a Nat budget. A source value is computed as `end - remaining` only after checking control; there is no source list or overflowing endpoint increment. Strings traverse Char elements directly. `into_list` accepts affine values and reverses its prepended accumulator once; both new consumers use Unit configuration and start fresh. `count` returns checked Nat. List data is passed directly through `over_list`.

The test suite covers emitted JS and native CPU execution, including affine-filter rejection and the array/mapcat fixture. Seven completion fixtures run through list and range. Boundary tests cover maximum U32 bounds, reversed/empty ranges, a near-full-domain range stopped at zero/one output, and consumer-originated Stop. JS instrumentation observes 16 source-value calls and 13 mapper calls in the range fixture, and nine mapper calls in the list fixture. The source fixture checks the map/inc/sum/range example returns 55 and string character traversal. Reusable conformance checks exercise the list, range, string, and external tree sources; a lifecycle fixture observes exactly 12 starts, 8 steps, and 12 finishes. The external tree supports affine elements and accumulators.

`tests/laws.bend` executes 18,750 bounded assertions per backend over 3,125 small parameter tuples. [LAWS.md](LAWS.md) states their scope, intended laws, the mathematical no-wrap/termination argument, and outstanding formal proof work. These checks are not mechanized proofs and do not establish compiler correctness. No compiler changes or explicit library `@unsafe` were added in this follow-up; the compiler still reports generated templates as unsafe annotations.

The binding delays its reducer recipe and type metadata as closed functions, avoiding repeated eager evaluation at binding boundaries that exhausted the existing specialization fuel. Representative fixtures eliminate both Reducer and Reduction records. The specialization remains bounded: custom callbacks that are bare pattern matchers may retain records, whereas forwarding lambdas allow the current pass to resolve those function heads. The lifecycle fixture uses that form. This is a documented code-generation limitation, not a semantic restriction or claim of universal allocation elimination.

See [range measurements](bench/RANGE.md) for the focused generated-range comparison. Existing CPU/GPU list measurements below are historical evidence; they do not validate this new range driver on GPU. Full compiler project gates remain outstanding for the existing compiler patch.

The remaining sections record the original priorities #1/#2 work.

## Delivered

`transduce.bend` implements a generic static reducer description carrying its configuration/state types and lifecycle callbacks. Adapters derive those types and callbacks together, so users declare the stage chain once. A reusable template can accept different downstream consumers and result types.

The sequential list driver supports identity, map, configured map, configured filter, take, and reduction. Start and step carry owned state in Continue/Stop. Initialization stopping avoids mapper calls; consumer stops propagate upstream. Taking retains downstream control so its own limit is distinguishable from downstream stopping. Completion runs on either outcome.

The API is provisional. It uses nested adapters rather than a runtime pipeline builder. Consumer initialization is part of the reducer configuration. The finite range source and into_list consumer were subsequently added in the priority #3 follow-up above.

## Why compiler specialization was needed for this representation

The historical static-record experiment exposed approximately 2x end-to-end overhead for cheap mapping compared with a direct traversal. The compiler substituted template expressions but still constructed and projected callback records during execution.

The required compiler change is in the [petterik/bend fork on branch `petter/transducers-sept-19`](https://github.com/petterik/bend/tree/petter/transducers-sept-19), commit `b1f9c936`. Its change to `bend2/comp.ts` resolves statically constructed function heads before normal compilation, shared by JS and native emission. It uses bounded call-by-value evaluation, preserves typed arguments and single evaluation of dynamic expressions, and avoids executing foreign/intrinsic calls, unsafe producers, dynamic inputs, or parallel lets during specialization. Applications through a temporary function binding preserve that binding's evaluation order.

Only saturated producers are eligible; a partially applied ordinary function is not recursively expanded just because it returns a function. Both evaluator work and specialization rewrites have finite budgets; unsupported or oversized candidates remain runtime calls. The pass does not change the language checker, its closure-affinity rules, or the runtime. `bend.ts` is unchanged.

Generated code for the representative pipeline has one list traversal and no Reducer records or callback construction. Specialized helper calls and state/control operations may remain. This is not a general collection-fusion pass, nor proof that no other library-only representation could work.

## Validation

The library test suite contains six Bend files, covering:

- Runtime threshold/count configuration, empty inputs, zero/oversized take, and no matches.
- Stage ordering, consecutive takes with independent counts, initial and mid-run consumer stopping, and fresh state on repeated runs.
- Mapping between element types, affine element values, an owned list accumulator, configured mapping, and identity.
- One pipeline declaration reused with scalar and collection consumers.
- Completion exactly once, flushing after upstream take, suppression after downstream stop, nested buffering, and stopping partway through a completion flush.
- Rejection of filtering affine function values.

Positive examples pass both emitted JS and native execution. Generated JS instrumentation counts nine mapper calls across the pipeline cases, confirming no calls after sequential stopping. A code-generation assertion checks that callback records are eliminated.

In the Bend checkout, five focused compiler regressions cover static callback records with an erased field, captured values and dynamic fallback, parallel callback producers, unsafe producers, and an unused computed record field that must prevent static evaluation. Existing over-application coverage caught a temporary-function application bug during development; it was fixed before the successful regression run.

Local regression validation passed 225 selected positive cases from Bend's compile, reg, base, and comptime namespaces. Native executables ran with `--threads 1 --gpu off`; the JS lane used Bun, and unprintable native main types were checked with the interpreter as in the gate. The run also compiled GPU-marked cases, but did not validate GPU execution. Clang's module cache was directed to a writable temporary directory.

Full cluster testing remains unavailable: the `cluster` SSH hostname cannot be resolved here. The repository-size gate is unavailable because `ttok` is not installed. After installing the checkout's locked development dependencies, strict TypeScript checking passes for the compiler and CLI. The full configured TypeScript project still reports missing canvas types in the existing documentation generators. These gaps are not passes; the compiler change remains experimental pending the normal project gates.

## Performance evidence

The [benchmark source](bench/pipeline.bend), [runner](bench/run.py), and [raw samples](bench/results.json) compare equivalent owned inputs and outputs on one native CPU thread. Seven timed runs follow a warm-up for each case, with rotating execution order. Times include process startup, input-list construction, transformation/reduction, and cleanup; compilation is recorded separately.

| Workload | Library | Materialized operations | Handwritten fused traversal |
| --- | ---: | ---: | ---: |
| Cheap map, consume all 2,000,000 inputs | 41.2 ms | 61.7 ms | 40.4 ms |
| Cheap map, take 32 of 2,000,000 inputs | 48.3 ms | 62.6 ms | 48.5 ms |
| Expensive map, take 32 of 100,000 inputs | 32.0 ms | 71.0 ms | 31.7 ms |

The expensive map uses 256 rounds of a nonlinear U32 recurrence. All benchmark variants validate their result. These local samples support retaining this representation: library execution is close to the direct reference for these workloads. They do not establish a universal speedup. In particular, input construction, owned-tail cleanup, and startup dominate early-consumption timings; fewer mapper calls need not imply a proportional wall-time reduction.

The historical single-map experiment was also rerun with specialization: its median was 31.7 ms versus 32.2 ms direct and 30.2 ms for direct template callbacks in that run, compared with the previously recorded 65.3 ms for the record implementation. See [specialized samples](experiments/static_reducer/specialized-results.json).

Allocation traffic and peak live heap were not measured. Absence of intermediate stage collections does not imply absence of per-element wrapper allocation, especially in JS. Native compiler specialization and these timing results do not justify a zero-allocation claim.

## Array and mapcat follow-up

The library now has an ordered `over_array` source for Bend's balanced array
tree, plus streaming `cat` and `mapcat` reducer adapters. `tests/array.bend`
checks structural order, an empty fragment, and stopping in the middle of a
fragment. The [wordscan benchmark](bench/wordscan/README.md) compares a
transduced `Array<Quad>` mapcat/filter/map/reduce pipeline with a materialized
Core Bend list path, a direct fused Bend traversal, and handwritten C,
TypeScript, and Lean twins. Its default report is in
[bench/wordscan/REPORT.md](bench/wordscan/REPORT.md).

The checked-in report records the local CPU medians and the independent
checksum for every successful variant. This supports the expected benefit over
materialization for a map-reduce-shaped workload, while the direct loop remains
a lower-level reference. The host had no available GPU device, and Lean was not
installed, so those columns are marked unavailable rather than inferred. The
benchmark also records the retained static reducer/source records in generated
JS for the richer mapcat composition; this is a current compiler code-shape
observation and not an allocation-free claim.

## CPU threads and GPU follow-up

[Parallel benchmark report](bench/PARALLEL.md) records actual Metal execution and 1/2/4/8/16-thread CPU measurements against equally parallel handwritten and materialized baselines. Balanced independent reductions scale well; a single list remains serial. Long GPU samples give 52 ms library versus 53 ms handwritten for full consumption, and 7 ms for both versus 50 ms materialized with early stopping. Every output matched. Cheap prebuilt lists expose an important limit: unused-tail cleanup can make early stopping slower than full consumption, for both fused implementations. No library/compiler changes were needed. This validates the measured workloads on this M3 Max, not arbitrary pipelines, CUDA, or the unavailable cluster gates.
