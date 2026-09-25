---
created_at: 2026-09-25
status: current
---

# Control cost on an independent branching source

To test whether the Array result was source-specific, we defined an owned
`Branch` with `Tip` and `Fork` constructors. Its leaves are in encounter order
and carry different values. The direct path and `Control` path use the same
depth-first traversal and `U32.inc`-then-sum operation; the latter wraps the
state in `Continue` and checks `Stop` at each node. Tree construction happens
before the microsecond timer. Runs use one native CPU thread, randomized order,
and 40 paired sessions at each depth.

| Leaves | Direct median | Control median | Paired Control / direct | Timed heap allocations |
| ---: | ---: | ---: | ---: | ---: |
| 262,144 | 581 µs | 656 µs | 1.131 (95% bootstrap 1.104–1.146) | 9 / 9 |
| 1,048,576 | 2,358.5 µs | 2,652 µs | 1.130 (95% bootstrap 1.119–1.135) | 9 / 9 |

Thus the roughly 10% Array gap is not merely an Array adapter artifact. The
branching source shows a roughly 13% full-traversal cost from the general
stopping `Control` path. The count of heap-allocation calls *inside* the timer
is equal; this is traversal/control work, not per-leaf heap allocation. The
total call count differs by two for the initial/final control objects.

The separate stopping tests consume only an ordered prefix and check a
pre-existing `Stop`. At depth 10, CLI value mode, compiled JS, and native
agree on the full sum, 17-leaf prefix sum, and initial-stop result. On large
trees, early-stop and initial-stop timings are dominated by disposing of the
unused owned tree; they are not evidence for a no-stop speedup. They do verify
that a future optimization must preserve short-circuit behavior and affine
consumption.

This is enough evidence to **consider** a general no-stop compiler prototype,
but not to integrate one yet. The proof must establish that the incoming state
is `Continue` and every reachable downstream step remains `Continue`; an
unknown reducer, `take`, or custom source keeps the current path. A prototype
would still need JS/native semantics, ownership, completion, runtime,
compile-time, and generated-code-size checks before it could replace the
current fold. The four requested worksets stop at this decision point.

The [fixture](../../experiments/affine_xf/branch_control_ablation.bend),
[measurement script](../../experiments/affine_xf/measure_branch_control.py),
and raw results at [depth 18](../../experiments/affine_xf/branch-control-results.json)
and [depth 20](../../experiments/affine_xf/branch-control-depth20-results.json)
make the comparison reproducible.
