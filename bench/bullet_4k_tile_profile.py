#!/usr/bin/env python3
"""Measure individual top and bottom 4K tile render times."""
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/bullet_4k_tile_profile.bend"
FRAMES = (7, 63, 96, 119)
SESSIONS = 12


def run(*args):
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout


def main():
    with tempfile.TemporaryDirectory(prefix="bullet-4k-tile-profile-") as tmp:
        generated = Path(tmp) / "profile.c"
        binary = Path(tmp) / "profile"
        run("bun", ROOT.parent / "bend/bend2/main.ts", SOURCE,
            "-o", generated)
        run("clang", "-O3", generated, "-o", binary)
        rng = random.Random(20260926)
        samples = {}
        checksums = {}
        for frame in FRAMES:
            by_tile = {"0": [], "1": []}
            by_checksum = {}
            for _ in range(SESSIONS):
                order = [0, 1]
                rng.shuffle(order)
                for tile in order:
                    output = run(binary, "--threads", 1, "--gpu", "off",
                                 "--", frame, tile)
                    micros, checksum = map(int, output.split())
                    by_tile[str(tile)].append(micros)
                    if str(tile) in by_checksum:
                        assert by_checksum[str(tile)] == checksum
                    by_checksum[str(tile)] = checksum
            samples[str(frame)] = by_tile
            checksums[str(frame)] = by_checksum
    medians = {frame: {tile: statistics.median(values)
                       for tile, values in by_tile.items()}
               for frame, by_tile in samples.items()}
    report = {
        "description": "Sequential isolated tile timing after world and pool setup",
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "renderer_sha256": hashlib.sha256(
            (ROOT / "bench/bullet_cathedral_4k_tiled16.bend").read_bytes()
        ).hexdigest(),
        "compiler_commit": run("git", "-C", ROOT.parent / "bend",
                               "rev-parse", "HEAD").strip(),
        "frames": FRAMES, "sessions": SESSIONS,
        "samples_us": samples, "medians_us": medians,
        "checksums": checksums,
        "timing_note": "One process per tile sample, one CPU thread, randomized top/bottom order. World simulation and bullet-pool construction occur before the Bend clock. Each timed call renders one 3840x1080 tile and computes its checksum.",
    }
    output = ROOT / "bench/bullet-4k-tile-profile.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(medians))


if __name__ == "__main__":
    main()
