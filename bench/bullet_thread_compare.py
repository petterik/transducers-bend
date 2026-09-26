#!/usr/bin/env python3
"""Measure Bullet Cathedral at one, two, four, and eight CPU threads."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import tempfile

from bullet_layout_compare import ROOT, SOURCES

THREADS = (1, 2, 4, 8)


def run(*args):
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True,
                          capture_output=True, text=True)


def build(source, directory):
    generated = directory / f"{source.stem}.c"
    binary = directory / source.stem
    run("bun", ROOT.parent / "bend/bend2/main.ts", source, "-o", generated)
    run("clang", "-O3", generated, "-o", binary)
    return binary


def timed(binary, frames, threads):
    output = run(binary, "--threads", threads, "--gpu", "off", "--",
                 frames, "bench", "x")
    return tuple(map(int, output.stdout.split()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--sessions", type=int, default=12)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "bench/bullet-thread-comparison.json")
    args = parser.parse_args()
    assert args.frames > 0 and args.sessions > 0 and args.warmups >= 0
    reference = json.loads((ROOT / "bench/bullet-cathedral-report.json").read_text())
    assert args.frames <= len(reference["frame_checksums"])
    expected = sum(reference["frame_checksums"][:args.frames]) & 0xFFFFFFFF

    with tempfile.TemporaryDirectory(prefix="bullet-threads-") as directory:
        directory = Path(directory)
        binaries = {name: build(source, directory)
                    for name, source in SOURCES.items()}
        conditions = [(name, threads) for name in SOURCES for threads in THREADS]
        samples = {name: {str(n): [] for n in THREADS} for name in SOURCES}
        for _ in range(args.warmups):
            for name, threads in conditions:
                assert timed(binaries[name], args.frames, threads)[1] == expected
        rng = random.Random(20260928)
        orders = []
        for _ in range(args.sessions):
            order = conditions.copy()
            rng.shuffle(order)
            orders.append([f"{name}/{threads}" for name, threads in order])
            for name, threads in order:
                micros, checksum = timed(binaries[name], args.frames, threads)
                assert checksum == expected, (name, threads, checksum)
                samples[name][str(threads)].append(micros)

    medians = {name: {n: statistics.median(values)
                      for n, values in by_thread.items()}
               for name, by_thread in samples.items()}
    speedups = {name: {n: medians[name]["1"] / median
                       for n, median in by_thread.items()}
                for name, by_thread in medians.items()}
    report = {
        "description": "CPU thread-count sweep of the existing sequential 120-frame Bullet Cathedral programs",
        "sources_sha256": {name: hashlib.sha256(source.read_bytes()).hexdigest()
                           for name, source in SOURCES.items()},
        "compiler_commit": run("git", "-C", ROOT.parent / "bend",
                               "rev-parse", "HEAD").stdout.strip(),
        "frames": args.frames, "threads": THREADS,
        "warmups_per_condition": args.warmups,
        "sessions": args.sessions, "random_seed": 20260928,
        "orders": orders, "samples_us": samples,
        "medians_us": medians, "speedups_relative_to_one_thread": speedups,
        "checksum": expected,
        "timing_note": "One native process per sample. The internal Bend clock times sequential simulation, collisions, RGB framebuffers, and checksums. Compilation, startup, export, and display are excluded. --gpu off is set for every run.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"medians_us": medians, "speedups": speedups}))


if __name__ == "__main__":
    main()
