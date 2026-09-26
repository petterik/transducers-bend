# Bullet Cathedral: parallel frame batches

The [parallel Bend source](bullet_cathedral_parallel_frames.bend) computes the
same Bullet Cathedral sequence as the [field-array source](bullet_cathedral_soa.bend).
Each frame's collisions update drone health, accepted hits, score, and player
shield, so state advances in frame order. After each update, the program takes
a snapshot of that frame's world. Eight snapshots render into eight independent
512×512 RGB framebuffers through the existing transducer drawing code.
Balanced `render_two`, `render_four`, and `render_eight` calls expose parallel
work to Bend's CPU scheduler. While a batch renders, the next eight world
states are prepared. A short final batch uses the sequential path.

This needs no spatial tiling or change to the drawing transducers. Each
snapshot clones the 256-element health array; the hit history is shared through
Bend's reference-counted list. Every renderer owns its framebuffer. The
parallel variant's benchmark mode is the batch program; its single-frame image
export path still uses the original renderer.

## CPU results

On an M3 Max, the median time to simulate, render, and checksum all 120 frames
was:

| CPU threads | Serial field arrays | Parallel frame batches | Speedup vs serial, 1 thread |
| ---: | ---: | ---: | ---: |
| 1 | 393.35 ms | 393.79 ms | 1.00× |
| 2 | 393.10 ms | 224.51 ms | 1.75× |
| 4 | 393.07 ms | 140.84 ms | 2.79× |
| 8 | 393.31 ms | **95.68 ms** | **4.11×** |

At eight threads, 120 / 0.095676 s is about **1,254 computed frames/s**, or
**0.797 ms per frame averaged over the 120-frame batch**. Individual frame
latency is a different measurement: each frame's simulation depends on the
previous frame, and the eight renderers finish at different times. The timing
includes simulation, collisions, full RGB framebuffers, and pixel checksums.
It excludes compilation, process startup, PNG/MP4 encoding, and display. The
video in the main showcase is deliberately encoded for 30 FPS playback.

Increasing `--threads` alone did not speed up the original serial program.
The calls in this variant give the runtime independent work. The speedup is
less than 8× because state updates remain ordered and the workers share CPU
and memory resources; these measurements do not isolate those costs.

## Correctness and reproduction

The [benchmark script](bullet_parallel_frames_bench.py) compiles both Bend
sources with the pinned Bend fork and Apple Clang 17 `-O3`. It checks the
cumulative checksum for **every prefix from zero through 120 frames**, which
also checks each frame's contribution, and verifies the final accepted-hit
count (`405`) and player shield (`214`). All conditions produce cumulative
checksum `367602200` at 120 frames. It then runs three warmups and 20 timed
processes for each of the eight variant/thread combinations, shuffled in each
session. All runs use `--gpu off`. The [raw JSON](bullet-parallel-frames.json)
records samples, order, source hashes, and compiler commit.

```sh
python3 bench/bullet_parallel_frames_bench.py --frames 120 --sessions 20
```

This experiment measures **batch throughput**, not a real-time presentation
loop. Showing the rendered images on screen or encoding the movie would require
additional work beyond this timed path.
