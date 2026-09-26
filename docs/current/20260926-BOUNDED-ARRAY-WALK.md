---
created_at: 2026-09-26
status: proposed-compiler-optimization
---

# Bounded Array walk for native transducer performance

The public `Array.source` already reads by index, but the compiler lowers each
`Array.get` through `blk_at(array, index, layout_shift)`. That masks the index
to preserve Bend's documented wraparound behavior. In the source's sequential
walk, every index is already in bounds. The mask prevents Clang from seeing a
simple stream of contiguous reads in the map/filter/sum benchmark.

## Evidence and limit

The [probe](../../bench/probe_array_nomask.py) changes only the generated C
offset of the public Array source's read from
`blk_at(_checked_1, _index_0, 0)` to `_index_0`. It does not change the stage
composition, reducer, stop protocol, block lookup, read, or disposal. The
independent checksum matched for three sizes and two seeds. On the tested M3
Max at 1,048,576 elements, the medians were approximately 352 µs for the
current transducer, 243 µs for direct Bend, and 178 µs for both the prototype
and handwritten C. The [raw probe results](../../bench/array-nomask-probe-20260926.json)
contain every sample. Clang reported full four-wide loop vectorization for
the prototype; the current public loop was interleaved but not fully widened.

The probe edits generated C for one `Array<U32>` fixture. It is evidence of
the performance opportunity, not a sound general change to `Array.get` or a
production compiler fix. A per-read in-bounds branch kept semantics but
measured about 509 µs in a separate one-million-element control, so adding a
branch to every `Array.get` is not the answer here.

## Chosen approach

Add a safe, compiler-recognized `Array.walk` operation in Bend Base. It owns
the Array and its index, calls a supplied inspection function before each
read, and then calls a specialized step function with the next value. The
public `Array.source` can delegate to this operation. Its ordinary Bend
definition gives the checker and JS lane the semantics; the native lowering
can use an unmasked element offset *inside this operation only*.

The walk controls the index, so callers cannot use it to request an arbitrary
out-of-bounds read. General `Array.get` keeps wraparound. This is preferable
to a public unchecked getter, and it avoids tying the Bend compiler to this
transducer library's function names. General compiler range analysis would
be broader and more complex than this one needed traversal. Compiler hints
on the existing masked read did not recover full vectorization in the probe.

The native lowering should keep `blk_loc` and the existing element-layout
read on each iteration. For boxed or multiword `Data` values it must preserve
the existing `blk_keep` and `arr_cells` behavior. It changes only the offset
from `(index & (size - 1)) << layout_shift` to
`index << layout_shift` within the walk. Keeping block lookup per iteration
also preserves behavior when another handle from `Array.fork` shares the
storage. The explicit affine Array source remains structural because
`Array.get` cannot read affine elements.

## Why the unmasked offset is safe in the walk

Let `n` be the Array's size, `i` the next index, and `r` the remaining count.
Initially `i = 0` and `r = n`. Every continuing step changes them to
`i + 1` and `r - 1`, so `i + r = n` remains true. A read occurs only when
`r > 0`, hence `i < n`. Inspection occurs before the read; a halted walk
does not read or invoke the mapper again. The block depth limit in Bend's
native runtime requires `depth + layout_shift <= 31`, so the final element
offset remains inside the allocated block and the U32 index does not wrap.
The Array is owned throughout the walk; its size cannot change.

This argument establishes the intended contract, not the correctness of a
future implementation. The native and JS implementations must be checked
against the ordinary Bend definition.

## Completion gates

1. Define the safe walk and adapt `Array.source` without changing user-facing
   transducer calls or ordinary `Array.get` behavior.
2. Differentially check JS and native on one-element Arrays, all relevant
   element layouts (including boxed and multiword `Data`), shared handles,
   and stop positions zero, one, middle, and end. Confirm no step after stop.
3. Check GPU compilation and results. Preserve the explicit affine source.
4. Re-run the [flat Array comparison](../../bench/PUBLIC-ARRAY-VS-C.md) and
   inspect vectorization remarks and generated code. Performance parity is a
   measured goal, not a semantic assumption.

Reproduce the current codegen probe from this repository with the supported
sibling Bend checkout:

```sh
python3 bench/probe_array_nomask.py --output /tmp/array-nomask-probe.json
```
