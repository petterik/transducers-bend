#!/usr/bin/env python3
"""Compare the public owned-List fold with three handwritten C layouts."""
import argparse
import json
from pathlib import Path
import platform
import random
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BEND = ROOT / "bench/public_list_map_fold.bend"
C = ROOT / "bench/manual_c_list.c"


def run(*args):
    return subprocess.run([str(arg) for arg in args], cwd=ROOT,
                          check=True, text=True, capture_output=True).stdout.strip()


def sample(command, expected):
    elapsed, result = map(int, run(*command).split())
    assert result == expected, (command, result, expected)
    return elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=36)
    parser.add_argument("--sizes", type=int, nargs="+", default=[65536, 262144])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    assert args.sessions > 0 and all(0 < n <= 0xFFFFFFFF for n in args.sizes)
    with tempfile.TemporaryDirectory(prefix="bend-vs-c-list-") as directory:
        temp = Path(directory)
        generated = temp / "bend.c"
        bend_binary = temp / "bend"
        c_binary = temp / "manual_c"
        run("bun", ROOT.parent / "bend/bend2/main.ts", BEND, "-o", generated)
        run("clang", "-O3", generated, "-o", bend_binary)
        run("clang", "-O3", C, "-o", c_binary)
        report = {
            "scope": "Ascending U32 input; sum of x+1; construction before clock; traversal and cleanup inside clock. C controls: separately allocated linked nodes, arena linked nodes, and flat array.",
            "compiler_commit": run("git", "-C", ROOT.parent / "bend", "rev-parse", "HEAD"),
            "platform": platform.platform(),
            "clock": "CLOCK_MONOTONIC microseconds; separate one-thread processes",
            "c_compiler": run("clang", "--version").splitlines()[0],
            "sessions": args.sessions,
            "results": [],
        }
        for size in args.sizes:
            expected = size * (size + 1) // 2 % (1 << 32)
            commands = {
                "bend_direct": [bend_binary, "--threads", "1", "--gpu", "off", "--", "0", size],
                "bend_transduce": [bend_binary, "--threads", "1", "--gpu", "off", "--", "1", size],
                "c_linked_list": [c_binary, "linked", size],
                "c_arena_list": [c_binary, "arena", size],
                "c_flat_array": [c_binary, "flat", size],
            }
            times = {name: [] for name in commands}
            for session in range(args.sessions):
                order = list(commands)
                random.Random(20260926 + size + session).shuffle(order)
                for name in order:
                    times[name].append(sample(commands[name], expected))
            medians = {name: statistics.median(values) for name, values in times.items()}
            report["results"].append({"size": size, "expected": expected,
                                      "samples_us": times, "median_us": medians})
            print(size, medians, flush=True)
        if args.output:
            args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
