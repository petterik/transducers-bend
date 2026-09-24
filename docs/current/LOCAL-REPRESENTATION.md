---
created_at: 2026-09-20T21:22:00+02:00
updated_at: 2026-09-24T22:16:50+02:00
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

## Type-changing `Maybe` map/fold experiment

The earlier `maybe-keep-results.json` report compared streaming `keep`, a
materialized map/fold, and a direct fold on the static-callback candidate. It
showed fixed allocation traffic for streaming `keep` and about 3.2 million
heap requests for a materialized `List<Maybe<U32>>`. That initial probe used a
let-bound mapped list, so the checked FoldRegion could not see through the
local variable.

The current experiment compares four source shapes: public streaming `keep`,
directly nested `List.map(U32 -> Maybe<U32>)` into `List.foldl`, the same map
bound to a local variable before folding, and a handwritten direct fold. Each
lane processes eight prebuilt 200,000-item lists (1.6 million values) per
sample. It uses 16 randomized native sessions and the microsecond clock.
Allocation counts come from separate instrumented C builds. The timed map
callback returns `Some{x}`; the type-changing semantic fixture also covers
all-`None`, mixed options, an empty list, and an order-sensitive fold.

| Compiler | Streaming `keep` µs / allocs | Nested map/fold µs / allocs | Let-bound map/fold µs / allocs | Direct fold µs / allocs |
| --- | ---: | ---: | ---: | ---: |
| Raw `bendlang/main` | 50,233.5 / 8,000,021 | 7,422 / 3,200,005 | 7,112.5 / 3,200,005 | 1,880 / 5 |
| Static-callback candidate | 2,636 / 5 | 7,315.5 / 3,200,005 | 7,004.5 / 3,200,005 | 1,714.5 / 5 |
| Checked FoldRegion candidate | 2,490.5 / 5 | 1,841.5 / 5 | 7,245.5 / 3,200,005 | 1,990.5 / 5 |

The directly nested type-changing map/fold goes from 7,315.5µs and 3,200,005
heap requests on the static-callback candidate to 1,841.5µs and five fixed
requests with FoldRegion. The paired FoldRegion/static-callback time ratio is
0.252 [0.209, 0.291], about a 75% reduction. Against the direct fold in the
same FoldRegion build, the fused map/fold ratio is 0.907 [0.833, 1.114]: the
timings are statistically consistent with parity, and the measured allocation
count is the same five fixed requests.

The let-bound map/fold stays at about 7.2ms and 3.2 million heap requests. Its
output remains correct, but the prototype does not propagate the producer
through a local binding. FoldRegion is 3.6% slower than the static candidate
on this lane (paired ratio 1.036 [1.021, 1.045]) without changing its
allocation count; treat that small cross-build difference as an unresolved
code-layout effect. The benchmark and
[`fold_region_bailouts.bend`](../../tests/fold_region_bailouts.bend) make that
limitation explicit: when the structural rule declines, the original
materialized program remains in place. So this is evidence for a checked
direct producer/fold rewrite, not yet for optimization that scales across
ordinary let-bound program shapes.

All native lanes and the small JS smoke runs return the same checksum. The JS
smoke uses two 256-item inputs because the large recursive-list setup exceeds
the JS stack; it provides semantic parity only, not JS timing. The FoldRegion
build's generated C is 143,941 bytes versus 146,087 bytes for the
static-callback build. The native Clang build takes about 0.26 seconds for both
candidate outputs; this probe does not time Bend source compilation. The
probe records raw samples, build hashes, generated code sizes, and paired
ratios in
[`maybe-keep-fold-region-results.json`](../../bench/compiler/maybe-keep-fold-region-results.json).

The checked-term rule now accepts different producer input and output List
element types. It erases checked type ascriptions from a copied consumer body
only for this type-changing case, then uses `Bend.def_check` on each generated
helper. The fixture generated ten helpers and all ten passed that check;
the full candidate suite passed 28/28 on JS and native. The semantic cases
also wrap an affine `Array<U32>` in `Maybe` and consume the `Some` branch. This
preserves the proof boundary while allowing the match-arm head and tail types
to be re-inferred from the source List.

This demonstrates that the current structural rule can eliminate a
type-changing intermediate when the producer call is the fold's direct input.
It does not support let-bound producer results, `filter`, `partition_all`,
early stop, retained chunks, or non-List sources. Keep results also vary with
the surrounding compiled fixture: use the standalone prior report for
historical keep/direct timing comparisons, and use this expanded fixture for
the matched type-changing map/fold result.

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

Reproduce the streaming, nested/let-bound map/fold, and direct comparison with:

```sh
python3 bench/compiler/prepare_static.py --output-dir /tmp/transduce-static
python3 bench/compiler/prepare_fold_region.py --output-dir /tmp/transduce-fold-region
python3 bench/compiler/maybe_keep_probe.py \
  --upstream-main ../bend/bend2/main.ts \
  --candidate-main /tmp/transduce-static/main.ts \
  --fold-region-main /tmp/transduce-fold-region/main.ts \
  --output /tmp/maybe-keep-fold-region-results.json \
  --sessions 16
```
