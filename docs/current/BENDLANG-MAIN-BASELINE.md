---
created_at: 2026-09-23T14:38:33+02:00
updated_at: 2026-09-23T16:33:34+02:00
status: current
---

# bendlang/main compiler baseline

This records the current upstream-only integration candidate. The remote was
refreshed from `bendlang/bend`; the `../bend` working tree remains untouched.

## Compiler inputs

| Input | Bend commit | `comp.ts` SHA-256 | Result |
| --- | --- | --- | --- |
| Upstream source | `6a77e1246c351055cb15031267a7c76c87036cbc` | `10afb08dd55a52bfbb88fdf84534cebdc000bdf7820c69cee1d6bb3fcfaf7d7b` | Current `bendlang/main` |
| Isolated candidate | Same as above | `e2f59c5c847cd77d6992d734ad54a26780d3ac613dc60dfab88c1f0bf413e9b0` | Upstream plus the local static-callback pass |

The upstream commits since `26659268` change package-name handling in
`bend2/bend.ts` and add its syntax to `guide/GUIDE.md`. They do not change
`bend2/comp.ts`. The preparation script now archives only the
`refs/remotes/bendlang/main` ref and accepts only the reviewed compiler source
hash.

## Validation

`python3 bench/compiler/prepare_static.py --output-dir …` passes its smoke
build, API-surface record checks, and five static-callback fixtures on JS and
native.

`python3 tests/run.py --bend-main <candidate>/main.ts --semantic-only` passes
all 23 fixtures on JS and native, including the affine rejection case. The
expected diagnostic now matches upstream's current call-site location.

The normal `tests/run.py` keeps the code-shape checks enabled. It passes
`api_surface`, `array`, `completion`, `composed_maps`, `configured_pipeline`,
and `extensions`, then stops at `keep_partition`: three runtime `Reducer`
records remain. The program's output is correct, but the full-fusion gate is
not met. The records are emitted by the closed `take` and `partition_all`
factory sites. Do not weaken this assertion or treat the semantic-only suite
as a fusion pass.

The generic evaluator rejects direct unfolding of `Def.x > 0`, resolves only
already checked zero-template-argument instances, tries exact `book.tmps` keys,
and uses bounded `term_compare` only as a fallback. Ambiguous or unsafe
lookups refuse specialization. The focused multi-instance test covers two
values and two callbacks, but the fallback still needs the adversarial matrix
listed in the integration plan.

The scoped constructor-facts emitter experiment was removed from the active
driver. Its synthetic test showed local value, but the pass recorded no fact
selections for `keep_partition`, so it did not address the current main
blocker. Historical fork measurements remain archived evidence only and are
not an acceptance baseline.

## Performance evidence

The calibrated native matrix uses ten sessions, five alternating paired
launches per session, at least 100 ms per batch, and a bootstrap upper 95%
bound against the 1.05 target. All JS/native expected outputs agree. Four of
eleven rows pass; seven full-traversal rows fail:

| Case | Upper ratio | Result |
| --- | ---: | --- |
| `keep_full` | 0.902 | pass |
| `keep_take_32` | 1.017 | pass |
| `keep_type_change` | 19.283 | fail |
| `keep_type_change_take_32` | 1.029 | pass |
| `partition_width_1` | 13.970 | diagnostic fail |
| `partition_width_8` | 4.017 | diagnostic fail |
| `partition_take_2` | 1.001 | diagnostic pass |
| `partition_sum_width_1` | 18.279 | fail |
| `partition_sum_width_2` | 10.676 | fail |
| `partition_sum_width_8` | 9.585 | fail |
| `partition_sum_take_2` | 1.004 | pass |

The raw result with compiler, library, and harness hashes, every sample, build
times, and source checksums is
[`bendlang-main-extension-parity-results.json`](../../bench/bendlang-main-extension-parity-results.json).
Generated sources and binaries are in
`/private/tmp/bend-main-current-parity-artifacts` on the current machine. These
timings measure complete CPU reductions over sequential List inputs; they do
not cover range, tree, Array, GPU, or include compilation in the timed ratio.
Emitted C is 1.5–1.8 times larger for the failing equivalent-consumer rows,
while the much larger runtime ratios point to repeated runtime reducer
construction and dispatch in the full cases.

## Next gate

First prove the `term_compare` instance-identity fallback on adversarial
template cases. Then specialize ordinary checked helpers at call sites where a
reducer argument is closed and the remaining state/input arguments are
dynamic. The live guide confirms a generic `~` parameter cannot be matched
directly in its definition (the checker cannot infer pattern-field types), but
a checked runtime helper can match a reducer value and then be specialized at
a call site. That targets the repeated construction/dispatch visible in the
generated JS while keeping the library independent of transducer names. Retain
the dynamic-reducer fallback. Only after these gates pass should the pass be
proposed in upstream `bend2/comp.ts`.
