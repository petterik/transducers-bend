#!/usr/bin/env python3
"""Paired native comparison for a user-defined owned stage plus take."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import tempfile

from measure_explicit_types import allocation_counts, interval


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / 'static_recipe_bench.bend'
MODES = {'direct': 0, 'current_static': 1, 'staged_xf': 2,
         'generic_xf': 3, 'rank2_xf': 4}
ENV = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}


def run(*args):
    result = subprocess.run([str(arg) for arg in args], env=ENV,
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bend-main', type=Path, required=True)
    parser.add_argument('--items', type=int, default=200000)
    parser.add_argument('--sessions', type=int, default=48)
    parser.add_argument('--seed', type=int, default=20260925)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert 0 < args.items < 4294967296 and args.sessions > 0
    compiler = args.bend_main.resolve()
    rng = random.Random(args.seed)
    expected = (args.items * (args.items + 1) // 2) & 0xFFFFFFFF

    with tempfile.TemporaryDirectory(prefix='static-recipe-measure-') as name:
        temp = Path(name)
        c_file = temp / 'bench.c'
        binary = temp / 'bench'
        run('bun', compiler, FIXTURE, '-o', c_file)
        run('clang', '-O3', c_file, '-o', binary)
        samples = {mode: [] for mode in MODES}
        paired = []
        for _ in range(args.sessions):
            names = list(MODES)
            rng.shuffle(names)
            session = {}
            for mode in names:
                result = run(binary, '--threads', '1', '--gpu', 'off', '--',
                             MODES[mode], args.items)
                elapsed, answer = map(int, result.stdout.split())
                assert answer == expected and elapsed > 0, \
                    (mode, elapsed, answer, expected)
                session[mode] = elapsed
                samples[mode].append(elapsed)
            paired.append(session)
        ratios = {
            'staged_over_current': [s['staged_xf'] / s['current_static']
                                    for s in paired],
            'staged_over_direct': [s['staged_xf'] / s['direct']
                                   for s in paired],
            'generic_over_current': [s['generic_xf'] / s['current_static']
                                     for s in paired],
            'rank2_over_current': [s['rank2_xf'] / s['current_static']
                                   for s in paired],
            'rank2_over_direct': [s['rank2_xf'] / s['direct']
                                  for s in paired],
        }
        report = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'compiler': str(compiler),
            'compiler_comp_sha256': hashlib.sha256(
                (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
            'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            'items': args.items, 'sessions': args.sessions, 'seed': args.seed,
            'expected': expected,
            'samples_us': samples,
            'median_us': {mode: statistics.median(times)
                          for mode, times in samples.items()},
            'paired_ratio': {key: {
                'median': statistics.median(values),
                'bootstrap_95': interval(values, random.Random(args.seed + i)),
            } for i, (key, values) in enumerate(ratios.items())},
            'heap_alloc_calls': allocation_counts(c_file, temp, args.items,
                                                  expected, MODES),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({key: report[key] for key in
                          ('median_us', 'paired_ratio', 'heap_alloc_calls')},
                         indent=2))


if __name__ == '__main__':
    main()
