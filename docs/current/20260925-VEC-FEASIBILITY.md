---
created_at: 2026-09-25T15:24:57+02:00
updated_at: 2026-09-25T15:33:58+02:00
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

The remaining cost for arbitrary affine `T` is empty-slot construction.
`Array.new` requires a `Data` element, whereas `Maybe<T>` is a `Type` when
`T` may be affine. Our affine `empty_slots` therefore builds a tree of
`None` leaves. Repeated growth constructs many intermediate blocks, even
though the final Array is flat.
At 200,000 inputs, the capacity is 262,144 and timed allocation requests are
about twice that capacity. Crossing from 131,072 to 131,073 elements doubles
Vec's timed requests from 262,158 to 524,302.

For `Data` elements, Bend has a better library-only route. Explicitly
writing `Maybe<&2, T>` makes the slot type `Data` whenever `T` is `Data`;
`Array.new(Maybe<&2, T>, depth, None{})` then creates a flat vacant block.
A second `VecFill<T: Data>` keeps a caller-provided filler value and stores
`Array<T>` directly, removing the `Maybe` tag. The filler is never exposed
from the initialized prefix. Both variants compiled and ran with a custom
`Quad` Data type, not just `U32`. The filler variant's checked `get` and
`set` use flat Array indexing; JS and native agree on ordered output,
replacement of an initialized slot, an out-of-range lookup, downstream
`take(2)`, and initial `take(0)` stopping.

The final 24-session paired native sample uses 200,000 List inputs, Clang `-O3`,
one thread, microsecond timing, and counts runtime heap requests during the
timed region. Every lane builds a collection and consumes its values by sum.
The direct Array lane starts with 262,144 zero slots and visits only the
initialized prefix, so it is a representation baseline for `U32`, not a
generic affine Vec implementation.

| Path | Median time | Timed allocation requests |
| --- | ---: | ---: |
| Direct List build and sum | 273.5 µs | 9 |
| `into(List)` and sum | 487.0 µs | 200,011 |
| Direct Array fill and indexed sum | 280.0 µs | 10 |
| Affine Vec, direct push and source sum | 5,077.0 µs | 524,298 |
| Affine Vec, `into` and source sum | 5,262.0 µs | 524,302 |
| `VecData<Maybe<&2,T>>`, `into` and sum | 1,915.5 µs | 52 |
| `VecFill<T: Data>`, `into` with growth and sum | 556.5 µs | 52 |
| `VecFill<T: Data>`, reserved capacity, `into` and sum | 309.0 µs | 16 |

The paired median `into(VecFill)` / direct Array ratio is 1.976 (95% bootstrap
interval 1.805–2.029) with growth and 1.152 (1.053–1.420) when capacity is
reserved. Dynamic growth copies a flat block at each doubling, just as an
ordinary growable vector must move its contents when it reallocates. The
`into(VecFill)` / handwritten VecFill builder ratio is 1.091 (1.057–1.138),
so the adapter is modest overhead. The `Maybe<&2,T>` Data variant has the
same low allocation count but is 3.4 times slower than the filler variant.
The extra tag representation and per-element branch are likely contributors;
this benchmark does not isolate their individual costs.

This makes an ordered, generic `Data` destination feasible without a compiler
change. `VecFill.empty(fill)` needs an explicit filler; `reserve(depth, fill)`
can approach a known-size Array. The affine `Type` version still merits a
narrow `Array.new_none<T>(depth)` experiment, but merely removing its
allocation explosion would not prove it is fast: the Data `Maybe` variant
shows optional-slot costs may remain. Repeating a particular `None`
constructor could be safe; relaxing `Array.new` from `Data` to arbitrary
`Type` would not be. The temporary compiler copy with that blanket signature
change was rejected by Bend's ownership checker and was not used for results.
Indexed lookup for the affine Vec currently swaps out and restores a slot;
its cost was not separately benchmarked. These are prototypes: a production
Vec also needs a defined maximum capacity and checked overflow when doubling,
plus a clear choice between exposing filler-based and optional-slot APIs.

The fixtures are `experiments/affine_xf/vec_probe.bend`,
`vec_data_probe.bend`, `vec_data_fill_probe.bend`, and
`vec_data_semantics.bend`; the paired benchmark is
`experiments/affine_xf/measure_vec.py`. Full samples and hashes are in
`experiments/affine_xf/vec-200k-results.json`.
