#!/usr/bin/env python3
"""Paired native comparison of Bend transducers, direct Bend, C, and Rust."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import re
import statistics
import subprocess
import tempfile

from public_array_map_filter_sum import instrument_allocations

ROOT = Path(__file__).resolve().parents[1]
BEND = ROOT / "bench/public_array_map_inc_sum.bend"
MANUAL_C = ROOT / "bench/public_array_map_inc_sum.c"
RUST = ROOT / "bench/public_array_map_inc_sum.rs"
NAMES = ["bend_transducer", "bend_direct", "manual_c", "rust_iterator", "rust_direct"]
MASK = 0xFFFFFFFF


def command(*args):
    return subprocess.run([str(a) for a in args], cwd=ROOT, check=True,
                          capture_output=True, text=True)


def want(depth, seed):
    return sum(((i * 1664525 + seed + 1) & MASK)
               for i in range(1 << depth)) & MASK


def measured(argv, expected):
    elapsed, result = map(int, command(*argv).stdout.split())
    assert result == expected, (argv, result, expected)
    return elapsed


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depths", type=int, nargs="+", default=[16, 18, 20])
    parser.add_argument("--sessions", type=int, default=36)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    assert args.sessions > 0 and 0 <= args.seed <= MASK
    assert all(0 <= d <= 23 for d in args.depths)

    with tempfile.TemporaryDirectory(prefix="bend-map-inc-sum-") as directory:
        temp = Path(directory)
        generated = temp / "bend.c"
        bend_binary = temp / "bend"
        c_binary = temp / "manual_c"
        rust_binary = temp / "rust"
        command("bun", ROOT.parent / "bend/bend2/main.ts", BEND, "-o", generated)
        remarks = command("clang", "-O3", "-Rpass=loop-vectorize",
                          generated, "-o", bend_binary).stderr
        command("clang", "-O3", MANUAL_C, "-o", c_binary)
        command("rustc", "-C", "opt-level=3", "-C", "target-cpu=native",
                RUST, "-o", rust_binary)
        alloc_source = temp / "alloc.c"
        alloc_source.write_text(instrument_allocations(generated.read_text()))
        alloc_binary = temp / "alloc"
        command("clang", "-O3", alloc_source, "-o", alloc_binary)

        report = {
            "scope": "Native CPU, one thread; flat Array<U32>/uint32_t/Vec<u32> built before timer; traversal and disposal in timer; each sample is a separate process",
            "compiler_commit": command("git", "-C", ROOT.parent / "bend", "rev-parse", "HEAD").stdout.strip(),
            "library_commit": command("git", "rev-parse", "HEAD").stdout.strip(),
            "compiler_comp_ts_sha256": digest(ROOT.parent / "bend/bend2/comp.ts"),
            "compiler_base_sha256": digest(ROOT.parent / "bend/bend2/base.bend"),
            "source_sha256": {path.name: digest(path) for path in (BEND, MANUAL_C, RUST)},
            "generated_c_sha256": digest(generated),
            "platform": platform.platform(),
            "clang": command("clang", "--version").stdout.splitlines()[0],
            "rustc": command("rustc", "--version").stdout.strip(),
            "vectorization_remarks": [line for line in remarks.splitlines()
                                      if "vectorized loop" in line],
            "seed": args.seed,
            "sessions": args.sessions,
            "results": [],
        }
        for depth in args.depths:
            expected = want(depth, args.seed)
            commands = {
                "bend_transducer": [bend_binary, "--threads", 1, "--gpu", "off", "--", 0, depth, args.seed],
                "bend_direct": [bend_binary, "--threads", 1, "--gpu", "off", "--", 1, depth, args.seed],
                "manual_c": [c_binary, depth, args.seed],
                "rust_iterator": [rust_binary, 0, depth, args.seed],
                "rust_direct": [rust_binary, 1, depth, args.seed],
            }
            samples = {name: [] for name in NAMES}
            for session in range(args.sessions):
                names = list(NAMES)
                random.Random(20260927 + 1000 * depth + session).shuffle(names)
                for name in names:
                    samples[name].append(measured(commands[name], expected))
            allocation_counts = {}
            for mode, name in enumerate(NAMES[:2]):
                result = command(alloc_binary, "--threads", 1, "--gpu", "off",
                                 "--", mode, depth, args.seed)
                assert int(result.stdout.split()[1]) == expected
                match = re.search(r"TIMED_ALLOC (\d+) (\d+)", result.stderr)
                assert match and int(match.group(2)) == 2
                allocation_counts[name] = int(match.group(1))
            row = {"depth": depth, "elements": 1 << depth,
                   "checksum": expected, "samples_us": samples,
                   "median_us": {name: statistics.median(samples[name]) for name in NAMES},
                   "timed_bend_heap_alloc_calls": allocation_counts}
            report["results"].append(row)
            print(depth, row["median_us"], allocation_counts, flush=True)
        if args.output:
            args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
