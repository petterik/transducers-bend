---
created_at: 2026-09-27
status: iterator-rust-comparison-verified
---

# Bullet Cathedral with Rust iterator pipelines

The [Rust control](../../bench/bullet_cathedral_control.rs) now uses
`Iterator::map`, `filter`, `flat_map`, `collect`, and `fold` for the scene's
main transformations. It generates friendly hit events by mapping active IDs
to bullets, filtering, expanding nine candidate cells with `flat_map`,
filtering collisions, and collecting hits. A second iterator counts hostile
player hits, as Bend's `hits` and `incoming` transductions do. Rendering maps
each layer to sprites, expands each sprite to pixels through a shared lazy
`sprite_pixels` pipeline, and folds ink into the owned framebuffer. The event
Vec and framebuffer are intentional stored state; pixel streams and candidate
cells are not collected. The [C control](../../bench/bullet_cathedral_control.c)
remains a direct-loop baseline.

The [cross-language runner](../../bench/bullet_cathedral_cross_language.py)
compiled Bend's generated C with Apple Clang 17 `-O3`, C with Clang 17
`-O3 -ffp-contract=off`, and Rust 1.95 with `-C opt-level=3 -C target-cpu=native`.
On an M3 Max, one CPU thread, 21 shuffled process sessions, it checked every
one of 120 sequential 512×512 frames. All three implementations agreed on
each frame's pixel checksum, accepted-hit count, and remaining shield. The
cumulative checksum was `367602200`. Internal timing includes setup,
simulation, rendering, checksums, and cleanup; it excludes startup,
compilation, and presentation.

| 120-frame lane | Median | Min–max |
| --- | ---: | ---: |
| Bend transducers, fresh framebuffer | 269.385 ms | 268.567–272.532 ms |
| C direct loops, fresh framebuffer | 242.912 ms | 242.219–246.859 ms |
| Rust iterators, fresh framebuffer | 246.524 ms | 245.872–249.773 ms |
| C direct loops, reused framebuffer | 242.643 ms | 242.186–250.977 ms |
| Rust iterators, reused framebuffer | 245.583 ms | 245.080–249.868 ms |

On the fresh-buffer lanes Bend took 1.11× C time and 1.09× iterator Rust
time. Rust iterators took 1.01× C time on this fixture. These medians show
composed pipelines running in the same range as direct loops; they do not
establish parity or a general language ranking. The earlier
[direct-loop report](20260927-BULLET-CATHEDRAL-CROSS-LANGUAGE.md) measured
227.616 ms for a 250-line Rust implementation. That is a different program
shape, retained as a historical ablation. The new Rust source is 18.9 ms
slower in the fresh lane, but the two measurements were taken in separate
benchmark runs, so the difference is descriptive rather than a paired
estimate of the iterator rewrite's cost.

The runner's complete-file counting rule strips blank lines and `#` or `//`
comments. It includes each file's own CLI driver, excludes imported
libraries and generated C, and counts raw `o200k_base` tokens on the full
source file:

| Handwritten scene | Code lines | Code-only lexical tokens | Raw BPE tokens |
| --- | ---: | ---: | ---: |
| Bend | 600 | 8,379 | 8,610 |
| C direct loops | 230 | 3,092 | 3,513 |
| Rust iterators | 260 | 3,348 | 3,498 |

The [size audit](20260927-SHOWCASE-SIZE-AND-PROOFS.md) traces the large Bend
gap to its more explicit language syntax and to how this particular scene
spells out source drivers and per-layer transducer chains. Rust's standard
`Iterator` adapters offer a concise generic source and transformation API.
Every public transducer stage used by the Bend scene already exists in the
local library; missing `map` or `map_indexed` implementations are not the
cause of the scene's size. The checked Bend proof artifacts remain separate
from these scene-file counts and do not prove the whole showcase.

The [raw report](../../bench/bullet-cathedral-iterator-cross-language-20260927.json)
contains all samples, per-frame triples, allocation counts, exact compiler
flags, toolchain versions, and source hashes. The [source metrics](../../bench/bullet-source-metrics-20260927.json)
pin the tokenization and file hashes. The Rust allocation meter counted
1,126 timed allocation/reallocation calls in the fresh lane, the same count
as the former direct-loop control; that is consistent with the iterator
pipelines avoiding per-pixel collections. It does not establish zero
allocation in the scene.
