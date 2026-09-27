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

| Handwritten scene file | Code lines | Lexical tokens |
| --- | ---: | ---: |
| Bend | 600 | 8,379 |
| C | 230 | 3,092 |
| Rust | 250 | 3,122 |

The Bend scene imports a reusable transducer library. `xf.bend` is 208 code
lines / 4,541 tokens and `transduce_core.bend` is 966 code lines / 15,464
tokens under the same rule. Those files serve far more than this scene, so
adding all of them to one showcase would answer a different code-size
question. The table nevertheless shows that this particular declarative Bend
scene is longer than the direct C and Rust ports by this count; it does not
support a code-size win claim.

The two small [Bend proof artifacts](../../proofs/README.md) establish a
List map/fold law and a no-stop Control law. The
[scene geometry argument](../../proofs/bullet_cathedral_geometry.md)
derives nine-cell coverage and index bounds from the current constants, with
an explicit floating-point boundary. None is an end-to-end machine-checked
proof of the Bullet Cathedral program or either port. The oracle and
all-frame differential checks are tests. No machine-checked proof
accompanies the C or Rust source here.
