#!/usr/bin/env python3
"""Reproduce the Julia-set checksum, CPU timings, and Bend-rendered PNG."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import struct
import subprocess
import tempfile
import zlib

from public_array_map_filter_sum import instrument_allocations, timed_allocations

ROOT = Path(__file__).resolve().parents[1]
BEND = ROOT / "bench/julia_showcase.bend"
MANUAL_C = ROOT / "bench/julia_showcase.c"
NAMES = ["fused", "direct", "pixel_list", "staged",
         "light_fused", "light_staged", "manual_c",
         "tiled_1", "tiled_2", "tiled_4", "tiled_8"]


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
    modes = {"fused": 0, "direct": 1, "pixel_list": 3,
             "staged": 8, "light_fused": 9, "light_staged": 10,
             "tiled_1": 4, "tiled_2": 4, "tiled_4": 4, "tiled_8": 4}
    threads = int(name.rsplit("_", 1)[1]) if name.startswith("tiled_") else 1
    return [bend_binary, "--threads", threads, "--gpu", "off",
            "--", modes[name], depth, frame]


def png_chunk(kind, payload):
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))


def write_gray_png(path, width, pixels):
    rows = bytearray()
    for y in range(width):
        rows.append(0)  # PNG filter: none
        rows.extend(min(255, p) for p in pixels[y * width:(y + 1) * width])
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, width, 8, 0, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + png_chunk(b"IEND", b""))


def light_checksum(depth):
    total = 0
    for pixel in range(1 << (2 * depth)):
        counts = []
        for sample_id in range(4 * pixel, 4 * pixel + 4):
            a = sample_id * 2654435761 & 0xFFFFFFFF
            b = a ^ (a >> 16)
            c = b * 2246822507 & 0xFFFFFFFF
            counts.append((c ^ (c >> 13)) & 31)
        shade = 2 * sum(counts)
        if shade >= 32:
            total = (total + shade) & 0xFFFFFFFF
    return total


def verify_image(bend_binary, c_binary, depth, frame, output, want):
    width = 1 << depth
    pixels = ast.literal_eval(run(bend_binary, "--threads", 1, "--gpu", "off",
                                  "--", 2, depth, frame))
    assert len(pixels) == width * width
    assert all(0 <= p <= 256 for p in pixels)
    assert sum(p for p in pixels if p >= 32) & 0xFFFFFFFF == want
    with tempfile.TemporaryDirectory(prefix="julia-image-") as directory:
        ppm = Path(directory) / "manual.ppm"
        _, c_want = timed([c_binary, depth, frame, ppm])
        assert c_want == want
        header = f"P6\n{width} {width}\n255\n".encode()
        data = ppm.read_bytes()
        assert data.startswith(header)
        rgb = data[len(header):]
        assert len(rgb) == width * width * 3
        assert all((min(255, p),) * 3 == tuple(rgb[3*i:3*i+3])
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
    with tempfile.TemporaryDirectory(prefix="julia-showcase-") as directory:
        temp = Path(directory)
        generated = temp / "bend.c"
        bend_binary = temp / "bend"
        c_binary = temp / "manual_c"
        run("bun", ROOT.parent / "bend/bend2/main.ts", BEND, "-o", generated)
        run("clang", "-O3", "-ffp-contract=off", generated, "-o", bend_binary)
        run("clang", "-O3", "-ffp-contract=off", MANUAL_C, "-o", c_binary)
        alloc_source = temp / "alloc.c"
        alloc_source.write_text(instrument_allocations(generated.read_text()))
        alloc_binary = temp / "alloc"
        run("clang", "-O3", "-ffp-contract=off", alloc_source, "-o", alloc_binary)
        report = {
            "scope": "Native CPU; IO microsecond timer encloses one frame kernel but excludes process startup, image output, and display",
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
            light_want = light_checksum(depth)
            commands = {name: command_for(name, bend_binary, c_binary,
                                          depth, args.frame) for name in NAMES}
            samples = {name: [] for name in NAMES}
            for session in range(args.sessions):
                order = list(NAMES)
                random.Random(20260926 + depth * 1000 + session).shuffle(order)
                for name in order:
                    elapsed, checksum = timed(commands[name])
                    expected = light_want if name.startswith("light_") else want
                    assert checksum == expected, (depth, name, checksum, expected)
                    samples[name].append(elapsed)
            allocs = {name: timed_allocations(alloc_binary, mode, depth,
                                              args.frame,
                                              light_want if name.startswith("light_") else want)
                      for name, mode in (("fused", 0), ("direct", 1),
                                         ("pixel_list", 3), ("staged", 8),
                                         ("light_fused", 9), ("light_staged", 10))}
            medians = {name: statistics.median(values)
                       for name, values in samples.items()}
            report["results"].append({
                "depth": depth, "width": width,
                "pixels": width * width, "samples": 4 * width * width,
                "checksum": want, "light_checksum": light_want,
                "samples_us": samples,
                "median_us": medians,
                "timed_bend_heap_alloc_calls": allocs,
            })
            print(depth, medians, allocs, flush=True)
        image_depth = args.image_depth
        image_want = timed([c_binary, image_depth, args.frame])[1]
        if args.image_output:
            args.image_output.parent.mkdir(parents=True, exist_ok=True)
            digest = verify_image(bend_binary, c_binary, image_depth,
                                  args.frame, args.image_output, image_want)
            report["image"] = {"path": str(args.image_output),
                               "depth": image_depth, "sha256": digest,
                               "pixel_parity": "all pixels match handwritten C"}
        if args.output:
            args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
