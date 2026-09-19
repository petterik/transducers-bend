# Control-flow confidence review

The 2026-09-19 investigation did **not** establish a beneficial control-flow rewrite. The library and compiler remain unchanged. The benchmark now accepts `--cases` and `--threshold` so filter selectivity can be checked explicitly. [Raw samples](control-results.json) retain the baseline, rejected variants, and final selective-filter run.

## Findings

The original cheap full-range gap reproduced at 48.5 ms library versus 33 ms direct. Native C flattens control/state wrappers into scalar arguments. Inspection of the optimized ARM64 repeat loop found no per-element allocation or helper calls on its normal path. JS still constructs control/state objects; native observations must not be generalized to JS or other pipelines.

The optimized native library loop retains stop/filter branches and a checked Nat reconstruction. The direct full-range loop simplifies the predicate after the initial rejected value. Thus the timing difference is not an isolated measurement of protocol dispatch cost. Removing checks from scratch generated C made performance worse; instruction selection and control-flow optimization matter, not just source branch counts.

Changing the filter threshold from 1 to 1,048,576, with both implementations and the independent oracle updated, gives **36 ms library versus 36.5 ms direct** in the final run. Both still visit two million source elements per transduction, but fewer reach take/sum. This is evidence of workload dependence, not a universal parity or speedup claim. The predicate is still compile-time-known; truly runtime configuration and irregular selectivity remain unmeasured.

```sh
python3 bench/range.py --cases cheap_full --threshold 1048576
```

Use the full-consumption case for this threshold: a highly selective filter can make the million-repeat early-stop cases prohibitively slow. The default benchmark remains unchanged at threshold 1.

## Rejected changes

All timings are whole-batch medians with the methodology in [RANGE.md](RANGE.md). The baseline and downstream-first experiment retained six samples per case; the zero-test and selective-filter experiments retained fourteen. Each process discards a warmup, and the second round reverses variant order. All batch checksums matched the independent oracle.

| Variant | Cheap full | Cheap early | Decision |
| --- | ---: | ---: | --- |
| Original library | 48.5 ms | 24 ms | Retained |
| Explicit zero test in take_control | 64 ms | 32 ms | Reverted: regression |
| Downstream-first take_control | 49 ms | 25.5 ms | Reverted: no gain |

The explicit-zero-test experiment replaced the match on `n` with `Nat.is_eq(n, 0n)` and a helper taking `(empty, n, c)`. For an empty count it returned `Stop{Taking{n, c}}`; otherwise it matched downstream control and preserved the count and inner tag. This avoided reconstructing `1n+p` in that helper but did not improve native optimization.

The downstream-first experiment kept the public helper's argument order and forwarded to a helper taking `(c, n)`. Its three cases were `Stop{s}, n`, `Continue{s}, 0n`, and `Continue{s}, 1n+p`, preserving the original returned states. It retained checked reconstruction in the positive continuing case.

Both compiled variants passed all twelve JS/native test files, including bounded laws, completion/flush fixtures, affine ownership, generated-description elimination, and exact source/mapper/lifecycle instrumentation. Neither changed take's distinction between upstream truncation and downstream stopping. Correctness tests alone did not justify keeping either change.

An earlier attempt to match range control before the remaining budget was rejected by Bend's checking rules: moving control before the budget in the function parameters also prevents the structurally decreasing recursive call, since the changed control argument precedes the shrinking budget. No unsafe bypass or compiler edit was attempted.

## Confidence and next decision

The evidence supports retaining the current implementation, not a universal diagnosis or proof. Preserve both inner and outer stopping information, checked arithmetic, affine state, and exactly-once completion in any future optimization. Do not claim a fixed abstraction penalty from a single predicate/loop shape.

Before further representation changes, expand measurement to runtime thresholds and irregular predicates, then identify a specific missed compiler optimization with a small reproducer. Full compiler gates, mechanized proofs, GPU/CUDA coverage, and performance on other machines remain separate gaps. No new performance guarantee is made.
