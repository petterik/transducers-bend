---
created_at: 2026-09-25T22:44:28+02:00
status: validated-on-local-fork
---

# Grouping, full windows, and Vec fragments

`partition_by(~A, ~K, ~key, ~equal)` emits an ordered List whenever the key
changes. It flushes the final group once on completion and forwards a
downstream stop at a group boundary. The input and key must be `Data`: the
callback inspects an input that is retained in the group, and the previous
key is retained for comparison. Groups are materialized Lists.

`windows(~A, width)` emits only complete overlapping List windows. Thus
`windows(2)` over `[1, 2, 3]` emits `[1, 2]` and `[2, 3]`, whereas
`partition_all(2)` retains its partial-tail behavior. A width of zero stops
before the source drives an item, matching the existing `partition_all(0)`
convention. Widths greater than the source length emit nothing. Overlap needs
`A: Data`, since one value belongs to consecutive windows. The implementation
keeps a reusable List of recent items, then copies each complete window to the
affine List type expected by downstream reducers. This is intentionally a
materializing transformation.

`window2(~A)` specializes the common width-two case. It emits `(A, A)` tuples,
keeps only the preceding value, and inherits the downstream stop permit.
`window3(~A)` analogously emits `(A, A, A)` tuples from its two-value prefix.
Neither builds a List per window. `Vec.adapter(~A)` also makes Vec a raw
fragment type for `cat`; Vec was already a source and destination.

The JS/native fixtures cover full and incomplete windows, widths zero through
four, Array and custom sources, ordered output, tuple windows of widths two
and three, `take` on either side, initial stopping, group completion, and Vec
as source, destination, and cat fragment.
The differential suite additionally checks 47 generated grouping/window cases
against independent Python results, including repeated values.

## Native width-two comparison

[`bench/windows2.bend`](../../bench/windows2.bend) consumes the same owned
List of ascending `U32` values in three ways: a handwritten adjacent sum,
`windows(2) → map(sum pair) → sum`, and
`window2() → map(sum tuple) → sum`. The input is built before the timer. The
runner uses Clang `-O3`, one thread, GPU off, 16 shuffled paired sessions per
size, and the compiler fork at `1b4f641b`. Heap calls count the generated C
`heap_alloc` calls inside the timed interval.

| Input items | Handwritten | `windows(2)` | `window2()` |
| ---: | ---: | ---: | ---: |
| 65,536 median µs | 253 | 1,819.5 | 235.5 |
| 65,536 timed heap calls | 9 | 458,758 | 10 |
| 262,144 median µs | 1,034 | 7,207.5 | 996.5 |
| 262,144 timed heap calls | 9 | 1,835,014 | 10 |

The tuple path is close to the handwritten fold in this run; the small median
difference is within timing noise. The generic List path is about 7 times
slower at 262,144 items because it constructs each window. This benchmark
consumes windows immediately; retaining the windows necessarily preserves
their storage cost. Other widths, source types, and consumers have not been
benchmarked. Raw samples and allocation counts are in
[`bench/windows2-results.json`](../../bench/windows2-results.json).
`window3` is covered by semantics tests but has not yet had a matching native
performance comparison.
