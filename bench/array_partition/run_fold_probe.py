#!/usr/bin/env python3
"""Check fold consumers against the List and direct baselines on both backends."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).with_name('fold_probe.bend')
SEMANTIC_FIXTURE = Path(__file__).with_name('semantic_probe.bend')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, required=True,
                    help='pinned bendlang/main compiler entry point')
parser.add_argument('--output', type=Path,
                    help='write the verification report as JSON')
a = parser.parse_args()

compiler = a.bend_main.resolve()
with tempfile.TemporaryDirectory(prefix='array-partition-fold-') as temp_name:
    out = Path(temp_name)
    env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
           'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
    stem = out / 'fold_probe'
    started = time.perf_counter()
    build = subprocess.run(
        ['bun', str(compiler), str(FIXTURE), '-o', str(stem),
         '-o', str(stem.with_suffix('.js')), '-o', str(stem.with_suffix('.c'))],
        env=env, capture_output=True, text=True, timeout=120)
    assert build.returncode == 0, (build.stdout, build.stderr)
    build_seconds = time.perf_counter() - started

    js = subprocess.run(['bun', str(stem.with_suffix('.js'))], env=env,
                        capture_output=True, text=True, timeout=30)
    native = subprocess.run([str(stem), '--threads', '1', '--gpu', 'off'],
                            env=env, capture_output=True, text=True, timeout=30)
    assert js.returncode == 0, (js.stdout, js.stderr)
    assert native.returncode == 0, (native.stdout, native.stderr)
    assert js.stdout == native.stdout, (js.stdout, native.stdout)
    values = re.findall(r'True\{\}', js.stdout)
    assert len(values) == 8, (len(values), js.stdout)
    assert 'False{}' not in js.stdout, js.stdout

    report = {
        'compiler_entry_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
        'compiler_source_sha256': hashlib.sha256(
            (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
        'fold_fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        'partition_fixture_sha256': hashlib.sha256(
            SEMANTIC_FIXTURE.read_bytes()).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'build_seconds': build_seconds,
        'c_bytes': stem.with_suffix('.c').stat().st_size,
        'js_bytes': stem.with_suffix('.js').stat().st_size,
        'semantic_checks': len(values),
        'js_native_equal': True,
        'cases': [
            {'width': width, 'budget': budget,
             'consumption': 'full' if budget == full else 'bounded',
             'result': True}
            for width, full, budget in [
                (1, 96, 96), (2, 48, 48), (3, 32, 32), (8, 12, 12),
                (1, 96, 2), (2, 48, 2), (3, 32, 2), (8, 12, 2)]
        ],
        'js_output': js.stdout.strip(),
        'artifacts': None,
    }
    text = json.dumps(report, indent=2) + '\n'
    if a.output:
        a.output.write_text(text)
    print(text, end='')
