#!/usr/bin/env python3
"""Compare public Array transduction with direct, materialized, and C loops."""
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
BEND = ROOT / "bench/public_array_map_filter_sum.bend"
MANUAL_C = ROOT / "bench/public_array_map_filter_sum.c"
NAMES = ["transducer", "direct_indexed", "array_mask", "list_filter", "manual_c"]
MASK = 0xFFFFFFFF


def run(*args):
    return subprocess.run([str(a) for a in args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()


def expected(depth, seed):
    total = 0
    selected = 0
    for i in range(1 << depth):
        x = (i * 1664525 + seed) & MASK
        a = (x * 2654435761) & MASK
        b = a ^ (a >> 16)
        c = (b * 2246822507) & MASK
        mapped = c ^ (c >> 13)
        if mapped & 255 < 96:
            total = (total + mapped) & MASK
            selected += 1
    return total, selected


def measured(command, want):
    elapsed, result = map(int, run(*command).split())
    assert result == want, (command, result, want)
    return elapsed


def instrument_allocations(source):
    heap = "INLINE Loc heap_alloc(Env e, Cls cls) {\n"
    tick = "static u64 io_tick(void) {\n"
    exit_code = "  io_sync();\n  return code;"
    for needle in (heap, tick, exit_code):
        assert source.count(needle) == 1, needle
    source = source.replace(heap,
        "static u64 timed_allocs = 0;\nstatic u32 ticks = 0;\n"
        "static bool timing = false;\n" + heap
        + "  if (timing) timed_allocs++;\n", 1)
    source = source.replace(tick,
        tick + "  if (ticks == 0) timing = true;\n"
        "  else if (ticks == 1) timing = false;\n  ticks++;\n", 1)
    return source.replace(exit_code,
        "  io_sync();\n"
        '  fprintf(stderr, "TIMED_ALLOC %llu %u\\n", '
        "(unsigned long long)timed_allocs, ticks);\n"
        "  return code;", 1)


def timed_allocations(binary, mode, depth, seed, want):
    result = subprocess.run([str(binary), "--threads", "1", "--gpu", "off",
                             "--", str(mode), str(depth), str(seed)],
                            cwd=ROOT, check=True, text=True, capture_output=True)
    assert int(result.stdout.split()[1]) == want
    match = re.search(r"TIMED_ALLOC (\d+) (\d+)", result.stderr)
    assert match and int(match.group(2)) == 2, result.stderr
    return int(match.group(1))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--depths", type=int, nargs="+", default=[16, 18, 20])
    p.add_argument("--sessions", type=int, default=36)
    p.add_argument("--seed", type=int, default=12345)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    assert args.sessions > 0 and 0 <= args.seed <= MASK
    assert all(0 <= d <= 23 for d in args.depths)

    with tempfile.TemporaryDirectory(prefix="public-array-vs-c-") as directory:
        temp = Path(directory)
        generated = temp / "generated.c"
        bend_binary = temp / "bend"
        manual_binary = temp / "manual_c"
        run("bun", ROOT.parent / "bend/bend2/main.ts", BEND, "-o", generated)
        run("clang", "-O3", generated, "-o", bend_binary)
        run("clang", "-O3", MANUAL_C, "-o", manual_binary)
        alloc_c = temp / "instrumented.c"
        alloc_c.write_text(instrument_allocations(generated.read_text()))
        alloc_binary = temp / "instrumented"
        run("clang", "-O3", alloc_c, "-o", alloc_binary)

        report = {
            "scope": "Native CPU, one thread; flat Array<U32>/uint32_t input built before microsecond timer; traversal and cleanup inside timer",
            "compiler_commit": run("git", "-C", ROOT.parent / "bend", "rev-parse", "HEAD"),
            "library_commit": run("git", "rev-parse", "HEAD"),
            "fixture_sha256": hashlib.sha256(BEND.read_bytes()).hexdigest(),
            "manual_c_sha256": hashlib.sha256(MANUAL_C.read_bytes()).hexdigest(),
            "platform": platform.platform(),
            "clang": run("clang", "--version").splitlines()[0],
            "seed": args.seed,
            "sessions": args.sessions,
            "results": [],
        }
        for depth in args.depths:
            want, selected = expected(depth, args.seed)
            commands = {
                "transducer": [bend_binary, "--threads", "1", "--gpu", "off", "--", 0, depth, args.seed],
                "direct_indexed": [bend_binary, "--threads", "1", "--gpu", "off", "--", 1, depth, args.seed],
                "array_mask": [bend_binary, "--threads", "1", "--gpu", "off", "--", 2, depth, args.seed],
                "list_filter": [bend_binary, "--threads", "1", "--gpu", "off", "--", 3, depth, args.seed],
                "manual_c": [manual_binary, depth, args.seed],
            }
            samples = {name: [] for name in NAMES}
            for session in range(args.sessions):
                order = list(NAMES)
                random.Random(20260926 + depth * 1000 + session).shuffle(order)
                for name in order:
                    samples[name].append(measured(commands[name], want))
            medians = {name: statistics.median(samples[name]) for name in NAMES}
            allocs = {name: timed_allocations(alloc_binary, mode, depth,
                                              args.seed, want)
                      for mode, name in enumerate(NAMES[:4])}
            row = {"depth": depth, "elements": 1 << depth,
                   "selected_elements": selected, "checksum": want,
                   "samples_us": samples, "median_us": medians,
                   "timed_bend_heap_alloc_calls": allocs}
            report["results"].append(row)
            print(depth, medians, allocs, flush=True)
        if args.output:
            args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
