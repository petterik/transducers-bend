#!/usr/bin/env python3
"""Compare full List windows, tuple windows, and a direct adjacent fold."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import re
import statistics
import subprocess
import tempfile

from public_list_map_fold import command, instrument_allocations

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'bench/windows2.bend'
MODES = {0: 'direct', 1: 'windows2_list', 2: 'window2_tuple'}


def sample(binary, mode, size):
    result = subprocess.run([str(binary), '--threads', '1', '--gpu', 'off',
                             '--', str(mode), str(size)], cwd=ROOT,
                            capture_output=True, text=True, check=True)
    elapsed, value = map(int, result.stdout.split())
    assert value == ((size - 1) ** 2) % (1 << 32), (mode, size, value)
    return elapsed


def allocations(binary, mode, size):
    result = subprocess.run([str(binary), '--threads', '1', '--gpu', 'off',
                             '--', str(mode), str(size)], cwd=ROOT,
                            capture_output=True, text=True, check=True)
    assert int(result.stdout.split()[1]) == ((size - 1) ** 2) % (1 << 32)
    match = re.search(r'ALLOC all=(\d+) timed=(\d+) ticks=(\d+)', result.stderr)
    assert match and int(match.group(3)) == 2, result.stderr
    return {'total_heap_alloc_calls': int(match.group(1)),
            'timed_heap_alloc_calls': int(match.group(2))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sessions', type=int, default=24)
    parser.add_argument('--sizes', type=int, nargs='+', default=[65536, 262144])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    assert args.sessions > 0 and all(size > 0 for size in args.sizes)
    with tempfile.TemporaryDirectory(prefix='windows2-bench-') as name:
        temp = Path(name)
        generated = temp / 'windows2.c'
        binary = temp / 'windows2'
        command('bun', ROOT.parent / 'bend/bend2/main.ts', FIXTURE,
                '-o', generated)
        command('clang', '-O3', generated, '-o', binary)
        instrumented = temp / 'windows2-instrumented.c'
        instrumented.write_text(instrument_allocations(generated.read_text()))
        alloc_binary = temp / 'windows2-instrumented'
        command('clang', '-O3', instrumented, '-o', alloc_binary)
        report = {
            'compiler_commit': command('git', '-C', ROOT.parent / 'bend',
                                       'rev-parse', 'HEAD'),
            'library_base_commit': command('git', 'rev-parse', 'HEAD'),
            'library_worktree_dirty': bool(command('git', 'status', '--porcelain')),
            'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            'platform': platform.platform(),
            'clock': 'native monotonic microseconds; input built before timer',
            'allocation_metric': 'generated C heap_alloc calls inside timer',
            'sessions': args.sessions,
            'results': {},
        }
        for size in args.sizes:
            timings = {name: [] for name in MODES.values()}
            for session in range(args.sessions):
                order = list(MODES)
                random.Random(20260925 + size + session).shuffle(order)
                for mode in order:
                    timings[MODES[mode]].append(sample(binary, mode, size))
            report['results'][str(size)] = {
                'timings_us': timings,
                'medians_us': {name: statistics.median(values)
                               for name, values in timings.items()},
                'allocations': {name: allocations(alloc_binary, mode, size)
                                for mode, name in MODES.items()},
            }
    payload = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.write_text(payload)
    print(payload)


if __name__ == '__main__':
    main()
