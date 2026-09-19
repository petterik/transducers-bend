# Generated-C ablations: a near-handwritten target

This is a **program-specific experiment**, not an installed compiler pass.
`ablate.py` compiles the original public map/filter/take/sum pipeline, then replaces
one generated scalar helper. The source driver, mapper, predicate, initializer,
completion and state layout are unchanged. No assumption about generic Source or
Control is added. Helper recognition is deliberately workload-specific and must
not be copied into a production compiler as a name/signature-based optimization.

## Results

Ten samples per variant after discarded warmups, forward/reverse order, native
single-thread CPU, GPU off, Apple Clang 17 at -O3. Full range: 32 reductions of
two million values, runtime predicate threshold. [Raw ablations](ablation-results.json).

| Generated helper variant | Mixed full | Predictable full |
| --- | ---: | ---: |
| Original | 329 ms | 51 ms |
| Handwritten loop | 96 ms | 35 ms |
| Flatten helpers, retain acceptance-first branching | 338.5 ms | 74 ms |
| Select all state updates | 115 ms | 72 ms |
| State guard, then scalar selections | 114 ms | 63 ms |
| State guard, then explicit acceptance branch | 114 ms | 82 ms |
| Derive stop from updated count | 103 ms | 51 ms |
| Add branch-likelihood hint | 103.5 ms | 51 ms |
| Separate cold fallback | 99 ms | 44 ms |
| Cold fallback plus explicit unchanged fields | **96.5 ms** | **36 ms** |

The candidate was also tested with take(32), one million reductions with starting
offsets varying modulo 65536. Fourteen samples per variant, [raw early-stop results](ablation-early-results.json):

| Pipeline | Mixed early | Predictable early |
| --- | ---: | ---: |
| Original | 139.5 ms | 26 ms |
| Handwritten | 105 ms | 17 ms |
| Candidate | **105.5 ms** | **18 ms** |

A separate [full-range confirmation](ablation-confirm-results.json) records another
fourteen samples per variant: mixed candidate 97 ms versus handwritten 95 ms and
original 328 ms; predictable candidate 36 ms versus handwritten 34 ms and original
51 ms. Small differences near 1 ms should not be interpreted
as exact percentage guarantees; this is one local CPU/toolchain, not a cross-platform gate.

## What changed, and why it is legal for this transition

The helper receives an already evaluated Boolean `keep`, threshold/configuration,
remaining count `n`, downstream Control tag, sum and already mapped value `x`.

1. If `n == 0` or the downstream tag is Stop, call the original helper via a
   separate noinline/cold function. It retains the original behavior even for
   continuing-zero states and other states not reached by the ordinary pipeline.
2. Otherwise, downstream is Continue and `n > 0`. Compute:
   `n_next = keep ? n - 1 : n` and `sum_next = keep ? U32(sum + x) : sum`.
3. Compute the outer stop tag as `n_next == 0`. Within this positive-count branch
   this is equivalent to `keep && n == 1`, but exposes the shared dependency more directly.
4. Preserve configuration and the downstream tag explicitly on **both** paths,
   including after the opaque fallback call. The original transition always copies
   those fields; it never derives the downstream tag from the outer stop decision.

For valid positive Nat input, subtraction cannot underflow. Original predecessor/
successor reconstruction returns an already valid count and cannot overflow. Sum
addition retains U32 wrapping. Map and predicate stay outside the helper, once in
their original order. The fast path contains no arbitrary downstream callback:
this particular specialized downstream operation is the pure U32 sum.

Every candidate is compared directly against the original generated helper for
200,000 full input states, including both Boolean decisions, both downstream tags,
counts zero/one/two/three/max Nat, U32 wrap boundaries, and seeded random states.
All five output fields and the success return are checked. Every timing batch is
also checked against an independent Python oracle. These checks and the argument
above are not a mechanized proof of a general compiler transformation.
The winning full-range differential harness also passes with Clang undefined-behavior
sanitization enabled (200,000 comparisons).

## Why the final step matters

The opaque cold fallback alone prevents Clang from seeing that configuration and
the downstream tag never change. Assembly inspection showed extra loop-carried
fields and stores around that call. Restating their preservation lets Clang simplify
the loop while keeping a real fallback. The likelihood hint alone did not achieve
the same result. Simple helper flattening was insufficient, and explicit select
syntax alone was not a robust performance solution.

## Compiler implementation target

The useful target is **guarded scalar specialization with field-preservation summaries**,
not merely converting small Boolean branches to C ternaries:

- Analyze a bounded scalar helper region with scoped bindings, rather than inline
  arbitrary helpers through the existing emitter (the earlier shortcut failed).
- Derive unchanged output fields from expressions, not names or record positions.
- Establish branch-local scalar facts and totality before rewriting arithmetic.
- Keep the original helper as fallback for unsupported state regions.
- Preserve predicate/callback evaluation and failure behavior; reject unknown,
  boxed/ownership-sensitive and effectful computations conservatively.
- Bound analysis/code growth and measure profitability: cold outlining can be bad
  when its fallback is frequent. The experiment does not justify a universal hint.

No whole-program invariant was assumed in these replacements. This reduces the
proof scope compared with deleting supposedly unreachable zero-state cases.
Automatic discovery, end-to-end compiler validation, negative callback tests and
broader performance gates are still required. The public library, API and sibling
compiler remain unchanged.

```sh
python3 bench/compiler/ablate.py --samples 5 --output bench/compiler/ablation-results.json
python3 bench/compiler/ablate.py --early --variants guarded_cold_invariants --samples 7 --output bench/compiler/ablation-early-results.json
python3 bench/compiler/ablate.py --variants guarded_cold_invariants --samples 7 --output bench/compiler/ablation-confirm-results.json
```

The runner retains generated sources, native binaries, differential harnesses and
assembly in the printed temporary directory. Raw reports include generated-C hashes.
