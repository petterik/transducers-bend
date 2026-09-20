---
created_at: 2026-09-20T22:54:05+02:00
status: proposed
---

# Proposed repairs after the follow-up review

Make the compiler safe, make the comparisons fair, then use that evidence to
decide which optimizations and API changes deserve to stay.

This proposal addresses all six findings in the
[follow-up review](../review/FOLLOWUP-IMPLEMENTATION-REVIEW.md) of `cd2bcb7`.
It specifies work for review; the repairs have not been implemented. Keep the
existing source-independent reducer protocol and `keep = map(f) → cat_maybe`.
Continue compiler experiments in isolated copies. Each workset ends with its
own commit and a record of which original acceptance conditions passed.

## Priority

Effort means difficulty of reasoning, maintenance, testing and API change.
It does not mean line count or time spent learning a library. Value combines
impact with those costs and with how much later work the repair enables.

| Order | Problem / recommended work | Impact | Effort | Value | Dependency |
| --- | --- | --- | --- | --- | --- |
| 1 | Contain constructor facts at shared helpers | Critical: prevents wrong results | Low–medium for containment; high for later specialization | Highest | None |
| 2 | Repair the independent keep reference | Critical: makes correctness/performance comparisons valid | Low–medium | Highest | None; validate compiler comparisons after 1 |
| 3 | Complete public extension lifecycle tests | High: catches incorrect stopping, flushing and ownership | Medium | Very high | Reuse the reference from 2 |
| 4 | Attribute representation costs to the actual computation | High: identifies what needs optimizing | Medium–high | High | Safe compiler from 1 |
| 5 | Replace median-only acceptance with paired measurements | High: makes parity decisions defensible | Medium | High | 1–3 for semantic validity; 4 for fusion explanations |
| 6 | Test and improve real configured composition | High for library use and language design | Medium–high | High, after correctness | 3; use 4–5 to evaluate the chosen API |

The order is a delivery order, not a claim that the last item matters less to
the language. The API investigation can start after lifecycle tests, but its
acceptance must include the repaired code-shape and performance checks.

## 1. Prevent one caller's knowledge from changing another caller's code

The compiler currently knows that one call passes `Left`. It removes the
`Right` branch from a helper, then reuses that helper for a call passing `Right`.
The fix must control where that knowledge is valid.

| Option | Impact | Effort | Value / decision |
| --- | --- | --- | --- |
| Disable the entire new fact pass | Immediate correctness fallback for this new pass | Low | Useful emergency fallback; loses all benefits of the experiment |
| Drop caller facts when entering a shared helper | Removes the reproduced leak; preserves opportunities within a local emitted body | Low–medium | **Recommended first** |
| Make separate helpers for each checked set of facts | Can preserve cross-call optimization | High: cache identity, recursion, code growth, ownership | Later, only for a measured cost |
| Insert runtime guards before specialized helpers | Can handle uncertain callers | High: extra branches and two versions of code | Defer; unnecessary for the first repair |

Build a shared helper using only what its declared inputs guarantee. Do not
copy facts from the first actual call into its parameters. For facts kept
inside one emitted body, follow the exact value as it moves; drop knowledge
when that connection is uncertain. Returning to a loop or entering another
continuation must not silently reuse assumptions from an earlier value.

Also separate two different statements: “this value was built with Left” and
“this field is a compile-time constant.” Giving a constant a runtime parameter
name does not make that parameter safe to put into a static data image. Audit
`fact_rebind`, held aliases and nested fields. Clear static eligibility when
rebinding to runtime storage unless a separately checked constant representation
is retained. Do not broaden the match rewrite to dynamic/affine payloads during
this repair.

The immediate implementation belongs in `bench/compiler/prepare_static.py`,
with ordinary Bend regression fixtures. Removing the `emit_native` fact import
fixed the two known failing inputs in the review's temporary experiment. That
is strong evidence for containment, not proof that every remaining fact path
is sound.

**Acceptance:** run opposite-constructor callers in both source orders, repeated
calls, a known caller followed by a runtime-selected caller, differing payloads,
and same-layout types. Add a recursive example whose next call changes the
constructor, plus nested constructor and alias cases. Require correct native
and JS outputs, relevant sanitizer checks, and both emission orders (JS then C,
C then JS). Run the existing suite. Confirm the intended generic path is used
where facts were dropped. If the small positive optimization disappears, record
that loss; correctness takes precedence over retaining its byte-count result.

Only then consider separate specialized helpers. Their identities must describe
the assumptions used to generate them. Every call and loop re-entry must either
establish those assumptions or take the generic path. Set limits on the number
and size of helper versions before measuring their benefit. This is a separate
workset, not part of the immediate bug fix.

## 2. Give keep a small, correct independent reference

The budget counts emitted values. None does not spend it. Once the last allowed
Some is emitted, the mapper must never see the next input.

| Option | Impact | Effort | Value / decision |
| --- | --- | --- | --- |
| Patch only the first decrement | Fixes the budget-1 example | Low | Incomplete: the extra callback problem remains |
| Rewrite the reference as a direct consuming loop | Makes stopping and budget rules explicit | Low–medium | **Recommended** |
| Use keep itself to compute expected results | Easy agreement with the candidate | Low | Reject: both sides would share the implementation under test |

The direct loop should do this, in order:

1. If the budget is zero, return the accumulator and discard the remaining source.
2. If the source is empty, return the accumulator.
3. Consume one input and call the mapper once.
4. On None, continue with the same budget.
5. On Some, consume the payload and subtract one from the budget. If that leaves
   zero, return immediately; otherwise continue.

Use a small direct Bend reference whose consumer matches the benchmark's result.
Test this exact implementation before using it in generated performance programs.
Keep the immutable broken fixture as historical evidence; add a regression that
calls the current benchmark reference. Merely editing the copied fixture could
make the review script pass while leaving the real benchmark broken.

**Acceptance:** empty input; budget 0, 1, 2 and oversized; None before/between/after
Some; all None; all Some; type-changing values. Observe ordered results and mapper
calls, not only a sum. Include a mapper that fails if reached after stopping,
and a separate test where it must be reached and must fail. Run native and JS
independently. Keep the reference free of transducer calls. Re-run all retained
benchmark cases after fixing it; the previous timings remain historical.

## 3. Observe the public adapters' complete lifecycle

A correct result list does not tell us whether completion ran twice or whether
the source advanced after stopping. Tests need to observe those events.

| Option | Impact | Effort | Value / decision |
| --- | --- | --- | --- |
| Add more final-output examples | Improves value/order coverage | Low | Useful but insufficient |
| Test public adapters with observable consumers and independent references | Covers the actual contract | Medium | **Recommended** |
| Add permanent instrumentation to production adapters | Makes internal events easy to count | Medium–high; changes code being measured | Avoid for the library; use dedicated fixtures |

Create a consumer whose state records ordered emissions and whose finish appends
a visible completion marker. Add dedicated JS call counters for source, start,
step and finish, following the existing runner pattern. On native, use observable
state transitions and checked-failure sentinels where possible. A marker detects
many lifecycle errors, but it cannot prove that an extra discarded call never
happened; state that limit. Instrumentation must fail loudly if its target changes.

Exercise public `partition_all`, not only the old mock buffer. The matrix must
include empty input, widths 0/1/2/larger than input, full and partial groups,
downstream initial Stop, custom consumer Stop on a full group and during a partial
flush, take on either side, nested partition, and repeated runs with new settings.
The consumer's Stop during flush permits no further emissions; finish still runs
once. For nested partition, inner completion may supply an outer partial group.

Run shared cases on List, range and the external tree. Run affine cases on
sources that can hold affine values: closure payloads through keep output and
partition full/partial/stop paths. Do not assert that discarded affine values
execute a destructor; Bend permits dropping them. Check that values actually
used are neither copied nor used after consumption, with compile-time rejection
tests where appropriate.

**Acceptance:** exact values/order, expected event counts where measured,
independent direct-reference agreement, and sentinels with proven failing
positive controls. Native evidence must not be inferred from JS counts. Record
any remaining unobservable requirement rather than calling the whole matrix done.

## 4. Ask the compiler where the costs belong

Finding five callback jumps in a whole program does not tell us whether they
belong to the reducer, an input closure, or printing the answer.

| Option | Impact | Effort | Value / decision |
| --- | --- | --- | --- |
| Keep whole-file counts with weaker wording | Honest descriptive data | Low | Retain as supplementary data only |
| Build a detailed parser for generated C | Can recover some call relationships | Medium–high; tied to emitted syntax | Fallback, not preferred |
| Emit structured diagnostics from the isolated compiler | Knows call targets, emitted bodies and their origins | Medium–high | **Recommended** |

Add optional diagnostic records when the compiler emits a call, constructor,
pack/unpack operation, or match rewrite. Each record identifies the emitted
function/segment, original definition or source location where available,
operation, known target, and the facts that authorized a rewrite or reason for
refusal. Keep these records outside the generated program. Enabling diagnostics
should leave emitted program bytes unchanged.

Starting at a selected reduction entry, follow known call edges and include
reachable helpers and continuations. Count each emitted site once; site counts
are not runtime frequencies. The test fixture identifies the requested entry
and callback roles. The optimizer itself must not recognize names such as keep
or partition. When provenance cannot distinguish an element callback from a
reducer callback, report “unknown,” not “no reducer overhead.” Unknown calls
also prevent an allocation-freedom claim about the code they can reach.

**Acceptance:** controls for a static reducer, a genuinely dynamic reducer and a
legitimate closure-valued input. Test an unresolved target and require an
inconclusive report. Explain the buffered fixture's dispatch sites. For a local
rewrite, show the specific before/after operation that disappeared, while real
buffer/output storage remains. Record compiler, library, fixture and harness
identities. Call the 85-byte result branch elimination until stronger evidence
demonstrates an allocation or dispatch saving.

## 5. Measure equivalent work and make uncertainty part of the result

| Option | Impact | Effort | Value / decision |
| --- | --- | --- | --- |
| Keep five consecutive samples and compare medians | Simple descriptive result | Low | Insufficient for a 5% acceptance threshold |
| Pair and alternate executions with declared statistics | Reduces order bias and exposes uncertainty | Medium | **Recommended** |
| Build a large benchmarking framework | Broad infrastructure | High maintenance | Unnecessary for this decision |

First define equivalent operations. Partition comparisons should produce ordered
groups or feed every group to the same order-sensitive consumer. Before timing,
compare exact small outputs with an independent oracle. A count-only lower bound
may remain, clearly labelled as a diagnostic. Include runtime configuration,
mixed Some/None and type-changing keep, partial/nested groups and both stopping
orders. Build source data and dispose of unused owned tails under matched rules.

Keep the end-to-end rows that include source construction and cleanup. Add rows
with source sizes suited to the stopping budget, so making a huge list cannot
hide reducer overhead. If a prepared-source experiment is useful, prepare a fresh
owned source for every run; include the unavoidable consumption/cleanup cost and
label the scope. Do not subtract two noisy timings or reuse consumed affine data
to manufacture a “pure reducer time.” Fusion claims also need evidence from 4.

Proposed protocol, to freeze before collecting acceptance results:

- Calibrate repetitions on both lanes to at least 100 ms per measured batch;
  use the same repetition count for that pair, then freeze it. Calibration is
  excluded from retained samples. If the floor cannot be reached reasonably,
  mark the row inconclusive.
- Use ten separately launched sessions, each with five paired native batches.
  Balance which lane runs first, retaining the schedule, seeds and raw samples.
  Avoid running competing benchmark jobs. Keep warmup policy fixed.
- Each session yields one estimate from its paired log time ratios. Combine
  sessions with equal weight; bootstrap whole sessions to obtain a one-sided
  95% upper confidence bound on the transducer/direct ratio. This is a proposed
  statistical decision rule, not a claim that sessions erase all machine noise.
- A row passes the existing 1.05 gate only if its upper bound is at most 1.05.
  Report the estimate and bound. A clear slowdown fails; an interval overlapping
  the threshold is inconclusive. Never change the threshold after seeing results.
- Inspect between-session variation. If a fresh run is needed, declare its size
  first and retain the earlier run; do not repeatedly sample until a pass appears.

The exact proposed sample counts can be reviewed now. Once accepted, they should
not be tuned to favor a result. Use the unchanged reference compiler and repaired
candidate to separate compiler effects from library-versus-direct effects. Measure
compilation cost and code size separately. All correctness checks precede timing.

**Acceptance:** retained raw data and identities; equivalent semantic cases;
calibration; paired schedule; uncertainty bounds; explicit pass/fail/inconclusive
per row. An overall parity statement requires every predeclared required row to
pass. Conclusions remain limited to the tested source, hardware and backend.

## 6. Make settings belong to the pipeline, not its callers

The current API test proves that a simple keep declaration can be reused. It
does not prove that a user can configure a realistic pipeline without knowing
its internal nested tuple structure.

| Option | Impact | Effort | Value / decision |
| --- | --- | --- | --- |
| Document the existing tuples | Reliable baseline | Low | Keep as the comparison, not the desired user experience |
| Add named settings at a pipeline's initialization boundary | Hides internal configuration while preserving ordinary reducers | Medium | **Recommended experiment** |
| Derive configuration builders through general composition | Best long-term consistency | Medium–high, depends on type expressiveness | Attempt after the concrete experiment |
| Add a runtime stage registry/interpreter | Flexible stage lists | High API/optimization consequences | Does not match this design's current goal |
| Change Bend to support richer static composition | Could solve the general expression problem | High language design and compatibility effort | Decide only from retained minimal blockers |

Use one real pipeline: configured filter → type-changing keep → take → partition.
Give it named settings such as threshold, kept-value limit and group width.
Keep consumer configuration separate: a count consumer and a group collector
need different initial values, and those values may be affine.

Prototype a general configuration adapter around an existing reducer. At start,
it translates the caller's settings into the wrapped reducer's required
configuration. Step and finish delegate unchanged, and the wrapped state type
stays the same. This is an initialization-only boundary: no settings interpreter
or extra callback needs to run per element. Its external configuration must accept
`Type` where the consumer needs it; do not force an owned collection into `Data`.

The intended user experience is conceptually:

```text
pipeline = declare transformations once
settings = { threshold, kept_value_limit, group_width }
run(pipeline, settings, chosen_consumer, consumer_settings, source)
```

This is a desired shape, not verified Bend syntax. First make a concrete wrapper
work, then see whether its internal configuration builder can be derived alongside
composition. A handwritten builder is a useful experiment, but a second maintained
copy of the pipeline's stage structure is not the final abstraction we want.

Retain the existing failed comp/settings attempts as executable minimal cases,
with exact compiler identities and diagnostics. Compare them to an explicit-tuple
version that works. Check parameter order, kinds and dependent configuration types
before classifying a failure as a language limit. A failed spelling is not proof
that the idea cannot be expressed in Bend.

**Acceptance:** one declaration, multiple runtime settings, fresh state on each
run, count and ordered-group collection, on List/range/tree; preserve initial Stop,
partial flush and completion. Test at least one non-Unit consumer configuration.
Inspect generated code and run applicable performance cases after API changes.
If general derivation is blocked, record the exact blocker and alternatives;
mark the concrete wrapper partial, and prepare a separate language proposal.

## Confidence checks and completion rules

These are the main ways a superficially successful repair could still fail:

| Loophole | Required protection |
| --- | --- |
| Only the original caller order is fixed | Reverse callers; mix known/unknown values; change constructor on recursion |
| A runtime alias is still treated as a constant | Separate constructor knowledge from static storage eligibility; nested-field tests |
| The copied wrong-code example passes but the real benchmark remains broken | Test the current reference implementation used to generate timed programs |
| Correct sums hide extra callbacks, lost order or repeated finish | Ordered outputs, lifecycle observations, and checked failures with positive controls |
| The sentinel is optimized away or never reached in any test | Independently demonstrate its expected failure on each backend |
| A large common cost hides slow reduction | Scope-matched small-source rows plus attributed code-shape evidence |
| An unresolved call looks like zero overhead | Treat unknown attribution as inconclusive |
| A temporary wrapper is declared the final API | Separate concrete feasibility from derived configuration and general composition |
| Losing the old optimization encourages weakening the correctness gate | Retain the generic path and record the performance loss explicitly |
| Each passing example becomes a new definition of done | Keep the original acceptance checklist; report unmet items individually |

Each implementation commit should state the changed behavior, tests run, exact
identities, measured scope and remaining gaps. Preserve the historical review
artifacts and add current regression tests rather than overwriting evidence.

These six repairs restore a reliable foundation. They do not by themselves finish
the earlier design: the eager Array/static-composition blocker, general visible
Maybe elimination, broader checked summaries, and applicable upstream/device
gates remain open. Tree specialization remains refused until its own proof and
tests support it. General reducible-source support is the library direction;
channels/files and other effectful sources still need their own lifecycle contract.

I have high confidence in this order and in conservative containment as the first
move. Cross-call specialization and general settings derivation remain design
questions to settle with the specified experiments. Finite tests cannot establish
100% correctness; the proposal makes uncertainty and refusal explicit rather than
turning an incomplete experiment into a completion claim.
