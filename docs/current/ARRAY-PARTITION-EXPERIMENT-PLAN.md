---
created_at: 2026-09-23T20:54:17+02:00
status: active
---

# Array-backed partition experiment

This plan investigates whether representing each emitted partition as a Bend
`Array` improves performance over the current `List` representation. It is a
benchmark and design investigation; it does not yet change the public
`partition_all` API or the compiler.

## Correct representation model

At the Bend source level, `Array<T>` is written as a perfect binary tree. The
backends store it as one flat block: machine-word arrays use packed 32-bit cells
and other elements use one owned term per cell. Native `get`, `set`, and `swap`
use indexed memory operations. Pattern-matching the tree can split and copy
blocks, so the experiment must use indexed operations rather than walk the tree.
See the [runtime description](../../../bend/bend2/docs/BendRT/main.typ) and the
[Array lowering](../../../bend/bend2/comp.ts).

The current `partition_all` holds a `List<A>`, prepends each input, and reverses
the group at emission. Generated native code can relink consumed list nodes in
place, and the allocator can reuse freed cells. The List path is therefore a
real optimized baseline, not a model where every reverse necessarily allocates
a second list. Existing full group-sum measurements are 1.455–1.491x the
handwritten direct baseline by the upper confidence bound; those results did
not measure an Array implementation. See the [current baseline](BENDLANG-MAIN-BASELINE.md).

## Prototype shape

Keep the first implementation inside the benchmark fixture. Represent a chunk
as an `Array<U32>` plus a logical element count. Initialize unused capacity to
zero and make every consumer read only indices below the logical count. This
avoids introducing a generic “default value” requirement and isolates the cost
of flat Array storage for the motivating scalar benchmark.

For width `w`, allocate capacity `2^ceil(log2(w))`. Width zero preserves the
existing policy: initialization stops before the source is read and allocates
no chunk. For positive widths, write each input at the next slot. Emit when the
logical count reaches `w`; on source completion, emit a final nonempty partial
chunk once. Test non-power-of-two widths so padding and the logical count are
exercised. Do not use tree destructuring to read the resulting Array.

This U32 experiment does not establish a generic representation. `Array.new`
currently requires a `Data` initializer. Other `Data` element types could use
an option-valued slot (`Maybe<A>`) or an explicit fill value, each with its own
cost. Affine elements cannot be initialized by duplicating a placeholder. A
general initialized-prefix buffer would need a separate language/runtime
capability or a different representation; that is outside this experiment.

## Worksets

Each workset should be separately reviewable and committed, following the
existing project workflow.

### 1. Add an isolated correctness and code-shape probe

Add a benchmark fixture and runner that compile against the pinned
`bendlang/bend:main` candidate. Keep the prototype `partition_array` reducer
and chunk type in the fixture, not `transduce.bend`.

Cover widths 1, 2, 3, and 8, with input lengths 0, `w-1`, `w`, `w+1`, and a
multi-chunk length that leaves a partial final chunk. Check chunk order, every
element, and the exact logical count. Also check zero-width behavior, initial
downstream stop, stop after a complete chunk, and completion with a partial
chunk. Run semantic output checks on both JS and native. Inspect generated C to
confirm the fixture uses the flat indexed Array operations and has not
accidentally introduced tree pattern matches.

**Exit:** both backends agree with an independent ordered reference for every
case, including stopping and partial completion.

### 2. Compare folding consumers

Compare three implementations over the same prebuilt List input and equivalent
work:

1. Existing `partition_all` with its List group and a consumer that sums each
   group immediately.
2. Fixture-only `partition_array` with an Array group and a consumer that sums
   only the logical prefix immediately.
3. A handwritten fused partition-and-sum loop as a lower-overhead reference.

The List and Array transducer lanes must share the same source, reducer
lifecycle, width, output, and stop behavior. The fused loop is a reference for
the attainable cost; it is not used to attribute an Array-versus-List
difference. Include widths 1, 2, 3, and 8, with full consumption and a bounded
consumer that stops after a small number of groups.

### 3. Compare retaining consumers

Add a consumer that retains every emitted group until source completion, then
traverses all groups and computes the final sum. Compare List groups and Array
groups under the same input, widths, and output. Keeping chunks live until the
later traversal prevents the test from treating retained data as reusable
storage.

This pair measures the case where an emitted group escapes. It also separates
“the allocator reuses storage after the consumer drops a group” from “the
producer can overwrite a group that remains live”; only the former is
automatic and safe under the current ownership model.

### 4. Measure allocation and native runtime separately

Use paired native sessions with alternating lane order and calibrated batches
long enough to exceed timer resolution. Report ratios and bootstrap confidence
bounds for Array/List and direct/List. Keep allocation instrumentation out of
the timed binaries. In separate instrumented builds, count Array-block
allocations/frees, List-node allocations/frees, allocator free-list hits, and
peak live storage for fold and retain consumers. Record generated C size,
compile time, source/compiler/harness hashes, workload, and all raw samples.

Do not infer reuse from source ownership alone: verify the allocation and free
counts. Do not claim Array/List parity from the current List-versus-direct
benchmark.

## Priority

Effort means semantic complexity, ownership proof, API commitment, and ongoing
maintenance, rather than lines of code.

| Order | Work | Impact | Effort | Value | Decision |
| --- | --- | --- | --- | --- | --- |
| 1 | Correctness and code-shape probe | Critical: prevents an invalid comparison | Low–medium | Highest: verifies the prototype and boundary cases | Do first |
| 2 | Allocation accounting | High: shows whether Array saves real storage work | Medium | Very high: directs later optimization | Pair with timing work |
| 3 | Immediate-fold comparison | High: targets the known full-partition gap | Medium | Very high: establishes whether Array helps the common non-escaping case | Required |
| 4 | Retaining-consumer comparison | High: tests the ownership case where buffers cannot be overwritten | Medium | High: determines whether Array helps materialized results too | Required |
| 5 | General affine-capable chunk buffer | Potentially high | Very high: requires representation/runtime/API design | Conditional: only pursue if the Data prototype demonstrates value | Defer |
| 6 | General producer/consumer chunk elision in the compiler | Potentially high across operations | High: escape, ownership, order, and stopping proofs | Conditional: compare after identifying measured costs | Defer |

## Decision gates

- If Array chunks improve fold and retain workloads across representative
  widths, and the result survives allocation accounting, design a public
  Array-backed partition API. Keep the logical length explicit for padded
  capacities.
- If Array helps folding but not retention, investigate a general
  producer/consumer fusion rule for chunks that do not escape. Preserve
  materialized output for consumers that retain chunks.
- If Array helps neither case, keep the List API and use the measured allocation
  profile to choose the next design experiment. Do not add RC-count checks or
  an initialized-prefix runtime primitive without evidence that either would
  address the measured cost.
- Do not make any compiler rule depend on the name `partition_all`, the
  `Array` constructor names, or one benchmark's reducer shape. Any later
  optimization should follow general checked terms and ownership facts.

## Out of scope

This investigation does not replace `partition_all`, claim generic affine
support, add borrowing or reference-count tests, alter `bendlang/bend`, or
promise that Clang removes heap allocation. It produces evidence for those
design choices before any production API or compiler change.

## Progress

### Workset 1: correctness and code shape — complete

The fixture-only U32 reducer and ordered direct reference are in
`bench/array_partition/semantic_probe.bend`. The fixture passes 20 grouping
cases across widths 1, 2, 3, and 8, plus five lifecycle cases, on JS and native.
Generated C contains indexed `blk_at`, `blk_read`, and `blk_write` operations,
with no `blk_half` call sites in the probe. The benchmark supplies the capacity
depth alongside the width; workset 2 will derive that depth for every workload.

The report is
[`semantic_probe-results.json`](../../bench/array_partition/semantic_probe-results.json).
It records compiler source SHA-256
`04d2f814c799808efd136f5a56f22236d0dd128045dbf562c227d2f17fae992d` and
confirms equal JS/native output. Its 25 checks include the independent ordered
reference and Array chunk summation.

### Workset 2: folding consumer equivalence — complete

[`fold_probe.bend`](../../bench/array_partition/fold_probe.bend) compares
List-backed `partition_all`, the fixture Array reducer, and a direct fused
partition-and-sum loop. It covers full consumption and a two-group bounded
consumer at widths 1, 2, 3, and 8. All eight cases return the same sum on JS
and native; the native output matches JS exactly. See
[`fold_probe-results.json`](../../bench/array_partition/fold_probe-results.json)
and rerun with `python3 bench/array_partition/run_fold_probe.py --bend-main
/path/to/bendlang/bend/main.ts`.

The semantic probe constructs equivalent numeric Lists independently because
Bend Lists are affine and cannot be reused across lanes. The timed harness must
build its lane's List before starting the timer; this check does not claim those
List construction costs are measured equally. No runtime or allocation
conclusion follows from these Boolean checks.

The Array fold now has two readers for an A/B comparison. The original reader
switches between `ReadArray` and `ReadValue` in two recursive steps per item.
The second reader uses one recursive loop step per item and a helper to unpack
the computed `Array.get` result. The JS and native checks confirm that List,
both Array readers, and direct fusion return equal sums for all eight widths
and stopping cases. This establishes correctness only; their relative native
cost remains to be measured.

### Workset 3: retained chunks — complete

[`retained_probe.bend`](../../bench/array_partition/retained_probe.bend) sends
all emitted List groups or Array chunks into `into_list`, completes the source,
then traverses the retained groups and sums them. The 97-element input leaves a
one-element last group at widths 1, 2, 3, and 8. Both representations produce
the expected total of 4656 and group counts 97, 49, 33, and 13, respectively;
all four checks agree across JS and native. See
[`retained_probe-results.json`](../../bench/array_partition/retained_probe-results.json).

This confirms the test actually observes every retained chunk after
transduction. It does not imply reuse is possible while the emitted chunk is
still live; allocation accounting is needed to quantify the difference.

### Workset 4: initial allocation and timing pass — partial checkpoint

[`measure_array_partition.py`](../../bench/array_partition/measure_array_partition.py)
now compiles separate native binaries for the List, Array, and direct lanes,
calibrates each workload, collects paired samples, and instruments separate C
builds for heap and chunk-allocation counts. Source Lists are built before
`IO.now`; transduction, result consumption, and source cleanup are timed. The
instrumented binaries are never used for timing.

The run was paused while executing a sample for `fold_bounded_w3`. Six of the
12 planned workloads are complete: all four full-fold widths and bounded-fold
widths 1 and 2. Each completed workload has ten sessions and five samples per
lane per session, and every sample's checksum matched the expected value. The
raw samples and allocation counters are preserved in
[`measurement-results-partial.json`](../../bench/array_partition/measurement-results-partial.json).
It records the tested compiler entry hash
`8c4dde245581f55afcfc3e731b4f45a62a601e5c6b3368f2efbed6c06a989c14`, compiler
source hash
`04d2f814c799808efd136f5a56f22236d0dd128045dbf562c227d2f17fae992d`, fixture
hashes, and the measurement harness hash.

| Workload | Repeats per sample | List median (ms) | Array median (ms) | Direct median (ms) | Array/List ratio, 95% interval | Direct/List ratio, 95% interval |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full, width 1 | 1,048,576 | 227.0 | 376.0 | 183.0 | 1.657 [1.650, 1.664] | 0.813 [0.809, 0.816] |
| Full, width 2 | 1,048,576 | 322.0 | 837.0 | 210.0 | 2.598 [2.587, 2.610] | 0.622 [0.617, 0.628] |
| Full, width 3 | 1,048,576 | 330.0 | 726.0 | 214.0 | 2.189 [2.182, 2.196] | 0.644 [0.641, 0.647] |
| Full, width 8 | 1,048,576 | 355.5 | 425.0 | 193.0 | 1.202 [1.193, 1.213] | 0.550 [0.546, 0.556] |
| Bounded, width 1 | 524,288 | 306.5 | 309.5 | 305.5 | 1.008 [0.993, 1.025] | 1.003 [0.995, 1.011] |
| Bounded, width 2 | 262,144 | 188.0 | 192.0 | 187.5 | 1.021 [1.016, 1.025] | 1.000 [0.996, 1.003] |

These timing rows were collected with the original two-phase Array reader,
before the single-loop candidate was added. That reader loses to List on full
folding at all four widths, by 20% to 160% in these samples; the bounded
width-1 and width-2 results are close to List. Direct fusion is faster than
List for all full-fold widths, but close to List for the two bounded widths.
Do not apply these ratios to the new reader. The confidence intervals bootstrap
the ten session-level ratios; they describe run-to-run variation on this one
machine, not variation across machines. Balanced three-lane timing and the
single-loop reader still need measurement.

The separate allocation probes completed for these six rows (18 lane/workload
combinations). For full folding, the Array lane made and freed one flat backing
block per emitted chunk; the List lane allocated List nodes for the groups, and
the direct lane allocated no group storage. The bounded Array lane made and
freed two blocks per input, matching the two groups it emitted. The measured
List and Array allocation requests were mostly served by Bend's internal
free-list: the counter records runtime heap allocation calls and free-list
hits, not operating-system `malloc` calls or allocations removed by Clang. In
the non-retaining folds, allocated group storage is freed as the consumer
finishes each group. The timed peak growth in Bend's managed heap was 32 bytes
for these instrumented samples; this is not process RSS. The retained rows are
needed to see how this changes when groups remain live.

The report marks itself `paused_partial`. It is a historical checkpoint for
the two-phase Array reader and the original order schedule. Its allocation
counts remain useful, but its Array timing ratios are superseded by the
follow-up measurements below.

### Array reader A/B and balanced full folds — complete

[`reader-ab-results.json`](../../bench/array_partition/reader-ab-results.json)
compares the original two-phase reader with the single-loop reader. It uses 12
sessions, five samples per lane per session, and alternates the two lane orders
six times each. Every sample returns the same checksum. The reader variants
have identical Array block allocation and free counts, so the timing change
comes from the read-and-sum implementation.

| Width | Two-phase median (ms) | Single-loop median (ms) | Single-loop / two-phase, 95% interval |
| ---: | ---: | ---: | ---: |
| 1 | 188 | 187 | 0.992 [0.983, 1.000] |
| 2 | 412 | 217 | 0.528 [0.526, 0.530] |
| 3 | 362 | 188 | 0.533 [0.529, 0.537] |
| 8 | 425 | 237.5 | 0.546 [0.542, 0.550] |

The simpler reader is about 47% faster at widths 2, 3, and 8, and makes no
meaningful difference at width 1. This confirms that the earlier full-fold
Array timings included a substantial consumer cost.

[`corrected-fold-results.json`](../../bench/array_partition/corrected-fold-results.json)
compares List, the single-loop Array reader, and direct fusion with all six
three-lane orders cycled twice across 12 sessions. Each lane has five samples
per session, every checksum is checked, and allocation instrumentation remains
outside timed binaries.

| Width | List median (ms) | Array median (ms) | Direct median (ms) | Array/List, 95% interval | Direct/List, 95% interval |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 229 | 379.5 | 188 | 1.661 [1.653, 1.669] | 0.823 [0.814, 0.833] |
| 2 | 321 | 434 | 217 | 1.350 [1.346, 1.354] | 0.637 [0.634, 0.640] |
| 3 | 329.5 | 378.5 | 214 | 1.176 [1.170, 1.181] | 0.642 [0.640, 0.644] |
| 8 | 356 | 237 | 193 | 0.649 [0.647, 0.651] | 0.545 [0.543, 0.547] |

With the better reader, Array remains slower than List at widths 1, 2, and 3,
but is faster at width 8. Direct fusion remains fastest at every width. This
rules out a simple global conclusion that Array chunks always lose; it also
does not support replacing List as the default for every width. The fold inputs
still contain 96 values, so every width divides evenly and this run says
nothing about partial-final-chunk cost.

The remaining measurement work is to add live Array-block peak counts, run
retained consumers over 97 values so the last chunk is partial, and compare
bounded consumers on both 96-value inputs and inputs of `2 * width + 1`. Then
inspect the generated C only if a material gap remains, and apply the decision
gates above. The harness cycles through all lane permutations and uses 12
sessions by default; the pinned candidate can be regenerated with the existing
`prepare_static.py` workflow if its prepared files are no longer available.
