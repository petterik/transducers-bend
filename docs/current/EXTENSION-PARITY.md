---
created_at: 2026-09-20T22:18:25+02:00
status: current
---

# Extension/direct parity checkpoint

This is the first retained performance check for the public `keep` and
`partition_all` extensions. It uses the isolated fact compiler with compiler
hash `5f2548b7ccec683ca64dda954f011e8f9fcf09ba72199f9cfba3d81f0d33d1ed` and
library hash `98285606bf5c33bf17e9e703a164060b09666dac755ef9c1562781c3e4b4db14`.
The source is a sequential `List<U32>` of 200,000 elements. Native runs use one
CPU thread with the GPU disabled; the generated JS lane is also run for every
case and must produce the same values. Each row has one warmup and five retained
samples, with 64 reductions per sample. Timings include list construction,
reduction, and cleanup.

| Case | Transducer median (ms) | Direct median (ms) | Ratio | 1.05 target |
| --- | ---: | ---: | ---: | --- |
| `keep`, full budget | 108 | 66 | 1.636 | open |
| `keep`, take 32 | 273 | 272 | 1.004 | passes |
| `partition_all`, width 1 | 323 | 107 | 3.019 | open |
| `partition_all`, width 8 | 377 | 202 | 1.866 | open |
| `partition_all`, width 8, take 2 groups | 269 | 273 | 0.985 | passes |

Every row agrees between native and JS and returns the independent expected
value. The bounded rows are close to the direct loop, which supports the
claim that stopping and early completion are fused through the ordinary
protocol. Full traversal is still materially slower. The result is useful
negative evidence: static composition and the first local constructor rewrite
do not yet remove all of the control, buffering, and completion costs of a
generic `keep`/`partition_all` pipeline.

The direct partition comparator owns a pending list and counts completed groups,
but it does not reverse a group before counting because the count consumer does
not inspect its elements. This makes the full partition rows a lower-bound
diagnostic for the current generic pipeline, rather than evidence that every
consumer should match this exact ratio. A list-producing downstream consumer
must retain its group storage and order. The report therefore does not claim
universal parity or allocation freedom.

The retained machine-readable report is
[`extension-parity-results.json`](../../bench/extension-parity-results.json),
and the independent harness is
[`extension_parity.py`](../../bench/extension_parity.py). Reproduce it with:

```sh
python3 bench/extension_parity.py \
  --bend-main /tmp/transduce-facts-current/main.ts \
  --samples 5 --repeats 64 \
  --output bench/extension-parity-results.json
```

This closes measurement workset 5 only as an evidence checkpoint. The three
open full-traversal rows remain performance work, and the provisional 1.05
target is not relaxed after seeing the result. The next optimization should
target a general elimination of unnecessary option/control or group-boundary
work, then rerun this matrix with the same source and stopping contracts.
