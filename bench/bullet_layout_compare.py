#!/usr/bin/env python3
"""Compare generated bullets with a per-frame structure-of-arrays pool."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import statistics
import subprocess
import tempfile

from public_array_map_filter_sum import instrument_allocations

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "generated": ROOT / "bench/bullet_cathedral.bend",
    "aos": ROOT / "bench/bullet_cathedral_aos.bend",
    "soa": ROOT / "bench/bullet_cathedral_soa.bend",
}


def run(*args):
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True,
                          capture_output=True, text=True)


def build(source, directory):
    generated = directory / f"{source.stem}.c"
    binary = directory / source.stem
    alloc_source = directory / f"{source.stem}_alloc.c"
    alloc_binary = directory / f"{source.stem}_alloc"
    run("bun", ROOT.parent / "bend/bend2/main.ts", source, "-o", generated)
    run("clang", "-O3", generated, "-o", binary)
    alloc_source.write_text(instrument_allocations(generated.read_text()))
    run("clang", "-O3", alloc_source, "-o", alloc_binary)
    return binary, alloc_binary


def timed(binary, frames):
    output = run(binary, "--threads", 1, "--gpu", "off", "--",
                 frames, "bench", "x")
    micros, checksum = map(int, output.stdout.split())
    return micros, checksum, output.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--pairs", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "bench/bullet-layout-comparison.json")
    args = parser.parse_args()
    assert args.frames > 0 and args.pairs > 0 and args.warmups >= 0
    reference = json.loads((ROOT / "bench/bullet-cathedral-report.json").read_text())
    assert args.frames <= len(reference["frame_checksums"])
    expected = sum(reference["frame_checksums"][:args.frames]) & 0xFFFFFFFF

    with tempfile.TemporaryDirectory(prefix="bullet-layout-") as temp:
        directory = Path(temp)
        binaries = {name: build(source, directory)
                    for name, source in SOURCES.items()}
        # Check every rendered frame in both materialized layouts.
        for name in ("aos", "soa"):
            for frame in range(args.frames):
                output = run(binaries[name][0], "--threads", 1,
                             "--gpu", "off", "--", frame).stdout.split()
                assert int(output[1]) == reference["frame_checksums"][frame], (
                    name, frame)
        samples = {name: [] for name in SOURCES}
        for _ in range(args.warmups):
            for name in SOURCES:
                assert timed(binaries[name][0], args.frames)[1] == expected
        rng = random.Random(20260926)
        orders = []
        for _ in range(args.pairs):
            order = list(SOURCES)
            rng.shuffle(order)
            orders.append(order)
            for name in order:
                micros, checksum, _ = timed(binaries[name][0], args.frames)
                assert checksum == expected, (name, checksum, expected)
                samples[name].append(micros)
        allocations = {}
        for name in SOURCES:
            _, checksum, stderr = timed(binaries[name][1], args.frames)
            assert checksum == expected
            match = re.search(r"TIMED_ALLOC (\d+) (\d+)", stderr)
            assert match and int(match.group(2)) == 2, stderr
            allocations[name] = int(match.group(1))

    paired_deltas = [a - b for a, b in
                     zip(samples["generated"], samples["soa"])]
    aos_minus_soa = [a - b for a, b in
                     zip(samples["aos"], samples["soa"])]
    report = {
        "description": "Generated bullet records versus stored array of records versus seven flat field arrays per frame; full sequential simulation and rendering",
        "compiler_commit": run("git", "-C", ROOT.parent / "bend",
                               "rev-parse", "HEAD").stdout.strip(),
        "sources_sha256": {name: hashlib.sha256(source.read_bytes()).hexdigest()
                           for name, source in SOURCES.items()},
        "frames": args.frames, "warmups_each": args.warmups,
        "random_seed": 20260926, "orders": orders,
        "samples_us": samples,
        "medians_us": {name: statistics.median(values)
                       for name, values in samples.items()},
        "paired_generated_minus_soa_us": paired_deltas,
        "median_paired_delta_us": statistics.median(paired_deltas),
        "paired_aos_minus_soa_us": aos_minus_soa,
        "median_paired_aos_minus_soa_us": statistics.median(aos_minus_soa),
        "checksum": expected,
        "verified_frame_checksums_per_materialized_layout": args.frames,
        "timed_heap_allocations": allocations,
        "timing_note": "One CPU thread. Each process times 120 sequential simulations, full RGB framebuffers, and pixel checksums internally. Compile, startup, export, and display are excluded. Paired orders are randomized.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("medians_us", "median_paired_delta_us",
                       "median_paired_aos_minus_soa_us", "timed_heap_allocations",
                       "verified_frame_checksums_per_materialized_layout")}))


if __name__ == "__main__":
    main()
