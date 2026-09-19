# Generated range measurements

Measured on the local M3 Max, using the sibling Bend fork's compiler and the open static reduction API. [Raw samples](range-results.json) include the compiler hash, build times, emitted code sizes, and every retained timing. No new compiler change was made.

```sh
python3 bench/range.py
# Optional report file; build artifacts otherwise live in a temporary directory:
python3 bench/range.py --output /tmp/range-results.json
```

The library pipeline and handwritten loop both generate U32 values, map, filter values above one, take, and sum with U32 wrapping. Cheap mapping is `(x XOR (x >> 13)) + 1`; expensive mapping uses 256 nonlinear arithmetic rounds. An independent Python implementation validates every batch checksum. Both variants use one native CPU thread with GPU off.

Timing uses IO.now inside a persistent process and excludes startup. Each process discards its first sample and retains seven; two process rounds reverse variant order, yielding 14 samples per variant/case. The table reports whole-batch medians, not single-call latency. Early-stop cases vary their starting value with the repetition index modulo 65536, preventing repeated constant answers from being folded away. Full-consumption starts at zero.

| Workload | Transductions per sample | Library batch | Handwritten batch |
| --- | ---: | ---: | ---: |
| Cheap map, consume to end 2,000,000 | 32 | 49 ms | 33 ms |
| Cheap map, take 32, end 2,000,000 | 1,000,000 | 25 ms | 17 ms |
| Cheap map, take 32, end 4,294,967,295 | 1,000,000 | 25.5 ms | 19 ms |
| Expensive map, take 32, end 2,000,000 | 1,000 | 11 ms | 11 ms |

The similar early-stop times at very different end bounds support bounded production without allocating or cleaning up an unused range tail. Exact source/mapper counts are separately checked by the test suite. Cheap work exposes library overhead versus the handwritten loop; the implementation does not achieve universal performance parity. Expensive mapping dominates both variants in these samples.

Generated JS for each library benchmark contains neither Reducer nor Reduction records. That establishes elimination of those descriptions for these workloads, not absence of control/state allocations or helper-call costs. Compilation takes roughly 0.45 seconds for library programs and 0.39 seconds for direct programs in this run; emitted sizes are in the snapshot.

Millisecond resolution, optimizer behavior, warm caches, and workload selection limit interpretation. Early results with constant inputs were below timer resolution, so the runner uses varying inputs and longer batches. No speedup ratio is inferred from zero-duration samples. The retained snapshot is from the final methodology and API.

This is a generated-source comparison. Historical prebuilt-list timings in [PARALLEL.md](PARALLEL.md) and [../IMPLEMENTATION.md](../IMPLEMENTATION.md) include different source and cleanup costs and must not be treated as directly comparable. No new range GPU/CUDA tests, allocation profiling, or peak-memory measurements were performed.
