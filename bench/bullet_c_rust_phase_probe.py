#!/usr/bin/env python3
"""Compare matching cumulative C and Rust render prefixes in paired sessions."""
import argparse
import json
from pathlib import Path
import random
import statistics
import tempfile

from bullet_c_render_phase import CUTS, variant as c_variant
from bullet_cathedral_cross_language import C, ROOT, RUST, command, sha

RUST_START = "fn render(world: &World, frame: u32, pixels: &mut [u32]) -> u32 {"
RUST_END = "\npub fn main() {"
RUST_CUTS = {
    "background": "    let begin = (frame - frame.min(95)) * 128;",
    "bullets": "    for i in 0..CELLS {",
    "drones": "    for h in world.accepted.iter().rev() {",
    "hits": "    let core = if world.score >= 192 {16727887} else {16759065};",
    "icons": "    for i in 0u32..6144 {",
}
CHECKSUMS = {
    "background": 2226259136, "bullets": 2774171692,
    "drones": 2412871340, "hits": 4241134454,
    "icons": 3520524107, "hud": 367602200,
}


def rust_variant(source, name):
    if name == "hud":
        return source
    assert source.count(RUST_START) == source.count(RUST_END) == 1
    begin = source.index(RUST_START)
    end = source.index(RUST_END, begin)
    render = source[begin:end]
    assert render.count(RUST_CUTS[name]) == 1
    head = render[:render.index(RUST_CUTS[name])]
    replacement = head + "    pixels.iter().copied().fold(0u32, u32::wrapping_add)\n}\n"
    return source[:begin] + replacement + source[end:]


def timed(binary, expected):
    elapsed, checksum = map(int, command(binary, "120", "new").split())
    assert checksum == expected, (binary, checksum, expected)
    return elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "bench/bullet-c-rust-phase-probe-20260927.json")
    args = parser.parse_args()
    assert args.sessions > 0
    with tempfile.TemporaryDirectory(prefix="bullet-c-rust-phase-") as name:
        temp = Path(name)
        commands = {}
        for phase in [*CUTS, "hud"]:
            c_source = temp / f"c_{phase}.c"
            rust_source = temp / f"rust_{phase}.rs"
            c_bin = temp / f"c_{phase}"
            rust_bin = temp / f"rust_{phase}"
            c_source.write_text(c_variant(C.read_text(), phase))
            rust_source.write_text(rust_variant(RUST.read_text(), phase))
            command("clang", "-O3", "-ffp-contract=off", c_source, "-o", c_bin)
            command("rustc", "-C", "opt-level=3", "-C", "target-cpu=native",
                    rust_source, "-o", rust_bin)
            commands[f"c_{phase}"] = (c_bin, CHECKSUMS[phase])
            commands[f"rust_{phase}"] = (rust_bin, CHECKSUMS[phase])
        for binary, expected in commands.values():
            timed(binary, expected)
        samples = {label: [] for label in commands}
        for session in range(args.sessions):
            order = list(commands)
            random.Random(20260927 + session).shuffle(order)
            for label in order:
                binary, expected = commands[label]
                samples[label].append(timed(binary, expected))
        report = {
            "scope": "Cumulative render prefixes, 120 sequential 512x512 frames, one CPU thread, fresh framebuffer; each prefix separately compiled; pairwise comparisons indicate scale but prefix subtraction is not isolated stage timing",
            "sessions": args.sessions,
            "checksums": CHECKSUMS,
            "compiler_flags": {"c": "clang -O3 -ffp-contract=off",
                               "rust": "rustc -C opt-level=3 -C target-cpu=native"},
            "sources_sha256": {path.name: sha(path) for path in (C, RUST)},
            "samples_us": samples,
            "median_us": {label: statistics.median(values)
                          for label, values in samples.items()},
        }
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report["median_us"]))


if __name__ == "__main__":
    main()
