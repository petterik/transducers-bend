---
created_at: 2026-09-23T14:20:13+02:00
updated_at: 2026-09-24T13:58:08+02:00
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

### Refreshed baseline — 2026-09-24

The local `bendlang/main` ref is `2f50df1ed36fcc3ebe6c75a2046e94001a44645d`.
Its `bend2/comp.ts` hash is
`34783e2779f23b0f7be586f70130292ea367fbe74d3d12b327d434633dc93850`. The
static-callback patch was reapplied in an isolated candidate and passed the
identity self-test, five focused JS/native fixtures, and all 23 library tests
on both backends. Full hashes and commands are recorded in
[`20260923-BENDLANG-MAIN-BASELINE.md`](20260923-BENDLANG-MAIN-BASELINE.md).

A matched native ablation now compares raw upstream, the static-callback
candidate, a handwritten materializing fold, and a direct fold. It uses both
sum and order-sensitive consumers. The candidate is 8.4–9.4x faster than raw
upstream on the public List-transducer rows, but is still 1.4–1.6x slower than
the materialized control; materialized is 1.6–2.0x slower than direct. The
candidate constructs one additional List Cons per input, while the handwritten
materialized path reuses consumed source nodes. Full timings, allocation
counts, confidence bounds, and the next experiment are recorded in
[`20260924-TRANSDUCER-FUSION-ABLATION.md`](20260924-TRANSDUCER-FUSION-ABLATION.md).

A matched retained-chunk run covers the negative case where every emitted
chunk stays alive through a later checksum traversal. The static-callback
candidate is 4.8–5.5x faster than raw upstream for the List lane and 6.4–6.5x
faster for the fixture Array lane. In the retained List lane, candidate heap
requests equal the List Cons cells required by the output; raw upstream makes
another 4.25–4.67 heap requests per input. Generated C shows active
`Continue`/`Stop`/`Partitioning` terms in raw upstream and no runtime
references to those tags in the candidate. The candidate Array lane does
request twice as many List Cons cells as raw, a separate unexplained fixture
detail. Full samples, allocation counters, generated-source hashes, and
limits are in the ablation document's retained-chunk section.

The prior baseline below is superseded for compiler identity and validation.
Its performance results remain evidence for the older candidate only. The
current Array width sweep used raw upstream at this refreshed commit; the
matched List fold ablation is the relevant measurement of the specialization
pass and is separate from that Array sweep.

### Previous checkpoint — superseded

The refreshed `bendlang/main` ref is
`6a77e1246c351055cb15031267a7c76c87036cbc`. Its `bend2/comp.ts` is unchanged
at SHA-256 `10afb08dd55a52bfbb88fdf84534cebdc000bdf7820c69cee1d6bb3fcfaf7d7b`
from the previously tested upstream commit. The new commits add named-package
imports in the checker and guide, not compiler changes. The build harness now
reads only the `bendlang/main` remote-tracking ref; it does not accept the fork's
`origin/main`. The sibling checkout remains unmodified.

The isolated candidate's compiler hash is
`04d2f814c799808efd136f5a56f22236d0dd128045dbf562c227d2f17fae992d`. Its
identity self-test and five static-callback fixtures pass on JS and native.
The complete library run passes 23/23 files on both backends, including the
code-shape gate for `keep_partition`; no `Reducer` or `Reduction` records
remain in the gated fixtures. The old fork candidate is not a comparison
target or supported fallback.

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

1. **P0 — Finish adversarial template-instance checks. Completed for the
   candidate.** The pass rejects direct evaluation of generic definitions and
   selects only an existing checked `x == 0` instance. It tries the exact
   `book.tmps` key, then a bounded structural key that removes erased
   annotations/spans and restores the checked lambda's default `Lone` quantity.
   It does not normalize or unfold terms to compare identities. Ambiguous,
   alias-only, missing, and oversized matches refuse specialization. Run
   `python3 bench/compiler/prepare_static.py --identity-self-test` for the
   focused alias, ambiguity, recursive-term, table/spine-limit, and per-Book
   cache checks. The regular suite also exercises checked annotation matching
   in real reducer pipelines. Keep the original expression on every uncertain
   identity. Do not call `def_inst` from code generation: it can recheck terms
   and mutate the Book.

2. **P0 — Remove closed-pipeline reducer records. Completed.** The
   annotation-aware checked-spine lookup resolves the existing reducer
   instances used by `keep_partition` without recognizing reducer names or
   constructors. `tests/run.py` now passes its full no-record, semantic,
   callback-count, lifecycle, and bounded-law checks on JS and native. Keep the
   dynamic-reducer fallback covered as later changes build on this.

3. **P1 — Measure the whole pipeline on the exact main snapshot. Completed on
   the prior candidate checkpoint; current partition comparison completed in
   the ablation.** The earlier calibrated native
   transducer/direct matrix covers 11 sequential List cases: full and early
   stop, type-changing `keep`, and bounded and full `partition_all`. The full
   library suite separately checks semantics on JS and native. Record the
   source, library, compiler, and harness hashes. Keep the existing 1.05 upper
   ratio target; emitted record counts alone do not prove runtime performance.
   The calibrated 11-row matrix has six passes. All four `keep` rows pass, and
   both bounded partition rows pass. The three full group-sum partition rows
   remain 1.455–1.491x direct by the upper bound; the two count-only diagnostics
   remain slower and are not equivalent-consumer claims. The report is retained
   in `bench/bendlang-main-extension-parity-results.json` and matches compiler
   hash `04d2f814c799808efd136f5a56f22236d0dd128045dbf562c227d2f17fae992d`.

4. **P1 — Harden the static-callback rewrite boundary. In progress.** Keep evaluation bounded
   and pure; use only checked bodies without unsafe or foreign computation.
   Scope cache entries to one immutable checked Book and closed semantic terms.
   Preserve annotations and evaluate every live argument once, in order,
   under its original quantity. Keep the fallback expression unchanged. The
   evaluator uses a 2,048-step fuel limit; the application-spine walk is capped
   at 2,048 nodes; identity keys are bounded to 8,192 nodes, 16,384 characters
   per argument, 64 arguments, and 64 table entries. The full suite checks
   evaluation results, affine rejection, and callback counts. Define a
   generated-code growth bound before proposing the pass upstream.

5. **P2 — Consider an upstream compiler change only after the fusion
   prototype clears its gates.** Template identity is already
   adversarially tested; now measure a source-independent fold-fusion rule with
   semantic negative cases and bounded code growth. Current allocation and C
   evidence does not justify a separate Control-record rewrite: the candidate
   already removes those runtime terms in the retained List pipeline. If the
   producer/consumer rule is valuable and safe, move it into `bend2/comp.ts`
   before lowering so JS and native share it. Add Bend tests for static
   callbacks, independent source adapters, dynamic fallback, template-instance
   identity, and affine behavior. Run upstream's current test gate from an
   archive of `bendlang/main`. The transducer library remains an ordinary
   consumer and example.

## Options considered

The recommended direction remains a general checked-term specialization, not
a recognizer for transducer names or reducer constructors. New matched
measurements show the public `partition_all` pipeline is still 1.4–1.6x slower
than a handwritten materializing control. The latter is 1.6–2.0x slower than a
direct loop, with the same pattern under an order-sensitive rolling hash. This
separates a remaining callback/state gap from the cost of creating and
traversing chunks; the exact causes within each gap still need a compiler
prototype to establish.

Allocation evidence also changes the buffer-reuse question. The candidate
constructs one extra List Cons per input item in the transducer path. The
handwritten materializing loop has zero timed List Cons constructions because
generated C rewrites consumed, uniquely owned source nodes as chunk nodes. This
is source-cell reuse, not proof that a previously emitted chunk can be reused.
The current compiler ownership proof is sufficient for that local case, so a
runtime reference-count branch is not justified by these results.

The next workset is the prioritized prototype in
[`20260924-TRANSDUCER-FUSION-ABLATION.md`](20260924-TRANSDUCER-FUSION-ABLATION.md): fuse a known,
fresh List result into a known, single-use fold only when non-escape,
callback-order, effect, affine-use, and stop proofs succeed. Use a custom
producer/fold pair so the optimization cannot pass by recognizing
`partition_all` or transducer names. Retained chunks, unknown consumers, and
effectful callbacks must keep the original path. Defer an explicit reusable
sink until a concrete case shows the checked-term rule cannot safely cover a
useful pipeline; such a sink changes ownership/API contracts and requires
additional source/consumer adapters. Ordinary collection consumers still
materialize their results.

## Stop conditions

The checked-term insertion point, closed-pipeline record elimination, and
bounded structural identity lookup are supported by the full suite and focused
self-tests. Conversion-equal aliases intentionally refuse specialization;
identity ambiguity also refuses specialization. Full buffered partition
group-sum still exceeds the 1.05 upper ratio bound. Do not claim universal full
fusion or direct-loop parity. The current evidence supports the static `keep`
pipelines and bounded partition cases on main.

The other checks are: stale cache after instance mutation; changed evaluation
order or duplicated live values; unchecked code growth; backend divergence; a
no-record assertion hiding wrong code; and microbenchmarks hiding a pipeline
regression. Scope cache entries to one immutable Book, check callback counts and
affine cases, bound evaluation and expansion, rewrite before both emitters, pair
code-shape checks with output oracles, and use the calibrated paired suite. A
failed gate leaves the candidate as an experiment and narrows the next step to
that specific failure.
