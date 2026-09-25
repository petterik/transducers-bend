# Array mapcat benchmark

This benchmark is a map-reduce-shaped workload for the public source and
reducer APIs. Each balanced `Array<Quad>` supplies four U32 lanes per record.
The pipeline expands those lanes with `map` followed by List `cat`, applies a wrapping U32
normalization, filters normalized lanes whose low two bits are zero, and sums
the result.

The variants have distinct meanings:

- **Transduced** uses `over_array`, `map`, List `cat`, `filter`, and `sum`.
- **Core Bend** uses `Array.to_list`, list flattening, `Base.List.map`, a
  list-kind-compatible filter adapter, and `List.foldl`.
- **Direct Bend** is a user-authored structural array traversal that performs
  the whole operation in one fused function.
- **C**, **TypeScript**, and **Lean** are handwritten scalar twins of the
  direct loop. They are CPU-1 reference languages; they are not Bend GPU or
  16-thread implementations.

The Bend runner keeps a persistent process and times each computation with
`IO.now`. It checks every checksum against an independent Python oracle and
records CPU-1, the configured threaded CPU mode, and GPU modes. GPU availability is reported as an
unavailable mode when the host has no device. External language timings include
process startup and are therefore reported separately.

On macOS, GPU mode requires the process to have access to the host's Metal
device. A sandboxed or headless execution can report no device even when the
machine has a supported Apple GPU; run the benchmark in a host context when
that happens.

Run the default sweep with:

```sh
python3 bench/wordscan/run.py --output bench/wordscan/results.json
```

Useful knobs are `--array-depth`, `--batch-depth`, `--repeats`,
`--normalize-rounds`, and `--gpu-memory`. Increase `--gpu-memory` when a
larger materialized workload exceeds the default device span. The default
workload is intentionally compute-heavy
enough for the millisecond clock while retaining a real four-lane allocation
and flattening boundary. `build` and the direct twins use the same seed order.
A checksum mismatch catches lane-membership, wrapping, or batch-partition
errors; because the checksum is a sum, it cannot by itself prove traversal
order. The ordered `over_array` conformance test covers that property.
