#!/usr/bin/env python3
"""Measure the sequential Bend simulation and renderer, including allocations."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
import tempfile

from public_array_map_filter_sum import instrument_allocations

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/bullet_cathedral.bend"


def run(*args):
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True,
                          capture_output=True, text=True)


def timed(binary, frames):
    output = run(binary, "--threads", 1, "--gpu", "off", "--",
                 frames, "bench", "x")
    elapsed, checksum = map(int, output.stdout.split())
    return elapsed, checksum, output.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "bench/bullet-cathedral-bench.json")
    args = parser.parse_args()
    assert args.frames > 0 and args.warmups >= 0 and args.sessions > 0

    with tempfile.TemporaryDirectory(prefix="bullet-bench-") as directory:
        directory = Path(directory)
        generated = directory / "bend.c"
        binary = directory / "bend"
        allocations_source = directory / "allocations.c"
        allocations_binary = directory / "allocations"
        run("bun", ROOT.parent / "bend/bend2/main.ts", SOURCE, "-o", generated)
        run("clang", "-O3", generated, "-o", binary)
        allocations_source.write_text(instrument_allocations(generated.read_text()))
        run("clang", "-O3", allocations_source, "-o", allocations_binary)

        baseline = timed(binary, args.frames)[1]
        for _ in range(args.warmups):
            assert timed(binary, args.frames)[1] == baseline
        samples = []
        for _ in range(args.sessions):
            elapsed, checksum, _ = timed(binary, args.frames)
            assert checksum == baseline
            samples.append(elapsed)
        elapsed, checksum, stderr = timed(allocations_binary, args.frames)
        assert checksum == baseline
        match = re.search(r"TIMED_ALLOC (\d+) (\d+)", stderr)
        assert match and int(match.group(2)) == 2, stderr
        allocations = int(match.group(1))

    report = {
        "description": "One-thread native Bend, sequential simulation and 512x512 RGB rendering",
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "compiler_commit": run("git", "-C", ROOT.parent / "bend",
                               "rev-parse", "HEAD").stdout.strip(),
        "frames": args.frames, "warmups": args.warmups,
        "samples_us": samples, "median_us": statistics.median(samples),
        "checksum": baseline, "timed_heap_allocations": allocations,
        "timing_note": "Each native process performs one sequential run; the internal Bend clock times simulation, framebuffer construction, and pixel checksums. Compilation, startup, text/PNG/MP4 encoding, and display are excluded.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("frames", "median_us", "checksum", "timed_heap_allocations")}))


if __name__ == "__main__":
    main()
