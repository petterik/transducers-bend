#!/usr/bin/env python3
"""Check library examples on JS and native, plus ownership/codegen checks."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, default=ROOT.parent / 'bend/bend2/main.ts')
args = parser.parse_args()
env = {**os.environ, 'BEND_NO_TELEMETRY': '1'}
compiler = ['bun', str(args.bend_main.resolve())]
passed = 0
with tempfile.TemporaryDirectory(prefix='transduce-tests-') as d:
    for file in sorted((ROOT / 'tests').glob('*.bend')):
        want = '\n'.join(line[2:] for line in file.read_text().splitlines() if line.startswith('#|'))
        assert want, f'{file.name}: missing expected output'
        out = Path(d) / file.stem
        build = subprocess.run(compiler + [str(file), '-o', str(out) + '.js', '-o', str(out)],
                               env=env, capture_output=True, text=True, timeout=30)
        if want.endswith('exit 1'):
            actual = (build.stdout + build.stderr).strip() + '\nexit ' + str(build.returncode)
            assert actual == want, (file.name, actual, want)
        else:
            assert build.returncode == 0, (file.name, build.stdout + build.stderr)
            for lane, command in [('JS', ['bun', str(out) + '.js']),
                                  ('native', [str(out), '--threads', '1'])]:
                result = subprocess.run(command, capture_output=True, text=True, timeout=10)
                assert result.returncode == 0 and result.stdout.strip() == want, (file.name, lane, result.stdout, result.stderr, want)
            if file.stem == 'pipeline':
                source = Path(str(out) + '.js').read_text()
                assert '{$: "Reducer"' not in source, 'callback records remain: use the compiler specialization patch'
                assert 'function $inc$(' in source
                source = source.replace('function $inc$(x_0) {', 'function $inc$(x_0) { mapperCalls++;', 1)
                source = 'let mapperCalls = 0; process.on("exit", () => process.stderr.write(String(mapperCalls)));\n' + source
                instrumented = Path(d) / 'instrumented.js'
                instrumented.write_text(source)
                result = subprocess.run(['bun', str(instrumented)], capture_output=True, text=True, timeout=10)
                # 3 for take(2) after filter, 0 for zero/empty, 3 for no
                # matches, and 3 for oversized take: no mapping past stop.
                assert result.returncode == 0 and result.stderr == '9', result.stderr
        passed += 1
        print('PASS', file.name)
print(f'PASS: {passed} / {passed}; pipeline code generation and mapper counts verified')
