---
created_at: 2026-09-20T20:19:47+02:00
status: current
---

# Completing the transducer design

Proposed execution plan, 2026-09-20. Prepared after the
[implementation review](../review/IMPLEMENTATION-REVIEW.md), for discussion before
the next implementation worksets. This document specifies work; it does not
claim the work has been performed.

## Intended result

Keep transformations and source traversal as ordinary Bend library code. Make
static composition predictable, then eliminate locally unnecessary representation
using general compiler rules. A newly written transform or source must not need
registration with the optimizer. Useful buffering and output allocation remain.

The existing tree refusal stays in place. The current List experiment is a
baseline to protect, not the implementation of the proposed general architecture.
Compiler prototypes remain in isolated copies of `comp.ts`; no edits to
`bend2/bend.ts`. Each workset ends in its own commit, with checks and remaining
acceptance items recorded. A successful probe closes an investigation, not an
unimplemented workset.

## Design decision: make keep ordinary composition

The desired relationship, written in input-to-output order, is:

```text
keep(f) = map(f) → cat_maybe

f: A → Maybe<B>
cat_maybe: Maybe<B> → zero or one B
```

`cat_maybe` is the optional-value counterpart of the existing List `cat`.
It forwards initialization and completion to its consumer. Its step consumes
the option once: None returns Continue with the unchanged consumer state; Some
passes the owned payload to the downstream step and returns its control.
There is no new compiler primitive and no option-to-List conversion.

`map(f) → filter(some?)` alone emits `Maybe<B>`, not `B`. Adding an unwrapping
map fixes the output type only if its None case is handled. In addition, today's
`filter` requires `Data`: it tests a value while retaining it for downstream.
That excludes affine payloads such as closures. A consuming option match both
tests and extracts without copying or introducing a partial unwrap operation.
For copyable payloads the three-stage expression can be a comparison fixture,
but it should not become a narrower semantic implementation of keep.

The concrete library shape to prototype is:

```text
cat_maybe(~B, ~R, ~down) : Reducer<Maybe<B>, R>
keep(~A, ~B, ~R, ~f, ~down) =
  map(~A, ~Maybe<B>, ~R, ~f, ~cat_maybe(~B, ~R, ~down))
```

This is a proposed template spelling to typecheck, not an already accepted new
API. It preserves keep's configuration type and its `A: Type`, `B: Type` scope.
The current `keep_choose` already contains the relevant consuming match; move
that responsibility into the optional flattening adapter and remove the redundant
specialized keep step once equivalence is established.

Conceptual `comp(map(f), cat_maybe)` should describe this same operation. We do
not need a runtime collection of stages or a compiler pipeline AST to get it.
A generic reusable `comp` helper depends on how today's templates express
transformations polymorphic in the downstream state/result; investigate its
actual syntax in workset 6. Until then, nested reducer templates express the
same static composition. Document composition order explicitly.

Fusion is an acceptance obligation, not an assumption. For a visible producer
returning Some/None, the compiler should eliminate the temporary constructor and
immediate match where justified. An opaque producer may still return a real
option; consumers must remain correct without inlining it. Neither case builds
an intermediate collection for the map/filter boundary.

## Priority and dependencies

Effort reflects semantic and maintenance complexity, not typing or line count.

| Workset | Impact | Effort | Value | Dependency |
| --- | --- | --- | --- | --- |
| 0. Repair status and measurement | Critical: trustworthy acceptance | Medium | Highest | None |
| 1. Complete extension semantics; compose keep | High: validates the abstraction | Medium | Very high | 0 for codegen claims |
| 2. Reduce and improve static composition | High: removes staging workarounds | Medium–high | Very high | 0; preserve 1 as it lands |
| 3. Introduce scoped local facts | Critical: sound rewrite authorization | High | Very high | 2's chosen term boundary |
| 4. Eliminate a demonstrated local cost | High: general fusion benefit | Medium–high | High | 1–3 |
| 5. Measure extension/direct parity | High: tests the actual objective | Medium | High | Baseline in 1; acceptance after 4 |
| 6. Simplify configured composition | High: usable public surface | Medium–high | High | 1–4; measure again after changes |
| 7. Broader control flow and promotion | High, required for promotion | High | High after foundation | 0–6 |

Worksets 0–4 are the first architectural milestone. They deliver trustworthy
tests, a compositional keep, improved static resolution, and a real general local
optimization. Worksets 5–6 establish performance and usability. Tree performance
and device/upstream promotion have their own explicit exit criteria in 7.

## 0. Repair the acceptance machinery

**Files:** `DESIGN-WORK-PLAN.md`, `HANDOFF.md`, `FINAL-VALIDATION.md`,
`bench/compiler/representation_probe.py`, `static_composition_probe.py`,
`bench/fusion_parity.py`, and a shared codegen inspection helper under
`bench/compiler/`.

1. Replace blanket completion claims with per-deliverable status. Original
   packages 2–4 remain incomplete; 1, 5, 6, and 7 remain partial. Package 0's
   conservative correctness repair is complete. Preserve old reports as history.
2. Separate measurements: JS dictionary construction, native dynamic dispatch,
   actual allocation sites, code size, compile time, and runtime. Do not use
   absence of a compiler-internal name in C as an acceptance condition.
3. Start native inspection with generated function/segment boundaries and actual
   `FID_CLO_APPLY` transfers. Attribute sites to the selected traversal and its
   reachable helpers. Label IO, affine input callbacks, and unknown targets;
   unknown attribution is inconclusive, not zero overhead. Avoid accepting a
   whole-file substring count as proof of per-element behavior.
4. Add small detector controls: a statically resolved reducer callback and an
   intentionally dynamic function argument. Require the second to report dispatch.
   Include a legitimate closure-valued element so the harness distinguishes an
   application callback from reducer dictionary dispatch. Report counts as sites,
   not execution frequency. If textual attribution is ambiguous, emit structured
   call-site diagnostics from the isolated compiler rather than guessing.
5. Make representation assertions optional by explicit expectation per fixture;
   execution equality remains mandatory. Add provenance for library, fixture,
   compiler, and harness revisions/hashes to new reports.

**Exit:** the detector's positive and negative controls pass; it identifies the
known dispatch sites in the buffered review fixture; unsupported attribution
cannot produce a pass. Existing semantic checks and the tree reproducer pass.
Refresh current conclusions to match the repaired measurements.

## 1. Complete semantics and implement compositional keep

**Files:** `transduce.bend`, focused fixtures under `tests/`, `tests/run.py`,
`LAWS.md`, `EXTENDING.md`. Use `examples/tree.bend` without source-specific logic.

1. Introduce `cat_maybe` with the lifecycle above. Express keep through map and
   this adapter, retaining its current public signature and runtime configuration.
   Keep an independent direct consuming-match reference in tests, not a second
   production implementation.
2. Verify keep, explicit map/cat_maybe, and the reference agree for Some/None,
   type-changing output, empty input, initial and consumer stopping, affine input
   and output, and repeated runs. Observe that `f` runs once per visited input
   and never after source stopping. Check completion exactly once.
3. Test the actual public partition adapter using the matrix below. Use ordered
   collectors to reveal missing/duplicated/reordered values and a consumer whose
   completion records a final marker. Use a custom consumer that returns Stop;
   testing take alone is insufficient.
4. Instrument source/step/start/finish counts in dedicated JS fixtures using the
   existing runner pattern. Add native success/failure sentinels for forbidden
   evaluation, with an independent test proving that each sentinel fails when
   reached. Counts and sentinels supplement output comparisons; neither backend
   borrows the other's evidence.
5. Add small direct references with the same stopping, grouping, ownership, and
   completion. They must not invoke the transducer implementation under test.
   Reuse these specifications when constructing performance fixtures in 5.

| Case | Required observation |
| --- | --- |
| Empty input; widths 1, 2, larger than input | No empty trailing group; ordered full/partial groups |
| Zero width | Initial Stop; zero source steps; downstream initialization/completion each once |
| Downstream initial Stop | No source steps or flush emissions |
| take before partition | Partial buffer flushes after upstream stop |
| partition before take | Downstream stop prevents further source steps/emissions |
| partition before partition | Inner completion can feed outer buffer; each finishes once |
| Consumer Stop on a full group | Exact stop propagation and no later callback |
| Consumer Stop during partial flush | Stop respected, then downstream finish once |
| Affine values through full/partial groups and stopping | No copying; correct use or discard on each path |
| Repeated use of one description with different settings | Fresh buffers/state; no cross-run contamination |

Run shared cases on List, range, and the external tree; run affine cases on the
sources that can hold those values. Test the new public adapter, rather than only
the historical pair-buffer mock. Keep the documented zero-width policy unless a
separate explicit API decision changes it.

**Exit:** reference and candidate JS/native pass the matrix; compositional keep
retains affine support, output types, stopping, and configuration. Record residual
representation without claiming that all of it is already eliminated.

## 2. Make static composition systematic

**Files:** isolated `comp.ts` changes around `static_fun`, `specialize`,
`def_body`, and existing caches; reproducible preparation code and fixtures in
`bench/compiler/`. No edits to the sibling checkout as an incidental experiment.

1. Preserve the eager migration as a reproducible variant. Update every adapter,
   including the external tree. Reduce the Array's three residual reducer records
   to one failing projection/call. Retain delayed/eager forms and bare matcher/
   forwarding-lambda forms as separate inputs with identical expected behavior.
2. Add diagnostics for static-head attempts: term/definition identity, result kind,
   refusal reason, consumed budget, repeated work, and emitted specialization.
   In the current code `static_fun` only returns lambda results; investigate
   matcher handling and partial application explicitly before choosing a fix.
3. Implement the smallest shared resolution mechanism that addresses the reduced
   case. Known lambdas and applicable matcher heads should preserve the same
   strict evaluation behavior. Keep bare named calls when expansion is unnecessary.
4. If repeated static evaluation is the cause, memoize immutable static results
   within one compilation. Identify entries by definition/term identity and the
   relevant static arguments, type instantiation, and environment. Never key
   semantic results solely by storage layout. Do not cache an open result without
   its environment or let one compilation's facts leak into another.
5. Handle recursion with an in-progress entry and ordinary fallback. Distinguish
   unsupported evaluation from budget exhaustion; a result refused solely because
   little budget remained must not poison a later query with a different budget.
   Track expansion size as well as evaluation effort; freeze limits before
   performance acceptance instead of increasing fuel until a benchmark passes.
6. Preserve live dynamic arguments as single, ordered bindings. Static projection
   cannot drop evaluation of another live field that may fail. Preserve erased
   arguments according to their quantifiers. Unknown, foreign, unsafe, or parallel
   operations stop speculative evaluation and retain the original computation.
7. Attempt removing recipe delays and unifying the List drivers, one change at a
   time. Keep a reduced blocker for every retained workaround. Remove delayed
   type metadata only if its own tests and compile-cost evidence justify it.

**Exit:** eager built-ins and migrated external source pass JS/native and the
repaired codegen checks; matcher/lambda forms agree; repeated/deep compositions
stay within declared limits. Test distinct same-layout instantiations, checked
failure ordering, affine arguments, unknown calls, and deterministic budget
fallback. A probe plus an unchanged compiler does not satisfy this workset.

## 3. Give local optimization facts explicit scope

**Files:** a small typed-region addition to the isolated compiler, integrated
after static resolution and before native FID/continuation emission. Inspect
`HTerm`, `anf`, and existing binding helpers before adding representation.

1. Use existing typed terms as the source of truth. The first region is local
   and nonrecursive: bindings, known constructor fields, matches, calls, and
   returns. Add only missing identities/edges in a side table or small region
   view; do not build another whole-program IR. Preserve annotations and source
   locations so diagnostics can explain a refusal.
2. Assign each binding a stable identity within its instantiation. Facts include
   the value identity, program point, constructor/tag or equality information,
   and origin/precondition. Equivalent layouts alone carry no fact.
3. Model branch entry and joins. A Some fact belongs to the matched value in the
   Some arm. A join retains only properties true on every incoming path, with
   explicit mapping to the joined value. Facts about one argument do not transfer
   to another argument with the same type.
4. Define summaries containing typed formal inputs, preconditions, output
   relations, preserved values, ownership uses, and failure/effect obligations.
   Provide one checked instantiation path that maps actual arguments and either
   authorizes the rewrite or declines it. Keep the unguarded emitter private to
   that path; do not expose a freely callable `summary.fast` equivalent.
5. Retain call order and conditional execution. Unknown calls yield unknown
   results and conservative escape information; unrelated immutable local facts
   may survive. If purity or ownership is uncertain, leave that boundary intact.
6. Do not import old scalar summaries by shape. Adapt them only where all their
   premises can be expressed and checked. Recursion and continuation crossings
   remain explicit refusal boundaries for this first implementation.

**Exit:** an ordinary non-transducer constructor/match example gets a positive
rewrite through this API. Negative tests cover unrelated same-layout values,
failed preconditions, differing instantiations/callers, joins, branch-local
checked failures, affine payloads, and opaque callbacks. Disabling the pass
preserves outputs/failures; diagnostics show why each rewrite was authorized.

## 4. Remove demonstrated local representation costs

**Files:** local rewrite rules at the boundary established in 3, independent
Bend fixtures, and repaired representation reports.

1. Choose the smallest residual cost from 1–2, first a visible option producer
   followed by consuming match. Compare with direct Bend and identify the exact
   constructor/match or state transfer being removed. If existing lowering already
   removes it, record that result and choose another demonstrated residual cost.
2. Eliminate the constructor and select its arm only with a known constructor
   fact. Bind live fields in their original evaluation order, including fields
   whose evaluation can fail even when their result is unused. Move affine fields
   once; do not duplicate or silently resurrect them.
3. Extend to nonescaping configuration/control wrappers only after the first rule
   passes. An escaping wrapper, unknown ownership use, or unresolved callback
   stays represented. An opaque buffer need not prevent optimization of unrelated
   scalar fields around it.
4. Inspect both backends. Locate removed allocation/packing/dispatch sites in
   the relevant path, rather than comparing whole executables containing unrelated
   IO and display functions. Preserve real partition buffer and output storage.
5. Compare direct keep, composed keep, renamed helpers, and a non-transducer
   example. No rule may name `keep`, `cat_maybe`, `partition_all`, or fixed fields
   of a transducer state.

**Exit:** at least one previously retained boundary cost disappears through a
general rule, with paired evidence and semantic/refusal tests. Composed keep has
no extra temporary wrapper cost where its visible constructor can be eliminated.
Unknown-producer cases remain correct and explicitly measured, not silently
excluded from reports. Existing map-chain behavior remains protected.

## 5. Establish extension performance, with honest statistics

**Files:** `bench/fusion_parity.py`, extension/direct fixtures, retained reports.

1. Preserve the five existing rows. Add cheap type-changing keep with mixed
   Some/None results, full and early-stop runs, and composed versus direct forms.
   Include a configuration supplied at runtime to prevent a single closed input
   from being the only specialization evidence.
2. Add partition widths 1, 2, and a larger width, full/partial completion, both
   stopping orders, and at least one nested case. Compare equivalent List output
   or consumers that consume whole groups. Do not compare a buffering pipeline
   to a scalar direct sum that avoids the specified group work.
3. Retain independent correctness oracles and matched ownership/source creation/
   cleanup. Separate allocation-site evidence, measured allocation if instrumented,
   runtime, generated code size, and compilation cost.
4. Calibrate repetitions to the duration floor before collecting retained samples.
   Alternate/randomize paired batches across lanes; retain session and batch IDs.
   Do not treat consecutive observations within one process as independent sessions.
   Bootstrap at the independently scheduled block level and report sensitivity
   across sessions. Timings below resolution remain inconclusive.
5. Use the existing provisional 1.05 upper-ratio target for equivalent CPU rows,
   declared before inspecting new results. Record failures as open performance
   items rather than changing the target afterward. Keep original/reference and
   candidate lanes for the compiler changes under evaluation.

**Exit:** every claimed extension row has semantic agreement, calibrated samples,
and a stated result against the predeclared target. Report source/backend scope
and all regressions. No general all-source or GPU claim follows from List timings.

## 6. Simplify the actual configured user experience

**Files:** `transduce.bend`, `tests/api_surface.bend`, README and extension examples.

1. Prototype a named reusable pipeline with type-changing keep, configured filter,
   take, and partition. Run it against a group-count consumer and a group collector
   on List, range, and the external tree. Consumer settings remain independent.
2. Specify the desired call site before changing internals: pipeline declaration
   once, named settings, chosen consumer, source. Derive internal state/configuration
   structure from the description; callers should not reconstruct nested tuples.
3. Try a typed configuration constructor associated with the composed description,
   using existing templates. A manually maintained second copy of the stage
   structure is not the desired end state. Keep public settings separate from
   the fresh owned state created by start.
4. Test a generic static `comp` spelling with polymorphic downstream consumers.
   Adopt it only if typechecking and lowering preserve the same abstraction and
   ownership. Do not erase types, introduce a runtime stage registry, or add a
   special-case pipeline interpreter to obtain attractive syntax.
5. If current type syntax cannot express the intended builder/composition, retain
   the smallest failure and alternatives in a design note. Distinguish required
   explicit type arguments from incidental compiler workarounds. A language feature
   proposal is a separate decision, not a reason to mark this acceptance complete.
6. Migrate examples coherently, remove redundant provisional paths where possible,
   and rerun semantic/codegen/performance acceptance after the API changes.

**Exit:** a configured, reusable type-changing composition works with multiple
consumers/sources, settings are typechecked without caller-maintained internal
state shapes, and result-type repetition is either removed or explicitly explained
by a retained language limitation. Unit-only examples do not close this workset.

## 7. Control-flow performance and promotion

Keep this separable from the local composition/representation contributions.

1. For each retained loop optimization, map entry premises to actual arguments
   and prove preservation on every reachable back edge, including exits before
   callbacks. Reuse valid existing tests, adding full state/control comparisons
   rather than only final sums. Run relevant sanitizer and checked-failure tests.
2. Before attempting tree specialization, express base cases, ordered child
   traversal, the exact left-return/right-input value, and Stop propagation in
   the analysis. Prefer a boundary before continuation lowering. If that is
   unavailable, model every continuation entry/frame explicitly or refuse it.
   Recursive AST visit counts are not the proof.
3. Select profitable forms separately from semantic eligibility. Include empty,
   zero/one/short/long sources, cheap/expensive callbacks, mixed predicates, and
   shared callers. Preserve generic behavior when proofs fail and record known
   short-loop regressions. No heuristic is promoted just because long List rows pass.
4. Stage separate reviewable compiler changes for static resolution, local
   representation, and optional loop/tree lowering. Each carries ordinary-code
   positive/refusal examples, budgets, code-growth evidence, and semantic scope.
5. Run relevant compiler type/regression gates and the upstream project gates.
   Shared pre-backend changes need device-specific validation even if introduced
   to improve CPU code. Record unavailable infrastructure as outstanding; run the
   required GPU/device matrix in the proper environment before promotion.

**Exit:** local compiler changes can be reviewed independently of tree optimization.
Tree remains generic until its own proof and performance criteria pass. Promotion
requires applicable backend and project gates; missing infrastructure never becomes
a passing result. IO/process and parallel-fold contracts remain separate designs.

## Workset completion record

Each commit should point to a short record containing: the changed behavior,
the original acceptance items satisfied, exact compiler/library identities,
commands and retained results, counterexamples/refusals, and remaining gaps.
Label each item implemented, demonstrated already optimized, unsupported with
reproducer, or blocked by a named external dependency. The latter two remain open.

Worksets 0 and 1 are now implemented. Workset 2 has a scoped memoization
prototype and a minimized, reproducible Array blocker. Workset 3 now has the
first isolated constructor-fact prototype, recorded in
[SCOPED-FACTS.md](SCOPED-FACTS.md), with positive and dynamic-field refusal
evidence. The full typed-region, join, recursion, and continuation work remains
open. Workset 4 now demonstrates one general tagged constructor-match rewrite,
recorded in [LOCAL-REPRESENTATION.md](LOCAL-REPRESENTATION.md); the composed
Maybe wrapper remains an explicit next target. The next compiler change should
use this boundary to measure that Maybe cost before changing the public staging
boundary. A surprising result should revise the explanation and tests before
expanding the optimizer.
This plan closes the identified gaps without assuming either universal fusion
or a new language feature in advance.
