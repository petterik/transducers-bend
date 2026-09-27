#!/usr/bin/env python3
"""Measure the cost of Clang leaving the C sprite loop outlined."""
import argparse
import json
from pathlib import Path
import random
import statistics
import tempfile

from bullet_cathedral_cross_language import C, ROOT, RUST, command, sha

OLD = "static void draw_sprite(uint32_t *pixels, Sprite s) {"
NEW = "__attribute__((always_inline)) static inline void draw_sprite(uint32_t *pixels, Sprite s) {"


def timed(binary):
    elapsed, checksum = map(int, command(binary, "120", "new").split())
    assert checksum == 367602200, (binary, checksum)
    return elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "bench/bullet-c-inline-sprite-probe-20260927.json")
    args = parser.parse_args()
    assert args.sessions > 0
    source = C.read_text()
    assert source.count(OLD) == 1
    with tempfile.TemporaryDirectory(prefix="bullet-c-inline-") as name:
        temp = Path(name)
        variant = temp / "control_c_inline.c"
        variant.write_text(source.replace(OLD, NEW))
        binaries = {"c_original": temp / "c_original",
                    "c_inline": temp / "c_inline",
                    "rust": temp / "rust"}
        command("clang", "-O3", "-ffp-contract=off", C,
                "-o", binaries["c_original"])
        command("clang", "-O3", "-ffp-contract=off", variant,
                "-o", binaries["c_inline"])
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
            "scope": "120 sequential 512x512 frames, one CPU thread, fresh framebuffer; same C scene except always_inline on draw_sprite; same per-frame checksums, scores, and shield as C and Rust",
            "sessions": args.sessions,
            "compiler_flags": {"c": "clang -O3 -ffp-contract=off",
                               "rust": "rustc -C opt-level=3 -C target-cpu=native"},
            "sources_sha256": {path.name: sha(path) for path in (C, RUST)},
            "c_variant_sha256": sha(variant),
            "samples_us": samples,
            "median_us": {label: statistics.median(values)
                          for label, values in samples.items()},
        }
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report["median_us"]))


if __name__ == "__main__":
    main()
