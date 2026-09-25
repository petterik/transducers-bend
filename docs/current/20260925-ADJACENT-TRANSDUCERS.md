---
created_at: 2026-09-25T22:32:20+02:00
status: implemented
---

# Adjacent transducers

`dedupe(~A, ~equal)` compares each input with the immediately preceding input
and drops it when `equal(previous, current)` is true. It does not maintain a
set: a value reappearing after a different value is emitted again. Bend has no
implicit equality interface here, so the caller supplies the comparison.
The stage stores the previous value and forwards the current one, requiring
`A: Data`; affine values need a separate key or borrow-based API.

`interpose(~A, separator)` emits the separator before every input after the
first. The separator can be reused only when `A: Data`. It inherits the
downstream stop permit. In particular, if the reducer stops after the
separator, the next input is not forwarded. Empty and singleton sources emit
no separator, and completion remains the downstream reducer's one finish.

Both stages use the same `Reducer`/`Xf` recipe and source protocol as the
existing stages. They add no compiler rule. The public fixture checks ordered
outputs, a custom equality relation, empty/singleton inputs, `take` on both
sides of `interpose`, and initial and separator-triggered stops on JS and
native. The differential suite checks 47 more List cases against independent
Python results, including repeated values and mixed compositions. These are
semantic checks; runtime and allocation parity with handwritten folds have
not yet been measured for these stages.
