---
created_at: 2026-09-20T21:22:00+02:00
updated_at: 2026-09-24T21:38:41+02:00
status: current
---

# Local representation elimination

The previous positive result in this document was not reproducible and should
not be treated as evidence for a compiler optimization. Its probe expected a
`BEND_FACT_REPORT` hook that is absent from the tracked compiler preparer, and
the compiler source used for that result is not retained. I rebuilt the
candidate from the pinned `bendlang/main` ref, applied the tracked
`checked-shape-fold-prototype.patch`, and reran the fixture. The upstream and
candidate outputs match, but their generated C and JS are byte-identical; this
fixture therefore shows no optimization on the current baseline.

The current run uses
[`local_representation_fact.bend`](../../bench/compiler/fixtures/local_representation_fact.bend),
which constructs `Left{5}` and passes it to a matcher with a dynamic Boolean.
The compiler snapshot is `bendlang/main` commit
`2f50df1ed36fcc3ebe6c75a2046e94001a44645d`. On that snapshot, both builds
produce result `6`, 83,089-byte C, and 13,531-byte JS. The previous values
from that run are superseded by the current report.

The refreshed result is
[`local-representation-results.json`](../../bench/compiler/local-representation-results.json).
The probe no longer assumes an optimization occurred or depends on the missing
`BEND_FACT_REPORT` hook. It builds with UBSan and compares native/JS results and
generated-code hashes. The preparer applies the retained patch to a fresh
static-callback candidate without changing `../bend`.

## Measured `Maybe` consumption

The new probe compares public streaming `keep`, materialized `List<U32>` to
`List<Maybe<U32>>` followed by a fold, and a direct fold. It uses eight prebuilt
200,000-item inputs per lane, 16 paired native sessions, and
`BenchClock.now_us`. Allocation counts come from separate instrumented builds.
The callback returns `Some{x}` for every item; existing
[`keep_partition.bend`](../../tests/keep_partition.bend) covers mixed `Some` /
`None` semantics. JS checks use two 256-item inputs because the larger
recursive-list setup exceeds the JS stack; no JS timing is claimed.

| Compiler | Lane | Median µs per 1.6M values | Heap allocation requests per sample |
| --- | --- | ---: | ---: |
| Raw `bendlang/main` | streaming `keep` | 48,555.5 | 8,000,021 |
| Static-callback candidate | streaming `keep` | 2,888.5 | 5 |
| Static-callback candidate | materialized map-to-Maybe + fold | 7,593.5 | 3,200,005 |
| Static-callback candidate | direct fold | 2,723.5 | 5 |

All lanes return the same checksum on native and the small JS smoke. On the
static-callback candidate, streaming `keep` is about 1.06 times the direct-fold
median and makes only five fixed allocator requests for the whole sample. The
raw compiler makes about five allocator requests per input item in this
streaming path. The materialized pipeline makes about two per item, while the
direct fold also stays at five fixed requests. These totals show that the
candidate removes per-item allocation traffic from the public `keep` pipeline;
they do not classify each allocation by constructor type.

This supports ordinary static composition for `keep`; it does not justify a
Maybe-specific compiler rule. It also exposes the next structural case: the
existing FoldRegion rejects a type-changing List map, so it leaves the
materialized `List<Maybe<U32>>` boundary intact. Generalize the checked
producer/fold rule to distinct source and output element types, then verify it
on this case and an independent custom producer. Preserve the generic path for
retained results, opaque callbacks, and failed checks.

For `keep`, the correct library composition is `map(f)` followed by
`cat_maybe`: `None` skips a downstream step and `Some{x}` transfers `x` once.
`map(f)` followed by `filter(some?)` is not equivalent: it leaves a list of
`Maybe<B>` values, and the filter requires `B` to be `Data`, so it cannot
support affine payloads such as arrays. A separate map-plus-Boolean-filter
experiment can follow once the Maybe boundary has evidence.

Rebuild and rerun the current candidate with:

```sh
python3 bench/compiler/prepare_local_representation.py \
  --output-dir /tmp/transduce-local-representation
python3 bench/compiler/local_representation_probe.py \
  --bend-main /tmp/transduce-local-representation/main.ts \
  --output bench/compiler/local-representation-results.json
```

Reproduce the streaming/materialized `Maybe` comparison with:

```sh
python3 bench/compiler/prepare_static.py --output-dir /tmp/transduce-static
python3 bench/compiler/maybe_keep_probe.py \
  --upstream-main ../bend/bend2/main.ts \
  --candidate-main /tmp/transduce-static/main.ts \
  --output /tmp/maybe-keep-results.json \
  --sessions 16
```
