# Bullet Cathedral: CPU simulation, spatial bins, and Metal rendering

The [512×512](bullet_cathedral_gpu.bend) and
[3840×2160](bullet_cathedral_gpu_4k.bend) experiments keep simulation and
collision on the CPU. A transducer turns bullets, live drones, hit effects,
and icons into sprites, then reduces those sprites into indexed screen-space
buckets. Each bucket holds only sprites overlapping its tile. The buckets are
assembled into a quadtree; one Bend `!` call forks independent render tasks
over that tree. Each task gathers its own pixels and returns a checksum. No
task writes a shared framebuffer.

This tests the CPU/GPU split suggested by the sibling Bend checkout's
`guide/SHADERS.md`: prepare scene data on the host, then issue one balanced
device call. The GPU renderer does not create a window or video. The
[live player](bullet_cathedral_live.py) remains on the CPU.

## Measured result

M3 Max, dense frame 119. Times below are median microseconds from three
interleaved rounds, three timed draws per round after one warmup. The same
binary and pixel code run on CPU and Metal. CPU and GPU draw times include
their scheduling and completion; shader compilation, process startup, image
export, and display are excluded.

| Canvas | Padded tiles | Visible tiles | CPU scene bins | Draw, 8 CPU threads | Draw, Metal |
| --- | ---: | ---: | ---: | ---: | ---: |
| 512×512 | 4,096 | 4,096 | 1.0 ms | 3.45 ms | 46.66 ms |
| 512×512 | 16,384 | 16,384 | 2.2 ms | **3.16 ms** | **20.76 ms** |
| 3840×2160 | 16,384 | ~8,160 | 1.1 ms | 42.67 ms | 387.78 ms |
| 3840×2160 | 65,536 | 32,400 | 2.9 ms | **30.90 ms** | **152.43 ms** |

The 4K tree covers a padded 4096×4096 square; branches wholly outside the
3840×2160 canvas are skipped. More, smaller tiles improve Metal substantially,
but its best tested draw is still **4.9× slower** than the eight-thread CPU
draw. At 512×512, its best draw is **6.6× slower**. The CPU scene bins are not
the limiting cost. The [raw samples](bullet-gpu-comparison.json) include
simulation replay, scene binning, and draw times separately.

The timed simulation value for frame 119 replays frames 0–119 to construct
the same deterministic world for each sample. It is about 37.5 ms at 4K and
44.1 ms at 512×512. It is **not** the cost of one live simulation step. Adding
CPU/GPU overlap would not fix this draw bottleneck: the Metal draw alone takes
far longer than the CPU draw and the replayed simulation. The current
[five-minute player](bullet_cathedral_live.py) should remain CPU-rendered.

## Correctness and reproduction

The tiled CPU renderer emits the **exact same packed RGB value at every
pixel** as the original at 512×512 frames 0, 48, and 119 and at 4K frame 96.
The 4K comparison covered all 8,388,608 Array elements, including the unused
tail after the visible pixels. GPU and CPU tile checksums agree with the
original at dense frame 119 for every tile count above. A matching checksum
alone is weaker than full pixel equality; the pixel comparison directly
checks the shared tile shader on CPU, while the GPU uses that same Bend
function through `!`.

```sh
python3 bench/bullet_gpu_compare.py
```

The script compiles both tiled renderers and original references, performs
pixel checks, runs interleaved CPU/Metal samples, and writes the JSON report.
It needs the sibling `../bend` compiler, `bun`, Apple Clang 17, and a Metal
device. Use `--cpu-only` where Metal is unavailable.

## What the experiment says

Indexed buckets and one GPU call make the architecture viable: scene
preparation takes about 1–5 ms across the tested modes, and all tested
results agree. This specific pixel-gather shader is a poor GPU fit. Each lane
evaluates the sky and walks its tile's sprite list for many pixels; the shader
guide warns that long serial work inside each lane and uneven tile work can
outweigh GPU parallelism. That is an explanation consistent with the code and timings,
not an isolated causal measurement. A different GPU shader would need a new
algorithm and another end-to-end test before replacing CPU rendering.
