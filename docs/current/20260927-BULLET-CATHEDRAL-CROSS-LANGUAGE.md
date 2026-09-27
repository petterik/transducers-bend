---
created_at: 2026-09-27
status: 512px-comparison-verified
---

# Bullet Cathedral in Bend, C, and Rust

The [Bend scene](../../bench/bullet_cathedral.bend),
[handwritten C port](../../bench/bullet_cathedral_control.c), and
[Rust port](../../bench/bullet_cathedral_control.rs) compute the same
**120 sequential 512×512 frames**. The [runner](../../bench/bullet_cathedral_cross_language.py)
compiles all three, then checks **every frame's** packed RGB checksum,
accepted-hit count, and remaining player shield. All 120 triples matched.
The cumulative pixel checksum was `367602200`; the last frame had 405
accepted drone hits and 214 shield points. This agrees with the independent
[exhaustive collision oracle](../../bench/bullet_cathedral_oracle.py), which
checked 54,018,048 candidate pairs and 76,049 geometric overlaps.

The C code uses `-ffp-contract=off` to preserve the Bend program's
intermediate F32 rounding; otherwise Clang's contraction changed four pixels
by frame four despite matching simulation counters. Both C and Rust promote
F32 arguments to the host `sin`/`cos` implementation and round the result
back to F32, matching this Bend runtime. The exact per-frame check, rather
than just the cumulative checksum, caught those small differences.

On the M3 Max, one CPU thread, 21 shuffled process sessions, these were the
median **internal microsecond intervals for all 120 frames**. The C and Rust
controls each have a reuse lane and a lane that allocates a new framebuffer
per frame, like the Bend renderer:

| Language | Median | Min–max | Relative to C |
| --- | ---: | ---: | ---: |
| Bend transducers and bounded fill | 269,027 | 268,581–271,129 | 1.11× |
| Handwritten C, reuse | 242,476 | 242,299–244,834 | 1.00× |
| Handwritten C, fresh | 242,650 | 242,249–244,712 | 1.00× |
| Rust loops, reuse | 226,863 | 226,681–229,165 | 0.94× |
| Rust loops, fresh | 227,616 | 227,287–229,842 | 0.94× |

The Bend scene now initializes its sky with the general `Array.fill`, which
matches the sequential framebuffer fill in C and Rust. The fork also emits
ordinary unsigned quotient operations for native CPU code while retaining
its existing Metal quotient workaround on device. In a
[same-source paired probe](../../bench/bullet-cpu-quotient-probe-20260927.json),
the latter change reduced Bend's 120-frame median from 301.529 to
268.901 ms against the final source. The [renderer follow-up](20260927-BULLET-RENDERER-FOLLOWUP.md)
records both changes and their correctness checks. The current Bend scene
is 26.377 ms behind the fresh C lane and 41.411 ms behind the fresh Rust
lane; this gap is still open. In the bullet sprite transducer, a measured
pixel now carries its squared distance from the filter to the color mapper,
as the C loop does. The
[paired ablation](../../bench/bullet-metric-probe-20260927.json) measured
277.806 ms when both stages calculated distance and 269.144 ms when the
mapper reused it. The change remains within the composable transducer
pipeline and preserved every frame's output.

The interval includes initial World and framebuffer setup, simulation,
collision handling, complete framebuffer construction, per-frame pixel
checksum, and cleanup. It excludes source compilation, process startup,
window presentation, and PNG/MP4 encoding. The reuse lanes allocate one
framebuffer at the start; the fresh lanes allocate and release one inside the
interval for each frame. The fresh/reuse differences were small on this fixture. A separate
allocation-count build found **133,791 Bend native heap-allocation calls**
inside the 120-frame clock. The C scene makes **1** explicit timed `malloc`
calls with reuse or **120** with fresh buffers. A separate Rust global
allocator meter counted **1,007** allocation/reallocation calls with reuse
and **1,126** with fresh buffers. These count different allocator interfaces;
the C count does not include possible libc internals. They do show that the
showcase has substantial runtime allocation beyond its output framebuffer,
so the small flat-Array fusion result does not imply an allocation-free scene.
The [raw report](../../bench/bullet-cathedral-cross-language-20260927.json)
contains all samples, per-frame triples, source hashes, compiler hashes,
toolchain, and exact flags. This is the 512×512 scene. The separate
[1920×1080 native-window run](../../bench/BULLET-CATHEDRAL.md) is Bend-only
and reported 38–40 presented FPS on one CPU thread after startup. These
numbers measure different resolutions and timing boundaries.

The runner's simple language-neutral count removes blank lines and comments,
then counts identifiers, digit runs, and individual nonspace punctuation.
Counts **include each file's own CLI harness** and exclude imported libraries
and generated C:

| Handwritten scene file | Code lines | Lexical tokens | Raw `o200k_base` tokens |
| --- | ---: | ---: | ---: |
| Bend | 600 | 8,379 | 8,610 |
| C | 230 | 3,092 | 3,513 |
| Rust | 250 | 3,122 | 3,320 |

The Bend scene imports a reusable transducer library. `xf.bend` is 208 code
lines / 4,541 tokens and `transduce_core.bend` is 966 code lines / 15,464
tokens under the same rule. Those files serve far more than this scene, so
adding all of them to one showcase would answer a different code-size
question. The table nevertheless shows that this particular declarative Bend
scene is longer than the direct C and Rust ports by this count; it does not
support a code-size win claim. The raw BPE column counts whole UTF-8 files,
including comments and harnesses, with `tiktoken` 0.14.0's `o200k_base`. It
is a named prompt-size proxy rather than the exact token bill for a model.
The [source metrics report](../../bench/bullet-source-metrics-20260927.json)
records file hashes and the separate reusable-library counts.

The three [Bend proof artifacts](../../proofs/README.md) establish List
map/fold and map-composition laws, a no-stop Control law, and local
`T.map`/`T.filter` step laws. Together they add **103 code lines / 1,357 raw
`o200k_base` tokens**, counted separately from the scene and libraries. The
[scene geometry argument](../../proofs/bullet_cathedral_geometry.md)
derives nine-cell coverage and index bounds from the current constants, with
an explicit floating-point boundary. None is an end-to-end machine-checked
proof of the Bullet Cathedral program or either port. The oracle and
all-frame differential checks are tests. No machine-checked proof
accompanies the C or Rust source here.

## Why the times differ so far

All three programs produce the same 120 frame triples, but the native paths
are different. Bend expresses the sprite passes as composed `map`, `cat`,
`filter`, and `map` transducers over reducible sprite rectangles. Its
reducer reads and updates an owned Array. C and Rust use a handwritten
`draw_sprite` loop over a direct framebuffer; Rust indexes a `Vec<u32>` and
C indexes a `uint32_t *`. This is a comparison of these three implementations
and compilers, not a general ranking of the languages.

Three earlier Bend costs have direct paired measurements in the
[renderer follow-up](20260927-BULLET-RENDERER-FOLLOWUP.md): replacing the
transducer sky with generic bounded `Array.fill` saved **71.619 ms** per
120 frames; using ordinary CPU unsigned division instead of the Metal
workaround saved **32.628 ms** in a same-source probe; carrying squared
distance between the bullet filter and mapper saved **8.662 ms**. These
probes use different baselines and should not be summed as an exact
decomposition. They explain improvements already included in the 269.027 ms
Bend result, not its remaining 26.377 ms gap to fresh C.

For that remaining gap, cumulative prefixes put Bend **7.216 ms** behind C
with only sky, simulation, and checksum, then **26.389 ms** behind C through
the full render. The prefix binaries are compiled separately, and their
medians are not isolated layer timers. The C generated from the
[Bend source](../../bench/bullet_cathedral.bend)
still contains `f32_to_u32` checks and general quotient/remainder arithmetic
in its sprite pixel source, and `blk_at` lookups for both Array read and
write. Clang may hoist or remove some of this after inlining; the source
alone cannot assign a runtime cost to each check. A deliberately unsafe
[mask-removal probe](../../bench/bullet-nomask-probe-20260927.json) improved
the current scene by only **3.749 ms**, and a larger Clang inline threshold
by about **1.494 ms**. Neither accounts for most of the remaining gap.
Bend made **133,791** timed native heap-allocation calls; the hit-layer
ablation added **121,164** of them, but that prefix added relatively
little time. Allocation count is not a measured explanation for the main
pixel-work gap.

The C–Rust gap is more localized. A new [paired render-prefix probe](../../bench/bullet-c-rust-phase-probe-20260927.json)
found **63.244 ms C vs 62.713 ms Rust** for sky plus simulation and
checksum, but **230.755 ms C vs 212.201 ms Rust** through the bullet pass.
The complete scene in that same probe was **242.891 ms C vs 228.015 ms
Rust**. The gaps after later prefixes are not monotonic, another reason
not to subtract rows as independent layer costs.

The native assembly gives one concrete reason the bullet paths differ:
Clang keeps C's `draw_sprite` as one outlined function with variable radius
and integer division in its pixel loop. Rust inlines its fixed-radius bullet
and drone calls; the bullet loop has constant 81 iterations and replaces
division by nine with constant-width arithmetic. In a
[same-source Rust ablation](../../bench/bullet-rust-inline-sprite-probe-20260927.json),
`#[inline(never)]` on `draw_sprite` raised the 120-frame median from
**227.591 to 250.246 ms** while preserving every frame triple. This shows
that Rust's inlining matters greatly for this build. It does not prove that
inlining alone explains its lead over C: forcing the whole C function inline
[slowed C](../../bench/bullet-c-inline-sprite-probe-20260927.json) from
**242.779 to 252.117 ms**, and duplicating only its fixed-radius bullet
and drone loops [slowed it further](../../bench/bullet-c-fixed-sprite-probe-20260927.json)
from **242.488 to 264.425 ms**. These edits change optimization and code
layout together, so the C regression has not been isolated further. The C
and Rust sprite loops both emit hardware `fmaxnm` for
the sprite maximum operation, so a C math-library call is not the cause.

The original builds used Clang's default CPU target for Bend and C but
`target-cpu=native` for Rust. A [paired target probe](../../bench/bullet-target-cpu-probe-20260927.json)
found that targeting Apple M3 improved C by a median **0.547 ms** within
sessions; changing Rust from generic to Apple M3 improved it by **1.997 ms**.
Rust still led C by about 15 ms in that probe. Absolute times in that
session were higher than the headline run, so only its paired differences
should be used for this question. The CPU-target flag does not explain the
ranking.

The strongest current conclusion is therefore narrower than a full
26 ms plus 15 ms accounting: Bend's residual is associated with its
generated generic sprite and Array update path; Rust's advantage over this
C port first appears in sprite rendering, and its current inlining is
important. The exact instruction-level cost of each remaining operation
has not been isolated. The separate 1920×1080 Bend-only 217.446 ms probe
uses 24 frames and cannot be placed in this 512×512 ranking.

Reproduce the additional probes with `python3` and their linked scripts:
`bench/bullet_target_cpu_probe.py`, `bench/bullet_c_rust_phase_probe.py`,
`bench/bullet_c_inline_sprite_probe.py`,
`bench/bullet_rust_inline_sprite_probe.py`, and
`bench/bullet_c_fixed_sprite_probe.py` (all default to 21 sessions).
