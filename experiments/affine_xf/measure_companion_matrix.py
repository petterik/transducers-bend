#!/usr/bin/env python3
"""Paired native timing and timed allocations for the companion API matrix."""

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
FIXTURE = HERE / 'companion_matrix_bench.bend'
MODES = {
    'keep_direct': 0, 'keep_static': 1, 'keep_generic': 2,
    'mapcat_direct': 3, 'mapcat_static': 4, 'mapcat_generic': 5,
    'array_direct': 6, 'array_generic': 7,
    'retain_direct': 8, 'retain_generic': 9,
    'take_pair_direct': 10, 'take_after_generic': 11,
    'take_before_generic': 12,
    'custom_direct': 13, 'custom_generic': 14,
}
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
    parser.add_argument('--array-depth', type=int, default=18)
    parser.add_argument('--sessions', type=int, default=24)
    parser.add_argument('--seed', type=int, default=20260925)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert 0 < args.items < 4294967296 and args.items % 2 == 0
    assert 0 <= args.array_depth <= 30
    assert args.sessions > 0
    compiler = args.bend_main.resolve()
    rng = random.Random(args.seed)
    half = (args.items + 1) // 2
    expected = {
        'keep': (half * (half - 1)) & 0xFFFFFFFF,
        'mapcat': (args.items * (args.items + 9)) & 0xFFFFFFFF,
        'array': (2 * (1 << args.array_depth)) & 0xFFFFFFFF,
        'take': ((args.items // 2) * (args.items // 2 + 9)) & 0xFFFFFFFF,
        'custom': (args.items * (args.items + 1) // 2) & 0xFFFFFFFF,
    }
    with tempfile.TemporaryDirectory(prefix='companion-matrix-') as name:
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
                lane = ('array' if mode.startswith('array') else
                        'mapcat' if mode.startswith('mapcat') else
                        'take' if mode.startswith('take') else
                        'custom' if mode.startswith('custom') else 'keep')
                size = args.array_depth if lane == 'array' else args.items
                result = run(binary, '--threads', '1', '--gpu', 'off', '--',
                             MODES[mode], size)
                elapsed, answer = map(int, result.stdout.split())
                assert answer == expected[lane] and elapsed > 0, \
                    (mode, elapsed, answer, expected[lane])
                samples[mode].append(elapsed)
                session[mode] = elapsed
            paired.append(session)
        comparisons = {
            'keep_generic_over_direct': ('keep_generic', 'keep_direct'),
            'keep_generic_over_static': ('keep_generic', 'keep_static'),
            'mapcat_generic_over_direct': ('mapcat_generic', 'mapcat_direct'),
            'mapcat_generic_over_static': ('mapcat_generic', 'mapcat_static'),
            'array_generic_over_direct': ('array_generic', 'array_direct'),
            'retain_generic_over_direct': ('retain_generic', 'retain_direct'),
            'take_after_over_direct': ('take_after_generic', 'take_pair_direct'),
            'take_before_over_direct': ('take_before_generic', 'take_pair_direct'),
            'take_after_over_before': ('take_after_generic', 'take_before_generic'),
            'custom_generic_over_direct': ('custom_generic', 'custom_direct'),
        }
        ratios = {name: [s[num] / s[den] for s in paired]
                  for name, (num, den) in comparisons.items()}
        groups = {
            'keep': {mode: MODES[mode] for mode in MODES
                     if mode.startswith(('keep', 'retain'))},
            'mapcat': {mode: MODES[mode] for mode in MODES
                       if mode.startswith('mapcat')},
            'array': {mode: MODES[mode] for mode in MODES
                      if mode.startswith('array')},
            'take': {mode: MODES[mode] for mode in MODES
                     if mode.startswith('take')},
            'custom': {mode: MODES[mode] for mode in MODES
                       if mode.startswith('custom')},
        }
        alloc = {}
        for lane, modes in groups.items():
            size = args.array_depth if lane == 'array' else args.items
            alloc.update(allocation_counts(c_file, temp, size,
                                           expected[lane], modes))
        report = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'compiler': str(compiler),
            'compiler_comp_sha256': hashlib.sha256(
                (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
            'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            'items': args.items, 'array_depth': args.array_depth,
            'sessions': args.sessions, 'seed': args.seed,
            'expected': expected,
            'generated_c_bytes': c_file.stat().st_size,
            'samples_us': samples,
            'median_us': {mode: statistics.median(times)
                          for mode, times in samples.items()},
            'paired_ratio': {key: {
                'median': statistics.median(values),
                'bootstrap_95': interval(values, random.Random(args.seed + i)),
            } for i, (key, values) in enumerate(ratios.items())},
            'heap_alloc_calls': alloc,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({key: report[key] for key in
            ('median_us', 'paired_ratio', 'heap_alloc_calls')}, indent=2))


if __name__ == '__main__':
    main()
