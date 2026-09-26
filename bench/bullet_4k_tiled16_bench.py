#!/usr/bin/env python3
"""Compare eight full 4K renders with sixteen half-frame render tasks."""
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
    "frames8": ROOT / "bench/bullet_cathedral_4k_frames.bend",
    "tiles16": ROOT / "bench/bullet_cathedral_4k_tiled16.bend",
}
THREADS = (8, 16)


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
    parser.add_argument("--sessions", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "bench/bullet-4k-tiled16.json")
    args = parser.parse_args()
    assert 1 <= args.frames <= 120 and args.sessions > 0 and args.warmups >= 0

    with tempfile.TemporaryDirectory(prefix="bullet-4k-tiles-") as directory:
        directory = Path(directory)
        binaries = {name: build(source, directory)
                    for name, source in SOURCES.items()}

        per_frame = []
        for frame in range(args.frames):
            full_output = run(binaries["frames8"], "--threads", 1,
                              "--gpu", "off", "--", frame).stdout
            full = int(full_output.split()[1])
            tiled = int(run(binaries["tiles16"], "--threads", 2,
                            "--gpu", "off", "--", frame, 3).stdout)
            assert tiled == full, (frame, full, tiled)
            per_frame.append(full)
        expected = sum(per_frame) & 0xFFFFFFFF

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
    speedups = {name: {n: baseline / median
                       for n, median in by_thread.items()}
                for name, by_thread in medians.items()}
    report = {
        "description": "3840x2160, eight full-frame tasks versus eight frames times two tiles",
        "sources_sha256": {name: hashlib.sha256(source.read_bytes()).hexdigest()
                           for name, source in SOURCES.items()},
        "compiler_commit": run("git", "-C", ROOT.parent / "bend",
                               "rev-parse", "HEAD").stdout.strip(),
        "frames": args.frames, "width": 3840, "height": 2160,
        "tasks_per_batch": {"frames8": 8, "tiles16": 16},
        "threads": THREADS, "sessions": args.sessions,
        "warmups_per_condition": args.warmups, "random_seed": 20260926,
        "orders": orders, "samples_us": samples, "medians_us": medians,
        "speedups_relative_to_frames8_eight_threads": speedups,
        "verified_frame_checksums": len(per_frame),
        "frame_checksums": per_frame,
        "final_accepted_hits": 405, "final_player_shield": 214,
        "checksum": expected,
        "timing_note": "One process per sample. Bend's internal clock includes ordered world updates, 3840x2160 rendering, and all pixel checksums. The tiled path renders two 3840x1080 buffers per frame and sums their checksums; it does not assemble a full image. Compilation, process startup, export, and display are excluded. All runs use --gpu off.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"medians_us": medians,
                      "verified_frame_checksums": len(per_frame),
                      "checksum": expected}))


if __name__ == "__main__":
    main()
