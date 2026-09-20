# Loop and tree profitability checkpoint

## Decision

Keep the isolated scalar/list loop specialization enabled for the candidate
compiler, but do not promote a broader policy. The tree specialization remains
disabled because its continuation-entry and independently supplied-control
proof is incomplete. The short-loop policies remain diagnostic only; no runtime
threshold or source-shape heuristic is justified by the current evidence.

## Fresh list parity gate

`bench/fusion-parity-acceptance-current.json` was generated from compiler SHA
`01adea0f6ef5bf13f76cfb222cc563d879440f873ea0070c0629dcc19da7c32e` with the
unchanged public list pipeline and an independently written direct Bend
traversal. It used 20 retained blocks in each of two sessions, 320 reductions
per batch, a 100 ms minimum batch, balanced lane order, and 4,000 paired
bootstrap resamples (seed `20260920`). Every row matched the Python oracle and
every retained batch met the duration floor.

| Case | Transducer median | Direct median | Ratio | Upper 95% | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Three-map chain | 142 ms | 140 ms | 1.014 | 1.022 | pass |
| U32 → Nat → U32 | 136 ms | 134.5 ms | 1.011 | 1.023 | pass |
| Mixed predicate, full | 147 ms | 145 ms | 1.014 | 1.024 | pass |
| Mixed predicate, take 32 | 379 ms | 383.5 ms | 0.988 | 0.993 | pass |
| Expensive callback, take 32 | 389 ms | 393 ms | 0.990 | 0.990 | pass |

The provisional engineering limit is an upper ratio of 1.05. The mixed rows
contain one guarded loop marker in the transducer C and none in the direct C;
the two simple composition rows do not need a marker. All rows have no
`Clo.apply` occurrences. This is candidate-only sequential List/CPU evidence;
it does not establish Array, GPU, or production-compiler readiness.

The smoke report `bench/fusion-parity-workset5.json` retains the dynamic-short
correctness row. Its timer values are zero milliseconds, so it is deliberately
not a performance claim. Short-loop regressions and the independent known-state
counterexamples remain recorded in [SHORT-LOOPS.md](SHORT-LOOPS.md).

## Open boundary

The current tree refusal is the correct result for arbitrary incoming controls
and continuation entries. Re-enabling it requires an explicit proof of leaf and
branch state flow, continuation frame layouts, and preservation for every
reachable back edge. Profitability work resumes only after that proof exists.
Until then, generic tree lowering is the declared fallback and Array parity is
an open performance item.

