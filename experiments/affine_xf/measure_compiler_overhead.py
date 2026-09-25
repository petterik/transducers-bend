#!/usr/bin/env python3
"""Measure process-inclusive compile/checkup cost on fork and bendlang/main."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import tempfile
import time

from check_fork_regression import ROOT, BEND, ENV, git, upstream_compiler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fork-main', type=Path,
                        default=BEND / 'bend2' / 'main.ts')
    parser.add_argument('--upstream-ref', default='bendlang/main')
    parser.add_argument('--sessions', type=int, default=25)
    parser.add_argument('--seed', type=int, default=20260925)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert args.sessions > 0
    listed = git('ls-tree', '-r', '--name-only', args.upstream_ref,
                 'tests').decode().splitlines()
    positive = []
    for name in sorted(listed):
        path = BEND / name
        if not name.endswith('.bend') or not path.is_file():
            continue
        want = '\n'.join(line[2:] for line in path.read_text().splitlines()
                         if line.startswith('#|'))
        if want and not want.startswith('Error:'):
            positive.append(path)
    with tempfile.TemporaryDirectory(prefix='compiler-overhead-') as temp:
        upstream = upstream_compiler(Path(temp), args.upstream_ref)
        with tempfile.TemporaryDirectory(prefix='.compiler-timing-',
                                         dir=ROOT) as scratch:
            scratch = Path(scratch)
            group = scratch / 'main.bend'
            group.write_text(''.join(
                f'import {os.path.relpath(path, group.parent)} as timing_{i}\n'
                for i, path in enumerate(positive[:80])))
            modes = {
                'array': [ROOT / 'tests/array.bend', '-o', scratch / 'array.js'],
                'pipeline': [ROOT / 'tests/pipeline.bend', '-o',
                             scratch / 'pipeline.js'],
                'group80': [group, '--checkup'],
            }
            rng = random.Random(args.seed)
            samples = {mode: {'upstream': [], 'fork': []} for mode in modes}
            for mode, tail in modes.items():
                for _ in range(args.sessions):
                    order = ['upstream', 'fork']
                    rng.shuffle(order)
                    for name in order:
                        compiler = upstream if name == 'upstream' \
                            else args.fork_main
                        command = ['bun', str(compiler),
                                   *(str(item) for item in tail)]
                        before = time.perf_counter_ns()
                        got = subprocess.run(command, env=ENV,
                                             capture_output=True, text=True,
                                             timeout=60)
                        elapsed = (time.perf_counter_ns() - before) / 1e6
                        assert got.returncode == 0, (mode, name, got.stderr)
                        samples[mode][name].append(elapsed)
            report = {
                'upstream_ref': args.upstream_ref,
                'fork_bend_sha256': hashlib.sha256(
                    (args.fork_main.parent / 'bend.ts').read_bytes()).hexdigest(),
                'fork_comp_sha256': hashlib.sha256(
                    (args.fork_main.parent / 'comp.ts').read_bytes()).hexdigest(),
                'sessions': args.sessions, 'seed': args.seed,
                'group_fixture_count': 80,
                'samples_ms': samples,
                'median_ms': {mode: {name: statistics.median(values)
                                     for name, values in lanes.items()}
                              for mode, lanes in samples.items()},
                'paired_fork_over_upstream': {
                    mode: statistics.median(
                        a / b for a, b in zip(lanes['fork'],
                                              lanes['upstream']))
                    for mode, lanes in samples.items()},
            }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'median_ms': report['median_ms'],
                      'paired_fork_over_upstream':
                          report['paired_fork_over_upstream']}, indent=2))


if __name__ == '__main__':
    main()
