#!/usr/bin/env python3
"""Benchmark the transformation-heavy starfield and verify its rendered pixels."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import subprocess
import tempfile

from julia_showcase import write_gray_png
from public_array_map_filter_sum import instrument_allocations, timed_allocations

ROOT = Path(__file__).resolve().parents[1]
BEND = ROOT / "bench/starfield_showcase.bend"
MANUAL_C = ROOT / "bench/starfield_showcase.c"
NAMES = ["fused", "direct", "pixel_list", "list_staged",
         "vec_staged", "manual_c", "tiled_1", "tiled_2", "tiled_4", "tiled_8"]
MODES = {"fused": 0, "direct": 1, "pixel_list": 3,
         "list_staged": 4, "vec_staged": 5}


def run(*args):
    result = subprocess.run([str(a) for a in args], cwd=ROOT, check=True,
                            capture_output=True, text=True)
    return result.stdout.strip()


def timed(command):
    elapsed, checksum = map(int, run(*command).split())
    return elapsed, checksum


def command_for(name, bend_binary, c_binary, depth, frame):
    if name == "manual_c":
        return [c_binary, depth, frame]
    if name.startswith("tiled_"):
        return [bend_binary, "--threads", int(name.rsplit("_", 1)[1]),
                "--gpu", "off", "--", 6, depth, frame]
    return [bend_binary, "--threads", 1, "--gpu", "off", "--",
            MODES[name], depth, frame]


def verify_image(bend_binary, c_binary, depth, frame, output, want):
    width = 1 << depth
    pixels = ast.literal_eval(run(bend_binary, "--threads", 1, "--gpu", "off",
                                  "--", 2, depth, frame))
    assert len(pixels) == width * width
    assert all(0 <= p <= 255 for p in pixels)
    assert sum(pixels) & 0xFFFFFFFF == want
    with tempfile.TemporaryDirectory(prefix="starfield-image-") as directory:
        ppm = Path(directory) / "manual.ppm"
        _, c_want = timed([c_binary, depth, frame, ppm])
        assert c_want == want
        header = f"P6\n{width} {width}\n255\n".encode()
        data = ppm.read_bytes()
        assert data.startswith(header)
        rgb = data[len(header):]
        assert len(rgb) == width * width * 3
        assert all((p,) * 3 == tuple(rgb[3*i:3*i+3])
                   for i, p in enumerate(pixels))
    write_gray_png(output, width, pixels)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depths", type=int, nargs="+", default=[7, 8, 9])
    parser.add_argument("--sessions", type=int, default=20)
    parser.add_argument("--frame", type=int, default=0)
    parser.add_argument("--image-depth", type=int, default=8)
    parser.add_argument("--image-output", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    assert args.sessions > 0 and 0 <= args.frame <= 10000
    assert all(6 <= d <= 10 for d in args.depths)
    assert 6 <= args.image_depth <= 9

    with tempfile.TemporaryDirectory(prefix="starfield-showcase-") as directory:
        temp = Path(directory)
        generated = temp / "bend.c"
        bend_binary = temp / "bend"
        c_binary = temp / "manual_c"
        run("bun", ROOT.parent / "bend/bend2/main.ts", BEND, "-o", generated)
        run("clang", "-O3", generated, "-o", bend_binary)
        run("clang", "-O3", MANUAL_C, "-o", c_binary)
        alloc_c = temp / "alloc.c"
        alloc_c.write_text(instrument_allocations(generated.read_text()))
        alloc_binary = temp / "alloc"
        run("clang", "-O3", alloc_c, "-o", alloc_binary)
        report = {
            "scope": "Native CPU; timer includes one frame kernel and allocations, excludes process startup, image output, and display",
            "compiler_commit": run("git", "-C", ROOT.parent / "bend", "rev-parse", "HEAD"),
            "library_commit": run("git", "rev-parse", "HEAD"),
            "fixture_sha256": hashlib.sha256(BEND.read_bytes()).hexdigest(),
            "manual_c_sha256": hashlib.sha256(MANUAL_C.read_bytes()).hexdigest(),
            "platform": platform.platform(),
            "clang": run("clang", "--version").splitlines()[0],
            "frame": args.frame,
            "sessions": args.sessions,
            "results": [],
        }
        for depth in args.depths:
            width = 1 << depth
            want = timed([c_binary, depth, args.frame])[1]
            commands = {name: command_for(name, bend_binary, c_binary,
                                          depth, args.frame) for name in NAMES}
            samples = {name: [] for name in NAMES}
            for session in range(args.sessions):
                order = list(NAMES)
                random.Random(20260926 + depth * 1000 + session).shuffle(order)
                for name in order:
                    elapsed, checksum = timed(commands[name])
                    assert checksum == want, (depth, name, checksum, want)
                    samples[name].append(elapsed)
            allocs = {name: timed_allocations(alloc_binary, mode, depth,
                                              args.frame, want)
                      for name, mode in MODES.items()}
            medians = {name: statistics.median(values)
                       for name, values in samples.items()}
            report["results"].append({
                "depth": depth, "width": width, "pixels": width * width,
                "samples": 4 * width * width, "checksum": want,
                "samples_us": samples, "median_us": medians,
                "timed_bend_heap_alloc_calls": allocs,
            })
            print(depth, medians, allocs, flush=True)
        if args.image_output:
            args.image_output.parent.mkdir(parents=True, exist_ok=True)
            image_want = timed([c_binary, args.image_depth, args.frame])[1]
            digest = verify_image(bend_binary, c_binary, args.image_depth,
                                  args.frame, args.image_output, image_want)
            report["image"] = {"path": str(args.image_output),
                               "depth": args.image_depth, "sha256": digest,
                               "pixel_parity": "all pixels match handwritten C"}
        if args.output:
            args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
