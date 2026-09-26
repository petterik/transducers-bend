#!/usr/bin/env python3
"""Measure the simulation portion of the three Bullet Cathedral layouts."""
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
    "generated": ROOT / "bench/bullet_cathedral.bend",
    "aos": ROOT / "bench/bullet_cathedral_aos.bend",
    "soa": ROOT / "bench/bullet_cathedral_soa.bend",
}
ORIGINAL = """run_frames(U32.to_nat(parsed_u32(U32.read(count))), 0,
            Held{initial(), Array.new(U32, 18n, 0)}, 0)"""
SIMULATION = """score_of(simulate(
            U32.to_nat(parsed_u32(U32.read(count))), 0, initial()))"""


def run(*args):
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True,
                          capture_output=True, text=True)


def timed(binary, frames):
    output = run(binary, "--threads", 1, "--gpu", "off", "--",
                 frames, "bench", "x")
    return tuple(map(int, output.stdout.split()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--pairs", type=int, default=21)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "bench/bullet-phase-comparison.json")
    args = parser.parse_args()
    assert args.frames > 0 and args.pairs > 0 and args.warmups >= 0

    temporary_sources = []
    try:
        with tempfile.TemporaryDirectory(prefix="bullet-phase-") as temp:
            directory = Path(temp)
            binaries = {}
            for name, source in SOURCES.items():
                original = source.read_text()
                assert original.count(ORIGINAL) == 1
                with tempfile.NamedTemporaryFile(mode="w", prefix=f"bullet_phase_{name}_",
                                                 suffix=".bend", dir=ROOT / "bench",
                                                 delete=False) as handle:
                    handle.write(original.replace(ORIGINAL, SIMULATION))
                    modified = Path(handle.name)
                temporary_sources.append(modified)
                generated = directory / f"{name}.c"
                binary = directory / name
                run("bun", ROOT.parent / "bend/bend2/main.ts", modified,
                    "-o", generated)
                run("clang", "-O3", generated, "-o", binary)
                binaries[name] = binary
            expected = timed(binaries["generated"], args.frames)[1]
            for _ in range(args.warmups):
                for binary in binaries.values():
                    assert timed(binary, args.frames)[1] == expected
            rng = random.Random(20260927)
            samples = {name: [] for name in SOURCES}
            orders = []
            for _ in range(args.pairs):
                order = list(SOURCES)
                rng.shuffle(order)
                orders.append(order)
                for name in order:
                    micros, score = timed(binaries[name], args.frames)
                    assert score == expected
                    samples[name].append(micros)
    finally:
        for modified in temporary_sources:
            modified.unlink(missing_ok=True)

    report = {
        "description": "Simulation-only timing from source-identical builds with the bench dispatch changed to score_of(simulate(...))",
        "sources_sha256": {name: hashlib.sha256(source.read_bytes()).hexdigest()
                           for name, source in SOURCES.items()},
        "frames": args.frames, "warmups_each": args.warmups,
        "random_seed": 20260927, "orders": orders,
        "samples_us": samples,
        "medians_us": {name: statistics.median(values)
                       for name, values in samples.items()},
        "final_accepted_hits": expected,
        "timing_note": "One CPU thread. Only simulation and collision resolution are timed; every framebuffer and pixel checksum is omitted from the bench dispatch. Compilation and process startup are excluded.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"medians_us": report["medians_us"],
                      "final_accepted_hits": expected}))


if __name__ == "__main__":
    main()
