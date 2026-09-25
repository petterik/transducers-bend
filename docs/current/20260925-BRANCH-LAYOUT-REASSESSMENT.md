---
created_at: 2026-09-25T21:43:00+02:00
status: validated-locally
---

# Branch fold performance reassessment

The first public `Branch` benchmark measured a native `map(inc)` + sum fold about 9–15% slower than a handwritten fold. Both produced the same result; an instrumented comparison found the same timed heap-allocation count. That was a real result for that compiled program, but it did not isolate the public transducer API from generated-code layout.

We then ran the public API and the earlier protocol prototype on the **same owned `Tree.Branch` type**, with the same handwritten direct fold and `inc` mapper in each binary. The two Bend fixtures differ only in which transducer call appears in the first versus second `choose` case. Source construction is outside the microsecond clock; each binary uses one native thread, GPU off, and Clang `-O3`. The [measurement script](../../experiments/affine_xf/measure_branch_api_ablation.py) compiles both fixtures and interleaves 64 runs of each mode at depth 19.

| Fixture | Direct µs | Public µs | Prototype µs | Public / direct | Prototype / direct |
| --- | ---: | ---: | ---: | ---: | ---: |
| Public in first case | 1170.5 | 1178.5 | 1314.0 | 1.007 | 1.123 |
| Prototype in first case | 1173.5 | 1313.5 | 1178.5 | 1.119 | 1.004 |

The overhead follows **case placement**, not the API. Whichever transducer call appears first is at handwritten speed; the call appearing second is about 12% slower. The two generated source loops have the same C operations apart from names, function IDs, and the mapper's inline identifier. Changing Clang loop alignment also moves or reverses the original fixture's gap: at depth 19, default `-O3` measured public/direct at 1.12, `-falign-loops=32` at 0.95, and `-falign-loops=64` at 0.99. Those flags also change handwritten time, so none is a demonstrated overall improvement.

This evidence rules out an inherent 9–15% public-transducer or companion cost in the tested Branch fold. It supports generated native code-layout sensitivity, but does not identify the exact hardware mechanism or guarantee parity for every program. The correct performance statement is that the public fold can match handwritten code on an independent branching source, while individual compiled layouts can vary by roughly ten percent. We should not add a source-named compiler optimization or globally change Clang flags on this evidence. A general compiler change would require assembly or hardware-counter attribution and a broader workload showing an absolute improvement without regressions.
