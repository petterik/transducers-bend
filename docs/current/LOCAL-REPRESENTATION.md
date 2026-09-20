---
created_at: 2026-09-20T21:22:00+02:00
status: current
---

# Local representation elimination

Status: first general constructor-match rewrite demonstrated in the isolated
compiler. The rule does not mention transducers or `keep`: it handles an
ordinary two-constructor value with an exact static arm fact.

The fixture constructs `Left{5}` and calls a matcher with a dynamic Boolean.
The original emitter still carries the generic `Left`/`Right` branch into the
fused segment. The scoped-fact compiler carries the tagged layout through the
fused call, selects `Left`, and emits only the Boolean match. The native output
shrinks by 85 bytes while JS output and native/JS results remain identical:

```text
facts: selected 2, rejected 0
original C: 84421 bytes
candidate C: 84336 bytes
delta: -85 bytes
result: 6
```

The report is [`local-representation-results.json`](../../bench/compiler/local-representation-results.json),
and the independent source is
[`local_representation_fact.bend`](../../bench/compiler/fixtures/local_representation_fact.bend).
The probe also builds both versions with UBSan and runs the JS artifact.

Tagged layouts required an adversarial correction to the first fact prototype.
The constructor tag occupies a word that is absent from the fact's field list;
fact rebinding now uses the recorded constructor arm and field offsets rather
than assuming fields start at word zero. The focused scoped-fact fixture still
reports two selections and two dynamic-field rejections after that change, and
the full 20-file suite passes in the JS-then-native output order.

This closes only the first local representation slice. The existing
`keep`/`cat_maybe` pipeline remains correct and has no reducer records in the
current representation probe, but this rule has not yet eliminated a visible
`Some`/`None` wrapper in that buffered pipeline. The next slice should compare
an ordinary `Maybe` producer with a direct consuming reference, preserving the
wrapper for opaque producers and retaining partition buffers and output
storage.

Reproduce it with:

```sh
python3 bench/compiler/local_representation_probe.py \
  --bend-main "$facts/main.ts" \
  --output bench/compiler/local-representation-results.json
```
