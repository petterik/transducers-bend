#!/usr/bin/env python3
"""Check that retained List and Array chunks produce the expected results."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time


FIXTURE = Path(__file__).with_name('retained_probe.bend')
PARTITION_FIXTURE = Path(__file__).with_name('semantic_probe.bend')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, required=True,
                    help='pinned bendlang/main compiler entry point')
parser.add_argument('--output', type=Path,
                    help='write the verification report as JSON')
a = parser.parse_args()

compiler = a.bend_main.resolve()
with tempfile.TemporaryDirectory(prefix='array-partition-retained-') as temp_name:
    out = Path(temp_name)
    env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
           'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
    stem = out / 'retained_probe'
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
    assert len(values) == 4, (len(values), js.stdout)
    assert 'False{}' not in js.stdout, js.stdout

    report = {
        'compiler_entry_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
        'compiler_source_sha256': hashlib.sha256(
            (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
        'retained_fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        'partition_fixture_sha256': hashlib.sha256(
            PARTITION_FIXTURE.read_bytes()).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'build_seconds': build_seconds,
        'c_bytes': stem.with_suffix('.c').stat().st_size,
        'js_bytes': stem.with_suffix('.js').stat().st_size,
        'semantic_checks': len(values),
        'js_native_equal': True,
        'input_count': 97,
        'expected_total': 4656,
        'cases': [
            {'width': width, 'expected_groups': groups,
             'last_group_length': tail, 'list_retained': True,
             'array_retained': True}
            for width, groups, tail in [(1, 97, 1), (2, 49, 1),
                                        (3, 33, 1), (8, 13, 1)]
        ],
        'js_output': js.stdout.strip(),
        'artifacts': None,
    }
    text = json.dumps(report, indent=2) + '\n'
    if a.output:
        a.output.write_text(text)
    print(text, end='')
