#!/usr/bin/env python3
"""Measure the current static-composition boundary and the eager probe."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path,
                    default=ROOT.parent / 'bend/bend2/main.ts')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
env = {**os.environ, 'BEND_NO_TELEMETRY': '1'}
source = HERE / 'fixtures/static_composition.bend'
out = Path(tempfile.mkdtemp(prefix='bend-static-composition-')).resolve()

def run(command):
    result = subprocess.run(list(map(str, command)), env=env,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result

stem = out / 'static_composition'
started = time.perf_counter()
run(['bun', args.bend_main, source, '-o', stem.with_suffix('.c'),
     '-o', stem.with_suffix('.js')])
compile_ms = (time.perf_counter() - started) * 1000
c_text = stem.with_suffix('.c').read_text()
js_text = stem.with_suffix('.js').read_text()
run(['clang', '-std=c11', '-O3', stem.with_suffix('.c'), '-lpthread',
     '-lm', '-o', stem])
native_run = run([stem, '--threads', '1', '--gpu', 'off'])
js_run = run(['bun', stem.with_suffix('.js')])
expected = '[9, 9, 7, 7, 3, 3]'
report = {
    'compiler_sha256': hashlib.sha256(
        (args.bend_main.parent / 'comp.ts').read_bytes()).hexdigest(),
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'artifacts': str(out),
    'compile_ms': round(compile_ms, 3),
    'native': native_run.stdout.strip(),
    'js': js_run.stdout.strip(),
    'expected': expected,
    'reducer_records_js': js_text.count('{$: "Reducer"'),
    'reduction_records_js': js_text.count('{$: "Reduction"'),
    'clo_apply_label_c': c_text.count('Clo.apply'),
    'closure_dispatch_transfers_c': c_text.count('WL_JMP(FID_CLO_APPLY)'),
    'reducer_symbols_c': c_text.count('Reducer'),
    'matches': native_run.stdout.strip() == js_run.stdout.strip() == expected,
}
args.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
assert report['matches']
