# Stop-permit public vertical slice (2026-09-25)

This slice tests the proposed library type change before altering the established modules. [The prototype](../../experiments/affine_xf/permit_protocol.bend) has an associated stop permit inside each reducer recipe, an unchanged `Xf` provider shape, a generic source contract, direct Array companion selection, and an explicitly witnessed independent branching source. [The benchmark](../../experiments/affine_xf/permit_public_bench.bend) calls the prototype's actual `transduce` entry point rather than a handwritten fold helper.

The confidence pass found one necessary correction to the initial sketch: the permit must be `Data`, not merely `Type`. Inspection retains a stopped accumulator and reports that it halted; doing both needs a reusable permit. `Empty` and `Unit` are `Data`, while the accumulator stays affine. Bend checks this: the first `Type`-permit version failed at that ownership boundary; the `Data`-permit version checks.

The prototype covers `sum` with `Empty`, `map` and `filter` preserving the downstream permit, and `take` introducing `Unit`. It checks and produces `[16, 16, 0, 6, 100, 27]` for total and stopping Array/tree examples under both stock Bend and the isolated match-only compiler. This includes `take(0)` before a source item. The `Xf` composition type remained the same shape; only reducer contents and the source `Drive`'s erased permit parameter changed. A source still returns the opaque accumulator, without constructing Stop itself.

Generated JS and native return those values. CLI value mode normalizes the Array calls but currently leaves the imported custom-source calls stuck with unresolved `?AUTO` template arguments; a direct call on the same tree normalizes to `100`. This is a separate interpreter/inference gap to resolve before claiming all execution modes work.

Fifteen randomized native executions per cell, microseconds, one thread, source construction outside the timed region:

| Source | Stock direct | Stock public `transduce` | Match-only direct | Match-only public `transduce` |
| --- | ---: | ---: | ---: | ---: |
| Array, 2^18 leaves | 1962 | 2165 | 1935 | 1945 |
| Branching tree, 2^16 leaves | 146 | 166 | 145 | 148 |

Thus the narrower compiler candidate closes this particular public total-path gap to about 0.5% on Array and 2% on the branching tree. These are local medians, not a blanket transducer performance guarantee. The established library has not changed yet. The next work is to migrate the full reducer/source protocol, preserve nested stopping and completion, and harden the compiler rule. If the full API loses this result, investigate the gap before accepting a larger compiler rewrite.
