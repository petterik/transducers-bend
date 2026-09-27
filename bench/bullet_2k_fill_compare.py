#!/usr/bin/env python3
"""Compare the 2K transducer sky with bounded Array.fill.prefix."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCENE = ROOT / "bench/bullet_cathedral_2k_frames.bend"
NEW = """def sky_color_after(ink: Ink) -> U32:
  match ink:
    case Ink{index, color}: color

def sky_color(index: U32) -> U32:
  sky_color_after(sky(index))

def background() -> Array<U32>:
  Array.fill.prefix(~U32, ~sky_color, 2073600,
    Array.new(U32, 21n, 0))
"""
OLD = """def background() -> Array<U32>:
  X.transduce(X.map(~U32, ~Ink, ~sky_at), ink_rf(),
    Array.new(U32, 21n, 0), T.range(2073600))
"""


def run(*args):
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()


def timed(binary, frames):
    return tuple(map(int, run(binary, "--threads", 1, "--gpu", "off",
                              "--", frames, "bench", "x").split()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path, default=ROOT /
                        "bench/bullet-2k-fill-comparison-20260927.json")
    args = parser.parse_args()
    assert args.frames > 0 and args.sessions > 0
    current = SCENE.read_text()
    assert current.count(NEW) == 1
    sources = {"transducer_sky": current.replace(NEW, OLD),
               "bounded_prefix_fill": current}
    with tempfile.TemporaryDirectory(prefix="bullet-2k-fill-") as name:
        temp = Path(name)
        binaries = {}
        generated_hashes = {}
        for key, body in sources.items():
            with tempfile.NamedTemporaryFile(mode="w", dir=ROOT / "bench",
                                             prefix="bullet_2k_fill_",
                                             suffix=".bend", delete=False) as file:
                file.write(body)
                scene = Path(file.name)
            try:
                generated = temp / f"{key}.c"
                binary = temp / key
                run("bun", ROOT.parent / "bend/bend2/main.ts", scene,
                    "-o", generated)
                run("clang", "-O3", generated, "-o", binary)
                binaries[key] = binary
                generated_hashes[key] = hashlib.sha256(generated.read_bytes()).hexdigest()
            finally:
                scene.unlink(missing_ok=True)
        checksums = {key: timed(binary, args.frames)[1]
                     for key, binary in binaries.items()}
        full_checksums = {key: timed(binary, 120)[1]
                          for key, binary in binaries.items()}
        assert len(set(checksums.values())) == 1
        assert len(set(full_checksums.values())) == 1
        spot_frames = (0, 23, 95, 119)
        spot_checksums = {key: [int(run(binary, "--threads", 1,
                                         "--gpu", "off", "--", frame).split()[1])
                                for frame in spot_frames]
                          for key, binary in binaries.items()}
        assert len({tuple(values) for values in spot_checksums.values()}) == 1
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
            "scope": "Same 1920x1080 Bend scene and CPU quotient compiler; sky transducer versus generic Array.fill.prefix over 2073600 active pixels in a 2097152-slot Array. One CPU thread, separate clang -O3 binaries, full simulation and checksum. Times cover the specified sequential frames. Both variants also checked for equal 120-frame cumulative checksums once.",
            "frames": args.frames, "full_check_frames": 120,
            "sessions": args.sessions,
            "scene_sha256": hashlib.sha256(SCENE.read_bytes()).hexdigest(),
            "compiler_comp_ts_sha256": hashlib.sha256((ROOT.parent /
                "bend/bend2/comp.ts").read_bytes()).hexdigest(),
            "compiler_base_sha256": hashlib.sha256((ROOT.parent /
                "bend/bend2/base.bend").read_bytes()).hexdigest(),
            "generated_c_sha256": generated_hashes,
            "checksums": checksums, "full_checksums": full_checksums,
            "spot_frames": spot_frames, "spot_checksums": spot_checksums,
            "orders": orders, "samples_us": samples,
            "median_us": {key: statistics.median(values)
                          for key, values in samples.items()},
        }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("checksums", "full_checksums", "median_us")}))


if __name__ == "__main__":
    main()
