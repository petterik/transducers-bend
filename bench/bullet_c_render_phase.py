#!/usr/bin/env python3
"""Measure cumulative render stages in the handwritten C control."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/bullet_cathedral_control.c"
START = "static uint32_t render(World *world, uint32_t frame, uint32_t *pixels) {"
END = "\nint main(int argc, char **argv) {"
CUTS = {
    "background": "  uint32_t begin = (frame - umin(frame, 95)) * 128;",
    "bullets": "  for (uint32_t i = 0; i < CELLS; ++i) {",
    "drones": "  for (size_t n = world->accepted_len; n > 0; --n) {",
    "hits": "  uint32_t core = world->score >= 192 ? 16727887 : 16759065;",
    "icons": "  for (uint32_t i = 0; i < 6144; ++i) {",
}


def command(*args):
    return subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True,
                          capture_output=True, text=True)


def variant(source, name):
    if name == "hud":
        return source
    assert source.count(START) == source.count(END) == 1
    begin = source.index(START)
    end = source.index(END, begin)
    render = source[begin:end]
    assert render.count(CUTS[name]) == 1
    head = render[:render.index(CUTS[name])]
    if name == "background":
        head = head.replace(START, START + "\n  (void)world; (void)frame;", 1)
    replacement = head + """  uint32_t checksum = 0;
  for (uint32_t i = 0; i < PIXELS; ++i) checksum += pixels[i];
  return checksum;
}
"""
    return source[:begin] + replacement + source[end:]


def timed(binary, frames):
    elapsed, checksum = map(int, command(binary, frames, "new").stdout.split())
    return elapsed, checksum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path, default=ROOT /
                        "bench/bullet-c-render-phase-20260927.json")
    args = parser.parse_args()
    assert args.frames > 0 and args.sessions > 0
    source = SOURCE.read_text()
    names = [*CUTS, "hud"]
    with tempfile.TemporaryDirectory(prefix="bullet-c-phase-") as temp_name:
        temp = Path(temp_name)
        binaries = {}
        checksums = {}
        for name in names:
            file = temp / f"{name}.c"
            file.write_text(variant(source, name))
            binary = temp / name
            command("clang", "-O3", "-ffp-contract=off", file, "-o", binary)
            binaries[name] = binary
            checksums[name] = timed(binary, args.frames)[1]
        if args.frames == 120:
            assert checksums == {
                "background": 2226259136, "bullets": 2774171692,
                "drones": 2412871340, "hits": 4241134454,
                "icons": 3520524107, "hud": 367602200,
            }, checksums
        samples = {name: [] for name in names}
        orders = []
        for session in range(args.sessions):
            order = names.copy()
            random.Random(20260928 + session).shuffle(order)
            orders.append(order)
            for name in order:
                elapsed, checksum = timed(binaries[name], args.frames)
                assert checksum == checksums[name]
                samples[name].append(elapsed)
    report = {
        "scope": "Cumulative C render stages, same sequential simulation and fresh framebuffer each frame, one native CPU thread. Each stage is separately compiled; differences between medians are indicative. Process startup excluded.",
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "frames": args.frames, "sessions": args.sessions,
        "orders": orders, "checksums": checksums,
        "samples_us": samples,
        "median_us": {name: statistics.median(values)
                      for name, values in samples.items()},
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"checksums": checksums, "median_us": report["median_us"]}))


if __name__ == "__main__":
    main()
