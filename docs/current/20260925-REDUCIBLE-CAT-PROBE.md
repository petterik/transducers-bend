---
created_at: 2026-09-25T15:08:50+02:00
updated_at: 2026-09-25T15:08:50+02:00
status: measured
---

# Reducible-source `cat` probe

The existing `mapcat` maps each input to a `List` and then reduces that list.
This probe instead maps each input to a `Source` and drives it into the
downstream reducer. The inner fold neither starts nor finishes that reducer;
the outer transduction still owns completion. This is a library-only change:
the compiler and the public transducer API were not changed.

The concrete example maps each `U32` to a two-element `SamplePair` source.
JS and native agree with List-based `mapcat` on a sum, an ordered retained
output, and `take(3)`, which stops midway through the second pair. A custom
`Bag` destination records exactly one completion. The existing companion
positive and negative fixtures also pass.

On two million List inputs, 48 shuffled native sessions with Clang `-O3`
produced these results. Times are microseconds; the ratio intervals are
paired bootstrap 95% intervals. Timed allocation requests exclude input
construction.

| Path | Median time | Timed allocation requests |
| --- | ---: | ---: |
| Handwritten direct fold | 3,361.5 µs | 9 |
| List-fragment `mapcat` | 8,513.0 µs | 4,000,009 |
| Reducible-source `cat` | 3,774.5 µs | 9 |

The source path took 0.426 times the List path (interval 0.401–0.451) and
1.045 times the direct path (interval 0.978–1.172). The latter interval
includes parity, so this run does not establish a reliable speed difference
from direct code. It does show that fragment allocation is avoidable for this
source and consumer: the source path has no per-input timed heap requests.

This is deliberately narrow evidence. The stage's fragment source type is
fixed (`SamplePair`), the elements are `U32`, and the timed consumer is sum.
Other reducible shapes, affine elements, retained fragments, and expensive
source drives may behave differently. A reusable `cat` can accept any source
whose concrete type and drive are known at the stage's type, but this probe
does not yet establish a convenient public signature for that abstraction.
The next API decision is whether List-based `mapcat` should remain a
convenience function while a source-based variant becomes the efficient
general path. This result does not imply that `partition_all` can avoid its
observable chunks.

Reproduce the semantics with `python3
experiments/affine_xf/probe_companion.py --bend-main
../bend/bend2/main.ts`. Reproduce the benchmark with `python3
experiments/affine_xf/measure_reducible_cat.py --bend-main
../bend/bend2/main.ts --output /tmp/reducible-cat-results.json`. The
recorded samples and compiler/fixture hashes are in
`experiments/affine_xf/reducible-cat-2m-isolated-results.json`.
