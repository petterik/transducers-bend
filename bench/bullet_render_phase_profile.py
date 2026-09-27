#!/usr/bin/env python3
"""Measure cumulative Bullet Cathedral render stages on one CPU thread."""

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
SOURCE = ROOT / "bench/bullet_cathedral.bend"
START = "def draw_frame(world: Damage, +frame: U32) -> Array<U32>:\n"
END = "def rendered(+frame: U32) -> Array<U32>:\n"
STAGES = {
    "background": [],
    "bullets": ["bullets"],
    "drones": ["bullets", "drones"],
    "hits": ["bullets", "drones", "hits"],
    "icons": ["bullets", "drones", "hits", "icons"],
    "hud": ["bullets", "drones", "hits", "icons", "hud"],
}
LINES = {
    "bullets": "bullets_image = draw_bullets(background(), frame)",
    "drones": "drones_image = draw_drones(bullets_image, health, frame)",
    "hits": "hits_image = draw_hits(drones_image, accepted, frame)",
    "icons": "icons_image = draw_sprites(hits_image, icons(frame, score, player_hp))",
    "hud": "draw_hud(icons_image, score, player_hp)",
}
VALUES = {"background": "background()", "bullets": "bullets_image",
          "drones": "drones_image", "hits": "hits_image",
          "icons": "icons_image", "hud": None}


def command(*args):
    return subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True,
                          capture_output=True, text=True)


def variant(source, name):
    assert source.count(START) == source.count(END) == 1
    begin = source.index(START)
    end = source.index(END, begin)
    steps = STAGES[name]
    body = [START, "  match world:\n",
            "    case Damage{health, +score, +player_hp, accepted}:\n"]
    for step in steps:
        body.append("      " + LINES[step] + "\n")
    if name != "hud":
        body.append("      " + VALUES[name] + "\n")
    body.append("\n")
    return source[:begin] + "".join(body) + source[end:]


def timed(binary, frames):
    result = command(binary, "--threads", 1, "--gpu", "off", "--",
                     frames, "bench", "x")
    elapsed, checksum = map(int, result.stdout.split())
    return elapsed, checksum, result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path, default=ROOT /
                        "bench/bullet-render-phase-20260927.json")
    args = parser.parse_args()
    assert args.frames > 0 and args.sessions > 0
    source = SOURCE.read_text()
    temporary_sources = []
    try:
        with tempfile.TemporaryDirectory(prefix="bullet-render-") as temp_name:
            temp = Path(temp_name)
            binaries = {}
            allocations = {}
            checksums = {}
            for name in STAGES:
                with tempfile.NamedTemporaryFile(mode="w", prefix=f"bullet_render_{name}_",
                                                 suffix=".bend", dir=ROOT / "bench",
                                                 delete=False) as handle:
                    handle.write(variant(source, name))
                    modified = Path(handle.name)
                temporary_sources.append(modified)
                generated = temp / f"{name}.c"
                binary = temp / name
                alloc_c = temp / f"{name}_alloc.c"
                alloc_binary = temp / f"{name}_alloc"
                command("bun", ROOT.parent / "bend/bend2/main.ts", modified,
                        "-o", generated)
                command("clang", "-O3", generated, "-o", binary)
                alloc_c.write_text(instrument_allocations(generated.read_text()))
                command("clang", "-O3", alloc_c, "-o", alloc_binary)
                binaries[name] = binary
                checksums[name] = timed(binary, args.frames)[1]
                _, checksum, stderr = timed(alloc_binary, args.frames)
                assert checksum == checksums[name]
                match = re.search(r"TIMED_ALLOC (\d+) (\d+)", stderr)
                assert match and int(match.group(2)) == 2
                allocations[name] = int(match.group(1))
            assert checksums["hud"] == 367602200 if args.frames == 120 else True
            samples = {name: [] for name in STAGES}
            orders = []
            for session in range(args.sessions):
                order = list(STAGES)
                random.Random(20260927 + session).shuffle(order)
                orders.append(order)
                for name in order:
                    elapsed, checksum, _ = timed(binaries[name], args.frames)
                    assert checksum == checksums[name]
                    samples[name].append(elapsed)
    finally:
        for modified in temporary_sources:
            modified.unlink(missing_ok=True)
    report = {
        "scope": "Cumulative render stages; each separately compiled program runs the same sequential simulation, then each frame builds the selected layers and checksums its framebuffer. One native CPU thread; process startup excluded. Differences between medians are indicative, not isolated within one executable.",
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "compiler_commit": command("git", "-C", ROOT.parent / "bend",
                                   "rev-parse", "HEAD").stdout.strip(),
        "frames": args.frames, "sessions": args.sessions,
        "orders": orders, "checksums": checksums,
        "timed_heap_allocations": allocations,
        "samples_us": samples,
        "median_us": {name: statistics.median(values)
                      for name, values in samples.items()},
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("checksums", "timed_heap_allocations", "median_us")}))


if __name__ == "__main__":
    main()
