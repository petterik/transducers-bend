#!/usr/bin/env python3
"""Pair generic and M3-targeted builds of the 512px scene without source edits."""
import argparse
import json
from pathlib import Path
import platform
import random
import statistics
import tempfile

from bullet_cathedral_cross_language import BEND, C, ROOT, RUST, command, sha


def timed(argv, expected):
    elapsed, checksum = map(int, command(*argv).split())
    assert checksum == expected, (argv, checksum, expected)
    return elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "bench/bullet-target-cpu-probe-20260927.json")
    args = parser.parse_args()
    assert args.sessions > 0
    with tempfile.TemporaryDirectory(prefix="bullet-target-cpu-") as name:
        temp = Path(name)
        generated = temp / "bend.c"
        command("bun", ROOT.parent / "bend/bend2/main.ts", BEND, "-o", generated)
        builds = {
            "bend_default": (["clang", "-O3", generated],
                             ["--threads", "1", "--gpu", "off", "--", "120", "bench", "x"]),
            "bend_m3": (["clang", "-O3", "-mcpu=apple-m3", generated],
                        ["--threads", "1", "--gpu", "off", "--", "120", "bench", "x"]),
            "c_default": (["clang", "-O3", "-ffp-contract=off", C], ["120", "new"]),
            "c_m3": (["clang", "-O3", "-mcpu=apple-m3", "-ffp-contract=off", C],
                     ["120", "new"]),
            "rust_generic": (["rustc", "-C", "opt-level=3", "-C",
                              "target-cpu=generic", RUST], ["120", "new"]),
            "rust_m3": (["rustc", "-C", "opt-level=3", "-C",
                         "target-cpu=apple-m3", RUST], ["120", "new"]),
        }
        commands = {}
        flags = {}
        for label, (compiler, runtime_args) in builds.items():
            binary = temp / label
            command(*compiler, "-o", binary)
            commands[label] = [binary, *runtime_args]
            flags[label] = " ".join(map(str, compiler[:-1]))
        expected = 367602200
        for argv in commands.values():
            timed(argv, expected)
        samples = {label: [] for label in commands}
        for session in range(args.sessions):
            order = list(commands)
            random.Random(20260927 + session).shuffle(order)
            for label in order:
                samples[label].append(timed(commands[label], expected))
        report = {
            "scope": "120 sequential 512x512 frames, one CPU thread, fresh framebuffer each frame; identical scene source per language; shuffled process sessions; compilation and startup excluded",
            "sessions": args.sessions,
            "expected_checksum": expected,
            "compiler_flags": flags,
            "sources_sha256": {path.name: sha(path) for path in (BEND, C, RUST)},
            "generated_c_sha256": sha(generated),
            "compiler_comp_ts_sha256": sha(ROOT.parent / "bend/bend2/comp.ts"),
            "samples_us": samples,
            "median_us": {label: statistics.median(values)
                          for label, values in samples.items()},
            "platform": platform.platform(),
            "clang": command("clang", "--version").splitlines()[0],
            "rustc": command("rustc", "--version"),
        }
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report["median_us"]))


if __name__ == "__main__":
    main()
