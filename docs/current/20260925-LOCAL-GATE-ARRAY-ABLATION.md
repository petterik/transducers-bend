---
created_at: 2026-09-25T18:02:00+02:00
status: validated-locally
---

# Local compiler gate and Array fusion ablation

## Compiler correctness on this Mac

The Bend upstream gate assumes an SSH mini cluster. We copied its current
gate code into a temporary directory, changed transport and build concurrency
for this machine, and kept its discovery, checking, interpretation, JS/native
builds, execution, and verdict logic. The reproducible adapter is
[`run_local_bend_gate.py`](../../experiments/affine_xf/run_local_bend_gate.py).
The complete run on fork branch `codex/transducer-companions` at `f8229311`
reported **1,461 / 1,463** tests passing. The only differences were the
native `gfx_clicks` and `gfx_window` tests: they expect a *headless* machine,
while this Mac has a desktop display. `gfx_clicks` waited for an event and
timed out; `gfx_window` produced its normal event-fold output. The same two
tests, built with stock `bendlang/main` and run on this Mac, behaved identically.
They are host-expectation mismatches, not fork regressions.

The gate exposed one real fork gap before that run: a value-mode interpreter
used an unconverted source body even though the checker inserted a companion
conversion. Its compiled JS/native versions already returned the expected
value. The fork now records which definitions were rewritten and normalizes
the checked body only for those definitions. This makes the interpreter return
`7` for `tests/check/companion_owned.bend` while preserving the original
surface spelling of stuck template expressions. Across 983 positive
interpreter fixtures, that test was the only output difference from the old
fork. The transducer library gate still passes **38 / 38** JS/native fixtures,
including code shape and callback counts. A fresh comparison against upstream
covered 982 positive checkup fixtures and 487 other checker fixtures with
zero unintended mismatches. Direct value-mode runs of the public `xf_public`
and `mapcat_public` fixtures also print their expected results.

The local adapter sets a writable Clang module cache. The first sandboxed run
could not write Clang's default cache or open loopback sockets; rerunning
outside that sandbox resolved those host restrictions. This report makes no
claim about performance or graphics behavior on the maintainers' machines.

## Where the Array difference begins

The [earlier matrix](20260925-COMPANION-PERFORMANCE-MATRIX.md) found an
approximately 9% Array-source gap against handwritten traversal with equal
timed allocation counts. We split that path into five ordered folds over the
same flat Bend Array and sum:

1. Handwritten `acc + x + 1` traversal.
2. Handwritten traversal calling the same `U32.inc` mapper as the transducer.
3. `reduce_array` with `Control` and an inline sum step, without reducer or
   companion selection.
4. Static `map` and `sum` reducer over Array.
5. Public `Xf.transduce` with Array's source companion.

Each run allocates its input before the microsecond clock read. Clang `-O3`
compiles all five modes into one native binary. Sessions shuffle the modes,
compare paired times, and verify the same result. At 2²⁰ elements, 40 sessions
gave these median ratios (95% bootstrap interval):

| Comparison | Ratio | Timed heap requests in both paths |
| --- | ---: | ---: |
| Handwritten `U32.inc` / handwritten `x + 1` | 1.000 (0.983–1.015) | 2,097,159 |
| Plain `Control` fold / handwritten `U32.inc` | 1.103 (1.088–1.113) | 2,097,159 |
| Static reducer / plain `Control` fold | 1.000 (0.975–1.020) | 2,097,159 |
| Public companion / static reducer | 1.011 (0.995–1.017) | 2,097,159 |
| Public companion / handwritten `x + 1` | 1.097 (1.087–1.115) | 2,097,159 |

At 2¹⁸ elements, 32 sessions reproduced the split: plain `Control` over
handwritten `U32.inc` was 1.095 (1.072–1.117); public over direct was 1.101
(1.078–1.121), with 524,295 timed heap requests in every mode. Samples are in
[`array-fusion-ablation-results.json`](../../experiments/affine_xf/array-fusion-ablation-results.json)
and [`array-fusion-ablation-262k-results.json`](../../experiments/affine_xf/array-fusion-ablation-262k-results.json).
The [fixture](../../experiments/affine_xf/array_fusion_ablation.bend) and
[`measure_array_fusion.py`](../../experiments/affine_xf/measure_array_fusion.py)
reproduce the experiment.

The emitted C for `reduce_array` still tests the `Stop` tag at both leaves
and internal nodes. That is necessary for the general fold: a downstream
`take` or custom reducer may stop before traversing the remaining tree. The
plain `Control` fold pays essentially the entire measured gap, so this run
does **not** implicate stage composition or companion lookup. Eliminating
those tests only in a proven non-stopping pipeline would require a reusable
interprocedural proof and specialization across the recursive source fold.
Ownership alone does not prove that stopping is impossible.

We should not add an Array-named compiler rule for this roughly 10% gap.
If another branching source shows the same significant cost, a bounded,
name-independent no-stop specialization would become a justified experiment.
Until then, the performance contract should distinguish allocation-equivalent
List/custom-source pipelines that are near handwritten speed from stoppable
Array traversal with this measured control cost. List-building `mapcat`,
partition chunks, and dynamic Vec growth retain their real construction costs.

The current fork's process-inclusive compile-time ratios to stock upstream,
from 25 paired sessions, are 1.024 for a small pipeline, 1.111 for the Array
fixture, and 1.090 for an 80-test checkup batch. These numbers include Bun
startup and are recorded in
[`compiler-overhead-interpreter-followup.json`](../../experiments/affine_xf/compiler-overhead-interpreter-followup.json).
