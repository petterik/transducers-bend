---
created_at: 2026-09-23T14:38:33+02:00
updated_at: 2026-09-24T13:58:08+02:00
status: current
---

# bendlang/main compiler baseline

This records the current upstream-only integration candidate. The sibling
`../bend` checkout is read-only for this experiment.

## Compiler inputs

| Input | Bend commit | `comp.ts` SHA-256 | `main.ts` SHA-256 | Result |
| --- | --- | --- | --- | --- |
| Upstream source | `2f50df1ed36fcc3ebe6c75a2046e94001a44645d` | `34783e2779f23b0f7be586f70130292ea367fbe74d3d12b327d434633dc93850` | `0984154bb5f8bfb0718e4ad60d58f5098af0f01812dc8ef75b6e793e800552f8` | Synced `bendlang/main` |
| Isolated candidate | Same as above | `083adb324e749a1ca20376896d3a14e716ccc355f019736e7b4c9dba6ab54bee` | `0984154bb5f8bfb0718e4ad60d58f5098af0f01812dc8ef75b6e793e800552f8` | Same entry point with this repository's static-callback pass |

The local `bendlang/main` ref and sibling checkout both resolve to the commit
above. Since the previously recorded baseline, upstream changed literal
handling in `bend2/comp.ts`. The preparation script now accepts the reviewed
hash `34783e…93850`, archives only `refs/remotes/bendlang/main`, and keeps the
static-callback pass in the isolated candidate.

## Validation

On 2026-09-24, `python3 bench/compiler/prepare_static.py
--identity-self-test --output-dir /tmp/transduce-main-current-baseline` passed
its smoke build, API-surface checks, five static-callback fixtures on JS and
native, and bounded template-identity self-tests. The candidate source hash is
`083adb32…6ab54bee`. The full
`python3 tests/run.py --bend-main
/private/tmp/transduce-main-current-baseline/main.ts` run passed all 23
fixtures on both backends, including code shape, callback counts, lifecycle,
affine rejection, and bounded laws. The tests found no runtime `Reducer` or
`Reduction` records in the gated fixtures, including `keep_partition`.

The semantic-only option remains available to isolate output behavior, but it
is not the reported acceptance run. The expected affine diagnostic matches
upstream's current call-site location.

The generic evaluator rejects direct unfolding of `Def.x > 0` and resolves
only already checked zero-template-argument instances. It first tries the exact
`book.tmps` source key, then compares bounded structural keys that remove
erased annotations and spans and restore the checked lambda's default `Lone`
quantity. It never evaluates or unfolds terms to compare identities. The
structural scan refuses ambiguous, missing, alias-only, or oversized matches;
an adversarial self-test covers those cases, recursive syntax, and Book-scoped
caching. Checked application spines are flattened across annotations for
lookup, with a 2,048-node cap; evaluation still sees the unchanged checked
term. The focused suite is run with
`python3 bench/compiler/prepare_static.py --identity-self-test --output-dir …`.

This verifies compatibility with the refreshed compiler snapshot. A matched
native comparison of raw upstream and the refreshed candidate is now recorded
in [`TRANSDUCER-FUSION-ABLATION.md`](TRANSDUCER-FUSION-ABLATION.md). The
static-callback pass improves this partition pipeline by about 8.4–9.4x, but
the candidate remains 1.4–1.6x slower than the handwritten materializing
control. Do not treat the old matrix below as a timing result for this
candidate.

## Historical performance evidence

The matrix below was collected on the earlier compiler snapshot at
`6a77e124…706cbc`, with candidate source hash
`04d2f814…faf7d7b`. It is useful diagnostic evidence, but it is not a timing
baseline for the refreshed compiler above. The latest Array width sweep used
raw upstream at `2f50df1e`, without the static-callback pass. Do not combine
these ratios; rerun matched workloads on raw upstream and the refreshed
candidate before attributing a change to the pass or compiler.

The calibrated native matrix uses ten sessions, five alternating paired
launches per session, at least 100 ms per batch, and a bootstrap upper 95%
bound against the 1.05 target. All expected outputs agree. Six of eleven rows
pass; five exceed the target, including two count-only diagnostics with
unequal consumer work:

| Case | Upper ratio | Result | C bytes (transducers/direct) | JS bytes (transducers/direct) |
| --- | ---: | --- | ---: | ---: |
| `keep_full` | 0.910 | pass | 97,469/93,363 | 17,804/16,029 |
| `keep_take_32` | 1.015 | pass | 150,069/145,712 | 17,793/16,018 |
| `keep_type_change` | 0.992 | pass | 97,687/93,141 | 17,941/16,111 |
| `keep_type_change_take_32` | 1.026 | pass | 156,165/151,368 | 17,930/16,100 |
| `partition_width_1` | 4.628 | diagnostic fail | 110,457/91,722 | 22,734/15,504 |
| `partition_width_8` | 1.559 | diagnostic fail | 139,247/121,964 | 22,733/15,503 |
| `partition_take_2` | 1.010 | pass | 169,188/153,377 | 22,722/15,492 |
| `partition_sum_width_1` | 1.491 | fail | 111,547/92,691 | 23,072/15,907 |
| `partition_sum_width_2` | 1.455 | fail | 111,547/92,691 | 23,072/15,907 |
| `partition_sum_width_8` | 1.462 | fail | 111,547/92,691 | 23,072/15,907 |
| `partition_sum_take_2` | 1.009 | pass | 164,781/148,468 | 23,060/15,895 |

The raw result with compiler, library, and harness hashes, every sample, build
times, and source checksums is
[`bendlang-main-extension-parity-results.json`](../../bench/bendlang-main-extension-parity-results.json).
Generated sources and binaries are in
`/private/tmp/bend-main-structural-v3-artifacts` on the current machine.
These timings measure complete CPU reductions over sequential List inputs; they do
not cover range, tree, Array, GPU, or include compilation in the timed ratio.
Full type-changing `keep` improved from a 19.283 upper ratio to 0.992 after
fixing annotated template-instance lookup. Full group-sum partition remains
1.455–1.491x direct by the upper bound. The direct sum is a valid equivalent
consumer: because the final result is a sum, group order is not observable.
The additional order-preserving diagnostic puts `List.reverse` before each
direct group sum. Its upper ratios are 1.416x (width 1), 1.696x (width 2), and
1.380x (width 8); all still fail the 1.05 target. A repeat of width 2 measured
1.688x for the ordered version and 1.444x for the default direct version.
Because the result shifts in opposite directions at different widths, group
order alone does not explain the remaining gap. The disabled-flag repeat
generated identical transducer/direct source hashes and C/JS byte sizes to the
primary width-2 row. The supplemental raw runs are
[`bendlang-main-partition-order-probe-results.json`](../../bench/bendlang-main-partition-order-probe-results.json),
[`bendlang-main-partition-order-width2-repeat-results.json`](../../bench/bendlang-main-partition-order-width2-repeat-results.json), and
[`bendlang-main-partition-default-width2-repeat-results.json`](../../bench/bendlang-main-partition-default-width2-repeat-results.json).

In the earlier candidate, the source held one pending `List<A>` for the current
chunk and prepended one `Con` per input item. Generated C showed `List.reverse`
relinking consumed nodes in place when affine ownership proved they were
unique. The refreshed matched ablation has now isolated allocations: the
current candidate still constructs one group Cons per input in the public
transducer path, while the handwritten materialized control reuses consumed
source Cons cells and performs no timed Cons construction. See
[`TRANSDUCER-FUSION-ABLATION.md`](TRANSDUCER-FUSION-ABLATION.md) for the exact
counts and timings. A group that the consumer retains still cannot be
recycled.

## Next gate

The partition materialization and allocation ablation is complete. The next
experiment is a small, isolated checked-term producer/consumer fusion for a
fresh List result consumed exactly once by a fold. It must preserve the
original expression unless freshness, non-escape, callback order, effects,
affine uses, and early-stop behavior are all proven. Keep the transformation
independent of transducer and reducer names; include a custom producer/fold
positive case and retaining/effectful negative cases. The details, prioritizing
and acceptance gates are in
[`TRANSDUCER-FUSION-ABLATION.md`](TRANSDUCER-FUSION-ABLATION.md).

Do not add a runtime reference-count test. The generated C already shows Bend
reusing consumed source cells in the handwritten materialized path, while the
candidate still constructs one group Cons per transducer input. A fold that
retains a chunk must continue to materialize it. Keep a code-growth bound and
run both backends before considering moving any rule into upstream
`bend2/comp.ts`.
