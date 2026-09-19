#!/usr/bin/env python3
"""Compare a library pipeline, materialized operations, and direct recursion."""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, default=ROOT.parent / 'bend/bend2/main.ts')
parser.add_argument('--samples', type=int, default=7)
args = parser.parse_args()
if args.samples < 1:
    parser.error('samples must be positive')
env = {**os.environ, 'BEND_NO_TELEMETRY': '1'}
compiler = ['bun', str(args.bend_main.resolve())]
source = (ROOT / 'bench/pipeline.bend').read_text().split('def main()')[0]
results = []
# Build programs in /tmp so the rewritten relative import has a stable base.
with tempfile.TemporaryDirectory(prefix='transduce-bench-', dir='/tmp') as directory:
    out = Path(directory)
    local_source = source.replace('import ../transduce.bend as T',
                                  'import ./' + os.path.relpath(ROOT / 'transduce.bend', out.resolve()) + ' as T')
    for label, count, take, expensive in [('cheap_full', 2000000, 2000000, False),
                                         ('cheap_early', 2000000, 32, False),
                                         ('expensive_early', 100000, 32, True)]:
        text = local_source
        value = 2
        if expensive:
            text = text.replace('  (x + 1 : U32)\n', '  work(256n, x)\n', 1)
            value = 1
            for _ in range(256):
                value = (((value * 1664525) & 0xFFFFFFFF) ^ (value >> 13)) + 1013904223
                value &= 0xFFFFFFFF
        expected = str((min(count, take) * value) & 0xFFFFFFFF) if value > 1 else '0'
        xs = f'build({count}n, [])'
        bodies = {'library': f'T.transduce(~U32, ~U32, ~pipeline(), (1, ({take}n, 0)), {xs})',
                  'materialized': f'staged({xs}, {take}n)',
                  'direct': f'direct({xs}, Running{{{take}n, 0}})'}
        builds = {}
        for name, body in bodies.items():
            file = out / (name + '.bend')
            file.write_text(text + f'def main() -> U32:\n  {body}\n#|{expected}\n')
            begin = time.perf_counter()
            build = subprocess.run(compiler + [str(file), '-o', str(out/name), '-o', str(out/(name+'.js')),
                                               '-o', str(out/(name+'.c'))], env=env, capture_output=True, text=True, timeout=60)
            assert build.returncode == 0, build.stdout + build.stderr
            builds[name] = {'seconds': time.perf_counter() - begin,
                            'c_bytes': (out/(name+'.c')).stat().st_size,
                            'js_bytes': (out/(name+'.js')).stat().st_size}
            if name == 'library':
                assert '{$: "Reducer"' not in (out/(name+'.js')).read_text(), 'callback record remained'
        names = list(bodies)
        samples = {name: [] for name in names}
        for index in range(args.samples + 1):
            order = names[index % 3:] + names[:index % 3]
            for name in order:
                begin = time.perf_counter()
                run = subprocess.run([str(out/name), '--threads', '1'], capture_output=True, text=True, timeout=30)
                elapsed = time.perf_counter() - begin
                assert run.returncode == 0 and run.stdout.strip() == expected, (name, run.stdout, run.stderr, expected)
                if index:
                    samples[name].append(elapsed)
        results.append({'case': label, 'elements': count, 'take': take, 'expected': expected,
                        'builds': builds, 'samples_seconds': samples,
                        'medians_seconds': {k: statistics.median(v) for k, v in samples.items()}})
print(json.dumps({'includes': 'startup, source construction, transformation/reduction, cleanup',
                  'threads': 1, 'results': results}, indent=2))
