#!/usr/bin/env python3
"""Check library examples on JS and native, plus ownership/codegen checks."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, default=ROOT.parent / 'bend/bend2/main.ts')
args = parser.parse_args()
env = {**os.environ, 'BEND_NO_TELEMETRY': '1', 'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
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
            source = Path(str(out) + '.js').read_text()
            if file.stem in {'pipeline', 'range', 'sources', 'extensions', 'lifecycle'}:
                assert '{$: "Reducer"' not in source, (file.name, 'callback records remain')
                assert '{$: "Reduction"' not in source, (file.name, 'source binding records remain')
            for lane, command in [('JS', ['bun', str(out) + '.js']),
                                  ('native', [str(out), '--threads', '1', '--gpu', 'off'])]:
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
            if file.stem == 'range':
                source = Path(str(out) + '.js').read_text()
                assert '{$: "Reducer"' not in source, 'range callback records remain'
                source, replacements = re.subn(
                    r'(function [\w$]*\$range_value\$\([^\n]*\) \{)',
                    r'\1 sourceCalls++;', source)
                assert replacements == 1, 'range source instrumentation target changed'
                source, replacements = re.subn(
                    r'(function \$inc\$\([^\n]*\) \{)', r'\1 mapperCalls++;', source)
                assert replacements == 1, 'range mapper instrumentation target changed'
                source = ('let sourceCalls = 0, mapperCalls = 0; process.on("exit", () => '
                          'process.stderr.write(`${sourceCalls},${mapperCalls}`));\n' + source)
                instrumented = Path(d) / 'range-instrumented.js'
                instrumented.write_text(source)
                result = subprocess.run(['bun', str(instrumented)], capture_output=True, text=True, timeout=10)
                # Source: 3*3 pipeline inputs, 2 boundary inputs, 1 take-one,
                # 1 consumer-stop input, 3 affine inputs. Mapper includes
                # the list pipeline's 3 inputs, but not identity/affine cases.
                assert result.returncode == 0 and result.stderr == '16,13', result.stderr
                assert result.stdout.strip() == want, result.stdout
            if file.stem == 'lifecycle':
                for function, counter in [('begin', 'starts'), ('advance', 'steps'), ('done', 'finishes')]:
                    source, replacements = re.subn(
                        rf'(function \${function}\$\([^\n]*\) \{{)', rf'\1 {counter}++;', source)
                    assert replacements == 1, (function, 'lifecycle target changed')
                source = ('let starts = 0, steps = 0, finishes = 0; process.on("exit", () => '
                          'process.stderr.write(`${starts},${steps},${finishes}`));\n' + source)
                instrumented = Path(d) / 'lifecycle-instrumented.js'
                instrumented.write_text(source)
                result = subprocess.run(['bun', str(instrumented)], capture_output=True, text=True, timeout=10)
                assert result.returncode == 0 and result.stderr == '12,8,12', result.stderr
                assert result.stdout.strip() == want, result.stdout
        passed += 1
        print('PASS', file.name)
print(f'PASS: {passed} / {passed}; code generation, source/mapper counts, and bounded laws verified')
