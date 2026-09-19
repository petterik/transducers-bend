# Stateful small-list crossovers

This follow-up measures `map inc` with the stateful cases that showed up in the
range work: `filter`, `take`, and `filter + take`. Every variant is Bend source
compiled to native C by the same sibling compiler. `direct_bend` is a
user-authored fused Bend traversal; `base_list` uses core `Base.List` operations
where their type kinds permit it. There is no manually written C baseline.

The mixed predicate is the same three-round U32 mixing function used by the
earlier control-flow measurements, with threshold `2^31 - 1`. Stable runs use
4,194,304 targeted input elements per timed sample, seven retained samples after
one warmup, and forward/reverse variant order. Lists are rebuilt inside every
timed call and every checksum is independently verified.

`filter` alone stays at direct-Bend parity across the sweep. `take(32)` alone
also stays at parity; one isolated size-4 timing is an outlier near the timer's
resolution. The core-list pipeline is slower throughout because it materializes
the mapped/filtered list before reducing it.

The combined mixed `filter + take` path is different. With a take budget of
1,048,576 (so the tested lists are fully traversed), the transducer is about
1.3–1.6× slower than direct Bend through the smallest sizes, falls to 1.07× at
96 elements, and reaches the 5% parity band around 192–256 elements. The
medians are equal at 512. With an actual early-stop budget of 32, the 5% band
starts around 96–128 elements and the medians are equal at 1,024. In both
experiments the transducer remains faster than the materialized core-list
pipeline at every non-empty size.

This isolates the remaining small-list crossover to the combined carried state
of `filter` and `take`; neither stateful layer alone reproduces the sustained
gap in these workloads. It does not establish a universal threshold for other
predicates, callbacks, or backends.

The filter cases use the benchmark's equivalent recursive `mapped_data` before
core `List.filter`, because the current prelude's `List.map` result kind does not
type-check as the input to `List.filter`. The take-only case uses actual
`List.map`, `List.take`, and `List.foldl`.

Stable reports:

- [filter only](stateful-filter-mixed-stable.json)
- [take only](stateful-take-stable.json)
- [filter + take, full traversal](stateful-filter-take-mixed-stable.json)
- [filter + take, early stop](stateful-filter-take-mixed-early-stable.json)

The runner is [stateful_crossover.py](stateful_crossover.py). Reproduce the
stateful crossover with:

```sh
python3 bench/stateful_crossover.py \
  --cases filter_take --samples 7 --target-calls 4194304 \
  --threshold 2147483647 --take 1048576 --work-rounds 3 \
  --sizes 0-16,24,32,48,64,96,128,192,256,512,1024 \
  --output /tmp/stateful-filter-take.json

python3 bench/stateful_crossover.py \
  --cases filter_take --samples 7 --target-calls 4194304 \
  --threshold 2147483647 --take 32 --work-rounds 3 \
  --sizes 0-16,24,32,48,64,96,128,192,256,512,1024 \
  --output /tmp/stateful-filter-take-early.json
```
