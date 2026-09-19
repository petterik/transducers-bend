#!/usr/bin/env python3
"""Compile the candidate and two baselines; run a small native comparison."""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path,
                    default=HERE.parents[2] / 'bend' / 'bend2' / 'main.ts')
parser.add_argument('--size', type=int, default=2_000_000)
parser.add_argument('--samples', type=int, default=7)
args = parser.parse_args()
if not 0 <= args.size <= 0xFFFFFFFF or args.samples < 1:
    parser.error('size must fit U32 and samples must be positive')
if not args.bend_main.is_file():
    parser.error('Bend checkout not found; pass --bend-main /path/to/bend2/main.ts')
env = {**os.environ, 'BEND_NO_TELEMETRY': '1'}
compiler = ['bun', str(args.bend_main.resolve())]
source = (HERE / 'probe.bend').read_text().split('def main()')[0]
source += '''def build(n: Nat, xs: List<U32>) -> List<U32>:
  match n:
    case 0n:
      xs
    case 1n+p:
      build(p, 1 <> xs)

def direct(xs: List<U32>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case h <> t:
      direct(t, (acc + (h + 1 : U32) : U32))

def mapped_step(acc: U32, x: U32) -> U32:
  (acc + (x + 1 : U32) : U32)

def static_step(acc: U32, x: U32) -> Control<U32>:
  Continue{(acc + (x + 1 : U32) : U32)}

def callbacks(~A: Type, ~S: Type, ~R: Type,
  ~advance: S -> A -> Control<S>, ~done: S -> R,
  xs: List<A>, c: Control<S>) -> R:
  match xs c:
    case Nil{} Continue{s}:
      done(s)
    case Nil{} Stop{s}:
      done(s)
    case h <> t Stop{s}:
      done(s)
    case h <> t Continue{s}:
      callbacks(~A, ~S, ~R, ~advance, ~done, t, advance(s, h))

'''
xs = f'build({args.size}n, Nil{{}})'
bodies = {
    'record': f'transduce(~U32, ~U32, ~pipeline(), 0, {xs})',
    'direct': f'direct({xs}, 0)',
    'callbacks': f'callbacks(~U32, ~U32, ~U32, ~static_step, ~(s => s), {xs}, Continue{{0}})',
    'template': f'List.foldl(~&1, ~U32, ~U32, ~mapped_step, {xs}, 0)',
}
expected = str((args.size * 2) & 0xFFFFFFFF)
with tempfile.TemporaryDirectory(prefix='transduce-static-reducer-') as directory:
    out = Path(directory)
    diagnostics = {}
    # Validate the small example on both backends, separately from benchmarking.
    probe = out / 'probe.bend'
    probe.write_text((HERE / 'probe.bend').read_text())
    subprocess.run(compiler + [str(probe), '-o', str(out / 'probe'),
                               '-o', str(out / 'probe.js')], env=env, check=True)
    for command in [['node', str(out / 'probe.js')],
                    [str(out / 'probe'), '--threads', '1']]:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        assert result.stdout.strip() == '9', result.stdout
    for name, body in bodies.items():
        file = out / (name + '.bend')
        file.write_text(source + f'def main() -> U32:\n  {body}\n#|{expected}\n')
        result = subprocess.run(compiler + [str(file), '-o', str(out / name),
                                 '-o', str(out / (name + '.js')),
                                 '-o', str(out / (name + '.c'))],
                                env=env, capture_output=True, text=True, check=True)
        diagnostics[name] = (result.stdout + result.stderr).strip()
    samples = {name: [] for name in bodies}
    names = list(bodies)
    for index in range(args.samples + 1):
        order = names[index % len(names):] + names[:index % len(names)]
        for name in order:
            before = time.perf_counter()
            result = subprocess.run([str(out / name), '--threads', '1'],
                                    capture_output=True, text=True, check=True)
            elapsed = time.perf_counter() - before
            assert result.stdout.strip() == expected, (name, result.stdout)
            if index:  # one warm-up per candidate
                samples[name].append(elapsed)
    print(json.dumps({
        'elements': args.size,
        'expected': expected,
        'includes': 'process startup, source construction, traversal, cleanup',
        'small_probe': 'JS and native returned 9',
        'compiler_diagnostics': diagnostics,
        'medians_seconds': {k: statistics.median(v) for k, v in samples.items()},
        'samples_seconds': samples,
    }, indent=2))
