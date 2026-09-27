---
created_at: 2026-09-27
status: local-cpu-gpu-check-complete
---

# Local Bend benchmark comparison after `Array.walk`

The [raw report](../../bench/upstream-local-regression-20260927.json) compares
an archive of fork HEAD `1b4f641b` before the `Array.walk` change
with the sibling fork containing that change (`cedde735`). The runner is
[`bench/upstream_local_regression.py`](../../bench/upstream_local_regression.py).
Each side compiled the same upstream `bench/runtime/*/main.bend` source into
its own native executable. Each executable ran three times with
`--threads 1 --gpu off`; the order alternated by pair. Process wall time
includes startup. Five upstream checker files each ran three times per
compiler. This local M3 Max comparison does not use the Apple M4 cluster
pins, and a separate oracle process overlapped part of the runtime pass.

Every runtime build and run exited successfully, and the printed output
matched between revisions in all 16 cases. Every checker run exited
successfully and its output matched between revisions. Median runtime ratios
are current divided by baseline:

| Benchmark | Ratio | Benchmark | Ratio |
| --- | ---: | --- | ---: |
| bfs | 1.00 | nbody | 1.00 |
| editdist | 0.87 | queens | 1.00 |
| gameoflife | 1.00 | raytrace | 1.00 |
| hashmap | 1.00 | symreg | 1.01 |
| kmeans | 1.02 | terrain | 1.00 |
| lexer | 0.99 | tree-bitonic | 1.00 |
| mandelbrot | 1.00 | tree-matmul | 1.00 |
| merkle | 1.00 | tree-radix | 1.00 |

`editdist`'s generated C is byte-identical on the two sides (SHA-256
`70bfd4c614a3d90988b0fbe5fc166cdeab894d5ef079adcee1ed1d6b2d4fa59e`).
Its 0.87 timing ratio therefore does not establish a speedup from the new
compiler rule. The other small deviations also need more controlled samples
before being called regressions or improvements. The five checker medians
range from 0.475 to 1.267 seconds on both sides, with at most about 1.4%
relative difference in this three-run sample.

A second [raw report](../../bench/upstream-local-parallel-20260927.json)
ran all 16 runtime cases at `--threads 8 --gpu off`, with two paired samples
per side. Every output matched and every run succeeded. Median current/base
ratios ranged from **0.984 to 1.017**. That range is compatible with ordinary
local timing variation; it does not identify a parallel CPU regression.

The sequential and parallel reports do not measure the cluster's
resident-memory gate or timing under isolated host load. A first single-run
Metal pass had a noisy `queens` result, so the full 16-case GPU pass was
repeated with **five paired runs per side**. The
[GPU raw report](../../bench/upstream-local-gpu-paired-20260927.json)
shows every build and run succeeded and every printed output matched.
Median current/base GPU ratios ranged from **0.996 to 1.011**. The initial
[single-run report](../../bench/upstream-local-gpu-20260927.json) is retained
to make that decision auditable. These are local Metal process wall times,
including startup, not the M4 cluster's isolated GPU-cell measurements.

The
[full compiler correctness gate](20260927-ARRAY-WALK-INTEGRATION.md)
and one Metal `Array.walk` fixture cover additional correctness paths; they
are different experiments.

Recreate the archived compiler and rerun the local comparisons from this
repository root:

```sh
mkdir -p /tmp/bend-baseline-20260927
git -C ../bend archive 1b4f641b9fea9b48fee37fc10b0a07977bba6e7d | tar -x -C /tmp/bend-baseline-20260927
python3 bench/upstream_local_regression.py --baseline /tmp/bend-baseline-20260927 --runtime-mode seq --runs 3 --output /tmp/bend-seq.json
python3 bench/upstream_local_regression.py --baseline /tmp/bend-baseline-20260927 --runtime-mode parallel --skip-checker --runs 2 --output /tmp/bend-parallel.json
python3 bench/upstream_local_regression.py --baseline /tmp/bend-baseline-20260927 --runtime-mode gpu --skip-checker --runs 5 --output /tmp/bend-gpu.json
```
