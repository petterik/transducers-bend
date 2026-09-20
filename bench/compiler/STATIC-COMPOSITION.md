# Static composition probe

Status: memoization prototype completed; the public delayed recipe remains in
place. The reduced eager migration remains an open Array-specific blocker.

The current binding uses `~(u => r)` for the reducer recipe and delays the
associated type metadata. This looks like an implementation detail, but it is
currently the staging boundary that lets the compiler resolve the nested reducer
description without exhausting its bounded evaluator. The probe adds an
equivalent local `over_list_eager` binding whose static argument is the reducer
itself. It does not change the public library.

## Evidence

`static_composition.py` exercises both forms over:

- a scalar map and sum;
- map, configured filter, take, and sum;
- `partition_all` and count, including completion of a partial group.

Both emitted JavaScript and native CPU return `[9, 9, 7, 7, 3, 3]`. The current
compiler emits no `Reducer` or `Reduction` records in the combined probe, and
the C output has no `Clo.apply` occurrences. The retained result is
[`static-composition-results.json`](static-composition-results.json), generated
from compiler SHA
`96c997a7d4700a7aaa7bb5a7f27ea810394168cb50fd7f6d267d45156f2e3df3`.

The reduced eager form therefore works in representative closed pipelines. It
does not justify removing the public delay. In a controlled temporary edit that
changed `reducible` to accept `~r: Reducer<A,R>` directly, the ordinary Array
fixture retained `Reducer` records, and the independent tree extension still
called the documented delayed-recipe form and failed to typecheck. The direct
form is a source/API migration, not a drop-in compiler improvement. The current
staging also matters for larger compositions whose specializations share type
metadata.

## Memoized static prototype

`prepare_static.py` builds an isolated compiler that memoizes normalized static
terms per compiler `Book`. The cache is scoped to one compilation, preserves a
null refusal result, and reports queries, hits, misses, and refusals through
`BEND_STATIC_REPORT`. `static_eager_probe.py` migrates every built-in adapter and
the external tree together, then compares delayed and eager forms on Array,
`keep`/`partition_all`, and the reusable API fixture.

The current prototype is semantically clean and useful: the full 20-file suite
passes, and the probe records thousands of repeated queries with high hit rates.
It does not remove the Array records: the eager Array lane still retains three
`Reducer` records and one `Reduction` record, while eager `keep_partition` and
`api_surface` have none. The cache reduces repeated evaluator work but does not
solve the Array driver’s unresolved static shape. The delayed recipe therefore
remains the public boundary until that reduced case receives a separate static
head/driver explanation.

## Decision

Keep the delayed recipe while making the compiler's static work explicit and
memoized. Treat the recipe as a compatibility boundary for third-party source
adapters until a replacement can compile both built-ins and extensions with
equal or better code shape. Do not add a second public binding helper merely to
hide a compiler limitation.

The next compiler task is a typed region with scoped summaries. It should expose
the reducer description after static resolution, bind dynamic configuration once,
and retain a correct fallback when its budget or proof is insufficient. The
probe remains a regression for the eventual staging change.

## Reproduce

```sh
python3 bench/compiler/static_composition_probe.py \
  --bend-main ../bend/bend2/main.ts \
  --output bench/compiler/static-composition-results.json
```

The script records source/compiler hashes, compile time, backend outputs, and
residual representation markers. It writes generated programs to a temporary
directory and does not edit either checkout.
