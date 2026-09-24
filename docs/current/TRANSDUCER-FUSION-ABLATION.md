---
created_at: 2026-09-24T13:58:08+02:00
updated_at: 2026-09-24T14:31:18+02:00
status: current
---

# Transducer fusion ablation on bendlang/main

This experiment separates three costs in a `partition_all` pipeline: the
public transducer pipeline, creation and consumption of ordinary List chunks,
and a handwritten loop that consumes the source without creating chunks. It
also compares raw `bendlang/main` with the isolated static-callback candidate.
The sibling `../bend` checkout was read-only.

## Setup and confidence

Both compiler inputs use Bend commit
`2f50df1ed36fcc3ebe6c75a2046e94001a44645d`. The upstream `comp.ts` SHA-256 is
`34783e2779f23b0f7be586f70130292ea367fbe74d3d12b327d434633dc93850`; the
candidate with the static-callback pass is
`083adb324e749a1ca20376896d3a14e716ccc355f019736e7b4c9dba6ab54bee`. The
entry point, library, fixtures and benchmark harness hashes are recorded in
the two raw reports linked below.

Each operation starts from a prebuilt, affine List of 200,000 ordered U32
values. It consumes the complete input and sums the values, or computes an
order-sensitive rolling hash. There are 12 sessions and five paired samples
per lane per session. Each lane is calibrated independently to at least 150ms
per sample; elapsed time is normalized by that lane's repetition count. The
95% intervals below bootstrap the within-compiler session ratios. The raw and
candidate runs were not paired against each other, so their compiler-to-compiler
speedup is a comparison of medians, not a paired confidence interval. Source
construction is outside the timed region; traversal, reduction, and source
cleanup are inside it. Allocation instrumentation uses separate builds and
does not affect the reported timings.

The three lanes are:

- **Transducer:** `over_list` + `partition_all` + `take` + `reducing`, using
  the public transducer library.
- **Materialized:** handwritten Bend code that builds each ordered List chunk
  and consumes it with the same sum or rolling hash.
- **Direct:** handwritten Bend code that feeds source values to the same
  consumer without constructing chunks.

The materialized control is important: the direct loop alone cannot tell
whether a gap comes from transducer callback/state work or from chunk storage
and traversal.

## Results

Median milliseconds per 200,000-value operation on the static-callback
candidate:

| Consumer | Width | Transducer | Materialized | Direct | Transducer / materialized | Materialized / direct |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Sum | 3 | 0.680 | 0.424 | 0.226 | 1.60 [1.60, 1.62] | 1.79 [1.77, 1.80] |
| Sum | 8 | 0.629 | 0.447 | 0.207 | 1.41 [1.38, 1.41] | 1.98 [1.96, 2.00] |
| Ordered hash | 3 | 0.664 | 0.424 | 0.245 | 1.57 [1.57, 1.59] | 1.59 [1.56, 1.60] |
| Ordered hash | 8 | 0.641 | 0.454 | 0.247 | 1.41 [1.38, 1.40] | 1.72 [1.70, 1.74] |

Brackets are bootstrap 95% intervals for the ratio. The order-sensitive hash
tracks the sum results closely, so sum commutativity does not account for the
measured gaps.

Raw upstream takes 5.31–6.22ms per transducer operation in these four rows;
the candidate takes 0.63–0.68ms. The ratio of medians is an 8.4–9.4x speedup
from the static-callback pass. Materialized and direct controls remain close
between compiler variants: 0.42–0.45ms and 0.21–0.25ms respectively.

These results support three separate conclusions:

1. **Static callback specialization is a large, measured win.** It cuts the
   public pipeline's runtime by about nine times on this workload, but does
   not yet reach handwritten-loop parity.
2. **Chunk creation and traversal have a separate cost.** Even handwritten
   materialization is 1.6–2.0x slower than the direct loop. The rolling-hash
   control confirms this for an order-sensitive consumer.
3. **The remaining transducer gap is also real.** On the candidate, the public
   pipeline is 1.4–1.6x slower than the handwritten materialized control. The
   timings do not by themselves identify which remaining reducer-state,
   callback, or loop costs account for that difference.

## Allocation and generated-code evidence

The static-callback candidate's separately instrumented sum runs use 256
repetitions of 200,000 inputs (51.2 million input items):

| Lane | Timed List Cons constructions | Timed List frees | Timed free-list hits |
| --- | ---: | ---: | ---: |
| Transducer | 51,200,000 | 102,400,256 | 51,200,005 |
| Materialized | 0 | 51,200,256 | 5 |
| Direct | 0 | 51,200,256 | 5 |

Thus the public List pipeline constructs one additional List Cons per input
item in this fixture. The handwritten materialized loop does not issue timed
Cons allocations. Generated C shows that Bend reuses unique, consumed source
Cons cells while forming its chunks: it rewrites a source node and points the
new List constructor at that same location. The producer and consumer are
affine, so the source cell is available after its old value is consumed. This
is reuse of input cells, not reuse of a previously returned chunk, and it does
not imply that a retained chunk could be mutated.

This is evidence against adding runtime reference-count checks to make the
handwritten path work. Bend's existing ownership analysis already enables
this specific reuse. It is not evidence that Clang can generally remove the
transducer's List construction: the instrumented candidate still requests one
Cons per input in that path.

## Retaining chunks

The retained consumer collects every emitted chunk, then traverses all chunks
to compute its checksum. It therefore tests the case where an emitted chunk
must remain valid after later input has been processed. This was measured on
the same `bendlang/main` commit with raw upstream and the isolated candidate,
using 200,001 input items, 12 sessions, five samples per session, and separate
allocation-instrumented builds. Each sample was checked against the expected
checksum. These rows are native timings; cross-compiler ratios below compare
medians and are not paired confidence intervals.

| Compiler | Width | List ms/op | Array ms/op | Array / List, bootstrap 95% interval | C bytes, List / Array |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw upstream | 3 | 4.102 | 5.250 | 1.243 [1.236, 1.250] | 162,872 / 169,862 |
| Static-callback candidate | 3 | 0.848 | 0.809 | 0.901 [0.897, 0.904] | 122,323 / 129,316 |
| Raw upstream | 8 | 3.734 | 5.000 | 1.381 [1.375, 1.391] | 162,872 / 169,862 |
| Static-callback candidate | 8 | 0.682 | 0.784 | 1.332 [1.327, 1.338] | 122,323 / 129,316 |

The candidate is 4.8–5.5x faster than raw upstream for retained List chunks,
and 6.4–6.5x faster for retained Array chunks, by the ratio of medians. The
Array/List result changes between widths 3 and 8, so these two points do not
establish a general crossover rule. They also compare this fixture's List and
Array implementations, not a common built-in partition API.

Timed allocator requests per input item show what remains live and what the
candidate removed:

| Compiler | Width | Lane | All heap allocations | List Cons allocations | Array blocks allocated | Peak retained Array blocks |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| Raw upstream | 3 | List | 6.000 | 1.333 | 0 | 0 |
| Static-callback candidate | 3 | List | 1.333 | 1.333 | 0 | 0 |
| Raw upstream | 8 | List | 5.375 | 1.125 | 0 | 0 |
| Static-callback candidate | 8 | List | 1.125 | 1.125 | 0 | 0 |
| Raw upstream | 3 | Array | 6.000 | 0.333 | 0.333 | 66,667 |
| Static-callback candidate | 3 | Array | 1.333 | 0.667 | 0.333 | 66,667 |
| Raw upstream | 8 | Array | 4.750 | 0.125 | 0.125 | 25,001 |
| Static-callback candidate | 8 | Array | 0.500 | 0.250 | 0.125 | 25,001 |

The counters classify List Cons cells and Array blocks separately; total heap
allocations include other runtime heap objects. In the retained List lane,
the candidate's total allocation requests equal the output List structure:
one inner Cons per input plus one outer group Cons per chunk. The raw compiler
requests another 4.7 or 4.25 heap objects per input at widths 3 and 8. The
static-callback candidate has removed those transient allocations in this
case. Generated C supports that interpretation: raw C contains runtime
`Continue`, `Stop`, and `Partitioning` constructor/match references, while the
candidate C has only their unused tag definitions and no references to those
tags. `Reducer` and `Reduction` likewise have no runtime constructors in raw
C. Constructor-site counts are code-shape evidence, not dynamic counts; the
allocator instrumentation is the runtime measurement.

For the Array lane, peak live Array blocks exactly equal the retained output
group count, and all blocks are released after consumption. The fixture
therefore keeps one buffer per emitted Array chunk alive through the checksum
pass. It does not attempt to borrow or recycle an earlier emitted chunk. This
supports the ownership boundary: reuse the current, uniquely owned working
buffer while it is being filled, but allocate a distinct result for each
chunk that escapes to a retaining consumer. The candidate Array lane also has
more List Cons requests than raw upstream (0.667 vs 0.333 per item at width 3,
0.250 vs 0.125 at width 8), despite its much lower total heap traffic. The
current measurements do not explain that change; keep it as an open Array
fixture question instead of treating its speed result as a general Array
allocation win.

This evidence changes the next compiler step. Static-callback specialization
already removes the per-input Control/Partitioning heap traffic in this
retaining pipeline. Do not add a separate Control-record rewrite without a
new profile showing another concrete cost. The fold ablation still has one
additional Cons per input and remains 1.4–1.6x slower than the handwritten
materialized control, so the next experiment should test a general
fresh-producer-to-single-use-fold rewrite. It must remove the temporary List
only when it proves non-escape; retained consumers remain the required
negative case.

## Options, prioritized

| Option | Impact | Effort | Value | Decision |
| --- | --- | --- | --- | --- |
| Prototype checked-term producer/consumer fusion for a fresh result consumed exactly once by a fold | High: could remove the temporary chunk and its traversal when semantics permit | High: requires escape, effect, ownership, callback-order, and stop proofs | Very high if it retains all fallbacks and works across user functions | **P1: next experiment** |
| Keep relying on C optimization and existing affine reuse | Medium: preserves the allocation-free handwritten case and improves generated C locally | Low: no new API or compiler rule | Medium: already useful, but the transducer-vs-materialized gap remains | Keep as baseline, not the whole strategy |
| Add an explicit reducer sink that returns a completed reusable buffer | Medium to high for chunk-building pipelines | High: expands reducer state/API and requires ownership-return semantics | Medium: useful when fusion cannot prove non-escape; premature before the fold experiment | Defer |
| Special-case `partition_all` or individual transducer names in the compiler | High for selected examples | High: compiler/library coupling and correctness burden grows per transducer | Low: conflicts with the goal that new transducers compose automatically | Reject |

## Next experiment

Implement only an isolated, checked-term prototype for the general pattern
“a known, fresh List result is consumed exactly once by a known fold.” Do not
match `partition_all`, `Reducer`, or transducer names. Keep this first step
small enough to inspect generated terms and C. The candidate must leave the
original program unchanged whenever it cannot prove all of the following:

- the intermediate List is fresh, locally owned, and does not escape or get
  observed by another use;
- the consumer is a known fold whose callback order and accumulator result can
  be preserved;
- callback effects and early `Stop` behavior are preserved, including an
  initially stopped reducer and a stop in the middle of a chunk;
- the rewrite does not duplicate, drop, or reorder live affine values.

Use the sum and ordered-hash folds as positive cases, then add a custom
producer/fold pair with no transducer-library names to demonstrate the rule is
general. Retaining a chunk, an unknown consumer, and an effectful callback are
negative cases that must keep the original materialized code. Compare JS and
native results, check source cleanup and callback counts, and inspect emitted
C for the disappearance of intermediate Cons construction. Measure generated
code growth and retain a small explicit limit. Do not move a prototype into
upstream compiler code or claim the general optimization works until these
gates pass.

The experiment is deliberately about a fold consuming a fresh result, not a
general borrowing API. If it cannot prove non-escape or preserve stop/effect
semantics, the fallback remains ordinary materialization. A later sink API can
be reconsidered using a concrete failing case rather than designed in advance.

## Reproduction

The paired result files retain raw samples and build/source hashes:

- [`fusion-ablation-upstream.json`](../../bench/array_partition/fusion-ablation-upstream.json)
- [`fusion-ablation-static-callback.json`](../../bench/array_partition/fusion-ablation-static-callback.json)
- [`retain-current-main-upstream.json`](../../bench/array_partition/retain-current-main-upstream.json)
- [`retain-current-main-static-callback.json`](../../bench/array_partition/retain-current-main-static-callback.json)

The fold fixture was checked on both JS and native with 17 semantic cases,
including partial final chunks and order-sensitive results, against both raw
upstream and the candidate. The candidate also passed the 23-fixture library
suite on both backends. The benchmark harness is
[`measure_array_partition.py`](../../bench/array_partition/measure_array_partition.py),
and the cases are in [`fold_probe.bend`](../../bench/array_partition/fold_probe.bend).
