# Public API release comparisons (2026-09-26)

The public API is `xf.bend`. The older [parallel report](PARALLEL.md) measured
`transduce.bend`, so `parallel.py --api public` now measures the public interface
with the same balanced binary fork tree, direct Bend fold, and materialized
`List.map`/`filter`/`take` control. Each of 16,384 leaves builds 256 ones,
applies eight rounds of a U32 recurrence, filters values above one, and sums
either all 256 results or the first eight. The source construction, traversal,
cleanup, and scheduler are timed; process startup, GPU initialization, compiler,
and printing are not. `take` resets at each leaf.

On this M3 Max, with two reversed-order rounds and ten retained samples per
round, all checksums passed:

| Case | Execution | Public transducer | Direct Bend | Materialized Bend |
| --- | --- | ---: | ---: | ---: |
| Full | CPU 1 thread | 14 ms | 15 ms | 36 ms |
| Full | CPU 8 threads | 2 ms | 2 ms | 5 ms |
| Full | CPU 16 threads | 2 ms | 2 ms | 5 ms |
| Full | Metal GPU | 1 ms | 1 ms | 4 ms |
| Take 8 | CPU 1 thread | 1 ms | 1 ms | 51 ms |
| Take 8 | Metal GPU | 1 ms | 1 ms | 3 ms |

The 1 ms GPU readings are coarse. A second run timed 16 sequential independent
batches per sample on Metal: full consumption took 9 ms public, 8 ms direct,
and 60 ms materialized; take eight took 7.5, 7, and 48 ms. These totals include
16 batch scheduling costs. They support the fused path and show a small
measured gap to direct Bend in this particular GPU layout; they are not
per-frame display times. The [single-batch raw data](public-parallel-20260926.json)
and [repeated-batch raw data](public-parallel-repeat-20260926.json) include
every observation and build metadata. The same harness's legacy default
continues to reproduce the older report.

This public batch with `work(256n, x)` in a closed mapper exceeded the harness's
240-second compilation limit. Eight rounds compiled and ran. That is a
specific compiler/code-shape limitation of the heavier generated fixture;
the measured eight-round result should not be extrapolated to a 256-round
public API GPU workload.

The [C control](manual_c_list.c) uses the same `x + 1` checksum as
[`public_list_map_fold.bend`](public_list_map_fold.bend). Both construct the
input before timing and include traversal and cleanup in the clock interval.
Three C layouts make the representation cost visible: individually `malloc`ed
linked nodes, linked nodes in one arena, and a flat U32 array. The latter has
the same numerical problem but a different representation. One-thread Clang
`-O3` and Bend native results from 48 randomized sessions were:

| Elements | Bend transduce | Bend direct | C linked malloc | C linked arena | C flat array |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 65,536 | 68.5 µs | 58.5 µs | 466 µs | 75 µs | 5 µs |
| 262,144 | 299.5 µs | 397 µs | 1868.5 µs | 304 µs | 19 µs |

The [raw C comparison](manual-c-list-20260926.json) records every sample.
Bend timings vary substantially with size and run, as the earlier
[public List comparison](../docs/current/20260925-PUBLIC-LIST-MAP-FOLD.md)
also shows. The sound result is that the public fold is in the same broad
range as an arena-backed handwritten C linked traversal for this workload.
Separately allocated C nodes pay for `free` per item; the C flat array is
far faster because it is contiguous and vectorizes. The follow-up
[indexed Array comparison](PUBLIC-ARRAY-VS-C.md) uses matched flat inputs,
independent checksums, and a disclosed C data layout and allocator.

Reproduce from this repository:

```sh
python3 bench/manual_c_list.py --sessions 48 --output /tmp/manual-c-list.json
python3 bench/parallel.py --api public --cases batch_long_full_14 batch_long_early_14 --work 8 --samples 10 --rounds 2 --threads 1 8 16 --gpu --out /tmp/public-parallel > /tmp/public-parallel.json
python3 bench/parallel.py --api public --cases batch_long_full_14 batch_long_early_14 --work 8 --repeat 16 --samples 10 --rounds 2 --threads --gpu --out /tmp/public-gpu-repeat > /tmp/public-gpu-repeat.json
```

The GPU runs require a visible Metal device. The timed work has no external
input, but the fixture takes run parameters so the same binary can exercise
different sizes and modes. CPU and GPU were checked on this one Mac; CUDA,
power use, peak memory, and displayed frames were not measured.
