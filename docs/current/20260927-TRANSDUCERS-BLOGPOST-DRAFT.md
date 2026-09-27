---
created_at: 2026-09-27
status: evidence-backed-draft
---

# Fusing transducers in Bend until a million items look like a C loop

Bend had just come out when I started this experiment. I wanted to write a
generic transformation once, compose it with other transformations, and see
whether the result could run as efficiently as a loop I would write in C.

Here is the small version:

```bend
# Clojure: (transduce (map inc) + 0 xs)
def transducer(xs: Array<U32>) -> U32:
  X.transduce(X.map(~U32, ~U32, ~U32.inc), X.sum_rf(), 0, xs)
```

The [exact fixture](../../bench/public_array_map_inc_sum.bend) builds one
million U32 values before the timer and includes traversal and disposal in
the timed interval. On my M3 Max, 36 shuffled, paired runs gave medians of
**76 µs in Bend, 80.5 µs in handwritten C, and 80 µs with a Rust iterator**.
All three produced the same wrapping U32 checksum. That is parity for this
array shape and operation, not a promise about every transducer.

More satisfyingly, the Bend compiler emitted C that Clang 17 turned into a
four-lane ARM vector loop. The inner assembly uses `ldp q4, q5` and
`sub.4s`/`add.4s` instructions. It is a useful sanity check: composition
did not leave a callback, boxed number, or per-item stage allocation in the
hot loop of this fixture.

Rust's [`Iterator`](https://doc.rust-lang.org/std/iter/trait.Iterator.html)
already gives programmers generic `map`, `filter`, and `fold` with strong
optimization opportunities. I chose the word *transducer* because I came to
this idea from Clojure. The interesting part here is making the same style of
source-independent composition work in Bend's type and ownership model.

## Why decouple the transformation?

[Clojure introduced transducers in 1.7](https://clojure.org/news/2015/06/30/clojure-17).
A transducer describes what happens to each input without choosing a source
collection or an output collection. `map inc`, `filter even?`, and `cat` can
therefore compose before any List, Array, stream, or destination is involved.

That gives each new component several immediate uses. A new source can feed
every existing stage. A new stage works with every source and destination.
A new destination can collect the results of every existing pipeline. The
source supplies items; the stages transform or skip them; the reducer owns
the result.

The Bend library currently has List, Array, Range, String, Vec, and VecMaybe
sources. Its Array source reads reusable `Data` elements; an explicit affine
Array source consumes structural nodes for elements that cannot be copied.
There is still one implementation of `map` and one of `filter`.

## The Bend contract

Clojure's [reference](https://clojure.org/reference/transducers) defines a
transducer as a function that transforms a reducing function. The resulting
reducing function supports initialization, stepping, and completion; a
`reduced` value can stop the process. `transduce` applies the transformation
to a reducer and then drives a source. `into` collects, while `sequence`
computes elements incrementally.

My Bend `Xf` is an owned stage value with a static recipe and runtime
configuration. `X.transduce(xf, rf, initial, source)` configures that recipe
with the reducer, starts it once, asks the source to drive it, and completes
it once. The initial value is always explicit. A stage value is used once;
construct another for another run. The current library implements
`transduce` and `into`, but no lazy `sequence` operation.

For an ordered destination, this is the Bend version of Clojure's vector
example:

```bend
# Clojure: (into [] (map inc) [1 2 3])
X.into(Vec.empty(~U32, 0),
  X.map(~U32, ~U32, ~U32.inc), numbers())
```

Here `numbers()` returns `[1, 2, 3]`; the
[checked example](../../tests/blogpost_examples.bend) verifies encounter
order through an indexed checksum. It yields `[2, 3, 4]`. A List destination prepends in this implementation,
so Vec is the ordered choice here.

The public source interface is `Type.source(value)`, not `.reduce` and not
a pull iterator. Its driver owns the source, receives a step and an inspect
callback, and returns an opaque state. It calls `inspect` before the first
item and after each step. When `inspect` says `Halted`, it stops providing
items. This makes the source responsible for the traversal it can perform
efficiently, while leaving all stage logic reusable.

For example, `Array.source` is a normal Bend definition that returns a
`Source` witness. Adding that owner method needed no language change.
Passing the raw Array to `X.transduce` did need a compiler rule: when the
expected nominal type is marked as a source protocol, the checker looks for
the corresponding method owned by the actual type (or the protocol module's
extension for a Base type). It inserts `Array.source(xs)` and solves leading
`~?AUTO` template arguments from the checked argument types. It declines
ambiguous or structurally unmatched cases. The implementation is in the
fork's `bend2/bend.ts`, and the
[public API guide](20260925-PUBLIC-API.md) has extension examples.

## What makes composition disappear?

`map` itself is almost boring:

```bend
# Clojure: (map inc)
def map(~A: Type, ~B: Type, ~f: A -> B) -> Xf<A, B,
  (R => down => T.map(~A, ~B, ~R, ~f, ~down))>:
  Xf{R => down => config => config}
```

The stage describes how to wrap a downstream reducer. Its callback is static;
it need not be a runtime closure for every item. The compiler's bounded
`specialize` pass resolves a computed function head when it can prove the
head is static. It then applies the known lambda to the dynamic argument,
binding that argument once when ownership requires it. Ordinary named calls
remain calls. This is a general compiler mechanism; it recognizes no
transducer names.

The same principle applies to `filter`: it decides whether to forward an
input to the downstream step. A selected item still requires a
data-dependent condition. In a retained List-chunk experiment, static
callback specialization removed transient heap objects and made the
pipeline 4.8–5.5 times faster than the unspecialized compiler. That
[ablation](20260924-TRANSDUCER-FUSION-ABLATION.md) is a different workload;
it is not the speedup for the million-item Array example above. Output
chunks retained by the program still allocate.

There is also a useful type-level fact about stopping. A total reducer uses
`Control<Empty, S>`; `Empty` has no values, so live checked code cannot
construct its `Stop{permit, state}` arm. `take` and other stopping stages use
an inhabitable permit and retain their stop path. The compiler's generic
uninhabited-arm rule deletes branches only when a live field's instantiated
type has zero constructors. It does not special-case `map` or `filter`.
The [checked List law](../../proofs/no_stop_control_law.bend) exercises this
`Control<Empty, U32>` boundary. I would not attach a universal “10% faster”
number to the rule: earlier single-binary timing changed by about that much
when only native code placement changed.

## The Array mask that stopped SIMD

Even with the stages fused, a flat Array benchmark was initially about
twice as slow as C. `Array.get` preserves Bend's wraparound semantics by
masking every index. Our source was walking from zero to the size, so the
mask did no useful work, but it hid a simple contiguous stream from Clang.
A generated-C probe showed the opportunity; a probe was not enough to make
an unchecked read part of the language.

I added a generic `Array.walk` to Bend Base. It owns the Array and controls
both the next index and remaining count. The public entry derives the size;
the caller cannot hand it an arbitrary start index. It inspects for a stop
before every read. The compiler checks the whole span once at loop entry
and uses the unmasked offset when valid:

```c
u64 _walk_size_0 = 1ull << (blk_cls(_checked_1) - 0);
bool _walk_bounded_0 = (u64)_index_0 <= _walk_size_0
  && (u64)_remaining_0 <= _walk_size_0 - (u64)_index_0;
Term _at_1 = _walk_bounded_0
  ? ((u32)_index_0 << 0)
  : blk_at(_checked_1, _index_0, 0);
```

The fallback preserves masked reads for malformed direct calls to the
helper. The normal walk starts with `index = 0`, `remaining = size`, then
increments one while decrementing the other. Their sum remains the size;
when remaining is positive, the next index is in bounds. The native path
still performs each block lookup and the usual element keep/disposal, which
matters for boxed, multiword, and shared Array handles.

The implementation passes 64 library cases, 1470 fork compiler cases, and a
Metal execution fixture. Tests cover initial and later stops, callback counts,
one-element Arrays, String and multiword elements, shared storage, and
rejection of affine elements on this path. These are tests plus a bounds
argument, not a machine-checked proof of the C emitter.

On the larger `map → filter → sum` fixture, the integrated version took
**188.5 µs**, C **199 µs**, and Rust's iterator chain **195.5 µs** at one
million elements in 36 paired runs. Clang reported width-four vectorization
for the actual Bend traversal loop. The timed Bend interval made ten heap
allocation calls, versus millions when the fixture materialized a filtered
List. It did not allocate one stage object per element; it did still allocate
elsewhere in the run. [Raw samples and exact flags](20260927-ARRAY-WALK-INTEGRATION.md)
are available.

## Bullet Cathedral

I used the library for a bullet-hell scene: 256 moving shield drones in a
16×16 grid, up to 12,288 active bullets, swept-circle collision checks, hit
history, and a 512×512 CPU framebuffer. A bullet is generated from its ID as
the source is driven rather than stored in a bullet collection. The friendly
path expands each bullet to at most nine nearby drone cells:

```bend
# Clojure: (into [] (comp (map bullet-at) (filter onscreen)
#   (filter friendly) (map near) cat (filter valid-cell)
#   (filter hit?) (map as-hit)) active-ids)
X.into(empty_hits(), X.comp2(X.comp5(
  X.map_with(~U32, ~Bullet, ~U32, ~bullet_at, frame),
  X.filter(~Bullet, ~onscreen),
  X.filter(~Bullet, ~friendly),
  X.map(~Bullet, ~Nearby, ~near),
  X.cat(Nearby.adapter())),
  X.comp3(X.filter(~Candidate, ~valid_cell),
    X.filter(~Candidate, ~hit),
    X.map(~Candidate, ~Hit, ~as_hit))), active_ids(frame))
```

The renderer uses another chain to expand sprites to bounded rectangles,
clip to circles, calculate radial color, and blend into a flat framebuffer.
The framebuffer, accepted-hit history, and event Vec are intentional stored
state. The pipeline does not materialize every candidate or pixel as a
separate collection.

![Bullet Cathedral at frame 96](../../bench/bullet-cathedral-frame-096.png)

[Watch the 120-frame video](../../bench/bullet-cathedral.mp4).

For the 512×512 scene I also wrote [C](../../bench/bullet_cathedral_control.c)
and [Rust](../../bench/bullet_cathedral_control.rs) controls. All three
implementations produced the **same checksum, accepted-hit count, and shield
value on every one of 120 frames**. The independent all-drone oracle checked
54,018,048 bullet–drone pairs; all 76,049 geometric overlaps were in the
nine-cell search. A separate [geometry argument](../../proofs/bullet_cathedral_geometry.md)
shows why the scene's bullet and drone motion bounds make the nine cells
sufficient. The oracle is an exhaustive test of this deterministic run, not
a theorem for arbitrary scenes.

| 120 frames, one CPU thread | Bend | C | Rust |
| --- | ---: | ---: | ---: |
| Median internal time, fresh framebuffer | 405.4 ms | 242.7 ms | 227.8 ms |
| Handwritten scene code lines | 567 | 230 | 250 |
| Handwritten lexical tokens | 7,989 | 3,092 | 3,122 |

The timing includes initial scene setup, simulation, rendering, a fresh
framebuffer each frame, pixel checksums, and cleanup, but no presentation.
Reusing a framebuffer measured
almost the same for C and Rust on this fixture. C was compiled with
`-ffp-contract=off` to match Bend's F32 rounding exactly. The code count
includes each scene's CLI harness and excludes
imported libraries and generated C. Bend's reusable `xf.bend` and
`transduce_core.bend` are separate files used beyond this scene. On this
showcase, C and Rust are faster and shorter by these measures. The
[comparison report](20260927-BULLET-CATHEDRAL-CROSS-LANGUAGE.md) gives the
raw samples and counting rule.

The allocation counts point to a different scale of work from the tiny flat
Array folds: 133,671 timed Bend native heap-allocation calls over 120 frames,
versus 1,126 Rust allocator calls in the fresh-buffer lane and 120 explicit
framebuffer `malloc` calls in the fresh C scene. Those interfaces count
different kinds of allocator requests, so I use them as observations rather
than a normalized memory-cost ratio.

The live 1920×1080 Bend version presented roughly 38–40 FPS after startup on
one CPU thread on my machine. That is a separate windowed measurement, not
the 512×512 headless comparison above.

## Proofs and what they establish

Bend checked source-level laws for this work. Two prove, by induction over a
List, that `map` followed by a left fold agrees with sending each mapped
value directly to the fold, and that two maps compose into one. Another uses
the library's actual `Control<Empty, U32>` type and proves a no-stop List
driver agrees with a total fold. A further proof uses the actual `T.map`,
`T.filter`, `T.step`, and `T.sum` constructors to establish their local
single-step behavior. The exact statements and commands are in
[`proofs/`](../../proofs/README.md).

I also have a bounds argument for `Array.walk`, a mathematical argument for
Bullet Cathedral's collision and index bounds, and an independent exhaustive
oracle for this animation. The complete transducer API, Bullet Cathedral
geometry, generated C, and native runtime are **not** covered by
machine-checked end-to-end theorems. No machine-checked proof accompanies
the C or Rust controls. The evidence is useful when kept at its actual
scope.

## What happened to existing Bend programs?

Against an archive of the fork before `Array.walk`, all 16 of Bend's local
runtime benchmarks compiled and produced the same output after the change.
All five checker benchmarks passed on both sides. Three local one-thread CPU
runs per runtime case showed most median ratios very near 1.0. The one
apparently large speed difference had byte-identical generated C, so it
cannot be credited to this compiler change. A separate eight-thread CPU
pass matched outputs in all 16 cases, with current/base median ratios from
0.984 to 1.017. Five paired Metal runs of each upstream runtime case also
matched outputs, with median ratios from 0.996 to 1.011. The
[local report](20260927-UPSTREAM-LOCAL-REGRESSION.md) gives the scope and
raw times. It is not the upstream M4 cluster performance gate.

## Where I landed

The small Array pipelines show that generic Bend stages can fuse into a
plain vectorized traversal, reaching C and Rust iterator time for these
fixtures. The larger scene shows the limit just as clearly: writing the
simulation and renderer with reusable transducers did not automatically
make it as fast or as short as the direct ports. I still like the programming
model. New sources, stages, and destinations reuse each other, and the
compiler optimizations that made it viable are general enough to help other
Bend code.

This is an experiment in a Bend fork. To the Bend developers: thank you for
making a language interesting enough to try this in. If any of these changes
are useful to you, please take and reshape them. ❤️

## Reproduce the numbers

The measured machine used Bun 1.3.8, Apple Clang 17.0.0, and Rust 1.95.0.
The measured Array source is in library commit `365326e`, and the compiler
change is in fork commit `cedde735`. Some reports were recorded before those
commits, so their commit fields name the parent heads; their source and
compiler hashes pin the measured edits. The complete samples, inputs,
outputs, scope, and flags are
in the reports linked above.

```sh
python3 tests/run.py
python3 bench/public_array_map_inc_sum.py --output bench/public-array-map-inc-sum-20260927.json
python3 bench/public_array_map_filter_sum_rust.py --depths 16 18 20 --sessions 36 --output bench/public-array-map-filter-sum-rust-integrated-20260927.json
python3 bench/bullet_cathedral_cross_language.py --frames 120 --sessions 21
bun ../bend/bend2/main.ts proofs/list_map_fold_law.bend
bun ../bend/bend2/main.ts proofs/no_stop_control_law.bend
bun ../bend/bend2/main.ts proofs/api_stage_laws.bend
```

The cross-language runner checks all 120 frame triples before taking timed
samples. The local upstream regression scripts and reports are linked in
their [comparison note](20260927-UPSTREAM-LOCAL-REGRESSION.md).
