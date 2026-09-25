---
created_at: 2026-09-25T14:37:00+02:00
updated_at: 2026-09-25T14:37:00+02:00
status: feature-branch
---

# Bend fork integration

`petterik/bend:main` was fast-forwarded to `bendlang/bend:main` at
`3276efac`. The compiler implementation lives on
`codex/transducer-companions`, commit `647be979`, branched from that commit.
No transducer compiler changes were placed on the fork's `main`.

The branch integrates three generic rules from the isolated candidate:

- A bounded compile-time specialization of statically constructed callbacks
  in the emitter. Its closed-term cache refuses open runtime captures.
- Structural inference for omitted template arguments from the checked types
  of runtime arguments. Noninferable forms defer rather than guessing.
- Opt-in owner-companion conversion for an expected nominal target type. A
  marked target accepts only a method owned by the source type, or one
  protocol-owned extension for a Base type. The method's result goes through
  the ordinary checker; no global registry or arbitrary imported method wins.

Bare constructors are resolved after inferable arguments, allowing
`into([], xf, xs)` and direct custom constructor sources. The constructor's
declaring type selects one method; the target's first index supplies at most
one template argument; every field and the result are checked normally.
`tests/check/companion_owned.bend` is a fork-local generic regression test.
The full transducer companion probe exercises raw List, Range, Array, custom
source and destination, literal forms, type changes, completion, ownership,
and six expected refusals. The 33-test library suite passes on the branch.

The direct branch is the authoritative compiler implementation. The local
candidate generator in `experiments/affine_xf` remains a reproducible way to
compare against upstream `bendlang/main`; it recognizes the upstream
`op_name` rename while retaining the older compiler hash for historical
results. The generated and branch compiler files were compared before the
branch commit.

Compile-time spot checks used twelve separate Bun compiler processes per
fixture, median wall time, comparing the same static pass without companions
against the full branch: `pipeline` 89.3/91.8 ms, `api_surface` 100.6/102.8
ms, `array` 174.8/186.4 ms. These are small, process-startup-inclusive
samples; the array lane merits a larger paired measurement before claiming
negligible compile-time cost. The marker-name prefilter avoids inspecting
every unmarked ADT's companion method.

The source protocol remains a library design in `transduce.bend`, and the
fork compiler branch remains experimental pending wider Bend regression and
performance testing. In particular, the general companion convention should
be reviewed before claiming it is suitable for the upstream language.
