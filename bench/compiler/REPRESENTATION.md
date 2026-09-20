# Local representation probe

Status: measurement complete; no new rewrite is promoted from this probe.

The first representation question is whether the reducer description and
callback dispatch survive in the generated program. The second is whether the
remaining state is real application data. `partition_all` must retain a group
buffer; its list storage is not abstraction overhead to erase.

`representation_probe.py` checks a scalar pipeline and the `keep` plus
`partition_all` extension on JS and native CPU. Both have no `Reducer` or
`Reduction` records in generated JS and no `Clo.apply` calls in generated C.
The report still records C `heap_alloc` and `term_pak` occurrences, but those are
source/runtime layout observations, not per-element allocation counts. They must
not be interpreted as a live heap profile.

The current result supports a narrow conclusion: static reducer/callback
composition is removed at these boundaries, while buffered state remains a real
cost. It does not identify a profitable local rewrite yet. The next target is a
small typed constructor/projection or nonescaping scalar-state case with a paired
direct reference. Keep/partition must remain a correctness and ownership test
while that analysis is developed.

```sh
python3 bench/compiler/representation_probe.py \
  --bend-main /tmp/transduce-workset0/main.ts \
  --output bench/compiler/representation-results.json
```
