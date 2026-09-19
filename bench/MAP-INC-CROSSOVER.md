# `map inc` crossover

## Result

The simple `map inc` case does not reproduce the short-list regression from the
stateful loop experiments.

For a scalar reduction, the current transducer pipeline
`over_list(map inc sum)` is at handwritten parity from the smallest input. In the
stable sweep, both were 47 ms at one element and 22 ms at 1,024 elements, with
4,194,304 input elements processed per timed sample. Across sizes 0–16, 24, 32,
48, 64, 96, 128, 192, 256, 512 and 1,024, the transducer medians stayed within
about ±3.3% of the fused handwritten reduction. That difference is at the limit
of this millisecond timer and local machine noise.

For a list result, `over_list(map inc into_list)` was faster than the naïve
recursive handwritten map at every tested size. At one element the medians were
46 ms transducer, 125.5 ms handwritten, and 126 ms for `Base.List.map`; at 1,024
they were 30.5, 41, and 42 ms. The accumulator-and-reverse handwritten map was
46–47 ms at one element and 30 ms at 1,024, matching the transducer path. The
fair handwritten shape therefore catches up immediately; the naïve recursive
shape is the outlier.

The list sweep includes dynamic list construction in every timed call and uses a
position-weighted checksum, so an incorrectly reversed output cannot pass the
check. The scalar sweep uses the ordinary U32 sum. Both use one warmup, seven
samples, alternating variant order, CPU-only execution, and an independent Python
oracle. The absolute milliseconds are local measurements; the paired ratios are
the useful result.

## Why the transducer can beat the handwritten version

The generated C explains the surprising result. The naïve handwritten map and
`Base.List.map` are emitted as worklist functions with per-element continuations
(`FID_DIRECT_MAP` and `FID_LIST_MAP_0`). The transducer's closed reducer chain is
lowered into inline `spin_*` loops. A handwritten accumulator-and-reverse map is
also lowered into the same loop-shaped code, which is why it reaches transducer
parity. For the scalar case, the transducer and the fused handwritten reducer
both emit an inline map-plus-add loop.

So the large-list speedup is a code-shape effect, not a mysterious transducer
advantage: the library composition exposes a loop to the compiler, while the
first handwritten comparator exposes a recursive list builder. This also means
that comparing only against that naïve handwritten function would exaggerate the
transducer's advantage.

## What this says about the broader problem

Simple mapping is already in the desired regime, including one-element inputs.
The short-loop regressions found earlier arise when the pipeline carries control
and state through `filter`/`take` and the specialized source loop chooses between
fast and generic entry paths. A source-only zero/one gate is therefore not the
general fix for this map case.

The next useful small-list benchmark should add one stateful feature at a time
(`filter`, `take`, then both) while retaining the accumulator-shaped handwritten
comparison. That will show exactly which control state causes the crossover and
whether the compiler can lower that state into the same loop form.

## Reproduction

```sh
python3 bench/map_inc_crossover.py \
  --mode sum --target-calls 4194304 --samples 7 \
  --sizes 0-16,24,32,48,64,96,128,192,256,512,1024 \
  --output /tmp/map-inc-sum.json

python3 bench/map_inc_crossover.py \
  --mode list --list-accumulator --target-calls 4194304 --samples 7 \
  --sizes 0-16,24,32,48,64,96,128,192,256,512,1024 \
  --output /tmp/map-inc-list.json
```

Raw results: [scalar sweep](map-inc-sum-crossover-stable.json), [list sweep](map-inc-list-crossover-stable.json), and [fair accumulator comparison](map-inc-list-crossover-accumulator.json). The benchmark source is [map_inc_crossover.py](map_inc_crossover.py).
