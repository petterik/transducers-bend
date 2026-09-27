---
created_at: 2026-09-27
status: implemented-and-locally-verified
---

# Bounded Array walk in the Bend fork

`Array.walk` is now an operation in the sibling Bend fork's `bend2/base.bend`.
The library's `Array.source` and `Array.adapter` call it through
`transduce_core.bend`. The compiler change is in the fork's `bend2/comp.ts`.
This supersedes the generated-C-only [proposal](20260926-BOUNDED-ARRAY-WALK.md)
for the local fork. The edits are still uncommitted at this checkpoint.

## Contract and lowering

`Array.walk` owns a `Data` Array, derives its size, starts at index zero, and
calls `inspect` before the first read and after each `advance`. A halted state
returns without another read. It does not expose a user-supplied index through
the public entry point. The existing `Array.get` wraparound behavior remains
available. Affine Arrays still use the structural `Array.affine_source` path.

The native compiler recognizes the generic `Array.walk.loop` definition. At
entry, it checks that the entire supplied span fits within the Array. Its own
read then uses the unmasked offset when the span is valid, and the ordinary
masked `blk_at` when a caller invokes the public helper with a malformed span:

```c
u64 walk_size = 1ull << (blk_cls(array) - layout_shift);
bool bounded = index <= walk_size && remaining <= walk_size - index;
Term at = bounded ? ((u32)index << layout_shift)
                  : blk_at(array, index, layout_shift);
```

The generated code keeps the per-read block lookup, `blk_keep`, and existing
layout handling. The guard is outside the loop. Within a valid walk, the
recurrence increments `index` and decrements `remaining` together, so their
sum stays equal to the Array size; every read has `remaining > 0`, hence
`index < size`. The native block depth limit makes the final offset fit in
U32. This is a source and compiler invariant argument, **not a machine-checked
proof** of the emitter or runtime.

## Correctness checks

- Library suite: **64/64**. This includes JS/native walk results, all stop
  positions, callback counts, one-element and larger Arrays, boxed `String`
  and multiword `Data`, and affine type rejection.
- Fork local compiler gate: **1470/1470** after adding pure and IO fixtures.
  A shared `Array.fork` write is checked in JS/native IO mode. The existing
  value evaluator differs from JS/native for this `@unsafe` shared-write
  pattern even without `Array.walk`, so it is not used as an oracle for that
  specific fixture.
- CPU and Metal runs of a parallel walk fixture both returned **2048** on the
  M3 Max. Metal was run with `--gpu on`.
- Direct malformed calls to `Array.walk.loop` with an invalid first or later
  index matched ordinary masked `Array.get` behavior on JS/native.

These tests cover the observed implementations and values; they are not an
exhaustive proof of every callback or Array layout.

## Matched performance

Both fixtures build a flat U32 input before the microsecond clock. Traversal
and disposal are within the clock. Every sample is a separate process; path
order is shuffled per session. All checksums match independent Python
calculations. Median times below are microseconds across **36 paired
sessions** per size on the M3 Max, Apple Clang 17 `-O3`, one CPU thread.

| Elements | Bend `map(inc) → sum` | Direct Bend index loop | C loop | Rust iterator | Rust loop |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 65,536 | 5 | 16 | 5 | 5 | 5 |
| 262,144 | 20 | 62.5 | 20 | 19 | 19 |
| 1,048,576 | 76 | 239 | 80.5 | 80 | 79 |

[Fixture and runner](../../bench/public_array_map_inc_sum.py) ·
[raw samples](../../bench/public-array-map-inc-sum-20260927.json)

| Elements | Bend `map → filter → sum` | Direct Bend index loop | C loop | Rust iterator | Rust loop |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 65,536 | 12 | 16 | 12 | 11 | 11.5 |
| 262,144 | 47 | 65.5 | 46.5 | 46 | 47 |
| 1,048,576 | 188.5 | 263 | 199 | 195.5 | 198 |

[Fixture, C/Rust controls and runner](../../bench/public_array_map_filter_sum_rust.py) ·
[raw samples](../../bench/public-array-map-filter-sum-rust-integrated-20260927.json)

The separate 36-session [original runner's integrated result](../../bench/public-array-map-filter-sum-integrated-20260927.json)
gave 192.5 µs for the Bend transducer and 192 µs for C at one million.
The earlier masked-read [baseline](../../bench/PUBLIC-ARRAY-VS-C.md) was
352 µs for Bend and 178 µs for C under its own run conditions. The integrated
paired runs support parity on these fixtures, not a universal speed ratio.

Clang's `-Rpass=loop-vectorize` reports width four and interleave count four
on each exact Bend traversal loop: generated C line 1503 for `map(inc)` and
line 1648 for `map → filter`. Both are the `Array.walk` loop containing the
guarded unmasked read. The numbers and generated C are recorded by source
hash in the benchmark reports. At one million elements, the Bend timed
interval made **9** native heap allocation calls for `map(inc)` and **10**
for `map → filter`, with no per-element stage collection. No claim of zero
total allocations follows from this result.

## Remaining boundary

The [local upstream comparison](20260927-UPSTREAM-LOCAL-REGRESSION.md) now
covers all 16 runtime benches in sequential, eight-thread CPU, and Metal
modes, plus the five checker benches. The original Apple M4 cluster gate
cannot be treated as an M3 Max paired measurement. Machine-checked proofs
for the whole walk/compiler path remain open. The
[512×512 cross-language showcase comparison](20260927-BULLET-CATHEDRAL-CROSS-LANGUAGE.md)
is a separate workload.

Reproduce the flat Array measurements from the repository root with the
edited sibling fork:

```sh
python3 bench/public_array_map_inc_sum.py --depths 16 18 20 --sessions 36 --output /tmp/map-inc-sum.json
python3 bench/public_array_map_filter_sum_rust.py --depths 16 18 20 --sessions 36 --output /tmp/map-filter-sum.json
```
