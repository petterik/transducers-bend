#!/usr/bin/env python3
"""Compare direct and Control traversal of an independent ordered tree."""

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
FIXTURE = HERE / 'branch_control_ablation.bend'
SEMANTICS = HERE / 'branch_control_semantics.bend'
MODES = {'direct': 0, 'control': 1, 'direct_take': 2,
         'control_take': 3, 'initial_stop': 4}


def expected(depth, limit, mode):
    leaves = 1 << depth
    if mode == 'initial_stop':
        return 0
    count = leaves if mode in ('direct', 'control') else min(leaves, limit)
    return (count * (leaves + 1) + count * (count - 1) // 2) & 0xFFFFFFFF


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bend-main', type=Path, required=True)
    parser.add_argument('--depth', type=int, default=18)
    parser.add_argument('--limit', type=int, default=1024)
    parser.add_argument('--sessions', type=int, default=40)
    parser.add_argument('--seed', type=int, default=20260925)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert 1 <= args.depth <= 20 and 0 <= args.limit <= 2 ** 32 - 1
    assert args.sessions > 0
    compiler = args.bend_main.resolve()
    with tempfile.TemporaryDirectory(prefix='branch-control-') as name:
        temp = Path(name)
        c_file = temp / 'bench.c'
        binary = temp / 'bench'
        run('bun', compiler, FIXTURE, '-o', c_file)
        run('clang', '-O3', c_file, '-o', binary)
        # Cross-backend semantics use a small tree so JS traversal remains
        # practical and retain an order-sensitive prefix check.
        semantics_js = temp / 'semantics.js'
        run('bun', compiler, SEMANTICS, '-o', semantics_js)
        want = '(' + ', '.join(str(expected(10, 17, mode))
                               for mode in MODES) + ')'
        result = run('bun', semantics_js)
        assert result.stdout.strip() == want, (result.stdout, want)
        for mode, number in MODES.items():
            result = run(binary, '--threads', '1', '--gpu', 'off', '--',
                         number, 10, 17)
            _, answer = map(int, result.stdout.split())
            assert answer == expected(10, 17, mode), (mode, answer)
        rng = random.Random(args.seed)
        samples = {mode: [] for mode in MODES}
        paired = []
        for _ in range(args.sessions):
            order = list(MODES)
            rng.shuffle(order)
            session = {}
            for mode in order:
                result = run(binary, '--threads', '1', '--gpu', 'off', '--',
                             MODES[mode], args.depth, args.limit)
                elapsed, answer = map(int, result.stdout.split())
                assert elapsed >= 0 and answer == expected(args.depth, args.limit, mode), \
                    (mode, elapsed, answer)
                samples[mode].append(elapsed)
                session[mode] = elapsed
            paired.append(session)
        comparisons = {
            'control_over_direct': ('control', 'direct'),
            'control_take_over_direct_take': ('control_take', 'direct_take'),
        }
        ratios = {label: [s[a] / s[b] for s in paired if s[b] > 0]
                  for label, (a, b) in comparisons.items()}
        allocations = allocation_counts(c_file, temp, args.depth,
                                        expected(args.depth, args.limit, 'direct'),
                                        {'direct': 0, 'control': 1},
                                        (args.limit,))
        report = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'compiler': str(compiler),
            'compiler_comp_sha256': hashlib.sha256(
                (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
            'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            'depth': args.depth, 'limit': args.limit,
            'sessions': args.sessions, 'seed': args.seed,
            'samples_us': samples,
            'median_us': {mode: statistics.median(values)
                          for mode, values in samples.items()},
            'paired_ratio': {label: {
                'median': statistics.median(values) if values else None,
                'bootstrap_95': interval(values, random.Random(args.seed + i))
                if values else None,
            } for i, (label, values) in enumerate(ratios.items())},
            'heap_alloc_calls': allocations,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in
          ('median_us', 'paired_ratio', 'heap_alloc_calls')}, indent=2))


if __name__ == '__main__':
    main()
