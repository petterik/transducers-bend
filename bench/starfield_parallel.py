#!/usr/bin/env python3
"""Benchmark warmed starfield frames on CPU threads and the native GPU."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BEND = ROOT / "bench/starfield_showcase.bend"
MANUAL_C = ROOT / "bench/starfield_showcase.c"
MODES = {
    "cpu_serial": (0, 1, "off"),
    "cpu_tiled_1": (6, 1, "off"),
    "cpu_tiled_2": (6, 2, "off"),
    "cpu_tiled_4": (6, 4, "off"),
    "cpu_tiled_8": (6, 8, "off"),
    "gpu_tiles_64": (8, 1, "1GB"),
    "gpu_tiles_1024": (9, 1, "1GB"),
    "gpu_tiles_4096": (7, 1, "1GB"),
}


def run(command, env=None):
    result = subprocess.run([str(x) for x in command], cwd=ROOT,
                            env=env, capture_output=True, text=True,
                            check=True, timeout=240)
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depths", type=int, nargs="+", default=[8, 9])
    parser.add_argument("--sessions", type=int, default=12)
    parser.add_argument("--repeat", type=int, default=8)
    parser.add_argument("--frame", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    assert args.sessions > 0 and args.repeat > 0
    assert all(6 <= depth <= 10 for depth in args.depths)
    assert 0 <= args.frame <= 10000
    report = {
        "scope": "Warm one frame outside each timed sample; then compute distinct consecutive frames in one process. Times include GPU dispatch and cleanup, but exclude process startup, shader compilation, image output, and display.",
        "compiler_commit": run(["git", "-C", ROOT.parent / "bend", "rev-parse", "HEAD"]),
        "library_commit": run(["git", "rev-parse", "HEAD"]),
        "fixture_sha256": hashlib.sha256(BEND.read_bytes()).hexdigest(),
        "manual_c_sha256": hashlib.sha256(MANUAL_C.read_bytes()).hexdigest(),
        "platform": platform.platform(),
        "sessions": args.sessions, "frames_per_session": args.repeat,
        "first_frame": args.frame, "results": [],
    }
    with tempfile.TemporaryDirectory(prefix="starfield-parallel-") as directory:
        temp = Path(directory)
        binary = temp / "bend"
        c_binary = temp / "manual_c"
        env = {**os.environ,
               "CLANG_MODULE_CACHE_PATH": "/tmp/bend-clang-modules",
               "BEND_NO_TELEMETRY": "1"}
        run(["bun", ROOT.parent / "bend/bend2/main.ts", BEND, "-o", binary], env)
        run(["clang", "-O3", MANUAL_C, "-o", c_binary])
        for depth in args.depths:
            frames = [args.frame + i for i in range(args.sessions * (args.repeat + 1))]
            expected = {frame: int(run([c_binary, depth, frame]).split()[1])
                        for frame in frames}
            samples = {}
            for name, (mode, threads, gpu) in MODES.items():
                output = run([binary, "--threads", threads, "--gpu", gpu,
                              "--", mode, depth, args.frame,
                              args.repeat, args.sessions], env)
                lines = [tuple(map(int, line.split()))
                         for line in output.splitlines()]
                assert len(lines) == args.sessions, (name, len(lines))
                timings = []
                for i, (elapsed, checksum, warm) in enumerate(lines):
                    first = args.frame + i * (args.repeat + 1)
                    want = sum(expected[j] for j in
                               range(first + 1, first + args.repeat + 1)) & 0xFFFFFFFF
                    assert warm == expected[first], (name, depth, i, "warm")
                    assert checksum == want, (name, depth, i, checksum, want)
                    timings.append(elapsed / args.repeat)
                samples[name] = timings
                print(depth, name, statistics.median(timings), flush=True)
            report["results"].append({
                "depth": depth, "width": 1 << depth,
                "pixels_per_frame": 1 << (2 * depth),
                "samples_per_frame": 1 << (2 * depth + 2),
                "samples_us_per_frame": samples,
                "median_us_per_frame": {name: statistics.median(v)
                                        for name, v in samples.items()},
                "first_warm_checksum": expected[args.frame],
            })
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
