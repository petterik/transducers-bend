#!/usr/bin/env python3
"""Differentially check public pipelines against independent Python semantics."""
from pathlib import Path
import random
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BEND = ROOT.parent / 'bend' / 'bend2' / 'main.ts'
SEED = 20260925
U32 = (1 << 32) - 1

PRELUDE = '''import Base
import ./xf.bend as X
import ./transduce_core.bend as T

def inc(x: U32) -> U32:
  U32.inc(x)

def even(x: U32) -> Bool:
  U32.is_zero(U32.mod(x, 2))

def pair(x: U32) -> List<U32>:
  +x = x
  [x, U32.add(x, 10)]

def choose(yes: Bool, x: U32) -> Maybe<U32>:
  match yes:
    case True{}: Some{x}
    case False{}: None{}

def keep_even(x: U32) -> Maybe<U32>:
  +x = x
  choose(even(x), x)

def empty_groups() -> List<List<U32>>:
  []
'''

SCALAR = '''
def after(xs: List<U32>, n: Nat) -> U32:
  X.transduce(X.comp3(X.map(~U32, ~U32, ~inc),
    X.filter(~U32, ~even), X.take(~U32, n)), X.sum_rf(), 0, xs)

def before(xs: List<U32>, n: Nat) -> U32:
  X.transduce(X.comp3(X.take(~U32, n),
    X.map(~U32, ~U32, ~inc), X.filter(~U32, ~even)),
    X.sum_rf(), 0, xs)

def flattened(xs: List<U32>, n: Nat) -> U32:
  X.transduce(X.comp2(
    X.mapcat(~U32, ~U32, ~List<U32>,
      ~(K => S => advance => inspect => input => state =>
        T.source_list(~U32, ~K, ~S, ~advance, ~inspect, input, state)),
      ~pair), X.take(~U32, n)), X.sum_rf(), 0, xs)

def kept(xs: List<U32>, n: Nat) -> U32:
  X.transduce(X.comp2(X.take(~U32, n),
    X.keep(~U32, ~U32, ~keep_even)), X.sum_rf(), 0, xs)

'''

PARTITION = '''
def groups(xs: List<U32>, width: Nat) -> List<List<U32>>:
  X.into(empty_groups(), X.partition_all(~U32, width), xs)

def take_after(xs: List<U32>, width: Nat, n: Nat) -> List<List<U32>>:
  X.into(empty_groups(), X.comp2(
    X.partition_all(~U32, width), X.take(~List<U32>, n)), xs)

def take_before(xs: List<U32>, width: Nat, n: Nat) -> List<List<U32>>:
  X.into(empty_groups(), X.comp2(
    X.take(~U32, n), X.partition_all(~U32, width)), xs)

'''

TRAVERSAL = '''
def small(x: U32) -> Bool:
  U32.is_lt(x, 10)

def indexed(index: Nat, x: U32) -> U32:
  U32.add(x, U32.from_nat(index))

def keep_indexed_even(index: Nat, x: U32) -> Maybe<U32>:
  choose(Nat.is_eq(Nat.mod(index, 2n), 0n), x)

def dropped(xs: List<U32>, n: Nat) -> U32:
  X.transduce(X.drop(~U32, n), X.sum_rf(), 0, xs)

def taken_while(xs: List<U32>) -> U32:
  X.transduce(X.take_while(~U32, ~small), X.sum_rf(), 0, xs)

def dropped_while(xs: List<U32>) -> U32:
  X.transduce(X.drop_while(~U32, ~small), X.sum_rf(), 0, xs)

def indexed_after_drop(xs: List<U32>, n: Nat) -> U32:
  X.transduce(X.comp2(X.drop(~U32, n),
    X.map_indexed(~U32, ~U32, ~indexed)), X.sum_rf(), 0, xs)

def kept_indexed(xs: List<U32>) -> U32:
  X.transduce(X.keep_indexed(~U32, ~U32, ~keep_indexed_even),
    X.sum_rf(), 0, xs)

def every(xs: List<U32>, n: Nat) -> U32:
  X.transduce(X.take_nth(~U32, n), X.sum_rf(), 0, xs)

def flattened_cat(xs: List<U32>, n: Nat) -> U32:
  X.transduce(X.comp3(X.map(~U32, ~List<U32>, ~pair),
    X.cat(T.List.adapter(~U32)),
    X.take(~U32, n)), X.sum_rf(), 0, xs)

'''


def show(value):
    if isinstance(value, list):
        return '[' + ', '.join(map(show, value)) + ']'
    return str(value)


def chunks(xs, width):
    if width == 0:
        return []
    return [xs[i:i + width] for i in range(0, len(xs), width)]


def oracle_scalar(xs, n):
    after = [((x + 1) & U32) for x in xs]
    after = [x for x in after if x % 2 == 0][:n]
    before = [((x + 1) & U32) for x in xs[:n]]
    before = [x for x in before if x % 2 == 0]
    flat = [y for x in xs for y in (x, (x + 10) & U32)][:n]
    kept = [x for x in xs[:n] if x % 2 == 0]
    return [sum(after) & U32, sum(before) & U32,
            sum(flat) & U32, sum(kept) & U32]


def oracle_partition(xs, width, n):
    return [list(reversed(chunks(xs, width))),
            list(reversed(chunks(xs, width)[:n])),
            list(reversed(chunks(xs[:n], width)))]


def oracle_traversal(xs, width, n):
    prefix = 0
    while prefix < len(xs) and xs[prefix] < 10:
        prefix += 1
    tail = xs[n:]
    flat = [y for x in xs for y in (x, (x + 10) & U32)]
    return [sum(tail) & U32, sum(xs[:prefix]) & U32,
            sum(xs[prefix:]) & U32,
            sum((x + i) & U32 for i, x in enumerate(tail)) & U32,
            sum(xs[::2]) & U32,
            0 if width == 0 else sum(xs[::width]) & U32,
            sum(flat[:n]) & U32]


def cases():
    rng = random.Random(SEED)
    lengths = list(range(9))
    xs = [[(i * 7 + n * 3) & U32 for i in range(n)] for n in lengths]
    xs += [[U32, 1, 2, U32, 0]]
    result = []
    for row in xs:
        limits = sorted({0, 1, max(0, len(row) - 1), len(row), len(row) + 1})
        widths = sorted({0, 1, 2, max(0, len(row) - 1), len(row) + 1})
        result.extend((row, n, rng.choice(widths)) for n in limits)
    return result


def source(case_rows, body, kind):
    definitions = []
    expressions = []
    for i, (xs, n, width) in enumerate(case_rows):
        definitions.append(f'def xs{i}() -> List<U32>:\n  {show(xs)}\n')
        if kind == 'partition':
            expressions.extend((f'groups(xs{i}(), {width}n)',
                                f'take_after(xs{i}(), {width}n, {n}n)',
                                f'take_before(xs{i}(), {width}n, {n}n)'))
        elif kind.startswith('traversal'):
            expressions.extend((f'dropped(xs{i}(), {n}n)',
                                f'taken_while(xs{i}())',
                                f'dropped_while(xs{i}())',
                                f'indexed_after_drop(xs{i}(), {n}n)',
                                f'kept_indexed(xs{i}())',
                                f'every(xs{i}(), {width}n)',
                                f'flattened_cat(xs{i}(), {n}n)'))
        else:
            expressions.extend((f'after(xs{i}(), {n}n)',
                                f'before(xs{i}(), {n}n)',
                                f'flattened(xs{i}(), {n}n)',
                                f'kept(xs{i}(), {n}n)'))
    result_type = 'List<List<List<U32>>>' if kind == 'partition' \
        else 'List<U32>'
    return PRELUDE + body + '\n' + '\n'.join(definitions) + \
        f'\ndef main() -> {result_type}:\n  [\n    ' + \
        ',\n    '.join(expressions) + '\n  ]\n'


def run(command):
    result = subprocess.run([str(x) for x in command], text=True,
                            capture_output=True, timeout=120)
    if result.returncode:
        raise AssertionError((command, result.stdout, result.stderr))
    return result.stdout.strip()


def check(temp, rows, kind, body, oracle):
    fixture = temp / f'{kind}.bend'
    fixture.write_text(source(rows, body, kind))
    want = show([item for xs, n, width in rows for item in
                 (oracle(xs, n) if kind == 'scalar'
                  else oracle(xs, width, n))])
    out = temp / kind
    run(['bun', BEND, fixture, '-o', str(out) + '.js', '-o', out])
    for lane, command in [('native', [out, '--threads', '1', '--gpu', 'off']),
                          ('JS', ['bun', str(out) + '.js'])]:
        actual = run(command)
        assert actual == want, (kind, lane, actual, want)
    print(f'PASS {kind}: {len(rows)} cases on native and JS')


def main():
    rows = cases()
    with tempfile.TemporaryDirectory(prefix='public-differential-') as name:
        temp = Path(name)
        for module in ['xf.bend', 'transduce_core.bend']:
            shutil.copyfile(ROOT / module, temp / module)
        check(temp, rows, 'scalar', SCALAR, oracle_scalar)
        check(temp, rows, 'partition', PARTITION, oracle_partition)
        for offset in range(0, len(rows), 16):
            check(temp, rows[offset:offset + 16],
                  f'traversal_{offset // 16}', TRAVERSAL, oracle_traversal)


if __name__ == '__main__':
    main()
