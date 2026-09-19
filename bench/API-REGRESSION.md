# Did the source API regress performance?

The controlled comparison finds **no API regression in these workloads**. The mixed-filter overhead already exists in the pre-range list library. Earlier near-parity results used different inputs and predicates.

## Historical changes

Commit `357a8f4` is the last library state before `4b0dbb1` added ranges and the open source API. The diff leaves `Reducer`, `map`, `filter`, `take`, and their state/control helpers unchanged. It replaces the list driver that finishes internally with a stopping fold that returns Control and an executor that finishes afterward; the new binding also adds the static Reduction description.

The recorded pre-range compiler hash is identical to the compiler used here: `96c997a7d4700a7aaa7bb5a7f27ea810394168cb50fd7f6d267d45156f2e3df3`. Neither a compiler update nor the unadopted case-split experiment participates in this comparison.

## Like-for-like test

```sh
python3 bench/api-regression.py
```

The runner extracts the old library directly from Git into a temporary directory without changing either checkout. Old and current variants use the same generated source values, map, predicate, runtime threshold, take limit, repeats, compiler, native CPU execution, and timing harness. Three samples follow a discarded warmup per process; a second process round reverses variant order, yielding six samples each. Lists include construction and cleanup. Independent Python arithmetic validates every checksum. Generated JS contains neither Reducer nor Reduction records.

[Raw samples and hashes](api-regression-results.json) accompany the medians below. Times are milliseconds per batch; compare columns within a row, not rows with different input counts/work.

| Workload | Old library/API | Current library/API | Handwritten |
| --- | ---: | ---: | ---: |
| Uniform list, cheap map | 7 | 7 | 6.5 |
| Uniform list, 256-round map | 90 | 90 | 90 |
| Ascending list, mixed predicate | 50 | 50 | 15 |
| Generated range, mixed predicate | 331* | 331 | 96 |

*Ranges did not exist in the old revision. This row is a **counterfactual old-style driver**, appended only to the temporary old library: it uses the original reducer API, computes the same `end - remaining` inputs, and calls finish inside the traversal, like the old list driver. It has no Reduction binding. This isolates the new binding/completion boundary; it is not a historical range measurement.

The uniform-list cases reproduce the character of the historical workload, not the full historical parallel/GPU setup. Cheap batches are near timer granularity for small differences. The mixed-list result is the decisive actual historical comparison: the old library is already substantially slower than the handwritten loop on identical irregular inputs.

## Native-code evidence

Using `clang -std=c11 -O3 -S` on the emitted mixed-list C, the entire `_WL_FID_REPEAT` assembly function is textually identical between the old and current API builds. Differences elsewhere include generated helper numbering, not this timed loop. Both library loops branch on predicate acceptance; the handwritten loop uses conditional scalar updates (`cset`/`csinc`). Thus the new source binding did not introduce the observed hot-loop difference in this controlled case.

This aligns with the standalone control-state reproducer, but gives it the missing historical context: the problematic stopping-state shape predates ranges and the API change. The measurements and assembly establish the lack of regression in these cases; they do not prove equality for every pipeline or backend, nor count hardware branch misses.

## Root cause of the apparent regression

The old parallel benchmark used lists of identical ones, and every transformed input passed its predicate. The main parity results also used 256 arithmetic rounds per mapping call. Uniform acceptance gives predictable control flow; expensive mapping makes small control costs relatively unimportant. Even its cheap-map sweep did not test irregular acceptance. This limitation was documented in PARALLEL.md.

The newer generated-range tests changed the source values to ascending integers and eventually added irregular mixed predicates. They also removed list allocation/cleanup costs and used cheap mapping. Those workloads expose control-flow optimization differences that the earlier benchmarks did not exercise. The near-parity selective-filter result was yet another workload, not evidence that the underlying issue had been fixed.

Conclusion: the source API is not the demonstrated cause, and reverting it is not supported by these results. The performance limitation is real but pre-existing. Any future optimization should be judged against both the original uniform workloads and the irregular ones. Historical comparison should have preceded the speculative compiler experiments.
