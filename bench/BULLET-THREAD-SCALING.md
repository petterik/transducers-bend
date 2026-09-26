# Bullet Cathedral: CPU thread-count sweep

Changing the native runtime from 1 to 2, 4, or 8 CPU threads **does not speed
up the current Bullet Cathedral programs**. The complete 120-frame medians,
in milliseconds, are:

| Bullet layout | 1 thread | 2 threads | 4 threads | 8 threads |
| --- | ---: | ---: | ---: | ---: |
| [Generated bullets](bullet_cathedral.bend) | 409.24 | 409.14 | 409.12 | 409.25 |
| [Stored records](bullet_cathedral_aos.bend) | 415.44 | 415.63 | 415.38 | 415.35 |
| [Separate field arrays](bullet_cathedral_soa.bend) | **393.08** | **393.05** | **393.00** | **392.94** |

The largest apparent speedup in the table is less than 0.04%. This is within
run-to-run variation, so the defensible conclusion is **no measured scaling**.
The field-array advantage from the [layout experiment](BULLET-LAYOUT-EXPERIMENT.md)
persists at every thread count.

## Why the thread setting has no effect

`--threads N` makes N CPU workers available. Bend schedules work onto those
workers when the program contains explicit parallel calls. These three
fixtures contain no such calls. `run_frames` advances the game state from one
frame to the next, so each frame depends on the previous frame's drone health,
hit history, score, and player shield. Within a frame, the transducers reduce
into one affine framebuffer array, with drawing layers applied in sequence.
The runtime therefore has one active computation to run at a time. Merely
raising the worker count cannot split that computation automatically.

This measurement says nothing about how a deliberately parallel renderer would
scale. A useful next design is to compute the dependent world states in order,
then render independent spatial tiles or frame snapshots with balanced parallel
calls. Each tile should own its output pixels, and tile results can be joined
afterward. That design would need its own correctness and performance checks,
especially around repeated bullet scans, copying state, and shared `+` values.

## Method

The [thread sweep script](bullet_thread_compare.py) compiles all three Bend
files with the pinned fork compiler and Apple Clang 17 `-O3`. For each of the
twelve layout/thread combinations, it runs two warmups and twelve timed native
processes. Conditions are shuffled for each session. All runs use `--gpu off`
and produce the same cumulative checksum, `367602200`.

The internal Bend clock includes 120 sequential simulations, collision
resolution, full 512×512 RGB framebuffers, and a pixel checksum pass for every
frame. It excludes compilation, process startup, PNG/MP4 encoding, and display.
The [raw samples](bullet-thread-comparison.json) include every run, condition
order, source hash, and compiler commit. These are CPU results from the M3 Max;
GPU execution was not measured.

```sh
python3 bench/bullet_thread_compare.py --frames 120 --sessions 12
```
