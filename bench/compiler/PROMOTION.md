# Promotion review: outlining profitability remains unresolved

**Implementation follow-up:** [automatic bounded loop specialization](AUTO-LOOP.md)
now implements caller discovery, the local proof and scoped cloning. This document
records the earlier investigation; dynamic short-loop profitability remains open.


**Follow-up:** [confidence review and priorities](STRATEGY.md) tests loop-entry
versioning and loop bailout, including local induction checks and counterexamples.
It narrows the next implementation target without claiming production readiness.

The automatic scalar transformation from commit `a8d62f5` passed broader local
correctness and compatibility checks. **Do not default-enable this compiler pass
on that evidence alone:** new measurements demonstrate a cost when valid zero or
stopped states frequently take the outlined fallback. No production compiler or
library changes were made during this review.

## Adversarial transition checks

`adversarial.py` builds 16 variants of the reordered scalar fixture with both the
original and experimental compiler. Changes include configuration updates only
on fallback or rejected paths, fallback sum/count changes, a changed inner tag,
repeated uses of a sum binding, extra wrapping additions, a constant sum, reversed
outer tags and a count that does not decrement.

Twelve variants specialize; four conservatively remain unchanged. All 16 pass
200,000 complete-state comparisons each under UBSan: **3.2 million comparisons**.
Inputs cover both decisions, both inner tags, zero/one/two/three/max Nat, wrapping
boundaries and seeded random values, including configuration values. The reference
helper comes from the **original compiler's emitted C**, not a handwritten oracle.
The runner verifies that the rest of the generated program is textually identical
before inserting the reference helper, so it cannot silently share other changed
helpers. It compares every returned field and the success return.

[Raw adversarial results](adversarial-results.json) retain the generated Bend, C and
harness artifacts. These are concrete counterexample searches, not a compiler proof.

## Local upstream compatibility

`upstream_local.py` checks positive Base-importing tests with a main definition in
`base`, `compile`, `flatten`, `reg`, and `state`:

- **216 native CPU and JS tests pass**, with output checked against their `#|`
  expectations. Their generated C is textually identical between the original and
  experimental compiler. None of these upstream programs activates the new rule;
  they test conservative refusal and compatibility, not optimized-path coverage.
- **50 interpreter-only tests pass.** Their function-valued or otherwise unprintable
  main types are refused identically by both native compilers, as expected. The
  official gate also excludes their native/JS lanes.
- One of the 216, `flatten/literal_rows_cubic.bend`, exceeds local Clang's default
  bracket nesting limit with **identical original and experimental C**. Its local
  execution check uses `-fbracket-depth=4096`. This is a disclosed local gate
  adjustment, not a fixed upstream compiler build or an ordinary CLI build pass.

[Raw local results](upstream-local-results.json) include per-test outcomes and that
extra flag. The official `gates/test.ts` uses a distributed mini cluster; this
local run does not replace that gate, negative checking tests, Metal or CUDA tests.
The production compiler's `bend.ts` was not edited.

## Fallback-frequency measurements

`fallback.py` calls the same automatically discovered scalar helper ten million
times per timed batch, independently supplying valid states at controlled zero or
stopped frequencies. Decisions are mixed, scalar results feed the next iteration,
and all output fields contribute to a checksum. Original/automatic checksums match.
Runs are sequential CPU, with discarded warmups and forward/reverse order.

This is a **helper-level stress test**, not a claim that ordinary take/sum drivers
encounter these frequencies. Those drivers ordinarily stop before repeatedly
feeding stopped or zero-count states. The generic compiler rule also sees programs
that directly supply such states; their semantics are valid and the current rule
has no caller-level profitability evidence that excludes them.

Ten-sample medians in milliseconds, [raw frequency sweep](fallback-results.json):

| Exceptional state | Frequency | Original | Automatic outlined |
| --- | ---: | ---: | ---: |
| Zero count | 0% | 10.884 | 9.895 |
| Zero count | 25% | 10.594 | 15.742 |
| Zero count | 50% | 10.351 | 24.146 |
| Zero count | 100% | 10.610 | 34.622 |
| Stopped inner | 0% | 12.549 | 8.736 |
| Stopped inner | 25% | 12.554 | 16.423 |
| Stopped inner | 50% | 12.572 | 26.780 |
| Stopped inner | 100% | 12.559 | 36.739 |

A second [linkage ablation](fallback-linkage-results.json), six retained samples
per variant, changes only the generated fallback declaration. Removing `cold`
while retaining `noinline` does not remove the regression: the 100% cases remain
around 33 ms. Allowing the fallback to inline reduces these cases to roughly
8.6 ms. Thus the extra call/optimization boundary is the main demonstrated cost;
changing the branch-likelihood/placement annotation alone is insufficient.

The same declaration-only ablation is checked against the full range benchmark
in [linkage-range-results.json](linkage-range-results.json). It retains the
original-helper differential harness, UBSan and independent batch oracle. This
is a generated-C diagnostic, **not an implemented automatic policy change**.

Ten-sample medians for full ranges:

| Workload | Original | Outlined | No cold attribute | Inline fallback | Handwritten |
| --- | ---: | ---: | ---: | ---: | ---: |
| Mixed | 320 | 95 | 93.5 | 102 | 93 |
| Predictable | 48 | 36 | 36 | 50 | 34 |

Inlining fixes the helper stress test but loses the predictable-range win.
The tiny difference between the two outlined mixed results is not enough to
recommend one attribute declaration over the other.

## Decision and next implementation target

Keep the successful automatic transition isolated. Neither blindly applying the
cold outline nor simply removing it meets all measured goals. Do not encode a
claim that zero/stopped states are unreachable from their record shape, or use
transducer/helper names to choose which calls get the optimized implementation.

The next useful investigation is a bounded caller-level profitability decision:
determine whether existing typed call/loop information can justify retaining the
outlined version for suitable callers while preserving normal optimization of
fallback-heavy callers. An alternative lowering must demonstrate both the range
speedup and absence of this stress-test regression. That is still unimplemented;
this review does not claim the performance problem is solved in production.

## Reproduction

```sh
python3 bench/compiler/prepare_guarded.py
# Substitute the printed compiler path below.
python3 bench/compiler/adversarial.py --bend-main /tmp/candidate/main.ts --output /tmp/adversarial.json
python3 bench/compiler/upstream_local.py --bend-main /tmp/candidate/main.ts --output /tmp/upstream.json
# Run the following sequentially, after all tests/compiles finish.
python3 bench/compiler/fallback.py --bend-main /tmp/candidate/main.ts --samples 5 --output /tmp/fallback.json
python3 bench/compiler/fallback.py --bend-main /tmp/candidate/main.ts --linkage-ablation --samples 3 --output /tmp/linkage.json
python3 bench/compiler/ablate.py --automatic-compiler /tmp/candidate/main.ts --linkage-ablation --samples 5 --output /tmp/range-linkage.json
```
