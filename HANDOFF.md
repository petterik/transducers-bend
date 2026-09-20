# Hand-off: Bend transducers

## Checkpoint 2026-09-20: boxed List source loop and parity matrix

This checkpoint is committed as `c868553`. It extends the isolated
typed loop experiment so a closed list transduction can reach the scalar fused
transition while retaining the original generic list traversal as fallback. The
public API and `../bend` checkout remain unchanged.

The remaining gap was caused by the source driver carrying one boxed recursive
List value. The loop-carried reducer state was already scalar after layout
lowering; the experiment rejected the whole helper merely because its first
source argument was boxed. `guarded_scalar.inc.ts` now admits exactly that shape
in loop mode, models the initial boxed source match through typed constructor
fields, and analyzes only the scalar state transition. `guarded_loop.inc.ts`
uses the same narrow signature boundary. Open matches, extra boxed state or
returns, multiple recursive sites, unsupported callbacks, and unproved paths
still fall back unchanged.

The new positive gate is
`bench/compiler/fixtures/list_transducer.bend`, exercised by
`bench/compiler/test_list_driver.py`. The candidate emits one `guarded_loop`
region for it, no `Clo.apply`, and the original compiler emits none. The fixture
passes native execution with `0:0:495:2820030815`.

Validation completed:

- `python3 tests/run.py --bend-main /tmp/transduce-next-candidate/main.ts` — 18/18.
- `python3 bench/compiler/test_auto_loop.py --bend-main /tmp/transduce-next-candidate/main.ts --output ...` — all five cases pass.
- `python3 bench/compiler/test_guarded.py --bend-main /tmp/transduce-next-scalar/main.ts --output ...` — scalar fallback and UBSan gates pass using the non-loop candidate.
- `python3 bench/compiler/adversarial.py --bend-main /tmp/transduce-next-candidate/main.ts --output ...` — all 16 refusal/state variants pass.
- `python3 bench/compiler/test_list_driver.py --bend-main /tmp/transduce-next-candidate/main.ts --output ...` — boxed List source gate passes.
- Five-sample candidate composition run: three maps 13/13 ms, cheap full 10/10 ms, mixed full 14/14 ms, mixed early 40/41.5 ms (transducers/direct). The mixed full C has one `guarded_loop` region and no `Clo.apply`.
- Runtime-threshold mixed range check: candidate/direct 85/88 ms full and 42/44 ms early, with one guarded loop and independent output checks.
- `bench/fusion_parity.py` matrix: mixed full 15/15 ms, mixed take-one 36/38 ms, mixed take-32 35/38 ms, and expensive take-32 36.5/37 ms (transducers/direct); dynamic short and zero/one-element rows pass correctness but are below timer resolution.

### Handoff for the next session

1. Verify this commit and a clean tree. Prepare a fresh isolated `--loop`
   candidate; do not reuse an old `/tmp` compiler directory for final evidence.
2. Rerun the 18-test gate, `test_auto_loop.py`, `adversarial.py`,
   `test_list_driver.py`, and the five-sample composition control.
3. Inspect the mixed full generated C and assembly. Confirm the fast wrapper is
   guarded by the typed state conditions and the generic list helper remains
   available for the fallback path.
4. Extend `bench/fusion_parity.py` with three-map, type-changing, range and
   other source cases, then calibrate repetitions so timed rows exceed 100 ms.
   Add the balanced 20-block, two-session run and paired-bootstrap interval from
   `FUSION-EXECUTION-PLAN.md`, including short, runtime-threshold, zero/one/
   max-count, and irregular-selectivity cases.
5. Exercise other boxed recursive sources and boxed reducer states. They should
   refuse the loop specialization and retain identical semantics. Do not widen
   the source exception until those negative cases are explicit.
6. Only after the candidate scope is complete, run the original compiler as the
   final comparison. GPU/CUDA and production compiler promotion remain separate
   gates; the generated host guard deliberately leaves device code unchanged.

## Checkpoint 2026-09-19: static list driver

The current target is unchanged: a closed `transduce` pipeline should compile
to the speed of an equivalent handwritten fused Bend traversal. Ergonomic
syntax, lazy `sequence`, `eduction`, arbitrary runtime captures, and a generic
`into`/`conj` interface are deferred. The immediate execution model is
`transduce`; ownership remains local to the run.

This checkpoint adds `T.reduce_list_static` in `transduce.bend`. It binds the
reducer as a template parameter and calls `step` directly from the recursive
list loop. `T.reduce_list` remains unchanged for source adapters that need a
runtime advance function. `T.cat` and `T.over_list` now use the static driver,
so closed list pipelines no longer build an affine advance closure for every
element. The change is semantics-preserving and leaves range/string/array
drivers untouched.

Validation completed before sign-off:

- `python3 tests/run.py --bend-main /tmp/bend-fusion-parity.5vo6VS/candidate/main.ts` — 18/18 tests pass on candidate JS/native lanes.
- `tests/static_driver.bend` exercises filtering, taking, stopping and sum through `over_list`.
- Candidate C for that fixture contains no `Clo.apply` occurrence.
- Five-sample candidate composition run: three maps 13/13 ms (transducer/handwritten); cheap full 11/10 ms; mixed full 44.5/14 ms; mixed early 38/38.5 ms. These are short engineering samples, not final acceptance measurements.

The static driver is a useful foundation, but it does **not** meet the final
performance target for mixed list map/filter/take. The remaining cost is the
scalar `Control`/`Taking` state protocol and helper transitions in the list
loop. Do not report parity from this checkpoint.

### Handoff for tomorrow

1. Start with `git status --short` and verify the checkpoint commit before editing. Keep `../bend` unchanged; candidate compiler work belongs in an isolated copy made by `bench/compiler/prepare_guarded.py`.
2. Re-run the 18-test candidate gate and preserve the five-sample composition artifacts under `/tmp`. Compare only candidate transducer versus candidate handwritten lanes during development.
3. Inspect `/tmp/bend-source-test/mixed.c` or regenerate it with the current `transduce.bend`. The static list loop is one native loop, but it still calls the nested typed transition chain. The direct loop carries only scalar `left`, `sum`, and its stop condition.
4. The next compiler experiment should be typed and general: expose/fuse the nested scalar transition only when layouts, ownership, totality and callback evaluation order are proved. Do not recognize transducer names, numeric tag positions or generated-C text. Preserve generic fallback and all valid stopped/zero states.
5. Existing experimental machinery is in `bench/compiler/guarded_scalar.inc.ts` and `guarded_loop.inc.ts`; it is not production compiler code. The guarded-scalar pass currently handles bounded pure scalar regions and has intentionally conservative fallback rules. Any promotion needs focused differential tests, checked-failure tests, code-growth limits, and a benchmark against direct Bend.
6. Do not compare with the original compiler until the candidate implementation is complete, as requested. Final acceptance still needs balanced retained blocks and the direct-lane tolerance in `FUSION-EXECUTION-PLAN.md`.

Scratch files from diagnosis (`experiments/*`, `transduce_static.bend`, and
`bench/__pycache__`) should stay untracked and be removed before the final
delivery if they are still present. No external branch or compiler checkout
has been modified by this checkpoint.

## Priority #3 follow-up (supersedes the original hand-off below)

The user authorized priority #3, confidence/prioritization reviews, and explicit laws with bounded executable checks. They rejected separate source drivers and then a closed Source enum in favor of an extensible reduction interface. The implemented API is `transduce(~reduction, config, source)`, where `over_list`, `over_range`, `over_string`, or a third-party adapter binds the user's pipeline once into a static Reduction description. `examples/tree.bend` adds an affine tree without changing the library. Source selection is explicit and static; ordinary source data remains runtime. See EXTENDING.md for the `reducible` binding helper and stopping-fold contract.

Range, ordered affine into_list, and Nat count are implemented. Ranges use ascending half-open U32 bounds with step 1; reversed/equal bounds are empty and endpoints never wrap. Strings yield Char. Twelve test files pass JS/native, including 18,750 bounded law assertions per backend, reusable source conformance checks, affine external-tree tests, and JS source/mapper/lifecycle counts. Representative fixtures eliminate Reducer and Reduction records. LAWS.md records non-mechanized arguments and remaining proof work.

The binding delays its reducer recipe (`~(u => r)`) and type metadata to stay within the existing compiler specialization budget. Direct pattern-matching callbacks in custom Reducer fields may retain runtime records; forwarding lambdas work with the current pass. No compiler changes were made. The actual compiler remains `../bend/bend2/main.ts`; a temporary debugging copy lacked effs/print.js, which was unrelated to the library. Final tests/benchmarks use the sibling checkout.

`python3 bench/range.py` measures generated ranges against handwritten traversal; bench/RANGE.md and range-results.json retain the final report. Cheap work shows overhead (49 vs 33 ms for the full batch); expensive work ties at the timer's resolution. Prior compiler full-gate gaps remain, and no new range GPU validation or formal library-law proof was performed. Check git status: this follow-up is uncommitted unless the user has subsequently committed it. Nothing was pushed.

## Original hand-off (historical)

The user is exploring efficient pure-data transducers for Bend, inspired by Clojure but adapted to Bend's ownership and explicit parallel execution. They prefer pragmatic performance and allow future bounded speculative work; never evaluating an unnecessary element is not a universal requirement. They authorized implementation priorities #1 and #2 and compiler specialization when necessary. Those are implemented and measured. Priority #3 has not yet been requested for implementation.

The latest request was to commit the work and prepare this hand-off. All current implementation/benchmark work is committed locally; nothing has been pushed. There is no running benchmark or unfinished implementation task. Ask what to pursue next if no new instruction accompanies this hand-off.

Read README.md for the actual API, IMPLEMENTATION.md for compiler details and validation, and bench/PARALLEL.md for CPU/GPU evidence. DESIGN.md, CONFIDENCE.md and PRIORITIES.md record earlier decisions; where their original scope excludes compiler changes, the later explicit user authorization supersedes that restriction.

## Repositories and commits

- Library: `/Users/petter/Github/petterik/transduce-bend`. The initial implementation is commit `b975f1d`; this hand-off is included in the subsequent benchmark/documentation commit (use `git log` for its hash).
- Compiler dependency: [petterik/bend](https://github.com/petterik/bend), branch [`petter/transducers-sept-19`](https://github.com/petterik/bend/tree/petter/transducers-sept-19). Local checkout: `/Users/petter/Github/petterik/bend`, commit `b1f9c936` (`Specialize statically constructed callbacks before lowering`). The library's performance/codegen expectations require this experimental patch.
- Bend's AGENTS.md explicitly prohibits editing `bend2/bend.ts`. It remains unchanged. Compiler/runtime work belongs in `bend2/comp.ts`.
- Read both repositories' current status before editing; the user sometimes commits between turns. Do not overwrite their changes.

Bend here is version 2.0.16-era dependent/affine Bend, with a strict CPU/GPU fork-join compiler/runtime. It is not the older interaction-net/HVM2 language originally discussed. `bend guide` and `bend guide shaders` explain the current model. Use the source checkout via `bun ../bend/bend2/main.ts` when testing this patch, not an unrelated installed compiler.

## Implemented representation and semantics

`transduce.bend` uses a static `Reducer<A,R>` description carrying configuration/state types and start/step/finish callbacks. Templates receive closed syntax (`~`); runtime settings travel explicitly in configuration. Closures are affine, not freely reusable.

- `Control<S>` is Continue or Stop, owning S.
- The sequential list driver starts once, steps until source exhaustion or Stop, and completes once on either path.
- Adapters: identity, map, map_with, configured filter, take. Consumers: sum and reducing; custom consumers can construct Reducer directly.
- Composition nests adapters or uses a reusable template accepting a downstream reducer. There is no runtime compose builder.
- Consumer initialization is part of configuration, not a separate transduce accumulator argument.
- Filter requires Data elements because it inspects then retains them; mapping and accumulators can be affine.
- Take retains downstream Control, distinguishing upstream truncation from downstream stopping. Completion may flush after upstream truncation, but must honor downstream Stop.
- Buffered operations exist only as protocol test fixtures, not public adapters.

No range driver, into_list, count convenience, mapcat, public buffering, IO driver, or general parallel collection driver has been added. No explicit `@unsafe` was added to the library. Bend reports generated template specializations as unsafe annotations; passing tests is not formal proof.

## Compiler patch

Without specialization, the static reducer representation rebuilt/projected callbacks in the hot path; the first simple experiment was roughly 2x a direct loop. The patch resolves statically constructed function heads before shared JS/native lowering.

It uses bounded call-by-value evaluation, refuses unsafe/foreign/intrinsic/dynamic/parallel producers, requires saturated named producers, and binds dynamic arguments once. Unsupported expressions fall back to runtime calls. Evaluation fuel is 2048, with 256 successful rewrites per definition. Ordinary bare named calls are not universally inlined.

Two important regression lessons: partially applied recursive functions must not be expanded indefinitely; a Let-headed application must preserve evaluation order and typing when hoisted. The existing over_application test exposed the latter during development. Reifying the transformed term once avoids consuming a mutable rewrite budget differently on subsequent emitter visits.

This is an experimental bounded specialization pass, not general collection fusion or a checker/theory change. Arbitrarily complex pipelines are not guaranteed to optimize completely.

## Validation already performed

- Six library Bend tests pass emitted JS (Bun) and native execution. They cover stage ordering, stopping/initial stopping, state freshness, affine ownership/type changes, completion/flush behavior and rejected affine filtering.
- Generated JS checks eliminate Reducer records and instrument nine expected mapper calls across the pipeline cases.
- Five compiler regression files cover static records, captures/dynamic fallback, parallel and unsafe producers, and strict evaluation of an unused computed field.
- 225 selected positive Bend tests from compile/reg/base/comptime passed locally on Bun and native `--threads 1 --gpu off`. GPU-marked programs compiled. This was a local selection, not the full official gate.
- Strict TypeScript checks passed for compiler and CLI. The full configured project lacked canvas types used by existing documentation generators.
- Official cluster tests could not run because SSH hostname `cluster` was unresolved. Repository-size gate could not run because `ttok` was missing. These are unresolved validation gaps, not passes.
- Later actual Metal benchmarks validated every output across CPU threads 1/2/4/8/16 and GPU execution. This validates the measured pipelines, not every lifecycle test on GPU or CUDA.
- Diff whitespace checks passed. No code changed during the benchmark follow-up; only benchmark artifacts/docs were added.

Useful commands from the library directory:

```sh
python3 tests/run.py
python3 bench/run.py
python3 bench/parallel.py
```

The scripts accept `--bend-main`. See bench/PARALLEL.md for focused sweeps. Run benchmarks sequentially to avoid self-contention. The GPU suite requires a native Metal/CUDA build toolchain even when `--no-gpu` skips device execution. It sets a writable Clang module cache. Actual GPU runs use `--gpu 1GB`, which requires a device rather than silently falling back.

## Performance findings to preserve

Machine: M3 Max, 16 CPU cores, 40 GPU cores, 128 GiB unified memory. The CPU/GPU runner measures inside a persistent process using millisecond IO.now, excluding startup but including source construction and cleanup. The older bench/run.py includes process startup, so its times are not directly comparable.

- Balanced 16,384-list batches, full consumption, 256 arithmetic rounds per map: library 392 ms on one CPU thread, 100 ms on four, 51 ms on eight, 36 ms on sixteen. Handwritten traversal closely matches.
- GPU-only heavier mapping (16,384 arithmetic rounds): full batch 52 ms library vs 53 ms handwritten vs 54.5 ms materialized. Early take: 7 ms library/handwritten vs 50 ms materialized.
- One long list remains sequential regardless of thread count. Moving it to GPU is much slower: full control 38 ms CPU vs 577 ms GPU for the library.
- Cheap mapping exposes owned-tail cleanup: for 256-element lists, full CPU-one-thread library median 10 ms, but take-eight 35.5 ms. The handwritten version also slows. Generated code sinks the unused tail generically; full traversal frees nodes directly. Fewer mapper calls do not guarantee lower wall time.
- GPU jobs are independent reductions with per-leaf take/state. They are NOT a correct implementation or benchmark of global ordered parallel take.
- Noise and timer quantization are documented. An anomalous two-thread block was retained and repeated: repeat medians 29 ms library vs 30 ms handwritten. Do not claim universal or exact-percentage speedups.
- No peak-memory/allocation profiling, CUDA runs, divergent/imbalanced workload study, or formal equivalence proof was performed.

Keep the checked-in bench/*.json snapshots: they are small, linked evidence, including noisy samples. Do not blanket-ignore them. New generated artifacts default to /tmp; if local scratch outputs are later placed in the repository, ignore a specific scratch directory instead of all JSON.

## Recommended next work, if authorized

Priority #3: a finite generated range source using the same reducer protocol, ordered into_list, count consumer and concise examples. The range source is especially valuable now because it can avoid constructing and disposing of an unused list tail.

Before implementing range, settle finite bound/step semantics and overflow behavior. Verify no production after initial/mid-run stopping, no bound wrap, and identical transformation results across list/range sources and scalar/collection consumers. Preserve completion exactly once and affine ownership. Do not weaken the protocol to make an example compile.

Keep general parallel drivers deferred until ordering, reducer combination, stateful stages and stopping across partitions have explicit semantics. Existing results justify fusion inside independent branches; they do not settle those design questions. The compiler patch still needs the normal project gates when infrastructure is available.
