#!/usr/bin/env python3
"""Measure whether Rust's inlined sprite loop explains its C lead."""
import argparse
import json
from pathlib import Path
import random
import statistics
import tempfile

from bullet_cathedral_cross_language import ROOT, RUST, command, sha

OLD = "fn draw_sprite(pixels: &mut [u32], s: Sprite) {"
NEW = "#[inline(never)]\nfn draw_sprite(pixels: &mut [u32], s: Sprite) {"


def timed(binary):
    elapsed, checksum = map(int, command(binary, "120", "new").split())
    assert checksum == 367602200, (binary, checksum)
    return elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "bench/bullet-rust-inline-sprite-probe-20260927.json")
    args = parser.parse_args()
    assert args.sessions > 0
    source = RUST.read_text()
    assert source.count(OLD) == 1
    with tempfile.TemporaryDirectory(prefix="bullet-rust-inline-") as name:
        temp = Path(name)
        variant = temp / "control_rust_noinline.rs"
        variant.write_text(source.replace(OLD, NEW))
        binaries = {"rust_original": temp / "rust_original",
                    "rust_noinline": temp / "rust_noinline"}
        for label, rust_source in (("rust_original", RUST),
                                   ("rust_noinline", variant)):
            command("rustc", "-C", "opt-level=3", "-C", "target-cpu=native",
                    rust_source, "-o", binaries[label])
        assert command(binaries["rust_original"], "120", "frames") == command(
            binaries["rust_noinline"], "120", "frames")
        for binary in binaries.values():
            timed(binary)
        samples = {label: [] for label in binaries}
        for session in range(args.sessions):
            order = list(binaries)
            random.Random(20260927 + session).shuffle(order)
            for label in order:
                samples[label].append(timed(binaries[label]))
        report = {
            "scope": "120 sequential 512x512 frames, one CPU thread, fresh framebuffer; same Rust scene except inline(never) on draw_sprite; all per-frame outputs equal",
            "sessions": args.sessions,
            "compiler_flags": "rustc -C opt-level=3 -C target-cpu=native",
            "source_sha256": sha(RUST),
            "variant_sha256": sha(variant),
            "samples_us": samples,
            "median_us": {label: statistics.median(values)
                          for label, values in samples.items()},
        }
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report["median_us"]))


if __name__ == "__main__":
    main()
