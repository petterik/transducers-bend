---
created_at: 2026-09-25T15:24:57+02:00
updated_at: 2026-09-25T15:24:57+02:00
status: measured
---

# Array-backed Vec feasibility

An experimental `Vec<T>` now owns an `Array<Maybe<T>>`, a logical length,
capacity, and tree depth. It appends in order, doubles capacity, offers
checked indexed replacement, and acts as both an `into` destination and a
source. Its source uses indexed `Array.swap` to consume initialized slots and
preserves downstream stopping. Compiled JS and native agree on growth through
capacities 1, 2, and 4; indexed replacement and lookup; ordered collection;
and affine `Token` elements.

The first implementation walked the Array through `ANode`/`ALeaf`. That
obscured Bend's actual representation. The native compiler lowers an Array
to a flat block: `Array.set` and `Array.swap` compute a cell address, while
`Array.new` allocates one block. Matching `ANode` splits a block and
constructing `ANode` joins blocks; both allocate and copy. The JS compiler
likewise represents an Array as a JS array, with indexed mutation and
`concat` for `ANode`. Vec source traversal was changed to indexed reads,
removing about half its timed allocation requests.

The remaining cost is empty-slot construction. `Array.new` requires a `Data`
element, whereas `Maybe<T>` is a `Type` when `T` may be affine. Our generic
`empty_slots` therefore builds a tree of `None` leaves. Repeated growth
constructs many intermediate blocks, even though the final Array is flat.
At 200,000 inputs, the capacity is 262,144 and timed allocation requests are
about twice that capacity. Crossing from 131,072 to 131,073 elements doubles
Vec's timed requests from 262,158 to 524,302.

The 24-session paired native sample uses 200,000 List inputs, Clang `-O3`,
one thread, microsecond timing, and counts runtime heap requests during the
timed region. Every lane builds a collection and consumes its values by sum.
The direct Array lane starts with 262,144 zero slots and visits only the
initialized prefix, so it is a representation baseline for `U32`, not a
generic affine Vec implementation.

| Path | Median time | Timed allocation requests |
| --- | ---: | ---: |
| Direct List build and sum | 348.5 µs | 9 |
| `into(List)` and sum | 416.0 µs | 200,011 |
| Direct Array fill and indexed sum | 379.5 µs | 10 |
| Direct Vec push and source sum | 5,026.5 µs | 524,298 |
| `into(Vec)` and source sum | 5,258.0 µs | 524,302 |

The paired median `into(Vec)` / direct Vec ratio is 1.053 (95% bootstrap
interval 1.036–1.064). The transducer adapter is a small share of this cost.
`into(Vec)` / direct Array is 14.01 (interval 12.49–18.75). The direct Array
result confirms that Bend's flattened Array and indexed operations can be
fast; this Vec builder fails because of how it creates generic vacant slots.

The next narrow experiment is a type-safe `Array.new_none<T>(depth)`-like
primitive that allocates one Array block filled with `None`, even when `T`
is affine. Repeating a particular empty constructor is safe; relaxing
`Array.new` from `Data` to arbitrary `Type` is not. If a single-block vacant
Array brings Vec close to direct Array, the general compiler/API proposal is
justified. Until then this Vec is an experiment, not a recommended default
destination. Indexed lookup for `Data` currently swaps out and restores the
slot because `Maybe<T>` itself is not `Data`; a purpose-built borrowed read
could improve that separately.

The fixture is `experiments/affine_xf/vec_probe.bend`; the paired benchmark
is `experiments/affine_xf/measure_vec.py`. Full samples and hashes are in
`experiments/affine_xf/vec-200k-results.json`.
