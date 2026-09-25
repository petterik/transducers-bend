#!/usr/bin/env python3
"""Paired native timings for the opaque source protocol."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'experiments' / 'affine_xf' / 'opaque_source_perf.bend'
MODES = {
    'pair_direct': 0, 'pair_public': 1,
    'list_direct': 2, 'list_public': 3,
    'array_direct': 4, 'array_public': 5,
    'array_total': 6, 'list_total': 7,
}


def run(args, **kwargs):
    result = subprocess.run(args, capture_output=True, text=True,
                            timeout=120, check=True, **kwargs)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bend-main', type=Path,
                        default=ROOT.parent / 'bend' / 'bend2' / 'main.ts')
    parser.add_argument('--items', type=int, default=2_000_000)
    parser.add_argument('--array-depth', type=int, default=20)
    parser.add_argument('--sessions', type=int, default=25)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    assert args.items > 0 and 0 <= args.array_depth <= 25 and args.sessions > 0
    expected = {
        'pair': args.items * (args.items + 9) % (1 << 32),
        'list': args.items * (args.items + 1) // 2 % (1 << 32),
        'array': 2 * (1 << args.array_depth),
    }
    env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
           'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
    samples = {name: [] for name in MODES}
    ratios = {name: [] for name in
              ('pair_public/direct', 'list_public/direct',
               'array_public/direct', 'list_total/direct',
               'array_total/direct')}
    with tempfile.TemporaryDirectory(prefix='opaque-source-perf-') as directory:
        c_path = Path(directory) / 'bench.c'
        binary = Path(directory) / 'bench'
        run(['bun', str(args.bend_main), str(FIXTURE), '-o', str(c_path)], env=env)
        run(['clang', '-O3', str(c_path), '-o', str(binary)], env=env)
        for index in range(args.sessions):
            names = list(MODES)
            random.Random(20260925 + index).shuffle(names)
            session = {}
            for name in names:
                group = name.split('_')[0]
                count = args.array_depth if group == 'array' else args.items
                output = run([str(binary), '--threads', '1', '--gpu', 'off',
                              '--', str(MODES[name]), str(count)], env=env)
                elapsed, answer = map(int, output.split())
                assert answer == expected[group] and elapsed > 0, \
                    (name, answer, expected[group], elapsed)
                samples[name].append(elapsed)
                session[name] = elapsed
            for group in ('pair', 'list', 'array'):
                ratios[f'{group}_public/direct'].append(
                    session[f'{group}_public'] / session[f'{group}_direct'])
            for group in ('list', 'array'):
                ratios[f'{group}_total/direct'].append(
                    session[f'{group}_total'] / session[f'{group}_direct'])
    report = {
        'compiler_commit': run(['git', '-C',
                                str(args.bend_main.resolve().parent.parent),
                                'rev-parse', 'HEAD']).strip(),
        'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        'items': args.items, 'array_depth': args.array_depth,
        'sessions': args.sessions,
        'median_us': {name: statistics.median(times)
                      for name, times in samples.items()},
        'median_paired_ratio': {name: statistics.median(values)
                                for name, values in ratios.items()},
        'samples_us': samples,
    }
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('median_us', 'median_paired_ratio')},
                     indent=2))


if __name__ == '__main__':
    main()
