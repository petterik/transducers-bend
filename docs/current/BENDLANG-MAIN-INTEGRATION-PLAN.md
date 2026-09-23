---
created_at: 2026-09-23T14:20:13+02:00
updated_at: 2026-09-23T16:33:34+02:00
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
`e2f59c5c847cd77d6992d734ad54a26780d3ac613dc60dfab88c1f0bf413e9b0`. Its
self-check passes the API fixture and five static-callback regressions on JS
and native. The full library code-shape run passes the first six fixtures, then
stops at `keep_partition.bend`: three runtime `Reducer` records remain. That
program's output is correct, but the requested fusion is incomplete. The old
fork candidate is not a comparison target or supported fallback.

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

1. **P0 — Prove template-instance lookup is safe.** The current candidate
   rejects direct evaluation of generic definitions, uses an existing checked
   `x == 0` instance, tries an exact `book.tmps` key, then uses bounded
   `term_compare` and refuses ambiguous matches. Test multiple values and
   types, explicit annotations, aliases, nested templates, erased arguments,
   recursion, and affine results. If any identity case remains ambiguous,
   retain the expression. Ask upstream for a read-only checked-instance ID only
   if the checked Book cannot resolve identity safely. Do not call `def_inst`
   from code generation: it can recheck terms and mutate the Book.

2. **P0 — Remove the remaining closed-pipeline reducer records.** The current
   candidate leaves three named factory sites in `keep_partition.bend`
   (`take` and `partition_all`) after the first six integration fixtures pass.
   Trace why those factories cross into runtime code. The likely general fix is
   to specialize calls whose reducer argument is a closed checked value before
   lowering, while dynamic reducer arguments keep the existing path. Do not
   fold every closed call to a constructor: that experiment increased emitted
   records. Keep zero-record assertions paired with JS/native output and
   callback-count checks.

3. **P1 — Measure the whole pipeline on the exact main snapshot.** Run the
   calibrated transducer/direct matrix on native and the independent semantic
   oracle on JS. Include full and early stop, type-changing `keep`, bounded and
   full `partition_all`, and List/range/tree/Array where supported. Record the
   source, library, compiler, and harness hashes. Keep the existing 1.05 upper
   ratio target; emitted record counts alone do not prove runtime performance.

4. **P1 — Harden the rewrite boundary.** Keep evaluation bounded and pure; use
   only checked bodies without unsafe or foreign computation. Scope cache
   entries to one immutable checked Book and closed semantic terms. Preserve
   annotations and evaluate every live argument once, in order, under its
   original quantity. Keep the fallback expression unchanged. Add a code-size
   growth bound before proposing the pass upstream.

5. **P2 — Propose the upstream compiler change.** Once both P0 gates pass,
   move the small pass into `bend2/comp.ts` before lowering so JS and native
   share it. Add Bend tests for static callbacks, independent source adapters,
   dynamic fallback, template-instance identity, and affine behavior. Run
   upstream's current test gate from an archive of `bendlang/main`. The
   transducer library remains an ordinary consumer and example.

## Options considered

The recommended choice is a general checked-term specialization in the
compiler. A recognizer for transducer names or reducer constructors could
remove today's records sooner, but every new reducer and source would need more
compiler rules, duplicating library semantics. A library-only rewrite keeps
the fold source-independent, but current evidence shows that closed reducer
values still reach runtime factory calls, so it has not established the
requested compiler-wide fusion. A checker-provided instance ID is the fallback
only if the existing checked Book cannot supply safe identity without
mutation.

## Stop conditions

The checked-term insertion point is well supported, but the current
`term_compare` fallback has not been adversarially validated and
`keep_partition` is not fully fused. Both are blocking gates. Do not claim full
fusion or upstream readiness until the template-instance matrix and recursive
source fixture pass on JS and native, and the calibrated whole-pipeline rows
remain within the agreed bound.

The other checks are: stale cache after instance mutation; changed evaluation
order or duplicated live values; unchecked code growth; backend divergence; a
no-record assertion hiding wrong code; and microbenchmarks hiding a pipeline
regression. Scope cache entries to one immutable Book, check callback counts and
affine cases, bound evaluation and expansion, rewrite before both emitters, pair
code-shape checks with output oracles, and use the calibrated paired suite. A
failed gate leaves the candidate as an experiment and narrows the next step to
that specific failure.
