# Optimization decision: confidence and priorities

## Latest milestone: automatic isolated compiler experiment

The [subsequent promotion review](bench/compiler/PROMOTION.md) passes broader
correctness checks but finds a measured outlining tradeoff: frequent valid
zero/stopped states make the outlined helper slower, while inlining its fallback
loses the predictable-range speedup. Caller-level profitability remains unresolved;
keep the pass isolated rather than enabling it universally.

[The typed guarded-scalar pass](bench/compiler/AUTOMATIC.md) now discovers and
lowers the successful transition from the unchanged public pipeline. It analyzes
typed helper bodies with separate binding scopes, derives preserved fields and
branch-local Nat bounds, and retains the original helper as a cold fallback.
It uses no transducer/helper names or fixed field positions for recognition.
This is a bounded CPU experiment in an isolated compiler copy, not a production
optimization or a general profitability guarantee. The Source API, production
library, and sibling compiler remain unchanged. Details, raw measurements,
validation, reproduction, and remaining promotion gates are in that report.

## Latest evidence: controlled generated-C ablations

[The ablation study](bench/compiler/ABLATION.md) now demonstrates a near-handwritten
code shape on mixed and predictable full/early ranges. The winning combination is
guarded scalar updates, a stop tag derived from the updated count, an original-helper
cold fallback, and explicit preservation of unchanged fields across that fallback.
Unlike the previous emitted-C selection pass, this targets the actual hot transition.
It is still a program-specific experiment, not an automatic optimization. This is
the current implementation target; the older ranking and prototype results below
are retained as the investigation history.

The Source API is not the demonstrated performance problem; [historical comparisons](bench/API-REGRESSION.md) show identical old/new timed mixed-list assembly. The opportunity is to lower a known scalar transition into conditional updates without speculating arbitrary callbacks or assuming a relationship between generic Control and numeric fields.

## Candidate established by experiment

[scalar_prototype.bend](bench/scalar_prototype.bend) is a benchmark-only, manually specialized map/filter/take/sum reducer. It uses the existing state types, Source API, driver, initializer, and completion. Only the step is replaced. This is evidence for a compiler transformation, not a new recommended public combinator or an implemented compiler pass.

For continuing downstream sum state, let `keep` be the evaluated predicate and `n` the take count:

- `accepted = 1` exactly when `keep && n > 0`, otherwise zero.
- `n' = n - accepted`, implemented using Nat.sub.
- `sum' = sum + accepted * x`, with the original U32 wrapping.
- Outer Stop exactly when `keep && n <= 1`; otherwise outer Continue.
- Preserve the downstream Continue tag independently of the outer tag.

For stopped downstream state, preserve its count and sum, keep its Stop tag, and choose the outer tag from `keep`. In particular, a rejected input does not normalize an arbitrary continuing-zero state to Stop. The map and predicate retain their evaluation order and run once per original step.

This transition is defined for zero counts and stopped inner states, not only reachable positive counts. Since `accepted <= n`, subtraction cannot underflow; multiplication and addition have defined U32 wrapping. These are source-level arguments, not mechanized compiler proofs.

The initial arithmetic-only prototype measured 106 ms mixed full-range versus 94.5 ms handwritten, compared with about 331 ms for the existing generic pipeline. Mixed early stopping measured 116 versus 103 ms. [Initial raw samples](bench/scalar-prototype-results.json) retain fourteen samples per case. However, [simple-predicate measurements](bench/scalar-default-results.json) exposed a regression: cheap full-range took 85 ms, versus the previous roughly 49 ms library baseline. Blanket predication is therefore not the recommendation.

The retained prototype first separates zero from positive counts, preserving the original computation in the zero branch. Within the positive branch it selects scalar updates without an acceptance branch. The map and predicate still execute in the original order and the zero-state behavior is preserved. [Refined simple-case samples](bench/scalar-guarded-default-results.json) measured 52 ms full / 26 ms early / 26 ms huge early / 11 ms expensive early; [refined mixed samples](bench/scalar-guarded-mixed-results.json) measured 112 ms full / 121 ms early versus 96 / 103 ms handwritten. Each refined case retains six samples. This trades some of the first prototype's mixed-case gain for much better simple-case behavior. Small regressions relative to the existing implementation remain possible and must be resolved or gated before default deployment. Historical snapshots describe their hashed source versions; `scalar_prototype.bend` contains the refined version.

A fresh [unchanged-library simple-workload baseline](bench/scalar-baseline-results.json), run sequentially after the refined prototype, measured the same medians: 52 / 26 / 26 / 11 ms. Thus no simple-case regression was observed in that comparison. This is a small CPU matrix, not a universal profitability guarantee or a replacement for the old list/parallel benchmarks.

```sh
python3 bench/range.py --source bench/scalar_prototype.bend --runtime-threshold --predicate mixed --threshold 2147483647 --cases cheap_full cheap_early
python3 tests/run.py
```

## Priority ranking

An initial [automatic compiler experiment](bench/compiler/README.md) now implements
a bounded selection rule for straight-line scalar Boolean arms. It fires in a
code-generation test and passes the 16-file suite, but does not improve the hot
generic filtering pipeline: helper calls and nested guarded arithmetic are still
outside its accepted region. Scoped helper-body exposure remains required; this
first pass is not the completed optimization and is not installed in the sibling fork.

The [composition and ordinary-list comparison](bench/COMPOSITION.md) sharpens the acceptance
criteria: pure map composition already matches handwritten code, with identical timed assembly
for three maps and one `+6` map. Preserve that result. Ordinary eager list pipelines are slower in
the tested workloads. The latest conditional-selection prototype reduces mixed-range overhead
to roughly 11–14%, but cheap ranges remain roughly 37–47% slower than handwritten. Recovering
most of the mixed-filter gap is therefore not sufficient to declare the performance task complete.
The current prototype uses `Bool.pick` for the next count/sum; older result files preserve the
hashes and measurements of the earlier arithmetic formulations.

Effort means semantic/implementation complexity, maintenance, proof obligations, and API consequences—not lines of code or coding speed.

| Option | Impact | Effort | Value / decision |
| --- | --- | --- | --- |
| Bounded scalar conditional-update lowering inside preserved guards | High: measured path to recovering most of the gap | Medium–high: expose an acyclic region, prove operations safe, and control profitability; no public API change | Highest: next implementation experiment |
| Differential correctness, arithmetic boundaries, negative speculation tests, workload matrix | High: prevents incorrect or overfit optimization | Medium | Required alongside the first option |
| Whole-program producer/loop invariant inference | Potentially broad | Very high: initialization, transitions, recursion, aliases, open call sites, failure semantics | Defer until narrow lowering proves insufficient |
| Public specialized map/filter/take/sum fast path | High for one pattern | Medium: permanent API and duplicated semantic maintenance | Keep only as benchmark oracle/prototype for now |
| New reducer readiness/continuing-state protocol | Potentially broad | High: API changes, custom reducers, completion/ownership contracts | Defer; current API need not change |
| Offset take-counter representation | No demonstrated speedup | Medium semantic maintenance despite small code change | Reject for now: prototype passed 13 tests but remained about 327 ms full / 140.5 ms early |
| Generic count guards or likelihood hints | No demonstrated speedup | Medium compiler/code-size risk | Reject based on measured experiments |
| Revert Source API | No demonstrated benefit | High ecosystem/API disruption | Reject: old/new controlled comparison disproves this explanation in tested cases |

## Confidence review and remaining gates

`tests/scalar_transition.bend` compares the entire returned state and both control tags against the original step for 144 combinations: counts 0/1/2/max Nat, three thresholds, zero/max U32 sums, three inputs, and continuing/stopped inner state. It includes states the ordinary pipeline would not reach. All 14 test files pass JS/native with the unmodified compiler and library. The mixed benchmark independently validates every checksum. None of this establishes 100% confidence in a future automatic compiler rewrite.

The compiler candidate must:

1. Materialize the original predicate and other already-required expressions once, in their original order.
2. Work only on a bounded, acyclic, scalar region after sufficient specialization/inlining has exposed its operations. Do not recognize library functions by their names.
3. Permit only operations whose totality and exact arithmetic semantics are established. Unresolved calls, affine/boxed values, effects, floating-point edge cases, and potentially failing arithmetic are initially out of scope. Keep their existing control flow.
4. Transform validated guarded scalar assignments into conditional updates, preserving all returned fields and tags for every valid input state. Preserve predictable guards; the blanket formulation regressed simple workloads. Do not infer Stop from a zero field.
5. Bound compile time/code growth and fall back unchanged when analysis is inconclusive. This requires actual region extraction/proof machinery; that machinery does not yet exist here.
6. Test negative cases where rejected branches would overflow or invoke callbacks, plus max counters, U32 wrap, zero/one take, downstream stopping, affine consumers, and completion emission. A rejected callback must remain uncalled, even if its result could be discarded.
7. Measure old uniform/list workloads, mixed/full/early ranges, no-match filters, and expensive callbacks. Preserve descriptions' elimination and check generated native code. A correctness win does not establish performance profitability.
8. Run compiler regression/typecheck gates and library tests before promotion; full project infrastructure gaps still need resolution. GPU/CUDA behavior is not validated by the CPU prototype.

The prototype proves a useful scalar formulation exists. It does not yet establish an automatic, profitable, semantics-preserving rewrite for arbitrary reducers. Production library/compiler code remains unchanged.
