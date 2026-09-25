#!/usr/bin/env python3
"""Compare a mixed five-stage affine pipeline with equivalent direct Bend."""

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
FIXTURE = HERE / 'mixed_pipeline_bench.bend'
MODES = {'direct': 0, 'static': 1, 'generic': 2}
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
    parser.add_argument('--items', type=int, default=2000000)
    parser.add_argument('--sessions', type=int, default=32)
    parser.add_argument('--seed', type=int, default=20260925)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert 0 < args.items < 4294967296 and args.sessions > 0
    expected = sum(x + 2 for x in range(1, args.items + 1)
                   if x % 2 == 0 and x % 3 != 0) & 0xFFFFFFFF
    rng = random.Random(args.seed)

    with tempfile.TemporaryDirectory(prefix='mixed-affine-measure-') as name:
        temp = Path(name)
        c_file = temp / 'bench.c'
        binary = temp / 'bench'
        run('bun', args.bend_main.resolve(), FIXTURE, '-o', c_file)
        run('clang', '-O3', c_file, '-o', binary)
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
                samples[mode].append(elapsed)
                session[mode] = elapsed
            paired.append(session)
        ratios = {
            'generic_over_direct': [s['generic'] / s['direct'] for s in paired],
            'generic_over_static': [s['generic'] / s['static'] for s in paired],
            'static_over_direct': [s['static'] / s['direct'] for s in paired],
        }
        report = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'compiler': str(args.bend_main.resolve()),
            'compiler_comp_sha256': hashlib.sha256(
                (args.bend_main.resolve().parent / 'comp.ts').read_bytes()
            ).hexdigest(),
            'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            'items': args.items, 'sessions': args.sessions, 'seed': args.seed,
            'expected': expected,
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
            ('median_us', 'paired_ratio', 'heap_alloc_calls')}, indent=2))


if __name__ == '__main__':
    main()
