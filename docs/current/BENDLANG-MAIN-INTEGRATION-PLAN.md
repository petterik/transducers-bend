---
created_at: 2026-09-23T14:20:13+02:00
status: proposed
---

# Integrating transducer fusion with bendlang/main

This is a plan for review, not a claim that the port is complete. The target is a
general compiler optimization for **statically known callback values**, independent
of `Reducer`, `Tree`, or any particular transducer. A new reducible source should
get the same optimization when it passes a closed reducer recipe. The library
can then add `remove`, `keep`, `partition_all`, and other stages without new
compiler recognizers. `keep` remains the existing composition of `map` and
optional-value flattening.

## Decision and evidence

Target `bendlang/main` commit
`26659268dbdf411696bf90d28e722783dceae0f8` (the fetched upstream ref),
with `bend2/comp.ts` SHA-256
`10afb08dd55a52bfbb88fdf84534cebdc000bdf7820c69cee1d6bb3fcfaf7d7b`.
Keep the current fork-main candidate at
`15ae0c86f3193b8f645b4bedbc438655b648d0da` as a measured control until
the replacement passes the full gates. Archive Git refs into temporary compiler
candidates; do not edit the sibling `../bend` checkout. In particular, its
`AGENTS.md` reserves `bend2/bend.ts` as the language/checker and says not to
edit it.

A temporary port of only the current `def_body` specialization (one changed
`Name` signature and one changed source hash) compiled and ran the focused
API and five callback fixtures on JS and native. It then failed
`tests/extensions.bend`: upstream candidate JS retained **two** runtime
`Reducer` records, versus **zero** with the fork-main facts candidate. The
upstream output was semantically right (`[1, 2]`, `[]`, `0`, `7`), but its
recursive tree step rebuilt a reducer and called `T.step` dynamically. Passing
direct `T.take(...)` expressions did not fix it. The first bad upstream commit
is `ee7efc91e9c6695969f025c875ef81f6ea1f8af0`, which changed template
instantiation: a checked `F~n` instance is minted at a live call. Thus passing
the narrow self-check is not enough to switch the default compiler.

The current evaluator's `Ref` case assumes every `Def.e` is an ordinary body.
On new main, a generic `Def.x > 0` already has its `~` binders removed for
checking. Evaluating it as an ordinary function can fail (as seen when
`into_list` becomes a `Reducer` before its `~U32` application), or worse,
produce an apparently successful but wrong static value. This is a correctness
bug in the port, not a mere missed optimization. **No pass may unfold a
generic template directly.**

## Integration point

Keep the compiler optimization in `bend2/comp.ts`, after the source has been
checked and before `def_raise`, call-graph discovery, ownership/layout analysis,
and either backend's emission. The existing `def_body` seam already gives both
JS and native the same typed higher-order term; materialize a rewritten/lowered
body once per definition. This avoids duplicated backend rules and means the
later compiler sees the actual reachable calls. Preserve a semantic fallback:
on any unproved static head, emit the original checked term.

The pass should recognize a **computed function head** that can be reduced to
a lambda from closed, checked definitions and constructor fields. It should
replace only the application whose head has been proved, bind live/dynamic
arguments once, retain annotations and quantities, and recurse within a
bounded budget. Bare named function calls remain ordinary calls. Do not add
rules keyed to transducer names, constructor tags, or source adapter shapes.
The compiler's existing `def_raise`/ANF/fusion machinery should then optimize
the revealed calls. This is a modest general optimization, not a new lowering
framework.

Separate the pass into a small maintained TypeScript source fragment or a
clearly isolated patch module plus a thin `prepare_static.py` archive/patch
driver. The current hundreds of lines of embedded TypeScript and exact-text
emitter substitutions make review and upstream rebases unnecessarily hard.
While upstream integration is being tested, keep the source hash/anchor guard
and provenance manifest. Once proposed upstream, move the reviewed pass into
`comp.ts` and add upstream-native tests; the Python driver remains a local
comparison harness.

## The critical template-instance decision

`book.tmps[generic]` maps the **syntax key** of closed `~` arguments to a
checked instance name, and that instance's `Def.e` is safe to consider.
However, the checked term seen by the compiler can contain checker-added
`Ann` nodes. A raw `term_key(term_lower(arg))` then differs from the key
`def_inst` used. Recursively stripping annotations is not justified: source
annotations can affect elaboration or distinguish valid instantiations.

Recommended rule: resolve an applied generic only to an **already checked,
unambiguous instance** and evaluate that instance's body. First determine
whether the compiler can recover the original argument identity from the
checked term and `book.tmps` without guesswork. Instrument generic calls in
the tree fixture and a matrix of same-generic/different-argument cases;
compare the original syntax key, checked argument, and selected `F~n`. The
implementation must use a documented equality/canonicalization rule whose
soundness follows from the checked representation. If an exact rule is not
available in `comp.ts`, stop this workset and seek a small upstream checker
interface that carries the checked instance identity into the compiled term;
do not infer identity from erased annotations, instance numbering, or a merely
similar type. `../bend/AGENTS.md` rules out locally editing `bend.ts` as an
expedient. An unresolved generic is a refusal, never a speculative unfold.

`def_inst` itself should not be called casually from code generation: it
rechecks arguments and mutates the book by minting instances. If a future
compiler interface is needed, it should expose a read-only checked identity,
or the checker should preserve the instance `Ref` where the compiler can use
it. Compiler-local lookup is preferable only after the equality proof and
adversarial tests above. This is the design gate that determines whether the
port can stay entirely within `comp.ts`.

## Worksets, in order

1. **Lock the upstream baseline and failure.** Record both compiler SHAs,
   output/codegen counts, and `extensions` failure. Add a minimal generic
   template regression where the old pass would unfold `Def.x > 0` incorrectly,
   and add a positive independently defined recursive source case. Assert
   semantic output on JS/native and absence of runtime reducer construction
   only for statically closed cases. Include a dynamic-recipe case that must
   retain the fallback. Commit this evidence before changing the pass.

2. **Repair static evaluation and instance identity.** First reject every
   generic `Def.x > 0` in the evaluator. Then implement only the proved
   checked-instance resolution from the decision gate above. Require an
   existing `Def` with `x == 0`, a completed checked body, no unsafe/foreign/
   bang side effects, and an exact argument identity. Refuse missing,
   ambiguous, cyclic, over-budget, or dynamic heads. Do not unfold through
   runtime computations. Keep the original term on refusal. Test same template
   at multiple types and values, explicit annotations, aliases, nested
   templates, erased `~` arguments, recursion, and affine results. Commit the
   compiler-only fix as one reviewable workset.

3. **Simplify the pass and its cache.** Make the pure resolver and rewrite
   boundaries explicit. Key memoization to one checked, immutable book and a
   closed term, including all semantics-relevant annotations/instance
   identities. Cache successful and refused results distinctly; do not reuse
   results after any instance table mutation. Keep a fixed evaluation-fuel,
   rewrite-count, and emitted-growth budget. Reify the rewritten body once.
   Verify live arguments are evaluated exactly once in original order;
   quantities, ownership, stop behavior, and failure behavior are unchanged.
   The safe fallback must be byte-for-byte the original checked expression
   where possible. Commit this cleanup separately from the correctness fix.

4. **Promote the baseline only after full gates.** Change `prepare_static.py`
   to default to `bendlang/main` and pin the new reviewed source hash. Run
   all 22 Bend fixtures on JS and native, including `extensions`; run the
   existing adversarial/static-callback checks and source-shape checks. Run
   upstream's available test gate for the archived candidate. Compare
   generated JS/C for hot source loops, runtime record counts, compile time,
   binary/code size, and checksums. Preserve a selectable old fork-main
   candidate for A/B runs. Do not weaken the `extensions` record assertion.
   Commit the default switch only after these pass.

5. **Measure performance before more compiler changes.** Re-run the existing
   paired, calibrated List/range/tree/Array and extension rows against
   handwritten direct Bend and the old candidate, in both backends where
   supported. Include full and early stop, type-changing `keep`, and bounded
   and full `partition_all`. A faster upstream `Array.map` or changed layout is
   useful only if these whole-pipeline rows improve without changing output.
   Retain the documented parity target and confidence bounds; investigate any
   regression before claiming a win.

6. **Port optional emitter work only if justified.** The diagnostics hook
   appears to need a `Name` signature update and can be ported independently.
   The scoped constructor-facts patch has multiple broken anchors because
   upstream rewrote argument, constructor, and match emission. Do not replay
   it textually. If workset 5 shows a material regression traceable to lost
   constructor facts, redesign the smallest equivalent fact flow on the new
   emitter and prove branch-local dominance/ownership; run the prior
   wrong-code reproducer, JS/native differential tests, and calibrated matrix.
   Otherwise leave it out. Keep guarded tree/loop experiments separate until
   their own proof and profitability gates are met.

7. **Prepare language-level adoption.** Once the general pass and regressions
   pass on current upstream, express it as a compact `comp.ts` change with
   upstream Bend fixtures for static callbacks, template instances,
   independent sources, dynamic fallback, and affine behavior. Propose the
   minimal checker identity interface only if workset 2 proved it necessary.
   The transducer library stays a consumer/example, not a compiler dependency.

## Confidence checks and stop conditions

The design is strong on *where* to optimize and on preserving a refusal path.
It is **not yet factually proven** that latest Bend exposes enough identity to
resolve every closed generic in `comp.ts` alone. Treat that as a blocking
implementation gate, not a detail to patch by intuition. No declaration of
full fusion or upstream readiness until the recursive extension source and
the multi-instance adversarial matrix pass on both backends.

The other loopholes and their checks are: (a) stale cache after instance
minting—scope or invalidate on mutation; (b) call-by-value changes—test
single evaluation, order, and affine use; (c) unchecked expansion/code
growth—bound fuel, rewrites, and generated size; (d) backend divergence—apply
the rewrite before both emitters and run both; (e) a no-record assertion
masking wrong code—pair every source check with output/oracle comparisons;
(f) microbenchmarks masking whole-program regressions—use the existing
calibrated paired suites. Each failed gate keeps the old candidate as default
and yields a narrower documented next decision rather than a speculative
fallback that silently loses fusion.
