#!/usr/bin/env python3
"""Compare public list transduction with an independent fused Bend traversal.

The runner is deliberately a small candidate-only parity harness.  It keeps the
source construction, reducer configuration, callbacks and cleanup the same
between the two lanes, while the direct lane uses an ordinary recursive loop.
It is not the final acceptance runner: use ``--samples 20`` in two separate
invocations after calibrating the repetitions for a machine.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, required=True,
                    help='candidate compiler entry point')
parser.add_argument('--samples', type=int, default=5,
                    help='timed samples per lane; one warmup is discarded')
parser.add_argument('--repeats', type=int, default=32,
                    help='reductions per timed sample')
parser.add_argument('--sessions', type=int, default=1,
                    help='independent timing sessions; each has forward/reverse orders')
parser.add_argument('--min-batch-ms', type=float, default=0,
                    help='require every retained timed sample to meet this duration')
parser.add_argument('--bootstrap-seed', type=int, default=20260920)
parser.add_argument('--bootstrap-resamples', type=int, default=2000)
parser.add_argument('--cases', nargs='+',
                    choices=['zero_take', 'one_element', 'map_chain',
                             'type_change', 'mixed_full',
                             'mixed_take_one', 'mixed_take_32',
                             'dynamic_short', 'expensive_take_32'],
                    help='selected cases; default: all')
parser.add_argument('--artifact-dir', type=Path,
                    help='preserve generated Bend/C/JS/native artifacts')
parser.add_argument('--output', type=Path,
                    help='write the JSON report to this path')
a = parser.parse_args()
if a.samples < 1:
    parser.error('--samples must be positive')
if a.repeats < 1:
    parser.error('--repeats must be positive')
if a.sessions < 1:
    parser.error('--sessions must be positive')
if a.min_batch_ms < 0:
    parser.error('--min-batch-ms cannot be negative')
if a.bootstrap_resamples < 1:
    parser.error('--bootstrap-resamples must be positive')

compiler = a.bend_main.resolve()
if a.artifact_dir:
    out = a.artifact_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
else:
    out = Path(tempfile.mkdtemp(prefix='transduce-fusion-parity-')).resolve()

env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}

# The cases are intentionally named by the proof/benchmark boundary.  The
# first five exercise fixed source shapes and stopping states; dynamic_short
# checks runtime variation without making a large timed list; the expensive
# case checks that callback cost hides no extra per-element transition work.
CASES = {
    'zero_take': {'count': 32, 'take': 0, 'threshold_mode': 'above',
                  'work_rounds': 0},
    'one_element': {'count': 1, 'take': 1, 'threshold_mode': 'above',
                    'work_rounds': 0},
    'map_chain': {'count': 200_000, 'take': 200_000,
                  'threshold_mode': 'above', 'work_rounds': 0,
                  'kind': 'map_chain'},
    'type_change': {'count': 200_000, 'take': 200_000,
                    'threshold_mode': 'above', 'work_rounds': 0,
                    'kind': 'type_change'},
    'mixed_full': {'count': 200_000, 'take': 200_000,
                   'threshold_mode': 'mixed', 'work_rounds': 0},
    'mixed_take_one': {'count': 200_000, 'take': 1,
                       'threshold_mode': 'mixed', 'work_rounds': 0},
    'mixed_take_32': {'count': 200_000, 'take': 32,
                      'threshold_mode': 'mixed', 'work_rounds': 0},
    'dynamic_short': {'count': 'dynamic', 'take': 'dynamic',
                      'threshold_mode': 'dynamic', 'work_rounds': 0},
    'expensive_take_32': {'count': 200_000, 'take': 32,
                          'threshold_mode': 'mixed', 'work_rounds': 256},
}
selected = a.cases or list(CASES)

source_template = '''import Base
import {transduce_import} as T

def work(n: Nat, +x: U32) -> U32:
  match n:
    case 0n:
      x
    case 1n+p:
      work(p, (U32.xor(U32.mul(x, 1664525), U32.shrn(x, 13n)) + 1013904223 : U32))

def cheap(+x: U32) -> U32:
  (U32.xor(x, U32.shrn(x, 13n)) + 1 : U32)

def transform(x: U32) -> U32:
  {work_call}

def above(t: U32, x: U32) -> Bool:
  {predicate}

{extra_defs}

def pipeline() -> T.Reducer<U32, U32>:
  T.map(~U32, ~U32, ~U32, ~transform,
    ~T.filter(~U32, ~U32, ~U32, ~above,
      ~T.take(~U32, ~U32, ~T.sum())))

type Running is Type:
  Running{{left: Nat, acc: U32}}

def keep(yes: Bool, left: Nat, acc: U32, x: U32) -> Running:
  match yes left:
    case False{{}} n:
      Running{{n, acc}}
    case True{{}} 0n:
      Running{{0n, acc}}
    case True{{}} 1n+p:
      Running{{p, (acc + x : U32)}}

def feed(threshold: U32, left: Nat, acc: U32, +x: U32) -> Running:
  keep(above(threshold, x), left, acc, x)

def direct_list(xs: List<U32>, state: Running, +threshold: U32) -> U32:
  match xs state:
    case xs Running{{0n, acc}}:
      acc
    case Nil{{}} Running{{left, acc}}:
      acc
    case h <> t Running{{1n+p, acc}}:
      direct_list(t, feed(threshold, 1n+p, acc, transform(h)), threshold)

def build(+n: Nat, xs: List<U32>) -> List<U32>:
  match n:
    case 0n:
      xs
    case 1n+p:
      build(p, U32.from_nat(p) <> xs)

{dynamic_helpers}

def repeat({repeat_params}) -> U32:
  match n:
    case 0n:
      acc
    case 1n+p:
{step_body}

def measure(n: Nat) -> IO(Unit):
  match n:
    case 0n:
      IO.pure(Unit, Unit{{}})
    case 1n+p:
      do IO<Unit>:
        before : Nat <- IO.now()
        answer : U32 = repeat({repeat_initial})
        after : Nat <- IO.now()
        IO.print(U32.show(answer) ++ ":" ++ Nat.show(Nat.sub(after, before)))
        measure(p)

def main() -> IO(Unit):
  measure({samples_plus_one}n)
'''


def u32_work(x, rounds):
    mask = 0xffffffff
    for _ in range(rounds):
        x = (((x * 1664525) & mask) ^ (x >> 13)) + 1013904223
        x &= mask
    return x


def cheap(x):
    return (((x ^ (x >> 13)) + 1) & 0xffffffff)


def threshold_for(mode, p):
    if mode == 'above':
        return 1
    if mode == 'mixed':
        return 0x7fffffff
    return [0, 1, 0x7fffffff, 0xffffffff][p % 4]


def count_for(case, p):
    if case['count'] != 'dynamic':
        return case['count']
    return [0, 1, 2, 4, 8, 32][p % 6]


def take_for(case, p):
    if case['take'] != 'dynamic':
        return case['take']
    return [0, 1, 2, 32, 64, 128][p % 6]


def expected(case, repeats):
    total = 0
    mode = 0
    for p in range(repeats - 1, -1, -1):
        count = count_for(case, mode)
        budget = take_for(case, mode)
        threshold = threshold_for(case['threshold_mode'], mode)
        accepted = 0
        subtotal = 0
        for x in range(count):
            if accepted == budget:
                break
            if case.get('kind') == 'map_chain':
                mapped = (x + 6) & 0xffffffff
                subtotal = (subtotal + mapped) & 0xffffffff
                accepted += 1
                continue
            if case.get('kind') == 'type_change':
                mapped = x
                subtotal = (subtotal + mapped) & 0xffffffff
                accepted += 1
                continue
            mapped = cheap(x) if case['work_rounds'] == 0 else u32_work(x, case['work_rounds'])
            key = mapped if case['threshold_mode'] == 'above' else u32_work(mapped, 3)
            if key > threshold:
                subtotal = (subtotal + mapped) & 0xffffffff
                accepted += 1
        total = (total + subtotal) & 0xffffffff
        mode = (mode + 1) % 6
    return total


def run(cmd, timeout=120):
    result = subprocess.run([str(part) for part in cmd], env=env,
                            capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, (cmd, result.stdout, result.stderr)
    return result


def bootstrap_ratio(pairs, seed, resamples):
    """Return a paired bootstrap interval for median(transducer)/median(direct)."""
    if not pairs or not any(direct for _, direct in pairs):
        return None
    rng = random.Random(seed)
    ratios = []
    for _ in range(resamples):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        transducers = statistics.median(t for t, _ in sample)
        direct = statistics.median(d for _, d in sample)
        if direct:
            ratios.append(transducers / direct)
    ratios.sort()
    if not ratios:
        return None
    quantile = lambda p: ratios[int(p * (len(ratios) - 1))]
    return {
        'seed': seed,
        'resamples': resamples,
        'paired_samples': len(pairs),
        'lower_95': quantile(0.025),
        'median': quantile(0.5),
        'upper_95': quantile(0.975),
    }


def write_program(stem, case, body):
    spec = CASES[case]
    if spec['work_rounds']:
        work_call = f'work({spec["work_rounds"]}n, x)'
    else:
        work_call = 'cheap(x)'
    if spec['threshold_mode'] == 'above':
        predicate = 'U32.is_gt(x, t)'
    elif spec['threshold_mode'] == 'mixed':
        predicate = 'U32.is_gt(work(3n, x), t)'
    else:
        predicate = 'U32.is_gt(work(3n, x), t)'
    if spec.get('kind') == 'map_chain':
        extra_defs = '''def inc1(x: U32) -> U32:
  (x + 1 : U32)

def inc2(x: U32) -> U32:
  (x + 2 : U32)

def inc3(x: U32) -> U32:
  (x + 3 : U32)

def chain_pipeline() -> T.Reducer<U32, U32>:
  T.map(~U32, ~U32, ~U32, ~inc1,
    ~T.map(~U32, ~U32, ~U32, ~inc2,
      ~T.map(~U32, ~U32, ~U32, ~inc3, ~T.sum())))

def direct_chain(xs: List<U32>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case h <> t:
      direct_chain(t, (acc + ((h + 6 : U32)) : U32))
'''
    elif spec.get('kind') == 'type_change':
        extra_defs = '''def to_nat(x: U32) -> Nat:
  U32.to_nat(x)

def from_nat(x: Nat) -> U32:
  U32.from_nat(x)

def type_change_pipeline() -> T.Reducer<U32, U32>:
  T.map(~U32, ~Nat, ~U32, ~to_nat,
    ~T.map(~Nat, ~U32, ~U32, ~from_nat, ~T.sum()))

def direct_type_change(xs: List<U32>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case h <> t:
      direct_type_change(t, (acc + from_nat(to_nat(h)) : U32))
'''
    else:
        extra_defs = ''
    if spec['count'] == 'dynamic':
        dynamic_helpers = '''type Mode is Data:
  Mode0{}
  Mode1{}
  Mode2{}
  Mode3{}
  Mode4{}
  Mode5{}

def dyn_count(+mode: Mode) -> Nat:
  match mode:
    case Mode0{}: 0n
    case Mode1{}: 1n
    case Mode2{}: 2n
    case Mode3{}: 4n
    case Mode4{}: 8n
    case Mode5{}: 32n

def dyn_budget(+mode: Mode) -> Nat:
  match mode:
    case Mode0{}: 0n
    case Mode1{}: 1n
    case Mode2{}: 2n
    case Mode3{}: 32n
    case Mode4{}: 64n
    case Mode5{}: 128n

def dyn_threshold(+mode: Mode) -> U32:
  match mode:
    case Mode0{}: 0
    case Mode1{}: 1
    case Mode2{}: 2147483647
    case Mode3{}: 4294967295
    case Mode4{}: 0
    case Mode5{}: 1

def dyn_next(+mode: Mode) -> Mode:
  match mode:
    case Mode0{}: Mode1{}
    case Mode1{}: Mode2{}
    case Mode2{}: Mode3{}
    case Mode3{}: Mode4{}
    case Mode4{}: Mode5{}
    case Mode5{}: Mode0{}
'''
        repeat_params = 'n: Nat, acc: U32, +mode: Mode'
        repeat_initial = f'{a.repeats}n, 0, Mode0{{}}'
        count_expr = take_expr = threshold_expr = ''
        step_body = '''      count = dyn_count(mode)
      budget = dyn_budget(mode)
      threshold = dyn_threshold(mode)
      xs = build(count, [])
      answer = {body}
      repeat(p, (acc + answer : U32), dyn_next(mode))'''.replace('{body}', body)
    else:
        dynamic_helpers = ''
        repeat_params = 'n: Nat, acc: U32'
        repeat_initial = f'{a.repeats}n, 0'
        count_expr = f'Nat.add({spec["count"]}n, 0n)'
        take_expr = f'Nat.add({spec["take"]}n, 0n)'
        threshold_expr = ('U32.from_nat(1n)' if spec['threshold_mode'] == 'above'
                          else 'U32.from_nat(2147483647n)')
        step_body = f'''      count = {count_expr}
      budget = {take_expr}
      threshold = {threshold_expr}
      xs = build(count, [])
      answer = {body}
      repeat(p, (acc + answer : U32))'''
    text = source_template.format(
        transduce_import=os.path.relpath(ROOT / 'transduce.bend', stem.parent),
        work_call=work_call,
        predicate=predicate,
        extra_defs=extra_defs,
        dynamic_helpers=dynamic_helpers,
        count_expr=count_expr,
        take_expr=take_expr,
        threshold_expr=threshold_expr,
        body=body,
        repeat_params=repeat_params,
        repeat_initial=repeat_initial,
        step_body=step_body,
        repeats=a.repeats,
        samples_plus_one=a.samples + 1,
    )
    stem.with_suffix('.bend').write_text(text)
    return text


report = {
    'platform': platform.platform(),
    'compiler_sha256': hashlib.sha256((compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
    'library_sha256': hashlib.sha256((ROOT / 'transduce.bend').read_bytes()).hexdigest(),
    'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'candidate compiler; sequential List source; CPU threads=1; GPU off; source construction and cleanup included',
    'timing': 'IO.now milliseconds per repeated batch; one warmup discarded; lanes run in forward and reverse order',
    'repeats_per_sample': a.repeats,
    'sessions': a.sessions,
    'minimum_batch_ms': a.min_batch_ms,
    'bootstrap': {'seed': a.bootstrap_seed, 'resamples': a.bootstrap_resamples,
                  'statistic': 'paired median(transducers) / median(direct)'},
    'artifacts': str(out),
    'results': [],
}

for case in selected:
    spec = CASES[case]
    result = {'case': case, **spec, 'expected': expected(spec, a.repeats),
              'samples_ms': {'transducers': [], 'direct': []},
              'paired_samples_ms': [],
              'program_sha256': {}, 'builds': {}}
    if spec.get('kind') == 'map_chain':
        bodies = {
            'transducers': 'T.transduce(~T.over_list(~U32, ~U32, ~chain_pipeline()), 0, xs)',
            'direct': 'direct_chain(xs, 0)',
        }
    elif spec.get('kind') == 'type_change':
        bodies = {
            'transducers': 'T.transduce(~T.over_list(~U32, ~U32, ~type_change_pipeline()), 0, xs)',
            'direct': 'direct_type_change(xs, 0)',
        }
    else:
        bodies = {
            'transducers': ('T.transduce(~T.over_list(~U32, ~U32, ~pipeline()), '
                            '(threshold, (budget, 0)), xs)'),
            'direct': 'direct_list(xs, Running{budget, 0}, threshold)',
        }
    for lane, body in bodies.items():
        stem = out / f'{case}-{lane}'
        program = write_program(stem, case, body)
        result['program_sha256'][lane] = hashlib.sha256(program.encode()).hexdigest()
        before = time.perf_counter()
        build = run(['bun', compiler, stem.with_suffix('.bend'),
                     '-o', stem, '-o', stem.with_suffix('.js'),
                     '-o', stem.with_suffix('.c')])
        result['builds'][lane] = {
            'seconds': time.perf_counter() - before,
            'js_bytes': stem.with_suffix('.js').stat().st_size,
            'c_bytes': stem.with_suffix('.c').stat().st_size,
            'guarded_loop_comments': stem.with_suffix('.c').read_text().count('/* guarded_loop:'),
            'clo_apply_occurrences': stem.with_suffix('.c').read_text().count('Clo.apply'),
        }
    expected_value = result['expected']
    for _session in range(a.sessions):
        for lanes in (list(bodies), list(reversed(bodies))):
            timed = {}
            for lane in lanes:
                stem = out / f'{case}-{lane}'
                run_result = run([stem, '--threads', '1', '--gpu', 'off'])
                rows = [line.split(':') for line in run_result.stdout.splitlines()]
                assert len(rows) == a.samples + 1, (case, lane, run_result.stdout)
                assert all(int(value) == expected_value for value, _ in rows), (case, lane, run_result.stdout, expected_value)
                samples = [int(ms) for _, ms in rows[1:]]
                timed[lane] = samples
                result['samples_ms'][lane].extend(samples)
            result['paired_samples_ms'].extend(zip(timed['transducers'], timed['direct']))
    result['median_ms'] = {lane: statistics.median(values)
                           for lane, values in result['samples_ms'].items()}
    if a.min_batch_ms:
        minimum = min(ms for values in result['samples_ms'].values() for ms in values)
        assert minimum >= a.min_batch_ms, (case, minimum, a.min_batch_ms)
        result['minimum_observed_ms'] = minimum
    result['bootstrap_95'] = bootstrap_ratio(
        result['paired_samples_ms'], a.bootstrap_seed, a.bootstrap_resamples)
    result['ratio_transducer_over_direct'] = (
        result['median_ms']['transducers'] / result['median_ms']['direct']
        if result['median_ms']['direct'] else None)
    report['results'].append(result)
    ratio_text = ('n/a' if result['ratio_transducer_over_direct'] is None
                  else f"{result['ratio_transducer_over_direct']:.3f}")
    interval = result['bootstrap_95']
    interval_text = ('n/a' if interval is None
                     else f"95%=[{interval['lower_95']:.3f},{interval['upper_95']:.3f}]")
    print(case, result['median_ms'],
          f"ratio={ratio_text}", interval_text, flush=True)

text = json.dumps(report, indent=2) + '\n'
if a.output:
    a.output.write_text(text)
print(json.dumps(report, indent=2))
