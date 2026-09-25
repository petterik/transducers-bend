#!/usr/bin/env python3
"""Reproduce public no-stop timings and timed native allocations."""
import argparse
import json
from pathlib import Path
import random
import re
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BEND = ROOT.parent / 'bend' / 'bend2' / 'main.ts'
NATIVE = ROOT / 'experiments/affine_xf/no_stop_public_library_bench.bend'
JS = './experiments/affine_xf/no_stop_public_js.bend'


def run(*args):
    result = subprocess.run([str(arg) for arg in args], cwd=ROOT,
                            text=True, capture_output=True, check=True)
    return result.stdout.strip()


def native(sessions, depth):
    with tempfile.TemporaryDirectory(prefix='no-stop-public-') as tmp:
        c_file = Path(tmp) / 'bench.c'
        binary = Path(tmp) / 'bench'
        run('bun', BEND, NATIVE, '-o', c_file)
        run('clang', '-O3', c_file, '-o', binary)
        samples = {str(mode): [] for mode in range(4)}
        for i in range(sessions):
            order = list(range(4))
            random.Random(20260925 + i).shuffle(order)
            for mode in order:
                elapsed, value = map(int, run(binary, '--threads', '1',
                                              '--gpu', 'off', '--', mode,
                                              depth).split())
                expected = 2 * (1 << depth) if mode < 2 else 2 * 524288
                assert value == expected, (mode, value, expected)
                samples[str(mode)].append(elapsed)
        medians = {mode: statistics.median(values)
                   for mode, values in samples.items()}
        source = c_file.read_text()
        heap = 'INLINE Loc heap_alloc(Env e, Cls cls) {\n'
        tick = 'static u64 io_tick(void) {\n'
        exit_code = '  io_sync();\n  return code;'
        assert source.count(heap) == source.count(tick) == source.count(exit_code) == 1
        source = source.replace(heap,
            'static u64 all_allocs = 0, timed_allocs = 0;\n'
            'static u32 ticks = 0;\nstatic bool timing = false;\n'
            + heap + '  all_allocs++;\n  if (timing) timed_allocs++;\n', 1)
        source = source.replace(tick,
            tick + '  if (ticks == 0) timing = true;\n'
            '  else if (ticks == 1) timing = false;\n  ticks++;\n', 1)
        source = source.replace(exit_code,
            '  io_sync();\n'
            '  fprintf(stderr, "ALLOC all=%llu timed=%llu ticks=%u\\n", '
            '(unsigned long long)all_allocs, '
            '(unsigned long long)timed_allocs, ticks);\n'
            '  return code;', 1)
        instrumented = Path(tmp) / 'instrumented.c'
        instrumented.write_text(source)
        alloc_binary = Path(tmp) / 'instrumented'
        run('clang', '-O3', instrumented, '-o', alloc_binary)
        allocs = {}
        for mode in range(4):
            result = subprocess.run([str(alloc_binary), '--threads', '1',
                                     '--gpu', 'off', '--', str(mode), str(depth)],
                                    cwd=ROOT, text=True, capture_output=True,
                                    check=True)
            _, value = map(int, result.stdout.split())
            assert value == (2 * (1 << depth) if mode < 2 else 2 * 524288)
            match = re.search(r'ALLOC all=(\d+) timed=(\d+) ticks=(\d+)',
                              result.stderr)
            assert match and int(match.group(3)) == 2, result.stderr
            allocs[str(mode)] = {'all': int(match.group(1)),
                                 'timed': int(match.group(2))}
        return medians, allocs


def javascript(sessions, depth):
    code = f'''import M from "{JS}";
const samples = [[], [], [], [], []];
const expected = 2 ** ({depth} + 1);
for (let i = 0; i < {sessions}; i++) {{
  const order = [0, 1, 2, 3, 4];
  if (i % 2) order.reverse();
  for (const mode of order) {{
    const xs = M.source(BigInt({depth}));
    const before = performance.now();
    const result = mode === 0 ? M.direct(xs, 0)
      : mode === 1 ? M.total(xs)
      : mode === 2 ? M.legacy(xs)
      : mode === 3 ? M.stopping(xs)
      : M.stopping_legacy(xs);
    const elapsed = (performance.now() - before) * 1000;
    const want = mode < 3 ? expected : 262144;
    if (result !== want) throw Error(`mode ${{mode}}: ${{result}} != ${{want}}`);
    samples[mode].push(elapsed);
  }}
}}
console.log(JSON.stringify(samples));'''
    samples = json.loads(run('bun', '--preload', BEND, '-e', code))
    return {str(mode): statistics.median(values)
            for mode, values in enumerate(samples)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sessions', type=int, default=24)
    parser.add_argument('--native-depth', type=int, default=20)
    parser.add_argument('--js-depth', type=int, default=18)
    parser.add_argument('--native-only', action='store_true',
                        help='skip JavaScript timing')
    args = parser.parse_args()
    assert args.sessions > 0 and args.native_depth >= 19 and args.js_depth >= 17
    native_us, heap_alloc_calls = native(args.sessions, args.native_depth)
    print(json.dumps({
        'native_us': native_us,
        'heap_alloc_calls': heap_alloc_calls,
        **({} if args.native_only else
           {'js_us': javascript(args.sessions, args.js_depth)}),
        'sessions': args.sessions,
        'native_depth': args.native_depth,
        'js_depth': args.js_depth,
    }, indent=2))


if __name__ == '__main__':
    main()
