---
created_at: 2026-09-23T14:38:33+02:00
updated_at: 2026-09-23T18:47:15+02:00
status: current
---

# bendlang/main compiler baseline

This records the current upstream-only integration candidate. The remote was
refreshed from `bendlang/bend`; the `../bend` working tree remains untouched.

## Compiler inputs

| Input | Bend commit | `comp.ts` SHA-256 | Result |
| --- | --- | --- | --- |
| Upstream source | `6a77e1246c351055cb15031267a7c76c87036cbc` | `10afb08dd55a52bfbb88fdf84534cebdc000bdf7820c69cee1d6bb3fcfaf7d7b` | Current `bendlang/main` |
| Isolated candidate | Same as above | `04d2f814c799808efd136f5a56f22236d0dd128045dbf562c227d2f17fae992d` | Upstream plus the local static-callback pass |

The upstream commits since `26659268` change package-name handling in
`bend2/bend.ts` and add its syntax to `guide/GUIDE.md`. They do not change
`bend2/comp.ts`. The preparation script now archives only the
`refs/remotes/bendlang/main` ref and accepts only the reviewed compiler source
hash.

## Validation

`python3 bench/compiler/prepare_static.py --output-dir …` passes its smoke
build, API-surface record checks, and five static-callback fixtures on JS and
native. The complete `python3 tests/run.py --bend-main <candidate>/main.ts`
run passes all 23 fixtures on both backends, including the code-shape,
callback-count, lifecycle, affine rejection, and bounded-law checks. No
`Reducer` or `Reduction` records remain in the gated fixtures, including
`keep_partition`.

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

The scoped constructor-facts emitter experiment was removed from the active
driver. Its synthetic test showed local value, but the pass recorded no fact
selections for `keep_partition`, so it did not address the current main
blocker. Historical fork measurements remain archived evidence only and are
not an acceptance baseline.

## Performance evidence

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
1.455–1.491x direct by the upper bound. Its generated code constructs each
group as a List, reverses it at completion, and traverses it again in the
consumer; the exact share of runtime cost attributable to those operations is
not yet measured. The direct benchmark currently folds groups in reverse order,
which is equivalent for addition but avoids the ordering work required by
`partition_all`; an order-preserving direct comparison is the next diagnostic.

## Next gate

Next compare group-sum `partition_all` against a direct implementation that
preserves group order, then test whether a source-independent producer/consumer
fusion or a library sink contract can remove the buffered group without
changing `partition_all` semantics. Keep the experiment separate from the
general checked-term pass. Define and measure a generated-code growth bound as
well. The language guide confirms that templates receive closed syntax and
compile separately for each argument set, closures are affine, and Bend has no
implicit protocol dispatch; preserve those rules in any general compiler
proposal. Once the remaining correctness and performance gates are met, move
the small pass into upstream `bend2/comp.ts` and add compiler-native fixtures.
