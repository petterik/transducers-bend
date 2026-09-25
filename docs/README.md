---
created_at: 2026-09-20T20:26:35+02:00
updated_at: 2026-09-25T22:14:00+02:00
status: current
---

# Transducer documentation

Substantive documents use `YYYYMMDD-TITLE.md`, with the date taken from their
`created_at` field. `README.md` stays undated as the stable index. A document's
filename records its origin, not its latest revision; check `updated_at` and
`status` in the front matter for that. The folders separate current work,
foundation material, reviews, and historical experiments.

Start with the [new traversal and indexed stages](current/20260925-TRAVERSAL-INDEXED-TRANSDUCERS.md)
and the [public API release comparison](current/20260925-PUBLIC-LIST-MAP-FOLD.md),
which tests the current API against a direct Bend fold and `Base.List.map`
followed by `List.foldl`. The [no-stop integration report](current/20260925-NO-STOP-PUBLIC-INTEGRATION.md)
records the compiler and source contract, while the
[Branch performance reassessment](current/20260925-BRANCH-LAYOUT-REASSESSMENT.md)
explains why a single compiled program's timing gap cannot be treated as a
stable transducer cost. Earlier documents are dated checkpoints.

## Current

Read these first for the current contract and measured limits:

- [Traversal and indexed transducers](current/20260925-TRAVERSAL-INDEXED-TRANSDUCERS.md) — drop/while, indexed, take-nth, and cat contracts.
- [Public API and List.map/fold comparison](current/20260925-PUBLIC-LIST-MAP-FOLD.md) — release benchmark and clean-clone gate.
- [No-stop public integration](current/20260925-NO-STOP-PUBLIC-INTEGRATION.md) — current public API and correctness boundary.
- [Branch performance reassessment](current/20260925-BRANCH-LAYOUT-REASSESSMENT.md) — native code-layout sensitivity.
- [Opaque source protocol](current/20260925-OPAQUE-SOURCE-PROTOCOL.md) — current source type and nested stop semantics.
- [Local compiler gate and Array ablation](current/20260925-LOCAL-GATE-ARRAY-ABLATION.md) — current correctness and Array cost boundary.
- [General mapcat and compiler hardening](current/20260925-MAPCAT-COMPILER-HARDENING.md) — raw-fragment API and allocation split.
- [Vec public contract](current/20260925-VEC-PUBLIC-CONTRACT.md) — supported ordered Data destinations and sources.
- [Affine `Xf` API workset](current/20260925-AFFINE-XF-API-WORKSET.md) — historical plan, now implemented.
- [Producer/fold region](current/20260925-PRODUCER-STEP-FOLD-REGION.md) — latest map/filter compiler experiment.
- [Transducer fusion ablation](current/20260924-TRANSDUCER-FUSION-ABLATION.md) — static callback and chunk-cost evidence.
- [bendlang/main integration plan](current/20260923-BENDLANG-MAIN-INTEGRATION-PLAN.md) — current upstream compiler boundary.
- [bendlang/main baseline](current/20260923-BENDLANG-MAIN-BASELINE.md) — pinned compiler and validation.
- [Array/partition experiment](current/20260923-ARRAY-PARTITION-EXPERIMENT-PLAN.md) — completed investigation.

Earlier checkpoints and reviews remain available for their specific findings:

- [Follow-up repair proposal](current/20260920-FOLLOWUP-REPAIR-PROPOSAL.md) — proposed 2026-09-20.
- [Adversarial design review](current/20260920-DESIGN-REVIEW.md) — created 2026-09-20.
- [Architecture work plan](current/20260920-DESIGN-WORK-PLAN.md) — created 2026-09-20.
- [Implementation repair plan](current/20260920-IMPLEMENTATION-REPAIR-PLAN.md) — created 2026-09-20.
- [Implementation review](review/20260920-IMPLEMENTATION-REVIEW.md) — created 2026-09-20.
- [Priorities](current/20260919-PRIORITIES.md) — created 2026-09-19, revised for the current review.
- [Handoff](current/20260919-HANDOFF.md) — created 2026-09-19, revised for the current review.
- [Final validation](current/20260920-FINAL-VALIDATION.md) — created 2026-09-20.
- [Scoped constructor facts](current/20260920-SCOPED-FACTS.md) — created 2026-09-20.
- [Local representation elimination](current/20260920-LOCAL-REPRESENTATION.md) — created 2026-09-20.
- [Extension/direct parity](current/20260920-EXTENSION-PARITY.md) — created 2026-09-20.
- [Configured API checkpoint](current/20260920-CONFIGURED-API.md) — created 2026-09-20.

## Foundation

These documents explain the library contract, laws, implementation, and design
constraints. They remain relevant background, but their historical status notes
must be read alongside the current review:

- [Library design](foundation/20260919-DESIGN.md) — created 2026-09-19.
- [Implementation status](foundation/20260919-IMPLEMENTATION.md) — created 2026-09-19.
- [Adding a reducible source](foundation/20260919-EXTENDING.md) — created 2026-09-19.
- [Laws and proof status](foundation/20260919-LAWS.md) — created 2026-09-19.
- [Optimization decision](foundation/20260919-OPTIMIZATION.md) — created 2026-09-19.
- [Confidence review](foundation/20260919-CONFIDENCE.md) — created 2026-09-19.
- [Deferred ergonomics](foundation/20260919-ERGONOMICS.md) — created 2026-09-19.

## Historical

These records capture the earlier fusion direction and are evidence for their
own revisions, not current implementation status:

- [Fusion direction](archive/20260919-FUSION.md) — created 2026-09-19.
- [Fusion execution plan](archive/20260919-FUSION-EXECUTION-PLAN.md) — created 2026-09-19.
- [Legacy reducer API guide](archive/20260925-LEGACY-REDUCER-API.md) — former README section for the original explicit API.

Benchmark reports remain under `bench/`, and source-level wrong-code reproducers
remain under `review/`. Those artifacts are linked from the current documents
where they provide active acceptance evidence.
