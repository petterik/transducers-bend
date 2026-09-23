---
created_at: 2026-09-23T20:54:17+02:00
status: proposal
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
