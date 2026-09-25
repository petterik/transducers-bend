#!/usr/bin/env python3
"""Attribute non-transducer compiler cost using isolated upstream/fork mixtures."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import tempfile
import time

from check_fork_regression import ROOT, BEND, ENV, git, upstream_compiler


HERE = Path(__file__).resolve().parent
VARIANTS = {
    'upstream': (),
    'static_inert': ('comp.ts',),
    'static_only': ('comp.ts',),
    'checker_only': ('bend.ts', 'main.ts'),
    'fork': ('bend.ts', 'comp.ts', 'main.ts'),
}


def fixtures(ref):
    listed = git('ls-tree', '-r', '--name-only', ref, 'tests').decode().splitlines()
    positive = []
    for name in sorted(listed):
        path = BEND / name
        if not name.endswith('.bend') or not path.is_file():
            continue
        want = '\n'.join(line[2:] for line in path.read_text().splitlines()
                         if line.startswith('#|'))
        if want and not want.startswith('Error:'):
            positive.append(path)
    return positive


def run(compiler, tail):
    before = time.perf_counter_ns()
    result = subprocess.run(['bun', str(compiler), *(str(x) for x in tail)],
                            env=ENV, capture_output=True, text=True,
                            timeout=90)
    return (time.perf_counter_ns() - before) / 1e6, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream-ref', default='bendlang/main')
    parser.add_argument('--sessions', type=int, default=20)
    parser.add_argument('--seed', type=int, default=20260925)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert args.sessions > 0
    positive = fixtures(args.upstream_ref)
    assert len(positive) >= 160
    with tempfile.TemporaryDirectory(prefix='.compiler-ablation-', dir=ROOT) as name:
        temp = Path(name)
        upstream = upstream_compiler(temp, args.upstream_ref)
        compilers = {'upstream': upstream}
        for variant, files in VARIANTS.items():
            if variant == 'upstream':
                continue
            target = temp / variant
            shutil.copytree(upstream.parent, target)
            for file in files:
                shutil.copy2(BEND / 'bend2' / file, target / file)
            if variant == 'static_inert':
                comp = target / 'comp.ts'
                source = comp.read_text()
                live = '''Bend.term_higher(Bend.term_lower(
      specialize(cb.book, Bend.term_higher(tld.e))))'''
                assert source.count(live) == 1
                comp.write_text(source.replace(live, 'Bend.term_higher(tld.e)'))
            compilers[variant] = target / 'main.ts'
        scratch = temp / 'fixtures'
        scratch.mkdir()
        simple = scratch / 'simple.bend'
        simple.write_text('import Base\ndef main() -> U32:\n  7\n')
        modes = {'simple': [simple, '--checkup'],
                 'array': [ROOT / 'tests/array.bend', '-o', scratch / 'array.js'],
                 'pipeline': [ROOT / 'tests/pipeline.bend', '-o', scratch / 'pipeline.js']}
        for count in (80, 160):
            group = scratch / f'group{count}.bend'
            group.write_text(''.join(
                f'import {os.path.relpath(path, group.parent)} as timing_{i}\n'
                for i, path in enumerate(positive[:count])))
            modes[f'group{count}'] = [group, '--checkup']
        samples = {mode: {name: [] for name in VARIANTS} for mode in modes}
        rng = random.Random(args.seed)
        for mode, tail in modes.items():
            expected = None
            for variant in VARIANTS:
                _, result = run(compilers[variant], tail)
                assert result.returncode == 0, (mode, variant, result.stderr)
                # Compile output is written to the same temporary file. The
                # checkup lanes must have exactly the same observations.
                if '--checkup' in tail:
                    observed = (result.stdout, result.stderr)
                    expected = observed if expected is None else expected
                    assert observed == expected, (mode, variant, observed, expected)
            for _ in range(args.sessions):
                order = list(VARIANTS)
                rng.shuffle(order)
                for variant in order:
                    elapsed, result = run(compilers[variant], tail)
                    assert result.returncode == 0, (mode, variant, result.stderr)
                    samples[mode][variant].append(elapsed)
        medians = {mode: {variant: statistics.median(values)
                          for variant, values in lanes.items()}
                   for mode, lanes in samples.items()}
        report = {
            'upstream_ref': args.upstream_ref,
            'fork_head': git('rev-parse', 'HEAD').decode().strip(),
            'fork_modified': bool(git('status', '--porcelain').strip()),
            'compiler_sha256': {
                variant: {file: hashlib.sha256((compiler.parent / file)
                                               .read_bytes()).hexdigest()
                          for file in ('bend.ts', 'comp.ts', 'main.ts')}
                for variant, compiler in compilers.items()},
            'sessions': args.sessions, 'seed': args.seed,
            'samples_ms': samples, 'median_ms': medians,
            'ratio_to_upstream': {
                mode: {variant: medians[mode][variant] / medians[mode]['upstream']
                       for variant in VARIANTS if variant != 'upstream'}
                for mode in modes},
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'median_ms': report['median_ms'],
                      'ratio_to_upstream': report['ratio_to_upstream']},
                     indent=2))


if __name__ == '__main__':
    main()
