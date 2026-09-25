#!/usr/bin/env python3
"""Compare fused drop/map_indexed/take_nth with the same direct Bend fold."""
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

from public_list_map_fold import command, instrument_allocations

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "bench/new_transducer_fusion.bend"
NORMAL = {0: "direct", 1: "transduce"}
MIRROR = {0: "transduce", 1: "direct"}


def expected(size, no_drop):
    start = 0 if no_drop else 32
    return sum(x + x - start for x in range(start, size, 3)) % (1 << 32)


def execute(binary, mode, size, no_drop):
    result = subprocess.run([str(binary), "--threads", "1", "--gpu", "off",
                             "--", str(mode), str(size)], cwd=ROOT,
                            text=True, capture_output=True, check=True)
    elapsed, value = map(int, result.stdout.split())
    assert value == expected(size, no_drop), (size, mode, value)
    return elapsed, result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=36)
    parser.add_argument("--sizes", type=int, nargs="+", default=[4096, 65536, 262144])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--mirror", action="store_true",
                        help="put the transducer in the first dispatch case")
    parser.add_argument("--no-drop", action="store_true",
                        help="ablate the initial drop in both comparators")
    args = parser.parse_args()
    assert args.sessions > 0 and all(size > 0 for size in args.sizes)
    modes = MIRROR if args.mirror else NORMAL
    with tempfile.TemporaryDirectory(prefix="new-transducer-fusion-") as tmp:
        tmp = Path(tmp)
        c_file = tmp / "bench.c"
        binary = tmp / "bench"
        source = FIXTURE.read_text()
        if args.mirror or args.no_drop:
            if args.no_drop:
                source = source.replace(
                    "X.transduce(X.comp3(X.drop(~U32, 32n),\n"
                    "    X.map_indexed(~U32, ~U32, ~indexed),\n",
                    "X.transduce(X.comp2(\n"
                    "    X.map_indexed(~U32, ~U32, ~indexed),\n")
                source = source.replace("direct_skip(xs, 32n)",
                                        "direct_steady(xs, 0n, 0n, 0)")
            if args.mirror:
                direct_call = ("direct_steady(xs, 0n, 0n, 0)" if args.no_drop
                               else "direct_skip(xs, 32n)")
                source = source.replace("case 0n: " + direct_call + "\n"
                                        "    case _: pipeline(xs)",
                                        "case 0n: pipeline(xs)\n"
                                        "    case _: " + direct_call)
            assert source != FIXTURE.read_text()
            with tempfile.NamedTemporaryFile(mode="w", dir=FIXTURE.parent,
                                             suffix=".bend") as mirrored:
                mirrored.write(source)
                mirrored.flush()
                command("bun", ROOT.parent / "bend/bend2/main.ts",
                        mirrored.name, "-o", c_file)
        else:
            command("bun", ROOT.parent / "bend/bend2/main.ts", FIXTURE,
                    "-o", c_file)
        command("clang", "-O3", c_file, "-o", binary)
        instrumented = tmp / "instrumented.c"
        instrumented.write_text(instrument_allocations(c_file.read_text()))
        alloc_binary = tmp / "instrumented"
        command("clang", "-O3", instrumented, "-o", alloc_binary)
        report = {
            "scope": ("Owned dynamic List<U32>; map_indexed/take_nth3/sum"
                      if args.no_drop else
                      "Owned dynamic List<U32>; drop32/map_indexed/take_nth3/sum"),
            "compiler_commit": command("git", "-C", ROOT.parent / "bend", "rev-parse", "HEAD"),
            "library_commit": command("git", "rev-parse", "HEAD"),
            "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            "compiled_fixture_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "layout": "swapped" if args.mirror else "normal",
            "drop_ablation": args.no_drop,
            "platform": platform.platform(),
            "clock": "native monotonic microseconds; one-thread processes",
            "allocation_metric": "generated C heap_alloc calls inside timer",
            "sessions": args.sessions, "results": [],
        }
        for size in args.sizes:
            samples = {name: [] for name in modes.values()}
            for session in range(args.sessions):
                order = list(modes)
                random.Random(20260925 + session).shuffle(order)
                for mode in order:
                    elapsed, _ = execute(binary, mode, size, args.no_drop)
                    samples[modes[mode]].append(elapsed)
            medians = {name: statistics.median(values)
                       for name, values in samples.items()}
            allocs = {}
            for mode, name in modes.items():
                _, stderr = execute(alloc_binary, mode, size, args.no_drop)
                match = re.search(r"ALLOC all=(\d+) timed=(\d+) ticks=(\d+)", stderr)
                assert match and int(match.group(3)) == 2, stderr
                allocs[name] = int(match.group(2))
            report["results"].append({
                "size": size, "expected": expected(size, args.no_drop),
                "samples_us": samples, "median_us": medians,
                "median_session_ratio": statistics.median(
                    public / direct for direct, public in
                    zip(samples["direct"], samples["transduce"])),
                "timed_heap_alloc_calls": allocs,
            })
            print(size, medians, allocs, flush=True)
        if args.output:
            args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
