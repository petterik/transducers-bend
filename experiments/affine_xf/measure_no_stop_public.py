#!/usr/bin/env python3
"""Reproduce public no-stop native and JS timings with source setup excluded."""
import argparse
import json
from pathlib import Path
import random
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
        binary = Path(tmp) / 'bench'
        run('bun', BEND, NATIVE, '-o', binary)
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
        return {mode: statistics.median(values)
                for mode, values in samples.items()}


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
    args = parser.parse_args()
    assert args.sessions > 0 and args.native_depth >= 19 and args.js_depth >= 17
    print(json.dumps({
        'native_us': native(args.sessions, args.native_depth),
        'js_us': javascript(args.sessions, args.js_depth),
        'sessions': args.sessions,
        'native_depth': args.native_depth,
        'js_depth': args.js_depth,
    }, indent=2))


if __name__ == '__main__':
    main()
