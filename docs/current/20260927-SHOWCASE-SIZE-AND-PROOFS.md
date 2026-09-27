---
created_at: 2026-09-27
status: source-size-and-proof-audit
---

# What the showcase size and proofs establish

The matched 512×512 Bullet Cathedral files contain 600 Bend transducer,
600 Bend direct, 230 C direct, 260 Rust iterator, and 250 Rust direct
nonblank, noncomment code lines under the complete-file rule. The Bend
transducer file uses `X.map`, `X.filter`, `X.cat`, `X.map_with`,
`X.map_indexed`, `X.keep`, `X.comp*`, `X.into`, and `X.transduce`. All are
already implemented in [`xf.bend`](../../xf.bend) and
[`transduce_core.bend`](../../transduce_core.bend). In particular,
`map_indexed` is a public library stage; the showcase only calls it.

The Bend file's 600 code lines break down as follows, using source line
boundaries from this version of [`bullet_cathedral.bend`](../../bench/bullet_cathedral.bend):

| Source lines | Responsibility | Code lines |
| --- | --- | ---: |
| 1–54 | Imports and scene types | 36 |
| 55–322 | Simulation and collisions | 225 |
| 323–630 | Sprite sources, transforms, and rendering | 262 |
| 631–720 | Frame assembly and CLI | 77 |

Moving an application-specific source or renderer into the library would
make one scene file shorter while leaving the same code to maintain. The
direct Bend port removes the transducer pipelines and their custom source
drivers, then adds explicit loops and Array state threading. It is exactly
the same length as the transducer port under this rule. The size gap to C
and Rust therefore persists in this direct implementation; extraction of
the current transducers alone cannot establish a full-scene code-size win.

## Where the size difference comes from

The complete-file comparison includes the scene's command-line driver in
each language and excludes imported libraries and generated C. Splitting the
files at their simulation, rendering, and driver boundaries gives a more
useful view of the gap. These are descriptive source partitions, not a
line-by-line allocation of causes:

| Responsibility | Bend transducers | Bend direct | C direct | Rust iterators | Rust direct |
| --- | ---: | ---: | ---: | ---: | ---: |
| Scene types, simulation, collisions | 261 | 269 | 119 | 127 | 127 |
| Rendering and frame assembly | 287 | 279 | 77 | 96 | 86 |
| Driver and output | 52 | 52 | 34 | 37 | 37 |
| **Complete file** | **600** | **600** | **230** | **260** | **250** |

The largest difference is in rendering. C and direct Rust implement one
`draw_sprite` loop and call it for each layer. Iterator Rust implements one
lazy `sprite_pixels` pipeline (`map → filter → map`), expands each layer
with `flat_map`, and applies pixels with `fold`. Bend transducers implement
a `SpritePixels` source and distinct chains in `draw_sprites`,
`draw_bullets`, `draw_hits`, and `draw_drones`. Direct Bend replaces those
chains with one shared sprite loop, but still needs recursive loop helpers,
record matches, and owned Array threading. Its special transducer bullet
chain carries squared distance from clipping into shading; a measured
attempt to use that record for every transducer sprite pass slowed the
whole scene. These are properties of the measured programs, not minimum
program sizes for any language.

Simulation has a similar, smaller effect. C and direct Rust generate each
active bullet once in `step` and branch between friendly and hostile work.
Both Bend ports and iterator Rust make two traversals: one gathers friendly
hits, and the other counts hostile player hits. The iterator Rust port uses
`flat_map` for nine nearby candidates and collects hit events. All five
preserve the same per-frame results. The two custom Bend transducer source
drivers, `Nearby` and `SpritePixels`, account for 64 of its 600 code lines;
moving them to a helper module would change their location, not erase them.

The language also makes these designs more explicit. The sibling fork's Bend guide
states that Bend does little inference, uses `match` for branches and
structural recursion for repetition, and requires explicit reuse of affine
values. In this file, that appears as `~` type arguments, `+` reuse marks,
record matches, recursive source drivers or direct loops, and helpers such as
`ink_after` to thread an owned Array through `Array.get` and `Array.set`. Tail calls compile
to loops; the extra source syntax does not imply recursion overhead in the
native loop. Bend also has infix arithmetic sugar, so the many explicit
`U32.add` and `F32.mul` calls are partly a style choice. We have not measured
how much shortening that style would save, or whether it would retain the
same type checking and runtime behavior in this file.

The transducer standard library is **not the main missing piece** in this
comparison: every public stage the transducer scene uses, including `map_indexed`, is
already in the library. A clearer generic API for bounded, context-dependent
sources might reduce adapter boilerplate, but a proposed `Tabulate` helper was
too specific to promote to the transducer core. The remaining gap includes
application logic and the current language's explicit syntax. The 103 lines
of machine-checked transducer laws are reported separately; they are not
inside the 600-line scene.

## Machine-checked transducer laws

All three files below checked with the sibling Bend fork on 2026-09-27:

- [`list_map_fold_law.bend`](../../proofs/list_map_fold_law.bend) proves by
  induction over `List<U32>` that a pure map followed by a fold agrees with
  feeding each mapped item directly to the fold; it also proves that two
  List maps compose. This is a model of the fusion law, not a theorem about
  `X.transduce` or generated C.
- [`no_stop_control_law.bend`](../../proofs/no_stop_control_law.bend) uses
  the library's actual `Control<Empty, U32>`. Its `Stop` case has no live
  permit, and induction shows that its List drive agrees with a total fold.
- [`api_stage_laws.bend`](../../proofs/api_stage_laws.bend) uses the actual
  `T.map`, `T.filter`, `T.step`, and `T.sum` constructors. It proves one map
  step forwards the mapped value, an always-true filter forwards its input,
  and an always-false filter preserves the accumulator.

These artifacts add 103 code lines and 1,357 raw `o200k_base` tokens,
reported separately from the scene and library in the
[source metrics](../../bench/bullet-source-metrics-20260927.json). They
trust Bend's checker and source semantics. They do not prove the full
transducer lifecycle, the compiler's fusion rewrite, or the native runtime.

## Showcase argument and checks

The [geometry document](../../proofs/bullet_cathedral_geometry.md) is a
written mathematical argument that the nine nearby grid cells cover every
possible geometric hit under the scene's motion bounds and that its health
and framebuffer indices are in range. It explicitly leaves an IEEE-754
rounding boundary open; it is **not machine-checked**.

The [independent oracle](../../bench/bullet_cathedral_oracle.py) enumerated
54,018,048 bullet–drone pairs over the measured 120 frames and found all
76,049 geometric overlaps within the nine-cell search. The
[cross-language runner](../../bench/bullet_cathedral_cross_language.py)
checked each of the 120 frame triples (pixel checksum, accepted-hit count,
and remaining shield) across Bend, C, and Rust. These are exhaustive checks
of the finite measured run and differential tests, respectively. Neither
is a machine-checked theorem about arbitrary runs, the renderer, or the
compiler. There is currently **no end-to-end machine-checked showcase
proof**.
