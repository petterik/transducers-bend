---
created_at: 2026-09-25T17:09:23+02:00
status: validated-on-fork-branch
---

# General mapcat and compiler hardening

The public `Xf.mapcat` now maps each input to a raw fragment and folds that
fragment with a closed source drive. The callback may return a List, Array,
or custom collection directly, including a List literal. Its concrete
fragment type and drive are supplied once in the stage type; no per-fragment
`Source` wrapper or callback-result compiler conversion is needed. The
lower-level `T.mapcat` has the same contract. The List-specific `mapcat`
function was removed;
`T.map` followed by `T.cat` remains available when an explicit List fold is
useful.

This unifies the semantics, not the cost of constructing the fragment. A
two-element List returned for each input still allocates two List cells. A
small structural source can expose two values without making a collection.
The downstream reducer starts and finishes once; the inner source only drives
steps. Its `Control` result permits `take` or a consumer to stop partway
through a fragment. The public test covers custom, List, Array, and affine
List fragments, mid-fragment stopping, retained List output, and Vec output
on JS and native. The older reducible-cat probe additionally checks exactly
one completion using a custom destination.

The stage still names its fragment type and closed source drive explicitly.
This is a Bend type-system/API limitation, not a runtime allocation. Both
`~(x => make_list(x))` and `~(x => [x])` work. No
contextual-constructor compiler rule was added for `into([], ...)`.

## Compiler branch changes

The changes are committed as `9ebef97f` on
`petterik/bend:codex/transducer-companions`, based on `bendlang/main` at
`3276efac`. The fork compiler now:

- Inserts omitted template placeholders only for a full runtime-argument
  call. The previous rule broke Bend's upstream-valid positional template
  call `app(Nat.add(1n), 3n)`; that call now has its original meaning.
- Rejects ordinary under-applied function heads before paying for the static
  callback specialization cache key and evaluator. This preserves the
  bounded specialization while lowering its cost on unrelated code.

The upstream `tests/comptime/no_tilde.bend` passes on JS and native. A local comparison
covered 982 positive upstream Bend tests in 17 checkup batches and 487
other upstream tests with `--check-only`; output and exit status matched
`bendlang/main` in every case. This is wider than the transducer suite but
does not run the cluster gate's JS/native lanes for every upstream fixture.
The reproducible result is in
`experiments/affine_xf/fork-regression-followup.json`. The library gate passes 38/38 JS/native
fixtures, including code-shape and callback-count checks. The companion
positive/negative probe also passes.

## Performance

On two million List inputs, 64 shuffled, paired native sessions with Clang
`-O3` produced these results. Timed heap requests exclude input creation.

| Path | Median | Paired ratio to direct | Timed heap requests |
| --- | ---: | ---: | ---: |
| Handwritten direct fold | 3,715 µs | 1.0 | 9 |
| Public mapcat, custom pair fragment | 3,755.5 µs | 1.009 (95% interval 0.969–1.090) | 9 |
| Public mapcat, List result | 8,507 µs | 2.297 (95% interval 2.185–2.498) | 4,000,009 |

The public custom-fragment lane is statistically compatible with direct in
this run and matches the earlier manually assembled source path (paired
median ratio 1.015, interval 0.969–1.072). The public List lane is 0.983
times the older List recipe (95% interval 0.962–0.994); its dominant cost is
fragment allocation.
The full samples and allocation counts are in
`experiments/affine_xf/public-mapcat-followup-results.json`.

Compile-time measurements use 25 randomized, paired sessions of separate
Bun processes on identical inputs. The fork/direct-upstream median ratios
are 1.016 for a small pipeline, 1.108 for the Array fixture, and 1.070 for
an 80-test checkup batch. The fast rejection reduced the checkup batch's
earlier roughly 1.24 ratio. These process-inclusive numbers are a real
remaining compile-time cost, not a claim of parity; samples are in
`experiments/affine_xf/compiler-overhead-followup.json`.

The branch remains the supported compiler for this library. Before merging
it into the fork's `main` or offering it to upstream Bend, run the cluster's
full gate and decide whether the remaining compile-time cost is acceptable.
The cluster gate was attempted locally but its SSH host `cluster` did not
resolve on this machine, so that final gate is outstanding. Neither merge
action is implied by the present validation.
