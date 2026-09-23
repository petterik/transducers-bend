---
created_at: 2026-09-20T20:05:38+02:00
status: historical
---

# Final validation checkpoint

> Historical checkpoint: this report used the fork's `origin/main` at
> `15ae0c86`, plus scoped-fact experiments. The active target is now only
> `bendlang/main`; these compiler and performance results do not establish its
> fusion or performance status. See the current main-only baseline and plan.

The follow-up review found two concrete defects in the earlier checkpoint: a
caller-specific fact could cross a shared native-helper boundary, and the
independent direct `keep` oracle mishandled its first budget value. Those
defects are now repaired. The lifecycle fixture, structured compiler
call-site report, and calibrated extension matrix are also retained below.

The candidate is now built from upstream Bend `origin/main` commit
`15ae0c86f3193b8f645b4bedbc438655b648d0da`; the bounded static-callback pass
is reapplied by `bench/compiler/prepare_static.py`. That candidate's compiler
source hash is unchanged from the retained measurements. The semantic suite
uses the contained facts compiler with compiler SHA
`a393e4f315a2c7a3286b241cee8c11a2fb346b5cdf530e3904c601953a1215d8`. The
structured representation probe uses its diagnostics-enabled compiler with
SHA `4560590cc170ea02f13a0a509ed98fd05e7b320b6848e649f58baf1fce18d35d`.
The extension report uses library hash
`98285606bf5c33bf17e9e703a164060b09666dac755ef9c1562781c3e4b4db14`.

## Current checks

| Check | Result |
| --- | --- |
| `python3 bench/compiler/prepare_static.py --output-dir …` self-check | Smoke compile, API surface has no runtime `Reducer` records, and five static-callback regression fixtures pass on JS/native |
| `python3 tests/run.py` | 22/22 JS/native files; prepares its candidate from local `origin/main` by default |
| `python3 tests/run.py --bend-main /tmp/transduce-facts-contained/main.ts` | 22/22 JS/native files, including named settings, laws, API surface, lifecycle, partition lifecycle, and source contracts, on the retained facts candidate |
| `python3 bench/run.py --bend-main <candidate>` (7 samples) | Latest-main candidate stays near the sibling patch baseline; medians below |
| `static_composition_probe.py` | Native/JS `[9, 9, 7, 7, 3, 3]`; zero reducer/reduction records and closure-dispatch transfers |
| `representation_probe.py --diagnostics` | Scalar, buffered, and dynamic-control outputs match on native/JS; structured call-site attribution has no unknown records |
| `test_scoped_constructor_fact.py` | Output `4\n1`; 2 exact selections, 2 dynamic rejections, conservative refusals retained |
| `local_representation_probe.py` | Output `6`; exact tagged-arm fact removes 85 native C bytes with equal JS/native output |
| `extension_parity.py` | Eleven calibrated rows with independent native/JS oracles; status recorded per row below |
| `configured_pipeline.bend` | Named settings wrapper works with count, ordered collection, non-`Unit` consumer configuration, List/range/tree sources, initial Stop, partial flush, and fresh repeated runs |

The current suite is a semantic and code-shape checkpoint for the facts
compiler. It does not claim that the facts compiler also contains the
separate historical guarded-loop/tree pass.

The latest-main refresh smoke used seven post-warmup samples per case, with
process startup, source construction, reduction, and cleanup included. It ran
against both the prepared facts candidate and the sibling `b1f9c936` checkout;
the latter is one commit ahead of the same upstream `main`. Their `comp.ts`
hashes were `a393e4f315a2c7a3286b241cee8c11a2fb346b5cdf530e3904c601953a1215d8`
and `96c997a7d4700a7aaa7bb5a7f27ea810394168cb50fd7f6d267d45156f2e3df3`,
respectively. In every case, the library, materialized, and direct programs
had identical C/JS byte counts under both compilers. Median milliseconds were:

| Case | Prepared transducer / direct | Sibling-patch transducer / direct |
| --- | ---: | ---: |
| `cheap_full` | 27.14 / 28.28 | 27.25 / 26.17 |
| `cheap_early` | 35.91 / 36.54 | 36.34 / 35.57 |
| `expensive_early` | 20.37 / 19.30 | 19.73 / 19.45 |

These short samples show no material shift between candidate compiler builds;
the last row has a small timing-level reversal and should be read as a smoke
check, not as a replacement for the calibrated extension/direct matrix below.
Recreate the compiler and run both sides with:

```sh
python3 bench/compiler/prepare_static.py --facts \
  --output-dir /tmp/transduce-facts-contained
python3 bench/run.py --bend-main /tmp/transduce-facts-contained/main.ts
python3 bench/run.py --bend-main ../bend/bend2/main.ts
```

## Measured representation and cost boundaries

The current scalar probe emits 91,720 bytes of C and 16,652 bytes of JS, with
13 `heap_alloc` and 9 `term_pak` occurrences. The buffered probe emits
246,106 bytes of C and 71,424 bytes of JS, with 66 `heap_alloc`, 77
`term_pak`, and 5 closure-dispatch transfers. The dynamic-control negative
control emits 119,407 bytes of C and 21,057 bytes of JS, with 2 reducer
records and 11 closure-dispatch transfers. These are code-shape counts, not
allocation or peak-heap measurements. Partition buffers are required state and
remain an explicit cost.

The representation harness asks the isolated compiler for structured call-site
records. Each record carries caller, target, segment, flatness, and site kind;
the report also carries compiler, library, and harness hashes. The scalar case
has 200 known records and no dynamic closure targets. The buffered case has
1,306 known records and 10 `Clo.apply` sites. The dynamic-control case has 304
known records and 26 `Clo.apply` sites. These are compiler-emitted site
counts, not execution frequencies. Unknown records are reported as
inconclusive; none appeared in this run. Whole-file C counts remain
supplementary diagnostics.

## Extension/direct parity

[`EXTENSION-PARITY.md`](EXTENSION-PARITY.md) and
[`bench/extension-parity-results.json`](../../bench/extension-parity-results.json)
record ten sessions of five paired process launches per row. Repetition
counts are calibrated to a 100 ms floor, the first lane alternates, and a row
passes only when its bootstrap upper 95% ratio is at most 1.05.

| Row | Ratio upper bound | Status |
| --- | ---: | --- |
| `keep_full` | 0.935 | passes |
| `keep_take_32` | 1.019 | passes |
| `keep_type_change` | 6.137 | open regression |
| `keep_type_change_take_32` | 1.013 | passes |
| `partition_width_1` | 4.980 | open diagnostic |
| `partition_width_8` | 1.433 | open diagnostic |
| `partition_take_2` | 1.010 | diagnostic passes |
| `partition_sum_width_1` | 1.573 | open equivalent-consumer regression |
| `partition_sum_width_2` | 1.469 | open equivalent-consumer regression |
| `partition_sum_width_8` | 1.466 | open equivalent-consumer regression |
| `partition_sum_take_2` | 1.010 | passes |

All native and JS outputs agree with their independent expected values. The
full type-changing `keep` row and the full equivalent-consumer partition rows
remain real performance gaps. Count-only partition rows are lower-bound
diagnostics because their direct loop does not inspect group values. The target
was not relaxed after measuring any of these rows.

## Historical compiler probes

The source-shape, automatic-loop, Array, and tree-entry artifacts under
`bench/compiler/`, `bench/array-parity-results.json`, and `review/` were made
by earlier isolated candidates with different compiler hashes. They remain
useful evidence for the guarded-loop investigation, but are not results from
the current facts compiler. In particular, the retained tree-entry reproducer
contains a native/JS mismatch in its historical report; tree specialization is
still refused and must not be described as promoted.

## Promotion status

The current deliverable is review-ready host-CPU evidence for the library,
scoped facts, local representation rewrite, lifecycle behavior, named-settings
feasibility, and extension matrix. The named wrapper is a concrete application
pattern, not yet a derived library abstraction: its generated JS still
materializes reducer records, so it carries no performance or allocation
claim. Tree specialization, short-loop profitability, GPU execution, a
general configuration builder, and full upstream project gates remain
outstanding. No all-source, all-backend, or GPU performance claim follows from
these List measurements.
