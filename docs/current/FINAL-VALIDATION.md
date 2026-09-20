---
created_at: 2026-09-20T20:05:38+02:00
status: current
---

# Final validation checkpoint

Date: 2026-09-20. The preceding library/API checkpoint is `66aefd6`; this
validation workset uses the current isolated facts compiler for the semantic and
representation probes has compiler SHA
`5f2548b7ccec683ca64dda954f011f8e9fcf09ba72199f9cfba3d81f0d33d1ed`.
The sibling `../bend` checkout remained unchanged. The extension parity report
uses library hash
`98285606bf5c33bf17e9e703a164060b09666dac755ef9c1562781c3e4b4db14`.

## Current checks

| Check | Result |
| --- | --- |
| `python3 tests/run.py --bend-main /tmp/transduce-facts-current/main.ts` | 20/20 JS/native files, including laws, `api_surface`, `keep_partition`, and source contracts |
| `static_composition_probe.py` | Native/JS `[9, 9, 7, 7, 3, 3]`; zero reducer/reduction records and closure-dispatch transfers |
| `representation_probe.py` | Scalar, buffered, and dynamic-control outputs match on native/JS; expected dispatch remains visible in the negative controls |
| `test_scoped_constructor_fact.py` | Output `4\n1`; 2 exact selections, 2 dynamic rejections, 30 conservative refusals |
| `local_representation_probe.py` | Output `6`; exact tagged-arm fact removes 85 native C bytes with equal JS/native output |
| `extension_parity.py` | Five rows compile and agree on native/JS output; early/bounded rows meet the provisional 1.05 target |

The current suite is a semantic and code-shape checkpoint for the facts
compiler. It does not claim that the facts compiler also contains the separate
historical guarded-loop/tree pass.

## Measured representation and cost boundaries

The current scalar probe emits 91,720 bytes of C and 16,652 bytes of JS, with
13 `heap_alloc` and 9 `term_pak` occurrences. The buffered probe emits 245,306
bytes of C and 71,424 bytes of JS, with 66 `heap_alloc`, 73 `term_pak`, and 5
closure-dispatch transfers. The dynamic-control negative control emits 119,407
bytes of C and 21,057 bytes of JS, with 2 reducer records and 11
closure-dispatch transfers. These are code-shape counts, not allocation or peak
heap measurements. Partition buffers are required state and remain an explicit
cost.

## Extension/direct parity

[`EXTENSION-PARITY.md`](EXTENSION-PARITY.md) and
`bench/extension-parity-results.json` record the calibrated List comparison
(five samples, 64 repeated batches, one warmup, CPU threads 1, GPU off):

| Row | Transducers/direct median | Status |
| --- | ---: | --- |
| `keep_full` | 1.636× | open regression |
| `keep_take_32` | 1.004× | within 1.05 checkpoint |
| `partition_width_1` | 3.019× | open diagnostic |
| `partition_width_8` | 1.866× | open diagnostic |
| `partition_take_2` | 0.985× | within 1.05 checkpoint |

All native and JS outputs agree. The full partition rows use a direct lower
bound whose count consumer does not inspect group values; they are useful
diagnostics, not an allocation-free or universal parity claim. The full
`keep` row remains a real gap and the target was not relaxed after measuring it.

## Historical compiler probes

The source-shape, automatic-loop, Array, and tree-entry artifacts under
`bench/compiler/`, `bench/array-parity-results.json`, and `review/` were made
by earlier isolated candidates with different compiler hashes. They remain
useful evidence for the guarded-loop investigation, but are not results from
the current facts compiler. In particular, the retained tree-entry reproducer
contains a native/JS mismatch in its historical report; tree specialization is
therefore still refused and must not be described as promoted.

## Promotion status

The current deliverable is review-ready host-CPU evidence for the library,
scoped facts, local representation rewrite, and extension matrix. The tuple
configuration API remains the supported public form while the named-settings
experiment is open. Tree specialization, short-loop profitability, GPU
execution, and full upstream project gates remain outstanding. No all-source,
all-backend, or GPU performance claim follows from these List measurements.
