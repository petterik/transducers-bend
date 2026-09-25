---
created_at: 2026-09-19T11:25:47+02:00
updated_at: 2026-09-25T09:17:39+02:00
status: current
---

# Implementation priorities

## Current ranking — design review, 2026-09-20

This ranking supersedes the historical build orders below and the earlier
benchmark-driven execution order. The [adversarial review](DESIGN-REVIEW.md)
explains the findings; [the work plan](DESIGN-WORK-PLAN.md) specifies tasks,
dependencies, acceptance criteria, and implementation boundaries. These are
planned tasks, not completed compiler changes.

Impact measures correctness, extension independence, and progress toward direct
Bend performance. Effort measures semantic complexity, proof obligations, API
commitments, and maintenance—not lines of code, typing time, or familiarity with
the library. Value includes how much uncertainty a task removes before further
investment. Ratings are qualitative; critical correctness work takes precedence
over a numerical impact/effort ratio.

| Order | Work | Impact | Effort | Value | Decision |
| --- | --- | --- | --- | --- | --- |
| 0 | Make the Array counterexample a permanent gate; stop applying unproved tree rewrites | Critical: removes known wrong-code behavior | Low–medium for conservative refusal; high for a complete tree proof | Highest, mandatory | First; retain the lost performance as an open item |
| 1 | Specify extension contracts and exercise keep, partition-all, and a custom source | High: tests whether the architecture serves new operations | Medium: ownership, buffering, completion, configuration | Very high: challenges the design before compiler investment | Implemented as a public semantic probe; extend with more operations later |
| 2 | Make static callback composition systematic with existing templates | High: benefits every pipeline and other Bend abstractions | Medium–high: strictness, type metadata, sharing, specialization budgets | Very high: removes compiler-driven library workarounds | Probe complete; keep delayed recipe until a general replacement passes built-ins and extensions |
| 3 | Establish typed regions and explicit, scoped optimization facts | Critical: prevents the class of error found in the review | High: binding identity, preconditions, joins, recursion, failure semantics | Very high: foundation for sound extension | Map/filter `Emit | Skip` lowering passes semantic/codegen gates and removes timed List nodes; one generated branch closure per source item remains, so test generic applied-match lowering next |
| 4 | Eliminate local wrapper and state-transfer overhead | High: generalizes fusion beyond the current scalar pattern | Medium–high: escape, ownership, layouts, unknown calls | High: broad benefit without a transducer vocabulary | The paired map/filter benchmark isolates a checked `App(Mat, value)` closure as the remaining FoldRegion cost; prototype a general rule with fallback and ownership tests |
| 5 | Recover profitable loop/tree optimization using proved facts | High: restores and broadens direct-Bend parity | High: induction, tree state flow, continuation entries, backend costs | High after 0–4; poor value as more ad hoc recognition now | List-loop gate passes; tree proof and short-loop profitability remain open |
| 6 | Simplify public composition and configuration | High usability; little demonstrated direct speed impact | Medium: type packaging and public API commitments | High after the representation works | Prototype during 1–2; stabilize after 4 |
| 7 | Complete performance/backend gates and prepare upstreamable changes | Critical before promotion | Medium–high: evidence, infrastructure, integration | Mandatory at release boundary | Candidate/reference report complete; GPU and full upstream gates remain blockers |
| Later | More operations: remove, drop, indexing, partition-by, dedupe, distinct | Medium–high feature breadth | Low–high depending on retained state and ownership | Higher after extension independence is demonstrated | Add as library work; remove may serve as a small control case now |
| Later | IO/file/channel execution contracts | High long-term reach | High: effects, cleanup, cancellation, suspension | Lower now; independent design effort later | Preserve room; do not force into the pure fold signature |
| Later | Parallel reduction contracts | High potential on Bend | Very high: combination laws and global stage state | Uncertain until the sequential foundation is sound | Separate proposal and evidence |
| Conditional | New language-level staging/module features | Potentially high across Bend | Very high: language/checker/API commitment | Unknown until existing-template limits are demonstrated | Require a reduced failing design probe first |
| Conditional | Mechanized proofs | High assurance for stable rules | High: model fidelity and proof maintenance | Best for stable, narrowly specified rewrites | State obligations now; formalize after their shape settles |
| Reject | Closed compiler vocabulary of transducers; more benchmark-shaped recognizers as the architecture | Narrow short-term wins | High lasting coupling and extension cost | Low | Keep operations as ordinary library code |

The first milestone is **a correct, extensible composition foundation**: the
counterexample passes, new operations compose through the same lifecycle, and
static descriptions specialize without user-managed representation tricks.
The next milestone removes residual local overhead. Direct-Bend parity and
upstream readiness remain explicit later gates, not assumptions.

## Historical priorities

Current implementation: priorities #1–#3 are implemented experimentally; see [implementation status and validation](../foundation/IMPLEMENTATION.md). The original ranking and scope decision below are historical; later user authorization included compiler specialization.

## Priority #3 follow-up ranking

Effort here means semantic complexity, API commitments, and maintenance, not lines of code or familiarity with Bend.

| Work | Impact | Effort | Value | Status |
| --- | --- | --- | --- | --- |
| Fix range/consumer contracts | High | Low | Very high | Implemented and documented |
| Range with boundary, stopping, and codegen checks | High | Medium | Very high | Implemented; JS/native validated |
| Ordered affine into_list | High | Low–medium | High | Implemented |
| Open static source reduction and external extension example | High | Medium | Very high | List/range/string and third-party tree validated |
| Reusable source conformance and exact lifecycle checks | High | Medium | Very high | All four sources validated |
| Nat count consumer | Medium | Low | High | Implemented |
| Cross-source lifecycle checks and reusable examples | High | Medium | Very high | Implemented |
| Explicit laws, bounded checks, no-wrap argument | High | Medium | High | Added; not formal proofs |
| Focused generated-range benchmark | High | Medium | High | Measured; see bench/RANGE.md |
| Full compiler project gates | High | Infrastructure-dependent | High | Still outstanding |
| Mechanized driver/composition proofs | High | High; formalization fit unknown | Higher after API settles | Follow-up investigation |
| Configurable range steps, parallel drivers, public buffering/mapcat | Potentially high | High | Lower now | Deferred |

This pass ranks the proposed design by impact, lasting effort, and value before initial implementation. It does not expand the scope in DESIGN.md.

Impact means contribution to efficient composition, correctness, or a usable API. Effort means conceptual complexity, ownership reasoning, API commitments, and ongoing maintenance—not lines of code or familiarity with Bend. Value balances impact and effort, including how much uncertainty an item removes. Ratings are qualitative judgments rather than benchmark results.

## Ranking

| Work | Impact | Effort | Value | When |
| --- | --- | --- | --- | --- | --- |
| Generic owned state and a practical template composition pattern | Critical: establishes whether this can be a usable library | High: types, configuration, and lifecycle must compose without reusable closures | Highest: resolves the central architectural risk | First |
| Initialization, stop propagation, and completion protocol | Critical: prevents wrong results and future API redesign | High: local stopping and downstream stopping differ | Highest: expensive to retrofit | First, with a minimal completion-emitting test wrapper |
| Sequential list `transduce` with identity and a sum consumer | High: establishes end-to-end execution | Low–medium: structural traversal and ownership handling | Highest: smallest executable foundation | First |
| `map`, configured `filter`, and runtime-count `take` | Critical: delivers the motivating use case | Medium: configuration, type changes, and state composition | Highest: validates both utility and representation | First complete pipeline |
| Correctness cases and ownership checks | Critical: catches errors a successful example misses | Medium: lifecycle and affine use require deliberate cases | Highest: protects the protocol before it becomes an API | Alongside the core |
| Generated-code inspection and a small native performance comparison | High: discovers abstraction costs before API investment | Medium: fair baselines and allocation evidence need care | Highest: performance is the reason for the library | As soon as the first pipeline runs |
| Finite range source using the same pipeline | High: demonstrates source independence and avoids unused production | Medium: termination and numeric boundaries | High: tests a benefit prebuilt lists cannot demonstrate | Before initial implementation is considered complete |
| Ordered `into_list` | High: makes transformed outputs directly useful | Low–medium: affine collection construction and final reversal | High: broad utility with modest new semantics | In the initial implementation |
| Count consumer and concise usage examples | Medium: makes the protocol easier to learn and exercise | Low: reuses the established protocol | High once the API works | Finish the initial implementation |
| Formal equivalence laws | High: strengthens semantic confidence | Medium–high: useful statements and template trust boundary need investigation | High after representation stabilizes | State laws early; prove tractable laws after the core gates |
| Broader performance suite | High: tests whether gains generalize | Medium–high: workload selection and reliable measurement | Medium initially; high before performance claims | After the small benchmark exposes basic costs |
| Buffered transformations such as partitioning | Medium: expands supported workflows | High: flushing, ownership, and nested stopping | Medium later | Defer public feature; validate its lifecycle requirements now |
| Flattening / `mapcat` | Medium: enables one-to-many transformations | Medium: nested traversal and immediate stop propagation | High now | Implemented as `cat`/`mapcat`; array map-reduce benchmark added |
| Batched and parallel drivers | Potentially high: fits Bend's strengths | Very high: ordering, global state, partitioning, and valid combination | Uncertain until measured | Defer implementation; preserve compatible semantics |
| IO sources and effectful consumers | Medium: expands integration | High: cleanup, handles, effects, and cancellation | Low for the initial pure-data goal | Defer |
| Runtime-selected pipeline structures or universal iterator abstraction | Uncertain for current use cases | Very high: closure restrictions, termination, and dispatch overhead | Low now | Defer until a concrete use case justifies them |
| Compiler fusion or changes to function types | Potentially high across Bend | Very high: compiler maintenance or foundational type-system changes | Low as a prerequisite to this library | Out of initial scope |

## Build order

### 1. Validate the representation

Implement the smallest generic reducer protocol and sequential list driver. Exercise identity and mapping that changes element types, an affine accumulator, and configuration supplied at runtime. Write the composition example a library user would actually write—not only manually specialized U32 helpers.

In the same phase, use a small completion-emitting wrapper to test upstream stopping versus downstream stopping, initial stop, stopping during a flush, and completion exactly once. This is a protocol test, not a commitment to ship partitioning.

Exit condition: these operations compose through one coherent protocol with no explicit `@unsafe` bypass. If normal composition requires users to manually maintain several inconsistent copies of pipeline structure, reconsider the representation before freezing the API.

### 2. Deliver the motivating pipeline and inspect its cost

Implement `map -> filter(runtime threshold) -> take(runtime count) -> sum`, including reordering stages and repeating runs with fresh state. Cover empty inputs, zero and oversized take, consumer-initiated stop, and independent state for consecutive take stages.

Inspect generated C and JS. Compare native execution with materialized composition and a handwritten fused traversal. Start with cheap mapping, where adapter overhead is visible, and early termination with expensive mapping, where avoided work matters. Keep source construction and ownership equivalent when comparing implementations.

Exit condition: correct results, no intermediate stage collections, and enough code-generation/performance evidence to decide whether the representation is worth retaining. Do not invent a speedup threshold before obtaining baseline measurements. Explain observed wrapper allocations or overhead rather than hiding them behind expensive callbacks.

### 3. Complete the initial library

Add finite range execution, ordered `into_list`, a count consumer, and concise examples. Run the same transformation over both sources and with scalar and collection consumers. Verify that the range driver does not produce values after initial or mid-run stop, and that bounds do not wrap.

Exit condition: the documented initial scope works on JS and native backends, lifecycle/ownership checks pass, and remaining limitations are explicit. Expand semantic laws and benchmarks around this stable implementation.

## Scope decision

The initial implementation includes the reducer lifecycle, practical static composition, identity/map/filter/take, sequential list and finite range drivers, transduce, into_list, sum/count consumers, focused validation, and a small performance comparison.

It now includes the first public buffered transformation, `partition_all`, as a semantic probe. It still excludes general buffering, batching, parallelism, IO, runtime pipeline construction, compiler changes, and promises of allocation-free execution. Streaming `cat`/`mapcat` and ordered array traversal are included. Bounded speculative pure work remains an allowed future strategy; exact sequential stopping must not accidentally become a universal restriction on all drivers.

The most valuable first deliverable is evidence that the abstraction is both usable and efficient. Feature breadth follows that evidence.
