#!/usr/bin/env python3
"""Measure the speedup available through a total, non-stopping source fold."""

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
FIXTURE = HERE / 'no_stop_total_probe.bend'
SOURCES = {'array': 0, 'tree': 1}
MODES = {'direct': 0, 'control': 1, 'total': 2, 'composed_total': 3,
         'public_total': 4}


def expected(source, depth):
    n = 1 << depth
    return (2 * n if source == 'array'
            else n * (n + 1) + n * (n - 1) // 2) & 0xFFFFFFFF


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bend-main', type=Path, required=True)
    parser.add_argument('--depth', type=int, default=18)
    parser.add_argument('--sessions', type=int, default=40)
    parser.add_argument('--seed', type=int, default=20260925)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert 1 <= args.depth <= 20 and args.sessions > 0
    compiler = args.bend_main.resolve()
    with tempfile.TemporaryDirectory(prefix='no-stop-total-') as name:
        temp = Path(name)
        c_file = temp / 'bench.c'
        binary = temp / 'bench'
        run('bun', compiler, FIXTURE, '-o', c_file)
        run('clang', '-O3', c_file, '-o', binary)
        rng = random.Random(args.seed)
        samples = {source: {mode: [] for mode in MODES} for source in SOURCES}
        paired = []
        for _ in range(args.sessions):
            order = [(source, mode) for source in SOURCES for mode in MODES]
            rng.shuffle(order)
            session = {source: {} for source in SOURCES}
            for source, mode in order:
                result = run(binary, '--threads', '1', '--gpu', 'off', '--',
                             SOURCES[source], MODES[mode], args.depth)
                elapsed, answer = map(int, result.stdout.split())
                assert elapsed > 0 and answer == expected(source, args.depth), \
                    (source, mode, elapsed, answer)
                samples[source][mode].append(elapsed)
                session[source][mode] = elapsed
            paired.append(session)
        comparisons = {
            source: {
                'control_over_direct': [s[source]['control'] / s[source]['direct']
                                        for s in paired],
                'total_over_direct': [s[source]['total'] / s[source]['direct']
                                      for s in paired],
                'total_over_control': [s[source]['total'] / s[source]['control']
                                       for s in paired],
                'composed_total_over_direct': [
                    s[source]['composed_total'] / s[source]['direct']
                    for s in paired],
                'public_total_over_direct': [
                    s[source]['public_total'] / s[source]['direct']
                    for s in paired],
            } for source in SOURCES
        }
        allocations = {source: {} for source in SOURCES}
        for source, source_number in SOURCES.items():
            for mode, mode_number in MODES.items():
                counts = allocation_counts(c_file, temp, mode_number,
                                           expected(source, args.depth),
                                           {'only': source_number},
                                           (args.depth,))
                allocations[source][mode] = counts['only']
        report = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'compiler': str(compiler),
            'compiler_comp_sha256': hashlib.sha256(
                (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
            'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            'depth': args.depth, 'sessions': args.sessions, 'seed': args.seed,
            'samples_us': samples,
            'median_us': {source: {mode: statistics.median(values)
                                   for mode, values in modes.items()}
                          for source, modes in samples.items()},
            'paired_ratio': {
                source: {label: {
                    'median': statistics.median(values),
                    'bootstrap_95': interval(values, random.Random(
                        args.seed + i + (100 if source == 'tree' else 0))),
                } for i, (label, values) in enumerate(labels.items())}
                for source, labels in comparisons.items()},
            'heap_alloc_calls': allocations,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'median_us': report['median_us'],
                      'paired_ratio': report['paired_ratio'],
                      'heap_alloc_calls': report['heap_alloc_calls']}, indent=2))


if __name__ == '__main__':
    main()
