# Bullet Cathedral at 4K: 16 render tasks

![Bullet Cathedral frame 96 rendered at 3840×2160 by Bend](bullet-cathedral-4k-frame-096.png)

This experiment renders the same 120-frame simulation at **3840×2160**. The
original 512×512 game world is scaled uniformly by 4.21875 to a 2160×2160
square centered in the 4K canvas. Bend computes the background across the
whole canvas, scales every glowing sprite before expanding its pixels, and
draws a larger HUD. Simulation and collision rules are unchanged.

The [eight-task version](bullet_cathedral_4k_frames.bend) renders one full
frame per task. The [16-task version](bullet_cathedral_4k_tiled16.bend) keeps
eight frames in flight and splits each into two 3840×1080 horizontal tiles.
Each tile owns its Bend Array and returns a checksum. The tiled path sums tile
checksums without assembling a full-frame image in the timed interval. The
tile-specific sprite and pixel filters use `X.filter_with` to carry the tile
number as a runtime setting. Background pixels are generated directly into
local tile indices.

## Performance

On an M3 Max, median time to simulate, render, and checksum all 120 frames:

| CPU threads | Eight full-frame tasks | 16 half-frame tasks |
| ---: | ---: | ---: |
| 8 | 2633.8 ms | 2303.7 ms |
| 16 | 2639.8 ms | **2277.1 ms** |

The best 16-task result is **13.5% faster** than the eight-task, eight-thread
baseline. It averages **19.0 ms per computed frame** over the batch, or about
**52.7 computed frames/s**. This is computation throughput, not individual
frame latency or displayed frame rate. Encoding and display are excluded.

The extra eight workers account for little of the improvement: the tiled
version improves from 2303.7 to 2277.1 ms when moving from 8 to 16 threads.
Equal pixel counts do not imply equal tile costs. In isolated one-thread
tile runs at dense frame 119, the top tile took **62.1 ms** and the bottom
**44.6 ms** (12 alternating samples per tile). The boss and many bullets
occupy the top half. Bend's scheduler does not move a forked task to another
worker after assignment, so that imbalance can leave workers idle. The
[tile profile](bullet-4k-tile-profile.json) measures this difference; it does
not isolate every reason for the batch scaling limit.

## Verification and reproduction

The [benchmark script](bullet_4k_tiled16_bench.py) compiles both Bend sources
with the pinned Bend fork and Apple Clang 17 `-O3`. It compares the **individual
checksum of every frame from 0 through 119** between the full-frame and tiled
renderers. Final accepted hits (`405`) and player shield (`214`) match. Every
full run produces cumulative checksum `229899170`. It then runs two warmups
and ten randomized sessions for each variant/thread combination. All runs
use `--gpu off`. [Raw samples](bullet-4k-tiled16.json) include order, source
hashes, compiler commit, and all frame checksums.

```sh
python3 bench/bullet_4k_tiled16_bench.py --frames 120 --sessions 10
python3 bench/bullet_4k_tile_profile.py
```

The internal Bend clock includes ordered world updates, collision handling,
full 4K background and sprite drawing, and checksum traversals. Compilation,
process startup, image export, video encoding, and display are outside it.
The 4K benchmark adds no image materialization beyond the two tile arrays
needed for rendering each frame. The still above was exported separately from
the full-frame Bend renderer with [the still exporter](bullet_4k_still.py):

```sh
python3 bench/bullet_4k_still.py --frame 96
```
