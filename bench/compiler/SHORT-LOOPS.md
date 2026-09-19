# Short-loop profitability checkpoint

## Decision

Pause here with all policies experimental. Automatic loop specialization retains
near-handwritten full/early range performance, but profitability depends on source
length, entry state, predicate, and backend optimization. No tested policy wins
across the expanded matrix. Neither the public library nor the sibling compiler
has changed. The default isolated `--loop` experiment retains its earlier behavior.

The only additional automatic policy is opt-in `--loop --source-gate`: a unique
scalar Nat parameter that decreases by one on every back edge is inferred from
typed terms. Dynamic values zero/one select the original loop before the existing
entry guard. Multiple qualifying countdowns leave entry mode unchanged. This is a
profitability choice, separate from the existing preservation proof; it is not a
new API or a production recommendation.

## What the measurements establish

Within `source-gate-results.json`, mixed full-range medians were 319.5 ms original,
88 ms handwritten, and 85 ms for both entry specialization and source gating.
Mixed early medians were 129 / 96 / 93 / 93 ms. Predictable full/early workloads
also retained the earlier gains. Absolute timings drifted during this session;
compare paired variants within one report, not absolute times across reports.

Longer batches and independent input variation changed the short-loop conclusion.
For a one-element reject-all source, source gating took 1.389 ms per 2^20 calls,
versus 1.669 original and 1.945 entry specialization. But with two elements,
reject-all, and zero-count entry states on 25% of calls, it took 3.898 ms versus
2.335 original and 3.550 entry specialization: about 67% slower than original.
These are local measurements, not a workload-weighted application forecast.

| Policy | Evidence | Decision |
| --- | --- | --- |
| Automatic source gate | Fixes many zero/one cases; independent two-element cases regress substantially | Keep opt-in only |
| One generic iteration before switching | Adds short-loop costs | Reject as current direction |
| Switch after first accepted predicate | Retains long-range gains; some tiny cases still roughly 14% slower | Diagnostic only |
| Deferred switch plus source gate | Not additive; some tiny cases roughly 27% slower | Diagnostic only |
| Constant guard / forced wrapper inline | Promising with unknown state; constant state and dynamic lengths still regress | Insufficient profitability rule |
| Constant region / call-site constant selection | Keeps long gains; known-state varying lengths still regress up to roughly 37–39% | Diagnostic only |

All policies except the opt-in source gate are program-specific generated-C
experiments in `short_loop_policy.py`. They depend on known helper names and field
positions and must not be described as compiler recognition. In particular, the
call-site macro can repeat argument expressions: it is suitable only for this
harness's pure scalar arguments, not general compiler lowering.

In the known-state call-site comparison, all three inspected `_main` bodies
(original, constant-region, call-site) had no remaining calls to spin helpers.
Their assembly sizes differed (460 versus 253 lines). This points toward changes
in inlining, loop optimization, or code layout as investigation targets; it does
not identify a proven backend cause or invalidate the harness.

## Benchmark confidence and limits

`short_loop_sweep.py` checks complete result checksums against an independent
scalar oracle and takes paired forward/reverse samples after warmup. `--stable`
uses longer batches (up to 2^24 calls) and normalizes times to 2^20 calls.
`--independent` uses disjoint low 17 seed bits for source offset, length, budget,
and exceptional state, covering their joint period uniformly. This is a controlled
deterministic distribution, not a random sample of real applications.

The full matrix has 58 rows (55 distinct cases, including repeated controls):
fixed and varying lengths, reject-all/accept-all/partial predicates, fixed and
varying budgets, and zero-count/stopped-inner states. Early correlated sweeps
(`short-policy-screen`, `short-policy-broad`, `short-policy-stable`) understated
regressions and are retained as investigation history. Use the independent
reports for decisions. `--known-budget 32` makes the active state constant while
leaving source lengths dynamic; its 27 distinct rows expose another failure mode
that the wholly unknown-state constant-policy sweep missed.

## Validation

- Actual source-gate output equals its C diagnostic; ungated control output equals
  the earlier loop experiment on all four full/early benchmark sources.
- Source-gate validation covers 400,000 complete driver states and event traces,
  plus 400,000 injected callback-failure cases with UBSan.
- Five compiler fixtures cover reordered/renamed inputs (400,000 states), refusal
  of noninductive/second-step candidates, checked overflow, unchanged JS, and
  device-selected fallback compiled and run on CPU. They do not test GPU hardware.
- All 16 library tests pass; map-only timed assembly remains identical.
- Final re-emission matches four measured benchmark artifacts and 216 upstream
  native/JS artifacts from the previously runtime-tested suite byte for byte;
  50 interpreter cases were rerun successfully. The 216 binaries were not rerun
  at this final checkpoint.
- Lazy and lazy-plus-gate diagnostics each pass 400,000 normal and 400,000 failure
  cases. Each also passes 33 controlled polling-boundary cases, checking callback
  and polling counts/order and failures around 4096-step boundaries. This is not
  a test of real asynchronous cancellation or GPU execution.

Raw evidence is in `source-gate-*.json`, `lazy-policy-*.json`, `lazy-gate-*.json`,
`constant-policy-*.json`, `constant-region-*.json`, and `callsite-policy-*.json`.
Reports retain artifact paths and hashes; temporary artifact directories must be
regenerated if no longer present.

## Reproduction

Prepare the isolated compiler and validate its recognition:

```sh
python3 bench/compiler/prepare_guarded.py --loop --source-gate --output-dir /tmp/bend-source-gate-check
python3 bench/compiler/test_auto_loop.py --bend-main /tmp/bend-source-gate-check/main.ts --source-gate --output /tmp/source-gate-fixtures.json
python3 tests/run.py --bend-main /tmp/bend-source-gate-check/main.ts
```

Use `ablate.py --automatic-loop --automatic-compiler <prepared-main>` to create fresh
benchmark artifacts (see `ablate.py --help` and [AUTO-LOOP.md](AUTO-LOOP.md)).
`--entry-compiler <ungated-main>` adds the comparator; `--policy-variants` adds
selected C diagnostics. Feed a fresh ungated automatic-loop report to the sweep:

```sh
python3 bench/compiler/short_loop_sweep.py --report <report.json> --full --stable --independent --variants original entry source_gate lazy --output /tmp/independent.json
python3 bench/compiler/short_loop_sweep.py --report <report.json> --full --stable --independent --known-budget 32 --variants original constant_region callsite_const --output /tmp/known-state.json
```

## Priorities when work resumes

| Next step | Impact | Effort | Priority |
| --- | --- | --- | --- |
| Reduce the known-state/dynamic-length regression and inspect backend optimization differences | Explains the remaining promotion blocker | Medium | First |
| Derive a caller-aware profitability restriction from that evidence | Could preserve wins while limiting regressions | Medium/high | After diagnosis |
| Automate lazy switching | More semantic machinery without a broad measured win | High | Defer |
| Production enablement or API specialization | Current evidence does not justify it | High risk | Defer |

The work is paused at this checkpoint. A general short-loop fix remains unresolved.
