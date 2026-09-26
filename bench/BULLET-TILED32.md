# Bullet Cathedral: 32 render-task experiment

The [tiled Bend variant](bullet_cathedral_tiled32.bend) keeps the eight-frame
batch, then splits each frame into four horizontal 512×128 tiles. Its balanced
fork tree exposes **32 independent tile render tasks**. Each tile owns a
65,536-pixel Bend Array, runs the same ordered background, bullet, drone, hit,
icon, and HUD drawing stages, and returns a pixel checksum. The four tile
checksums add to the full-frame checksum. The timed path does not assemble a
full-frame image.

The tiles use the new `X.filter_with` stage to pass the tile number into
sprite and pixel predicates without a runtime predicate closure. Bullets whose
sprites cannot intersect a tile are rejected before expanding them into
pixels. Every tile still traverses the bullet pool and owns a cloned copy of
its seven field arrays; these costs are visible in the measured result.

## Measured result

On the M3 Max, median time to simulate, render, and checksum 120 frames was:

| CPU threads | Eight full-frame tasks | 32 tile tasks |
| ---: | ---: | ---: |
| 1 | 393.97 ms | 425.74 ms |
| 2 | 224.58 ms | 251.47 ms |
| 4 | 140.85 ms | 178.59 ms |
| 8 | **95.77 ms** | 114.65 ms |
| 16 | 98.14 ms | 115.12 ms |

The 32-task version is **20% slower** than eight full-frame tasks at the best
thread count for each. Moving it from 8 to 16 threads does not improve its
median. The extra tasks increase available parallelism, but the current tiling
also duplicates bullet traversal and array copies. This experiment does not
separate those costs from tile imbalance or shared-memory contention.

The result argues against increasing the tile count in this implementation.
A useful next experiment would prepare read-only sprite spans for each tile
without materializing thousands of `Sprite` records, then measure per-tile
work and the cost of preparing those spans. Bend's current scheduler assigns
forked tasks once, so balanced tile costs remain important.

## Checks and reproduction

The [benchmark script](bullet_tiled32_bench.py) compiled both sources with the
pinned Bend fork and Apple Clang 17 `-O3`. It checked the cumulative checksum
for **every prefix from zero through 120 frames**, which also checks each
frame's contribution. It verified final accepted hits (`405`) and player
shield (`214`). Every timed run produced cumulative checksum `367602200`.
The script used three warmups and 20 randomized sessions per condition, with
one native process per sample and `--gpu off`. The [raw data](bullet-tiled32.json)
includes all samples, condition order, source hashes, and compiler commit.

```sh
python3 bench/bullet_tiled32_bench.py --frames 120 --sessions 20
```

The Bend clock includes sequential state updates, collision handling,
tile rendering, and pixel checksums. It excludes compilation, process startup,
video encoding, and display. The single-frame export path still uses the
original full-frame renderer.

At [3840×2160](BULLET-4K-TILED16.md), two larger tiles per frame did improve
the batch time by 13.5% over eight full-frame tasks.
