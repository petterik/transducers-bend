# Review of the design-plan implementation

Reviewed 2026-09-20, at `684c49a`, against the plan committed in `267c257`.

## Verdict

Accept the conservative tree refusal and retain the useful library additions,
fixtures, and measurements. Do not accept the claim that the design plan is
complete or the compiler architecture has been implemented. Most of its central
compiler work remains undone. This is a useful experimental checkpoint.

I found no new wrong-output failure in the checks rerun below. That is a narrower
statement than compiler soundness or completion of the planned acceptance matrix.
Confidence is high in the concrete findings below; finite tests cannot establish
literal 100% correctness.

## Findings, in priority order

### 1. High: completion claims substitute probes for the planned implementation

`DESIGN-WORK-PLAN.md:353` says packages 0–6 are complete. Its own package status
paragraphs say the implementation of static composition is deferred, the typed
region and summary API remain next, and representation work is only measurement.
The final handoff also presents packages 0–6 as completed.

The implementation diff confirms this discrepancy: the only change to existing
compiler implementation code after the plan is disabling `GL_ENABLE_TREE`.
There is no new static memoization boundary, callback normalization, typed region,
scoped summary interface, local representation rewrite, or optimization diagnostic
implementation. The scoped-facts fixture tests the pre-existing loop machinery.
The new probes are useful evidence, but do not satisfy those implementation tasks.

This matters because general optimization beneath ordinary reducer abstractions
was the central goal of the design. The architecture still depends on the same
bounded structural recognizers that the design proposed moving beyond.

Fix: mark packages 2–4 incomplete and restore their original acceptance criteria.
Implement one reduced static-composition improvement and one ordinary-code typed
region with explicit preconditions, value identity, and a positive rewrite, plus
refusal tests. It is reasonable to discover that an existing optimization already
eliminates a particular cost, but establish that with paired code inspection and
measurements rather than claiming a new pass is complete. Keep tree refusal until
its separate proof obligations are met; re-enabling trees is not the prerequisite
for finishing the first local region.

### 2. High: the native closure-dispatch checks cannot support their conclusion

`bench/compiler/representation_probe.py:59` counts the string `Clo.apply` in
generated C and line 65 asserts zero. `static_composition_probe.py:52` uses the
same measurement; the existing parity harness does too.

`Clo.apply` is the compiler's internal operation name. Native generated dispatch
uses `FID_CLO_APPLY`. Re-running the representation probe reports zero while the
buffered C contains five `WL_JMP(FID_CLO_APPLY)` sites, including `ADD_FUNCTION`
and `KEEP_CLOSURE`. This is a demonstrated false-negative metric.

Those examples include required calls to affine function values and IO; their
presence does not prove that reducer dictionary dispatch remains. It proves that
this check cannot distinguish absence of dispatch from its presence. Likewise,
whole-file allocation-call counts do not locate transient adapter allocations.
The report correctly qualifies allocation counts, but overstates callback removal.

Fix: examine generated functions or compiler call-graph diagnostics for the
particular reducer/traversal boundary, distinguishing IO and element callbacks.
Add a negative control with deliberately retained dynamic dispatch so the detector
must fail when the property is false. Keep JS record elimination as separate
evidence. Do not merely require zero `FID_CLO_APPLY` occurrences across a runtime
that legitimately contains a closure dispatcher.

### 3. Medium: the public buffered adapter lacks the required conformance matrix

`tests/keep_partition.bend:42` exercises useful full/partial groups, both orders
of take and partition, zero width, and affine inputs. However, no maintained test
of the new public adapter covers nested partitioning, empty input, downstream
initial stop, or a consumer returning Stop specifically during a partial flush.
The zero-width output check does not observe whether source callbacks ran.
There is no paired direct implementation for these new operations.

`tests/completion.bend` tests an older, separately implemented pair-buffer adapter.
It establishes useful protocol behavior, but cannot catch a regression in
`partition_finish` or the new partition state. The distinction is important for
owned buffered values and completion exactly once.

Fix: apply the plan's required cases to `T.partition_all` itself on List, range,
and the independent tree. Observe source steps and completion counts, including
initial stopping, nested completion, consumer stopping during flush, affine
discard paths, and fresh state across repeated uses of one description. Retain
small direct references. Publish semantic acceptance only after these pass.

### 4. Medium: the staging decision includes an invalid blocker and lacks a retained reduction

`bench/compiler/STATIC-COMPOSITION.md:27` cites a tree extension type error when
changing `reducible` to accept a reducer directly. It explicitly says the adapter
still supplied the old delayed recipe. This is an incomplete API migration, not
evidence that the eager form cannot support the source.

In a temporary copy I changed the recipe argument to `Reducer<A,R>`, replaced
`recipe(Unit{})` with `recipe`, and migrated both built-in adapters and the external
tree from `~(u => r)` to `~r`. `api_surface` and `keep_partition` both typechecked,
produced their expected JS outputs, and contained zero JS Reducer records.
The Array fixture also returned the correct outputs but retained three Reducer
records. That is a real code-generation limitation and still justifies caution.

Fix: retain a minimized Array reproducer and investigate its static-head resolution.
Remove the unmigrated tree failure from the architectural evidence. Compare matcher
and forwarding forms, repeated/deep specialization, evaluation order, and compiler
cost as planned. Keeping the delay temporarily is reasonable; this experiment does
not establish that the eventual language or library design needs it.

### 5. Medium: the API acceptance fixture avoids the configuration problem

`tests/api_surface.bend:9` proves that a one-stage, unconfigured transformation
can be reused with two consumers and several sources. It does not exercise the
planned simplification of nested settings. Every configuration in this fixture
is `Unit{}`, and callers still repeat result types. The library still has the
delayed recipe and two List drivers.

Fix: mark package 6 partial. Use a reusable, type-changing pipeline with multiple
configured/stateful stages and two consumers. Demonstrate typed configuration
construction and explain any remaining result-type plumbing. If Bend prevents
the desired surface, retain a reduced type-system example and record a design
decision rather than calling the existing surface stabilized by this fixture.

### 6. Medium: performance evidence does not cover the new extension claim

The retained five-row List benchmark has calibrated durations and its recorded
upper ratios are below 1.05. However, it contains no public `keep` or
`partition_all` versus equivalent direct-Bend row. Package 7 explicitly required
extension cases; package 4 required residual extension/direct comparisons.
The representation probe provides neither paired code attribution nor timings.

Fix: add a consuming type-changing keep case and a buffered partition case with
equivalent ownership, outputs, stopping, and required storage. Measure compile
cost/code growth as well as runtime. Keep current conclusions restricted to the
five measured List workloads. Device and full upstream gates remain outstanding
as already disclosed; those disclosures are appropriate.

## What meets expectations

- Tree specialization is conservatively disabled, and the permanent reproducer
  passes with arbitrary incoming controls. This follows the design's safety rule.
- `keep` and `partition_all` use the existing reducer lifecycle and require no
  source registry or operation-specific compiler branch. Inspection supports
  their basic ownership and upstream/downstream stopping design.
- The compiler candidate remains isolated and reproducible from a checked source
  hash. The sibling compiler was not changed by these worksets.
- The existing tests and timing artifacts are useful. Historical reports remain
  available, and unavailable GPU/upstream validation is explicitly acknowledged.

## Verification performed for this review

Fresh candidate preparation:

```sh
python3 bench/compiler/prepare_guarded.py --loop --output-dir /tmp/transduce-review-current
python3 tests/run.py --bend-main /tmp/transduce-review-current/main.ts
python3 review/check_tree_entry.py --bend-main /tmp/transduce-review-current/main.ts --output /tmp/transduce-review-tree.json
python3 bench/compiler/test_scoped_facts.py --bend-main /tmp/transduce-review-current/main.ts --output /tmp/transduce-review-scoped.json
python3 bench/compiler/representation_probe.py --bend-main /tmp/transduce-review-current/main.ts --output /tmp/transduce-review-representation.json
```

Candidate compiler SHA:
`01adea0f6ef5bf13f76cfb222cc563d879440f873ea0070c0629dcc19da7c32e`.
The suite passed 20/20; the tree probe returned `[9, 1000, 2000, 1017]` with zero
tree markers; scoped-facts candidate/reference native and candidate JS matched.
The representation probe reproduced its saved outputs and code sizes, including
the misleading zero closure-dispatch count. Generated C was inspected directly.

The eager migration experiment was JS-only and does not establish native parity
or justify changing the public API. The original library was not edited.
The saved timing report was checked for its five rows, 80 sample pairs per row,
duration floors, and reported intervals. Performance timings, the full upstream
suite, and device execution were not rerun. The core pre-existing optimizer has
not been exhaustively proved by this review.

## Recommended next worksets

1. Correct completion status and repair the generated-code detector with a
   negative control. Add the missing public-extension lifecycle tests.
2. Reduce the actual static-composition blocker and implement the smallest general
   improvement, preserving failure order, affine use, and bounded compiler work.
3. Implement the first scoped typed region and an independently justified local
   rewrite, paired with direct references and extension performance measurements.
4. Revisit configured public composition using that evidence. Then evaluate
   broader loop/tree profitability and the required backend/project gates.

This order retains the working library and sound fallback while returning the
work to the design's central objective. It does not require another broad rewrite
proposal or more transducer-specific compiler recognizers.
