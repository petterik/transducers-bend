# Array mapcat benchmark report

This run used `ARRAY_DEPTH=8`,
`BATCH_DEPTH=10`, `REPEATS=2`,
and `NORMALIZE_ROUNDS=32`. Every successful
variant returned checksum `1287990074`. Bend timings are
persistent-process `IO.now` medians after one discarded warm-up; the C and
TypeScript figures include process startup and are therefore a separate
reference.

| Variant | Bend CPU 1 | Bend CPU 16 | Bend GPU | External CPU 1 |
| --- | ---: | ---: | --- | ---: |
| Transduced (`over_array` + `mapcat`) | 62.00 ms | 8.00 ms | 17.00 ms | — |
| Core Bend materialized list | 68.00 ms | 9.00 ms | 39.00 ms | — |
| Direct fused Bend | 51.00 ms | 6.00 ms | 7.00 ms | — |
| Handwritten C | — | — | — | 2.79 ms |
| Handwritten TypeScript | — | — | — | 93.57 ms |
| Handwritten Lean | — | — | — | unavailable: lean not found |

The public transduced path is 9% faster than the materialized Core Bend list path at one thread in this run. It is 22% above the direct fused Bend loop at one thread. The direct Bend and C loops are lower-level reference points;
this benchmark does not claim that the public transducer API beats handwritten
C. The emitted transduced JavaScript contains 5 static reducer/source
records; that is a compiler/code-shape observation, not a correctness failure.

The benchmark checksum validates lane membership, wrapping arithmetic, and
batch partitioning. It is a sum, so it cannot by itself prove traversal order;
the ordered `over_array` conformance test covers that separately.

The host exposed Metal and the transduced GPU median was 17.00 ms. Lean was `unavailable: lean not found`. Raw
samples, compiler/library hashes, checksums, and the artifact directory are in
[results.json](results.json).

Reproduce with:

```sh
python3 bench/wordscan/run.py --array-depth 8 --batch-depth 10 --repeats 2 --normalize-rounds 32 --samples 5 --threads 16 --gpu-memory 1GB --output bench/wordscan/results.json
```
