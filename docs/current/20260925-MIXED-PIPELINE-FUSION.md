---
created_at: 2026-09-25T13:49:00+02:00
updated_at: 2026-09-25T13:49:00+02:00
status: experimental
---

# Mixed five-stage fusion probe

The simpler shift/take benchmark did not establish that the generic affine
API scales across different stages. This follow-up compares one pipeline with
`map_with(+1)`, `filter(even)`, `remove(multiple-of-three)`, `take(n)`, and
`map_with(+2)`, followed by sum. The input is a prebuilt List of `0..n-1`.
The [`mixed_pipeline_bench.bend`](../../experiments/affine_xf/mixed_pipeline_bench.bend)
fixture has three independent implementations: direct recursive Bend, a
handwritten static reducer recipe, and `V.comp5` with the generic stage
constructors. They agree on the small `n=20` answer `88`; the measurement
script checks each larger answer independently in Python.

Clang `-O3` runs one native CPU thread, randomizes lane order per session,
uses the microsecond clock, and separately instruments timed heap requests.
Raw results are [`200k`](../../experiments/affine_xf/mixed-pipeline-200k-results.json),
[`2m`](../../experiments/affine_xf/mixed-pipeline-2m-results.json), and
[`2m repeat`](../../experiments/affine_xf/mixed-pipeline-2m-confirm-results.json).

| Items / sessions | Static median | Generic median | Paired generic/static median | 95% bootstrap interval | Timed heap requests: static / generic |
| --- | ---: | ---: | ---: | ---: | ---: |
| 200k / 40 | 245 µs | 253 µs | 1.056 | 1.012–1.082 | 9 / 21 |
| 2m / 32 | 2248.5 µs | 2340.5 µs | 1.041 | 1.035–1.050 | 9 / 21 |
| 2m / 48 | 2265 µs | 2333.5 µs | 1.030 | 1.022–1.039 | 9 / 21 |

The generic pipeline has 12 extra fixed timed allocation requests, not an
allocation cost proportional to the source length. Its generated JS has no
runtime `Reducer` record. For this pipeline at two million items, the
generic API is within roughly four percent of the handwritten static
recipe; the clean repeat's 95% interval stays below four percent. This is
specific evidence for these five stages, not a blanket parity result for
`mapcat`, `keep`, partitioning, retained outputs, or other consumers.

The direct recursive lane had medians around 4.2 ms at two million items,
slower than both reducer lanes. It uses two `@unsafe` mutually recursive
functions because safe Bend forbids mutual recursion and computed-value
matches. Its code shape is therefore different from the compiler's
specialized List loop. The handwritten static recipe is the better
reference for isolating overhead from the value API. The direct numbers are
retained in the raw results, but they should not be used as a general claim
that transducers beat all direct Bend programs.

The result supports continuing with the rank-2 affine API and general
specialization rule. It also identifies a modest constant setup cost to
investigate later. It does not justify adding stage-specific compiler rules;
the measured hot loop is already close without them.
