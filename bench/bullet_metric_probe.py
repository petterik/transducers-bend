#!/usr/bin/env python3
"""Compare bullet filter/map with and without carrying the distance."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCENE = ROOT / "bench/bullet_cathedral.bend"
MEASURED = """    X.comp3(X.map(~PixelSample, ~MeasuredPixel, ~measure_pixel),
      X.filter(~MeasuredPixel, ~covered_measured),
      X.map(~MeasuredPixel, ~Ink, ~pixel_ink_measured))),"""
REPEATED = """    X.comp2(X.filter(~PixelSample, ~covered),
      X.map(~PixelSample, ~Ink, ~pixel_ink))),"""


def run(*args):
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()


def timed(binary, frames):
    return tuple(map(int, run(binary, "--threads", 1, "--gpu", "off",
                              "--", frames, "bench", "x").split()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path, default=ROOT /
                        "bench/bullet-metric-probe-20260927.json")
    args = parser.parse_args()
    assert args.frames > 0 and args.sessions > 0
    source = SCENE.read_text()
    assert source.count(MEASURED) == 1
    assert source.count(REPEATED) == 1  # the drone pass remains unchanged
    with tempfile.TemporaryDirectory(prefix="bullet-metric-") as name:
        temp = Path(name)
        sources = {"measured_bullets": source,
                   "repeated_bullets": source.replace(MEASURED, REPEATED)}
        binaries = {}
        generated_hashes = {}
        checksums = {}
        for key, body in sources.items():
            # A temporary sibling retains the scene's relative Bend imports.
            with tempfile.NamedTemporaryFile(mode="w", dir=ROOT / "bench",
                                             prefix="bullet_metric_",
                                             suffix=".bend", delete=False) as file:
                file.write(body)
                scene = Path(file.name)
            try:
                generated = temp / f"{key}.c"
                binary = temp / key
                run("bun", ROOT.parent / "bend/bend2/main.ts", scene,
                    "-o", generated)
                run("clang", "-O3", generated, "-o", binary)
                generated_hashes[key] = hashlib.sha256(generated.read_bytes()).hexdigest()
                binaries[key] = binary
                checksums[key] = timed(binary, args.frames)[1]
            finally:
                scene.unlink(missing_ok=True)
        assert len(set(checksums.values())) == 1
        if args.frames == 120:
            assert next(iter(checksums.values())) == 367602200
        samples = {key: [] for key in binaries}
        orders = []
        for session in range(args.sessions):
            order = list(binaries)
            random.Random(20260928 + session).shuffle(order)
            orders.append(order)
            for key in order:
                elapsed, checksum = timed(binaries[key], args.frames)
                assert checksum == checksums[key]
                samples[key].append(elapsed)
        report = {
            "scope": "Same Bend scene with bounded fill and native CPU quotient; only the bullet pixel pipeline differs. Two separate clang -O3 binaries, 120 sequential frames and one CPU thread.",
            "frames": args.frames, "sessions": args.sessions,
            "scene_sha256": hashlib.sha256(SCENE.read_bytes()).hexdigest(),
            "compiler_comp_ts_sha256": hashlib.sha256((ROOT.parent /
                "bend/bend2/comp.ts").read_bytes()).hexdigest(),
            "generated_c_sha256": generated_hashes,
            "checksums": checksums, "orders": orders,
            "samples_us": samples,
            "median_us": {key: statistics.median(values)
                          for key, values in samples.items()},
        }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("checksums", "median_us")}))


if __name__ == "__main__":
    main()
