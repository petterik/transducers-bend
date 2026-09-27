---
created_at: 2026-09-27
status: execution-in-progress
---

# Transducers in Bend: implementation, evidence, and blog post plan

## Progress on 2026-09-27

The required `Array.walk` promotion is implemented in the local fork and
library. The [integration report](20260927-ARRAY-WALK-INTEGRATION.md) records
64/64 library tests, 1470/1470 fork gate cases, a Metal run, vectorized
generated C, and paired Bend/C/Rust flat-Array measurements. The
[512×512 cross-language showcase](20260927-BULLET-CATHEDRAL-CROSS-LANGUAGE.md)
has exact agreement on every frame and 21-session timing. The
[local upstream comparison](20260927-UPSTREAM-LOCAL-REGRESSION.md) covers all
16 sequential, eight-thread CPU, and Metal runtime benchmarks and five
checker benchmarks. An
[evidence-backed article draft](20260927-TRANSDUCERS-BLOGPOST-DRAFT.md) is
available.

For the showcase, use performance as a feasibility result: the composed
Bend program took 1.11× C and 1.18× Rust time on the matched 512×512 run.
The more revealing comparison is handwritten size, source complexity,
safety obligations, and the shared library cost. The current Bend scene
is longer than both controls. Use a named tokenizer for prompt-size
estimates and distinguish those from lexical tokens. Treat code clarity
as a source-reading judgment, not a measured score. State exact proof and
memory-safety boundaries, including that the Rust control uses safe code.
Keep Clojure as the source of the transducer vocabulary; a Clojure runtime
port would answer a different question and is not needed as a slow foil.
The [source metrics](../../bench/bullet-source-metrics-20260927.json) and
[cross-language report](20260927-BULLET-CATHEDRAL-CROSS-LANGUAGE.md)
carry the evidence.

Open gates remain: broader machine-checked proofs of the public API and
showcase; C/Rust ports
of the separate 1920×1080 live variant; and final review of the article and
its media. The draft states those boundaries explicitly.

## Goal

Tell the story of building reusable, source-independent transformations in
Bend, making their composition compile efficiently, and testing the result
against direct Bend, C, and Rust. The post should teach the mechanism and
show what the generated program actually does. Its performance headline must
come from the completed implementation and measurements.

Promoting the bounded `Array.walk` from a generated-C probe into the Bend fork
and this library is **required work for this post**. The [proposal](20260926-BOUNDED-ARRAY-WALK.md)
provides the design and first measurement, not a production implementation.
The blog's flat-Array SIMD and C-parity claims wait for the integrated result.

Deliverables are: the fork and library changes with regression tests; raw,
reproducible benchmark reports; checked Bend or Lean proof artifacts and an explicit
proof boundary; C and Rust Bullet Cathedral implementations; source and
generated-code excerpts; a final post with the video and image; and an
appendix containing commands, versions, checksums, and full results.

## Starting facts and language for the post

- The current public API is [`xf.bend`](../../xf.bend) with
  [`transduce_core.bend`](../../transduce_core.bend). A source implements
  `Type.source(value)` and supplies an owned, push-style drive. Its method is
  not currently named `.reduce`, and it does not return a pull iterator. The
  [public API guide](20260925-PUBLIC-API.md) is authoritative for examples.
- `transduce(xf, rf, initial, source)` configures the stage recipe with the
  reducer, starts it once, lets the source drive it, and completes it once.
  A stage value owns settings and is used once. Explain that distinction from
  Clojure's transducer-as-reducing-function-transformer and Rust's lazy
  iterator adapters without calling the Bend stage “already initialized.”
- Clojure introduced transducers in **1.7**. Its reference defines the
  init, step, completion, and `reduced` contracts, plus `into`, `transduce`,
  `sequence`, and `eduction`. Use the official
  [Clojure release](https://clojure.org/news/2015/06/30/clojure-17) and
  [reference](https://clojure.org/reference/transducers) in the post.
  [Rust iterators](https://doc.rust-lang.org/std/iter/trait.Iterator.html)
  provide the important prior art for generic `map`/`filter` followed by
  `fold` or `collect`. Bend does not currently implement `sequence`.
- `X.into` with a List destination prepends; use an ordered Vec destination
  for a Bend example meant to match Clojure's `(into [] ...)` output order.
- The original public Array source used indexed `Array.get`. Its native read
  masks the index. The [flat-Array comparison](../../bench/PUBLIC-ARRAY-VS-C.md)
  measured 352 µs for Bend versus 178 µs for matched handwritten C at
  1,048,576 elements. A [generated-C probe](../../bench/probe_array_nomask.py)
  reached approximately 178 µs and Clang reported four-wide vectorization.
  Those are historical baseline and probe numbers. The integrated results
  are in the [Array.walk report](20260927-ARRAY-WALK-INTEGRATION.md).
- The [native 2K window](../../bench/BULLET-CATHEDRAL.md) reported 38–40
  presented FPS after startup on **one CPU thread**. The [eight-thread
  frame-batch result](../../bench/BULLET-PARALLEL-FRAMES.md) is separate
  512×512 computed-frame throughput. Label resolution, thread count, and
  whether display is timed beside every figure.
- “No intermediate stage collection” is narrower than “no allocations.”
  Framebuffers, retained events, List fragments, and some chunk stages
  allocate by design. A filter still needs a data-dependent selection. Inspect
  the generated code before claiming that particular wrappers, stop checks,
  bounds masks, or boxing have disappeared.

## Execution order and acceptance gates

### 1. Freeze the evidence baseline

Record the exact library commit, fork commit and upstream base, toolchain,
hardware, compiler flags, fixture hashes, and current test results. Make a
claim ledger with one row for each proposed numerical or semantic statement,
its source, its reproduction command, and its status: verified, historical,
proposed, or unsupported. Choose one public-API `map(inc) -> sum` fixture and
one flat-Array `map -> filter -> sum` fixture. Establish direct Bend, matched
C, and Rust comparators with the same input representation, `U32` wrapping
rules, seeds, equal results, and timing boundaries. Keep
input construction, traversal, disposal, and process startup consistently
identified rather than silently changing what “fast as C” measures.

**Gate:** every number considered for the introduction has raw samples,
matching outputs, and a workload description. If a comparison uses different
data layouts, show the layout difference explicitly.

### 2. Implement `Array.walk` in the fork and library

Add a generic, safe `Array.walk` operation to Bend Base and its compiler
lowering. For element type `A: Data`, it owns an `Array<A>`, maintains the
next index and remaining count internally, inspects the opaque state before
each read, steps once per visited element, and returns that same state.
Preserve the existing `Array.get` wraparound contract for arbitrary indexes.
In native lowering, remove the index mask only for this bounded walk while
retaining the usual
block lookup, element-layout read, keep/disposal behavior, and observable
order. A general Array operation, rather than recognition of a transducer
name, keeps this optimization useful to other Bend code.

Change the public `Array.source` and `Array.adapter` in
[`transduce_core.bend`](../../transduce_core.bend) to use the walk without
changing `X.transduce` or `X.into` calls. Keep the structurally consuming
`Array.affine_source`/adapter for affine elements, which cannot be copied out
with `Array.get`.

The safety argument to check is `i + remaining = size`, with `i = 0` at
entry. A read occurs only while `remaining > 0`; therefore `i < size`. This
argument must be checked against the actual native block-size limits, index
width, one-element Arrays, an initially halted traversal, and every compiler
lowering. Inspect must precede the read, including when the initial state is
halted. After each step it must run once before another read; completion
remains the `transduce` boundary's job. A shared `Array.fork` handle may be
changed by a callback, so the lowering must not hoist a stale block location across
steps.

Differential tests compare the new walk with the ordinary Bend traversal on
JS and native: size one and larger powers of two; numeric, boxed, and
multiword `Data`; shared handles; initial, first-item, middle, final, and
never-stopping states; and callback/inspection counts. Check CPU and GPU
code generation and results, using CI or other hardware for unavailable GPU
backends. Add negative or type tests for affine misuse and for any proposed
operation that would expose an unchecked arbitrary index.
Run the fork's compiler gate and the library's JS/native suite.

**Gate:** the fork and library both contain the implementation; supported
backends tested in this milestone preserve the source contract, with any
unavailable runtime explicitly listed; no generated-C string substitution is
needed; and emitted native code shows the bounded unmasked read. Re-run the
flat-Array benchmark with randomized paired samples and Clang vectorization
remarks. If either semantics or speed differs from the probe, investigate the
real code path before changing the article's result.

### 3. Explain the compiler changes through ablations

Trace a checked Bend example through source, specialization, emitted C, and,
where useful, assembly. Cover bounded static callback specialization,
template-argument inference, owner-companion conversion, and generic
uninhabited-match-arm elimination. Show the `?AUTO`/companion rule using an
actual public call and compiler excerpt, including the cases it refuses.
Explain that `Empty` as a stop permit makes the Stop constructor unreachable
in a total pipeline; `take` and other stopping stages retain their stop path.

For each mechanism, include its problem, transformation, correctness
boundary, and measured effect **only where an isolating comparison exists**.
Keep the separate FoldRegion experiment and the historical APIs distinct
from the shipped public path. Recheck no-stop performance on at least Array
and an independent source; the roughly 10% historical cost is not a universal
speedup, and native code layout can move a single program's timing.

**Gate:** generated-code claims match the exact tested binary. A timing
section must not attribute a difference to a compiler pass without an
ablation that isolates it.

### 4. Build proofs with explicit trust boundaries

First check which statements about the present `xf.bend` API can be expressed
and checked in Bend's proof language; use a faithful Lean model where that
cannot be done without changing the library's meaning. Start with reducer
lifecycle, source encounter order, map composition, stop propagation through
`cat`, and the no-stop property of `Control<Empty, S>`. Reuse and, if needed,
adapt the existing
[inductive List-drive agreement proof](../../experiments/affine_xf/no_stop_list_law_probe.bend).
For `Array.walk`, prove or mechanically check the bounded-index invariant and
the agreement between checked and total traversal for the supported element
and stop model. A type that cannot construct `Stop` does not itself prove
that an arbitrary source visits all its elements.

For Bullet Cathedral, specify proof targets before implementation: the
nine-cell broad phase covers every geometrically possible drone collision
under the scene's size and motion bounds; pixel and drone indexes are valid;
frame updates are deterministic; and stage completion/stop does not lose
events. Preserve the independent exhaustive collision oracle and per-frame
checksum comparison as tests. Report every property as a machine-checked
proof, mathematical argument, bounded check, or unproved assumption. A
source-level proof does not prove the C emitter, Clang, or runtime correct.

**Gate:** the post contains no generic “the showcase is proven” sentence
unless the stated end-to-end theorem and its trusted components exist.
Publish the proof artifacts and exact statements that do check.

### 5. Implement and compare C and Rust showcases

Port the simulation and CPU renderer with the same world evolution, sprite
rules, collision policy, color packing, and frame dimensions. Match every
frame's checksum and gameplay counters against Bend and the independent
oracle before measuring. Keep idiomatic Rust iterators where they express
the same stage pipeline; include a direct Rust loop where it helps identify
iterator overhead. Separate pure simulation/render computation, headless
frame throughput, and actual window presentation. Record one-thread and
explicitly parallel variants separately.

Count complete handwritten scene files with one documented rule, including
each file's own CLI harness so the boundary is objective. Exclude generated
Bend C and report reusable library code separately. Provide both lexical
code-token counts and raw source tokens under a named BPE tokenizer, without
presenting either as an exact model bill. Show proof code separately. State
precisely that these C and Rust implementations have no accompanying
machine-checked proofs; neither language is inherently unprovable. Report timing, allocation, and
memory observations beside correctness and code size, with source hashes and
compiler flags.

**Gate:** cross-language performance and code-size tables use equivalent
outputs and declared boundaries. The 2K live number is never compared with
512×512 batch throughput as though they measured the same thing.

### 6. Check unrelated Bend regressions

Build the fork at the pinned upstream base and at the final implementation.
Run the sibling `../bend/bench/` runtime and checker suites under equivalent
local conditions, then the available compiler correctness gate. Record
sequential CPU, parallel CPU, and GPU results where supported, as well as
compile time and memory. The upstream performance gate uses a mini cluster;
its pins and one-run threshold cannot by themselves establish a paired
before/after result on this Mac. Use repeated paired runs and preserve the
raw observations. Compare any host-dependent graphics failures with the
unchanged upstream baseline.

**Gate:** report the full suite, including regressions, noise, missing
hardware modes, and unexplained differences. Do not infer “no effect on
existing Bend programs” from passing transducer tests alone.

### 7. Write, render, and review the article

Suggested narrative: result and Rust precedent; why decoupled transducers;
Clojure/Bend contract differences; the small example; source/reducer
protocol; specialization and companions; no-stop elimination; `Array.walk`
and the SIMD inspection; proofs and limits; Bullet Cathedral; C/Rust/Bend
results; conclusion. Use the smallest representation that explains each
point: Bend source for API, a few generated C lines for allocation and
branches, assembly/vectorization output for SIMD, and diagrams only where
control or ownership would otherwise be hard to follow. Put a Clojure
equivalent in a comment beside every Bend example. Include the 2K video and
a still with measured presentation conditions, and put reproduction details
in an appendix.

**Gate:** every code excerpt comes from a committed, checked fixture; every
number is linked to raw data; and every claim is scoped to the tested
backend, workload, and revision.

## Confidence review

The first pass found conceptual errors in the draft: Clojure's release
version; `.reduce` and iterator terminology for the current Bend source;
mixing one-thread 2K presentation with eight-thread 512×512 batch throughput;
and treating the unmasked-read probe as an implemented optimization. The
starting-facts section and gates above correct them.

The second pass challenged the revised implementation and comparison plan:

| Possible loophole | Resolution required before the claim ships |
| --- | --- |
| An unmasked read is safe only in the one generated-C fixture. | Put the bounds invariant in the generic operation; test all supported layouts, stop positions, and backends; retain ordinary `Array.get` semantics. |
| A callback changes shared Array storage or owns a nontrivial element. | Preserve per-read block lookup and existing keep/disposal logic; test shared handles, boxed/multiword `Data`, and affine rejection. |
| A faster single binary is due to code placement or noisy microtiming. | Pair and shuffle repeated measurements; inspect emitted code; measure more than one size and one pipeline. |
| SIMD is reported because a probe was vectorized. | Inspect vectorization remarks and assembly from the final, unmodified fork output. |
| SIMD for `map -> filter -> sum` is assumed to apply to `map(inc) -> sum`. | Compile and inspect each exact fixture independently; report only the paths that vectorize. |
| “Zero allocation” ignores the frame buffer or retained events. | Count allocations within named intervals and describe which stage collections are absent. |
| Formal proofs are conflated with exhaustive tests or a checked type. | Publish exact theorems, assumptions, and trust boundary; retain tests and oracle under their own labels. |
| C/Rust ports change the algorithm or measure presentation differently. | Match per-frame outputs and counters, document layouts and timing boundaries, and compare like modes. |
| The fork improves the demo but slows unrelated Bend programs. | Run the sibling compiler and benchmark suites against a pinned upstream base with paired measurements. |

After those fixes, the **strategy has a falsifiable gate for each material
claim**. It cannot honestly promise 100% confidence today that `Array.walk`
will reproduce the probe, that the showcase ports will match its speed, or
that every desired proof will check. Those are outcomes to establish during
execution. If a gate fails, repair the underlying design or narrow the post's
claim to what the evidence establishes; do not patch a generated-C fixture
or relabel a bounded test as a proof.
