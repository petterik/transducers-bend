# Supersampled Julia-set showcase (2026-09-26)

![A 256×256 Julia-set image produced from Bend's transducer pixels](julia-showcase-frame0.png)

The [Bend program](julia_showcase.bend) is self-contained. It enumerates pixel
IDs with `T.Range`, maps each pixel to a four-element sample range, flattens
those ranges with `cat`, runs up to 32 complex iterations per sample, groups
four sample counts with `partition4`, maps each group to a grayscale pixel,
filters pixels below 32, and sums the remaining shades modulo `2^32`. The
frame number moves the Julia parameter. No image or input file is read.

```bend
X.transduce(X.comp2(X.comp5(
  X.map(~U32, ~T.Range, ~pixel_samples),
  X.cat(T.Range.adapter()),
  X.map_with(~U32, ~U32, ~Render, ~sample, config),
  X.partition4(~U32),
  X.map(~(U32 & U32 & U32 & U32), ~U32, ~shade)),
  X.filter(~U32, ~visible)),
  X.sum_rf(), 0, T.range(pixels))
```

The image above comes from the same Bend five-stage path before the filter.
The image export mode collects shades into a List, prints them, and the
[benchmark script](julia_showcase.py) writes a PNG. It checks every exported
pixel against the [handwritten C renderer](julia_showcase.c) before saving.
The picture is a correctness and visual check; image construction and PNG
encoding are outside the checksum benchmark.

At 512×512, there are 262,144 pixels and 1,048,576 sample evaluations per
frame. The frame-zero checksum is **16,843,184** in every implementation.
On an M3 Max, one native CPU thread, Apple Clang 17 `-O3`
`-ffp-contract=off`, 20 randomized process sessions gave these median
**milliseconds for one checksum frame**:

| Bend transducer | Direct Bend | Materialized Bend image List | Handwritten C |
| ---: | ---: | ---: | ---: |
| 37.41 | 37.41 | 38.20 | 15.64 |

The fused pipeline tracks the handwritten Bend loop in this workload. It is
2.39 times the handwritten C time. The materialized path is only 2.1% slower
than the fused path because the 32-step orbit calculation
dominates the List work. Nevertheless, native heap allocation calls inside
the timed interval are **32 fused, 12 direct, and 262,175 materialized** at
512×512. This distinguishes fusion from a speedup claim the workload does
not support. See [raw CPU samples](julia-showcase-20260926.json).

## CPU threads and GPU

`tiled` splits the image into equal numbers of consecutive pixels, and runs
independent leaves in parallel. A leaf uses the same fused pipeline over its
pixel range. The work per leaf still varies because sample orbits escape at
different iterations. The GPU needs more, smaller leaves than the CPU here.

The [parallel benchmark](julia_parallel.py) warms one frame outside each
timed sample, then times eight *different* consecutive frame numbers in the
same process. It validates every warm frame and eight-frame checksum against
C. Twelve samples per configuration gave these median **milliseconds per
computed frame**:

| Width | Serial CPU | 8 CPU threads, 64 tiles | GPU, 64 tiles | GPU, 1,024 tiles | GPU, 4,096 tiles |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 256 | 10.29 | 2.02 | 4.53 | 0.66 | 0.52 |
| 512 | 40.36 | 7.78 | 17.03 | 1.42 | 0.81 |

At 512×512 with 4,096 GPU tiles, this is about **1.29 billion sample
evaluations per second**, or 10 times the eight-thread CPU rate for this
kernel. Those samples have variable orbit lengths. A tile count of 64 leaves
most of the GPU underused, so it is slower than eight CPU threads. See
[raw parallel samples](julia-parallel-20260926.json) for all thread counts,
tile counts, and checksums.

These figures time computation and Bend's scheduling/cleanup. They exclude
process startup, GPU shader compilation, image List construction, PNG output,
and display. They are **not displayed frames per second**. The C comparison
is single-threaded CPU C; it is not a C GPU renderer. Native `U32`/`F32`
values are inline words, but this does not imply every state is unboxed.

## Reproduce

Use the supported sibling `../bend` checkout and an Apple GPU for the GPU
measurements. CPU checks work without a GPU.

```sh
python3 bench/julia_showcase.py --depths 7 8 9 --sessions 20 \
  --image-depth 8 --image-output bench/julia-showcase-frame0.png \
  --output bench/julia-showcase-20260926.json
python3 bench/julia_parallel.py --depths 8 9 --sessions 12 --repeat 8 \
  --output bench/julia-parallel-20260926.json
```

`julia_showcase.py` checks every checksum against C, and also compares all
PNG pixels against C's PPM output. `julia_parallel.py` checks every timed
frame group against separate C frame checksums. Both raw JSON files record
source hashes and compiler commits.
