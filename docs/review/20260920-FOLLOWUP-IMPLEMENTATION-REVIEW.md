---
created_at: 2026-09-20T22:50:35+02:00
status: current
---

# Follow-up implementation review

Reviewed revision: `cd2bcb7`. Verdict: changes requested. The library composition
is a useful improvement, but the fact compiler has a reproduced wrong-code bug
and the follow-up plan's acceptance criteria have not been met. This supersedes
the earlier positive assessment of the facts compiler in the current handoff and
validation checkpoint. It does not invalidate their recorded individual runs.

## Findings, in priority order

### P1: caller facts escape into a shared native helper

`bench/compiler/prepare_static.py:106–124` passes actual-argument facts into
`emit_native` and installs them on the helper's formal parameters. The existing
helper cache (`../bend/bend2/comp.ts:2250`) is keyed by function and erased-argument
layouts; it does not include these facts or check their premises at later calls.
The first caller therefore decides which constructor branch every caller runs.

The retained ordinary-code reproducer is
[`shared_constructor_fact.bend`](../../review/shared_constructor_fact.bend).
It calls the same matcher with `Left{5}` and `Right{7}` and a runtime Boolean.

| Input | Reference native / JS | Candidate JS | Candidate native |
| --- | --- | --- | --- |
| No arguments | 112 | 112 | **12** |
| One argument | 213 | 213 | **14** |

The candidate native failures also reproduce with UBSan. Both compilers pass
the existing 20-file suite. This directly demonstrates why the plan required
differing callers and failed-precondition tests, beyond a positive example and
one dynamic-field refusal.

Immediate repair: drop caller-specific facts at the shared `emit_native`
boundary. I tested this removal in a temporary compiler copy; both inputs then
return 112 and 213 correctly. This is a mitigation experiment, not a reviewed
production repair. If specialization is retained later, its identity must include
the relevant semantic premises, with checked argument mapping and explicit
recursive/back-edge handling. Do not simply add a constructor tag to a cache key
and assume that all facts and loops are now sound.

`fact_rebind` also preserves field `stat` flags while replacing constants with
runtime parameter names (lines 147–149). Thus the documented claim that eligible
fields are necessarily scalar constants is too strong. Audit nested facts and
static-image eligibility separately from constructor knowledge.

### P1: the direct keep benchmark is not a correct stopping reference

`bench/extension_parity.py:106–113` decrements the budget before learning whether
the first mapped value is Some. At budget 1, an initial None returns immediately,
even when the next input should be emitted. The retained reduction of the
benchmark template, [`keep_reference_boundary.bend`](../../review/keep_reference_boundary.bend),
prints `0` for the direct implementation and `1` for the transducer on both
backends and both compilers. The expected pair is `1, 1`.

The step loop also computes the next mapped value before checking whether the
current Some exhausts the budget. For an all-Some prefix this evaluates one
extra callback beyond stopping. The retained large fixtures use a pure mapper
and return equal sums; they do not establish equivalent evaluation behavior.

Repair the oracle to decrement only on emission and stop before evaluating the
next input. Test budget 0/1/2, leading/consecutive None, all Some, and a checked
failure after the stopping point before reusing it for performance acceptance.

### P2: performance acceptance was replaced with descriptive medians

`bench/extension_parity.py:234–250` executes all samples of one lane in one
process, then all samples of the other. There is no paired/alternating schedule,
independent-session evidence, block bootstrap, confidence bound, or enforced
duration calibration. The report has five consecutive observations per lane;
a median ratio below 1.05 does not satisfy the predeclared upper-ratio gate.

The early-stop rows build and discard 200,000 source elements to process only
32 kept values or two groups. End-to-end parity is useful, but that common cost
can hide substantial reducer overhead; it does not prove fusion. The partition
reference counts groups without reproducing their complete ordered contents.
This is disclosed as a diagnostic, but the plan explicitly required equivalent
group-consuming rows too. Type-changing keep, runtime settings, width 2, partial
completion, nested partition and both stopping orders are absent from this matrix.

Withdraw the “passes” labels in `20260920-EXTENSION-PARITY.md` until the oracle and
measurement schedule satisfy workset 5. Retain the numbers as observations.

### P2: the repaired dispatch detector still cannot establish the promised scope

`bench/compiler/representation_probe.py:60–81` now counts a real dispatch spelling
and has a useful negative control. However, counts remain whole-file substrings.
There is no function/segment reachability attribution, separation of affine
element callbacks from reducer callbacks, or inconclusive result for unknown
targets. Allocation counts likewise include runtime/support functions.

This is partial workset 0, not its stated exit. Add scoped call-site evidence
and source/library/harness provenance before using the report as a fusion gate.
The 85-byte total-C reduction in the local probe is a narrow branch-elimination
observation; its harness does not establish removal of a keep/Maybe allocation
or dispatch boundary.

### P2: public extension lifecycle acceptance remains incomplete

`tests/keep_partition.bend:62–110` adds useful initial-stop, partial-flush, empty,
nested and affine-input examples. Its custom completion functions are identity
functions, so outputs cannot detect zero versus repeated completion. The runner
does not instrument this fixture. Existing lifecycle/completion tests exercise
other adapters or mock buffering, not the full public partition matrix.

Missing evidence includes completion markers/counts for full and partial custom
consumer Stop, checked native forbidden-evaluation sentinels with positive
controls, affine output from keep, affine partial/stop paths, and the required
shared List/range/tree reference matrix. Correct output examples do not close
these lifecycle obligations. Workset 1 is partial despite the completion record.

### P2: the configured-API checkpoint does not test the configured API

`tests/api_surface.bend:6–10` is a reusable keep-only pipeline. Its mapping always
returns Some and every run supplies Unit configuration. It contains no configured
filter, take, partition, named settings, or derived configuration builder.
It cannot close the semantic portion of workset 6 as claimed in
`20260920-CONFIGURED-API.md` and the repair plan.

The failed generic-comp and settings-record probes are described in prose but
their sources are not retained. Preserve minimal executable failures and a
successful explicit-tuple comparator before treating either as a language
limitation. Complete the concrete configured pipeline and multiple-consumer
experiment specified in the plan.

## Acceptance against the original follow-up plan

| Workset | Review status |
| --- | --- |
| 0: measurement/status | Partial; genuine dispatch spelling fixed, attribution absent |
| 1: composition/semantics | keep composition implemented; lifecycle matrix incomplete |
| 2: systematic static composition | Memoization experiment; eager Array blocker and required diagnostics/negative tests remain |
| 3: scoped facts | Rejected candidate: shared-caller wrong code; checked summary boundary absent |
| 4: representation elimination | Narrow example only; depends on unsound fact propagation; Maybe target open |
| 5: extension parity | Diagnostic data only; oracle and statistical acceptance need repair |
| 6: configured composition | Open; Unit-config reuse is not the requested configured experiment |
| 7: promotion | Open; no promotion recommendation |

Isolated compiler copies are appropriate here and were explicitly required by
the plan. The problem is correctness and acceptance coverage, not the absence
of edits in the sibling checkout. Keep `map(f) → cat_maybe`: its consuming match
preserves the intended affine-friendly semantics without compiler registration.

## Validation and next work

I ran `bend guide`, rebuilt the facts compiler from the checked-in preparation
script, and reran the full suite on candidate and reference: both pass 20/20.
The newly retained review harness builds both backends and checks native with
UBSan; it fails on the two findings above as expected. Results and exact hashes
are in [`followup-review-results.json`](../../review/followup-review-results.json).

```sh
python3 bench/compiler/prepare_static.py --facts --output-dir /tmp/review-facts
python3 review/check_followup.py --bend-main /tmp/review-facts/main.ts \
  --output /tmp/followup-review-results.json
```

Repair in this order: (1) contain facts and add multi-caller/back-edge regression
tests; (2) fix the direct oracle and complete lifecycle tests; (3) repair scoped
measurement and paired statistical gates; (4) return to static composition,
visible Maybe elimination and configured settings. Reassess the original exit
criteria after each workset rather than redefining completion around the probe
that happened to succeed. No claim of exhaustive correctness follows from this
review; the concrete counterexamples are sufficient to withhold approval.
