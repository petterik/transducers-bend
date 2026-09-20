#!/usr/bin/env python3
"""Measure keep and partition against independent direct Bend loops.

This is a supplemental extension benchmark. It keeps the source construction,
configuration and cleanup in both lanes, but the direct lane implements the
specified Maybe consumption or grouping loop without importing the transducer
implementation. Results are candidate CPU measurements, not a universal
fusion claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, required=True)
parser.add_argument('--samples', type=int, default=5)
parser.add_argument('--repeats', type=int, default=8)
parser.add_argument('--cases', nargs='+',
                    choices=['keep_full', 'keep_take_32',
                             'partition_width_1', 'partition_width_8',
                             'partition_take_2'])
parser.add_argument('--output', type=Path)
parser.add_argument('--artifact-dir', type=Path)
a = parser.parse_args()
if a.samples < 1 or a.repeats < 1:
    parser.error('--samples and --repeats must be positive')

compiler = a.bend_main.resolve()
if a.artifact_dir:
    out = a.artifact_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
else:
    out = Path(tempfile.mkdtemp(prefix='bend-extension-parity-')).resolve()
shutil.copy2(ROOT / 'transduce.bend', out / 'transduce.bend')
env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}

CASES = {
    'keep_full': {'kind': 'keep', 'count': 200_000, 'budget': 200_000},
    'keep_take_32': {'kind': 'keep', 'count': 200_000, 'budget': 32},
    'partition_width_1': {'kind': 'partition', 'count': 200_000,
                          'size': 1, 'budget': 200_000},
    'partition_width_8': {'kind': 'partition', 'count': 200_000,
                          'size': 8, 'budget': 200_000},
    'partition_take_2': {'kind': 'partition', 'count': 200_000,
                         'size': 8, 'budget': 2},
}
selected = a.cases or list(CASES)

TEMPLATE = '''import Base
import {transduce_import} as T

def build(+n: Nat, xs: List<U32>) -> List<U32>:
  match n:
    case 0n:
      xs
    case 1n+p:
      build(p, U32.from_nat(p) <> xs)

def is_zero(x: U32) -> Bool:
  U32.is_zero(x)

def maybe_keep_bool(z: Bool) -> Maybe<U32>:
  match z:
    case True{{}}:
      None{{}}
    case False{{}}:
      Some{{1}}

def maybe_keep(x: U32) -> Maybe<U32>:
  maybe_keep_bool(is_zero(x))

def keep_pipeline() -> T.Reducer<U32, U32>:
  T.keep(~U32, ~U32, ~U32, ~maybe_keep,
    ~T.take(~U32, ~U32, ~T.sum()))

def keep_direct_step(xs: List<U32>, m: Maybe<U32>, +left: Nat,
  acc: U32) -> U32:
  match xs m left:
    case xs None{{}} 0n:
      acc
    case xs Some{{value}} 0n:
      acc
    case Nil{{}} None{{}} 1n+p:
      acc
    case Nil{{}} Some{{value}} 1n+p:
      (acc + value : U32)
    case h <> t None{{}} 1n+p:
      keep_direct_step(t, maybe_keep(h), 1n+p, acc)
    case h <> t Some{{value}} 1n+p:
      keep_direct_step(t, maybe_keep(h), p, (acc + value : U32))

def keep_direct(xs: List<U32>, +left: Nat, acc: U32) -> U32:
  match xs left:
    case xs 0n:
      acc
    case Nil{{}} 1n+p:
      acc
    case h <> t 1n+p:
      keep_direct_step(t, maybe_keep(h), 1n+p, acc)

def partition_pipeline() -> T.Reducer<U32, Nat>:
  T.partition_all(~U32, ~Nat,
    ~T.take(~List<U32>, ~Nat, ~T.count(~List<U32>)))

def partition_loop(xs: List<U32>, budget: Nat,
  groups: Nat, left: Nat, items: List<U32>) -> Nat:
  match xs budget left:
    case Nil{{}} 0n left:
      groups
    case Nil{{}} 1n+b left:
      match items:
        case Nil{{}}:
          groups
        case h <> t:
          1n+groups
    case h <> t 0n left:
      groups
    case h <> t 1n+b 0n:
      partition_loop(t, b, groups, {size}n, h <> items)
    case h <> t 1n+b 1n+p:
      match p:
        case 0n:
          partition_loop(t, b, 1n+groups, {size}n, [])
        case 1n+q:
          partition_loop(t, 1n+b, groups, 1n+q, h <> items)

def partition_direct(xs: List<U32>, budget: Nat,
  groups: Nat, left: Nat, items: List<U32>) -> Nat:
  partition_loop(xs, budget, groups, left, items)

def repeat(n: Nat, acc: U32) -> U32:
  match n:
    case 0n:
      acc
    case 1n+p:
      xs = build({count}n, [])
      answer = {body}
      repeat(p, (acc + answer : U32))

def measure(n: Nat) -> IO(Unit):
  match n:
    case 0n:
      IO.pure(Unit, Unit{{}})
    case 1n+p:
      do IO<Unit>:
        before : Nat <- IO.now()
        answer : U32 = repeat({repeats}n, 0)
        after : Nat <- IO.now()
        IO.print(U32.show(answer) ++ ":" ++ Nat.show(Nat.sub(after, before)))
        measure(p)

def main() -> IO(Unit):
  measure({samples_plus_one}n)
'''

def run(command, timeout=180):
    result = subprocess.run([str(x) for x in command], env=env,
                            capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result

def expected(spec):
    if spec['kind'] == 'keep':
        per_batch = min(spec['budget'], max(0, spec['count'] - 1))
    else:
        groups = (spec['count'] + spec['size'] - 1) // spec['size']
        per_batch = min(spec['budget'], groups)
    return per_batch * a.repeats

def write_program(stem, spec, lane):
    if spec['kind'] == 'keep':
        body = (f'T.transduce(~T.over_list(~U32, ~U32, ~keep_pipeline()), '
                f'({spec["budget"]}n, 0), xs)'
                if lane == 'transducers' else
                f'keep_direct(xs, {spec["budget"]}n, 0)')
    else:
        body = (f'U32.from_nat(T.transduce(~T.over_list(~U32, ~Nat, '
                f'~partition_pipeline()), ({spec["size"]}n, '
                f'({spec["budget"]}n, Unit{{}})), xs))'
                if lane == 'transducers' else
                f'U32.from_nat(partition_direct(xs, {spec["budget"]}n, '
                f'0n, {spec["size"]}n, []))')
    text = TEMPLATE.format(
        transduce_import='./transduce.bend',
        count=spec['count'], size=spec.get('size', 0), body=body, repeats=a.repeats,
        samples_plus_one=a.samples + 1)
    stem.with_suffix('.bend').write_text(text)
    return text

report = {
    'platform': platform.platform(),
    'compiler_sha256': hashlib.sha256(
        (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
    'library_sha256': hashlib.sha256(
        (ROOT / 'transduce.bend').read_bytes()).hexdigest(),
    'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'candidate compiler; sequential List source; CPU threads=1; GPU off; source construction and cleanup included',
    'timing': 'IO.now milliseconds per repeated batch; one warmup discarded',
    'samples': a.samples, 'repeats_per_sample': a.repeats,
    'artifacts': str(out), 'results': [],
}

for name in selected:
    spec = CASES[name]
    result = {'case': name, **spec, 'expected': expected(spec),
              'samples_ms': {'transducers': [], 'direct': []},
              'program_sha256': {}, 'builds': {}}
    for lane in ('transducers', 'direct'):
        stem = out / f'{name}-{lane}'
        source = write_program(stem, spec, lane)
        result['program_sha256'][lane] = hashlib.sha256(source.encode()).hexdigest()
        started = time.perf_counter()
        run(['bun', compiler, stem.with_suffix('.bend'), '-o', stem,
             '-o', stem.with_suffix('.js'), '-o', stem.with_suffix('.c')])
        result['builds'][lane] = {
            'seconds': time.perf_counter() - started,
            'c_bytes': stem.with_suffix('.c').stat().st_size,
            'js_bytes': stem.with_suffix('.js').stat().st_size,
        }
    for lane in ('transducers', 'direct'):
        stem = out / f'{name}-{lane}'
        native = run([stem, '--threads', '1', '--gpu', 'off'])
        js = run(['bun', stem.with_suffix('.js')])
        native_rows = [line.split(':') for line in native.stdout.splitlines()]
        js_rows = [line.split(':') for line in js.stdout.splitlines()]
        assert len(native_rows) == a.samples + 1
        assert len(js_rows) == a.samples + 1
        assert [value for value, _ in native_rows] == [value for value, _ in js_rows]
        assert all(int(value) == result['expected'] for value, _ in native_rows), (
            name, lane, native.stdout, result['expected'])
        result['samples_ms'][lane].extend(int(ms) for _, ms in native_rows[1:])
    result['median_ms'] = {lane: statistics.median(values)
                           for lane, values in result['samples_ms'].items()}
    direct = result['median_ms']['direct']
    result['ratio_transducer_over_direct'] = (
        result['median_ms']['transducers'] / direct if direct else None)
    report['results'].append(result)
    print(name, result['median_ms'],
          f"ratio={result['ratio_transducer_over_direct']}", flush=True)

text = json.dumps(report, indent=2) + '\n'
if a.output:
    a.output.write_text(text)
print(text)
