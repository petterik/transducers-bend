---
created_at: 2026-09-20T20:26:35+02:00
status: current
---

# Transducer documentation

Every document carries a `created_at` timestamp taken from the first Git commit
that introduced it. The folders separate the current decision record from the
foundation documents and historical exploration.

The latest [follow-up implementation review](review/FOLLOWUP-IMPLEMENTATION-REVIEW.md)
found a reproduced wrong-code bug in the isolated facts compiler and an incorrect
direct keep benchmark reference. Its acceptance assessment supersedes the earlier
checkpoint summaries.

The [proposed repairs](current/FOLLOWUP-REPAIR-PROPOSAL.md) compare options for
each finding, prioritize them by impact/effort/value, and specify acceptance
conditions. This is a proposal for review, not an implementation completion record.

## Current

These documents describe the accepted direction and the work still required:

- [Follow-up repair proposal](current/FOLLOWUP-REPAIR-PROPOSAL.md) — proposed 2026-09-20.
- [Adversarial design review](current/DESIGN-REVIEW.md) — created 2026-09-20.
- [Architecture work plan](current/DESIGN-WORK-PLAN.md) — created 2026-09-20.
- [Implementation repair plan](current/IMPLEMENTATION-REPAIR-PLAN.md) — created 2026-09-20.
- [Implementation review](review/IMPLEMENTATION-REVIEW.md) — created 2026-09-20.
- [Priorities](current/PRIORITIES.md) — created 2026-09-19, revised for the current review.
- [Handoff](current/HANDOFF.md) — created 2026-09-19, revised for the current review.
- [Final validation](current/FINAL-VALIDATION.md) — created 2026-09-20.
- [Scoped constructor facts](current/SCOPED-FACTS.md) — created 2026-09-20.
- [Local representation elimination](current/LOCAL-REPRESENTATION.md) — created 2026-09-20.
- [Extension/direct parity](current/EXTENSION-PARITY.md) — created 2026-09-20.
- [Configured API checkpoint](current/CONFIGURED-API.md) — created 2026-09-20.

The repair plan and implementation review are the best starting points. The
current work remains partial: the tree rewrite is refused, while static
composition, scoped facts, local representation elimination, configured API
design, and extension performance still require implementation or stronger
evidence.

## Foundation

These documents explain the library contract, laws, implementation, and design
constraints. They remain relevant background, but their historical status notes
must be read alongside the current review:

- [Library design](foundation/DESIGN.md) — created 2026-09-19.
- [Implementation status](foundation/IMPLEMENTATION.md) — created 2026-09-19.
- [Adding a reducible source](foundation/EXTENDING.md) — created 2026-09-19.
- [Laws and proof status](foundation/LAWS.md) — created 2026-09-19.
- [Optimization decision](foundation/OPTIMIZATION.md) — created 2026-09-19.
- [Confidence review](foundation/CONFIDENCE.md) — created 2026-09-19.
- [Deferred ergonomics](foundation/ERGONOMICS.md) — created 2026-09-19.

## Historical

These records capture the earlier fusion direction and are evidence for their
own revisions, not current implementation status:

- [Fusion direction](archive/FUSION.md) — created 2026-09-19.
- [Fusion execution plan](archive/FUSION-EXECUTION-PLAN.md) — created 2026-09-19.

Benchmark reports remain under `bench/`, and source-level wrong-code reproducers
remain under `review/`. Those artifacts are linked from the current documents
where they provide active acceptance evidence.
