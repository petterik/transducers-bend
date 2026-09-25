# Type-indexed stopping: public integration (2026-09-25)

The public value API is now `xf.bend`, backed by `transduce_core.bend`. The previous low-level `transduce.bend` remains available for its existing tests and examples; `xf_legacy.bend` preserves the prior value API for historical benchmark comparisons. No caller-side spelling changed: `transduce(xf, rf, init, source)` and `into(destination, xf, source)` still use companion selection. `Vec` and `VecMaybe` now implement the indexed source and total destination protocols.

## Contract and confidence boundary

`Reducer<A,R>` has an associated `Permit: Data`. Its `start` and `step` return `Control<Permit,State>`. Total reducers choose `Empty`; a stopping reducer chooses `Unit`. `map`, `filter`, `remove`, `keep`, `mapcat`, and `map_with` inherit the downstream permit. `take` and `partition_all` introduce `Unit`, including initial stop at zero. The source's erased `Drive` parameter is generic in the permit and carries `Checked<Permit,S>` through its own traversal. The source returns only the opaque `S`; it cannot construct a `Stop` for arbitrary `Permit`. `mapcat` passes the same permit into the inner source, so a stop inside a fragment reaches the outer source. `finish` is invoked once at the transduce boundary.

The proof is intentionally narrow. It establishes that `Stop<Empty,S>` and `Halted<Empty,S>` cannot be constructed in live checked code. It does not prove that a custom source visits every element, preserves order, or refrains from returning early. A custom reducer that may stop must declare an inhabitable permit. A user can also create a total reducer with `Empty`, but then its checked `start`/`step` cannot emit Stop.

The companion compiler branch is `codex/transducer-no-stop` in `../bend`, based on `codex/transducer-companions` and `bendlang/main`. Its new rule removes a match arm only when a live constructor field has a datatype with zero constructors. It leaves layout and ABI unchanged and does not recognize transducer or source names. Reachable constructors are cached by instantiated datatype; the `IO.OP` default arm is retained. A separate compiler regression covers generic boundaries, explicit and default arms, recursion, and indexed values in Array. The full local Bend gate passed 1462/1464 cases; the two native graphics differences (`gfx_clicks`, `gfx_window`) match stock upstream on this machine. The library gate passed 45/45 JS/native examples, code-shape and callback-count checks, and source rejection.

## Measured result

On this machine, with one native thread, Bend's native compiler, and source construction outside the measured interval, 24 interleaved samples at Array depth 20 gave these medians in microseconds:

| Pipeline | Median µs | Result |
| --- | ---: | ---: |
| Direct handwritten Array sum of `inc` | 7900.5 | 2097152 |
| Public total `map(inc)` + `sum_rf` | 7900.0 | 2097152 |
| New public `map(inc)` + `take(524288)` + `sum_rf` | 4771.5 | 1048576 |
| Previous value API with the same stopping pipeline | 4949.0 | 1048576 |

These are local medians, not a universal speed claim. The total path is at direct speed in this sample. Stopping did not regress against the previous API. The earlier independent branching-source public prototype measured 145 µs direct versus 148 µs indexed total on the compiler candidate; this integration retains its protocol shape but has not remeasured that exact custom source through `xf.bend`.

The JavaScript lane preserves semantics but remains slower than direct Bend for this Array fold. With 24 interleaved calls at depth 18 in Bun, median in-function times were 17.4 ms direct, 30.7 ms new total, and 31.1 ms previous value API. Thus the indexed change did not introduce the JavaScript gap, and the match-only compiler rule does not close it. For a stopping pipeline over 131072 values, 20 samples measured 35.8 ms new versus 34.7 ms previous, too close and noisy to infer a meaningful difference. These JavaScript measurements use a preload import and `performance.now()` around each pure Bend call, with source construction outside the interval.

Process-inclusive compiler medians from the hardened candidate were 236.4 ms upstream versus 240.1 ms fork for the permit fixture, and 282.6 ms versus 292.3 ms for `mapcat_public`. Bun startup is included. No compiler hot path was identified from these small differences. The only new compiler rule is the conservative match-arm rule, so a larger fixture and a profiler would be needed before claiming a compile-time cost.

## Limits and follow-up

`partition_all` still builds ordered List chunks, and a consumer retaining those chunks must allocate them. List-producing `mapcat` callbacks likewise allocate their fragment. Both are semantic costs, not evidence that the general no-stop optimization failed. The indexed API accepts a raw reducible fragment by an explicit closed `Drive` in `mapcat`; automatic fragment companion inference remains a separate API improvement. Direct list literals still need enough type context, as in the prior value API. CLI value-mode evaluation of an imported custom source still leaves an unrelated unresolved `?AUTO`; generated JS and native code agree on that source.

The branch is ready for review and broader performance checks. The next optimization question is the existing JavaScript adapter gap, which should be investigated independently of the stop-permit proof. Avoid broadening the compiler rewrite to change layouts unless a separate correctness and performance case justifies it.
