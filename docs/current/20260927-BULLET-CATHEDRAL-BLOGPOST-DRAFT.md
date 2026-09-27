---
created_at: 2026-09-27
status: part-two-evidence-backed-draft
---

# Bullet Cathedral in five implementations

In [part one](20260927-TRANSDUCERS-BLOGPOST-DRAFT.md), a Bend transducer
mapped and summed a million array elements in about the same time as C and
Rust, and Clang turned the generated C into a vector loop. That was a good
test of fusion. It left a larger question: when simulation and rendering
are involved, how much does the compositional style cost in time and code?

I built Bullet Cathedral to find out. It has 256 moving shield drones on a
16×16 grid, up to 12,288 active bullets, swept-circle collisions, accepted
hit history, and a 512×512 CPU framebuffer. A friendly bullet checks the
nine nearby grid cells, and each visible sprite expands to a circle of
shaded pixels. The scene also fills a sky, draws a HUD, and checksums every
frame. The benchmark runs 120 sequential frames, from a sparse opening to
a full field.

![Bullet Cathedral at frame 96](../../bench/bullet-cathedral-frame-096.png)

[Watch the 120-frame video](../../bench/bullet-cathedral.mp4).

## Five ways to write the same scene

I kept the same arithmetic, output order, framebuffer policy, and hit
history semantics in five complete handwritten scene files:

| Implementation | Main traversal style |
| --- | --- |
| [Bend transducers](../../bench/bullet_cathedral.bend) | `map`, `filter`, `cat`, and reducers over owned sources |
| [Bend direct](../../bench/bullet_cathedral_direct.bend) | Explicit structurally recursive loops and a shared sprite loop |
| [C direct](../../bench/bullet_cathedral_control.c) | `for` loops over IDs, candidate cells, sprites, and pixels |
| [Rust iterators](../../bench/bullet_cathedral_control.rs) | `map`, `filter`, `flat_map`, `collect`, and `fold` |
| [Rust direct](../../bench/bullet_cathedral_loops.rs) | `for` loops and a shared sprite loop |

The Bend transducer version collects friendly hits through a pipeline:

```bend
# Clojure: (into [] (comp (map bullet-at) (filter onscreen)
#   (filter friendly) (map near) cat (filter valid-cell)
#   (filter hit?) (map as-hit)) active-ids)
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

The direct Bend version performs the same two passes over active bullets
as the transducer version: one collects friendly hits, and one counts
hostile player hits. Its loops call the same bullet geometry and collision
functions. The renderer uses a shared direct sprite loop:

```bend
def direct_draw_sprite_loop(left: Nat, +slot: U32, +sprite: Sprite,
  framebuffer: Array<U32>) -> Array<U32>:
  match left:
    case 0n: framebuffer
    case 1n+p:
      direct_draw_sprite_loop(p, U32.inc(slot), sprite,
        direct_pixel(pixel_at(sprite, slot), framebuffer))
```

Rust's iterator port is the closest stylistic comparison with Bend's
transducers. It maps and filters bullets, uses `flat_map` for candidate
cells, collects the same hit events, and counts hostile bullets in a second
pass. Its shared pixel pipeline maps and filters each sprite's rectangle,
then applies the resulting ink without collecting a pixel array:

```rust
let _ = sprites.flat_map(sprite_pixels).fold(pixels, |pixels, (index, color)| {
    ink(pixels, index, color);
    pixels
});
```

C and direct Rust combine friendly and hostile work in one bullet loop.
That difference matters when interpreting their times; the five sources
match behavior, while their traversals are not identical. All five use a
fresh framebuffer per frame in the main comparison. The Bend direct port
uses the same general `Array.fill` sky operation and `Array.walk` checksum
primitive as the transducer port. Neither Bend port materializes candidate
cells or pixel streams; both intentionally store the framebuffer and hit
events. The direct Bend scene still imports the shared `Vec` module, which
defines optional transducer integration; this port calls its ordinary
`empty`, `push`, and `get_unchecked` operations directly.

## The measured result

The [five-way runner](../../bench/bullet_cathedral_five_way.py) checked
**every frame's pixel checksum, accepted-hit count, and remaining player
shield** in all five programs. All 120 triples matched. An independent
[oracle](../../bench/bullet_cathedral_oracle.py) checked 54,018,048
bullet–drone pairs over this run and found all 76,049 geometric overlaps
within the nine-cell search. The [geometry argument](../../proofs/bullet_cathedral_geometry.md)
explains the bounds; its floating-point boundary remains explicit.

On my M3 Max, one CPU thread, 21 shuffled sessions gave these median
**internal times for the complete 120-frame run**:

| Implementation | Median time | Code lines | Raw source tokens |
| --- | ---: | ---: | ---: |
| Bend transducers | 269.067 ms | 600 | 8,610 |
| Bend direct | 277.063 ms | 600 | 8,443 |
| C direct | 242.621 ms | 230 | 3,513 |
| Rust iterators | 246.035 ms | 260 | 3,498 |
| Rust direct | 227.742 ms | 250 | 3,321 |

The clock includes scene setup, simulation, rendering, fresh framebuffer
construction, per-frame checksums, and cleanup. It excludes compilation,
process startup, window presentation, and video encoding. Bend-generated C
and C were compiled with Apple Clang 17 `-O3`; C also used
`-ffp-contract=off` to preserve the scene's F32 rounding. Rust 1.95 used
`-C opt-level=3 -C target-cpu=native`. The
[earlier target-CPU probe](../../bench/bullet-target-cpu-probe-20260927.json)
found sub-2 ms shifts for the C and Rust controls on this machine; the
table's small C/Rust differences should be read with that build choice in
view. The
[raw report](../../bench/bullet-cathedral-five-way-20260927.json) records
all samples, exact flags, hashes, and per-frame triples. The
[source metrics](../../bench/bullet-source-metrics-20260927.json) count each
whole handwritten file, including its CLI driver, and exclude imported
libraries and generated C. Raw tokens use `tiktoken` 0.14.0's
`o200k_base` as a named prompt-size proxy.

## What the five versions tell me

The Bend transducer version finished **8.0 ms faster** than the direct Bend
port, about **3%** of the latter's time. This is evidence that composition
is not forcing a large runtime penalty in this scene. It is not a pure
measurement of transducer dispatch: the transducer renderer carries squared
distance between the bullet filter and color mapper, while the shared
direct sprite loop computes it twice. The measured gap therefore includes
data-flow and compiler differences as well as the choice of abstraction.
This direct version is one reference implementation, not an optimizer's
lower bound.

Rust iterators took **18.3 ms longer** than Rust direct loops, about **8%**
of direct-loop time. Its hit and incoming paths also make two bullet passes
where direct Rust makes one. Iterator composition is therefore fast in this
scene, but the two Rust source shapes are not interchangeable for exact
runtime. The iterator port is still within **1.4%** of C direct loops in
this run. Bend transducers took about **11% more time than C** and **9% more
than Rust iterators**. These are results for this scene and toolchain, not
language-wide rankings.

The code-size result surprised me more. **Both Bend ports are 600 code
lines.** Removing the transducer pipelines did not make this complete
scene shorter. The direct file replaces stage composition and two custom
source drivers with explicit recursion, case handling, and Array state
threading. Rust expresses the same high-level iterator approach in 260
lines; C and direct Rust are shorter still. Bend's guide describes its
limited type inference, `match` in place of `if`, structurally recursive
loops, and explicit reuse of affine values. Those features appear
throughout both Bend ports. Some verbosity is also my style: Bend has
infix arithmetic sugar, while I often spelled out `U32.add` and `F32.mul`.
The counts report these programs, not a minimum size for either language.

The transducer library already provides every public stage this scene uses,
including `map_indexed`. `Nearby` and `SpritePixels` are scene-specific
reducible sources, not missing `map` implementations. The shared library
and compiler changes are additional reusable code outside the 600-line
scene; C and Rust standard libraries are outside their counts too. The
[size audit](20260927-SHOWCASE-SIZE-AND-PROOFS.md) gives a finer breakdown.

## Safety, proofs, and memory

The C port uses raw framebuffer pointers and explicit bounds checks for
pixels and hit history. Both Rust ports use safe code without an `unsafe`
block. Bend uses typed ownership and Array operations. Bend also checked
three [proof artifacts](../../proofs/README.md): List map/fold fusion and
map composition, a no-stop `Control<Empty,U32>` law, and local laws for
the actual `T.map` and `T.filter` constructors. They add 103 code lines
and 1,357 raw tokens outside the scene. These are reusable transducer
facts. They do **not** prove the Bullet Cathedral simulation, renderer,
compiler output, or native runtime. The geometry argument is written,
and the finite 120-frame oracle and differential checks are tests. This
showcase does not establish an end-to-end formal-safety advantage over
safe Rust.

The timed Bend native heap-allocation meter counted 133,791 calls for the
transducer port and 127,551 for direct Bend. A Rust global allocator meter
counted 1,126 allocation or reallocation calls in each Rust port. C made
120 explicit framebuffer `malloc` calls. Those meters see different
interfaces, so these are observations rather than a normalized memory
cost ratio. The transducer port was faster than direct Bend despite more
counted native heap calls; allocation count alone does not explain this
result.

## The larger live version

An earlier 1920×1080 Bend-only window presented roughly 38–40 FPS after
startup on one CPU thread. The current live source uses
`Array.fill.prefix` for its 2,073,600 visible sky pixels, preserving the
zero tail of its 2,097,152-slot framebuffer. A paired 24-frame headless
probe fell from 269.743 to 217.446 ms. I have not remeasured windowed FPS
after that change. The five-way table above is a separate 512×512,
120-frame benchmark; there is no 2K C or Rust control in this experiment.

## Where I landed

The flat benchmark in part one showed that a generic pipeline can become
a vectorized loop. This larger program shows that Bend transducers can
stay close to direct-loop runtime and even beat this direct Bend port,
while the current Bend scene is much longer than either C or Rust by lines
and tokens. The five versions make the tradeoff visible. I would work on
the language's source-level ergonomics and the library's source API before
claiming that this style makes large Bend programs shorter. I would also
want machine-checked showcase properties before calling proof a demonstrated
scene-level win.

## Reproduce

```sh
python3 bench/bullet_cathedral_five_way.py --frames 120 --sessions 21
python3 -m pip install 'tiktoken==0.14.0'
python3 bench/bullet_source_metrics.py
```

The benchmark runner checks every frame in every implementation before
timing. The linked raw report contains the resulting source and compiler
hashes so the five-way table can be tied to the measured files.
