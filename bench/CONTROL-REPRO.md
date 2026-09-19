# Standalone control-state reproducer

[The historical API comparison](API-REGRESSION.md) establishes that this control-flow limitation predates the range/source API; the old and current mixed-list loops produce identical timed-loop assembly.

The mixed-filter gap reproduces without the transducer library, templates, callbacks, runtime configuration wrappers, or nested control tags. [control-repro.bend](control-repro.bend) imports only Base. It reduces a generated range with the same mapping and three-round predicate used in [the runtime-filter investigation](RUNTIME-FILTER.md).

```sh
python3 bench/control-repro.py
```

The runner prints an artifact directory and retains Bend, JS, native C, executables, and a JSON report there. It reads the predicate threshold from IO.args outside the timed region. Compile the emitted `direct.c`, `tagged.c`, or `guarded.c` with `clang -std=c11 -O3 -S` to inspect native assembly. These assembly observations are specific to the local Apple ARM64 toolchain.

## Reduction and result

Only scalar `State{left: Nat, sum: U32}` is needed. The original four variants are:

- `direct`: exits by matching the remaining count in State; no explicit stop tag.
- `tagged`: carries `Continue{State}` or `Stop{State}` between iterations. Converts the updated State to Control after merging the accepted/rejected paths.
- `split`: carries the same tag, but converts to Control only on the accepted path, as a filtered stopping reducer does.
- `guarded`: same tag and step as `tagged`, plus an explicit zero-count exit before stepping. This restates an invariant that already holds for executions initialized with `control(State{left, 0})`.

Whole-batch medians on the local M3 Max, 32 repetitions of two million inputs, runtime threshold 2,147,483,647:

| Variant | Median |
| --- | ---: |
| Direct scalar state | 93 ms |
| Tagged, control after merge | 328.5 ms |
| Tagged, control in accepted arm | 330.5 ms |
| Tagged with explicit count guard | 96 ms |

[Raw results](control-repro-results.json) retain fourteen samples per variant, seven after one discarded warmup per process, with variant order reversed in the second round. Runs were sequential, CPU threads=1 and GPU off. Every batch matched the independent Python oracle checksum 3,358,576,704. Source and compiler hashes are recorded. Timing resolution is milliseconds, not single-call latency.

Seven small cases per variant also passed both JS and native execution against the oracle: empty input, zero take, take one, early stop under mixed filtering, exhaustion with oversized take, and all-rejected input. These test returned results for the scalar reproducer; they do not prove arbitrary reducer lifecycle or callback-trace equivalence.

## What the native code shows

The unguarded tagged loop branches on the mixed predicate (`cmp` followed by `b.ls`). The guarded loop instead uses `cset` and `csinc` to choose scalar updates, then computes the next stop tag from the new count. The tag is still present: removing all tagged state is not necessary to recover performance in this case.

The key source difference is the added case before the recursive step:

```bend
case 1n+p Continue{State{0n, sum}}:
  sum
case 1n+p Continue{State{1n+k, sum}}:
  guarded(p, (x + 1 : U32),
    tagged_step(threshold, State{1n+k, sum}, mapped(x)), threshold)
```

The unguarded variant matches only `Continue{s}` there. For reachable states, Continue implies a positive count: initialization and each control conversion map zero to Stop. The explicit guard exposes count information at the loop body that the optimizer does not recover from the tag alone. Its presence enables substantially better control flow in the observed code. This is a compiler-optimization lead, not a proof of which internal LLVM pass is responsible or a hardware branch-misprediction measurement.

A separate scratch C experiment removed only the checked Nat reconstruction inside the tagged variant's `control` helper. It did not recover performance (roughly 335–339 ms versus 325–331 ms with the check). No such unchecked code is retained. Removing the check alone is therefore not a sufficient fix in this reproducer.

## Safety boundary and next step

This is an optimization reproducer, not a proposed change to generic Control or take. Its guard is justified only for the reachable states constructed here. Generic Continue has no positive-count invariant: sources and arbitrary reducers do not expose a take count, and nested adapters must preserve downstream Stop and completion semantics.

The next investigation can focus on exposing or deriving valid scalar-state facts during specialization/lowering, using this reproducer as the acceptance case. It must preserve checked arithmetic and evaluation behavior. In particular, turning a filter into unconditional downstream execution is invalid for arbitrary affine, stopping, or potentially failing callbacks. No library or compiler implementation changed in this investigation.

## Compiler experiment: a guard is not enough

After committing the original reproducer, a compiler prototype was tested in an isolated copy of the sibling compiler, including its effect files. The sibling checkout and `bend2/bend.ts` were not edited. The [rejected experimental patch](case-split-experiment.patch) is retained for reproducibility, **not for installation**: it is an unreviewed heuristic, not an accepted optimization.

At native scalar-record binding sites, the experiment split zero and nonzero values of one numeric field in a small unboxed record. The zero arm substituted literal zero; both arms emitted the original body. Splitting was bounded to once per emitted segment. This avoids asserting that zero is unreachable or skipping user computation. Initial medians were 335 ms for tagged versus 91.5 ms direct. Adding a branch-likelihood hint still measured 334.5 ms tagged versus 92.5 ms direct. Neither variant recovered conditional-selection performance. No compiler patch was promoted.

The fifth standalone variant, `preserving`, makes the same distinction in Bend source: its zero arm performs the original step and recursive call, unlike `guarded`, which exits. A seven-sample/two-round rerun produced:

| Variant | Median |
| --- | ---: |
| Direct | 94 ms |
| Tagged | 328.5 ms |
| Guarded early exit | 94 ms |
| Case split preserving the zero-state step | 342 ms |
| Split accepted arm | 331 ms |

[Raw follow-up samples](control-preserving-results.json) preserve the complete rerun. Every checksum matched and all five variants passed their small JS/native oracle checks. These results qualify the earlier inference: merely making the numeric fact explicit is not sufficient. The useful fast case also removes the zero-state continuation from the loop. The optimizer may need a proven reachable-state invariant or a proof that the zero-state computation can be eliminated; these experiments do not identify a particular LLVM pass as the cause.

`tests/zero_state.bend` is a counterexample to inferring such an invariant from record shape. Its custom reducer starts with `Continue{State{0n, sum}}`, then consumes one input and stops. List, range, and take-wrapped cases must preserve the input's contribution. Generic code must not silently replace that Continue with Stop.

Next work needs a bounded analysis of initialization and transition producers, with conservative fallback when callbacks are unknown or can return continuing zero states. Such analysis must cover all call sites (including externally callable helpers), preserve strict evaluation and arithmetic failures, and justify any eliminated path. This broader compiler pass is not implemented or validated here; the measured opportunity remains open.
