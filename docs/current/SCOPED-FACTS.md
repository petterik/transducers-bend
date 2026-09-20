---
created_at: 2026-09-20T21:14:00+02:00
status: current
---

# Scoped constructor facts

> Review update: the [follow-up review](../review/FOLLOWUP-IMPLEMENTATION-REVIEW.md)
> reproduces wrong code in the facts compiler and a broken direct keep oracle.
> Its workset assessment supersedes the completion/acceptance claims below;
> historical individual test results remain recorded evidence.


Status: isolated compiler prototype. This is the first small local rewrite
behind the typed-region plan; it is evidence for the design, not an upstream
compiler change.

The prototype attaches provenance to the compiler's existing emitted `Val`
record. When `emit_ctr` creates a value, it records the constructor name and
the emitted field values. The provenance is rebound when a fused call or a
native specialization changes the field names. A projection drops the fact
instead of guessing from layout identity, and a held alias rebinds the fact
while resetting the old `stat` bit so a runtime local cannot enter the static
image.

At `emit_match`, the fast arm is allowed only when all of these hold:

- the scrutinee carries an exact constructor fact from the value that was
  emitted;
- its representation is unboxed;
- every constructor field is static and has no boxed word; and
- the match contains the recorded constructor arm.

The selected arm receives the original field values directly. This is safe for
the first rule because the fields are pure scalar constants: dropping an
unused field cannot drop a heap root or a checked dynamic computation. Boxed,
affine, projected, mismatched, or otherwise uncertain values take the existing
generic match path. The rule is deliberately local and nonrecursive; it does
not infer facts from equal layouts, call names, prior code generation, or a
whole-program call graph.

The isolated compiler is built by
[`prepare_static.py`](../../bench/compiler/prepare_static.py) with `--facts`.
The fixture uses a dynamic command-line flag to exercise a positive static
constructor and a second constructor with a dynamic field. The candidate and
the sibling compiler agree in native and JS output. The retained report is
[`scoped-constructor-fact-results.json`](../../bench/compiler/scoped-constructor-fact-results.json):

```text
matches: 32   known: 4   selected: 2   rejected: 2
```

The rejected facts are the dynamic-field boundary; the remaining matches use
the ordinary emitter. The full 20-file suite also passes on the isolated
compiler, including the two-output JS-then-native build order. That order found
the alias/static-image regression during review and is now part of the check.

Reproduce the focused proof and the suite with:

```sh
facts=$(mktemp -d /tmp/transduce-facts.XXXXXX)
python3 bench/compiler/prepare_static.py --facts --output-dir "$facts"
python3 bench/compiler/test_scoped_constructor_fact.py \
  --bend-main "$facts/main.ts" \
  --output bench/compiler/scoped-constructor-fact-results.json
python3 tests/run.py --bend-main "$facts/main.ts"
```

This does not close the full typed-region workset. Joins, recursive summaries,
continuation entry proofs, arbitrary affine fields, and general option
constructor elimination remain open. The next representation work should use
this fact boundary to compare a visible `Some`/`None` producer with its direct
consuming reference, while preserving the generic path for opaque producers.
