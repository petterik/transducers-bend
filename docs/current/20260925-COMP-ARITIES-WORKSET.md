---
created_at: 2026-09-25T13:30:00+02:00
updated_at: 2026-09-25T13:30:00+02:00
status: complete
---

# Fixed-arity affine composition through `comp5`

The prototype library now exposes `comp2`, `comp3`, `comp4`, and `comp5`.
Each function takes independently constructed affine stages in source order,
retains the distinct intermediate types and closed reducer providers, and
delegates to the existing binary `compose`. Callers supply no type or provider
arguments on the isolated template-inference compiler. An ordinary
homogeneous List of stages would lose those differing types and providers.
No new syntax or stage-specific compiler rule was added.

[`rank2_comp_arities.bend`](../../experiments/affine_xf/rank2_comp_arities.bend)
checks all four arities, a `U32 → Nat` stage inside `comp3`, and
`comp2(comp5(...), comp5(...))` with ten stages. JS and native return the same
independent results. Reusing one stage twice and connecting incompatible
stage types are rejected. A `comp5` containing `take(0)` also leaves a custom
Bag destination unchanged and runs its completion once in
[`rank2_auto_sources.bend`](../../experiments/affine_xf/rank2_auto_sources.bend).

The confidence pass found a code-generation boundary. With the prior static
callback pass, nine or ten nested stages could emit runtime `Reducer` records
even though the program checked and returned the right answer. The pass
rejected an exact template-instance key longer than 32 KB before trying its
existing normalized lookup. Checked annotations can lengthen that exact key
while the normalized spelling still satisfies its own 32 KB bound. The small
change in [`static_callback_pass.ts.inc`](../../bench/compiler/static_callback_pass.ts.inc)
skips only the oversized exact lookup and proceeds to the bounded, unique,
checked-instance fallback. It does not raise the expansion, depth, or key
limits. The ten-stage fixture now emits no runtime `Reducer` record.

The targeted inference probe passes all nine positive fixtures on JS/native
and its expected checker refusals. The pinned `bendlang/main` candidate's
full 33-case suite also passes. This establishes correctness and reducer
erasure for the tested arities and ten-stage composition. Native timing for
longer compositions remains a separate performance measurement; generated
code shape alone does not prove parity with a direct loop.
