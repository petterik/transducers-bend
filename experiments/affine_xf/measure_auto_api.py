#!/usr/bin/env python3
"""Paired native timing and heap traffic for the inferred affine API."""

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
import time

from measure_explicit_types import allocation_counts, interval


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / 'auto_api_bench.bend'
MODES = {'direct': 0, 'current_static': 1, 'rank2_explicit': 2,
         'api_list': 3, 'api_source': 4}
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
    assert 0 < args.items < 4294967296 and args.sessions > 0
    compiler = args.bend_main.resolve()
    expected = (args.items * (args.items + 1) // 2) & 0xFFFFFFFF
    rng = random.Random(args.seed)

    with tempfile.TemporaryDirectory(prefix='auto-api-measure-') as name:
        temp = Path(name)
        c_file = temp / 'bench.c'
        binary = temp / 'bench'
        start = time.perf_counter()
        run('bun', compiler, FIXTURE, '-o', c_file)
        bend_seconds = time.perf_counter() - start
        start = time.perf_counter()
        run('clang', '-O3', c_file, '-o', binary)
        clang_seconds = time.perf_counter() - start
        samples = {mode: [] for mode in MODES}
        paired = []
        for _ in range(args.sessions):
            session = {}
            names = list(MODES)
            rng.shuffle(names)
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
            'api_list_over_current':
                [s['api_list'] / s['current_static'] for s in paired],
            'api_list_over_direct':
                [s['api_list'] / s['direct'] for s in paired],
            'api_source_over_current':
                [s['api_source'] / s['current_static'] for s in paired],
            'api_source_over_api_list':
                [s['api_source'] / s['api_list'] for s in paired],
            'api_list_over_rank2_explicit':
                [s['api_list'] / s['rank2_explicit'] for s in paired],
        }
        report = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'compiler': str(compiler),
            'compiler_comp_sha256': hashlib.sha256(
                (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
            'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            'items': args.items, 'sessions': args.sessions, 'seed': args.seed,
            'expected': expected,
            'build_seconds': {'bend': bend_seconds, 'clang': clang_seconds},
            'generated_c_bytes': c_file.stat().st_size,
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
            ('build_seconds', 'generated_c_bytes', 'median_us',
             'paired_ratio', 'heap_alloc_calls')}, indent=2))


if __name__ == '__main__':
    main()
