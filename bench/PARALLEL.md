# CPU threads and Metal GPU performance

The current library scales when the caller supplies balanced independent work. It does not parallelize one list reduction. The benchmark uses the same explicit binary fork tree for the library, a handwritten fused traversal, and materialized map/filter/take/fold.

Each leaf builds and owns its own list of 64 inputs, maps a nonlinear U32 recurrence, filters values above 1, takes either 64 or 8 outputs, and sums. A batch contains 4,096 or 16,384 independent leaves. `take` resets at each leaf; this is not a parallel implementation of a global ordered take. The serial control uses one 100,000-element list.

## Method

Measured on an Apple M3 Max, 16 CPU cores, 40 GPU cores, 128 GiB unified memory. The checkout's compiler specialization is enabled. Native binaries include Metal code and call `batch!`; CPU modes use `--gpu off`, while the GPU mode uses `--gpu 1GB`, which fails if no GPU is available rather than silently falling back. There is no CPU fork before the bang in a timed evaluation.

`IO.now` brackets each computation inside a persistent process. Timings include source construction, transformation, reduction, scheduling, and owned-tail cleanup. They exclude compiler, process, GPU initialization and printing time. One warm-up is discarded per process. Two rounds run the variants/modes in opposite orders. The main sweep retains seven samples per round; the heavier sweep retains five. Every result is checked against independently calculated U32 arithmetic. Generated library JS is checked for surviving Reducer records. These checks establish the benchmark's results, not every library lifecycle behavior on GPU.

The clock has millisecond resolution. Values around 0–3 ms cannot establish small relative differences; zero means below clock resolution, not free work. The heavier workload increases mapping from 256 to 2,048 rounds to make device comparisons more meaningful. The computer was not reserved exclusively for benchmarking; raw samples retain scheduling/background-load noise.

## CPU scaling

For 16,384 lists consuming all inputs, with 256 mapping rounds:

| CPU threads | Library | Handwritten | Materialized |
| --- | ---: | ---: | ---: |
| 1 | 392 ms | 393 ms | 402 ms |
| 2 | 199 ms | 199 ms | 204 ms |
| 4 | 100 ms | 100 ms | 102.5 ms |
| 8 | 51 ms | 50.5 ms | 52 ms |
| 16 | 36 ms | 36.5 ms | 37.5 ms |

The library scales about 7.7x at eight threads and 10.9x at sixteen. Its overhead relative to the handwritten pipeline is negligible at this resolution for this workload. The CPU is heterogeneous, and sixteen-thread runs are more variable; linear scaling to sixteen is not a requirement.

Taking eight values per leaf reduces the library's one-thread median to 57 ms, versus 406 ms materialized and 58 ms handwritten. At sixteen threads these are 7, 40.5, and 7 ms. Construction and cleanup remain, so stopping after one eighth of the items need not reduce total time by exactly eight.

One two-thread early-take block slowed markedly during the reverse-order round (library samples 51–64 ms versus 29 ms in the first round, with a neighboring materialized block also slowing). This outlier is retained in the main raw results. A dedicated two-thread repeat returned medians of 29 ms library, 30 ms handwritten and 210 ms materialized. The slowdown did not reproduce as library-specific overhead.

## Serial control

A single full list takes 38 ms for both library and handwritten traversal at every tested CPU thread count. On GPU it takes 577 ms for the library and 590.5 ms handwritten. Early stopping takes roughly 1 ms on CPU but 134 ms on GPU for both fused variants: allocating and releasing one long owned list on a single device lane is a poor GPU workload.

This is expected, and is an important limit: `!` selects a device; it does not create independent tasks. GPU throughput needs a balanced fork tree. A faster fused sequential loop is not automatically a useful GPU kernel.

## Metal GPU

The 256-round batches finish in about 1–2 ms; the timer is too coarse to interpret their ratios. Raising work to 2,048 rounds gives full-batch medians of 8 ms library, 7 ms handwritten, and 7.5 ms materialized. A further GPU-only sweep uses 16,384 rounds to reduce timer quantization (four rounds, ten samples each, alternating order):

| GPU workload, 16,384 independent lists | Library | Handwritten | Materialized |
| --- | ---: | ---: | ---: |
| Full consumption, 64 values/list | 52 ms | 53 ms | 54.5 ms |
| Early stop, 8 of 64 values/list | 7 ms | 7 ms | 50 ms |

These results show no substantial library overhead for this compute-heavy workload, and about 7x benefit from early stopping versus materialization. They do not establish exact percentage differences between the fused implementations: individual GPU timings still drift across rounds. At 2,048 work rounds, early stopping also yields 2 ms library/handwritten versus 10 ms materialized.

The heavier CPU sweep was noisier than the initial thread sweep (including a 7,261 ms materialized sample alongside typical values near 3,500–4,000 ms). Its raw CPU timings are retained, but should not be used for precise overhead estimates.

## Cheap mapping and the cleanup limitation

A separate sweep uses one recurrence round and 256 input values per leaf, still with 16,384 independent lists:

| Workload / execution | Library | Handwritten | Materialized |
| --- | ---: | ---: | ---: |
| Full / CPU 1 | 10 ms | 9 ms | 36.5 ms |
| Full / CPU 16 | 2 ms | 2 ms | 7.5 ms |
| Full / GPU | 2 ms | 2 ms | 5.5 ms |
| Take 8 / CPU 1 | 35.5 ms | 39 ms | 60.5 ms |
| Take 8 / CPU 16 | 6 ms | 8 ms | 14 ms |
| Take 8 / GPU | 2 ms | 2 ms | 4 ms |

Fusion helps versus materialization, but stopping early is **slower than full consumption on CPU** here, for both fused implementations. Generated code uses the runtime's generic `term_sink` to release the unused list tail, whereas full traversal frees each node directly. The results are consistent with cleanup dominating the cheap early-stop workload; its exact share was not separately profiled. Consequently, fewer mapper calls are not a wall-time guarantee. The planned generated range/source driver would avoid building and disposing of an unused prebuilt list tail; that remains future work, not a performance claim already measured.

## Reproduce

From the library repository:

```sh
python3 bench/parallel.py > /tmp/parallel.json
python3 bench/parallel.py --out /tmp/transduce-heavy --cases batch_full_14 batch_early_14 --work 2048 --samples 5 --threads 1 8 16 > /tmp/heavy.json
python3 bench/parallel.py --out /tmp/transduce-device --threads --cases batch_full_14 batch_early_14 --work 16384 --samples 10 --rounds 4 > /tmp/device.json
python3 bench/parallel.py --out /tmp/transduce-cheap --cases batch_long_full_14 batch_long_early_14 --work 1 --threads 1 16 > /tmp/cheap.json
python3 bench/parallel.py --out /tmp/transduce-repeat --cases batch_early_14 --threads 2 --no-gpu > /tmp/repeat.json
```

Run these sequentially, not concurrently. `--bend-main` selects another compiler checkout. `--no-gpu` skips device execution; these bang-containing programs still require the native GPU build toolchain. Generated Bend/C/JS/native/GPU artifacts and a checkpoint `results.json` remain under `--out` (default `/tmp/transduce-parallel-build`) for inspection. GPU runs use a 1 GiB heap cap.

Raw results: [main sweep](parallel-results.json), [heavier sweep](parallel-heavy.json), [long GPU samples](parallel-device.json), [cheap mapping](parallel-cheap.json), [two-thread repeat](parallel-repeat.json). All measured outputs matched their expected result. No library or compiler edits were necessary for these tests.

## Interpretation and limits

The evidence supports retaining the specialized reducer representation for these CPU workloads and for balanced GPU batches. It does not justify automatic parallel reduction, global parallel take, a fixed chunk size, or a universal speedup. The existing sequential semantics remain useful inside independent jobs; an eventual parallel driver needs explicit rules for combining accumulators and handling ordered/stateful stages.

The measured inputs are intentionally uniform: every input is 1 and every transformed value passes the predicate. This isolates scheduling, fusion and stopping, but does not measure divergent predicates, uneven list lengths, shared inputs/refcount contention, list-valued results, completion-heavy adapters, or transfer costs on discrete GPUs. Only Metal on this machine was tested; CUDA and the project's cluster gates remain unverified. Memory consumption was not profiled.
