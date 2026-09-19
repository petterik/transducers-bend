# Confidence review

## Range-overhead follow-up

The confidence pass challenged treating the cheap-range gap as a general protocol cost. Native inspection found scalarized state, not per-element wrapper allocation in this measured loop. A more selective filter measured 36 ms library versus 36.5 ms handwritten, while the original workload still exposes overhead. Two semantics-preserving take-control experiments passed the full library suite but were reverted because they regressed or failed to improve performance. The library and compiler are unchanged. See [the experiment report and retained samples](bench/CONTROL.md).

This review therefore changed the strategy: retain the representation and broaden workload evidence before attempting further optimization. It does not establish 100% confidence or a formal proof.

Current implementation: priorities #1–#3 are implemented experimentally; see [implementation status and validation](IMPLEMENTATION.md). The original review below is historical; its open items and compiler-scope restriction are superseded by later authorized work.

## Priority #3 confidence follow-up

The pre-implementation review narrowed range semantics to the existing ascending, half-open U32 design with step 1. Reversed bounds are checked before subtraction. A decreasing numeric Nat budget avoids eager source construction; computing `end - remaining` only while Continue prevents value generation after Stop and avoids endpoint wrap. The maximum U32 cannot be emitted with this exclusive-bound API; this is documented rather than hidden behind a widened bound type.

Consumers use Unit configuration: ordered `into_list` supports affine elements and reverses once; `count` returns Nat and follows the compiler's checked limit. This avoids a second pipeline interface and silent U32 count wrapping. Tests cover both sources, affine ownership, stopping, boundary behavior, and existing completion fixtures. [LAWS.md](LAWS.md) records the intended laws, no-wrap argument, 18,750 bounded assertions per backend, and limits of the evidence.

The final source API is an open static reduction interface: third-party modules supply an ordered stopping fold and a small binding adapter using `reducible`. `transduce(~reduction, config, source)` derives types from that binding and callers supply their pipeline once. The built-in list/range/string implementations and the external tree pass reusable conformance tests, affine ownership checks, and exact lifecycle instrumentation. There is no source enum, registry, automatic trait resolution, or runtime reusable callback.

Prototypes established that ordinary runtime callback reuse is rejected by affinity. Static reduction works, but repeated eager evaluation at binding boundaries exceeded the compiler's bounded evaluator for larger pipelines. Delaying the closed recipe and type metadata fixed the representative codegen checks without modifying the compiler. Callback shape still matters: forwarding lambdas around pattern-matching functions specialize where bare matcher heads can remain runtime calls. This limitation is documented rather than treated as universal optimization.

Remaining uncertainty is explicit: no mechanized library proof, allocation profiling, new range GPU validation, or full compiler gates. The benchmark compares equivalent generated sources and includes an independent output oracle; it does not imply universal performance parity. Passing tests and bounded specialization do not justify 100% confidence in arbitrary pipelines.

Performed before drafting DESIGN.md, against the current Bend checkout and installed CLI (both reporting 2.0.16). This is an adversarial design review, not a claim of exhaustive proof or 100% certainty.

## Findings and resolutions

| Potential failure | Resolution in the design | Evidence/status |
| --- | --- | --- |
| Reusable reducer closures violate affinity | Specialize code with templates; pass owned state explicitly | Stateless composition and a stateful pipeline compiled and ran |
| Template callbacks capture runtime locals | Supply runtime configuration in state or explicit callback arguments | Runtime filter threshold and take count exercised |
| `take(0)` still maps or produces an input | Initialization returns control before source traversal | Prototype covers zero; range production not yet implemented |
| Taking counts source inputs instead of filtered outputs | Each stage counts only values reaching it | Runtime filter followed by take produced the expected sum |
| Stopping loses accumulator/state | Both control alternatives retain owned state | Generic affine control state compiled |
| Buffered output is lost after an upstream take | Retain downstream-open status separately from a wrapper's own stopping condition | Protocol analysis; full buffering probe required |
| Completion emits after downstream stop | Suppress further steps to that downstream reducer and still complete it once | Protocol analysis; full lifecycle probe required |
| Filtering duplicates an affine element | Restrict conventional predicate filtering to Data inputs | Matches the ownership requirement of current Base filtering |
| An arbitrary iterator cannot prove termination | Start with structural list traversal and bounded finite range production | List recursion compiled; range driver remains to be tested |
| Early termination is advertised as O(k) on any input | Account for preconstruction and owned-tail cleanup | Native runtime's term_drop walks owned descendants |
| A supposedly generic source becomes an intermediate list | Use source-specific traversals over the same reducer protocol | Design requirement; second driver is an acceptance gate |
| Collecting by repeated append becomes quadratic | Prepend and reverse once | Planned consumer; not yet benchmarked |
| Sequential fusion destroys parallel speedup | Keep parallel execution as a separately validated strategy | Current Array.map contains explicit parallel branches |
| Chunking resets state or changes ordering | Preserve global state semantics; require valid combining operations | Deferred parallel design, explicitly constrained |
| “No intermediates” is mistaken for “no allocations” | Inspect control/state code generation and measure | Allocation behavior remains unmeasured |
| Compilation is presented as proof of a safe library | Report CLI template diagnostics and distinguish tests from proofs | CLI counts defs with `~` in their names as unsafe annotations |

## Experiments

Temporary probes were created outside both repositories under `/tmp/bend-transducers.ERDHiK`. They are exploratory evidence, not permanent tests or an implemented library. Their sources are not part of this design-only change.

The first probe compared materialized `map(+1)` followed by `take` with a handwritten fused traversal over `[1, 2, 3, 4]`. Instrumented emitted JS counted mapper calls:

| Take count | Existing composition | Fused traversal |
| --- | ---: | ---: |
| 0 | 4 | 0 |
| 2 | 4 | 2 |
| 8 | 4 | 4 |

Returned lists agreed. A native executable also returned the expected combined checksum. This establishes the optimization opportunity for this example, not a general performance result.

A second probe composed two template-based mapping reducer adapters with a fold. Mapping +1 then *2 over `[1, 2, 3]` and summing returned `18` on JS and native builds. Emitted JS contains a single list traversal with no intermediate mapped lists, but retains specialized helper calls.

The confidence-pass probe uses generic `Control<S>`, an affine state wrapper for configured filtering, a taking reducer, a mapping adapter, and a structurally recursive list driver. It exercises map(+1), filter(> threshold), take(count), sum:

| Input | Threshold | Count | Result |
| --- | ---: | ---: | ---: |
| [1, 2, 3, 4, 5] | 2 | 2 | 7 |
| [1, 2, 3] | 2 | 0 | 0 |
| [] | 2 | 2 | 0 |
| [1, 2, 3] | 99 | 2 | 0 |
| [1, 2, 3] | 2 | 9 | 7 |

Both backends returned `[7, 0, 0, 0, 7]`. The probe initially had an incorrect handwritten expected comment of 4 for the final case; manual arithmetic confirmed 3 + 4 = 7 and the comment was corrected. No code was changed to accommodate that mistake.

Builds used the checkout's `bun bend2/main.ts <probe> -o <probe>.js -o <probe>`, with telemetry disabled, followed by Node and native `--threads 1` execution. The stateful probe reported “All terms check, with 5 unsafe annotations.” Its source contains no explicit `@unsafe`; `bend2/main.ts`'s cli_report also counts template-specialized definitions. This is not evidence of a fully verified safe implementation.

## Remaining confidence limits

There is enough evidence to draft the proposed library architecture. There is not enough evidence to freeze its public API, claim fully validated completion semantics, promise allocation-free execution, or claim performance parity with direct loops.

The next confidence loop is the implementation acceptance sequence in DESIGN.md. A failure should revise the representation or scope, not introduce compiler changes or unsafe bypasses merely to preserve this draft.

## Source references

In the sibling Bend checkout:

- `guide/GUIDE.md`, Closures, Recursion and Termination, Templates, and Parallelism.
- `bend2/base.bend`, List.map, List.filter, List.foldl, List.take, and Array.map.
- `bend2/comp.ts`, emit_args and term_drop.
- `bend2/main.ts`, cli_report.
- `bend2/docs/BendRT/main.typ`, compilation, ownership, and interaction-net comparison.

Clojure's [transducer reference](https://clojure.org/reference/transducers) supplies the comparison for reducer transformations, early termination, and completion. This design deliberately uses explicit owned state rather than directly translating Clojure's stateful closures.
