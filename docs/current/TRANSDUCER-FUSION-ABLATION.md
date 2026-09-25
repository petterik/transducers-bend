---
created_at: 2026-09-24T13:58:08+02:00
updated_at: 2026-09-25T09:17:39+02:00
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

That gap is specific to the `partition_all` workload above. A separate
map/filter/full-fold benchmark finds the static-callback pipeline at parity
with handwritten code; FoldRegion does not materially change that transducer
lane. It also removes the materialized pipeline's List nodes, while exposing
a remaining per-input branch closure. The separate result and next compiler
experiment are documented in
[`PRODUCER-STEP-FOLD-REGION.md`](PRODUCER-STEP-FOLD-REGION.md).

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

## Dynamic List producer/fold probe

This is a deliberately small dynamic case: a recursively built List is either
mapped into a new List and then folded, or passed through the public `map`
transducer into the same fold. The consumer is tested with both a sum and an
order-sensitive hash. The source List is prebuilt before each timed sample.
The fixture checks equal results on JS and native; the timing fixtures measure
eight 200,000-item inputs per sample using `BenchClock.now_us()`.

Both compiler inputs use `bendlang/main` commit
`2f50df1ed36fcc3ebe6c75a2046e94001a44645d`. The raw compiler has `comp.ts`
SHA-256 `34783e2779f23b0f7be586f70130292ea367fbe74d3d12b327d434633dc93850`;
the isolated static-callback candidate has SHA-256
`083adb324e749a1ca20376896d3a14e716ccc355f019736e7b4c9dba6ab54bee`.
`../bend` remained clean and on `bendlang/main`.

The `083adb…` compiler includes the optional `--identity-self-test` code from
`prepare_static.py`; the current plain static-callback candidate is
`cfd14f244c5a6d2d0b4069d03e53f3682bd09fb535fd15d2d8757b5f21546579`. The
self-test runs inside the compiler process and does not change generated user
programs. The historical numbers above remain useful, but the matched
static-callback-versus-FoldRegion result below uses the plain candidate on
both sides so the compiler hashes and comparison are explicit.

| Compiler | Lane | Median µs per 200k-item input | Stream / materialized, paired 95% interval | Allocator calls per eight inputs | Generated C bytes |
| --- | --- | ---: | ---: | ---: | ---: |
| Raw upstream | `List.map` + fold | 884.6 | — | 3,200,058 | 101,383 |
| Raw upstream | `over_list` + transducer `map` + fold | 2,777.1 | 3.16 [3.10, 3.28] | 6,400,074 | 125,764 |
| Static-callback candidate | `List.map` + fold | 876.3 | — | 3,200,058 | 101,383 |
| Static-callback candidate | `over_list` + transducer `map` + fold | 208.1 | 0.24 [0.22, 0.27] | 1,600,057 | 98,529 |

This exposes two separate compiler effects. On raw upstream, the streaming
transducer form is about 3.2 times slower than ordinary `List.map` plus fold;
the generated C retains runtime `TransduceContinue` records and makes about
3.2 million more allocator calls across the eight inputs. Relative to raw
upstream, the static-callback candidate removes about 4.8 million allocator
calls from the streaming lane. That candidate takes
about one quarter of the materialized lane's time and makes no per-element
mapped-List allocations. The callback optimization is already doing useful
work, but it is a distinct optimization from eliminating arbitrary
List-producing computations.

The C output makes the boundary concrete. The materialized lane contains a
dynamic `Cons` construction in the map loop. The streaming lane does not have
that constructor, because its source fold calls the downstream step directly.
Clang cannot remove the mapped List from the materialized lane under the
current compiler output. This confirms that source-level producer/fold
composition can be efficient after the compiler specializes the static
callbacks; it does not show that the compiler recognizes and fuses a normal
`List.map` call with a later fold.

The best internal shape is a **typed fold region**, not a runtime producer
closure:

- The source and its loop remain explicit: List, Range, Array, or another
  reducible source.
- The accumulator and configuration remain ordinary runtime state.
- The step callback is closed checked code supplied statically, so the compiler
  can specialize it into the source loop without allocating a closure or
  reducer object per element.
- A List builder may stay virtual inside that region only while the compiler
  proves the result is fresh, single-use, and consumed by a known fold. If the
  List escapes, is retained, has another use, or reaches an unknown consumer,
  emit the existing materialized program.

For `partition_all`, this representation needs a nested chunk producer: it must
represent the elements of the current chunk as foldable work that a known
consumer can accept directly. A consumer that stores or otherwise inspects the
chunk still receives a real List or Array. This keeps `partition_all`'s public
value semantics intact while creating a narrow optimization path for
non-escaping consumers.

The optimizer also has to preserve evaluation order. `List.map` finishes
mapping the whole source before a later fold starts. A fused fold interleaves
mapping and reducing, and an early stop could skip later mapping work. The
compiler may cross this boundary only when callback effects, failure/divergence
behavior, reducer stop behavior, completion, and affine uses are all accounted
for. Linear ownership helps prove that a value is consumed once; it does not
prove that a constructed List cannot escape or be observed.

A naive first-class encoding that passes one runtime fold callback through a
recursive producer was also rejected by the current affine checker when the
callback was invoked repeatedly. That points toward storing callback code in
the compiler's fold region, with dynamic state kept separately; it does not
justify a new runtime callback capability or a language change.

The isolated checked-term FoldRegion prototype and its current limits are
described below. It stays in this repository's compiler-preparation harness;
`../bend` remains untouched. The experiment inserts a compiler-only recursive
helper for one structural producer/fold shape. It does not yet provide a
general transducer representation or an upstream-ready implementation.

The test program is
[`dynamic_map_fold_probe.bend`](../../bench/array_partition/dynamic_map_fold_probe.bend);
the microsecond fixtures are
[`dynamic_map_fold_bench_materialized.bend`](../../bench/array_partition/dynamic_map_fold_bench_materialized.bend)
and
[`dynamic_map_fold_bench_stream.bend`](../../bench/array_partition/dynamic_map_fold_bench_stream.bend).
The repeatable runner and raw samples are
[`run_dynamic_map_fold_probe.py`](../../bench/array_partition/run_dynamic_map_fold_probe.py)
and
[`dynamic-map-fold-results.json`](../../bench/array_partition/dynamic-map-fold-results.json).

## Options, prioritized

| Option | Impact | Effort | Value | Decision |
| --- | --- | --- | --- | --- |
| Track direct producer values through a single-use local binding | High: removes the main syntax-shape limitation found by the benchmark | Medium: local use count and checked helper remain explicit | High for this narrow shape; not yet general local propagation | **Complete: one checked immediate-fold alias** |
| Control lane-order effects in the let-alias benchmark | High: prevents a layout/order artifact from being mistaken for optimizer cost | Medium: compare balanced measurement orders | Complete: the let/direct ratio flips with call order | **Done; use balanced or isolated timing** |
| Extend the fold region to filtering and skip semantics | High: tests whether a real transducer changes source traversal and step count | High: needs skip/continue state and callback-order proofs | High if a compositional fold representation emerges | **P1: test map + Boolean filter** |
| Keep relying on C optimization and existing affine reuse | Medium: preserves the allocation-free handwritten case and improves generated C locally | Low: no new API or compiler rule | Medium: useful baseline, but leaves the materialized producer cost | Keep as baseline, not the whole strategy |
| Extend the region to partitioning and reducer stop/finish | High for general transducer pipelines | High: must model buffering, completion, and early stop | Unproven until map/filter composition works | Defer |
| Add an explicit reducer sink that returns a completed reusable buffer | Medium to high for chunk-building pipelines | High: expands reducer state/API and requires ownership-return semantics | Medium: useful when fusion cannot prove non-escape; premature before a measured need | Defer |
| Special-case `partition_all` or individual transducer names in the compiler | High for selected examples | High: compiler/library coupling and correctness burden grows per transducer | Low: conflicts with the goal that new transducers compose automatically | Reject |

## Checked-term FoldRegion prototype

The isolated prototype lives in
[`fold_region_pass.ts.inc`](../../bench/compiler/fold_region_pass.ts.inc) and
is injected by
[`prepare_fold_region.py`](../../bench/compiler/prepare_fold_region.py) into a
fresh candidate made from `bendlang/main`. The rule matches checked function
shapes, not `List.map`, `fold_left`, or transducer names: a direct recursive
List producer must build `Con{map(head), producer(tail)}`, and a direct
recursive consumer must be a full left fold whose `Con` arm calls the consumer
on the tail with `step(state, head)`. It then replaces the consumer's recursive
call with a helper that steps on the mapped head and recurses on the original
tail.

The plain static-callback compiler has `comp.ts` SHA-256
`cfd14f244c5a6d2d0b4069d03e53f3682bd09fb535fd15d2d8757b5f21546579`. The
current checked FoldRegion pass has SHA-256
`9a062f282f1004107ad75d8827f1fa7985a6db36738aeb54691aadb6674d1e0d`, and
the prepared compiler has SHA-256
`d5e55b51598f3b1f6cf4e615cdf84f8bb1649d2e1d2266eb7d5f439e28a0ccb4`.

The pass allows different producer input/output List element types, with the
producer's output List matching the fold's input. The producer can be the
fold's direct input or a value held by exactly one local binding that the body
immediately folds. The pass opens that let, verifies the binder occurs once,
then asks the same structural rule to prove the producer and consumer shapes.
Callbacks still need a conservative checked call graph and the initial state
must be trivial. Unsafe/foreign definitions, parallel calls, dynamic closure
calls, unknown intrinsics, retained output, and unknown consumers fall back to
the original checked term. The helper receives the source expression once,
preserving its evaluation before the fold. This shape has no reducer `Stop` or
completion protocol; such cases do not match the full-fold consumer and are
not optimized.

The use-count gate is defensive. `List<A>` has the same quantity as its
elements, and `List<U32>` is affine by default, so Bend rejects a program that
uses the same affine mapped list twice before the optimizer sees it. The
positive fixture covers one binding and one immediate fold; the fallback
fixture checks an unsafe callback and a let-bound map consumed by `List.length`.

The matched benchmark rebuilt the plain static-callback candidate and the
checked FoldRegion candidate from the same compiler snapshot. It used 16
native sessions, each timing all four compiler/lane binaries in randomized
order; each binary processed eight prebuilt 200,000-item inputs with
`BenchClock.now_us`. Allocation counts came from separate instrumented
binaries. The compiler-to-compiler intervals bootstrap paired
candidate/baseline time ratios from those sessions.

| Compiler | Lane | Median µs per input | FoldRegion / static-only, paired 95% interval | Allocator calls per eight inputs | Generated C bytes |
| --- | --- | ---: | ---: | ---: | ---: |
| Static-callback only | `List.map` + fold | 854.8 | — | 3,200,058 | 101,383 |
| Checked FoldRegion candidate | `List.map` + fold | 238.8 | 0.27 [0.25, 0.30] | 1,600,057 | 97,323 |
| Static-callback only | streaming transducer map + fold | 232.6 | — | 1,600,057 | 98,529 |
| Checked FoldRegion candidate | streaming transducer map + fold | 220.5 | 1.00 [0.91, 1.07] | 1,600,057 | 98,529 |

For this workload, the structural rewrite removes 1,600,001 allocation calls
across the eight materialized inputs and brings ordinary `List.map` plus fold
to parity with the streaming transducer pipeline. Its paired runtime is about
73% lower than the static-only materialized lane; the unchanged streaming lane
shows no measurable regression. The order-sensitive hash and sum agree with
the direct controls on both JS and native.

The pass also fused custom-named map/fold functions and a separate source
adapter returning a List, and moved fresh affine `Array` values through the
rewrite. It leaves retained output, `List.length`, a runtime closure callback,
an `@unsafe` callback, and non-immediate let uses unfused. The full candidate
suite passes 29/29 with codegen gates; raw upstream and static-callback builds
pass the same 29/29 semantic JS/native checks. These are useful checks for
structural matching, order, ownership, and bailouts, but they do not validate
arbitrary producer/consumer programs.

Each synthesized helper is converted back to a source term and passed through
`Bend.def_check` before installation. For type-changing maps, the pass removes
the old consumer body's checked type ascriptions, lets the helper's new source
List type determine the branch variables, then checks the entire generated
helper again. The type-changing fixture generated ten helpers and all ten
passed the checker, including a `Maybe<Array<U32>>` payload; the harness asserts
every installed helper was rechecked.
The rule still handles only a direct recursive List producer into a full fold.
It has not fused `filter`, `keep`, `partition_all`, a non-List source, early
stop, completion, or retained-chunk semantics.

This is evidence that a small structural producer/fold optimization can
eliminate a type-changing intermediate without recognizing library names. It
is not yet evidence that adding transducers automatically composes into such
regions: the pass has one producer shape and one consumer shape, with only one
supported alias form for the producer.

The current four-lane `Maybe` probe compares streaming `keep`, a directly
nested `List<Maybe<U32>>` map/fold, the same map bound to a local before the
fold, and direct consumption. Each lane processes 1.6M values; 32 randomized
native sessions use the microsecond clock and allocator requests are counted
in separate builds. FoldRegion reduces the nested map/fold from 8,482.5µs and
3,200,005 requests on the static-callback candidate to 1,932µs and five fixed
requests. Its paired time ratio versus the static-callback build is
0.224 [0.204, 0.251]. Against direct consumption in the same FoldRegion build,
the nested map/fold ratio is 0.999 [0.882, 1.159], consistent with parity.

The single-use let-bound shape falls from 8,258µs and 3,200,005 requests to
3,175µs and five fixed requests. Its FoldRegion/static-callback ratio is
0.387 [0.376, 0.405]. This validates allocation elimination through that
local alias. The canonical lane order gave a let/direct ratio of 1.625, but
four cyclic measurement orders changed the ratio from 0.619 to 1.625,
depending on the position of each lane. Each FoldRegion C output is 137,787
bytes, but its C hash changes with the order. The shared-process benchmark
therefore does not support an intrinsic latency comparison between these two
lanes. The measured keep lane remains at five fixed requests; its canonical
paired FoldRegion/static-callback ratio is 1.053 [0.985, 1.097], consistent
with no measurable change. Full reports include raw samples, allocations, C hashes,
code sizes, and JS smoke results in
[`maybe-keep-fold-region-results.json`](../../bench/compiler/maybe-keep-fold-region-results.json).
The balanced lane-order controls are
[`maybe-keep-order-map-let-direct-keep-results.json`](../../bench/compiler/maybe-keep-order-map-let-direct-keep-results.json),
[`maybe-keep-order-let-direct-keep-map-results.json`](../../bench/compiler/maybe-keep-order-let-direct-keep-map-results.json),
and
[`maybe-keep-order-direct-keep-map-let-results.json`](../../bench/compiler/maybe-keep-order-direct-keep-map-let-results.json).

The keep lane remains fixed at five heap requests on both static-callback and
FoldRegion builds. This expanded fixture changes the generated program, so its
keep/direct timing should not be mixed with the earlier standalone
[`maybe-keep-results.json`](../../bench/compiler/maybe-keep-results.json)
timing report. Neither result claims a JS performance measurement.

## Map/filter producer-shape experiment

The single-use let case still only crosses one local when it is the immediate
fold input and has exactly one use; it eliminated 3.2M allocations in the
benchmark fixture. The new fixture
[`fold_region_map_filter.bend`](../../tests/fold_region_map_filter.bend)
checks a reusable custom map producer, then `List.filter`, then `List.foldl`.
It covers accepted-value order with a rolling hash, the exact number of fold
steps, empty input, and an all-rejected predicate. The FoldRegion candidate
and raw Bend both pass the fixture on JS and native. Raw upstream was run in
semantic-only mode because it does not pass this repository's static-callback
code-shape gates; the static-callback and FoldRegion candidates pass all
30 fixture gates.

The usual `List.map` then `List.filter` spelling cannot form this test: Base
types `List.map` as returning `List<&1, B>`, while `List.filter` requires
`List<&2, A>`. The fixture uses a custom checked producer that returns the
reusable list required by `List.filter`, without relying on the compiler to
recognize that producer by name.

This is a deliberate negative optimization result. The FoldRegion preparer
records 72 attempts, zero fused calls, zero generated helpers, and zero helper
rechecks for the fixture; it safely falls back with `producer-body-shape`.
The existing producer matcher accepts a branch shaped like
`Con{mapped_head, recursive_tail}`. Checked `List.filter` instead calls a
Boolean-selecting helper whose two branches either return the recursive list
unchanged or prepend the head. That means the producer emits zero or one value
per input, while the current rule only models exactly one. Since the compiler
did not generate a fused helper, no timing or allocation claim is made for this
case; benchmarking that unchanged fallback would not measure fusion.

### Prioritized options

| Option | Impact | Effort | Value | Priority |
| --- | --- | --- | --- | --- |
| Add a checked `List.filter.put`-shaped exception to FoldRegion | Medium, limited to one helper/control-flow form | Medium: branch and ownership proof; future filters need more cases | Low–medium: tests this library shape but encourages one rule per operation | Defer |
| Design and prototype a typed producer-step/fold region for map, skip, and downstream step | High, potentially reusable across sources and transducers | High: define the normalized checked shape and prove order, effects, totality, ownership, and bailout rules | Highest: tests whether checked behavior composes without operation-name rules | **P1; map + filter lowers through the checked `Emit | Skip` region; performance and independent-shape tests next** |
| Add a public `Reducible`/iterator API now | Potentially high and language-wide | Very high: source lifecycle, completion, early stop, affine elements, and compatibility | Uncertain before the lowering is proven | P2, after the region design |
| Measure fused map/filter against materialized and handwritten-fused Bend | High: decides whether eliminating Lists outweighs closure/control overhead | Medium: dynamic allocation counts, matched native timings, compile time | High: tests end-to-end value, not just the IR rewrite | **P1; structural codegen passes, runtime allocation and timing next** |

### Recommended next work

The typed region now composes checked `Emit | Skip` stages with a full fold
and synthesizes a helper over the original source. The tested map/filter path
passes JS/native order, count, empty, all-rejected, retained-value, and
type-changing Nat-to-U32 cases;
each helper is installed only after `Bend.def_check`. The callback gate is a
deliberate conservative subset, not a proof of termination for every Bend
function.
The first generated-C check finds two dynamic producer List-cons sites upstream
and none in the fused candidate, with about 1 KB less C for this small
fixture. It also shows continuation closure/task allocation sites in the new
loop. Next measure actual allocation traffic and native microseconds over a
dynamic input, against upstream and handwritten fused Bend; include compile
time and generated-code size. If the closure cost remains material, test
whether a generic compiler rule can lower a checked applied match as control
flow. Then add an independently written producer to test that the normal form
is not coupled to this producer implementation.

Keep `take`, early stop, completion changes, and `partition_all` out of this
lowering. Partition needs explicit state and completion semantics beyond
`Emit | Skip`.

If this region requires a separate bespoke compiler pattern for every
transducer, stop and consider a source-level reducible interface with checked
static steps. Do not make that public API change until the region experiment
shows what semantics it must expose. Balanced lane-order runs also remain
necessary: shared-process ratios changed with lane position in the previous
probe, so they cannot establish a let-versus-direct latency gap.

## Reproduction

The dynamic producer/fold probe can be rerun against the synced upstream
compiler and a freshly prepared static-callback candidate:

```sh
python3 bench/compiler/prepare_static.py --output-dir /tmp/transduce-static
python3 bench/array_partition/run_dynamic_map_fold_probe.py \
  --upstream-main ../bend/bend2/main.ts \
  --candidate-main /tmp/transduce-static/main.ts \
  --output bench/array_partition/dynamic-map-fold-results.json
```

For a matched incremental comparison, prepare a plain static-callback
baseline, then compare it with the fold-region candidate using
`--baseline-name static-callback`:

```sh
python3 bench/compiler/prepare_static.py --output-dir /tmp/transduce-static
python3 bench/compiler/prepare_fold_region.py --output-dir /tmp/transduce-fold-region
python3 bench/array_partition/run_dynamic_map_fold_probe.py \
  --upstream-main /tmp/transduce-static/main.ts \
  --baseline-name static-callback \
  --candidate-main /tmp/transduce-fold-region/main.ts \
  --output bench/array_partition/dynamic-map-fold-static-vs-fold-region-results.json
```

The isolated FoldRegion candidate's raw-upstream comparison is recorded in
[`dynamic-map-fold-fold-region-results.json`](../../bench/array_partition/dynamic-map-fold-fold-region-results.json),
and the matched static-only comparison is in
[`dynamic-map-fold-static-vs-fold-region-results.json`](../../bench/array_partition/dynamic-map-fold-static-vs-fold-region-results.json).

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
