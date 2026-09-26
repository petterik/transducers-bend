# Starfield: a transformation-heavy visual showcase

![A deterministic 256×256 frame rendered from Bend transducer pixels](starfield-frame0.png)

This renderer needs no input file. Each frame scrolls a deterministic field
of tiny stars. A 32×32 subpixel cell has one star center and brightness,
selected by an integer hash. Four subpixels produce one grayscale pixel. The
integer kernel is deliberately short so moving and grouping the samples is a
meaningful share of the work. The [Bend source](starfield_showcase.bend) and
[handwritten C control](starfield_showcase.c) implement the same hash,
coordinates, sample intensity, average, visibility test, and checksum.

The fused path is a public-API pipeline:

```bend
X.transduce(X.comp2(X.comp5(
  X.map(~U32, ~T.Range, ~pixel_samples),
  X.cat(T.Range.adapter()),
  X.map_with(~U32, ~U32, ~Render, ~sample, config),
  X.partition4(~U32),
  X.map(~(U32 & U32 & U32 & U32), ~U32, ~shade)),
  X.filter(~U32, ~visible)),
  X.sum_rf(), 0, T.range_between(begin, end))
```

`pixel_samples` maps each pixel ID to four sample IDs in a finite range;
`cat` flattens them. `partition4` groups four sample intensities in a tuple
and emits one pixel shade. The filter keeps nonzero shades for the checksum.
All of these steps are fused into a single traversal. The direct Bend loop
computes the same four samples for each pixel without transducers. The C
control does the same, with its small `shade` function explicitly inlined so
Clang does not leave a function call in the inner loop.

The materialized controls expose the cost of boundaries:

- **Final-pixel List** runs the first five stages fused, stores the resulting
  shades in a List, then folds the List.
- **Staged List** stores a separate List after every stage: ranges, sample
  IDs, intensities, groups, shades, and selected shades. It reverses each
  List because `into(List, ...)` prepends.
- **Staged Vec** stores separate Array-backed Vecs of ranges, IDs,
  intensities, shades, and selected shades. `partition4` and `shade` remain
  fused at one boundary because Bend tuples are `Type` and `Vec` stores only
  `Data`. It is still a meaningful flat-storage materialization control, but
  it materializes one fewer stage than the List path.

## Results

One M3 Max, native Apple Clang 17 `-O3`, 30 randomized sessions per size. The
clock encloses one frame's computation and temporary allocations. Process
startup, compilation, image construction, and display are excluded. Every
implementation matched C's checksum at every size; the exported 256×256 Bend
image also matched C at every pixel. Times are median **microseconds**.

| Pixels | Samples | Fused Bend | Direct Bend | C | Final-pixel List | Staged Vec | Staged List |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 128² | 65,536 | 40 | 37 | 36 | 221 | 498.5 | 960.5 |
| 256² | 262,144 | 159 | 146 | 143 | 891.5 | 1,949.5 | 3,886.5 |
| 512² | 1,048,576 | 640 | 584 | 576.5 | 3,734 | 7,771 | 15,579.5 |
| 1024² | 4,194,304 | 2,545 | 2,339 | 2,305.5 | 15,163.5 | 30,987.5 | 62,363.5 |

At 512², fused Bend is about **1.1× C**, while staged Vec is **12×** and
fully staged Lists **24×** slower than fusion. This is the intended contrast:
short per-sample math exposes the cost of traversals and temporary storage.
Timed native heap-allocation calls at this size were **32 fused**, **12
direct**, **232 staged Vec**, and **4,989,190 staged List**. Vec has fewer
allocation calls because it uses flat Array storage, but repeated writes and
reads still cost time. The [raw CPU samples](starfield-benchmarks.json) include
all timings, checksums, compiler revision, source hashes, and allocation
counts. These are computation times, not displayed frames per second.

## CPU threads and Metal GPU

For the parallel measurement, each sample warms one frame, then times eight
different consecutive frames in one process. The frame checksums are checked
against independent C runs. `tiled` splits pixels into balanced ranges; the
CPU path uses 64 leaf jobs, while the GPU runs use 64, 1,024, or 4,096 jobs.
The timed region includes GPU scheduling and cleanup, but not shader
compilation or process startup. Median microseconds **per computed frame**:

| Pixels | Serial CPU | CPU 4 threads | CPU 8 threads | GPU 1,024 tiles | GPU 4,096 tiles |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 256² | 159.2 | 115.9 | 159.9 | 488.3 | 658.0 |
| 512² | 636.1 | 235.9 | 207.0 | 462.9 | 456.1 |
| 1024² | 2,543.7 | 735.6 | 444.1 | 606.8 | 488.4 |

At these sizes, eight CPU threads are the best measured route at 1024²;
Metal's dispatch overhead is still substantial for this short kernel.
It is useful evidence about where this demo runs well, not a GPU speedup
claim. The [256² and 512² samples](starfield-parallel-20260926.json) and
[1024² samples](starfield-parallel-1024-20260926.json) contain all modes,
tile counts, and samples.

Reproduce the CPU and image comparison with the sibling `../bend` compiler:

```sh
python3 bench/starfield_showcase.py --depths 7 8 9 10 --sessions 30 \
  --image-depth 8 --image-output bench/starfield-frame0.png \
  --output bench/starfield-benchmarks.json
```

Run the separate native parallel comparison on a machine with a visible
Metal device:

```sh
python3 bench/starfield_parallel.py --depths 8 9 10 --sessions 8 \
  --repeat 8 --output /tmp/starfield-parallel.json
```
