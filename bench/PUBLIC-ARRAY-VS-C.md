# Indexed Array source and map/filter/sum comparison (2026-09-26)

Bend's `Array` has a structural `ANode`/`ALeaf` type, but its native storage
is a flat block. The public `Array.source` now calls `Array.get` at successive
indexes. It no longer matches tree constructors for ordinary `Data` elements.
This is the same indexed operation used by `Vec`. The source checks for a
downstream stop before each read. `Array.get` requires `Data`, so arrays of
affine `Type` elements use the explicit `Array.affine_source` and
`Array.affine_adapter`, which consume the structural view.

The [Bend fixture](public_array_map_filter_sum.bend) creates an `Array<U32>`
of `2^depth` values using indexed writes. Each value is transformed with two
U32 multiplications, two xors and two shifts. The filter keeps values whose
low byte is below 96; the reducer sums them modulo `2^32`. This gives the
fused pipeline arithmetic work while still passing roughly 3/8 of its input.
The input is constructed before timing. Traversal and disposal of the input
are inside the interval.

The compared paths compute the same checksum:

| Path | Implementation |
| --- | --- |
| Public transducer | `map` then `filter` then `sum_rf` on the raw Array source |
| Direct Bend | Handwritten indexed `Array.get` loop with the same transform and branch |
| Materialized Array mask | `Array.map(transform)`, `Array.map(mask)`, then indexed sum; masking with zero represents a rejected value for this sum |
| Materialized List filter | `Array.map(transform)`, `Array.to_list`, construct a filtered List, then `List.foldl` |
| Manual C | One contiguous `uint32_t*`, one fused handwritten loop, and `free` inside the timer |

On an M3 Max, native CPU with one thread, Apple Clang 17 `-O3`, 36
randomized process runs per path and size gave these **median microseconds**:

| Elements | Selected | Public transducer | Direct Bend | Array mask | List filter | Manual C |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 65,536 | 24,776 | 23 | 15 | 119 | 1,026 | 12 |
| 262,144 | 98,333 | 89 | 61 | 461.5 | 4,091.5 | 45 |
| 1,048,576 | 393,287 | 352 | 243 | 1,849.5 | 16,422 | 178 |

All paths matched an independent Python checksum at every size. At one
million elements, the public pipeline is 1.45 times the direct Bend loop and
1.98 times handwritten C. It is 5.25 times faster than the materialized Array
mask and 46.7 times faster than materializing a filtered List. The Array mask
is an equivalent control for this sum, but does not produce a compact filtered
collection. The List path does produce that collection and pays for its nodes
and the Array-to-List conversion. These are distinct materialization costs.

Instrumenting the generated Bend C's heap allocation function **inside the
timed interval** at one million elements found 10 calls for the public
transducer, 9 for direct Bend, 11 for Array mask, and 3,539,023 for the List
path. This supports the claim that the fused numeric path does not allocate
one object per element; it does not prove every machine instruction is
unboxed. The [raw results](public-array-map-filter-sum-20260926.json) record
all samples, allocation counts, checksums, toolchain, and source hashes.

Reproduce with the supported sibling Bend compiler checkout:

```sh
python3 bench/public_array_map_filter_sum.py --depths 16 18 20 --sessions 36 --output bench/public-array-map-filter-sum-20260926.json
```

The fixture accepts depth and seed as run parameters but needs no external
data. These results are local CPU measurements of this transform, not GPU
throughput or display frame rate. The public transducer's residual cost versus
direct Bend remains visible here; the comparison does not claim parity with
handwritten C.

The [bounded Array walk proposal](../docs/current/20260926-BOUNDED-ARRAY-WALK.md)
records a generated-C probe that reaches manual C speed by removing only the
redundant index mask in this source walk. The production compiler still emits
the masked read measured above.
