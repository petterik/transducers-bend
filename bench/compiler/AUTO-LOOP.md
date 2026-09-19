# Automatic bounded loop specialization

Latest checkpoint: [short-loop profitability](SHORT-LOOPS.md). Independent input
variation and known-state callers expose regressions beyond the original
one-element case. The optional source gate is experimental; default behavior
remains unchanged and work is paused.

## Result and decision

The next milestone from [STRATEGY.md](STRATEGY.md) is implemented in an isolated
compiler. It discovers the scalar loop and helper chain, derives the entry guard
and state feedback from typed terms, proves preservation, and emits scoped native
clones. The public pipeline, Source/Reduction API, production library and sibling
compiler are unchanged. There is no generated-C recognition or rewriting in this
pass; emitted C is inspected only by test harnesses.

**Keep the pass experimental.** Full and early ranges reach handwritten performance
locally, and frequent exceptional entry states no longer repeatedly call an
outlined fallback. Dynamic one-element loops still show a cost. Literal zero/one
countdown callers use the generic loop at compile time, but that is not a complete
profitability policy.

## What the compiler proves and emits

`prepare_guarded.py --loop` integrates `guarded_scalar.inc.ts` and
`guarded_loop.inc.ts` into a copy of the pinned sibling `comp.ts`. `bend.ts` is
copied unchanged. Without `--loop`, the earlier outlined-scalar experiment remains
available.

The scalar analyzer first records a pure transition summary. In loop mode it
leaves the original helper unchanged. A candidate loop must have one self-call
site, scalar inputs and outputs, one reachable summarized transition, and a bounded
direct helper chain. The analyzer follows typed bindings and constructor layouts;
opaque scalar calls produce unconstrained symbolic values. Their actual operations,
failures and ordering remain in the emitted loop.

Every specialized step call must receive the same guard from unchanged entry
scalars. The analyzer substitutes each back edge's actual arguments into that
guard and into the paths by which the next iteration can reach the step. It proves:

```
entry guard + current path + next iteration reaches step
    implies next step guard
```

A driver may recur with an outer Stop and return immediately next time. That
back edge does not need to preserve a guard for an unreachable step. Neither tag
numbers nor state field positions are assumed. Recursive erasure layouts must
also agree. Unknown mappings, non-preserving transitions, additional back edges,
boxed layouts, and exhausted analysis budgets retain original lowering.

The emitter then produces an entry wrapper, the original loop and a fast loop.
It re-emits the typed helper chain in a separate native-cache context; only the
pure summarized transition is replaced with its proven expressions. Unrelated
calls retain the original helper. Context is suspended when emitting ordinary
dependencies, so an on-demand dependency cannot inherit a fast shared callee.
Original loop polling, callback ordering, failures and state updates are retained.

A scalar Nat argument that decrements on every back edge can identify trivial
callers. If its typed argument is literally zero or one, the call uses the generic
loop directly. No runtime size test is added. Device-selected aliases resolve to
the original helper; the specialization is CPU-only and JS remains unchanged.

Work limits per emission pass: 64 attempted loops, 16 accepted loop contexts,
6 scoped helpers per context, graph depth 8 / bounded graph size, scalar input
width 12 and return width 8, interpreter fuel 3,000 and proof fuel 60,000. Existing
scalar expression, depth and leaf budgets also apply. These are implementation
bounds, not compile-time or object-size guarantees.

## Measurements

Apple Clang 17, `-O3`, sequential CPU. Ten retained samples per row after warmup,
forward/reverse order. Milliseconds per benchmark batch; compare within each row.
Every batch passes an independent checksum oracle.

| Workload | Original compiler | Automatic loop | Handwritten |
| --- | ---: | ---: | ---: |
| Mixed full range | 344 | **91.5** | 95 |
| Predictable full range | 51 | **30** | 34 |
| Mixed early stop | 139 | **99.5** | 104 |
| Predictable early stop | 26 | **16** | 17.5 |

[Full measurements](auto-loop-results.json), [early measurements](auto-loop-early-results.json).

The [complete-driver stress sweep](auto-loop-fallback-results.json) uses one million
reductions per sample and a runtime threshold rejecting every element. With 32
source elements and 100% zero-count entry states, original/automatic medians are
18.53/13.24 ms; with stopped-inner entry states they are 18.12/13.95 ms. There is
no repeated outlined-helper fallback in this mode.

Most one-element rows cost approximately 1.06–1.09 ms originally and 1.33–1.36 ms
automatically per million reductions: roughly 25% slower, or 0.27 ns more per
reduction in this harness. One initial row differs; do not extrapolate a universal
fixed cost from this microbenchmark. The runtime length in this sweep bypasses the
literal-caller policy, intentionally exposing the remaining dynamic-short cost.

The final compiler includes extra context isolation and recursive-erasure checks
added after timing. It reproduces **byte-identical C for all four measured cases**;
[the re-emission report](auto-loop-final-equivalence.json) records both compiler
hashes and emitted-code hashes. Timing is not represented as a fresh run of a
different binary.

The [compile-cost sample](auto-loop-compile-cost.json) measures Bun startup plus C
emission, with eight retained alternating-order samples. Original/automatic medians
were 109.5/132.5 ms for mixed and 111.9/124.4 ms for predictable sources. Emitted C
increased by 6,321 bytes per case, including the retained device fallback. Complete
native file sizes were equal in this sample; runtime size/alignment can hide code
growth, so this is not an object-code-size guarantee.

## Correctness and compatibility evidence

- [Actual compiler-emitted range loops](auto-loop-validation.json): 400,000 complete
  driver-state comparisons against their untouched generic copies, including
  ordered source/mapper/predicate argument fingerprints, under UBSan.
- [Injected callback failure returns](auto-loop-failure-validation.json): another
  400,000 comparisons of success/failure and event ordering. Failed calls do not
  compare uninitialized output buffers.
- [Reordered layouts and callers](auto-loop-fixtures.json): another 400,000 driver
  states under UBSan; changed type names, field order, parameter order and inner
  tag numbering; shared generic helper remains byte-identical; literal-one callers
  select generic lowering. A deliberately non-inductive transition is refused for
  that reason. A second step with an unavailable entry guard is also refused.
- A real checked Nat overflow outside the pure transition still fails identically
  while the enclosing loop specializes. JS output is byte-identical for all five
  dedicated fixtures. Selecting this pass's device fallback and compiling it with
  the CPU runtime checks conditional declarations and aliases; this is **not** GPU
  execution coverage.
- [Library suite](auto-loop-library.json): 16/16 on native/JS, including lifecycle, completion, ordering,
  ownership and source/mapper count checks.
- [Upstream local gate](auto-loop-upstream.json): 216 native/JS passes plus 50
  interpreter-only passes across base, compile, flatten, reg and state. None
  activates the new loop rule; these are compatibility checks, not new-rule
  coverage. The final compiler re-emits identical C **and** JS for all 216 and
  reruns all 50 interpreter cases. One unchanged C test still needs the existing
  `-fbracket-depth=4096` workaround on this Clang.
- [Map-chain assembly](auto-loop-map-parity.json): three maps, one combined map and
  the original compiler retain identical timed-function assembly.
- The refactored outlined-scalar mode also passes its [400,000-state gates and
  checked-failure tests](auto-loop-scalar-regression.json), and the existing
  [3.2-million-state adversarial suite](auto-loop-adversarial-regression.json).

The 1.2 million driver comparisons are sampled differential checks, not an
exhaustive or mechanized proof of compiler correctness. The official distributed
upstream gate and actual GPU compilation/execution have not been run.

## Remaining priorities

| Priority | Work | Impact | Complexity / decision |
| --- | --- | --- | --- |
| 1 | Dynamic short-loop profitability and broader workload distribution | High: current promotion blocker | Medium; measure caller strategies before adding runtime branches |
| 2 | Broader caller shapes and independent proof/emitter review | High correctness confidence | Medium–high; retain conservative refusal for now |
| 3 | Actual backend gates and broader owned sources | Required for broader promotion | High ownership/backend obligations; scalar CPU scope remains explicit |
| 4 | Per-step bailout | Possible coverage beyond inductive loops | Medium–high; backup only, no demonstrated need to build it now |
| 5 | Whole-program state inference or public API changes | No demonstrated incremental need | Defer |

Confidence is high in the measured scalar-range result and stronger than the
previous program-specific diagnostic in automatic recognition and shared-helper
isolation. It is insufficient for universal enablement or claims about arbitrary
sources/backends.

## Reproduction

Run timings sequentially, without concurrent builds or benchmarks. Preparation
prints the isolated `main.ts`; substitute that path below.

```sh
python3 bench/compiler/prepare_guarded.py --loop --output-dir /tmp/loop-candidate
python3 tests/run.py --bend-main /tmp/loop-candidate/main.ts
python3 bench/compiler/test_auto_loop.py --bend-main /tmp/loop-candidate/main.ts --output /tmp/fixtures.json
python3 bench/compiler/upstream_local.py --bend-main /tmp/loop-candidate/main.ts --output /tmp/upstream.json
python3 bench/compiler/ablate.py --automatic-compiler /tmp/loop-candidate/main.ts --automatic-loop --samples 5 --output /tmp/full.json
python3 bench/compiler/ablate.py --automatic-compiler /tmp/loop-candidate/main.ts --automatic-loop --early --samples 5 --output /tmp/early.json
python3 bench/compiler/test_loop_version.py --report /tmp/full.json --automatic-loop --output /tmp/driver.json
python3 bench/compiler/test_loop_version.py --report /tmp/full.json --automatic-loop --inject-failure --output /tmp/failure.json
python3 bench/compiler/loop_fallback.py --report /tmp/full.json --automatic-loop --samples 3 --output /tmp/fallback.json
```

`check_map_parity.py` accepts `--bend-main`, a `--composition-report` produced by
`bench/composition.py`, and `--output`. `check_loop_reemission.py` records exact C/JS
equivalence against retained benchmark/upstream artifacts after compiler hardening.
`measure_loop_cost.py --bend-main ... --report /tmp/full.json --output /tmp/cost.json`
records emission timing and file sizes. Use `BEND_LOOP_REPORT=/tmp/proofs.jsonl` to record accepted guards, caller selection
and local-proof refusal reasons; `BEND_GUARDED_TRACE=1` adds debugging diagnostics.
