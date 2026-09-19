#!/usr/bin/env python3
"""CPU thread/GPU comparison: serial lists and independent balanced batches."""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import statistics
import subprocess
import sys
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
p.add_argument('--bend-main', type=Path, help='Compiler entry point (defaults to sibling Bend checkout)')
p.add_argument('--out', type=Path, default=Path('/tmp/transduce-parallel-build'))
p.add_argument('--samples', type=int, default=7)
p.add_argument('--cases', nargs='+', default=['serial_full', 'serial_early', 'batch_full_12', 'batch_full_14', 'batch_early_14'])
p.add_argument('--threads', nargs='*', type=int, default=[1, 2, 4, 8, 16], help='Empty list runs GPU only')
p.add_argument('--gpu', action=argparse.BooleanOptionalAction, default=True)
p.add_argument('--rounds', type=int, default=2, help='Interleaved process rounds; each discards its first sample')
p.add_argument('--work', type=int, default=256, help='Nonlinear U32 rounds per mapped element')
a = p.parse_args()
assert a.samples > 0 and a.rounds > 0 and a.work >= 0
assert a.gpu or a.threads, 'Select at least one execution mode'
assert all(t > 0 for t in a.threads)
root = a.root.resolve()
out = a.out.resolve()
out.mkdir(parents=True, exist_ok=True)
env = {**os.environ, 'BEND_NO_TELEMETRY': '1', 'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
source = (root/'bench/pipeline.bend').read_text().split('def main()')[0]
source = source.replace('import ../transduce.bend as T', 'import ./'+os.path.relpath(root/'transduce.bend', out)+' as T')
source = source.replace('  (x + 1 : U32)\n', f'  work({a.work}n, x)\n', 1)
value = 1
for _ in range(a.work):
    value = ((((value * 1664525) & 0xffffffff) ^ (value >> 13)) + 1013904223) & 0xffffffff
cases = {'serial_full': (0, 100000, 100000), 'serial_early': (0, 100000, 32),
         'batch_full_12': (12, 64, 64), 'batch_full_14': (14, 64, 64), 'batch_early_14': (14, 64, 8),
         'batch_long_full_14': (14, 256, 256), 'batch_long_early_14': (14, 256, 8)}
report = {'timing': 'IO.now milliseconds; excludes process/GPU startup, includes source construction and cleanup',
          'semantics': 'Independent list reductions; take resets at every leaf. Not a parallel global take.',
          'rounds': a.rounds, 'samples_per_round': a.samples, 'results': []}
report['work_rounds'] = a.work
report['platform'] = platform.platform()
report['compiler_sha256'] = hashlib.sha256(((a.bend_main or root.parent/'bend/bend2/main.ts').resolve().parent/'comp.ts').read_bytes()).hexdigest()
report['cpu_count'] = os.cpu_count()
for case in a.cases:
    depth, count, take = cases[case]
    expected = (value * min(count, take) * (1 << depth)) & 0xffffffff if value > 1 else 0
    bodies = {'library': f'T.transduce(~T.over_list(~U32, ~U32, ~pipeline()), (1, ({take}n, 0)), xs)',
              'materialized': f'staged(xs, {take}n)', 'direct': f'direct(xs, Running{{{take}n, 0}})'}
    row = {'case': case, 'leaves': 1 << depth, 'elements_per_leaf': count, 'take_per_leaf': take,
           'expected': expected, 'builds': {}, 'samples_ms': {}, 'medians_ms': {}}
    for variant, body in bodies.items():
        stem = out/(case+'_'+variant)
        code = source + f'''def leaf() -> U32:
  xs = build({count}n, [])
  {body}

def batch(+depth: Nat) -> U32:
  match depth:
    case 0n:
      leaf()
    case 1n+p:
      a b = batch(p) batch(p)
      (a + b : U32)

def measure(n: Nat) -> IO(Unit):
  match n:
    case 0n:
      IO.pure(Unit, Unit{{}})
    case 1n+p:
      do IO<Unit>:
        before : Nat <- IO.now()
        answer : U32 = batch!({depth}n)
        after : Nat <- IO.now()
        IO.print(U32.show(answer) ++ ":" ++ Nat.show(Nat.sub(after, before)))
        measure(p)

def main() -> IO(Unit):
  measure({a.samples+1}n)
'''
        stem.with_suffix('.bend').write_text(code)
        start = time.perf_counter()
        r = subprocess.run(['bun', str((a.bend_main or root.parent/'bend/bend2/main.ts').resolve()), str(stem.with_suffix('.bend')),
                            '-o', str(stem), '-o', str(stem.with_suffix('.c')), '-o', str(stem.with_suffix('.js'))],
                           env=env, capture_output=True, text=True, timeout=240)
        assert r.returncode == 0, r.stdout+r.stderr
        if variant == 'library':
            assert '{$: "Reducer"' not in stem.with_suffix('.js').read_text()
        gpu_file = stem.with_suffix('.gpu')
        row['builds'][variant] = {'seconds': time.perf_counter()-start,
                                 'gpu_bytes': gpu_file.stat().st_size if gpu_file.exists() else 0}
    modes = [(f'cpu_{t}', ['--threads', str(t), '--gpu', 'off']) for t in a.threads]
    if a.gpu:
        modes.append(('gpu', ['--threads', '1', '--gpu', '1GB']))
    jobs = [(mode, flags, variant) for mode, flags in modes for variant in bodies]
    for round_index in range(a.rounds):
        for mode, flags, variant in (jobs if round_index % 2 == 0 else reversed(jobs)):
            stem = out/(case+'_'+variant)
            r = subprocess.run([str(stem), *flags], capture_output=True, text=True, timeout=180)
            assert r.returncode == 0, (case, mode, variant, r.stdout, r.stderr)
            pairs = [line.split(':') for line in r.stdout.splitlines()]
            assert len(pairs) == a.samples+1 and all(int(v)==expected for v, _ in pairs), r.stdout
            key = mode+'/'+variant
            row['samples_ms'].setdefault(key, []).extend(int(t) for _, t in pairs[1:])
            print(case, round_index, key, [int(t) for _, t in pairs[1:]], file=sys.stderr, flush=True)
    row['medians_ms'] = {k: statistics.median(v) for k,v in row['samples_ms'].items()}
    report['results'].append(row)
    (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
