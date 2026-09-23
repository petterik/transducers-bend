---
created_at: 2026-09-23T14:20:13+02:00
updated_at: 2026-09-23T17:39:13+02:00
status: active
---

# Integrating transducer fusion with bendlang/main

This plan targets **only `bendlang/bend:main`**. The goal is one compiler
optimization for statically known callback values that does not recognize
`Reducer`, `Tree`, or individual transducer names. A new source should get the
same behavior when it supplies a closed reducer recipe. `keep` remains the
composition of `map` and optional-value flattening.

## What the language guide implies

The current upstream guide says `~` arguments are closed syntax, substituted at
compile time, with a separate compiled copy for each distinct argument set.
Closures are affine, and recursion is how Bend expresses loops. Bend has no
implicit protocol or trait dispatch. “Reducible source” therefore means an
explicit library adapter contract, not a compiler-discovered interface. Source
ownership and live state stay in checked Bend code; templates expose callback
code to the compiler.

## Decision and current evidence

The refreshed `bendlang/main` ref is
`6a77e1246c351055cb15031267a7c76c87036cbc`. Its `bend2/comp.ts` is unchanged
at SHA-256 `10afb08dd55a52bfbb88fdf84534cebdc000bdf7820c69cee1d6bb3fcfaf7d7b`
from the previously tested upstream commit. The new commits add named-package
imports in the checker and guide, not compiler changes. The build harness now
reads only the `bendlang/main` remote-tracking ref; it does not accept the fork's
`origin/main`. The sibling checkout remains unmodified.

The isolated candidate's compiler hash is
`51b37bfbf854f4efcc1beafcf7c0d756dc7735fd49839a8f14f62cd6e7927557`. Its
self-check passes five static-callback fixtures on JS and native. The complete
library run passes 23/23 files on both backends, including the code-shape gate
for `keep_partition`; no `Reducer` or `Reduction` records remain in the gated
fixtures. The old fork candidate is not a comparison target or supported
fallback.

The fix was not a partition-specific rewrite. Checked terms place type
annotations between curried application nodes, so the evaluator previously
could not see all `~` arguments when resolving an already checked template
instance. The pass now flattens only that application spine for lookup, with a
2,048-node scan cap; the checked term itself remains intact for evaluation and
fallback. This also makes type-changing `keep` run at parity with its direct
loop.

The evaluator must not treat every `Def.e` as an ordinary body. A generic
`Def.x > 0` has its `~` binders removed for checking; unfolding it as an ordinary
function can fail or produce a wrong static value. Never unfold a generic
template directly. Evaluate only an existing checked instance with `x == 0`,
and retain the original expression whenever its identity cannot be resolved.

## Recommended compiler boundary

Keep the optimization after checking and before `def_raise`, call-graph
discovery, ownership/layout analysis, and backend emission. The `def_body`
seam gives JS and native the same checked higher-order term. Rewrite once there,
then let the existing lowering and fusion machinery see the resulting calls.
On any unproved static head, keep the checked expression unchanged.

The pass should reduce only a computed function head that comes from closed,
checked definitions and constructor fields. It should bind live arguments once,
retain annotations and quantities, and recurse under explicit fuel and rewrite
limits. Bare function calls remain ordinary calls. The rule must not depend on
transducer names, constructor tags, or source adapter shapes. The compiler
change should remain a small optimization rather than introduce a second
lowering framework.

During experimentation, keep the pass in a small TypeScript fragment and use a
thin `prepare_static.py` archive/patch driver. Keep the source hash, anchors,
and provenance manifest. If the pass clears the gates below, move it into
upstream `bend2/comp.ts` and add compiler-native Bend fixtures; the Python
driver then remains only a comparison harness. Upstream `AGENTS.md` says not to
edit `bend2/bend.ts`; no checker edit is part of this plan.

## Prioritized work

1. **P0 — Finish adversarial template-instance checks.** The candidate rejects
   direct evaluation of generic definitions, uses only an existing checked
   `x == 0` instance, tries an exact `book.tmps` key, then uses bounded
   `term_compare` and refuses ambiguous matches. `tests/template_instances`
   covers two static values and two callbacks; the full suite also covers
   annotated calls, nested templates, runtime fallback, and affine rejection.
   Still add focused cases for aliases that compare equal, ambiguous entries,
   recursion, oversized spines/tables, and cache stability. Retain the original
   expression on every uncertain identity. Ask upstream for a read-only
   checked-instance ID only if the checked Book cannot resolve identity safely.
   Do not call `def_inst` from code generation: it can recheck terms and mutate
   the Book.

2. **P0 — Remove closed-pipeline reducer records. Completed.** The
   annotation-aware checked-spine lookup resolves the existing reducer
   instances used by `keep_partition` without recognizing reducer names or
   constructors. `tests/run.py` now passes its full no-record, semantic,
   callback-count, lifecycle, and bounded-law checks on JS and native. Keep the
   dynamic-reducer fallback covered as later changes build on this.

3. **P1 — Measure the whole pipeline on the exact main snapshot. Completed for
   this candidate; partition remains open.** The calibrated native
   transducer/direct matrix covers 11 sequential List cases: full and early
   stop, type-changing `keep`, and bounded and full `partition_all`. The full
   library suite separately checks semantics on JS and native. Record the
   source, library, compiler, and harness hashes. Keep the existing 1.05 upper
   ratio target; emitted record counts alone do not prove runtime performance.
   The calibrated 11-row matrix now has six passes. All four `keep` rows pass,
   and both bounded partition rows pass. The three full group-sum partition
   rows remain 1.46–1.49x direct; the two count-only diagnostics remain slower
   and are not equivalent-consumer claims. The report is retained in
   `bench/bendlang-main-extension-parity-results.json`.

4. **P1 — Harden the rewrite boundary. In progress.** Keep evaluation bounded
   and pure; use only checked bodies without unsafe or foreign computation.
   Scope cache entries to one immutable checked Book and closed semantic terms. Preserve
   annotations and evaluate every live argument once, in order, under its
   original quantity. Keep the fallback expression unchanged. The current
   evaluator uses a 2,048-step fuel limit and bounded template comparisons; the
   application-spine walk now has the same explicit cap. The full suite checks
   evaluation results, affine rejection, and callback counts. Add focused
   alias/ambiguity/cache tests and define a code-size growth bound before
   proposing the pass upstream.

5. **P2 — Propose the upstream compiler change.** Once template identity is
   adversarially tested and full partition performance is addressed or
   explicitly scoped, move the small pass into `bend2/comp.ts` before lowering
   so JS and native share it. Add Bend tests for static callbacks, independent
   source adapters, dynamic fallback, template-instance identity, and affine
   behavior. Run
   upstream's current test gate from an archive of `bendlang/main`. The
   transducer library remains an ordinary consumer and example.

## Options considered

The recommended choice remains a general checked-term specialization in the
compiler. A recognizer for transducer names or reducer constructors would
duplicate library semantics and would not scale to custom reducers or sources.
The current change establishes this boundary for closed reducer factories,
but the buffered partition consumer still pays to build/reverse each group
list and then traverse it in `sum_group`; the generated code shows both passes
and the `Continue`/`Stop` state wrappers. The list creation and traversal are
observed; their exact share of the 1.46–1.49x timing gap is an inference.

There are two viable next directions. A general checked-term List
producer/consumer fusion could remove the temporary group when a downstream
consumer immediately folds it, and could benefit other Bend List pipelines;
it has high correctness and implementation effort around affine ownership,
early termination, and effects. A new chunk/fold sink contract could avoid
materializing groups for compatible consumers while leaving `partition_all`
semantics intact, but it expands the reducer API and must remain source
independent. The next experiment should measure those options against the
current result before adding a partition-specific compiler rule.

## Stop conditions

The checked-term insertion point and closed-pipeline record elimination are
now supported by the full suite. The `term_compare` fallback has not been
adversarially validated, and full buffered partition group-sum still exceeds
the 1.05 upper ratio bound. Both remain blockers for an upstream promotion.
Do not claim universal full fusion or direct-loop parity. The current evidence
supports the static `keep` pipelines and bounded partition cases on main.

The other checks are: stale cache after instance mutation; changed evaluation
order or duplicated live values; unchecked code growth; backend divergence; a
no-record assertion hiding wrong code; and microbenchmarks hiding a pipeline
regression. Scope cache entries to one immutable Book, check callback counts and
affine cases, bound evaluation and expansion, rewrite before both emitters, pair
code-shape checks with output oracles, and use the calibrated paired suite. A
failed gate leaves the candidate as an experiment and narrows the next step to
that specific failure.
