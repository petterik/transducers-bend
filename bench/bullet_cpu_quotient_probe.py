#!/usr/bin/env python3
"""Measure the old Metal quotient on CPU against native CPU division."""

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
COMPILER = ROOT.parent / "bend/bend2/comp.ts"
OLD = """#if DEVICE
#define U32_QUO(a, b) \\
  ((a) / 2 / (b) * 2 + ((a) - (a) / 2 / (b) * 2 * (b) >= (b)))
#else
// Native CPU division has no Metal constant-folding bug. Keep its ordinary
// quotient so clang can combine a quotient and remainder into one division.
#define U32_QUO(a, b) ((a) / (b))
#endif"""
NEW = """#define U32_QUO(a, b) \\
  ((a) / 2 / (b) * 2 + ((a) - (a) / 2 / (b) * 2 * (b) >= (b)))"""


def run(*args):
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()


def timed(binary, frames):
    elapsed, checksum = map(int, run(binary, "--threads", 1, "--gpu", "off",
                                     "--", frames, "bench", "x").split())
    return elapsed, checksum


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path, default=ROOT /
                        "bench/bullet-cpu-quotient-probe-20260927.json")
    args = parser.parse_args()
    assert args.frames > 0 and args.sessions > 0
    with tempfile.TemporaryDirectory(prefix="bullet-cpu-quotient-") as name:
        temp = Path(name)
        generated = temp / "native.c"
        old = temp / "old.c"
        binary = {"cpu_quotient": temp / "native",
                  "metal_quotient_on_cpu": temp / "old"}
        run("bun", ROOT.parent / "bend/bend2/main.ts", SCENE, "-o",
            generated)
        source = generated.read_text()
        assert source.count(OLD) == 1
        old.write_text(source.replace(OLD, NEW))
        run("clang", "-O3", generated, "-o", binary["cpu_quotient"])
        run("clang", "-O3", old, "-o", binary["metal_quotient_on_cpu"])
        checksums = {key: timed(value, args.frames)[1]
                     for key, value in binary.items()}
        assert len(set(checksums.values())) == 1
        if args.frames == 120:
            assert next(iter(checksums.values())) == 367602200
        samples = {key: [] for key in binary}
        orders = []
        for session in range(args.sessions):
            order = list(binary)
            random.Random(20260928 + session).shuffle(order)
            orders.append(order)
            for key in order:
                elapsed, checksum = timed(binary[key], args.frames)
                assert checksum == checksums[key]
                samples[key].append(elapsed)
        report = {
            "scope": "Same Bend scene and generated C, two separate clang -O3 binaries, one CPU thread; only U32_QUO macro differs. All sequential frames, full simulation, fresh framebuffer, checksum and cleanup are timed internally.",
            "frames": args.frames, "sessions": args.sessions,
            "scene_sha256": sha(SCENE), "compiler_comp_ts_sha256": sha(COMPILER),
            "generated_c_sha256": {"cpu_quotient": sha(generated),
                                   "metal_quotient_on_cpu": sha(old)},
            "checksums": checksums, "orders": orders,
            "samples_us": samples,
            "median_us": {key: statistics.median(values)
                          for key, values in samples.items()},
        }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("checksums", "median_us")}))


if __name__ == "__main__":
    main()
