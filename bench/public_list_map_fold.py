#!/usr/bin/env python3
"""Compare current public transduce with direct Bend and Base.List.map/foldl."""
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

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "bench/public_list_map_fold.bend"
MODES = {0: "direct", 1: "transduce", 2: "list_map_fold"}


def command(*args):
    result = subprocess.run([str(arg) for arg in args], cwd=ROOT,
                            text=True, capture_output=True, check=True)
    return result.stdout.strip()


def expected(size):
    return (size * (size + 1) // 2) % (1 << 32)


def run_sample(binary, mode, size):
    elapsed, value = map(int, command(binary, "--threads", "1", "--gpu",
                                      "off", "--", mode, size).split())
    assert value == expected(size), (mode, size, value)
    return elapsed


def instrument_allocations(source):
    heap = "INLINE Loc heap_alloc(Env e, Cls cls) {\n"
    tick = "static u64 io_tick(void) {\n"
    exit_code = "  io_sync();\n  return code;"
    for needle in (heap, tick, exit_code):
        assert source.count(needle) == 1, needle
    source = source.replace(heap,
        "static u64 all_allocs = 0, timed_allocs = 0;\n"
        "static u32 ticks = 0;\nstatic bool timing = false;\n"
        + heap + "  all_allocs++;\n  if (timing) timed_allocs++;\n", 1)
    source = source.replace(tick,
        tick + "  if (ticks == 0) timing = true;\n"
        "  else if (ticks == 1) timing = false;\n  ticks++;\n", 1)
    return source.replace(exit_code,
        "  io_sync();\n"
        '  fprintf(stderr, "ALLOC all=%llu timed=%llu ticks=%u\\n", '
        "(unsigned long long)all_allocs, "
        "(unsigned long long)timed_allocs, ticks);\n"
        "  return code;", 1)


def allocations(binary, mode, size):
    result = subprocess.run([str(binary), "--threads", "1", "--gpu", "off",
                             "--", str(mode), str(size)], cwd=ROOT,
                            text=True, capture_output=True, check=True)
    assert int(result.stdout.split()[1]) == expected(size)
    match = re.search(r"ALLOC all=(\d+) timed=(\d+) ticks=(\d+)", result.stderr)
    assert match and int(match.group(3)) == 2, result.stderr
    return {"total_heap_alloc_calls": int(match.group(1)),
            "timed_heap_alloc_calls": int(match.group(2))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=24)
    parser.add_argument("--sizes", type=int, nargs="+", default=[4096, 65536, 262144])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    assert args.sessions > 0 and all(size > 0 for size in args.sizes)
    with tempfile.TemporaryDirectory(prefix="public-list-map-fold-") as tmp:
        tmp = Path(tmp)
        c_file = tmp / "bench.c"
        binary = tmp / "bench"
        command("bun", ROOT.parent / "bend/bend2/main.ts", FIXTURE, "-o", c_file)
        command("clang", "-O3", c_file, "-o", binary)
        instrumented = tmp / "instrumented.c"
        instrumented.write_text(instrument_allocations(c_file.read_text()))
        alloc_binary = tmp / "instrumented"
        command("clang", "-O3", instrumented, "-o", alloc_binary)
        report = {
            "scope": "Owned dynamic List<U32>; sum of inc; source built before timer",
            "compiler_commit": command("git", "-C", ROOT.parent / "bend", "rev-parse", "HEAD"),
            "library_commit": command("git", "rev-parse", "HEAD"),
            "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            "platform": platform.platform(),
            "clock": "native monotonic microseconds; separate one-thread processes",
            "allocation_metric": "generated C heap_alloc calls; timed interval excludes input build",
            "sessions": args.sessions,
            "variants": MODES,
            "results": [],
        }
        for size in args.sizes:
            samples = {name: [] for name in MODES.values()}
            for session in range(args.sessions):
                order = list(MODES)
                random.Random(20260925 + session).shuffle(order)
                for mode in order:
                    samples[MODES[mode]].append(run_sample(binary, mode, size))
            medians = {name: statistics.median(times)
                       for name, times in samples.items()}
            allocs = {name: allocations(alloc_binary, mode, size)
                      for mode, name in MODES.items()}
            report["results"].append({
                "size": size, "expected": expected(size),
                "samples_us": samples, "median_us": medians,
                "ratio_to_direct": {name: value / medians["direct"]
                                    for name, value in medians.items()},
                "median_session_ratio_to_direct": {
                    name: statistics.median(value / direct
                        for value, direct in zip(times, samples["direct"]))
                    for name, times in samples.items()},
                "heap_alloc_calls": allocs,
            })
            print(size, medians, allocs, flush=True)
        if args.output:
            args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
