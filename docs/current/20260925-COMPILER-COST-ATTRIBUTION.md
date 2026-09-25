---
created_at: 2026-09-25
status: current
---

# Compiler cost attribution on ordinary Bend programs

The fork changes general compiler paths, so its compile-time cost matters even
when a program has no transducers. We measured 25 randomized sessions per
fixture and compiler variant on this Mac. Every variant used the same
`bendlang/main` snapshot and test inputs. `static_only` replaces only
`comp.ts`; `checker_only` replaces `bend.ts` and `main.ts`; `fork` replaces all
three. `static_inert` loads the fork's `comp.ts` but bypasses its `specialize`
call at `def_body`. All checkup variants produced identical output.

| Fixture | Upstream median | Static inert | Static only | Checker only | Full fork |
| --- | ---: | ---: | ---: | ---: | ---: |
| Simple checkup | 58.3 ms | 57.7 ms | 58.3 ms | 58.9 ms | 59.3 ms |
| Array JS compile | 150.3 ms | 149.9 ms | 166.0 ms | 152.3 ms | 170.2 ms |
| Pipeline JS compile | 85.0 ms | 85.7 ms | 87.9 ms | 86.0 ms | 89.8 ms |
| 80 upstream test checkup | 304.1 ms | 303.6 ms | 328.1 ms | 306.7 ms | 329.3 ms |
| 160 upstream test checkup | 546.9 ms | 545.0 ms | 574.3 ms | 548.6 ms | 577.9 ms |

The 80- and 160-test groups are upstream Bend tests, independent of this
transducer library; Array and pipeline are local library fixtures. The static
rewrite's execution accounts for nearly all repeatable overhead:
the inert copy tracks upstream, while `static_only` adds about 3–11% on the
larger fixtures. The checker and interpreter changes add about 0–2% in
isolation. These are process-inclusive elapsed times, so the difference is
not a CPU profile; the ablation is the causal evidence. In the 80-test checkup,
the static rewrite was queried 3,605 times and refused every query. That
establishes that ordinary code pays for traversal and eligibility checks even
when no callback is specialized.

No compiler rewrite is justified from this measurement alone. A future cost
fix should avoid whole-body specialization where it cannot apply, then prove
the gate, non-transducer semantics, and transducer code shape unchanged. The
current workset only attributes the cost. Raw timing samples, compiler hashes,
and the isolated-candidate script are in
[`compiler-ablation-results.json`](../../experiments/affine_xf/compiler-ablation-results.json)
and [`measure_compiler_ablation.py`](../../experiments/affine_xf/measure_compiler_ablation.py).
