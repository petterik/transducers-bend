# Array mapcat benchmark report

The default local run used `ARRAY_DEPTH=8`, `BATCH_DEPTH=10`, two batches per
timed sample, and 32 normalization rounds per lane. Every variant returned
checksum `1287990074` for every sample. Bend timings are persistent
process `IO.now` medians after one discarded warm-up; the C and TypeScript
figures include process startup and are therefore a separate reference.

| Variant | Bend CPU 1 | Bend CPU 16 | Bend GPU | External CPU 1 |
| --- | ---: | ---: | --- | ---: |
| Transduced (`over_array` + `mapcat`) | 62 ms | 7 ms | unavailable: no device | — |
| Core Bend materialized list | 68 ms | 9 ms | unavailable: no device | — |
| Direct fused Bend | 50 ms | 6 ms | unavailable: no device | — |
| Handwritten C | — | — | — | 2.83 ms |
| Handwritten TypeScript | — | — | — | 93.12 ms |
| Handwritten Lean | — | — | — | unavailable: `lean` not installed |

The useful within-Bend result is that streaming transduction is about 9% faster
than the materialized Core Bend list path at one thread. The CPU-16 medians are
7 ms versus 9 ms, but the one-millisecond clock makes that smaller difference
less certain. The transduced path remains within roughly 24% of the direct
fused Bend loop at one thread for this mapcat/filter/map workload. The direct Bend and C loops still define a
lower-level ceiling; this benchmark does not claim that the public transducer
API beats handwritten C. The richer mapcat composition currently leaves four
static reducer/source records in emitted JS; that is a compiler/code-shape
observation, not a correctness failure.

The host had no available GPU device, so the GPU column records an attempted
run rather than a performance result. Re-run the benchmark on a Metal host to
populate that mode. Raw samples, compiler/library hashes, checksums, and the
artifact directory are in [results.json](results.json).

Reproduce with:

```sh
python3 bench/wordscan/run.py --output bench/wordscan/results.json
```
