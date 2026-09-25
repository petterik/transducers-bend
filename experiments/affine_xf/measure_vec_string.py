#!/usr/bin/env python3
"""Paired native retained-output Vec comparison with String values."""

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
FIXTURE = HERE / 'vec_string_bench.bend'
MODES = {'array': 0, 'maybe_vec': 1, 'fill_vec': 2,
         'public_vec': 3}
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
    parser.add_argument('--sessions', type=int, default=12)
    parser.add_argument('--seed', type=int, default=20260925)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert 0 < args.items <= 262144 and args.sessions > 0
    expected = sum(len(str(i)) for i in range(args.items))
    compiler = args.bend_main.resolve()
    rng = random.Random(args.seed)
    with tempfile.TemporaryDirectory(prefix='vec-string-bench-') as name:
        temp = Path(name)
        c_file = temp / 'bench.c'
        binary = temp / 'bench'
        run('bun', compiler, FIXTURE, '-o', c_file)
        run('clang', '-O3', c_file, '-o', binary)
        samples = {name: [] for name in MODES}
        sessions = []
        for _ in range(args.sessions):
            order = list(MODES)
            rng.shuffle(order)
            session = {}
            for mode in order:
                result = run(binary, '--threads', '1', '--gpu', 'off', '--',
                             MODES[mode], args.items)
                elapsed, answer = map(int, result.stdout.split())
                assert answer == expected and elapsed > 0, \
                    (mode, elapsed, answer, expected)
                session[mode] = elapsed
                samples[mode].append(elapsed)
            sessions.append(session)
        comparisons = {
            'fill_vec_over_array': ('fill_vec', 'array'),
            'maybe_vec_over_array': ('maybe_vec', 'array'),
            'maybe_vec_over_fill_vec': ('maybe_vec', 'fill_vec'),
            'public_vec_over_array': ('public_vec', 'array'),
            'public_vec_over_fill_vec': ('public_vec', 'fill_vec'),
        }
        ratios = {name: [s[n] / s[d] for s in sessions]
                  for name, (n, d) in comparisons.items()}
        report = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'compiler': str(compiler),
            'compiler_comp_sha256': hashlib.sha256(
                (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
            'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            'items': args.items, 'sessions': args.sessions,
            'seed': args.seed, 'expected': expected,
            'samples_us': samples,
            'median_us': {name: statistics.median(values)
                          for name, values in samples.items()},
            'paired_ratio': {name: {
                'median': statistics.median(values),
                'bootstrap_95': interval(values, random.Random(args.seed + i)),
            } for i, (name, values) in enumerate(ratios.items())},
            'heap_alloc_calls': allocation_counts(c_file, temp, args.items,
                                                  expected, MODES),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({key: report[key] for key in
            ('median_us', 'paired_ratio', 'heap_alloc_calls')}, indent=2))


if __name__ == '__main__':
    main()
