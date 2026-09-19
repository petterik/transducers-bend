# Automatic scalar-selection experiment

**Next implementation priority:** [bounded loop specialization](STRATEGY.md),
supported by new diagnostic measurements and a local proof check. Automatic
caller discovery/cloning and small-input profitability are not yet implemented.

**Current implementation:** [typed guarded scalar specialization](AUTOMATIC.md),
prepared with `prepare_guarded.py`. It derives the successful transition
automatically and reaches near-handwritten local CPU timings. The older
`prepare.py` and C-text selection experiment below remain unchanged.
The [promotion review](PROMOTION.md) now records a fallback-heavy outlining
regression and broader correctness checks; default enablement remains deferred.

Newer result: [controlled generated-C ablations](ABLATION.md) identify a substantially
better target: guarded specialization plus unchanged-field summaries across a cold
fallback. That experiment reaches near-handwritten timing on full/early mixed and
predictable ranges. The narrow selection pass described below is retained as an
earlier experiment, not the preferred implementation path.

Status: implemented in an isolated compiler copy; **not a performance fix yet**.
The sibling compiler and production transducer library are unchanged.

`python3 bench/compiler/prepare.py` copies the pinned sibling compiler (including
its effect files), applies the emitter integration, runs grammar tests, and checks
that the rule fires on `tests/scalar_codegen.bend`. It prints the experimental
main.ts path, which can be passed to `tests/run.py --bend-main` and
`bench/range.py --bend-main`. Temporary artifacts are retained for inspection.

The emitter considers only two-arm Boolean matches with unboxed outputs. It
records each emitted arm and accepts at most 32 straight-line assignments, eight
outputs, and 2048 characters per expanded expression. The expression grammar is
limited to materialized scalar inputs, integer literals, and an explicit list of
total wrapping/comparison U32_BIN operations. Local u32 truncation is retained.
Each output becomes a C conditional selection. Nat matches and their count guards
are not transformed. Unknown operations, calls, allocation, ownership operations,
checked arithmetic, shifts, division and floating-point operations are rejected.

This does not speculate arbitrary callbacks. The emitted selections are also lazy
C expressions; Clang remains responsible for deciding whether to use conditional
instructions. It does not guarantee branchless machine code or profitability.
The unit tests exercise syntax rejection, output alias restrictions and truncation;
the Bend test covers multiple outputs, U32 wrapping and a dynamically rejected
overflowing Nat successor. Both production and experimental compilers are checked
with the full library suite. This is not a formal proof or full upstream gate run.

[First measurements](scalar-select-first-results.json), six retained samples per case:
the unchanged generic pipeline remains 329.5 ms mixed full-range versus 93.5 ms
handwritten; mixed early is 138 vs 103 ms. This narrow pass does **not** reproduce
the manual prototype's speedup. The hot branches contain helper calls with nested
count guards and checked Nat reconstruction, so the conservative rule cannot
select their scalar updates yet.

Next required work: a scoped, bounded scalar-region representation that can expose
those helper bodies, retain count guards, and prove which reconstructed arithmetic
is total. A trial of routing scalar flat calls directly through the existing inline
emitter failed with an unbound-binder error in completion.bend and was removed.
That shortcut did not preserve the native-helper binder scope. Do not broaden the
selection grammar to admit these calls or erase their checks to make a benchmark pass.
