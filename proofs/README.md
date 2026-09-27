# Checked laws and trust boundary

Run each proof with the sibling fork's checker:

```sh
bun ../bend/bend2/main.ts proofs/list_map_fold_law.bend
bun ../bend/bend2/main.ts proofs/no_stop_control_law.bend
```

Both commands returned `{==}` on the 2026-09-27 local fork.

- `list_map_fold_law.bend` proves by induction that mapping a pure `List<U32>`
  and then folding gives the same result as feeding each mapped value directly
  to the fold step, for arbitrary static U32 mapper and fold functions. It
  also proves that two List maps compose into one map. These model the
  map/fold part of a transducer. They do not mention `Xf` or prove the
  emitter's optimization.
- `no_stop_control_law.bend` uses the library's actual
  `T.Control<Empty, U32>` type. Its `Stop` branch eliminates an impossible
  `Empty` permit, and induction proves that its List driver agrees with a
  total fold for arbitrary static U32 steps.

The public `X.transduce` lifecycle, `Array.walk` bounds lowering, stop
propagation through `cat`, and Bullet Cathedral's collision geometry remain
without machine-checked theorems in this directory. Tests and the independent collision oracle are
separate evidence. Any proof here trusts Bend's checker and source semantics;
it does not establish correctness of the generated C, Clang, CPU, or GPU.

The [Bullet Cathedral geometry argument](bullet_cathedral_geometry.md)
derives nine-cell collision coverage and health/framebuffer index bounds
from the scene's constants. It is a mathematical argument with an explicit
floating-point trust boundary, not a Bend-checked proof.
