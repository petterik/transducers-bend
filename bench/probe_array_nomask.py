#!/usr/bin/env python3
"""Measure a bounded Array-read codegen prototype without changing Bend."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import tempfile

from public_array_map_filter_sum import BEND, MANUAL_C, ROOT, expected, run

OLD_READ = "Term _at_1 = blk_at(_checked_1, _index_0, 0);"
NEW_READ = "Term _at_1 = _index_0;"
NAMES = ("public_current", "public_no_wrap_prototype", "direct_bend", "manual_c")


def sample(command, checksum):
    elapsed, answer = map(int, run(*command).split())
    assert answer == checksum, (command, answer, checksum)
    return elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depths", type=int, nargs="+", default=[16, 18, 20])
    parser.add_argument("--seeds", type=int, nargs="+", default=[12345, 987654321])
    parser.add_argument("--sessions", type=int, default=24)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    assert args.sessions > 0
    assert all(0 <= depth <= 23 for depth in args.depths)
    assert all(0 <= seed <= 0xFFFFFFFF for seed in args.seeds)

    with tempfile.TemporaryDirectory(prefix="array-nomask-probe-") as directory:
        temp = Path(directory)
        generated = temp / "bend.c"
        prototype = temp / "bend_no_wrap.c"
        bend_binary = temp / "bend"
        prototype_binary = temp / "bend_no_wrap"
        manual_binary = temp / "manual_c"
        run("bun", ROOT.parent / "bend/bend2/main.ts", BEND, "-o", generated)
        source = generated.read_text()
        assert source.count(OLD_READ) == 1, "Array source code shape changed"
        prototype.write_text(source.replace(OLD_READ, NEW_READ, 1))
        run("clang", "-O3", generated, "-o", bend_binary)
        run("clang", "-O3", prototype, "-o", prototype_binary)
        run("clang", "-O3", MANUAL_C, "-o", manual_binary)

        report = {
            "scope": "One native CPU thread; only the generated C read in public Array.source is changed",
            "prototype_edit": {"old": OLD_READ, "new": NEW_READ},
            "production_fix": False,
            "compiler_commit": run("git", "-C", ROOT.parent / "bend", "rev-parse", "HEAD"),
            "library_commit": run("git", "rev-parse", "HEAD"),
            "fixture_sha256": hashlib.sha256(BEND.read_bytes()).hexdigest(),
            "manual_c_sha256": hashlib.sha256(MANUAL_C.read_bytes()).hexdigest(),
            "platform": platform.platform(),
            "clang": run("clang", "--version").splitlines()[0],
            "sessions": args.sessions,
            "results": [],
        }
        for depth in args.depths:
            for seed in args.seeds:
                checksum, selected = expected(depth, seed)
                commands = {
                    "public_current": [bend_binary, "--threads", "1", "--gpu", "off", "--", 0, depth, seed],
                    "public_no_wrap_prototype": [prototype_binary, "--threads", "1", "--gpu", "off", "--", 0, depth, seed],
                    "direct_bend": [bend_binary, "--threads", "1", "--gpu", "off", "--", 1, depth, seed],
                    "manual_c": [manual_binary, depth, seed],
                }
                samples = {name: [] for name in NAMES}
                for session in range(args.sessions):
                    order = list(NAMES)
                    random.Random(20260926 + depth * 1000 + seed + session).shuffle(order)
                    for name in order:
                        samples[name].append(sample(commands[name], checksum))
                medians = {name: statistics.median(values) for name, values in samples.items()}
                report["results"].append({
                    "depth": depth,
                    "elements": 1 << depth,
                    "seed": seed,
                    "selected_elements": selected,
                    "checksum": checksum,
                    "samples_us": samples,
                    "median_us": medians,
                })
                print(depth, seed, medians, flush=True)
        if args.output:
            args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
