---
created_at: 2026-09-27
status: current-evidence-ledger
---

# Claims for the transducers article

| Claim in draft | Status and scope | Evidence |
| --- | --- | --- |
| Clojure transducers arrived in 1.7. | Verified historical fact. | [Official 1.7 announcement](https://clojure.org/news/2015/06/30/clojure-17) |
| Clojure's transducer transforms a reducing function and supports init, step, completion, and reduced termination. | Verified for the referenced Clojure contract. | [Official reference](https://clojure.org/reference/transducers) |
| Rust has generic iterator `map`/`filter`/`fold` as prior art. | Verified API fact; performance is measured only in our fixtures. | [Rust Iterator documentation](https://doc.rust-lang.org/std/iter/trait.Iterator.html), [simple raw report](../../bench/public-array-map-inc-sum-20260927.json) |
| Bend stages are source-independent; `transduce` configures, starts, drives, and finishes once. | Verified against current source and public tests. | [`xf.bend`](../../xf.bend), [`transduce_core.bend`](../../transduce_core.bend), [API guide](20260925-PUBLIC-API.md) |
| A raw Array is converted through `.source`, not `.reduce` or a pull iterator. | Verified against current source/compiler. | [`Array.source`](../../transduce_core.bend), sibling fork `bend2/bend.ts` companion rule, [API test](../../tests/blogpost_examples.bend) |
| Flat `map(inc) → sum` is at C/Rust time at one million. | Verified on M3 Max, 36 paired sessions; 76 / 80.5 / 80 µs median Bend/C/Rust iterator. | [Raw report](../../bench/public-array-map-inc-sum-20260927.json), [fixture](../../bench/public_array_map_inc_sum.bend) |
| Flat `map → filter → sum` is at C/Rust time at one million. | Verified on M3 Max, 36 paired sessions; 188.5 / 199 / 195.5 µs median Bend/C/Rust iterator. | [Raw report](../../bench/public-array-map-filter-sum-rust-integrated-20260927.json) |
| The exact integrated Bend loops vectorize four-wide. | Verified in Clang 17 vectorization remarks for the `Array.walk` traversal line of each generated C file; exact source hashes recorded. | [Integration report](20260927-ARRAY-WALK-INTEGRATION.md), benchmark reports |
| These flat pipelines allocate no per-item stage collection. | Supported by generated code and constant timed native heap-allocation counts (9 and 10 at one million), not a zero-allocation claim. | [Integration report](20260927-ARRAY-WALK-INTEGRATION.md) |
| `Array.walk` preserves stop order and ordinary Array semantics. | Verified by 64 library tests, 1470 fork gate tests, one Metal fixture, layout and malformed-span fixtures. A formal compiler correctness proof remains open. | [Integration report](20260927-ARRAY-WALK-INTEGRATION.md), [tests](../../tests/array_walk.bend) |
| C/Rust Bullet Cathedral ports match Bend. | Verified for every one of 120 512×512 frames: pixel checksum, accepted hits, shield. | [Raw report](../../bench/bullet-cathedral-cross-language-20260927.json), [cross-language runner](../../bench/bullet_cathedral_cross_language.py) |
| Bullet Cathedral broad phase covers the 120-frame run. | Exhaustively checked against all 256 drones for every on-screen friendly bullet. A mathematical argument covers the stated scene bounds, with a floating-point trust boundary. | [Oracle](../../bench/bullet_cathedral_oracle.py), [geometry argument](../../proofs/bullet_cathedral_geometry.md) |
| The 512×512 showcase Bend/C/Rust fresh-buffer median times are 405.4/242.7/227.8 ms for 120 frames. | Verified on one M3 Max CPU thread, 21 paired sessions; initial scene setup and cleanup timed, no display. Reuse lanes and allocation counts are also in the report. | [Raw report](../../bench/bullet-cathedral-cross-language-20260927.json) |
| The 2K Bend window presented 38–40 FPS after startup. | Historical one-thread native-window observation; not the 512×512 cross-language benchmark. | [2K run report](../../bench/BULLET-CATHEDRAL.md) |
| List map/fold fusion, map composition, and no-stop List agreement have Bend-checked proof terms. | Verified for exact U32 List models and `Control<Empty,U32>` statement. Not an end-to-end proof of Xf, Array lowering, or showcase. | [Proofs](../../proofs/README.md) |
| Existing Bend runtime benches did not show an identified regression. | Verified outputs and local timings for 16 sequential CPU, 16 eight-thread CPU, 16 Metal cases, plus five checker cases. Local host noise and cluster differences remain. | [Regression report](20260927-UPSTREAM-LOCAL-REGRESSION.md) |

Do not promote these broader statements without new evidence: that every
pipeline is allocation-free or SIMD; that the 512×512 showcase is C-fast;
that the whole public API or showcase has a machine-checked end-to-end proof;
that the 2K live result uses eight CPU threads; or that local paired results
substitute for the upstream M4 cluster gate.
