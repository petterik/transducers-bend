#!/usr/bin/env python3
"""Compare composed maps and filtering with handwritten and Base.List pipelines."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--samples', type=int, default=5)
p.add_argument('--output', type=Path)
p.add_argument('--artifact-dir', type=Path,
               help='Preserve generated Bend/C/JS/native artifacts in a new directory')
p.add_argument('--bend-main', type=Path, default=ROOT.parent / 'bend/bend2/main.ts')
a = p.parse_args()
if a.samples < 1:
    p.error('samples must be positive')
a.artifact_dir = a.artifact_dir.resolve() if a.artifact_dir else None
if a.artifact_dir:
    a.artifact_dir.mkdir(parents=True, exist_ok=False)
out = a.artifact_dir or Path(tempfile.mkdtemp(prefix='transduce-composition-')).resolve()
print(out, flush=True)
env = {**os.environ, 'BEND_NO_TELEMETRY': '1', 'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
compiler = a.bend_main.resolve()
source_path = ROOT / 'bench/scalar_prototype.bend'
source = source_path.read_text().split('def main()')[0]
source = source.replace('import ../transduce.bend as T',
                        'import ./' + os.path.relpath(ROOT / 'transduce.bend', out) + ' as T')
source += '''
def inc1(x: U32) -> U32:
  (x + 1 : U32)
def inc2(x: U32) -> U32:
  (x + 2 : U32)
def inc3(x: U32) -> U32:
  (x + 3 : U32)
def inc6(x: U32) -> U32:
  (x + 6 : U32)
def chain() -> T.Reducer<U32, U32>:
  T.map(~U32, ~U32, ~U32, ~inc1,
    ~T.map(~U32, ~U32, ~U32, ~inc2,
      ~T.map(~U32, ~U32, ~U32, ~inc3, ~T.sum())))
def single() -> T.Reducer<U32, U32>:
  T.map(~U32, ~U32, ~U32, ~inc6, ~T.sum())
def build(+n: Nat, xs: List<U32>) -> List<U32>:
  match n:
    case 0n:
      xs
    case 1n+p:
      build(p, U32.from_nat(p) <> xs)
def direct_list(xs: List<U32>, state: Running, +threshold: U32) -> U32:
  match xs state:
    case xs Running{0n, acc}:
      acc
    case Nil{} Running{left, acc}:
      acc
    case h <> t Running{1n+p, acc}:
      direct_list(t, feed(threshold, 1n+p, acc, transform(h)), threshold)
def direct_chain(xs: List<U32>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case h <> t:
      direct_chain(t, (acc + inc6(h) : U32))
# Base.List.map returns List<&1,U32>, but Base.List.filter needs List<&2,U32>.
# Same recursive map, with the result kind required by the existing filter.
def mapped_data(xs: List<U32>) -> List<&2, U32>:
  match xs:
    case Nil{}:
      Nil{}
    case h <> t:
      transform(h) <> mapped_data(t)
'''
report = {
    'platform': platform.platform(),
    'compiler_sha256': hashlib.sha256((compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
    'library_sha256': hashlib.sha256((ROOT / 'transduce.bend').read_bytes()).hexdigest(),
    'prototype_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
    'scope': 'Sequential lists, construction and cleanup included; literal threshold in every variant; three_maps uses actual Base.List.map; filter cases use equivalent recursive map returning List<&2,U32> because Base.List.map returns List<&1,U32>, incompatible with Base.List.filter; actual Base.List.filter/take/foldl; early staged pipeline eagerly maps/filters all inputs',
    'timing': 'IO.now milliseconds; CPU threads=1 GPU off; warmup discarded per process; reversed second round',
    'artifacts': str(out), 'results': []}
for label, mixed, take in [('three_maps', False, 200000), ('cheap_full', False, 200000),
                           ('mixed_full', True, 200000), ('mixed_early', True, 32)]:
    count, repeats = 200000, 32
    threshold = 2147483647 if mixed else 1
    src = source.replace('  U32.is_gt(x, t)', '  U32.is_gt(work(3n, x), t)') if mixed else source
    xs = f'build({count}n, [])'
    config = f'({threshold}, ({take}n, 0))'
    if label == 'three_maps':
        bodies = {name: f'T.transduce(~T.over_list(~U32, ~U32, ~{fun}()), 0, {xs})'
                  for name, fun in [('transducers', 'chain'), ('single_map', 'single')]}
        bodies['handwritten'] = f'direct_chain({xs}, 0)'
        mapped = f'List.map(~U32, ~U32, ~inc3, List.map(~U32, ~U32, ~inc2, List.map(~U32, ~U32, ~inc1, {xs})))'
        bodies['base_list'] = f'List.foldl(~&1, ~U32, ~U32, ~U32.add, {mapped}, 0)'
        expected = sum(range(6, count + 6)) * repeats & 0xffffffff
    else:
        bodies = {name: f'T.transduce(~T.over_list(~U32, ~U32, ~{fun}()), {config}, {xs})'
                  for name, fun in [('transducers', 'base_pipeline'), ('scalar_prototype', 'pipeline')]}
        bodies['handwritten'] = f'direct_list({xs}, Running{{{take}n, 0}}, {threshold})'
        mapped = f'mapped_data({xs})'
        filtered = f'List.filter(~U32, ~(x => above({threshold}, x)), {mapped})'
        bodies['base_compatible'] = f'List.foldl(~&2, ~U32, ~U32, ~U32.add, List.take(&2, U32, {filtered}, {take}n), 0)'
        total = accepted = 0
        for i in range(count):
            if accepted == take:
                break
            x = ((i ^ (i >> 13)) + 1) & 0xffffffff
            key = x
            if mixed:
                for _ in range(3):
                    key = ((((key * 1664525) & 0xffffffff) ^ (key >> 13)) + 1013904223) & 0xffffffff
            if key > threshold:
                total = (total + x) & 0xffffffff
                accepted += 1
        expected = total * repeats & 0xffffffff
    row = {'case': label, 'count': count, 'take': take, 'repeats': repeats,
           'expected': expected, 'samples_ms': {name: [] for name in bodies}, 'program_sha256': {}}
    for name, body in bodies.items():
        program = src + f'''
def repeat(n: Nat, acc: U32) -> U32:
  match n:
    case 0n:
      acc
    case 1n+p:
      repeat(p, (acc + {body} : U32))
def measure(n: Nat) -> IO(Unit):
  match n:
    case 0n:
      IO.pure(Unit, Unit{{}})
    case 1n+p:
      do IO<Unit>:
        before : Nat <- IO.now()
        answer : U32 = repeat!({repeats}n, 0)
        after : Nat <- IO.now()
        IO.print(U32.show(answer) ++ ":" ++ Nat.show(Nat.sub(after, before)))
        measure(p)
def main() -> IO(Unit):
  measure({a.samples + 1}n)
'''
        stem = out / (label + '-' + name)
        stem.with_suffix('.bend').write_text(program)
        row['program_sha256'][name] = hashlib.sha256(program.encode()).hexdigest()
        build = subprocess.run(['bun', str(compiler), str(stem.with_suffix('.bend')),
                                '-o', str(stem), '-o', str(stem.with_suffix('.c'))],
                               env=env, capture_output=True, text=True, timeout=60)
        assert build.returncode == 0, build.stdout + build.stderr
    for names in (list(bodies), list(reversed(bodies))):
        for name in names:
            output = subprocess.check_output([str(out / (label + '-' + name)), '--threads', '1', '--gpu', 'off'],
                                             text=True, timeout=60)
            pairs = [list(map(int, line.split(':'))) for line in output.splitlines()]
            assert len(pairs) == a.samples + 1 and all(v == expected for v, ms in pairs), (label, name, output, expected)
            row['samples_ms'][name].extend(ms for v, ms in pairs[1:])
    row['medians_ms'] = {name: statistics.median(values) for name, values in row['samples_ms'].items()}
    report['results'].append(row)
    print(row['case'], row['medians_ms'], flush=True)
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    if a.output:
        a.output.write_text(json.dumps(report, indent=2) + '\n')
