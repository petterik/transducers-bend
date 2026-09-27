#!/usr/bin/env python3
"""Compare a synthesized transducer sky with current bounded Array.fill."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import statistics
import subprocess
import tempfile

from bullet_render_phase_profile import variant
from public_array_map_filter_sum import instrument_allocations

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/bullet_cathedral.bend"
OLD = """def background() -> Array<U32>:
  X.transduce(X.map(~U32, ~Ink, ~sky_at), ink_rf(),
    Array.new(U32, 18n, 0), T.range(262144))
"""
NEW = """def sky_color_after(ink: Ink) -> U32:
  match ink:
    case Ink{index, color}: color

def sky_color(index: U32) -> U32:
  sky_color_after(sky(index))

def background() -> Array<U32>:
  Array.fill(~U32, ~sky_color, Array.new(U32, 18n, 0))
"""


def command(*args):
    return subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True,
                          capture_output=True, text=True)


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
                        "bench/bullet-fill-comparison-20260927.json")
    args = parser.parse_args()
    assert args.frames > 0 and args.sessions > 0
    filled = SOURCE.read_text()
    assert filled.count(NEW) == 1
    original = filled.replace(NEW, OLD)
    sources = {"original_full": original,
               "fill_full": filled,
               "original_background": variant(original, "background"),
               "fill_background": variant(filled, "background")}
    modified_files = []
    try:
        with tempfile.TemporaryDirectory(prefix="bullet-fill-") as temp_name:
            temp = Path(temp_name)
            binaries = {}
            checksums = {}
            allocations = {}
            generated_hashes = {}
            for name, source in sources.items():
                with tempfile.NamedTemporaryFile(mode="w", prefix=f"bullet_{name}_",
                                                 suffix=".bend", dir=ROOT / "bench",
                                                 delete=False) as handle:
                    handle.write(source)
                    modified = Path(handle.name)
                modified_files.append(modified)
                generated = temp / f"{name}.c"
                binary = temp / name
                instrumented = temp / f"{name}_alloc.c"
                alloc_binary = temp / f"{name}_alloc"
                command("bun", ROOT.parent / "bend/bend2/main.ts", modified,
                        "-o", generated)
                generated_hashes[name] = hashlib.sha256(generated.read_bytes()).hexdigest()
                command("clang", "-O3", generated, "-o", binary)
                instrumented.write_text(instrument_allocations(generated.read_text()))
                command("clang", "-O3", instrumented, "-o", alloc_binary)
                binaries[name] = binary
                checksums[name] = timed(binary, args.frames)[1]
                _, checksum, stderr = timed(alloc_binary, args.frames)
                assert checksum == checksums[name]
                match = re.search(r"TIMED_ALLOC (\d+) (\d+)", stderr)
                assert match and int(match.group(2)) == 2
                allocations[name] = int(match.group(1))
            assert checksums["original_full"] == checksums["fill_full"]
            assert checksums["original_background"] == checksums["fill_background"]
            if args.frames == 120:
                assert checksums["original_full"] == 367602200
            samples = {name: [] for name in sources}
            orders = []
            for session in range(args.sessions):
                order = list(sources)
                random.Random(20260928 + session).shuffle(order)
                orders.append(order)
                for name in order:
                    elapsed, checksum, _ = timed(binaries[name], args.frames)
                    assert checksum == checksums[name]
                    samples[name].append(elapsed)
    finally:
        for file in modified_files:
            file.unlink(missing_ok=True)
    report = {
        "scope": "Separate generated Bend C binaries, one CPU thread, 120 sequential frames; same simulation and checksum, original transducer background versus generic bounded Array.fill. Full scene and background-only cumulative ablation; order shuffled by session.",
        "frames": args.frames, "sessions": args.sessions,
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "compiler_comp_ts_sha256": hashlib.sha256((ROOT.parent / "bend/bend2/comp.ts").read_bytes()).hexdigest(),
        "compiler_base_sha256": hashlib.sha256((ROOT.parent / "bend/bend2/base.bend").read_bytes()).hexdigest(),
        "generated_c_sha256": generated_hashes,
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
