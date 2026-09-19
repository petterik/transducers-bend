# Composition and ordinary-list baselines

Run `python3 bench/composition.py --samples 5 --output bench/composition-results.json`.
The runner retains generated Bend/C/native artifacts in the printed temporary directory.
[Raw samples](composition-results.json) include source/compiler hashes and ten samples per variant,
after warmup, in forward and reverse variant order. Checksums are independently calculated in Python.
All cases use 32 reductions of freshly constructed ascending 200,000-element U32 lists,
including construction and cleanup. These are sequential CPU measurements, not parallel/GPU results.

Here, **Handwritten** means a user-authored direct Bend traversal compiled to native C by the
same sibling compiler. **Ordinary list pipeline** means calls to core `Base.List` operations.
The emitted C is compiler output for every variant; this benchmark has no manually written C
baseline.

| Workload | Transducers | Scalar prototype | Direct Bend | Core `Base.List` pipeline |
| --- | ---: | ---: | ---: | ---: |
| map +1, map +2, map +3, sum | 13 ms | single-map +6: 13 ms | 13 ms | 118 ms |
| cheap map/filter/take-all/sum | 10.5 ms | 11 ms | 10 ms | 118 ms |
| mixed filter, take-all | 44 ms | 16 ms | 14 ms | 129 ms |
| mixed filter, take 32 | 40.5 ms | 42.5 ms | 40 ms | 128 ms |

The early-stop list benchmark is dominated by construction and disposal of the unused tail;
do not use it to infer step-level parity. The ordinary pipeline eagerly maps/filters the whole
list before taking 32. Every variant in this comparison uses a literal threshold, because ordinary
List.filter takes a closed template callback. The separate range tests use runtime thresholds.

The three-map ordinary baseline uses actual Base.List.map three times. There is a type mismatch
in the current prelude for the filtering baseline: List.map returns List<&1,U32>, whereas
List.filter requires List<&2,U32>. Filtering cases therefore use `mapped_data`, the same recursive
map definition with a List<&2,U32> return type, followed by actual Base.List.filter/take/foldl.
No extra conversion traversal was inserted, and the prelude was not modified.

## Does +1/+2/+3 become +6?

Yes, for the tested transducer composition with wrapping U32 arithmetic. The fork's main.ts
selects Clang (including a compatible $CC override), and compiles native C with `-std=c11 -O3`.
This run used Apple Clang 17.0.0, not GCC. Bend specialization exposes the mapped operations;
Clang then folds the arithmetic and inlines the scalar calls.

Compiling the retained `three_maps-transducers.c` and `three_maps-single_map.c` with
`clang -std=c11 -O3 -S` produced textually identical `_WL_FID_REPEAT` functions on arm64.
The reduction loop contains:

```asm
add w13, w13, w14  ; accumulator + input
add w13, w13, #6   ; combined three map additions
```

There are no mapper calls or intermediate mapped lists in that loop. Input list construction
and disposal remain. This verifies the concrete example, not an assurance that arbitrary
functions, checked arithmetic or floating-point operations can be reassociated.
`tests/composed_maps.bend` checks empty input, ordinary values, wrapping boundaries and ranges.

## Remaining optimization target

The scalar prototype now selects the next sum/count directly (`Bool.pick`) inside the positive-count
guard, instead of multiplying the value by an acceptance bit and subtracting it from the count.
The original state representation, initializer, completion and driver remain intact. Differential
transition tests include continuing-zero and stopped-inner states.

[Mixed generated-range measurements](scalar-select-mixed-results.json): 108 vs 95 ms full,
114 vs 103 ms early, prototype vs direct Bend. [Simple range measurements](scalar-select-default-results.json)
still show 51.5 vs 35 ms full and 26 vs 19 ms early; expensive early is 11 vs 11 ms.
The simple-case prototype is approximately unchanged from the existing implementation, not at parity.

Thus ordinary list pipelines are already substantially slower in these cases, and pure map composition
already meets direct Bend performance. Mixed-filter conditional updates remain worthwhile, but the
remaining cheap-range control/driver overhead needs separate attention to meet a target near the
direct Bend result. The manually specialized prototype is not an automatic compiler optimization and is not
installed in the public library. Do not ship it as a general solution based on these results alone.

## Candidate-only parity audit (September 19, 2026)

The current fusion work uses the isolated compiler prepared by
`bench/compiler/prepare_guarded.py --loop`; the original sibling compiler is reserved
for the final regression comparison. The runner now accepts `--artifact-dir`, so each
case can be inspected without changing the timed program.

In a five-sample candidate run on the same host, three maps were at parity within the
timer resolution (transducers 14 ms, direct 15 ms). The mixed list case remained the
important gap: transducers 48 ms versus the handwritten direct traversal 15 ms, while
the manually specialized scalar prototype measured 18 ms. The early mixed case was
closer (44 ms, 43.5 ms, and 45.5 ms respectively) but is dominated by owned-tail
cleanup. These are diagnostic samples, not final acceptance evidence.

The retained generated C explains the full mixed gap. The list driver is already one
native loop, and Clang inlines the map/filter/take helpers. The generic transition still
branches through the nested `Control`/`Taking` state for each item; the direct reference
uses a scalar acceptance mask to update the accumulator and remaining count. The
remaining work is therefore a typed transition/state representation or lowering change,
not another source-specific driver and not a claim that the current product signal
probe has fused. The next implementation must preserve all stop origins and completion
states while exposing that scalar transition to the existing lowering.
