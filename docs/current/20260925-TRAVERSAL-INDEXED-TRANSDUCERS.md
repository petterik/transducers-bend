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
measurements use 36 interleaved native runs per size, one thread, GPU off,
Clang `-O3`, and compiler fork `1b4f641b`.

| Layout | List length | Direct median µs | Transducer median µs | Paired median transducer/direct |
| --- | ---: | ---: | ---: | ---: |
| Direct first | 65,536 | 66 | 78 | 1.09× |
| Direct first | 262,144 | 268 | 279 | 1.08× |
| Transducer first | 65,536 | 80 | 80.5 | 0.99× |
| Transducer first | 262,144 | 234 | 288 | 1.18× |

The direct path made nine timed native `heap_alloc` calls, and the public path
made fifteen, at both sizes. Thus this mixed pipeline fuses without a
per-element intermediate allocation, but **direct-speed parity is not
established for every compiled layout**. Mirroring only the call order changes
the relative time. Removing `drop` also changes both generated programs, and
the handwritten direct path gets much slower in this sample; that ablation
does not isolate a `drop` cost. It does show twelve constant
timed allocation calls in the no-drop public path, again with no per-element
allocation. The four [normal](../../bench/new-transducer-fusion-20260925.json),
[mirrored](../../bench/new-transducer-fusion-mirror-20260925.json),
[no-drop](../../bench/new-transducer-fusion-no-drop-20260925.json), and
[no-drop mirrored](../../bench/new-transducer-fusion-no-drop-mirror-20260925.json)
raw records contain every sample and compiler/fixture hash.

These results support the general fusion mechanism for these stages but leave
an 8–18% paired native timing gap in several full-pipeline runs. It could be
stage-state work, code layout, or both. A compiler rewrite or a source-specific
fast path would need better attribution and a broader regression matrix; this
workset adds neither.
