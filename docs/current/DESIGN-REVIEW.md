---
created_at: 2026-09-20T19:31:00+02:00
status: current
---

# Adversarial design review — 2026-09-20

## Recommendation

Keep transducers as ordinary, statically composed reducer transformations, and
keep traversal owned by each source. Develop general compiler support for static
composition and local representation elimination. Treat aggressive control-flow
optimization as a separate, scoped analysis with explicit preconditions.

The existing library is a useful semantic foundation. The latest native candidate
is performance evidence, but is not ready to become a language implementation:
this review found a reproducible Array miscompilation in the exact candidate
whose hash appears in the latest parity report.

Do not change the reducer contract to make that counterexample illegal. Do not
continue adding structural recognizers to this candidate as the architectural
answer. Preserve its useful experiments, scalar analysis, and regression cases;
redesign how facts authorize rewrites.

This review changes no compiler or library implementation. The new files are
this discussion document, a source reproducer, a checker, and recorded evidence.

## What exists today

| Layer | Actual implementation | Assessment |
| --- | --- | --- |
| Reducer semantics | `Reducer<A,R>` packages configuration/state types and start/step/finish; state is owned | Keep this foundation |
| Transformations | Templates transform a downstream reducer; map adds no state, filter carries settings, take carries count and downstream control | Already independent of traversal |
| Source binding | `Reduction` binds a source fold and one reducer recipe; `transduce` starts, folds, finishes | Open extension mechanism, although staging leaks into adapters |
| Shared compiler change | Fork commit `b1f9c936`, roughly 122 added/changed lines in `comp.ts`, resolves computed static function heads before lowering | General mechanism worth developing independently |
| Experimental native changes | `guarded_scalar.inc.ts` and `guarded_loop.inc.ts`, 907 lines plus integration in `prepare_guarded.py` | Bounded symbolic scalar analysis, guarded loop cloning, and tree/FID re-emission |
| Backend scope | Static callback specialization feeds JS/native; experimental guarded lowering selects host C and retains other paths for devices | Latest CPU parity does not establish latest GPU parity |

The candidate is reconstructed in a temporary compiler copy. It is not installed
in the sibling fork. Its hash is
`96451e7383a8634bc7efe554564b6310c3eb7803b07ac13d3c2a887486c5831e`.

There are three distinct performance properties:

1. **Streaming composition:** stages feed downstream directly instead of building
   a collection at each boundary. The library already does this.
2. **Representation elimination:** remove static dictionaries, callback dispatch,
   transient wrappers, and state packing where the program permits it.
3. **Control-flow optimization:** remove redundant tests or choose a faster loop
   formulation under proved facts and a separate profitability decision.

Parity on selected workloads is evidence about all three together. It is not a
compositional guarantee that adding a new reducer adapter preserves that parity.

## Confirmed blocking findings

### 1. Tree control rewriting applies a conditional output fact to arbitrary input

`gl_tree_context_for_def` takes the scalar summary's output relation, checks its
layout, and installs it as `control` for a whole tree definition.
`gl_tree_match_rewrite` then replaces matching control-tag tests with counter-zero
tests. Layout equality does not establish that this particular value came from
the summarized operation, or that its precondition held.

The relation is proved for a guarded callback result. It is not proved for the
driver's initial state, every recursive input, or every same-layout value matched
inside the definition. The host FID is replaced without a caller entry proof.
Keeping the original body behind the device preprocessor branch does not provide
a host fallback for other valid inputs.

### 2. The tree callback chain uses an unguarded fast summary without its precondition

`guarded_scalar` records both `pc` and a `fast` emitter. The fast emitter omits the
guard. The tail-loop path constructs a `GLProbe`, maps the guard to entry values,
and checks its preservation. The tree path selects a summary by call-graph and
layout shape, then re-emits its callback chain using `candidate.fast` without the
equivalent proof or a checked helper dispatch.

The comment that tree callback helpers retain their own fallback is inconsistent
with this use of `fast`. Disabling only the tag rewrite does not fix the bug.

### Reproducer and observations

[Source](../../review/tree-entry-control.bend) calls the public `reduce_array` with
well-typed controls. These inputs need not arise from the standard initializer:
the source contract explicitly accepts initialized control and must preserve an
initial Stop. Bend does not encode a narrower refinement on this argument.

The probe encodes Stop as 1000 plus the final sum and Continue as 2000 plus the
final sum. Its first result is an ordinary transduction as a control case.

| Case | Expected / candidate JS | Candidate host C |
| --- | ---: | ---: |
| Standard filter/take/sum | 9 | 9 |
| Initially Stop, count 2, sum 0 | 1000 | 1009 |
| Continue, count 0, every input rejected | 2000 | 1000 |
| Continue, count 2, downstream Stop with sum 17 | 1017 | 1026 |

The candidate processes data after the first Stop and fails to preserve control
or downstream stopping in the other cases. These are semantic differences, not
benchmark noise. A temporary diagnostic with only tag rewriting disabled returns
`[9, 1000, 1000, 1026]`, confirming the second gap survives independently.

[Recorded evidence](../../review/tree-entry-results.json) includes compiler/source hashes.
Reproduce with a fresh empty output directory:

```sh
python3 bench/compiler/prepare_guarded.py --loop --output-dir /tmp/design-review-candidate
python3 review/check_tree_entry.py --bend-main /tmp/design-review-candidate/main.ts --output /tmp/tree-entry-results.json
```

The checker intentionally exits 1 on the current candidate's disagreement.
During this review the existing `tests/run.py` suite passed **18/18** on that same
candidate. Those tests therefore do not cover this proof boundary sufficiently.
The historical scalar and tail-loop adversarial tests cannot establish tree-entry
correctness. No new performance timings or full upstream/device gates were run.

## Extensibility findings

### Name-independent recognition is not yet general optimization

The candidate avoids transducer function names, which is good. However, scalar
selection requires exactly two chosen state tests, a derived zero-test output,
and at least two conditional outputs. It admits wrapping U32 addition within
the analyzed scalar region, not arbitrary arithmetic. Boxes in reducer state or
results are refused. It accepts exactly one candidate summary in the bounded
call graph. The tree recognizer counts four recursive application visits and two
non-tail visits in the elaborated syntax.

These are understandable experiment limits. They are not a natural specification
for optimization of arbitrary reducers. A counter adapter, two buffered stages,
another accumulator representation, or an equivalent traversal refactoring can
leave the recognized region. Budget limits should control compiler resource use;
the semantic unit of optimization should not be “looks like this benchmark.”

### Compiler behavior currently leaks into library representation

The public binding helper takes a delayed `Unit -> Reducer` recipe. `Reduction`
delays type metadata too, specifically to avoid repeated evaluation and fuel
exhaustion. Forwarding lambdas can specialize where bare matcher callbacks do not.
The list implementation has both `reduce_list` and `reduce_list_static`; both
actually take static template code, but package it differently to expose it to
the compiler.

These observations motivate a better static-code boundary. They do not prove a
new language feature is necessary. First test whether a shared, memoized static
representation and systematic callback exposure can eliminate these workarounds
with existing templates. Preserve strict evaluation and ownership while doing so.

### The lifecycle is worth preserving

Upstream termination and downstream termination are different. For example:

```text
take(3) → partition_all(2) → collect
```

must flush the remaining one-element group, while

```text
partition_all(2) → take(1) → collect
```

must discard pending output once downstream stops. The existing owned state and
completion tests already express this distinction. A single universal stop bit,
or a rule equating stop with a counter value, would lose necessary semantics.
This agrees with Clojure's [transducer lifecycle contract](https://clojure.org/reference/transducers).

## Proposed target architecture

The library's conceptual boundary should remain:

```text
Reducer<A,R> = { Config, State, start, step, finish }
Xform<A,B>   = a static transformation of Reducer<B,R> into Reducer<A,R>, for any R
Reducible<X,A> = source-owned ordered stopping fold, for any reducer state S
```

This is conceptual notation, not a claim that these higher-rank interfaces are
directly expressible with today's Bend syntax. Current templates approximate
them. Static composition should derive types and configuration structure when a
consumer is supplied. Named settings or typed configuration constructors should
replace users manually assembling nested positional tuples.

Code remains static; settings and owned execution state remain runtime values.
New transforms implement the reducer lifecycle. New pure sources implement their
fold once. Neither should need compiler registration or knowledge of other stages.

The compiler should operate on general program structure:

1. **Specialize static code:** resolve template dictionaries and callback
   projections, memoize static work, bind dynamic expressions once, and retain
   their evaluation order. Normalize equivalent lambda/matcher forms. Report
   refusals and budget exhaustion in optional optimization diagnostics.
2. **Expose a bounded typed region:** preserve stable binding identity, calls,
   branches, constructors, ownership, and checked operations. Build on existing
   typed terms/ANF; introduce only the additional region representation needed.
   Avoid a second whole compiler and avoid deriving semantics from emitted C.
3. **Eliminate local representation:** simplify constructor/projection pairs,
   propagate constants, scalarize nonescaping state, and retain boxes that are
   real buffers or outputs. An unknown callback should limit the surrounding
   optimization without requiring all-or-nothing rejection of the entire chain.
4. **Apply scoped facts:** a summary must carry preconditions, result relations,
   preserved fields, and relevant failure/effect obligations. At each use, prove
   the precondition for the actual arguments or retain a valid generic path.
   Attach facts to values and program points, not just equal layouts.
5. **Lower continuations and backend code:** preferably perform contextual
   specialization before FID/frame lowering, where typed function entry is still
   explicit. If facts cross continuation boundaries, model each entry and its
   frame explicitly. Do not dispatch raw continuation frames as root arguments.
6. **Choose profitable forms separately:** preserve branches where appropriate;
   scalar replacement need not mean blanket predication. Bound code growth and
   evaluate profitability per backend and workload class.

For tree recursion, a sound summary composes “left traversal returns state” with
“right traversal receives that exact state,” including early termination and
base cases. If this proof is unavailable, retain the original tree control flow
and optimize only locally justified callback regions. That is a correctness
boundary; it does not require abandoning source-owned tree traversal.

## How additional operations should fit

| Operation | Library semantics | Compiler opportunity / real cost |
| --- | --- | --- |
| remove | Filter with negated predicate | Ordinary branch/call simplification |
| keep | Consuming `A -> Maybe<B>`, emit only Some | Local option elimination; can support affine elements without inspecting then duplicating A |
| drop / take-while / indexing | Owned local state and explicit stop propagation | General state simplification; keep checked arithmetic semantics |
| partition-all / partition-by | Buffer, downstream control, completion flush | Remove boundary overhead; retain necessary buffer storage |
| cat / mapcat | Nested reduction with stop propagation | Expose nested loops; existing List fragments are real allocations unless producer elimination proves them unnecessary |
| distinct / dedupe | Set or previous-element state | Real storage and equality/ownership constraints remain |

“Add an operation once” should mean no source-specific implementation or compiler
case is required for its semantics. It cannot mean that every operation becomes
allocation-free or that every target backend always discovers optimal code.

## Sources, IO, and parallelism

Lists, balanced arrays, strings, ranges, and a user-defined tree already exercise
the pure fold model. Maps can choose a documented entry order and yield owned
key/value pairs. They do not require a universal iterator allocation.

Files and channels add execution obligations: IO errors, handle lifetime,
cancellation, suspension/backpressure, and completion on each exit path. A pure
`X -> Control<S> -> Control<S>` cannot itself perform arbitrary IO. The same pure
transducer logic can be driven by an effectful process, but its runner needs an
explicit effect/lifecycle contract. Push channels may apply a reducer directly
rather than implementing the same synchronous pull-fold interface. This broader
process model is also described in the [Clojure reference](https://clojure.org/reference/transducers).

Likewise, reducible does not imply parallelizable. A single stateful reduction is
ordered. Parallel fold needs an associative combination contract and a valid
strategy for stateful stage boundaries. Clojure also distinguishes reducible from
[parallel foldable collections](https://clojure.org/reference/reducers). Fusion
can happen inside each valid execution region without promising fusion across
IO or scheduling boundaries.

## Options to discuss

| Option | Benefit | Cost / recommendation |
| --- | --- | --- |
| Keep extending the current emitter recognizers | Shortest route to another benchmark win | Scope and structural coupling grow; do not choose as the long-term architecture |
| Ordinary reducer library plus general typed specialization | Open user extensions; language-wide benefit; preserves current semantics | Requires disciplined region/dataflow work; recommended foundation |
| Explicit general static module/staging feature | Predictable code/configuration boundary; can remove recipe thunks and signature repetition | Language/checker design commitment; prototype with current templates first |
| Dedicated transducer AST or compiler intrinsic set | Easy recognition of a fixed vocabulary | Arbitrary user operations require an escape or extension mechanism; avoid a closed vocabulary as the semantic foundation |

A general staging boundary can complement general optimization. It need not
introduce a privileged transducer pipeline type into the compiler.

## Decision sequence

1. Accept the semantic foundation: source-owned traversal, owned reducer state,
   explicit lifecycle, static code, runtime settings. Keep the candidate isolated.
2. Establish scoped summary preconditions as the compiler design rule. The Array
   counterexample is an acceptance test; forbidding its inputs is not a fix.
3. Prototype one ordinary-code optimization region and one cleaner static binding
   using existing templates. Preserve the direct map-chain baseline. Evaluate
   compiler cost and whether library staging workarounds disappear.
4. Validate extension independence using keep, a buffered partition operation,
   scalar and affine consumers, and a separately implemented source. No compiler
   names or branches should be added for those operations.
5. Test shared callers, initial and returned controls, same-layout unrelated
   values, continuation entries, failure ordering, and completion. Pair structural
   codegen tests with end-to-end semantic comparisons.
6. Only then revisit performance acceptance and upstreaming, with separate
   changes for static composition, representation elimination, and optional
   backend loop optimization.

The open design question is how much explicit staging the public library needs,
not whether a transducer should become a compiler-recognized map/filter/take
pattern. My preference is to start with the smallest template-based library
surface and strengthen the compiler underneath it.

Confidence is property-specific: the reported counterexample is reproduced;
the lifecycle design is supported by existing tests and source reasoning; the
proposed compiler architecture still needs prototypes and verification. No finite
review establishes literal 100% correctness or universal performance parity.
