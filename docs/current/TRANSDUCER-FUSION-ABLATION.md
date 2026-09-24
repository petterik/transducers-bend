---
created_at: 2026-09-24T13:58:08+02:00
updated_at: 2026-09-24T17:38:39+02:00
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

The earlier fold and retention tables, including the historical group-fold
probe, use `IO.now()`, which reports whole milliseconds on both backends. Their
per-operation values inherit that quantization. The later C-inline and
checked-term probes use the benchmark-only `BenchClock.now_us()` effect and
record calibrated sample durations in integer microseconds. Native uses the
runtime's monotonic nanosecond clock, converted to microseconds; JS scales
`performance.now()` to microseconds, with effective resolution determined by
its host. Historical reports remain in their original units and are not
relabeled as higher-precision measurements.

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

This evidence motivated the checked-term producer/fold experiment below.
Static-callback specialization already removes the per-input
Control/Partitioning heap traffic in the retaining pipeline. Do not add a
separate Control-record rewrite without a new profile showing another concrete
cost. The remaining List-pipeline allocation is not removed by merely
inlining small functions or relying on Clang.

## Explicit group-state fold probe

The bench-only `group_fold` reducer tests a second route to chunk-free group
processing. It keeps a state `S` for the current group, updates it with an
`advance` callback for each input, and sends `finish(state)` to the downstream
reducer when the group is complete. It does not build chunks. The sum example
uses a scalar group state; the order-sensitive hash example carries a hash
segment that lets the downstream reducer combine groups without changing
order. This is a narrower contract than `partition_all`: callers cannot retain
or otherwise inspect each group's original values.

The probe ran on the same pinned compiler candidate with 200,000 input values,
16 sessions, five paired samples per session, and a 150ms calibration target.
The following median operation times are from the historical millisecond
timer; ratio intervals are paired bootstrap 95% intervals within sessions.

| Consumer | Width | List pipeline ms/op | `group_fold` ms/op | `group_fold` / List | `group_fold` / direct |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sum | 3 | 0.707 | 0.361 | 0.502 [0.496, 0.508] | 1.432 [1.403, 1.461] |
| Sum | 8 | 0.660 | 0.368 | 0.537 [0.532, 0.541] | 1.484 [1.461, 1.506] |
| Ordered hash | 3 | 1.443 | 0.701 | 0.475 [0.439, 0.507] | 1.187 [1.088, 1.281] |
| Ordered hash | 8 | 0.697 | 0.378 | 0.539 [0.531, 0.548] | 1.291 [1.274, 1.305] |

Across these workloads, `group_fold` takes about half the List pipeline's time
and is about 19–48% slower than direct consumption. It is also about 19–25%
faster than the handwritten loop that materializes List chunks. Separate
allocation instrumentation saw no per-input List Cons or Array allocation in
`group_fold`: over 256 repetitions of 200,000 items, it made five generic heap
allocations, the same fixed count as the materialized and direct controls. The
List pipeline made 51.2 million timed List Cons allocations. The group-fold C
output is slightly larger than the List pipeline's C output (131KB vs 127KB
for sum, 133KB vs 127KB for ordered hash), so the runtime win comes with a
small code-size increase in this fixture.

Semantic probes cover List and range sources, empty input, width zero and one,
downstream `take`, partial groups, and order-preserving hash composition. An
additional probe consumes affine `Array<U32>` elements in the group-state
callback. These probes passed on both JS and native. This is evidence that an
explicit state-fold reducer can avoid chunk construction under the current
compiler and can compose with more than one source adapter. It is not evidence
that the compiler has generalized transducer fusion: the API intentionally
replaces arbitrary group output with a caller-chosen summary, and the compiler
has no new fusion rule.

The result makes `group_fold` a useful comparison point for the planned
compiler experiment. A general producer/consumer rewrite should be measured
against both this narrower no-chunk API and the public `partition_all`
pipeline, while preserving the latter's observable chunk semantics. Do not
make `group_fold` the required implementation of `partition_all`.

## Does more C inlining remove the remaining cost?

I recompiled the same generated List-pipeline and direct-loop C with Apple
Clang 17.0.0 (build 1700.6.4.2) at `-O3`. The only change was forcing every
host `INLINE` function to use `always_inline`. This is a focused native probe,
not a Bend compiler change: 200,000 values per operation, 16 operations per
timed sample, and 12 paired sessions. Source construction stayed outside the
timed region, and the new microsecond clock recorded the sample durations.

| Lane | Default median µs/op | Forced inline median µs/op | Forced / default, paired 95% interval |
| --- | ---: | ---: | ---: |
| Public List pipeline | 715.53 | 628.25 | 0.890 [0.873, 0.911] |
| Direct loop | 306.94 | 230.97 | 0.769 [0.724, 0.821] |

Forcing inlining improves both lanes in this probe, but helps the direct loop
more. The paired List/direct ratio grows from 2.304 [2.255, 2.356] to 2.667
[2.516, 2.807]; the relative gap grows by 15.8% [7.9%, 23.1%]. The generated
C grows by 31 bytes for the List lane, while the native binary size is
essentially unchanged. A separate forced-inline allocator run still records
51.2 million timed List Cons allocations for 51.2 million inputs, the same as
the default List pipeline.

This rejects forced inlining as a fusion solution for this case. Clang can
reduce some call overhead, but inlining alone neither removes the chunk nodes
nor brings this transducer closer to direct consumption. One workload does not
establish a global inlining policy. The useful compiler experiment still needs
to represent and prove that a fresh chunk is consumed once, then replace its
construction and traversal with equivalent state updates. The complete paired
samples and generated-code hashes are in
[`clang-inline-ablation.json`](../../bench/array_partition/clang-inline-ablation.json).

## Checked-term constructor-spine prototype

I tested whether a bounded, name-independent rewrite over checked terms could
cover the missing producer/fold case. The temporary compiler prototype
inlined small, pure, fully applied user definitions when either the producer
returned a visibly known constructor spine or the consumer matched a
visibly-known constructor argument. It unrolled recursive folds only while
that matched spine got strictly smaller, and substituted a non-constant
constructor argument directly only when its parameter was affine. It did not
edit `../bend` or the checked-in compiler.

The positive fixture used ordinary names: `produce_pair` returned a two-item
List and `consume_sum` folded it. At the larger inline budget, generated C
reduced the pipeline to scalar additions and removed both List Cons
allocations. This proves that a small, statically visible producer/fold can be
rewritten without recognizing transducer names. It does not cover a
runtime-length List built in a loop.

The dynamic benchmark gives the more important result. It used 96 source items,
widths 3 and 8, four sessions with two paired samples per session, and a
100ms minimum sample batch. The candidate allowed four inlines per checked
definition; the budget-32 prototype did not finish compiling the width-3
List-pipeline fixture within 20 seconds, while the unchanged candidate
compiled it in about 0.20 seconds and the constructor-only patch also compiled
in about 0.20 seconds. With the four-inline budget, lane builds took about
1.03–1.14 seconds versus 0.45–0.56 seconds for the baseline; the List lane
was 1.11–1.14 seconds versus 0.54–0.56 seconds.

| Width | Baseline List µs/op | Prototype List µs/op | Timed Cons per op, baseline/prototype | Generated C bytes, baseline/prototype |
| ---: | ---: | ---: | ---: | ---: |
| 3 | 0.315129 | 0.314857 | 96 / 96 | 142,944 / 142,944 |
| 8 | 0.337014 | 0.337672 | 96 / 96 | 142,944 / 142,944 |

The per-operation timings come from long calibrated batches; the cross-compiler
comparison was not paired, so the sub-percent differences are not evidence of
a speedup or regression. More decisively, the compiler emitted byte-identical
C for each lane, and allocator instrumentation found the same 96 List Cons
allocations per 96 inputs. The materialized, direct, and `group_fold` lanes
also had identical C and allocation counts between the two compiler inputs.
The rule does not see the runtime-accumulated chunk in `partition_all`, so it
does not improve the real transducer pipeline.

All 23 existing fixtures produced matching JS/native outputs with the bounded
prototype. The full runner's lifecycle callback-count probe could not find its
`expand_one` JavaScript function after the compiler inlined it, so that
function-name-based instrumentation gate needs a call-site-aware replacement
before it can validate an inlining candidate. No semantic fixture failed.

This is not a viable general fusion pass: a static two-item example fuses, but
the runtime producer shape that matters stays unchanged, and a larger inlining
budget has severe compile-time cost. Do not move this pass into
`bendlang/main`. The checked-term rewrite also needed extra typing and affine
substitution rules; those costs are not justified by the benchmark result.

## Options, prioritized

| Option | Impact | Effort | Value | Decision |
| --- | --- | --- | --- | --- |
| Design a dedicated internal producer/fold representation for runtime-built chunks | High if it proves single-use and preserves stop/finish behavior | High: requires escape, effect, ownership, callback-order, and stop proofs | Very high only if it removes measured allocations across user functions | **P1: design the proof boundary, then test one dynamic List producer/fold** |
| Keep relying on C optimization and existing affine reuse | Medium: preserves the allocation-free handwritten case and improves generated C locally | Low: no new API or compiler rule | Medium: already useful, but the transducer-vs-materialized gap remains | Keep as baseline, not the whole strategy |
| Add an explicit reducer sink that returns a completed reusable buffer | Medium to high for chunk-building pipelines | High: expands reducer state/API and requires ownership-return semantics | Medium: useful when fusion cannot prove non-escape; premature before the fold experiment | Defer |
| Special-case `partition_all` or individual transducer names in the compiler | High for selected examples | High: compiler/library coupling and correctness burden grows per transducer | Low: conflicts with the goal that new transducers compose automatically | Reject |

## Next experiment

Do not increase the checked-term inline budget. First design an internal
producer/fold representation for a runtime-built List, with a clear proof
boundary and an unchanged fallback. Test it on a custom `map-then-fold`
producer/consumer pair with no transducer names. It must remove the temporary
List only when it proves all of the following:

- the intermediate List is fresh, locally owned, and does not escape or get
  observed by another use;
- the consumer is a known fold whose callback order and accumulator result can
  be preserved;
- callback effects and early `Stop` behavior are preserved, including an
  initially stopped reducer and a stop in the middle of a chunk;
- the rewrite does not duplicate, drop, or reorder live affine values.

Use the sum and order-sensitive folds as consumers, and try both List and an
independent source adapter. A retained chunk, an unknown consumer, an
effectful callback, an early stop, and affine elements are negative or
boundary cases. Compare JS and native results, check source cleanup and
callback counts, and inspect emitted C for intermediate Cons construction.
Measure compile time and generated-code size as well as runtime. Do not move a
prototype into upstream compiler code or claim general fusion until these
gates pass.

The experiment is deliberately about a fold consuming a fresh result, not a
general borrowing API. If it cannot prove non-escape or preserve stop/effect
semantics, the fallback remains ordinary materialization. A later sink API can
be reconsidered using a concrete failing case rather than designed in advance.

The explicit `group_fold` probe is already a useful lower-allocation reference
when evaluating that rewrite. Its results do not remove the need to test the
compiler rule with an independent producer/consumer pair or retained-output
negative cases.

## Reproduction

The paired result files retain raw samples and build/source hashes:

- [`fusion-ablation-upstream.json`](../../bench/array_partition/fusion-ablation-upstream.json)
- [`fusion-ablation-static-callback.json`](../../bench/array_partition/fusion-ablation-static-callback.json)
- [`retain-current-main-upstream.json`](../../bench/array_partition/retain-current-main-upstream.json)
- [`retain-current-main-static-callback.json`](../../bench/array_partition/retain-current-main-static-callback.json)
- [`group-fold-current-main-static-callback-ms.json`](../../bench/array_partition/group-fold-current-main-static-callback-ms.json)
- [`clang-inline-ablation.json`](../../bench/array_partition/clang-inline-ablation.json)
- [`checked-shape-fold-baseline-us.json`](../../bench/array_partition/checked-shape-fold-baseline-us.json)
- [`checked-shape-fold-budget4-us.json`](../../bench/array_partition/checked-shape-fold-budget4-us.json)
- [`checked-shape-fold-prototype.patch`](../../bench/compiler/checked-shape-fold-prototype.patch)

The fold fixture was checked on both JS and native with 17 semantic cases,
including partial final chunks and order-sensitive results, against both raw
upstream and the candidate. The static-callback candidate passed the
23-fixture library suite on both backends. The isolated checked-term prototype
passed all 23 semantic outputs on both backends, with the lifecycle
function-name instrumentation limitation described above. The benchmark harness is
[`measure_array_partition.py`](../../bench/array_partition/measure_array_partition.py),
and the cases are in [`fold_probe.bend`](../../bench/array_partition/fold_probe.bend).
The group-fold reducer and its affine-input probe are in
[`group_fold_probe.bend`](../../bench/array_partition/group_fold_probe.bend) and
[`group_fold_affine_probe.bend`](../../bench/array_partition/group_fold_affine_probe.bend).
The microsecond benchmark clock is in
[`bench_clock.bend`](../../bench/array_partition/bench_clock.bend), with a
small backend smoke fixture in
[`bench_clock_probe.bend`](../../bench/array_partition/bench_clock_probe.bend).
