#!/usr/bin/env python3
"""Check and time CPU simulation plus spatially tiled CPU/Metal rendering."""

import argparse
import filecmp
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("512_4096", "bullet_cathedral_gpu.bend", "bullet_cathedral.bend", 119, 6),
    ("512_16384", "bullet_cathedral_gpu.bend", "bullet_cathedral.bend", 119, 7),
    ("4k_16384", "bullet_cathedral_gpu_4k.bend", "bullet_cathedral_4k_frames.bend", 119, 7),
    ("4k_65536", "bullet_cathedral_gpu_4k.bend", "bullet_cathedral_4k_frames.bend", 119, 8),
)


def run(command, env, stdout=None):
    result = subprocess.run([str(part) for part in command], cwd=ROOT, env=env,
                            stdout=stdout or subprocess.PIPE,
                            stderr=subprocess.PIPE, check=True, timeout=240)
    return result.stdout.decode().strip() if stdout is None else None


def compile_bend(source, binary, env):
    run(["bun", ROOT.parent / "bend/bend2/main.ts", ROOT / "bench" / source,
         "-o", binary], env)


def full_pixels_match(reference, tiled, frame, level, env, directory):
    original = directory / "original.txt"
    changed = directory / "tiled.txt"
    with original.open("wb") as stream:
        run([reference, "--threads", 1, "--gpu", "off", "--", frame, 0],
            env, stdout=stream)
    with changed.open("wb") as stream:
        run([tiled, "--threads", 1, "--gpu", "off", "--", frame, level],
            env, stdout=stream)
    if not filecmp.cmp(original, changed, shallow=False):
        raise AssertionError(f"pixel mismatch at frame {frame}")
    return original.stat().st_size


def measure(binary, thread_count, gpu, frame, level, count, expected, env):
    lines = run([binary, "--threads", thread_count, "--gpu", gpu, "--",
                 frame, level, 1 if gpu != "off" else 0, count + 1], env)
    values = [tuple(map(int, line.split())) for line in lines.splitlines()]
    if len(values) != count + 1 or any(len(row) != 4 for row in values):
        raise AssertionError(f"unexpected benchmark output: {lines[:200]}")
    if any(row[3] != expected for row in values):
        raise AssertionError("render checksum differs from reference")
    # The first dispatch in each process is a warmup; shader compilation is
    # already outside Bend's internal clock.
    return [dict(simulation_us=row[0], scene_us=row[1], draw_us=row[2])
            for row in values[1:]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--cpu-only", action="store_true")
    parser.add_argument("--skip-pixels", action="store_true")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "bench/bullet-gpu-comparison.json")
    args = parser.parse_args()
    if args.rounds < 1 or args.samples < 1:
        parser.error("--rounds and --samples must be positive")
    env = {**os.environ, "BEND_NO_TELEMETRY": "1",
           "CLANG_MODULE_CACHE_PATH": "/tmp/bend-clang-modules"}
    report = {
        "scope": "Single 512x512 or 3840x2160 frame, repeated in one process; first sample discarded. Internal Bend times separate simulation replay, CPU scene binning, and CPU/Metal draw plus synchronization. Compilation, image export, and display excluded.",
        "platform": platform.platform(),
        "compiler_commit": run(["git", "-C", ROOT.parent / "bend", "rev-parse", "HEAD"], env),
        "rounds": args.rounds, "samples_per_round": args.samples,
        "results": [],
    }
    with tempfile.TemporaryDirectory(prefix="bullet-gpu-compare-") as tmp:
        directory = Path(tmp)
        binaries = {}
        for _, source, reference, _, _ in CASES:
            for name in (source, reference):
                if name not in binaries:
                    binary = directory / name.removesuffix(".bend")
                    compile_bend(name, binary, env)
                    binaries[name] = binary
        for label, source, reference, frame, level in CASES:
            tiled = binaries[source]
            baseline = binaries[reference]
            checksum = int(run([baseline, "--threads", 1, "--gpu", "off",
                                "--", frame], env).split()[1])
            pixels = []
            if not args.skip_pixels and label == "512_16384":
                for check_frame in (0, 48, 119):
                    pixels.append({"frame": check_frame, "bytes":
                                   full_pixels_match(baseline, tiled,
                                                     check_frame, level, env,
                                                     directory)})
            if not args.skip_pixels and label == "4k_65536":
                pixels.append({"frame": 96, "bytes":
                               full_pixels_match(baseline, tiled, 96, level,
                                                 env, directory)})
            modes = [("cpu_1", 1, "off"), ("cpu_8", 8, "off")]
            if not args.cpu_only:
                modes.append(("metal", 1, "1GB"))
            samples = {name: [] for name, _, _ in modes}
            for round_number in range(args.rounds):
                order = list(modes)
                random.Random(2609 + round_number + level * 13).shuffle(order)
                for name, threads, gpu in order:
                    got = measure(tiled, threads, gpu, frame, level,
                                  args.samples, checksum, env)
                    samples[name].extend(got)
                    print(label, name, round_number + 1,
                          statistics.median(x["draw_us"] for x in got),
                          flush=True)
            medians = {name: {key: statistics.median(x[key] for x in rows)
                              for key in ("simulation_us", "scene_us", "draw_us")}
                       for name, rows in samples.items()}
            report["results"].append({
                "name": label, "frame": frame, "tile_depth": level,
                "tile_count": 1 << (2 * level), "reference_checksum": checksum,
                "full_pixel_checks": pixels,
                "source_sha256": hashlib.sha256((ROOT / "bench" / source).read_bytes()).hexdigest(),
                "samples": samples, "median_us": medians,
            })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
