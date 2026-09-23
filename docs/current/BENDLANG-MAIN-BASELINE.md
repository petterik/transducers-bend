---
created_at: 2026-09-23T14:38:33+02:00
status: current
---

# bendlang/main compiler baseline

This report captures the pre-fix regression for the
[integration plan](BENDLANG-MAIN-INTEGRATION-PLAN.md). Both candidates were
built from archived Git refs; the sibling `../bend` checkout remains clean.

## Compiler inputs

| Candidate | Bend commit | `comp.ts` SHA-256 | Result |
| --- | --- | --- | --- |
| Upstream with existing static pass | `26659268dbdf411696bf90d28e722783dceae0f8` | `cff1914fc98646fd99d087a2d3b7707b9a24b60af9f6824aff9b07082b6c8340` | New upstream template semantics, current static pass, no scoped facts |
| Fork facts control | `15ae0c86f3193b8f645b4bedbc438655b648d0da` | `a393e4f315a2c7a3286b241cee8c11a2fb346b5cdf530e3904c601953a1215d8` | Previously measured candidate with scoped facts |

The upstream input `bend2/comp.ts` itself has SHA-256
`10afb08dd55a52bfbb88fdf84534cebdc000bdf7820c69cee1d6bb3fcfaf7d7b`.

## Reproduction

Commands from the repository root:

```sh
python3 tests/run.py --bend-main /private/tmp/bend-upstream-baseline/main.ts
bun /private/tmp/bend-upstream-baseline/main.ts tests/extensions.bend -o /tmp/extensions.js
bun /private/tmp/bend-upstream-baseline/main.ts tests/keep_partition.bend -o /tmp/keep_partition.js
```

`tests/run.py` stops at `extensions.bend` because generated JS contains two
runtime `Reducer` records. Directly running the generated program prints the
expected four lines (`[1, 2]`, `[]`, `0`, `7`), so semantics pass while the
fusion/code-generation assertion fails. The broader `keep_partition.bend`
program also prints all thirteen expected lines but leaves six runtime
`Reducer` records. The fork facts control leaves zero records in each fixture.
The focused static callback fixtures pass on upstream JS and native.

Added [`template_instances.bend`](../../tests/template_instances.bend) as a
small semantic check for two values and two functions passed through the same
generic definitions, including explicitly annotated values. It prints
`[42, 42, 42, 42]` on upstream JS and native. This guards against accidental
cross-instance substitution; `extensions.bend` remains the positive
independent-source fusion check.

The implementation trace points to template instantiation introduced at
`ee7efc91e9c6695969f025c875ef81f6ea1f8af0`: `Def.x > 0` denotes a generic
template whose checked ordinary body is not an ordinary value at its `~`
arguments. The specialization pass must not unfold it directly. It can use
only a checked `x == 0` instance and must keep the original term when identity
cannot be proven. A prototype used Bend's `term_compare("EQ", ...)` to resolve
existing entries in `book.tmps`; it removed the two records in
`extensions.bend` while preserving output. That prototype is investigation
evidence only: it still left three records in `keep_partition.bend`, and it
has not passed the adversarial instance, cache, performance, or full-suite
gates. Do not promote it as the completed fix.
