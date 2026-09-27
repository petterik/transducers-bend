#!/usr/bin/env python3
"""Probe C sprite specialization for only the fixed-radius bullet and drone passes."""
import argparse
import json
from pathlib import Path
import random
import statistics
import tempfile

from bullet_cathedral_cross_language import C, ROOT, RUST, command, sha

START = "static void draw_sprite(uint32_t *pixels, Sprite s) {"
END = "static uint32_t sky(uint32_t index) {"
BULLET_CALL = "draw_sprite(pixels, (Sprite){b.x, b.y, 4, b.color});"
DRONE_CALL = "draw_sprite(pixels, (Sprite){enemy_x(frame, cx, cy),"


def variant(source):
    assert source.count(START) == source.count(END) == 1
    assert source.count(BULLET_CALL) == source.count(DRONE_CALL) == 1
    begin = source.index(START)
    end = source.index(END, begin)
    body = source[begin:end]
    extra = []
    for radius in (4, 8):
        extra.append(body.replace(START,
            f"__attribute__((always_inline)) static inline void draw_sprite_fixed_{radius}(uint32_t *pixels, Sprite s) {{", 1)
            .replace("s.radius", str(radius)))
    source = source[:end] + "\n".join(extra) + source[end:]
    source = source.replace(BULLET_CALL,
        "draw_sprite_fixed_4(pixels, (Sprite){b.x, b.y, 4, b.color});")
    source = source.replace(DRONE_CALL,
        "draw_sprite_fixed_8(pixels, (Sprite){enemy_x(frame, cx, cy),")
    return source


def timed(binary):
    elapsed, checksum = map(int, command(binary, "120", "new").split())
    assert checksum == 367602200, (binary, checksum)
    return elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "bench/bullet-c-fixed-sprite-probe-20260927.json")
    args = parser.parse_args()
    assert args.sessions > 0
    with tempfile.TemporaryDirectory(prefix="bullet-c-fixed-") as name:
        temp = Path(name)
        modified = temp / "control_c_fixed.c"
        modified.write_text(variant(C.read_text()))
        binaries = {"c_original": temp / "c_original",
                    "c_fixed": temp / "c_fixed", "rust": temp / "rust"}
        command("clang", "-O3", "-ffp-contract=off", C,
                "-o", binaries["c_original"])
        command("clang", "-O3", "-ffp-contract=off", modified,
                "-o", binaries["c_fixed"])
        command("rustc", "-C", "opt-level=3", "-C", "target-cpu=native",
                RUST, "-o", binaries["rust"])
        frames = [command(binary, "120", "frames") for binary in binaries.values()]
        assert frames[0] == frames[1] == frames[2]
        for binary in binaries.values():
            timed(binary)
        samples = {label: [] for label in binaries}
        for session in range(args.sessions):
            order = list(binaries)
            random.Random(20260927 + session).shuffle(order)
            for label in order:
                samples[label].append(timed(binaries[label]))
        report = {
            "scope": "120 sequential 512x512 frames, one CPU thread, fresh framebuffer; C has duplicate fixed-radius inline sprite loops for bullet radius 4 and drone radius 8, but all per-frame outputs match",
            "sessions": args.sessions,
            "compiler_flags": {"c": "clang -O3 -ffp-contract=off",
                               "rust": "rustc -C opt-level=3 -C target-cpu=native"},
            "sources_sha256": {path.name: sha(path) for path in (C, RUST)},
            "c_variant_sha256": sha(modified),
            "samples_us": samples,
            "median_us": {label: statistics.median(values)
                          for label, values in samples.items()},
        }
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report["median_us"]))


if __name__ == "__main__":
    main()
