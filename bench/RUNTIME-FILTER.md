# Runtime thresholds and irregular filtering

Follow-up to [the control-flow review](CONTROL.md), measured on the same M3 Max and sibling compiler. No library or compiler code changed. [Raw reports](runtime-filter-results.json) preserve every retained sample, checksums, compiler hash, and generated benchmark-source hashes.

## Method

`--runtime-threshold` reads a decimal U32 from `IO.args` before timing, passes it through the benchmark and handwritten driver, and supplies it as the library filter configuration. Low and selective full-range runs have identical generated-source SHA-256 hashes for each implementation, confirming the threshold does not change their compiled source.

`--predicate mixed` applies three rounds of the existing U32 mixing function to the mapped value before comparing it with the threshold. Each round is `((x * 1664525) XOR (x >> 13)) + 1013904223`, with U32 wrapping. Both variants use the same predicate. The consumer sums the original mapped value, not the mixed comparison key. This is deterministic irregular filtering, not a claim of random or representative real-world input.

The independent Python oracle computes the checksum and expected input/accepted counts. These counts describe the reference execution; they are not measured native instruction counters. Full runs visit 64 million elements per sample (32 ranges of two million); early runs perform one million transductions taking 32 accepted values each. Different thresholds can therefore change how many inputs an early run visits.

Each case uses seven samples after a discarded warmup, then a second process round with reversed implementation order: fourteen retained samples per implementation. Timing excludes process startup and argument parsing. CPU threads=1, GPU off. Final recorded cases ran sequentially; overlapping exploratory runs were excluded and rerun. Default-case smoke tests also passed after changing the handwritten driver to accept configuration.

```sh
python3 bench/range.py --runtime-threshold --cases cheap_full cheap_early
python3 bench/range.py --runtime-threshold --threshold 1048576 --cases cheap_full
python3 bench/range.py --runtime-threshold --predicate mixed --threshold 2147483647 --cases cheap_full cheap_early
```

## Results

Whole-batch medians, milliseconds:

| Predicate / runtime threshold | Case | Library | Handwritten |
| --- | --- | ---: | ---: |
| Above / 1 | Full | 50 | 34 |
| Above / 1 | Take 32 | 25 | 18 |
| Above / 1,048,576 | Full | 38 | 34 |
| Three-round mixed / 2,147,483,647 | Full | 330.5 | 95.5 |
| Three-round mixed / 2,147,483,647 | Take 32 | 139 | 103 |

The selective runtime case retains a modest gap; the earlier near-parity observation concerned a literal threshold. The mixed full-range case exposes a much larger gap. The full mixed case accepts 32,001,824 of 64,000,000 inputs per sample. Its early case visits 64,126,141 inputs to obtain 32,000,000 accepted values. Do not compare their timings as equal-work measurements.

## Native-code finding

Inspecting the emitted C compiled with `clang -std=c11 -O3 -S` shows a specific difference in the mixed full-range repeat loop:

```asm
; Library: branch on predicate result
cmp   w15, w27
b.ls  rejected
; accepted path updates accumulator and take state

; Handwritten: select updates without branching on the predicate
cmp   w15, w27
cset  w15, hi
csinc w14, wzr, w14, ls
add   w11, w14, w11
sub   x13, x13, x15
```

Both loops inline the three mixing rounds. The library retains extra control branches; the direct loop uses conditional scalar updates for acceptance. Both retain a numeric check in this case. No allocation or helper call appears on either loop's normal per-element path. An additional inspection run reproduced approximately 331 versus 95.5 ms.

This supports investigating missed branch-to-selection optimization for scalar reducer state. It does **not** establish branch-misprediction counts or attribute the entire timing difference to one instruction: no hardware counters or controlled assembly intervention were collected.

## Next target and safety boundary

Completed follow-up: [the standalone reproducer](CONTROL-REPRO.md) removes the library and nested tags, reproduces the slowdown with one control tag, and recovers near-direct performance by explicitly exposing the positive-count invariant at loop entry.

Reduce this case to a small compiler optimization reproducer before changing the reducer API. Investigate why equivalent scalar updates with nested control tags inhibit conditional selection. Do not eagerly execute arbitrary downstream callbacks on rejected inputs: they can stop, use affine values, or fail checked arithmetic. A valid optimization must preserve evaluation behavior and completion, not merely match this sum benchmark. No general branchless filter, performance guarantee, or new compiler pass is implemented here.
