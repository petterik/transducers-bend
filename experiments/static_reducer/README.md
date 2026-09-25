# Static reducer composition: implementation gate

Historical experiment: this records the pre-specialization candidate and the tradeoff that paused priority #1. Subsequent compiler specialization and the initial library are described in [implementation status](../../docs/foundation/20260919-IMPLEMENTATION.md); the original measurements are retained for comparison.

## What works

`probe.bend` packages configuration/state types and initialization/step/completion callbacks in one reducer description. A template-based mapping adapter wraps that description. A generic list traversal uses its owned state and Continue/Stop control protocol. A named pipeline declares its composition once.

The probe maps +1 over [1, 2, 3], sums the result, and returns 9 on both emitted JavaScript and a native build. It has no explicit @unsafe annotation. Bend reports three unsafe annotations because its CLI also counts template specializations.

This is a representation experiment. It has not completed the affine-accumulator, type-changing map, buffered-completion, configured-filter, or take acceptance cases. Neither priority #1 nor priority #2 is claimed complete.

## Issue found

Supplying a closed reducer description as a template argument does not make all its projections and callback construction compile-time operations. In the emitted JS, the traversal calls the pipeline constructor to obtain the callback for each step. The constructor builds reducer records and closures, including its downstream description. Emitted C also retains callback entry points and the pipeline construction path.

A record-based API is attractive because users express their pipeline once and keep its lifecycle operations consistent. But this candidate does not provide the expected specialization. Passing individual closed callbacks directly as templates avoids much of the observed cost; using that alone as a public API still leaves composition of the complete lifecycle to be solved.

This is evidence against this particular implementation, not proof that every library-only representation has the same limitation. Ordinary template substitution is not a guarantee of arbitrary compile-time evaluation.

## Native comparison

`results.json` records seven samples after one warm-up, rotating execution order, using two million input elements and one CPU thread. Every input is 1; all candidates map +1 and sum to 4,000,000. All build and consume equivalent owned input lists.

| Candidate | Median end-to-end time |
| --- | ---: |
| Composed reducer description | 65.3 ms |
| Direct fused recursion | 32.5 ms |
| Direct template callbacks with Continue/Stop | 34.4 ms |
| Base List.foldl with a closed mapped callback | 33.2 ms |

The candidate was about 1.9 times the direct-callback control-protocol baseline in this run. Timings include process startup, list construction, traversal, and cleanup; they are not isolated callback timings. These are local diagnostic measurements, not a broad benchmark or allocation profile. They do not measure filtering, early stopping, expensive callbacks, or parallel execution.

The direct-callback baseline is important: the difference cannot be attributed solely to adding the Continue/Stop protocol. No precise allocation count or peak-memory claim is made.

## Reproduce

From the repository root, with Python 3, Bun, Node, and a native toolchain available:

```sh
python3 experiments/static_reducer/run.py
```

The default compiler is the sibling `../bend/bend2/main.ts`. Override it when necessary:

```sh
python3 experiments/static_reducer/run.py --bend-main /path/to/bend/bend2/main.ts
```

The script checks the small probe on JS and native, builds four native comparison programs, validates every result, and prints timing samples and compiler diagnostics as JSON. Generated files live in a temporary directory and are removed afterward. `--size` and `--samples` control the diagnostic workload. It does not edit either repository or install dependencies.

## Decision to discuss

Do not freeze the record API or ship a manually duplicated initialization/step/completion chain merely to finish the milestone.

Available directions are:

1. Keep investigating a library-only representation that composes lifecycle operations once and specializes well. This candidate does not establish impossibility.
2. Accept the record representation's measured overhead for a prototype, explicitly relaxing the direct-traversal performance target until a better implementation is found.
3. If a small compiler specialization change is acceptable, investigate whether closed reducer descriptions can be resolved before runtime. This is a scope expansion, not an implemented or proven fix, and does not authorize changing bend.ts.

The recommendation is to retain the performance target and settle the library-only versus compiler-experiment boundary before investing in the full map/filter/take API.
