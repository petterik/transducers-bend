#!/usr/bin/env python3
"""Check and time five equivalent 512x512 Bullet Cathedral implementations."""
import argparse
import json
from pathlib import Path
import platform
import random
import re
import statistics
import tempfile

from bullet_cathedral_cross_language import (ROOT, command, command_full,
    instrument_allocations, sha, source_size, timed)


BEND_XF = ROOT / "bench/bullet_cathedral.bend"
BEND_DIRECT = ROOT / "bench/bullet_cathedral_direct.bend"
C = ROOT / "bench/bullet_cathedral_control.c"
RUST_ITER = ROOT / "bench/bullet_cathedral_control.rs"
RUST_LOOPS = ROOT / "bench/bullet_cathedral_loops.rs"
RUST_METER = ROOT / "bench/bullet_cathedral_rust_alloc.rs"


def bend_frame(binary, frame):
    base = (binary, "--threads", 1, "--gpu", "off", "--", frame)
    checksum = int(command(*base).split()[1])
    score = int(command(*base, 1))
    shield = int(command(*base, 2))
    return checksum, score, shield


def allocation_count(binary, frames, expected):
    run = command_full(binary, "--threads", 1, "--gpu", "off", "--",
                       frames, "bench", "x")
    assert int(run.stdout.split()[1]) == expected
    match = re.search(r"TIMED_ALLOC (\d+) (\d+)", run.stderr)
    assert match and int(match.group(2)) == 2
    return int(match.group(1))


def rust_allocation_count(binary, frames, expected):
    run = command_full(binary, frames, "new")
    assert int(run.stdout.split()[1]) == expected
    match = re.search(r"TIMED_ALLOC (\d+)", run.stderr)
    assert match
    return int(match.group(1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path, default=ROOT /
        "bench/bullet-cathedral-five-way-20260927.json")
    args = parser.parse_args()
    assert 1 <= args.frames <= 120 and args.sessions > 0

    with tempfile.TemporaryDirectory(prefix="bullet-five-way-") as folder:
        temp = Path(folder)
        binaries = {name: temp / name for name in
            ("bend_xf", "bend_direct", "c_loops", "rust_iter", "rust_loops")}
        generated = {}
        for name, source in (("bend_xf", BEND_XF),
                             ("bend_direct", BEND_DIRECT)):
            generated[name] = temp / (name + ".c")
            command("bun", ROOT.parent / "bend/bend2/main.ts", source,
                    "-o", generated[name])
            command("clang", "-O3", generated[name], "-o", binaries[name])
        command("clang", "-O3", "-ffp-contract=off", C,
                "-o", binaries["c_loops"])
        for name, source in (("rust_iter", RUST_ITER),
                             ("rust_loops", RUST_LOOPS)):
            command("rustc", "-C", "opt-level=3", "-C", "target-cpu=native",
                    source, "-o", binaries[name])

        c_frames = [tuple(map(int, line.split())) for line in
            command(binaries["c_loops"], args.frames, "frames").splitlines()]
        rust_frames = {}
        for name in ("rust_iter", "rust_loops"):
            rust_frames[name] = [tuple(map(int, line.split())) for line in
                command(binaries[name], args.frames, "frames").splitlines()]
            assert rust_frames[name] == c_frames, name
        for name in ("bend_xf", "bend_direct"):
            for frame, expected in enumerate(c_frames):
                actual = bend_frame(binaries[name], frame)
                assert actual == expected, (name, frame, actual, expected)
        expected_sum = sum(row[0] for row in c_frames) & 0xFFFFFFFF

        bend_alloc = {}
        for name in ("bend_xf", "bend_direct"):
            instrumented = temp / (name + "_alloc.c")
            instrumented.write_text(instrument_allocations(
                generated[name].read_text()))
            binary = temp / (name + "_alloc")
            command("clang", "-O3", instrumented, "-o", binary)
            bend_alloc[name] = allocation_count(binary, args.frames,
                                                expected_sum)
        rust_alloc = {}
        for name, source in (("rust_iter", RUST_ITER),
                             ("rust_loops", RUST_LOOPS)):
            wrapper = temp / (name + "_alloc.rs")
            wrapper.write_text(RUST_METER.read_text().replace(
                "bullet_cathedral_control.rs", str(source)))
            binary = temp / (name + "_alloc")
            command("rustc", "--cfg", "alloc_meter", "-C", "opt-level=3",
                    "-C", "target-cpu=native", wrapper, "-o", binary)
            rust_alloc[name] = rust_allocation_count(binary, args.frames,
                                                     expected_sum)

        commands = {
            "bend_xf": [binaries["bend_xf"], "--threads", 1, "--gpu",
                        "off", "--", args.frames, "bench", "x"],
            "bend_direct": [binaries["bend_direct"], "--threads", 1,
                            "--gpu", "off", "--", args.frames, "bench", "x"],
            "c_loops": [binaries["c_loops"], args.frames, "new"],
            "rust_iter": [binaries["rust_iter"], args.frames, "new"],
            "rust_loops": [binaries["rust_loops"], args.frames, "new"],
        }
        samples = {name: [] for name in commands}
        for session in range(args.sessions):
            order = list(commands)
            random.Random(20260927 + session).shuffle(order)
            for name in order:
                samples[name].append(timed(commands[name], expected_sum))
        sources = {"bend_xf": BEND_XF, "bend_direct": BEND_DIRECT,
                   "c_loops": C, "rust_iter": RUST_ITER,
                   "rust_loops": RUST_LOOPS}
        report = {
            "scope": "120 sequential 512x512 frames, one CPU thread, fresh framebuffer per frame; internal times include setup, simulation, rendering, checksums, and cleanup; exclude process startup, compilation, and presentation",
            "frames": args.frames,
            "sessions": args.sessions,
            "all_frame_triples_equal": True,
            "per_frame": c_frames,
            "cumulative_checksum": expected_sum,
            "samples_us": samples,
            "median_us": {name: statistics.median(values)
                          for name, values in samples.items()},
            "timed_allocations": {
                "bend_native_heap_alloc": bend_alloc,
                "rust_global_allocator_calls": rust_alloc,
                "c_explicit_scene_malloc": args.frames,
            },
            "allocation_count_scope": "Bend counts generated native heap_alloc calls; Rust counts System alloc/alloc_zeroed/realloc calls; C counts only explicit scene malloc calls, not libc internals. These interfaces differ.",
            "sources_sha256": {name: sha(path) for name, path in sources.items()},
            "generated_c_sha256": {name: sha(path) for name, path in generated.items()},
            "compiler_comp_ts_sha256": sha(ROOT.parent / "bend/bend2/comp.ts"),
            "compiler_base_sha256": sha(ROOT.parent / "bend/bend2/base.bend"),
            "source_size": {name: source_size(path)
                            for name, path in sources.items()},
            "source_size_rule": "Nonblank, noncomment lines and code-only lexical tokens in each complete handwritten scene file, including its own CLI driver; imported libraries and generated C excluded",
            "compiler_flags": {"bend_generated_c": "clang -O3",
                               "manual_c": "clang -O3 -ffp-contract=off",
                               "rust": "rustc -C opt-level=3 -C target-cpu=native"},
            "platform": platform.platform(),
            "clang": command("clang", "--version").splitlines()[0],
            "rustc": command("rustc", "--version"),
        }
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({name: report[name] for name in
            ("median_us", "timed_allocations", "source_size")}))


if __name__ == "__main__":
    main()
