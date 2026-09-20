---
created_at: 2026-09-20T22:18:25+02:00
status: current
---

# Extension/direct parity checkpoint

This checkpoint measures the public `keep` and `partition_all` extensions
against independent direct loops. It uses the contained facts compiler with
compiler hash
`a393e4f315a2c7a3286b241cee8c11a2fb346b5cdf530e3904c601953a1215d8` and
library hash
`98285606bf5c33bf17e9e703a164060b09666dac755ef9c1562781c3e4b4db14`.
The source is a sequential `List<U32>` of 200,000 elements. Native runs use
one CPU thread with the GPU disabled; the generated JS lane is also run for
every case and must produce the independent expected value. Timings include
source construction, reduction, and cleanup.

The retained protocol has ten independent sessions and five paired process
launches per session. The first lane alternates on every pair, and repetition
counts are calibrated per case until both lanes take at least 100 ms. The
calibration runs are discarded. The retained estimate is the geometric mean
of the ten session ratios; the upper bound is a 1,000-resample bootstrap 95%
bound. A row passes only when the full ten-by-five design is present and its
upper bound is at most 1.05.

| Case | Consumer | Ratio (transducers/direct) | Bootstrap upper bound | Status |
| --- | --- | ---: | ---: | --- |
| `keep_full` | same-type sum | 0.928 | 0.935 | passes |
| `keep_take_32` | same-type sum, bounded | 1.010 | 1.019 | passes |
| `keep_type_change` | `U32 -> Maybe<Nat>`, full | 6.116 | 6.137 | fails |
| `keep_type_change_take_32` | type-changing, bounded | 1.006 | 1.013 | passes |
| `partition_width_1` | count-only diagnostic | 4.939 | 4.980 | diagnostic fails |
| `partition_width_8` | count-only diagnostic | 1.423 | 1.433 | diagnostic fails |
| `partition_take_2` | count-only, bounded diagnostic | 1.006 | 1.010 | diagnostic passes |
| `partition_sum_width_1` | equivalent group sum | 1.561 | 1.573 | fails |
| `partition_sum_width_2` | equivalent group sum | 1.462 | 1.469 | fails |
| `partition_sum_width_8` | equivalent group sum | 1.460 | 1.466 | fails |
| `partition_sum_take_2` | equivalent group sum, bounded | 1.002 | 1.010 | passes |

The full type-changing `keep` row is a real regression: the generic
transducer path is much slower when it must construct and consume a changing
`Maybe<Nat>` result for the whole source. Its bounded form passes because the
take stage stops after a small number of accepted values. This is a useful
target for a later optimization; it is not evidence of universal `keep`
parity.

The `partition_sum_*` rows are the partition rows that support a direct parity
claim: both lanes inspect every element in every emitted group. They show that
full traversal still pays a substantial generic group-boundary cost, while a
bounded consumer is close to the direct loop. The older `partition_width_*`
rows retain the count-only comparison for continuity. Their direct loop does
not inspect group values, so those rows are lower-bound diagnostics rather than
claims about every downstream consumer or about allocation-free partitioning.

Every native result agrees with the independent expected value, and every JS
run agrees as well. The machine-readable report retains the raw paired
samples, calibration batches, source hashes, and eligibility decision at
[`bench/extension-parity-results.json`](../../bench/extension-parity-results.json).
The harness is
[`bench/extension_parity.py`](../../bench/extension_parity.py). Reproduce this
checkpoint with:

```sh
python3 bench/extension_parity.py \
  --bend-main /tmp/transduce-facts-contained/main.ts \
  --sessions 10 --pairs 5 --min-batch-ms 100 --bootstrap 1000 \
  --output bench/extension-parity-results.json
```

This closes the measurement workset as an evidence checkpoint. The open rows
remain performance work; the 1.05 target is kept unchanged. The next useful
optimization should reduce unnecessary option/control or group-boundary work,
then rerun this same matrix and stopping contract.
