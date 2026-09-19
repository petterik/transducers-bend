# Initial implementation: priorities #1 and #2

## Delivered

`transduce.bend` implements a generic static reducer description carrying its configuration/state types and lifecycle callbacks. Adapters derive those types and callbacks together, so users declare the stage chain once. A reusable template can accept different downstream consumers and result types.

The sequential list driver supports identity, map, configured map, configured filter, take, and reduction. Start and step carry owned state in Continue/Stop. Initialization stopping avoids mapper calls; consumer stops propagate upstream. Taking retains downstream control so its own limit is distinguishable from downstream stopping. Completion runs on either outcome.

The API is provisional. It uses nested adapters rather than a runtime pipeline builder. Consumer initialization is part of the reducer configuration. The planned finite range source and into_list convenience remain priority #3.

## Why compiler specialization was needed for this representation

The historical static-record experiment exposed approximately 2x end-to-end overhead for cheap mapping compared with a direct traversal. The compiler substituted template expressions but still constructed and projected callback records during execution.

The accompanying change in the sibling Bend checkout's `bend2/comp.ts` resolves statically constructed function heads before normal compilation, shared by JS and native emission. It uses bounded call-by-value evaluation, preserves typed arguments and single evaluation of dynamic expressions, and avoids executing foreign/intrinsic calls, unsafe producers, dynamic inputs, or parallel lets during specialization. Applications through a temporary function binding preserve that binding's evaluation order.

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

## CPU threads and GPU follow-up

[Parallel benchmark report](bench/PARALLEL.md) records actual Metal execution and 1/2/4/8/16-thread CPU measurements against equally parallel handwritten and materialized baselines. Balanced independent reductions scale well; a single list remains serial. Long GPU samples give 52 ms library versus 53 ms handwritten for full consumption, and 7 ms for both versus 50 ms materialized with early stopping. Every output matched. Cheap prebuilt lists expose an important limit: unused-tail cleanup can make early stopping slower than full consumption, for both fused implementations. No library/compiler changes were needed. This validates the measured workloads on this M3 Max, not arbitrary pipelines, CUDA, or the unavailable cluster gates.
