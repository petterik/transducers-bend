#!/usr/bin/env python3
"""Measure an intentionally unsafe generated-C Array-index ablation."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/bullet_cathedral.bend"
MASKED = "return ((u32)i & (u32)((1ull << (blk_cls(a) - lgs)) - 1)) << lgs;"
UNMASKED = "return (u32)i << lgs;"


def command(*args):
    return subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True,
                          capture_output=True, text=True)


def timed(binary, frames):
    result = command(binary, "--threads", 1, "--gpu", "off", "--",
                     frames, "bench", "x")
    return tuple(map(int, result.stdout.split()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path, default=ROOT /
                        "bench/bullet-nomask-probe-20260927.json")
    args = parser.parse_args()
    assert args.frames > 0 and args.sessions > 0
    with tempfile.TemporaryDirectory(prefix="bullet-nomask-") as temp_name:
        temp = Path(temp_name)
        generated = temp / "generated.c"
        normal = temp / "normal"
        unsafe_c = temp / "unsafe.c"
        unsafe = temp / "unsafe"
        command("bun", ROOT.parent / "bend/bend2/main.ts", SOURCE,
                "-o", generated)
        code = generated.read_text()
        assert code.count(MASKED) == 1
        unsafe_c.write_text(code.replace(MASKED, UNMASKED))
        command("clang", "-O3", generated, "-o", normal)
        command("clang", "-O3", unsafe_c, "-o", unsafe)
        binaries = {"normal": normal, "unsafe_global_nomask": unsafe}
        expected = timed(normal, args.frames)[1]
        assert timed(unsafe, args.frames)[1] == expected
        samples = {name: [] for name in binaries}
        orders = []
        for session in range(args.sessions):
            order = list(binaries)
            random.Random(20260928 + session).shuffle(order)
            orders.append(order)
            for name in order:
                elapsed, checksum = timed(binaries[name], args.frames)
                assert checksum == expected
                samples[name].append(elapsed)
        generated_hash = hashlib.sha256(generated.read_bytes()).hexdigest()
    report = {
        "scope": "Unsafe probe only: globally replacing blk_at wraparound with a direct offset changes the Array contract and can access out of bounds. Matching this deterministic checksum does not make the replacement safe. One native CPU thread; 21 shuffled paired runs; process startup excluded.",
        "frames": args.frames, "sessions": args.sessions, "checksum": expected,
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "generated_c_sha256": generated_hash,
        "orders": orders, "samples_us": samples,
        "median_us": {name: statistics.median(values)
                      for name, values in samples.items()},
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["median_us"]))


if __name__ == "__main__":
    main()
