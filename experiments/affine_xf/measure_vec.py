#!/usr/bin/env python3
"""Paired native comparison of direct and generic List/Vec collection."""

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
FIXTURE = HERE / 'vec_bench.bend'
MODES = {'list_direct': 0, 'list_into': 1,
         'vec_direct': 2, 'vec_into': 3, 'array_direct': 4,
         'vec_data_direct': 5, 'vec_data_into': 6,
         'vec_fill_direct': 7, 'vec_fill_into': 8,
         'vec_fill_reserved': 9, 'vec_data_reserved': 10,
         'array_retained': 11, 'vec_data_retained': 12,
         'vec_fill_retained': 13, 'list_retained': 14,
         'public_vec_reserved': 15, 'public_vec_retained': 16,
         'public_vec_dynamic': 17, 'public_vec_dynamic_retained': 18}
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
    parser.add_argument('--sessions', type=int, default=24)
    parser.add_argument('--seed', type=int, default=20260925)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert 0 < args.items <= 262144 and args.sessions > 0
    expected = (args.items * (args.items + 1) // 2) & 0xFFFFFFFF
    compiler = args.bend_main.resolve()
    rng = random.Random(args.seed)
    with tempfile.TemporaryDirectory(prefix='vec-bench-') as name:
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
            'vec_into_over_vec_direct': ('vec_into', 'vec_direct'),
            'vec_into_over_list_into': ('vec_into', 'list_into'),
            'vec_into_over_array_direct': ('vec_into', 'array_direct'),
            'vec_data_into_over_vec_data_direct':
                ('vec_data_into', 'vec_data_direct'),
            'vec_data_into_over_array_direct':
                ('vec_data_into', 'array_direct'),
            'vec_data_into_over_vec_into': ('vec_data_into', 'vec_into'),
            'vec_fill_into_over_vec_fill_direct':
                ('vec_fill_into', 'vec_fill_direct'),
            'vec_fill_into_over_array_direct':
                ('vec_fill_into', 'array_direct'),
            'vec_fill_into_over_vec_data_into':
                ('vec_fill_into', 'vec_data_into'),
            'vec_fill_reserved_over_array_direct':
                ('vec_fill_reserved', 'array_direct'),
            'vec_fill_into_over_reserved':
                ('vec_fill_into', 'vec_fill_reserved'),
            'vec_data_reserved_over_array_direct':
                ('vec_data_reserved', 'array_direct'),
            'vec_data_reserved_over_vec_fill_reserved':
                ('vec_data_reserved', 'vec_fill_reserved'),
            'list_into_over_list_direct': ('list_into', 'list_direct'),
            'vec_data_retained_over_array_retained':
                ('vec_data_retained', 'array_retained'),
            'vec_fill_retained_over_array_retained':
                ('vec_fill_retained', 'array_retained'),
            'vec_data_retained_over_vec_fill_retained':
                ('vec_data_retained', 'vec_fill_retained'),
            'public_vec_reserved_over_vec_fill_reserved':
                ('public_vec_reserved', 'vec_fill_reserved'),
            'public_vec_retained_over_array_retained':
                ('public_vec_retained', 'array_retained'),
            'public_vec_retained_over_vec_fill_retained':
                ('public_vec_retained', 'vec_fill_retained'),
            'public_vec_dynamic_over_vec_fill_into':
                ('public_vec_dynamic', 'vec_fill_into'),
            'public_vec_dynamic_retained_over_array_retained':
                ('public_vec_dynamic_retained', 'array_retained'),
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
