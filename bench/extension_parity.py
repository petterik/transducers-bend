#!/usr/bin/env python3
"""Measure equivalent transducer and direct Bend computations.

The harness calibrates a common batch size, then launches paired native runs in
alternating order across independent sessions. Every row has an independent
semantic oracle and reports a session-level bootstrap upper bound for the
predeclared 1.05 ratio target. Results are CPU observations for the selected
compiler and source shapes, not universal fusion claims.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, required=True)
parser.add_argument('--sessions', type=int, default=10)
parser.add_argument('--pairs', type=int, default=5)
parser.add_argument('--min-batch-ms', type=int, default=100)
parser.add_argument('--bootstrap', type=int, default=5000)
parser.add_argument('--seed', type=int, default=0)
parser.add_argument('--preserve-partition-group-order', action='store_true',
                    help='reverse buffered direct groups before summing them')
parser.add_argument('--samples', type=int,
                    help='legacy alias for --sessions; pairs defaults to one')
parser.add_argument('--repeats', type=int,
                    help='fixed repetitions; skips repetition calibration')
parser.add_argument('--cases', nargs='+', choices=[
    'keep_full', 'keep_take_32',
    'keep_type_change', 'keep_type_change_take_32',
    'partition_width_1', 'partition_width_8', 'partition_take_2',
    'partition_sum_width_1', 'partition_sum_width_2',
    'partition_sum_width_8', 'partition_sum_take_2'])
parser.add_argument('--output', type=Path)
parser.add_argument('--artifact-dir', type=Path)
a = parser.parse_args()
if a.samples is not None:
    a.sessions = a.samples
    if a.pairs == 5:
        a.pairs = 1
if min(a.sessions, a.pairs, a.min_batch_ms, a.bootstrap) < 1:
    parser.error('sessions, pairs, min-batch-ms and bootstrap must be positive')

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
    'keep_type_change': {'kind': 'keep_nat', 'count': 200_000,
                         'budget': 200_000},
    'keep_type_change_take_32': {'kind': 'keep_nat', 'count': 200_000,
                                 'budget': 32},
    # These retain the earlier count-only diagnostics for continuity.
    'partition_width_1': {'kind': 'partition_count', 'count': 200_000,
                          'size': 1, 'budget': 200_000},
    'partition_width_8': {'kind': 'partition_count', 'count': 200_000,
                          'size': 8, 'budget': 200_000},
    'partition_take_2': {'kind': 'partition_count', 'count': 200_000,
                         'size': 8, 'budget': 2},
    # These consume every group in both lanes, so they are the partition rows
    # eligible for a parity claim.
    'partition_sum_width_1': {'kind': 'partition_sum', 'count': 200_000,
                              'size': 1, 'budget': 200_000},
    'partition_sum_width_2': {'kind': 'partition_sum', 'count': 200_000,
                              'size': 2, 'budget': 200_000},
    'partition_sum_width_8': {'kind': 'partition_sum', 'count': 200_000,
                              'size': 8, 'budget': 200_000},
    'partition_sum_take_2': {'kind': 'partition_sum', 'count': 200_000,
                             'size': 8, 'budget': 2},
}
selected = a.cases or list(CASES)
sum_items = ('List.reverse(&1, U32, items)'
             if a.preserve_partition_group_order else 'items')
sum_completed_items = ('List.reverse(&1, U32, h <> items)'
                        if a.preserve_partition_group_order else 'h <> items')

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

def maybe_keep_nat_value(n: Nat) -> Maybe<Nat>:
  match n:
    case 0n:
      None{{}}
    case 1n+p:
      Some{{1n+p}}

def maybe_keep_nat(x: U32) -> Maybe<Nat>:
  maybe_keep_nat_value(U32.to_nat(x))

def add_nat(total: Nat, x: Nat) -> Nat:
  (total + x : Nat)

def keep_nat_pipeline() -> T.Reducer<U32, Nat>:
  T.keep(~U32, ~Nat, ~Nat, ~maybe_keep_nat,
    ~T.take(~Nat, ~Nat,
      ~T.reducing(~Nat, ~Nat, ~Nat, ~add_nat, ~(s => s))))

def keep_nat_direct_step(xs: List<U32>, m: Maybe<Nat>, +left: Nat,
  acc: Nat) -> Nat:
  match xs m left:
    case xs None{{}} 0n:
      acc
    case xs Some{{value}} 0n:
      acc
    case Nil{{}} None{{}} 1n+p:
      acc
    case Nil{{}} Some{{value}} 1n+p:
      (acc + value : Nat)
    case h <> t None{{}} 1n+p:
      keep_nat_direct_step(t, maybe_keep_nat(h), 1n+p, acc)
    case h <> t Some{{value}} 1n+p:
      keep_nat_direct_step(t, maybe_keep_nat(h), p, (acc + value : Nat))

def keep_nat_direct(xs: List<U32>, +left: Nat, acc: Nat) -> Nat:
  match xs left:
    case xs 0n:
      acc
    case Nil{{}} 1n+p:
      acc
    case h <> t 1n+p:
      keep_nat_direct_step(t, maybe_keep_nat(h), 1n+p, acc)

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

def identity_u32(x: U32) -> U32:
  x

def sum_group(xs: List<U32>, +total: U32) -> U32:
  match xs:
    case Nil{{}}:
      total
    case h <> t:
      sum_group(t, (total + h : U32))

def add_group(total: U32, group: List<U32>) -> U32:
  (total + sum_group(group, 0) : U32)

def partition_sum_pipeline() -> T.Reducer<U32, U32>:
  T.partition_all(~U32, ~U32,
    ~T.take(~List<U32>, ~U32,
      ~T.reducing(~List<U32>, ~U32, ~U32, ~add_group, ~(s => s))))

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

def partition_sum_loop(xs: List<U32>, budget: Nat,
  total: U32, left: Nat, items: List<U32>) -> U32:
  match xs budget left:
    case Nil{{}} 0n left:
      total
    case Nil{{}} 1n+b left:
      match items:
        case Nil{{}}:
          total
        case h <> t:
          (total + sum_group({sum_items}, 0) : U32)
    case h <> t 0n left:
      total
    case h <> t 1n+b 0n:
      partition_sum_loop(t, b, total, {size}n, h <> items)
    case h <> t 1n+b 1n+p:
      match p:
        case 0n:
          partition_sum_loop(t, b,
            (total + sum_group({sum_completed_items}, 0) : U32), {size}n, [])
        case 1n+q:
          partition_sum_loop(t, 1n+b, total, 1n+q, h <> items)

def partition_sum_direct(xs: List<U32>, budget: Nat,
  total: U32, left: Nat, items: List<U32>) -> U32:
  partition_sum_loop(xs, budget, total, left, items)

def repeat(n: Nat, acc: U32) -> U32:
  match n:
    case 0n:
      acc
    case 1n+p:
      xs = build({count}n, [])
      answer = {body}
      repeat(p, (acc + answer : U32))

def main() -> IO(Unit):
  do IO<Unit>:
    before : Nat <- IO.now()
    answer : U32 = repeat({repeats}n, 0)
    after : Nat <- IO.now()
    IO.print(U32.show(answer) ++ ":" ++ Nat.show(Nat.sub(after, before)))
'''


def run(command, timeout=180):
    result = subprocess.run([str(x) for x in command], env=env,
                            capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result


def expected_per_repeat(spec):
    if spec['kind'] == 'keep':
        return min(spec['budget'], max(0, spec['count'] - 1))
    if spec['kind'] == 'keep_nat':
        kept = min(spec['budget'], max(0, spec['count'] - 1))
        return sum(range(1, kept + 1)) % (1 << 32)
    if spec['kind'] == 'partition_count':
        groups = (spec['count'] + spec['size'] - 1) // spec['size']
        return min(spec['budget'], groups)
    values = min(spec['count'], spec['budget'] * spec['size'])
    return sum(range(values)) % (1 << 32)


def write_program(stem, spec, lane, repeats):
    if spec['kind'] == 'keep':
        body = (f'T.transduce(~T.over_list(~U32, ~U32, ~keep_pipeline()), '
                f'({spec["budget"]}n, 0), xs)'
                if lane == 'transducers' else
                f'keep_direct(xs, {spec["budget"]}n, 0)')
    elif spec['kind'] == 'keep_nat':
        body = (f'U32.from_nat(T.transduce(~T.over_list(~U32, ~Nat, '
                f'~keep_nat_pipeline()), ({spec["budget"]}n, 0n), xs))'
                if lane == 'transducers' else
                f'U32.from_nat(keep_nat_direct(xs, {spec["budget"]}n, 0n))')
    elif spec['kind'] == 'partition_count':
        body = (f'U32.from_nat(T.transduce(~T.over_list(~U32, ~Nat, '
                f'~partition_pipeline()), ({spec["size"]}n, '
                f'({spec["budget"]}n, Unit{{}})), xs))'
                if lane == 'transducers' else
                f'U32.from_nat(partition_direct(xs, {spec["budget"]}n, '
                f'0n, {spec["size"]}n, []))')
    else:
        body = (f'T.transduce(~T.over_list(~U32, ~U32, '
                f'~partition_sum_pipeline()), ({spec["size"]}n, '
                f'({spec["budget"]}n, 0)), xs)'
                if lane == 'transducers' else
                f'partition_sum_direct(xs, {spec["budget"]}n, 0, '
                f'{spec["size"]}n, [])')
    text = TEMPLATE.format(transduce_import='./transduce.bend',
                           count=spec['count'], size=spec.get('size', 0),
                           body=body, repeats=repeats,
                           sum_items=sum_items,
                           sum_completed_items=sum_completed_items)
    stem.with_suffix('.bend').write_text(text)
    return text


def parse_measure(output, expected):
    rows = [line.split(':') for line in output.splitlines()]
    assert len(rows) == 1 and len(rows[0]) == 2, output
    value, milliseconds = rows[0]
    assert int(value) == expected, (value, expected, output)
    return int(milliseconds)


def compile_lanes(name, spec, repeats, directory):
    stems = {}
    builds = {}
    hashes = {}
    for lane in ('transducers', 'direct'):
        stem = directory / f'{name}-{lane}'
        source = write_program(stem, spec, lane, repeats)
        hashes[lane] = hashlib.sha256(source.encode()).hexdigest()
        started = time.perf_counter()
        run(['bun', compiler, stem.with_suffix('.bend'), '-o', stem,
             '-o', stem.with_suffix('.js'), '-o', stem.with_suffix('.c')])
        builds[lane] = {
            'seconds': time.perf_counter() - started,
            'c_bytes': stem.with_suffix('.c').stat().st_size,
            'js_bytes': stem.with_suffix('.js').stat().st_size,
        }
        stems[lane] = stem
    return stems, builds, hashes


def measure(stem, expected):
    result = run([stem, '--threads', '1', '--gpu', 'off'])
    return parse_measure(result.stdout, expected)


def calibrate(name, spec, directory):
    if a.repeats is not None:
        return a.repeats, {'fixed': True, 'batches': []}
    repeats = 1
    batches = []
    while repeats <= 1_048_576:
        stems, _, _ = compile_lanes(name + '-calibration', spec, repeats,
                                    directory)
        expected = (expected_per_repeat(spec) * repeats) % (1 << 32)
        pair = {lane: measure(stems[lane], expected)
                for lane in ('transducers', 'direct')}
        batches.append({'repeats': repeats, **pair})
        if min(pair.values()) >= a.min_batch_ms:
            return repeats, {'fixed': False, 'batches': batches}
        repeats *= 2
    raise AssertionError((name, 'calibration did not reach duration floor', batches))


def geometric_mean(values):
    return math.exp(statistics.fmean(math.log(v) for v in values))


def bootstrap_upper(values, rng, count):
    estimates = []
    for _ in range(count):
        sample = [values[rng.randrange(len(values))] for _ in values]
        estimates.append(geometric_mean(sample))
    estimates.sort()
    return estimates[min(len(estimates) - 1,
                         math.ceil(0.95 * len(estimates)) - 1)]


report = {
    'platform': platform.platform(),
    'compiler_sha256': hashlib.sha256(
        (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
    'library_sha256': hashlib.sha256(
        (ROOT / 'transduce.bend').read_bytes()).hexdigest(),
    'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'candidate compiler; sequential List source; CPU threads=1; GPU off; source construction and cleanup included',
    'protocol': {
        'sessions': a.sessions, 'paired_batches_per_session': a.pairs,
        'min_batch_ms': a.min_batch_ms, 'bootstrap_resamples': a.bootstrap,
        'seed': a.seed, 'upper_ratio_target': 1.05,
        'schedule': 'paired process launches; first lane alternates by session and pair',
        'calibration_excluded': True,
    },
    'preserve_partition_group_order': a.preserve_partition_group_order,
    'artifacts': str(out), 'results': [],
}
rng = random.Random(a.seed)

for name in selected:
    spec = CASES[name]
    case_dir = out / name
    case_dir.mkdir()
    shutil.copy2(ROOT / 'transduce.bend', case_dir / 'transduce.bend')
    repeats, calibration = calibrate(name, spec, case_dir)
    stems, builds, hashes = compile_lanes(name, spec, repeats, case_dir)
    expected = (expected_per_repeat(spec) * repeats) % (1 << 32)
    # JS is a semantic check only; native processes provide the retained timing.
    for lane in ('transducers', 'direct'):
        js = run(['bun', stems[lane].with_suffix('.js')])
        assert parse_measure(js.stdout, expected) >= 0
    samples = []
    for session in range(a.sessions):
        for pair in range(a.pairs):
            first = ('transducers' if (session + pair) % 2 == 0 else 'direct')
            second = 'direct' if first == 'transducers' else 'transducers'
            times = {first: measure(stems[first], expected),
                     second: measure(stems[second], expected)}
            samples.append({'session': session, 'pair': pair, 'first': first,
                            'transducers_ms': times['transducers'],
                            'direct_ms': times['direct']})
    session_ratios = []
    unusable = []
    for session in range(a.sessions):
        rows = [r for r in samples if r['session'] == session]
        if any(r['transducers_ms'] <= 0 or r['direct_ms'] <= 0 for r in rows):
            unusable.append(session)
            continue
        trans = sum(r['transducers_ms'] for r in rows)
        direct = sum(r['direct_ms'] for r in rows)
        session_ratios.append(trans / direct)
    if session_ratios:
        estimate = geometric_mean(session_ratios)
        upper = bootstrap_upper(session_ratios, rng, a.bootstrap)
    else:
        estimate = upper = None
    enough_blocks = a.sessions >= 10 and a.pairs >= 5
    if not session_ratios or unusable or not enough_blocks:
        status = 'inconclusive'
    elif upper <= 1.05:
        status = 'passes'
    else:
        status = 'fails'
    result = {
        'case': name, **spec, 'repeats_per_batch': repeats,
        'expected_per_batch': expected, 'calibration': calibration,
        'program_sha256': hashes, 'builds': builds,
        'samples': samples, 'unusable_sessions': unusable,
        'session_ratios': session_ratios,
        'geometric_mean_ratio': estimate,
        'bootstrap_upper_95_ratio': upper,
        'status': status,
        'statistical_eligibility': {
            'required_sessions': 10, 'required_pairs': 5,
            'met': enough_blocks and not unusable,
        },
        'equivalent_group_consumer': spec['kind'] == 'partition_sum',
    }
    report['results'].append(result)
    print(name, status, estimate, upper, flush=True)

text = json.dumps(report, indent=2) + '\n'
if a.output:
    a.output.write_text(text)
print(text)
