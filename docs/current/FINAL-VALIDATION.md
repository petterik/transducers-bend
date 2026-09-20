---
created_at: 2026-09-20T20:05:38+02:00
status: current
---

# Final validation checkpoint

Date: 2026-09-20. This report covers the committed design and library work
through `19812ee` and the isolated compiler candidate prepared from compiler
SHA `01adea0f6ef5bf13f76cfb222cc563d879440f873ea0070c0629dcc19da7c32e`.
The sibling `../bend` checkout is at `b1f9c936` and remained clean. The library
hash used by the parity report is
`b14ed740061378cb39433ffcd14cf39f58785d8ff623b9a05437bc0cf61da98a`.

## Passing checks

| Check | Result |
| --- | --- |
| `python3 tests/run.py --bend-main /tmp/transduce-workset0/main.ts` | 20/20 JS/native files, including laws and `api_surface` |
| `python3 tests/run.py` with the sibling reference compiler | 20/20 JS/native files |
| `test_source_shapes.py` | String loop 1; Array tree 0; boxed state 0; tree-entry control 0; all JS/native outputs match |
| `test_auto_loop.py` | 5/5 positive/refusal/failure cases |
| `adversarial.py` | 16/16 variants |
| `test_list_driver.py` | Boxed List source gate passes |
| `test_scoped_facts.py` | Candidate and reference outputs match; guarded loop plus generic fallback retained; JS bytes identical |
| `static_composition_probe.py` | Native/JS `[9, 9, 7, 7, 3, 3]`; zero Reducer/Reduction records and `Clo.apply` occurrences |
| `representation_probe.py` | Scalar and buffered outputs match on JS/native; no Reducer/Reduction records or `Clo.apply` |
| `review/check_tree_entry.py` | JS/native `[9, 1000, 2000, 1017]`; zero guarded-tree markers |

The calibrated List parity report is
[bench/fusion-parity-acceptance-current.json](bench/fusion-parity-acceptance-current.json).
It used 20 retained blocks in each of two sessions, 320 reductions per batch,
a 100 ms duration floor, balanced lane order, and 4,000 paired bootstrap
resamples. The three-map, type-changing, mixed-full, mixed-take-32, and
expensive-callback rows had upper 95% transducer/direct ratios of 1.022, 1.023,
1.024, 0.993, and 0.990. All rows matched an independent Python oracle. The
dynamic-short smoke row is a correctness check only because its timer is below
resolution.

## Measured representation and cost boundaries

The scalar probe emitted 97,589 bytes of C and 16,652 bytes of JS, with 13
`heap_alloc` and 9 `term_pak` occurrences in C. The buffered probe emitted
182,545 bytes of C and 45,032 bytes of JS, with 44 `heap_alloc` and 45
`term_pak` occurrences. These are code-shape counts, not allocation or peak
heap measurements. Buffered group storage is required state and remains an
explicit cost.

## Promotion status

The known wrong-code tree rewrite is fixed by conservative refusal, so no known
correctness failure remains in the maintained candidate scope. The scalar/list
loop is still an isolated compiler experiment. Tree specialization is not
promoted: continuation-entry layouts and arbitrary incoming control/state
relations still lack a proof. The short-loop policy remains diagnostic because
the independent known-state/dynamic-length cases regress under candidate
heuristics.

GPU execution and the full upstream project gates are outstanding. The checked
suite runs CPU with `--gpu off`; no device result is inferred. `ttok` is not
installed and the historical cluster gate is unavailable in this environment.
These are release blockers, not passes. The next compiler work should either
complete the typed tree/continuation proof or leave generic tree lowering as
the stable fallback, then rerun the full backend matrix before promotion.
