---
created_at: 2026-09-20T21:22:00+02:00
updated_at: 2026-09-24T21:10:37+02:00
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
below are retained only as a record of the now-unreproducible run and are
superseded by the current report.

The refreshed result is
[`local-representation-results.json`](../../bench/compiler/local-representation-results.json).
The probe no longer assumes an optimization occurred or depends on the missing
`BEND_FACT_REPORT` hook. It builds with UBSan and compares native/JS results and
generated-code hashes. The preparer applies the retained patch to a fresh
static-callback candidate without changing `../bend`.

The next useful experiment is to measure immediate `Maybe` consumption before
writing another rewrite. Use a checked function returning `Maybe<B>` and a
consumer that immediately matches it; compare that with direct conditional
consumption, then run the same cases through the public `keep` transducer. Cover
all-`Some`, all-`None`, mixed results, and an affine payload. Add a compiler
rule only if current `bendlang/main` leaves a measurable wrapper cost and a
small structural rule removes it while preserving the opaque-producer
fallback.

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
