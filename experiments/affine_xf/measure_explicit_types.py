#!/usr/bin/env python3
"""Paired native microsecond comparison of explicit Xf, current T, and direct."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import statistics
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / 'explicit_reducer_bench.bend'
MODES = {'direct': 0, 'current_transducer': 1, 'explicit_xf': 2,
         'composed_xf': 3, 'staged_xf': 4}
ENV = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}


def run(*args):
    result = subprocess.run([str(arg) for arg in args], env=ENV,
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result


def interval(values, rng):
    medians = sorted(statistics.median(
        values[rng.randrange(len(values))] for _ in values)
        for _ in range(10000))
    return [medians[249], medians[9749]]


def allocation_counts(c_source, temp, items, expected, modes=None):
    source = c_source.read_text()
    heap_anchor = 'INLINE Loc heap_alloc(Env e, Cls cls) {\n'
    tick_anchor = 'static u64 io_tick(void) {\n'
    exit_anchor = '  io_sync();\n  return code;'
    assert source.count(heap_anchor) == 1
    assert source.count(tick_anchor) == 1
    assert source.count(exit_anchor) == 1
    source = source.replace(heap_anchor,
        'static u64 stats_total_alloc = 0, stats_timed_alloc = 0;\n'
        'static u32 stats_ticks = 0;\n'
        'static bool stats_in_timed = false;\n'
        + heap_anchor + '  stats_total_alloc++;\n'
        '  if (stats_in_timed) stats_timed_alloc++;\n', 1)
    source = source.replace(tick_anchor,
        tick_anchor + '  if (stats_ticks == 0) stats_in_timed = true;\n'
        '  else if (stats_ticks == 1) stats_in_timed = false;\n'
        '  stats_ticks++;\n', 1)
    source = source.replace(exit_anchor,
        '  io_sync();\n'
        '  fprintf(stderr, "ALLOC_STATS total=%llu timed=%llu ticks=%u\\n", '
        '(unsigned long long)stats_total_alloc, '
        '(unsigned long long)stats_timed_alloc, stats_ticks);\n'
        '  return code;', 1)
    inst_c = temp / 'bench-alloc.c'
    inst_binary = temp / 'bench-alloc'
    inst_c.write_text(source)
    run('clang', '-O3', inst_c, '-o', inst_binary)
    counts = {}
    for name, mode in (MODES if modes is None else modes).items():
        result = run(inst_binary, '--threads', '1', '--gpu', 'off', '--',
                     mode, items)
        _, answer = map(int, result.stdout.split())
        assert answer == expected
        match = re.search(r'ALLOC_STATS total=(\d+) timed=(\d+) ticks=(\d+)',
                          result.stderr)
        assert match and int(match.group(3)) == 2, result.stderr
        counts[name] = {'total': int(match.group(1)),
                        'timed': int(match.group(2))}
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bend-main', type=Path, required=True)
    parser.add_argument('--items', type=int, default=200000)
    parser.add_argument('--sessions', type=int, default=40)
    parser.add_argument('--seed', type=int, default=20260925)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert 0 < args.items < 4294967296 and args.sessions > 0
    compiler = args.bend_main.resolve()
    rng = random.Random(args.seed)
    expected = (args.items * (args.items + 1) // 2) & 0xFFFFFFFF
    with tempfile.TemporaryDirectory(prefix='affine-xf-measure-') as temp_name:
        temp = Path(temp_name)
        c_file = temp / 'bench.c'
        binary = temp / 'bench'
        run('bun', compiler, FIXTURE, '-o', c_file)
        run('clang', '-O3', c_file, '-o', binary)
        samples = {name: [] for name in MODES}
        paired = []
        for _ in range(args.sessions):
            names = list(MODES)
            rng.shuffle(names)
            session = {}
            for name in names:
                result = run(binary, '--threads', '1', '--gpu', 'off', '--',
                             MODES[name], args.items)
                elapsed, answer = map(int, result.stdout.split())
                assert answer == expected, (name, answer, expected)
                assert elapsed > 0, (name, elapsed)
                session[name] = elapsed
                samples[name].append(elapsed)
            paired.append(session)
        ratios = {
            'current_over_direct': [s['current_transducer'] / s['direct']
                                    for s in paired],
            'explicit_over_direct': [s['explicit_xf'] / s['direct']
                                     for s in paired],
            'explicit_over_current': [s['explicit_xf'] / s['current_transducer']
                                      for s in paired],
            'composed_over_current': [s['composed_xf'] / s['current_transducer']
                                      for s in paired],
            'staged_over_current': [s['staged_xf'] / s['current_transducer']
                                    for s in paired],
        }
        report = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'compiler': str(compiler),
            'compiler_comp_sha256': hashlib.sha256(
                (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
            'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            'items': args.items, 'sessions': args.sessions, 'seed': args.seed,
            'expected': expected,
            'samples_us': samples,
            'median_us': {name: statistics.median(times)
                          for name, times in samples.items()},
            'paired_ratio': {name: {
                'median': statistics.median(values),
                'bootstrap_95': interval(values, random.Random(args.seed + i)),
            } for i, (name, values) in enumerate(ratios.items())},
            'heap_alloc_calls': allocation_counts(c_file, temp, args.items,
                                                  expected),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'median_us': report['median_us'],
                          'paired_ratio': report['paired_ratio'],
                          'heap_alloc_calls': report['heap_alloc_calls']},
                         indent=2))


if __name__ == '__main__':
    main()
