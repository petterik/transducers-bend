# Bullet Cathedral: a transducer bullet hell

![Bullet Cathedral at frame 96](bullet-cathedral-frame-096.png)

**[Watch the 120-frame MP4](bullet-cathedral.mp4)** · [Bend source](bullet_cathedral.bend) · [all stills and checksums](bullet-cathedral-report.json)

This is a complete, deterministic bullet-hell scene written in Bend. It needs no
input file. A rotating boss emits four families of hostile bullets; the player
ship moves and fires a curved fan; 256 moving shield drones occupy a 16×16
arena grid. Swept-circle collisions damage drones and the player. Drones have
three health points, hits leave fading afterglows, the boss changes phase after
192 accepted hits, and two bars display drone-hit progress and player shield.

The simulation and every RGB pixel are computed by Bend transducers. The Python
exporter converts Bend's packed RGB `Array<U32>` output to PNG and MP4; it does
not simulate, collide, shade, or draw the scene.

## The data flow

Bullets are generated on demand from a range of spawn IDs. At peak the range
contains 96 spawn ticks × 128 bullets, or 12,288 bullets. A generated `Bullet`
is a short-lived record of scalar fields, not an element in a stored bullet
array. This allows a single traversal to construct, test, and consume each
bullet without keeping an intermediate bullet collection.

```bend
X.into(empty_hits(), X.comp2(X.comp5(
  X.map_with(~U32, ~Bullet, ~U32, ~bullet_at, frame),
  X.filter(~Bullet, ~onscreen),
  X.filter(~Bullet, ~friendly),
  X.map(~Bullet, ~Nearby, ~near),
  X.cat(Nearby.adapter())),
  X.comp3(X.filter(~Candidate, ~valid_cell),
    X.filter(~Candidate, ~hit),
    X.map(~Candidate, ~Hit, ~as_hit))), active_ids(frame))
```

`Nearby` is a source that emits the nine grid cells around one bullet. Each
32×32 cell owns one moving drone. `cat` expands nearby cells, `filter` discards
out-of-bounds cells and tests a swept bullet segment against the drone circle,
and `map` produces a hit event. Thus a friendly bullet checks at most nine
drone candidates rather than all 256. Accepted events are reduced into a flat
`Array<U32>` of health values and a history of recent hit effects. Hostile
bullets take a separate fused path to the moving player's collision circle.

Rendering is another transducer program. A range of 262,144 pixel IDs builds
the background in a flat framebuffer. Bullets, live drones, afterglows, the
boss, and the player become `Sprite` values. The `SpritePixels` source expands
each sprite to a bounded rectangle; `filter` clips the pixels to a circle and
the screen; `map` computes a radial color; a reducer blends it into the
framebuffer with indexed `Array.get` and `Array.set`. The HUD is another
`map → filter → map → reduce` pass. The only stored output image is the flat
framebuffer. The small hit-event `Vec` and persistent hit history are
intentional materialized state; the bullet, candidate, and pixel stages are
fused.

## Measured run

On the development M3 Max, the native compiler generated C and Apple Clang 17
compiled it with `-O3`. One CPU thread computed 120 sequential 512×512 frames
in a **439.373 ms median** across 21 timed processes after three warmups.
That is **about 273 computed frames per second averaged over the whole
sequence**, which grows from a sparse opening to the full bullet field. The
range was 436.443–441.581 ms. Each timed run produced the same cumulative
32-bit checksum, `367602200`.

The clock starts before frame zero and stops after frame 119. It includes
simulation, collision resolution, full framebuffer construction, and a
checksum traversal of every pixel. It excludes compilation, process startup,
text transfer, PNG/MP4 encoding, and display. The MP4 plays at 30 FPS by
choice; its playback rate is separate from computation throughput. Native
heap-allocation instrumentation counted **133,671 calls over 120 frames**.
This count covers all native heap allocation sites in the timed interval; it
does not classify their causes. Raw samples and the instrumentation method are in
[the benchmark JSON](bullet-cathedral-bench.json) and
[benchmark script](bullet_cathedral_bench.py).

## Collision checks

[The independent oracle](bullet_cathedral_oracle.py) reproduces bullet and
drone positions in Python, then checks every on-screen friendly bullet against
all 256 drones for every frame. Across **54,018,048 exhaustive pairs**, it
found 76,049 geometric overlaps and verified that every one belongs to the
nine cells visited by the Bend broad phase. It also compares cumulative
accepted drone hits and remaining player shield against Bend **at every
frame**. The final values are 405 accepted drone hits and 214 shield points.
This is a check of this deterministic animation, not a proof for all possible
bullet paths or grid configurations.

Every exported frame has a packed-RGB checksum in
[the export report](bullet-cathedral-report.json). The sum of those 120
checksums modulo 2³² equals the native benchmark checksum.

## Why the storage is shaped this way

The mutable data that persists is already split by use: one flat health array
for the 256 drones and one flat RGB array for the 512×512 pixels. Bullets are
recomputed from ID, spawn tick, and current frame; they do not live in an
array of records. A structure-of-arrays bullet pool might be faster if future
versions store and update bullets across frames, particularly when collision
and rendering read different subsets of fields. It would also make spawning,
deletion, and compaction more involved. For this generated workload, a stored
AoS-to-SoA rewrite would add storage and copies rather than remove them.
The current approach leaves the short-lived scalar record available for
compiler specialization and C optimization.

## Reproduce

Use the sibling `../bend` compiler fork at commit
`1b4f641b9fea9b48fee37fc10b0a07977bba6e7d`. `bun`, `clang`, Python 3,
and `ffmpeg` are needed to export the video; the oracle and benchmark do not
need `ffmpeg`.

```sh
python3 bench/bullet_cathedral_oracle.py --frames 120
python3 bench/bullet_cathedral_bench.py --frames 120 --sessions 21
python3 bench/bullet_cathedral_export.py --frames 120 --fps 30
```

The exporter writes the MP4, six PNG stills, and JSON report into `bench/`.
The scene is deterministic and requires no external assets.
