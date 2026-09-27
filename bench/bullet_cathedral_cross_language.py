#!/usr/bin/env python3
"""Check and time the 512x512 Bend, C, and Rust Bullet Cathedral scenes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import statistics
import subprocess
import tempfile

from public_array_map_filter_sum import instrument_allocations

ROOT = Path(__file__).resolve().parents[1]
BEND = ROOT / "bench/bullet_cathedral.bend"
C = ROOT / "bench/bullet_cathedral_control.c"
RUST = ROOT / "bench/bullet_cathedral_control.rs"
RUST_ALLOC = ROOT / "bench/bullet_cathedral_rust_alloc.rs"


def command(*args):
    env = dict(os.environ, CLANG_MODULE_CACHE_PATH="/tmp/bend-clang-modules")
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True,
                          capture_output=True, text=True, env=env).stdout.strip()


def command_full(*args):
    env = dict(os.environ, CLANG_MODULE_CACHE_PATH="/tmp/bend-clang-modules")
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True,
                          capture_output=True, text=True, env=env)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_size(path):
    text = path.read_text()
    marker = "#" if path.suffix == ".bend" else "//"
    lines = [line.split(marker, 1)[0].strip() for line in text.splitlines()]
    code = "\n".join(line for line in lines if line)
    return {"nonblank_noncomment_lines": sum(bool(line) for line in lines),
            "lexical_tokens": len(re.findall(r"[A-Za-z_][A-Za-z_0-9]*|[0-9]+|[^\s]", code))}


def timed(argv, expected):
    elapsed, checksum = map(int, command(*argv).split())
    assert checksum == expected, (argv, checksum, expected)
    return elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path,
                         default=ROOT / "bench/bullet-cathedral-iterator-cross-language-20260927.json")
    args = parser.parse_args()
    assert 1 <= args.frames <= 120 and args.sessions > 0
    with tempfile.TemporaryDirectory(prefix="bullet-cross-language-") as name:
        temp = Path(name)
        generated = temp / "bend.c"
        bend_bin = temp / "bend"
        c_bin = temp / "control_c"
        rust_bin = temp / "control_rust"
        bend_alloc_bin = temp / "bend_alloc"
        rust_alloc_bin = temp / "rust_alloc"
        command("bun", ROOT.parent / "bend/bend2/main.ts", BEND, "-o", generated)
        command("clang", "-O3", generated, "-o", bend_bin)
        command("clang", "-O3", "-ffp-contract=off", C, "-o", c_bin)
        command("rustc", "-C", "opt-level=3", "-C", "target-cpu=native",
                RUST, "-o", rust_bin)
        bend_alloc_source = temp / "bend_alloc.c"
        bend_alloc_source.write_text(instrument_allocations(generated.read_text()))
        command("clang", "-O3", bend_alloc_source, "-o", bend_alloc_bin)
        command("rustc", "--cfg", "alloc_meter", "-C", "opt-level=3",
                "-C", "target-cpu=native", RUST_ALLOC, "-o", rust_alloc_bin)

        c_frames = [tuple(map(int, line.split())) for line in
                    command(c_bin, args.frames, "frames").splitlines()]
        rust_frames = [tuple(map(int, line.split())) for line in
                       command(rust_bin, args.frames, "frames").splitlines()]
        assert len(c_frames) == len(rust_frames) == args.frames
        assert c_frames == rust_frames, next((i for i, (a, b) in
            enumerate(zip(c_frames, rust_frames)) if a != b), None)
        bend_frames = []
        for frame in range(args.frames):
            checksum = int(command(bend_bin, "--threads", 1, "--gpu", "off",
                                   "--", frame).split()[1])
            score = int(command(bend_bin, "--threads", 1, "--gpu", "off",
                                "--", frame, 1))
            shield = int(command(bend_bin, "--threads", 1, "--gpu", "off",
                                 "--", frame, 2))
            bend_frames.append((checksum, score, shield))
            assert c_frames[frame] == bend_frames[-1], (frame, c_frames[frame],
                                                        bend_frames[-1])
        expected = sum(row[0] for row in bend_frames) & 0xFFFFFFFF
        bend_alloc_run = command_full(bend_alloc_bin, "--threads", 1,
                                      "--gpu", "off", "--", args.frames,
                                      "bench", "x")
        assert int(bend_alloc_run.stdout.split()[1]) == expected
        bend_alloc_match = re.search(r"TIMED_ALLOC (\d+) (\d+)",
                                     bend_alloc_run.stderr)
        assert bend_alloc_match and int(bend_alloc_match.group(2)) == 2
        rust_alloc_counts = {}
        for lane, mode in (("rust_reuse", None), ("rust_fresh", "new")):
            argv = [rust_alloc_bin, args.frames]
            if mode is not None: argv.append(mode)
            result = command_full(*argv)
            assert int(result.stdout.split()[1]) == expected
            match = re.search(r"TIMED_ALLOC (\d+)", result.stderr)
            assert match
            rust_alloc_counts[lane] = int(match.group(1))
        commands = {
            "bend": [bend_bin, "--threads", 1, "--gpu", "off", "--",
                     args.frames, "bench", "x"],
            "c_reuse": [c_bin, args.frames],
            "c_fresh": [c_bin, args.frames, "new"],
            "rust_reuse": [rust_bin, args.frames],
            "rust_fresh": [rust_bin, args.frames, "new"],
        }
        samples = {name: [] for name in commands}
        for session in range(args.sessions):
            order = list(commands)
            random.Random(20260927 + session).shuffle(order)
            for name in order:
                samples[name].append(timed(commands[name], expected))
        report = {
            "scope": "120 sequential 512x512 frames, one CPU thread; initial World and framebuffer setup, simulation, framebuffer construction, pixel checksum, and cleanup timed internally; process startup, compilation, and display excluded",
            "frames": args.frames, "sessions": args.sessions,
            "all_frame_checksums_scores_shields_equal": True,
            "per_frame": bend_frames,
            "cumulative_checksum": expected,
            "samples_us": samples,
            "median_us": {name: statistics.median(values)
                          for name, values in samples.items()},
            "timed_allocation_calls": {
                "bend_heap_alloc": int(bend_alloc_match.group(1)),
                "rust_global_allocator": rust_alloc_counts,
                "c_explicit_scene_malloc": {"c_reuse": 1,
                                            "c_fresh": args.frames},
            },
            "allocation_count_scope": "Bend counts generated native heap_alloc calls; Rust counts System alloc/alloc_zeroed/realloc calls from the separate global-allocator meter; C counts explicit malloc calls in the handwritten scene, not libc internals. Counts are not identical allocator abstractions.",
            "sources_sha256": {path.name: sha(path) for path in (BEND, C, RUST)},
            "rust_allocation_meter_sha256": sha(RUST_ALLOC),
            "generated_c_sha256": sha(generated),
            "compiler_comp_ts_sha256": sha(ROOT.parent / "bend/bend2/comp.ts"),
            "compiler_base_sha256": sha(ROOT.parent / "bend/bend2/base.bend"),
            "source_size_rule": "Count nonempty lines after stripping # or // comments; tokens are identifiers, digit runs, and individual nonspace punctuation. Counts include each file's own CLI harness; Bend library and generated C are separate.",
            "source_size": {path.name: source_size(path) for path in
                            (BEND, C, RUST, ROOT / "xf.bend",
                             ROOT / "transduce_core.bend")},
            "compiler_flags": {"bend_generated_c": "clang -O3",
                               "manual_c": "clang -O3 -ffp-contract=off",
                               "rust": "rustc -C opt-level=3 -C target-cpu=native"},
            "platform": platform.platform(),
            "clang": command("clang", "--version").splitlines()[0],
            "rustc": command("rustc", "--version"),
        }
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: report[k] for k in ("frames", "cumulative_checksum",
                                                  "median_us", "timed_allocation_calls",
                                                  "source_size")}))


if __name__ == "__main__":
    main()
