# Confidence review and priorities: specialize the loop boundary

**Implementation follow-up:** [automatic bounded loop specialization](AUTO-LOOP.md)
now implements caller discovery, the local proof and scoped cloning. This document
records the earlier investigation; dynamic short-loop profitability remains open.


## Recommendation

Investigate **bounded loop-entry versioning with a local preservation proof**, not
whole-program inference about which states a caller will usually supply. Runtime
entry checks establish the required facts; the local proof establishes that those
facts continue to hold whenever the driver takes its back edge. Other entries and
unrelated helper callers retain the original implementation.

This is the strongest next implementation candidate, **not a production-ready
optimization**. New experiments demonstrate the code shape and a feasible local
proof obligation. Automatic loop discovery, scoped cloning and profitability
selection remain unimplemented. A short-source regression remains, so there is
no evidence for universally enabling any of the tested strategies.

The confidence skill's request for 100% confidence cannot be established by these
experiments. The useful outcome is a tested strategy with explicit assumptions,
negative cases and remaining gates, rather than a numerical certainty claim.

## What changed in the investigation

The original proposal risked expanding into initializer analysis and global
state propagation. That is unnecessary for the demonstrated range loop:

- Its current caller checks source exhaustion and the **outer** control tag. It
  does not thereby establish the take count or **inner** control tag. Merely
  inspecting those existing branch facts cannot justify the fast helper.
- Instead, test `P = count > 0 && inner is Continue` at loop entry. If false,
  execute the original loop. This handles arbitrary valid input states without
  assumptions about their initializer or how they were constructed.
- On the fast loop, require `P(state) && next.outer is Continue => P(next.state)`.
  For this pipeline, rejection leaves count/tag unchanged; acceptance at count
  greater than one decrements to another positive count; acceptance at one
  returns outer Stop, so it takes no next step. U32 wrapping does not affect P.
- Clone only the bounded helper chain used by that loop. The generic helper stays
  unchanged for direct calls and other callers. Do not replace a shared helper
  globally based on evidence from one caller.

`inspect_induction.py` uses the existing pass's **typed scalar path expressions**
with a manually supplied feedback map and continuing-output tag. It establishes
the implication for the public pipeline and reordered fixture. It rejects a
variant that changes the inner tag while returning outer Continue. This is a
local symbolic check, not automatic discovery of the caller's feedback map and
not a mechanized proof of the compiler implementation.

[Induction evidence](induction-results.json) records the guards, paths, feedback
map, output expressions and per-condition results. The automatic implementation
must derive that map and the continuation condition from the typed caller, not
copy the diagnostic's positions or assume that tag zero means Continue.

## Measured alternatives

`loop_version.py` is a **program-specific generated-C diagnostic**. It obtains the
fast scalar expressions from the automatic compiler, but manually identifies and
clones the scalar helper, its predicate wrapper and the range driver. Its symbol
and field assertions must not become production recognition rules.

Two versions were tested:

- **Entry version:** check P once, then run either the original loop or a fast
  loop without per-step fallback checks. Requires the preservation proof.
- **Loop bailout:** check P at each step boundary. On the first failure, transfer
  the untouched current state and remaining source to the original driver, which
  finishes the reduction. No repeated outlined fallback calls and no inductive
  assumption are needed. The diagnostic's transfer point is safe for scalar
  ranges; owned-source handoff has not been implemented or validated.

Ten retained samples after warmup, forward/reverse order, Clang 17 -O3, sequential
CPU, runtime thresholds. Milliseconds per batch; compare columns within a row.

| Workload | Original | Outlined helper | Entry version | Loop bailout | Handwritten |
| --- | ---: | ---: | ---: | ---: | ---: |
| Mixed full range | 320 | 89 | **85** | 87 | 88 |
| Predictable full range | 47.5 | 34.5 | **30** | 33 | 33 |
| Mixed early | 135.5 | 98 | **94.5** | 100 | 100 |
| Predictable early | 24 | 18 | **15** | 17 | 17 |

[Full samples](loop-strategy-results.json), [early samples](loop-strategy-early-results.json).
Every timed batch passes the independent oracle. The original scalar differential
and UBSan checks still run for the automatic helper. This does not establish a
cross-platform advantage over handwritten code.

The driver variants additionally pass **400,000 full driver-state comparisons
each**, including both outer/inner tags, zero/one/two/three/max count, source
exhaustion, wrap boundaries and random states. Source, mapper and predicate entry
counts and their ordered argument fingerprints match the original driver under
UBSan. [Entry checks](loop-entry-validation.json), [bailout checks](loop-bailout-validation.json).

The induction requirement was tested negatively, not merely asserted. A controlled
C perturbation gives both the generic and fast one-step transition identical
semantics on P, but changes the inner tag on an accepted outer Continue:

- Entry-only versioning then produces a [concrete counterexample](loop-entry-counterexample.json).
- Per-step bailout still passes another **400,000 driver-state/trace comparisons**
  under UBSan on that non-inductive transition.
  [Negative-transition bailout checks](loop-bailout-noninductive-validation.json).

The typed negative fixture and C perturbation serve different purposes: the former
checks rejection by the proposed proof, and the latter demonstrates why skipping
that proof is unsafe and why bailout does not need it.

## Profitability loophole: short sources

The [loop-level stress test](loop-fallback-results.json) uses one million complete
driver invocations per batch with runtime no-match thresholds and controlled
zero/stopped entry frequencies. Checksums match an independent oracle. Unlike the
earlier helper-only stress test, this includes dispatch and the complete source
loop. Six retained samples per variant.

For 32-element sources and 100% exceptional entries:

| Entry state | Original | Outlined helper | Entry version | Loop bailout |
| --- | ---: | ---: | ---: | ---: |
| Zero count | 17.313 ms | 52.331 ms | 17.523 ms | 12.581 ms |
| Stopped inner | 17.297 ms | 47.194 ms | 17.449 ms | 12.706 ms |

Moving the boundary to the loop removes the large repeated-fallback penalty in
these cases. It does **not** establish zero overhead everywhere. With one-element
sources, several original cases take about 0.99 ms per million reductions, entry
versioning about 1.23–1.29 ms, and bailout about 1.63–1.97 ms. The absolute cost is
sub-nanosecond to roughly one nanosecond per reduction in those cases, but the
relative regression is real and matters for a blanket compiler policy.

A further [short-source experiment](loop-small-source-results.json) adds a runtime
entry restriction requiring both source and take budgets to exceed one. It does
**not** cure the short-source regression and can worsen it. Therefore "add another
runtime size check" is not a demonstrated fix. Do not bake this diagnostic's
threshold or field positions into the compiler.

The better next gate is whether caller-aware lowering can leave **statically
trivial** calls on the original path without routing them through a larger
wrapper. Dynamic short-source cases still need a measured profitability policy;
static selection alone cannot establish their cost. No such policy is implemented.

The range diagnostic adds about 3.8 KB of emitted C (one scalar body, one wrapper
chain and a second loop). The sampled executable sizes did not grow materially,
but runtime/object alignment can hide changes. This is not a code-size guarantee;
an automatic pass needs explicit clone/work budgets.

## Known loopholes and required handling

| Loophole | Required handling / current evidence |
| --- | --- |
| Generic Continue with zero is valid | Runtime P check; original loop for failure. Full-state tests cover it. |
| Fast guard can fail after a continuing transition | Prove preservation from expressions and actual back-edge arguments; negative fixture must be refused. Bailout is an alternative, not a substitute proof for entry-only code. |
| Wrong field/tag feedback mapping | Derive identities from typed call bindings and the caller's branch. Never infer from record names, positions, or numeric-zero convention. Manual map is the current missing automation. |
| Fast helper reused by an unguarded caller | Keep original helper; clone and key specializations by their proven context. Existing `fl.spun` is keyed by callee/layout, so global replacement is insufficient. |
| Guard depends on a newly mapped input or opaque call | Entry versioning must refuse unless every guard operand is already available as a safe loop-entry scalar. No speculative callbacks to compute guards. |
| Source has already been consumed at bailout | Resume only with still-owned, unconsumed inputs. Start with the scalar range loop; decline boxed/ownership-sensitive cases until the handoff is verified. |
| Callback/failure/completion order changes | Clone existing operations in place; pure entry test only. Driver event traces pass, but arbitrary callbacks, failures and completion need compiler-integrated tests. |
| Bailout changes runtime polling state | Re-entering a native helper can reset its internal `wpoll` counter. Preserve required error/cancellation handling or verify the backend contract; sequential no-error traces do not establish that behavior. Entry cloning keeps the original loop's polling structure. |
| Extra back edges, state edits between step and recursion, indirect calls | Refuse outside a bounded, explicitly recognized loop/call chain; no guessed transitive facts. |
| One-element or frequently stopping loops | Preserve statically trivial callers; measure dynamic short cases. Added runtime count gating is experimentally insufficient. |
| Compile time/code size expands | Limit loop/call-chain depth and clones; fall back unchanged when limits are exceeded. |
| Backend differences | CPU-only until actual backend gates pass; do not infer GPU validity from these C experiments. |

These are identified risks and fixes, not a claim that every possible compiler bug
has been enumerated.

## Impact, effort and value

Effort here means semantic complexity, proof/ownership obligations, maintenance
and API consequences, not implementation line count. All recommended options
preserve Source/Reduction and the public pipeline API.

| Priority / option | Impact | Effort | Value / decision |
| --- | --- | --- | --- |
| **1. Bounded automatic loop-entry versioning + local preservation proof** | High: best full/early results; eliminates repeated helper fallback for the target loop | Medium–high: typed feedback mapping, scoped native clones, local proof and code-growth limits | **Highest next prototype.** Runtime entry checks avoid whole-program initializer inference. Start with one scalar range loop. |
| **2. Caller-level treatment of trivial loops and dynamic short-loop cost gate** | High for promotion confidence: prevents hiding a small-input regression behind long-loop gains | Medium: caller facts and measured cost policy; no API change | **Required alongside 1 before default enablement.** Do not rely on another runtime threshold check. |
| **3. Per-step transfer to the original loop** | High: near-handwritten target timing, robust even when P is not inductive | Medium–high: continuation/state/ownership handoff and small-input costs; avoids induction proof | **Backup design.** Prefer if bounded preservation checking cannot support the desired cases; do not build both production paths prematurely. |
| 4. Whole-program initializer/loop invariant propagation | Potentially broad, but no incremental benefit demonstrated for this target | Very high: global contexts, recursive fixed points, ownership/aliasing and maintenance | **Defer.** A runtime entry check plus local implication suffices for the demonstrated loop. |
| 5. Global outlining, blanket inlining or attribute changes | Already measured tradeoff; none meets both target and exceptional-state goals | Low implementation cost, unresolved workload-dependent behavior | **Reject as the default solution.** Keep as controls only. |
| 6. Public specialized pipeline or Source API changes | No demonstrated need | High permanent API/semantic maintenance cost | **Do not pursue.** The successful diagnostics use the unchanged pipeline. |

## Concrete next milestone and confidence

Build one automatic end-to-end caller case in an isolated compiler:

1. Discover a single self-loop and bounded direct helper chain in typed terms.
2. Derive the fast guard's entry operands, the state feedback map and actual
   continuation condition. Unknown mappings and non-inductive transitions keep
   original code.
3. Emit an original loop plus a guarded specialized version; preserve original
   helper identity for unrelated callers. No source/helper-name recognition.
4. Run the full-state/trace and non-inductive rejection tests on the **automatically
   emitted** loops; add shared-callee/short-loop cases, lifecycle/failure checks,
   map-chain assembly parity, and clone/compile-time bounds.
5. Compare full, early, no-match, tiny-source and fallback-heavy timings before
   deciding any default policy. Preserve an explicit unsupported fallback.

**High confidence** that loop-scoped specialization is a better next direction
than whole-program inference or another annotation tweak: it has local proof and
measurement evidence. **Moderate confidence** in the bounded automatic integration
until caller mapping and native-cache scoping are implemented and tested. **Not
confident enough for production promotion:** short-loop profitability, automatic
lowering, broader sources and backend gates remain open.

## Reproduction

Use the isolated compiler printed by `prepare_guarded.py`. These experiments leave
both production repositories unchanged. Run timed measurements sequentially.

```sh
python3 bench/compiler/inspect_induction.py --bend-main /tmp/candidate/main.ts --output /tmp/induction.json
python3 bench/compiler/ablate.py --automatic-compiler /tmp/candidate/main.ts --loop-version --samples 5 --output /tmp/loops.json
python3 bench/compiler/ablate.py --automatic-compiler /tmp/candidate/main.ts --loop-version --early --samples 5 --output /tmp/early.json
python3 bench/compiler/test_loop_version.py --report /tmp/loops.json --output /tmp/entry-check.json
python3 bench/compiler/test_loop_version.py --report /tmp/loops.json --bailout --output /tmp/bailout-check.json
python3 bench/compiler/test_loop_version.py --report /tmp/loops.json --break-induction --output /tmp/entry-counterexample.json
python3 bench/compiler/test_loop_version.py --report /tmp/loops.json --bailout --break-induction --output /tmp/bailout-negative-check.json
python3 bench/compiler/loop_fallback.py --report /tmp/loops.json --samples 3 --output /tmp/loop-fallback.json
```
