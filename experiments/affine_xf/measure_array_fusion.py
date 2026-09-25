#!/usr/bin/env python3
"""Separate Array traversal, stopping, reducer, and companion overhead."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import statistics
import tempfile

from measure_explicit_types import allocation_counts, interval, run


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / 'array_fusion_ablation.bend'
MODES = {'direct': 0, 'direct_inc': 1, 'control': 2,
         'static': 3, 'public': 4}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bend-main', type=Path, required=True)
    parser.add_argument('--depth', type=int, default=20)
    parser.add_argument('--sessions', type=int, default=40)
    parser.add_argument('--seed', type=int, default=20260925)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert 0 <= args.depth <= 30 and args.sessions > 0
    compiler = args.bend_main.resolve()
    expected = (2 * (1 << args.depth)) & 0xFFFFFFFF
    rng = random.Random(args.seed)
    with tempfile.TemporaryDirectory(prefix='array-fusion-') as name:
        temp = Path(name)
        c_file = temp / 'bench.c'
        binary = temp / 'bench'
        run('bun', compiler, FIXTURE, '-o', c_file)
        run('clang', '-O3', c_file, '-o', binary)
        samples = {mode: [] for mode in MODES}
        paired = []
        for _ in range(args.sessions):
            order = list(MODES)
            rng.shuffle(order)
            session = {}
            for mode in order:
                result = run(binary, '--threads', '1', '--gpu', 'off', '--',
                             MODES[mode], args.depth)
                elapsed, answer = map(int, result.stdout.split())
                assert elapsed > 0 and answer == expected, \
                    (mode, elapsed, answer, expected)
                samples[mode].append(elapsed)
                session[mode] = elapsed
            paired.append(session)
        comparisons = {
            'direct_inc_over_direct': ('direct_inc', 'direct'),
            'control_over_direct_inc': ('control', 'direct_inc'),
            'static_over_control': ('static', 'control'),
            'public_over_static': ('public', 'static'),
            'public_over_direct': ('public', 'direct'),
        }
        ratios = {label: [s[a] / s[b] for s in paired]
                  for label, (a, b) in comparisons.items()}
        allocations = allocation_counts(c_file, temp, args.depth,
                                        expected, MODES)
        report = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'compiler': str(compiler),
            'compiler_comp_sha256': hashlib.sha256(
                (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
            'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            'depth': args.depth, 'sessions': args.sessions,
            'seed': args.seed, 'expected': expected,
            'samples_us': samples,
            'median_us': {mode: statistics.median(values)
                          for mode, values in samples.items()},
            'paired_ratio': {label: {
                'median': statistics.median(values),
                'bootstrap_95': interval(values, random.Random(args.seed + i)),
            } for i, (label, values) in enumerate(ratios.items())},
            'heap_alloc_calls': allocations,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({key: report[key] for key in
              ('median_us', 'paired_ratio', 'heap_alloc_calls')}, indent=2))


if __name__ == '__main__':
    main()
