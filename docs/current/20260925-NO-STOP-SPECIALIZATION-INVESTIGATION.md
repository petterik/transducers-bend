---
created_at: 2026-09-25
status: current
---

# General no-stop specialization investigation

The later [opaque source protocol](20260925-OPAQUE-SOURCE-PROTOCOL.md)
replaces the public `Source` contract described below. It prevents a generic
source from constructing `Stop`, but its `Checked` tag still costs time in
the Array total fold. The benchmarks and candidate options in this document
record the preceding design state.

## Result

There is a real, recoverable cost in the current stopping fold. A total fold
whose step has type `S -> A -> S` runs at handwritten speed on both Bend Array
and an independently defined branching tree. A composed `map`-style step also
stays near handwritten speed. Wrapping the total fold in the existing
`T.Reduction` and calling the existing `T.transduce` does not reintroduce the
cost. The experiment does **not** automatically infer that a current
`Control` pipeline cannot stop; that proof and source selection remain open.

Generated C explains the difference. The stopping tree fold carries a tag and
state in separate registers, tests the tag at both leaf and branch, and passes
it through a continuation frame after the left subtree. The direct and total
folds carry only the state. Array has the same shape. Clang `-O3` did not
remove those checks from the current stopping fold. The total fold's composed
step remains an inlineable C helper; the direct step is emitted in its loop.
The public `T.transduce` total wrapper jumps directly to the total fold, with
no runtime `Reduction` record in this probe.

| Source, 1,048,576 leaves | Direct median | Current `Control` | Total | Composed total | Public `transduce` total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Array | 7,920.5 µs | 8,641.5 µs | 7,855.5 µs | 7,864.5 µs | 7,831.5 µs |
| Branch tree | 2,349.5 µs | 2,674 µs | 2,354 µs | 2,341 µs | 2,338 µs |

In 40 paired sessions, `Control`/direct was 1.088 for Array and 1.136 for
tree; public total/direct was 0.993 and 0.995. At 262,144 leaves the same
comparisons were 1.089 and 1.128, then 0.994 and 1.000. Treat ratios near
1.0 as parity rather than a claim that total is faster. Timed heap allocation
calls were equal across all five paths for each source. Array's structural
`blk_half` traversal allocates in every path; this experiment removes control
traffic, not Array traversal work.

The [correctness probe](../../experiments/affine_xf/probe_no_stop_total.py)
checks CLI value mode, JS, and native on both sources. A step returning
`Stop` is rejected by the total step type. The raw paired results are at
[depth 18](../../experiments/affine_xf/no-stop-total-depth18-results.json)
and [depth 20](../../experiments/affine_xf/no-stop-total-depth20-results.json).
The [Bend fixture](../../experiments/affine_xf/no_stop_total_probe.bend)
contains the direct, stopping, total, composed, and public paths.

## What a general rule must prove

For a pipeline beginning with `Continue(s)`, the reducer's start, step, and
every nested source drive must preserve `Continue`; completion must still run
once with the same state. Proving only that the *leaf reducer*
returns `Continue` is insufficient under the current types: an adapter can
invent `Stop`, while a stage such as `take` can stop before or after a step.
The rule must keep
evaluation order and consume owned values exactly once. It must preserve the
original stopping path for initial `Stop`, `take(0)`, dynamic or unknown
callbacks, sources without a totality guarantee, and failed analysis.

`map`, `filter`, `remove`, and `keep` can preserve a total downstream step;
`take` generally cannot. `mapcat` can preserve totality only if both its
downstream step and its nested fragment drive qualify. Partitioning may be
total but can still allocate its output chunks. These are semantic
properties of the stage and source, not names to match in compiler code.

## Options

| Approach | Benefit | Main cost and risk |
| --- | --- | --- |
| **Typed totality path in the library/source protocol** | Near-direct speed already demonstrated; `transduce` stays the public entry point; a `S -> A -> S` step cannot stop by construction | Sources need an optional total drive as well as the current stopping drive, or fall back to the current path. Selecting the fast path and proving both drives agree adds library/API work. |
| **General compiler constructor-invariant specialization** | Could keep one source fold and optimize any suitable ADT, not only transducers | Needs interprocedural fixed-point analysis and cloning of recursive folds plus continuation frames after checked template instantiation. It must transform state representation while preserving affine disposal. This is substantially more invasive than the current callback rewrite and could add compile-time cost to ordinary programs. |
| **Rely on Clang for the existing `Control` fold** | No new API or compiler code | The generated state-machine C and repeated measurements show that Clang is not eliminating the tag checks here. |

**Recommendation:** prototype the typed path next, as an optional capability
of the existing source protocol, while retaining the stopping fold as the
universal fallback. A source still implements one protocol; common sources
can provide a second, total drive and an agreement proof within it. Totality
should be represented in reducer/source types and propagate through stage
composition, so adding a
new total stage needs one implementation, not a compiler pattern. `T.transduce`
can keep its current call shape because its static `Reduction` can select the
drive. Measure API verbosity, code size, compile time, and agreement of the
two drives before adopting this publicly.

If requiring two source drives proves too costly, the compiler alternative
should be a separate bounded experiment. It should use constructor invariants
on checked, specialized terms, never recognize `Control`, `sum`, Array, or
transducer names, and fall back on any unproved call or ownership path. The
existing static specialization already adds measurable compile time to
ordinary code, so another whole-body analysis should not be added without
profiling and a strict compile-time budget.

A concrete compiler prototype would use an abstract domain such as
`known Continue / known Stop / unknown` for a constructor-valued parameter and
result. It would analyze all arms of source-data matches, follow only checked
closed callbacks, and solve recursive call groups to a fixed point. A dynamic
call, unsafe or foreign body, ambiguous template instance, or mixed result
becomes `unknown`. Only after proving `Continue -> Continue` could it clone
the recursive fold and its continuation frames with the state field in place
of the tagged value, then rewrap `Continue` at the public boundary. The
original fold remains callable for every other path. This transformation must
inspect checked code without evaluating runtime callbacks during analysis.

## Proof boundary clarified

Normal source exhaustion returns `Continue`, not `Stop`. A well-behaved source
only propagates an incoming `Stop` or one returned by the downstream step.
This matters for nested sources: when `take` stops inside one `mapcat`
fragment, that `Stop` must reach the outer source so it does not enter the
next fragment. The current `Source` type permits an adapter to invent or
discard `Stop`, however; it does not itself encode this behavioral contract.

For a typed fast path, two claims are distinct:

1. A `TotalReducer` step has type `S -> A -> S`, so it cannot return `Stop`.
   Composition preserves this property only for stages whose start and step
   are total. A possible initial `Stop` must be handled before entering the
   fast fold.
2. The total source drive agrees with the existing stopping drive when every
   callback returns `Continue`. For every owned input `x`, state `s`, and
   closed total step `f`, the desired law is
   `drive_stop(x, Continue(s), (s,a) => Continue(f(s,a))) ==
   Continue(drive_total(x,s,f))`. This entails no spontaneous `Stop` on that
   path and the same final state and encounter order for arbitrary `f`.

The first claim follows from the step type. The second does not: two
independent source implementations could traverse in different orders or
drop elements while both satisfy their function types. We checked a Bend
inductive [List proof](../../experiments/affine_xf/no_stop_list_law_probe.bend)
over an opaque template step; it verifies the law for that small source.
This does not establish that the same proof is convenient for affine
branching sources or Bend Array. A direct branching proof needs to carry the
left subtree's computed state into the right subtree without reusing the
affine left value. A result-plus-proof witness is a plausible approach, but
remains untested.

The safest incremental protocol is therefore **certified totality**: use a
total drive only when both the reducer's total type and a checked source
agreement proof are available; otherwise keep the stopping drive. A single
canonical source traversal representation that generates both drives would
also establish agreement by construction, but its performance on Array and
branching structures is unmeasured. A compiler clone of the same checked
source body could avoid per-source proofs, at the substantially higher
compiler complexity described above. Merely declaring an optional fast drive
and testing it is a useful engineering contract, not a proof of equivalence.

This investigation changes no production compiler or transducer-library code.
