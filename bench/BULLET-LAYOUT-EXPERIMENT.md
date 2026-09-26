# Bullet layout experiment

**Question:** would a flat array for each bullet field make Bullet Cathedral
faster, and would the improvement matter to the complete program?

**Answer:** yes, modestly. In 30 randomized, paired native runs on the M3 Max,
the seven-array layout saved a median **15.9 ms per 120 frames** against the
committed generated-bullet program, about **3.9%** of its total time. It saved
**22.0 ms** against a stored array of bullet records, about **5.3%**. Every
pair favored the field arrays. The corresponding 120-frame medians were:

| Bullet representation | Simulation only | Simulation + 512×512 RGB frames + checksums | Timed heap allocations |
| --- | ---: | ---: | ---: |
| Generate records as needed | 44.1 ms | 409.6 ms | 133,671 |
| One `Array<Bullet>` | 56.6 ms | 415.5 ms | 133,431 |
| Seven field arrays | **37.6 ms** | **393.4 ms** | 135,591 |

The simulation-only column comes from a separate 21-pair benchmark. Its full
dispatch is replaced with `score_of(simulate(...))`, so it measures spawning,
collision tests, health updates, and player damage without constructing a
framebuffer. Field arrays won all 21 simulation pairs too. The generated
version's simulation is only about **11% of its complete measured time**;
framebuffer construction and pixel checksums dominate the total. That is why
a large relative gain in simulation becomes a small gain in the whole program.
The earlier showcase report measured 439 ms for the generated version in a
different session. The paired deltas here compare processes run immediately
beside one another and are the relevant layout result.

## What changed

The [generated version](bullet_cathedral.bend) maps active spawn IDs to
short-lived `Bullet` records separately in friendly collision, player
collision, and drawing passes. It has no stored bullet pool.

The [array-of-records control](bullet_cathedral_aos.bend) computes each active
bullet once per frame and stores it in a 16,384-slot `Array<Bullet>`. It clones
the array so the same bullet data can feed the three original transducer
pipelines. This tests whether merely avoiding repeated bullet generation
explains the gain.

The [field-array version](bullet_cathedral_soa.bend) also computes each bullet
once. It stores `x`, `y`, `old_x`, `old_y`, radius, color, and friendly flag in
seven separate 16,384-slot arrays. `id` is implicit in the array index, and
the frame is common to the pool. A custom indexed source reconstructs a
`Bullet` record for each pass, so the collision, sprite, `filter`, `cat`, and
reducer stages are the same as in the other versions. The arrays are cloned
for the three passes. At peak, 12,288 slots are active.

The array-of-records control is slightly slower than generated bullets; the
field arrays are faster than both. The result supports using separate scalar
arrays when bullet state is materialized. It does **not** isolate hardware
cache locality from all other effects: Bend's representation of `Bullet`,
array cloning, generated C, and callback specialization can also affect
the result. Timed allocation counts are similar, so the improvement is not
explained by fewer calls to Bend's native heap allocator.

The Bend guide says scalar `F32` and `U32` terms fit in a word, while larger
values are heap references. That makes flat scalar arrays a plausible locality
win over an `Array<Bullet>` of multi-field records. We did not collect hardware
cache-miss counters, so the measured difference should not be labeled a pure
cache effect.

## Correctness and measurement

Both materialized versions match **all 120 packed-RGB frame checksums** from
the committed animation, plus the final 405 accepted drone hits and 214
player shield points. The complete-run checksum is `367602200` for all three.

The [full-run script](bullet_layout_compare.py) compiles each Bend file with
the same fork compiler and Apple Clang 17 `-O3`, warms each three times, then
times 30 randomized triples on one CPU thread. The clock is inside Bend and
includes simulation, collisions, every framebuffer, and the pixel checksum
pass. Compilation, process startup, PNG/MP4 encoding, and display are outside
the interval. It also instruments native heap allocation calls. The
[raw full-run data](bullet-layout-comparison.json) includes every sample and
pair order; all 30 generated-minus-field-array and all 30
array-of-records-minus-field-array deltas are positive.

The [simulation script](bullet_phase_compare.py) applies the same one-line
dispatch change to all three source files and measures 21 randomized triples.
Its [raw data](bullet-phase-comparison.json) records every sample. The
simulation-only medians should not be subtracted from the full medians as a
precise phase profile: they come from separately compiled programs and
separately timed sessions. They show the scale of the bottleneck.

```sh
python3 bench/bullet_layout_compare.py --frames 120 --pairs 30
python3 bench/bullet_phase_compare.py --frames 120 --pairs 21
```

This is a one-thread CPU result for this generated, fixed-lifetime bullet
field. It does not predict a GPU result or a game with dynamic spawns,
deletions, and divergent bullet behaviors. A next optimization would read
only the fields needed by each pass; this experiment deliberately reconstructs
the full record to keep the existing transducer stages comparable.
