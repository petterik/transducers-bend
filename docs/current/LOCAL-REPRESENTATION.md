---
created_at: 2026-09-20T21:22:00+02:00
updated_at: 2026-09-25T07:35:41+02:00
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
sample. It uses 32 randomized native sessions and the microsecond clock.
Allocation counts come from separate instrumented C builds. The timed map
callback returns `Some{x}`; the type-changing semantic fixture also covers
all-`None`, mixed options, an empty list, an order-sensitive fold, and an
affine `Array` payload.

| Compiler | Streaming `keep` µs / allocs | Nested map/fold µs / allocs | Let-bound map/fold µs / allocs | Direct fold µs / allocs |
| --- | ---: | ---: | ---: | ---: |
| Raw `bendlang/main` | 57,696.5 / 8,000,021 | 8,494.5 / 3,200,005 | 8,201 / 3,200,005 | 2,046 / 5 |
| Static-callback candidate | 2,989 / 5 | 8,482.5 / 3,200,005 | 8,258 / 3,200,005 | 1,925.5 / 5 |
| Checked FoldRegion candidate | 3,050 / 5 | 1,932 / 5 | 3,175 / 5 | 1,934 / 5 |

The directly nested type-changing map/fold goes from 8,482.5µs and 3,200,005
heap requests on the static-callback candidate to 1,932µs and five fixed
requests with FoldRegion. Its paired FoldRegion/static-callback time ratio is
0.224 [0.204, 0.251], about a 78% reduction. Against the direct fold in the
same FoldRegion build, the ratio is 0.999 [0.882, 1.159], statistically
consistent with parity.

The let-bound map/fold drops from 8,258µs and 3,200,005 requests to 3,175µs
and five fixed requests. Its paired FoldRegion/static-callback ratio is 0.387
[0.376, 0.405], about a 61% reduction. This confirms that the single-use
alias rule removes the materialized `List<Maybe<U32>>`.

The FoldRegion let/direct latency comparison depends strongly on lane order.
The benchmark runs each lane in one compiled program, so changing measurement
order also changes generated-code layout. Four cyclic orders, each with 32
sessions, produced these paired let/direct ratios:

| Measurement order | Let position | Direct position | Let / direct, paired 95% interval |
| --- | ---: | ---: | ---: |
| Keep, map/fold, let/fold, direct | 3 | 4 | 1.625 [1.544, 1.770] |
| Map/fold, let/fold, direct, keep | 2 | 3 | 0.737 [0.667, 0.757] |
| Let/fold, direct, keep, map/fold | 1 | 2 | 0.619 [0.579, 0.636] |
| Direct, keep, map/fold, let/fold | 4 | 1 | 1.375 [1.310, 1.479] |

All four FoldRegion outputs have the same C byte count (137,787), but each
ordering has a different C hash. The ratio is below one when let/fold runs
before direct, and above one when it runs after. This shows that the apparent
let/direct latency gap is an order/layout effect in this shared-process
harness, not evidence that the let rewrite does more work per item. The
reliable measured win is allocation elimination; use isolated or balanced
lane timing before making a latency claim about this shape. The four full reports are
[`maybe-keep-fold-region-results.json`](../../bench/compiler/maybe-keep-fold-region-results.json),
[`maybe-keep-order-map-let-direct-keep-results.json`](../../bench/compiler/maybe-keep-order-map-let-direct-keep-results.json),
[`maybe-keep-order-let-direct-keep-map-results.json`](../../bench/compiler/maybe-keep-order-let-direct-keep-map-results.json),
and
[`maybe-keep-order-direct-keep-map-let-results.json`](../../bench/compiler/maybe-keep-order-direct-keep-map-let-results.json).

The positive and fallback controls are in
[`fold_region_let_alias.bend`](../../tests/fold_region_let_alias.bend) and
[`fold_region_bailouts.bend`](../../tests/fold_region_bailouts.bend). The
positive case has exactly one let binding, one use, and an immediate fold.
An unsafe callback and a let-bound mapped value consumed by `List.length`
remain unchanged. Lists of affine elements cannot be legally used twice, but
the optimizer still counts uses before rewriting. This is evidence for that
specific checked alias shape, not arbitrary local propagation.

All native lanes and the small JS smoke runs return the same checksum. The JS
smoke uses two 256-item inputs because the large recursive-list setup exceeds
the JS stack; it provides semantic parity only, not JS timing. The FoldRegion
build's generated C is 137,787 bytes versus 146,087 bytes for the
static-callback build. Clang -O3 compiles those C files in about 0.25 seconds;
this probe does not time Bend source compilation. The
probe records raw samples, build hashes, generated code sizes, and paired
ratios in
[`maybe-keep-fold-region-results.json`](../../bench/compiler/maybe-keep-fold-region-results.json).

The checked-term rule accepts different producer input/output List element
types and one single-use let alias. For type-changing maps it erases checked
type ascriptions from a copied consumer body, then uses `Bend.def_check` on
each generated helper. The type-changing fixture generated ten helpers, all
rechecked successfully; the isolated let fixture also verifies that its
generated helpers are rechecked. The full FoldRegion candidate suite passed
30/30 with codegen gates, and upstream plus static-callback builds passed
30/30 semantic JS/native checks. The affine array payload still passes through
the type-changing helper check.

This demonstrates that the current structural rule can eliminate a
type-changing intermediate when the producer call is the fold's direct input
or is held by one single-use local immediately consumed by the fold. It does
not support `filter`, `partition_all`, early stop, retained chunks, or
non-List sources. Keep results also vary with
the surrounding compiled fixture: use the standalone prior report for
historical keep/direct timing comparisons, and use this expanded fixture for
the matched type-changing map/fold result.

For `keep`, the correct library composition is `map(f)` followed by
`cat_maybe`: `None` skips a downstream step and `Some{x}` transfers `x` once.
`map(f)` followed by `filter(some?)` is not equivalent: it leaves a list of
`Maybe<B>` values, and the filter requires `B` to be `Data`, so it cannot
support affine payloads such as arrays. The Boolean map/filter shape is now
tested in [`TRANSDUCER-FUSION-ABLATION.md`](TRANSDUCER-FUSION-ABLATION.md): a
custom reusable map producer followed by `List.filter` and a fold preserves
order and skips rejected steps, but the current FoldRegion rule refuses to
fuse it because it only models one output per source item. The exact
`List.map` → `List.filter` spelling also fails the library's quantity types
(`List<&1, B>` versus `List<&2, A>`). The proposed typed producer-step/fold
region, including the effect, totality, ownership, and fallback proof gates,
is specified in [`PRODUCER-STEP-FOLD-REGION.md`](PRODUCER-STEP-FOLD-REGION.md).

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
  --sessions 32
```

To change the order of the four timed lanes while keeping the inputs and
consumers fixed, pass a permutation such as
`--measurement-order map_fold,let_bound_map_fold,direct,keep`. The runner
records that order, the generated C hashes, and all paired samples.
