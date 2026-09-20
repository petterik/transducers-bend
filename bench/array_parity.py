#!/usr/bin/env python3
"""Compare Array transduction with an independent fused tree traversal.

The runner exercises the simple scalar callback chain that the candidate tree
specialization is allowed to clone.  It keeps the balanced source construction,
predicate, take budget, result and ownership contract identical between lanes;
the direct lane performs the same depth-first tree walk explicitly.  This is a
candidate-only host-CPU parity harness.  Use two sessions and ``--samples 20``
for acceptance after calibrating ``--repeats`` so every retained batch is at
least 100 ms.
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
parser.add_argument('--repeats', type=int, default=512,
                    help='Array reductions per timed sample')
parser.add_argument('--depth', type=int, default=8,
                    help='balanced Array depth; leaves per reduction are 2**depth')
parser.add_argument('--sessions', type=int, default=1,
                    help='independent timing sessions; each has forward/reverse orders')
parser.add_argument('--min-batch-ms', type=float, default=0,
                    help='require every retained timed sample to meet this duration')
parser.add_argument('--bootstrap-seed', type=int, default=20260920)
parser.add_argument('--bootstrap-resamples', type=int, default=2000)
parser.add_argument('--cases', nargs='+', choices=['cheap_full', 'cheap_early'],
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
if a.depth < 0 or a.depth > 12:
    parser.error('--depth must be between 0 and 12')
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
    out = Path(tempfile.mkdtemp(prefix='transduce-array-parity-')).resolve()

env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}

CASES = {
    # The budget is larger than the tree, so this visits every leaf even when
    # the predicate rejects values.  Thresholds still vary at runtime.
    'cheap_full': {'budget_mode': 'full'},
    # A zero and several small budgets exercise the source driver's immediate
    # Stop propagation through both tree branches.
    'cheap_early': {'budget_mode': 'early'},
}

source_template = '''import Base
import {transduce_import} as T

def above(t: U32, x: U32) -> Bool:
  U32.is_gt(x, t)

def pipeline() -> T.Reducer<U32, U32>:
  T.filter(~U32, ~U32, ~U32, ~above,
    ~T.take(~U32, ~U32, ~T.sum()))

def build(+depth: Nat, +seed: U32) -> Array<U32>:
  match depth:
    case 0n:
      ALeaf{{seed}}
    case 1n+p:
      left right = build(p, seed) build(p, U32.add(seed, U32.shln(1, p)))
      ANode{{left, right}}

type Running is Data:
  Running{{left: Nat, acc: U32}}

def feed(yes: Bool, left: Nat, acc: U32, x: U32) -> Running:
  match yes left:
    case False{{}} n:
      Running{{n, acc}}
    case True{{}} 0n:
      Running{{0n, acc}}
    case True{{}} 1n+p:
      Running{{p, (acc + x : U32)}}

# This is the independent handwritten comparator.  Matching the tree first
# keeps Array ownership explicit; matching the state inside each branch lets
# the direct traversal stop before touching the right subtree.
def direct_array_step(shape: Array<U32>, st: Running, +threshold: U32) -> Running:
  match shape:
    case ALeaf{{+x}}:
      match st:
        case Running{{0n, acc}}:
          Running{{0n, acc}}
        case Running{{1n+p, acc}}:
          feed(above(threshold, x), 1n+p, acc, x)
    case ANode{{left, right}}:
      match st:
        case Running{{0n, acc}}:
          Running{{0n, acc}}
        case Running{{1n+p, acc}}:
          next = direct_array_step(left, Running{{1n+p, acc}}, threshold)
          direct_array_step(right, next, threshold)

def direct_array(xs: Array<U32>, state: Running, threshold: U32) -> Running:
  direct_array_step(xs, state, threshold)

def finish_running(st: Running) -> U32:
  match st:
    case Running{{left, acc}}:
      acc

type Mode is Data:
  Mode0{{}}
  Mode1{{}}
  Mode2{{}}
  Mode3{{}}
  Mode4{{}}
  Mode5{{}}

def dyn_threshold(+mode: Mode) -> U32:
  match mode:
    case Mode0{{}}: 0
    case Mode1{{}}: 1
    case Mode2{{}}: 2147483647
    case Mode3{{}}: 4294967295
    case Mode4{{}}: 0
    case Mode5{{}}: 1

def dyn_budget(+mode: Mode) -> Nat:
  match mode:
{budget_cases}

def dyn_next(+mode: Mode) -> Mode:
  match mode:
    case Mode0{{}}: Mode1{{}}
    case Mode1{{}}: Mode2{{}}
    case Mode2{{}}: Mode3{{}}
    case Mode3{{}}: Mode4{{}}
    case Mode4{{}}: Mode5{{}}
    case Mode5{{}}: Mode0{{}}

def one(n: Nat, threshold: U32, budget: Nat) -> U32:
  xs = build({depth}n, U32.from_nat(n))
  {body}

def repeat(n: Nat, +acc: U32, +mode: Mode) -> U32:
  match n:
    case 0n:
      acc
    case 1n+ +p:
      answer = one(p, dyn_threshold(mode), dyn_budget(mode))
      repeat(p, (acc + answer : U32), dyn_next(mode))

def measure(n: Nat) -> IO(Unit):
  match n:
    case 0n:
      IO.pure(Unit, Unit{{}})
    case 1n+p:
      do IO<Unit>:
        before : Nat <- IO.now()
        answer : U32 = repeat({repeats}n, 0, Mode0{{}})
        after : Nat <- IO.now()
        IO.print(U32.show(answer) ++ ":" ++ Nat.show(Nat.sub(after, before)))
        measure(p)

def main() -> IO(Unit):
  measure({samples_plus_one}n)
'''


def budget_cases(mode):
    if mode == 'full':
        leaves = 1 << a.depth
        values = [leaves] * 6
    else:
        values = [0, 1, 2, 8, 32, 128]
    return '\n'.join(
        f'    case Mode{i}{{}}: {value}n' for i, value in enumerate(values))


def expected(case, repeats, depth):
    budgets = ([(1 << depth)] * 6 if case['budget_mode'] == 'full'
               else [0, 1, 2, 8, 32, 128])
    thresholds = [0, 1, 2147483647, 4294967295, 0, 1]
    leaves = 1 << depth
    total = 0
    mode = 0
    for seed in range(repeats - 1, -1, -1):
        budget = budgets[mode]
        threshold = thresholds[mode]
        accepted = 0
        subtotal = 0
        for x in range(seed, seed + leaves):
            if accepted >= budget:
                break
            if x > threshold:
                subtotal = (subtotal + x) & 0xffffffff
                accepted += 1
        total = (total + subtotal) & 0xffffffff
        mode = (mode + 1) % 6
    return total


def run(cmd, timeout=240):
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
    text = source_template.format(
        transduce_import=os.path.relpath(ROOT / 'transduce.bend', stem.parent),
        budget_cases=budget_cases(spec['budget_mode']),
        depth=a.depth,
        body=body,
        repeats=a.repeats,
        samples_plus_one=a.samples + 1,
    )
    stem.with_suffix('.bend').write_text(text)
    return text


def parse_output(output, expected_value):
    rows = []
    for line in output.splitlines():
        fields = line.split(':')
        if len(fields) != 2:
            raise AssertionError(output)
        value, millis = map(int, fields)
        if value != expected_value:
            raise AssertionError((expected_value, output))
        rows.append(millis)
    if len(rows) != a.samples + 1:
        raise AssertionError((a.samples, output))
    return rows[1:]


report = {
    'platform': platform.platform(),
    'compiler_sha256': hashlib.sha256((compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
    'library_sha256': hashlib.sha256((ROOT / 'transduce.bend').read_bytes()).hexdigest(),
    'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'candidate compiler; balanced Array<U32> source; scalar filter/take/sum; sequential CPU; GPU off',
    'timing': 'IO.now milliseconds per repeated batch; one warmup discarded; lanes run in forward and reverse order',
    'depth': a.depth,
    'leaves_per_reduction': 1 << a.depth,
    'repeats_per_sample': a.repeats,
    'sessions': a.sessions,
    'minimum_batch_ms': a.min_batch_ms,
    'bootstrap': {'seed': a.bootstrap_seed, 'resamples': a.bootstrap_resamples,
                  'statistic': 'paired median(transducers) / median(direct)'},
    'artifacts': str(out),
    'results': [],
}

selected = a.cases or list(CASES)
for case in selected:
    result = {
        'case': case,
        **CASES[case],
        'expected': expected(CASES[case], a.repeats, a.depth),
        'samples_ms': {'transducers': [], 'direct': []},
        'paired_samples_ms': [],
        'program_sha256': {},
        'builds': {},
    }
    bodies = {
        'transducers': ('T.transduce(~T.over_array(~U32, ~U32, ~pipeline()), '
                        '(threshold, (budget, 0)), xs)'),
        'direct': 'finish_running(direct_array(xs, Running{budget, 0}, threshold))',
    }
    for lane, body in bodies.items():
        stem = out / f'{case}-{lane}'
        program = write_program(stem, case, body)
        result['program_sha256'][lane] = hashlib.sha256(program.encode()).hexdigest()
        before = time.perf_counter()
        run(['bun', compiler, stem.with_suffix('.bend'),
             '-o', stem, '-o', stem.with_suffix('.js'),
             '-o', stem.with_suffix('.c')])
        c_text = stem.with_suffix('.c').read_text()
        run(['clang', '-std=c11', '-O3', stem.with_suffix('.c'),
             '-lpthread', '-lm', '-o', stem])
        result['builds'][lane] = {
            'seconds': time.perf_counter() - before,
            'js_bytes': stem.with_suffix('.js').stat().st_size,
            'c_bytes': stem.with_suffix('.c').stat().st_size,
            'guarded_loop_comments': c_text.count('/* guarded_loop:'),
            'guarded_tree_comments': c_text.count('/* guarded_tree:'),
            'clo_apply_occurrences': c_text.count('Clo.apply'),
        }
    if result['builds']['transducers']['guarded_tree_comments'] != 1:
        raise AssertionError((case, result['builds']))
    if result['builds']['direct']['guarded_tree_comments'] != 0:
        raise AssertionError((case, result['builds']))
    expected_value = result['expected']
    for _session in range(a.sessions):
        for lanes in (list(bodies), list(reversed(bodies))):
            timed = {}
            for lane in lanes:
                stem = out / f'{case}-{lane}'
                run_result = run([stem, '--threads', '1', '--gpu', 'off'])
                samples = parse_output(run_result.stdout, expected_value)
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
    interval = result['bootstrap_95']
    interval_text = ('n/a' if interval is None
                     else f"95%=[{interval['lower_95']:.3f},{interval['upper_95']:.3f}]")
    ratio_text = ('n/a' if result['ratio_transducer_over_direct'] is None
                  else f"{result['ratio_transducer_over_direct']:.3f}")
    print(case, result['median_ms'],
          f"ratio={ratio_text}",
          interval_text, flush=True)

text = json.dumps(report, indent=2) + '\n'
if a.output:
    a.output.write_text(text)
print(json.dumps(report, indent=2))
