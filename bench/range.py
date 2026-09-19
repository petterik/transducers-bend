#!/usr/bin/env python3
"""Focused sequential generated-range comparison, with independent output oracle."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--bend-main', type=Path, default=ROOT.parent / 'bend/bend2/main.ts')
p.add_argument('--samples', type=int, default=7)
p.add_argument('--output', type=Path, help='Optional raw JSON report; otherwise print only')
p.add_argument('--cases', nargs='+', choices=['cheap_full', 'cheap_early', 'huge_early', 'expensive_early'],
               help='Run only these cases; default: all')
p.add_argument('--threshold', type=int, default=1,
               help='U32 filter threshold; high values can make early-stop cases very slow')
a = p.parse_args()
if a.samples < 1:
    p.error('samples must be positive')
if not 0 <= a.threshold <= 4294967295:
    p.error('threshold must fit U32')
env = {**os.environ, 'BEND_NO_TELEMETRY': '1', 'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
report = {'timing': 'IO.now milliseconds per batch; excludes process startup; one warmup per process',
          'scope': 'Sequential generated U32 ranges; CPU threads=1, GPU off; no prebuilt lists',
          'platform': platform.platform(),
          'compiler_sha256': hashlib.sha256((a.bend_main.resolve().parent / 'comp.ts').read_bytes()).hexdigest(),
          'results': []}
cases = [('cheap_full', 0, 2000000, 2000000, 0, 32),
         ('cheap_early', 0, 2000000, 32, 0, 1000000),
         ('huge_early', 0, 4294967295, 32, 0, 1000000),
         ('expensive_early', 0, 2000000, 32, 256, 1000)]
if a.cases:
    cases = [case for case in cases if case[0] in a.cases]
with tempfile.TemporaryDirectory(prefix='transduce-range-') as directory:
    out = Path(directory).resolve()
    source = (ROOT / 'bench/range.bend').read_text().split('def main()')[0]
    source = source.replace('import ../transduce.bend as T',
                            'import ./' + os.path.relpath(ROOT / 'transduce.bend', out) + ' as T')
    source = source.replace('U32.is_gt(x, 1)', f'U32.is_gt(x, {a.threshold})')
    for label, begin, end, take, work, repeats in cases:
        # Vary early-range starts to prevent folding a repeated constant answer.
        varying = label != 'cheap_full'
        offsets = Counter((i & 65535) if varying else begin for i in range(repeats))
        expected = 0
        for offset, multiplicity in offsets.items():
            total = accepted = 0
            for x in range(offset, end):
                if accepted == take:
                    break
                if work:
                    for _ in range(work):
                        x = ((((x * 1664525) & 0xffffffff) ^ (x >> 13)) + 1013904223) & 0xffffffff
                else:
                    x = ((x ^ (x >> 13)) + 1) & 0xffffffff
                if x > a.threshold:
                    total = (total + x) & 0xffffffff
                    accepted += 1
            expected = (expected + total * multiplicity) & 0xffffffff
        code = source.replace('  cheap(x)\n',
                              f'  work({work}n, x)\n', 1) if work else source
        bodies = {'library': f'T.transduce(~T.over_range(~U32, ~pipeline()), ({a.threshold}, ({take}n, 0)), T.range_between(offset, {end}))',
                  'direct': f'direct(U32.to_nat(({end} - offset : U32)), offset, Running{{{take}n, 0}})'}
        row = {'case': label, 'begin': begin, 'end': end, 'take': take, 'work_rounds': work,
               'threshold': a.threshold,
               'starts': 'descending repetition index modulo 65536' if varying else 'constant begin',
               'repeats_per_sample': repeats, 'expected_batch_sum': expected, 'builds': {},
               'samples_ms': {name: [] for name in bodies}}
        for name, body in bodies.items():
            stem = out / name
            offset_expr = 'U32.and(U32.from_nat(p), 65535)' if varying else str(begin)
            program = code + f'''def repeat(+n: Nat, acc: U32) -> U32:
  match n:
    case 0n:
      acc
    case 1n+p:
      +offset = {{{offset_expr} : U32}}
      answer = {body}
      repeat(p, (acc + answer : U32))

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
  measure({a.samples+1}n)
'''
            stem.with_suffix('.bend').write_text(program)
            before = time.perf_counter()
            build = subprocess.run(['bun', str(a.bend_main.resolve()), str(stem.with_suffix('.bend')),
                                    '-o', str(stem), '-o', str(stem.with_suffix('.js')),
                                    '-o', str(stem.with_suffix('.c'))],
                                   env=env, capture_output=True, text=True, timeout=60)
            assert build.returncode == 0, build.stdout + build.stderr
            emitted = stem.with_suffix('.js').read_text()
            if name == 'library':
                assert '{$: "Reducer"' not in emitted, 'callback records remain'
                assert '{$: "Reduction"' not in emitted, 'source binding records remain'
            row['builds'][name] = {'seconds': time.perf_counter() - before,
                                  'js_bytes': len(emitted.encode()),
                                  'c_bytes': stem.with_suffix('.c').stat().st_size}
        # Reverse order in the second round to reduce order bias.
        for names in (list(bodies), list(reversed(bodies))):
            for name in names:
                run = subprocess.run([str(out/name), '--threads', '1', '--gpu', 'off'],
                                     capture_output=True, text=True, timeout=60)
                assert run.returncode == 0, run.stderr
                pairs = [line.split(':') for line in run.stdout.splitlines()]
                assert len(pairs) == a.samples + 1 and all(int(v) == expected for v, _ in pairs), run.stdout
                row['samples_ms'][name].extend(int(ms) for _, ms in pairs[1:])
        row['median_batch_ms'] = {k: statistics.median(v) for k, v in row['samples_ms'].items()}
        row['median_us_per_transduction'] = {k: ms * 1000 / repeats for k, ms in row['median_batch_ms'].items()}
        report['results'].append(row)
text = json.dumps(report, indent=2) + '\n'
if a.output:
    a.output.write_text(text)
print(text, end='')
