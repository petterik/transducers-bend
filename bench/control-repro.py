#!/usr/bin/env python3
"""Standalone control-tag codegen reproducer; retains generated C/JS and binaries."""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--bend-main', type=Path, default=ROOT.parent / 'bend/bend2/main.ts')
p.add_argument('--samples', type=int, default=7)
a = p.parse_args()
if a.samples < 1:
    p.error('samples must be positive')
out = Path(tempfile.mkdtemp(prefix='bend-control-repro-')).resolve()
print(f'Artifacts: {out}', flush=True)
env = {**os.environ, 'BEND_NO_TELEMETRY': '1', 'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
source = (ROOT / 'bench/control-repro.bend').read_text()

def oracle(end, left, threshold):
    total = 0
    for x in range(end):
        if left == 0:
            break
        value = ((x ^ (x >> 13)) + 1) & 0xffffffff
        key = value
        for _ in range(3):
            key = (((key * 1664525) & 0xffffffff) ^ (key >> 13)) + 1013904223
            key &= 0xffffffff
        if key > threshold:
            total = (total + value) & 0xffffffff
            left -= 1
    return total

variants = {'direct': 'State{left, 0}', 'tagged': 'control(State{left, 0})',
            'guarded': 'control(State{left, 0})',
            'split': 'control(State{left, 0})'}
checks = [(0, 0, 0), (0, 4, 0), (8, 0, 0), (8, 1, 0),
          (32, 3, 2147483647), (32, 64, 2147483647), (32, 64, 4294967295)]
report = {'compiler_sha256': hashlib.sha256((a.bend_main.resolve().parent / 'comp.ts').read_bytes()).hexdigest(),
          'platform': platform.platform(),
          'timing': 'IO.now milliseconds; one warmup then samples per process, two reversed-order rounds; CPU threads=1 GPU off',
          'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
          'end': 2000000, 'take': 2000000, 'repeats': 32,
          'threshold': 2147483647, 'samples_ms': {v: [] for v in variants}}
expected = oracle(2000000, 2000000, 2147483647) * 32 & 0xffffffff
for name, state in variants.items():
    wrapper = f'''def run(+end: U32, left: Nat, threshold: U32) -> U32:
  {name}(U32.to_nat(end), 0, {state}, threshold)
'''
    test = source + wrapper + '\ndef main() -> List<U32>:\n  [' + ', '.join(
        f'run({end}, {left}n, {threshold})' for end, left, threshold in checks) + ']\n'
    test_file = out / f'{name}-check.bend'
    test_file.write_text(test)
    test_bin = out / f'{name}-check'
    subprocess.run(['bun', str(a.bend_main), str(test_file), '-o', str(test_bin), '-o', str(test_bin)+'.js'],
                   env=env, check=True, capture_output=True, text=True, timeout=60)
    want = '[' + ', '.join(str(oracle(*c)) for c in checks) + ']'
    for cmd in ([str(test_bin), '--threads', '1', '--gpu', 'off'], ['bun', str(test_bin)+'.js']):
        result = subprocess.check_output(cmd, text=True, timeout=10).strip()
        assert result == want, (name, result, want)
    program = source + wrapper + f'''
def repeat(n: Nat, sum: U32, +threshold: U32) -> U32:
  match n:
    case 0n:
      sum
    case 1n+p:
      repeat(p, (sum + run(2000000, 2000000n, threshold) : U32), threshold)

def measure(n: Nat, +threshold: U32) -> IO(Unit):
  match n:
    case 0n:
      IO.pure(Unit, Unit{{}})
    case 1n+p:
      do IO<Unit>:
        before : Nat <- IO.now()
        answer : U32 = repeat!(32n, 0, threshold)
        after : Nat <- IO.now()
        IO.print(U32.show(answer) ++ ":" ++ Nat.show(Nat.sub(after, before)))
        measure(p, threshold)

def parsed(value: Maybe<&2, U32>) -> U32:
  match value:
    case None{{}}:
      0
    case Some{{n}}:
      n

def argument(args: List<String>) -> U32:
  match args:
    case Nil{{}}:
      0
    case h <> t:
      parsed(U32.read(h))

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    measure({a.samples+1}n, argument(args))
'''
    stem = out / name
    stem.with_suffix('.bend').write_text(program)
    result = subprocess.run(['bun', str(a.bend_main), str(stem.with_suffix('.bend')),
                             '-o', str(stem), '-o', str(stem.with_suffix('.c')),
                             '-o', str(stem.with_suffix('.js'))],
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
for names in (list(variants), list(reversed(variants))):
    for name in names:
        output = subprocess.check_output([str(out/name), '--threads', '1', '--gpu', 'off', '--', '2147483647'],
                                         text=True, timeout=60)
        pairs = [list(map(int, line.split(':'))) for line in output.splitlines()]
        assert len(pairs) == a.samples+1 and all(value == expected for value, ms in pairs), (name, output)
        report['samples_ms'][name].extend(ms for _, ms in pairs[1:])
report['expected_batch_sum'] = expected
report['median_ms'] = {name: statistics.median(samples) for name, samples in report['samples_ms'].items()}
(out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
