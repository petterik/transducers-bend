#!/usr/bin/env python3
"""Compare eight full-frame renders with 32 tiled render tasks."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "frames8": ROOT / "bench/bullet_cathedral_parallel_frames.bend",
    "tiles32": ROOT / "bench/bullet_cathedral_tiled32.bend",
}
THREADS = (1, 2, 4, 8, 16)


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
    parser.add_argument("--sessions", type=int, default=20)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "bench/bullet-tiled32.json")
    args = parser.parse_args()
    assert 1 <= args.frames <= 120 and args.sessions > 0 and args.warmups >= 0
    frame_checksums = json.loads(
        (ROOT / "bench/bullet-cathedral-report.json").read_text()
    )["frame_checksums"]
    expected = sum(frame_checksums[:args.frames]) & 0xFFFFFFFF

    with tempfile.TemporaryDirectory(prefix="bullet-tiled32-") as directory:
        directory = Path(directory)
        binaries = {name: build(source, directory)
                    for name, source in SOURCES.items()}

        prefix = 0
        for count in range(args.frames + 1):
            if count:
                prefix = (prefix + frame_checksums[count - 1]) & 0xFFFFFFFF
            got = timed(binaries["tiles32"], count, 16)[1]
            assert got == prefix, (count, got, prefix)
        for name, binary in binaries.items():
            for mode, want in ((1, 405), (2, 214)):
                got = int(run(binary, "--threads", 1, "--gpu", "off",
                              "--", 119, mode).stdout.strip())
                assert got == want, (name, mode, got)

        conditions = [(name, threads) for name in SOURCES for threads in THREADS]
        samples = {name: {str(n): [] for n in THREADS} for name in SOURCES}
        for _ in range(args.warmups):
            for name, threads in conditions:
                assert timed(binaries[name], args.frames, threads)[1] == expected
        rng = random.Random(20260926)
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
    baseline = medians["frames8"]["8"]
    relative = {name: {n: baseline / median
                       for n, median in by_thread.items()}
                for name, by_thread in medians.items()}
    report = {
        "description": "Eight full-frame tasks versus eight frames times four tiles",
        "sources_sha256": {name: hashlib.sha256(source.read_bytes()).hexdigest()
                           for name, source in SOURCES.items()},
        "compiler_commit": run("git", "-C", ROOT.parent / "bend",
                               "rev-parse", "HEAD").stdout.strip(),
        "frames": args.frames, "threads": THREADS,
        "sessions": args.sessions, "warmups_per_condition": args.warmups,
        "random_seed": 20260926, "orders": orders,
        "samples_us": samples, "medians_us": medians,
        "speedups_relative_to_frames8_eight_threads": relative,
        "verified_prefix_counts": args.frames + 1,
        "final_accepted_hits": 405, "final_player_shield": 214,
        "checksum": expected,
        "timing_note": "One process per sample. Bend's internal clock includes ordered world updates, rendering, and all pixel checksums. The tiled path renders four 512x128 buffers per frame and sums their checksums; it does not assemble a full image. Compilation, process startup, export, and display are excluded. All runs use --gpu off.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"medians_us": medians,
                      "verified_prefix_counts": args.frames + 1}))


if __name__ == "__main__":
    main()
