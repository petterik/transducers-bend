---
created_at: 2026-09-27
status: source-size-and-proof-audit
---

# What the showcase size and proofs establish

The matched 512×512 Bullet Cathedral files contain 600 Bend, 230 C, and
250 Rust nonblank, noncomment code lines under the published complete-file
rule. The Bend file uses `X.map`, `X.filter`, `X.cat`, `X.map_with`,
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
make the scene file shorter while leaving the same code to maintain. A
reusable source abstraction might remove tens of scene lines, but the
non-rendering parts alone are 338 lines. Therefore, library extraction of
the current transducers cannot establish a full-scene code-size win against
the 230-line C port. Achieving that honestly would require a larger Bend
ergonomics or scene-design change, with the same behavior, checks, and
complete-file accounting. The current article should present speed,
composability, and checked laws as the verified benefits of this version.

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
