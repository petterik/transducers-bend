# Scoped optimization facts

Status: first executable boundary test complete; the general region data
structure remains the next compiler implementation.

An optimization summary is valid only with the conditions under which it was
derived. The minimum summary for a scalar transition is:

```text
inputs and their typed layouts
entry precondition / path facts
returned fields and their expressions
unchanged fields
failure and conditional-evaluation obligations
back-edge arguments, if the summary is used for a loop
```

Facts are attached to actual values and dominated program points. A same-layout
value from another caller is not enough. At a branch join, retain only facts
supported by every incoming path. An opaque callback preserves its order and
conditional execution; it invalidates only the facts that depend on its result.
If a fact crosses a continuation/FID boundary, each possible entry frame needs
to be represented. Otherwise the compiler must keep the generic path.

## Current boundary test

`scoped_fact_boundary.bend` calls one typed loop from a normal caller and from a
same-layout exceptional caller. `test_scoped_facts.py` requires the candidate
to retain a guarded loop marker, a generic fallback, and identical JS/native
results. The candidate's existing loop proof records the guard and back-edge
paths; the test treats those records as diagnostics, not as a proof by itself.

The test complements the 200,000-state sanitizer comparisons in
`test_auto_loop.py`. Those compare the specialized helper with its generic body
across arbitrary counters, tags, sums, cookies, and permits. The tree entry
counterexample remains a separate refusal gate because the tree pass has no
entry/continuation proof yet.

## Implementation direction

Build the first typed region over the compiler's existing typed terms/ANF rather
than adding a second whole compiler. Give summaries stable value identities,
branch edges, and scoped preconditions. Resolve actual call arguments against a
summary before using its fast form. Keep the original helper as a valid fallback
when the proof or budget fails. Move facts before continuation lowering where
possible; do not route raw continuation frames through a root helper based on a
layout coincidence.

The current candidate has useful pieces (`GLProbe.guard`, back-edge paths, and
bounded rejection), but those pieces are not yet a general summary interface.
This document is the design contract for the next workset, not a claim that the
experimental tree optimizer is ready to re-enable.
