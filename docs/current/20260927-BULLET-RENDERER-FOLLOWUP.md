---
created_at: 2026-09-27
status: bounded-fill-cpu-quotient-and-bullet-metric-verified-remaining-gap-open
---

# Bullet Cathedral renderer: three measured changes and the remaining gap

The 512×512, one-thread showcase now uses the generic `Array.fill` for its
sequential sky pass. It still uses transducers for bullets, drones, hit
effects, icons, and the HUD. `Array.fill` owns a `Data` Array, derives its
size, and writes each index in order. The native compiler checks the entire
remaining span before using unmasked offsets. Direct malformed calls to its
loop helper fall back to `Array.set`'s masked indexing. The implementation is
in the sibling fork's `bend2/base.bend` and `bend2/comp.ts` at `98e79611`.

## Measured change

The [21-session paired comparison](../../bench/bullet-fill-comparison-20260927.json)
compiled the previous transducer sky and the bounded-fill sky as separate
Bend programs. Both produced the same cumulative checksum for the full
120-frame scene and for the background-only ablation. The number of timed
native heap-allocation calls was unchanged.

| 120 frames, one CPU thread | Previous transducer sky | Bounded fill | Difference |
| --- | ---: | ---: | ---: |
| Background plus checksum | 142.138 ms | 70.376 ms | −71.762 ms |
| Complete scene | 340.601 ms | 268.982 ms | −71.619 ms |

This is a **21.0% reduction in complete-scene time** for the final source
and compiler. The
full [Bend/C/Rust comparison](20260927-BULLET-CATHEDRAL-CROSS-LANGUAGE.md)
then checked every frame's pixel checksum, accepted hits, and shield value.
Before the CPU quotient change, its fresh-buffer medians were **311.389 ms
Bend**, **242.763 ms C**, and **227.844 ms Rust** over 120 frames. The
next comparison after that change measured **277.951 ms Bend**,
**242.499 ms C**, and **227.564 ms Rust**. A further bullet-stage change
brings the [current comparison](20260927-BULLET-CATHEDRAL-CROSS-LANGUAGE.md)
to **269.027 ms Bend**, **242.650 ms C**, and **227.616 ms Rust**. Bend
remains **26.377 ms** behind C and **41.411 ms** behind Rust in this
one-thread comparison.

The `Array.fill` fixtures cover one-element, boxed, and shared Arrays, and
invalid direct helper spans. The full local fork gate passed **1473/1473**;
the library suite passed **65/65**. A native Metal `Array.fill` fixture
returned the same value as CPU. These checks support the implementation;
they are not a proof of the C emitter.

## The 1920×1080 player

The windowed player uses a 2,097,152-slot Array for 2,073,600 visible
pixels. Plain `Array.fill` would color the unused tail, changing its
whole-Array checksum. The fork now also provides `Array.fill.prefix`
(`4d27fef8`), which
clamps a requested count to the Array size and uses the same bounded fill
loop. The 2K scene fills only the visible prefix, leaving the tail zero.

In a [21-session paired 2K probe](../../bench/bullet-2k-fill-comparison-20260927.json),
24 sequential frames took **269.743 ms** with the old sky transducer and
**217.446 ms** with prefix fill on one CPU thread, a **19.4% reduction**.
The 120-frame cumulative checksums matched, as did individual checksums at
frames 0, 23, 95, and 119. This is a headless measurement; the previous
38–40 presented FPS observation has not been remeasured with this change.

The native window entry previously failed Bend's template-growth check when
it imported the 2K frame module. Both the old and new sky versions hit the
same error. The launcher now assembles the existing frame and window code
into one temporary Bend module before compiling; `--compile-only` verifies
that build without opening a window. This changes module packaging, not
simulation or rendering behavior.

## Where time and allocations remain

The next root cause was the generated `U32_QUO` macro. Its original formula
halves the dividend, divides, doubles the quotient, then corrects the odd
bit. The comment in the compiler says it avoids a Metal constant-folding
error near `2^32`, but the CPU emitter used it too. Every sprite pixel
calculates both a quotient and a remainder from its slot and rectangle
width. Using ordinary unsigned division on CPU lets Clang combine those
operations. The fork now keeps the workaround under `#if DEVICE` and emits
ordinary division on native CPU (`bd749c7c`). The
[21-session same-source probe](../../bench/bullet-cpu-quotient-probe-20260927.json)
measured **301.529 ms** with the old formula against **268.901 ms** with
native CPU division, with the same cumulative checksum. The full C/Rust
runner also matched all 120 frame triples after the change. This is a
general compiler fix for `U32.div` and `U32.mod`, not a sprite-specific
rewrite.

The phase measurements below use **bounded fill, the CPU quotient fix,
and the bullet-stage change**. Each prefix is a separate binary, so
their differences remain approximate.

The [Bend](../../bench/bullet-render-phase-20260927.json) and
[C](../../bench/bullet-c-render-phase-20260927.json) phase runners compiled
one cumulative render prefix at a time. Both include the same sequential
simulation, a fresh framebuffer each frame, and the pixel checksum. Each
prefix produced the same cumulative checksum in both languages. Because
each prefix is a different binary, the difference between rows is an
indication of scale, not an isolated stage timer.

| Through render layer | Bend median | C median | Bend minus C |
| --- | ---: | ---: | ---: |
| Background | 70.361 ms | 63.145 ms | 7.216 ms |
| Bullets | 242.765 ms | 230.934 ms | 11.831 ms |
| Drones | 258.006 ms | 243.976 ms | 14.030 ms |
| Hit effects | 265.243 ms | 239.427 ms | 25.816 ms |
| Icons | 269.463 ms | 241.867 ms | 27.596 ms |
| HUD | 269.072 ms | 242.683 ms | 26.389 ms |

The independently instrumented
[allocation-site report](../../bench/bullet-alloc-sites-20260927.json)
counts **133,791** Bend native heap-allocation calls inside the timed
interval. `rfc_wrap` accounts for 62,472; two generated hit-history `work_loop`
sites account for 30,111 each. Those three sites contribute 122,694 calls,
about **91.7%** of the total. The hit-layer ablation increases calls by
121,164 but adds far less elapsed time than the bullet layer. Allocation
count alone therefore does not identify the main CPU cost. The report counts
calls, not bytes, allocator latency, or live memory.

The bullet pass originally calculated `dx² + dy²` in `covered`, then again
in `pixel_ink`. The C loop calculates it once and reuses it for radial
falloff. A `MeasuredPixel` map now carries squared distance, squared radius,
position, and color through the bullet filter to the mapper. The
[21-session paired ablation](../../bench/bullet-metric-probe-20260927.json)
measured **277.806 ms** with repeated arithmetic and **269.144 ms** with
the carried values. The final runner matched all 120 frame triples and
counted **133,791** timed native heap allocations. Applying the same
record to every sprite pass did not improve the full scene in an
exploratory paired run, so only bullets use it.

An intentionally unsafe [generated-C probe](../../bench/bullet-nomask-probe-20260927.json)
replaced *every* `blk_at` mask with a direct offset. Before bounded fill,
this reduced the scene from about 405 to 328 ms, but changed Array semantics.
With the current scene and compiler, 21 paired runs measured **268.955 ms
normal** versus **265.206 ms for the unsafe probe**. This small gain cannot
justify changing Array semantics. The probe must not be used as an
implementation.

## Next optimization boundary

The remaining gap still grows through the sprite passes. The handwritten C
renderer operates on a `uint32_t *` framebuffer inside a compact sprite
loop. Bend's generic source and reducer pass sprite, pixel, and ink values
through generated functions before reading and updating its owned Array.
The native code does not allocate per pixel. An exploratory 21-run
generated-C probe raising Clang's inline threshold to 1000 shortened the
final scene from 269.104 to 267.610 ms. That small gain does not yet
justify a global compiler flag change. A focused sprite-only benchmark and
assembly inspection would be the next useful way to separate the remaining
scalar work from source and reducer dispatch.

The previous full-scene C/Rust report and the original transducer-sky source
are recoverable from library commit `4088e9e`. The current runner synthesizes
that sky variant from the current scene for paired reproduction:

```sh
python3 bench/bullet_fill_compare.py --sessions 21
python3 bench/bullet_render_phase_profile.py --sessions 21
python3 bench/bullet_c_render_phase.py --sessions 21
python3 bench/bullet_alloc_sites.py
python3 bench/bullet_nomask_probe.py --sessions 21
python3 bench/bullet_cpu_quotient_probe.py --sessions 21
python3 bench/bullet_metric_probe.py --sessions 21
python3 bench/bullet_2k_fill_compare.py --sessions 21
python3 bench/bullet_cathedral_2k_native.py --compile-only
```
