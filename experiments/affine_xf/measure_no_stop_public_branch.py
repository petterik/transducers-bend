#!/usr/bin/env python3
"""Compare a handwritten Branch fold with both public source-selection paths."""
import argparse
import json
from pathlib import Path
import random
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BEND = ROOT.parent / 'bend' / 'bend2' / 'main.ts'
FIXTURE = Path(__file__).with_name('no_stop_public_branch_bench.bend')
NAMES = ('direct', 'automatic', 'explicit')


def run(command):
    result = subprocess.run([str(part) for part in command], cwd=ROOT,
                            text=True, capture_output=True, check=True)
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--depth', type=int, default=18)
    parser.add_argument('--sessions', type=int, default=32)
    args = parser.parse_args()
    assert args.depth > 0 and args.sessions > 0
    with tempfile.TemporaryDirectory(prefix='public-branch-bench-') as tmp:
        c_file = Path(tmp) / 'bench.c'
        binary = Path(tmp) / 'bench'
        run(['bun', BEND, FIXTURE, '-o', c_file])
        run(['clang', '-O3', c_file, '-o', binary])
        samples = {name: [] for name in NAMES}
        answers = set()
        for session in range(args.sessions):
            modes = list(range(len(NAMES)))
            random.Random(20260925 + session).shuffle(modes)
            for mode in modes:
                elapsed, value = map(int, run([
                    binary, '--threads', '1', '--gpu', 'off', '--',
                    mode, args.depth]).split())
                samples[NAMES[mode]].append(elapsed)
                answers.add(value)
        assert len(answers) == 1, answers
    medians = {name: statistics.median(values)
               for name, values in samples.items()}
    print(json.dumps({
        'depth': args.depth,
        'sessions': args.sessions,
        'result': next(iter(answers)),
        'median_us': medians,
        'automatic_over_direct': medians['automatic'] / medians['direct'],
        'explicit_over_direct': medians['explicit'] / medians['direct'],
    }, indent=2))


if __name__ == '__main__':
    main()
