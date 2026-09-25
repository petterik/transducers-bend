---
created_at: 2026-09-25T22:14:00+02:00
status: validated-locally
---

# Traversal and indexed transducers

The public `xf.bend` API now includes `drop`, `take_while`, `drop_while`,
`map_indexed`, `keep_indexed`, `take_nth`, and `cat`. All are ordinary reducer
adapters in `transduce_core.bend`; they use the existing source-owned drive and
require no compiler change.

`drop(n)` discards the first `n` owned values. It accepts affine elements and
inherits the downstream stop permit. `take_while(predicate)` passes the
matching prefix and stops the source at the first failure; its own stop permit
is `Unit`. `drop_while(predicate)` discards only the initial matching prefix,
then forwards the rest without rechecking the predicate. The predicate stages
currently require `Data` elements, like `filter`, because they inspect an item
that may then be passed downstream. All three initialize their downstream
reducer once and complete it once, including after an initial or mid-source
stop.

`map_indexed(f)` calls `f(index, item)` with a zero-based `Nat` index for every
item that reaches the stage. `keep_indexed(f)` is that stage followed by
consuming `Maybe` output, so omitted values still advance the index. Both
accept affine input. Indexed counters use Bend's checked `Nat` arithmetic.
`take_nth(n)` passes the first item and then every `n`th item. At `n=0`, it
emits nothing but still consumes the source: this preserves a total downstream
permit and avoids adding a per-item stopping path. Use `take(0)` when immediate
source stopping is required. This zero case is a Bend-specific convention.

`cat` flattens each reducible fragment and carries the downstream stop permit
through the inner drive, including a stop in the middle of a fragment. It uses
the same generic `cat_source` reducer as `mapcat`. `comp2(map(f), cat(...))`
therefore handles a callback returning a List, Array, or custom reducible
fragment without introducing a special List implementation. The fragment's
static `Drive` is still explicit: companion selection does not currently infer
source implementations inside an arbitrary mapper's return type. Materializing
a fragment remains a real allocation cost.

The [traversal fixture](../../tests/xf_public_traversal.bend) covers List,
Array, Range, and a custom source, affine dropping, zero and oversized counts,
ordering relative to `take`, and retained output. Its
[completion fixture](../../tests/xf_public_traversal_completion.bend) covers
partial partition flushing and downstream stops. The
[indexed/cat fixture](../../tests/xf_public_indexed_cat.bend) covers affine
mapping and flattening, ordered output, zero and positive `take_nth` intervals,
Array and custom fragments, and nested stopping. The
[differential suite](../../tests/public_differential.py) checks 44 generated
List cases for these stages against independent Python results on native and
JavaScript backends, in addition to its existing scalar and partition cases.

The [native fusion benchmark](../../bench/new_transducer_fusion.bend) compares
`drop(32) → map_indexed → take_nth(3) → sum` with a handwritten Bend fold over
the same owned List. The direct version has a separate prefix-skip loop and a
steady-state loop; source construction occurs before the microsecond timer.
The [runner](../../bench/new_transducer_fusion.py) can mirror dispatch order
and remove `drop` in both variants to test code-layout and stage costs. Its
measurements should be read as local compiled-program results, not a universal
speed claim.
