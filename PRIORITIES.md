# Implementation priorities

Current implementation: priorities #1–#3 are implemented experimentally; see [implementation status and validation](IMPLEMENTATION.md). The original ranking and scope decision below are historical; later user authorization included compiler specialization.

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

It excludes public buffered transformations, batching, parallelism, IO, runtime pipeline construction, compiler changes, and promises of allocation-free execution. Streaming `cat`/`mapcat` and ordered array traversal are now included. Bounded speculative pure work remains an allowed future strategy; exact sequential stopping must not accidentally become a universal restriction on all drivers.

The most valuable first deliverable is evidence that the abstraction is both usable and efficient. Feature breadth follows that evidence.
