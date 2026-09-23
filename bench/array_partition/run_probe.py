#!/usr/bin/env python3
"""Compile and validate the fixture-only Array partition prototype."""
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
FIXTURE = Path(__file__).with_name('semantic_probe.bend')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, required=True,
                    help='pinned bendlang/main compiler entry point')
parser.add_argument('--output', type=Path,
                    help='write the verification report as JSON')
parser.add_argument('--artifact-dir', type=Path,
                    help='preserve compiler outputs in a new directory')
a = parser.parse_args()

compiler = a.bend_main.resolve()
if a.artifact_dir:
    out = a.artifact_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
else:
    temp = tempfile.TemporaryDirectory(prefix='array-partition-probe-')
    out = Path(temp.name)

env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
stem = out / 'semantic_probe'
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
assert len(values) == 25, (len(values), js.stdout)
assert 'False{}' not in js.stdout, js.stdout

c_source = stem.with_suffix('.c').read_text()
assert 'blk_at(' in c_source, 'indexed Array address calculation is absent'
assert 'blk_read(e.mem, 0,' in c_source, 'indexed Array reads are absent'
assert 'blk_write(e.mem, 0,' in c_source, 'indexed Array writes are absent'
assert 'blk_half(e,' not in c_source, 'Array tree splitting leaked into the fixture'

report = {
    'compiler_entry_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
    'compiler_source_sha256': hashlib.sha256(
        (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
    'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
    'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'build_seconds': build_seconds,
    'c_bytes': stem.with_suffix('.c').stat().st_size,
    'js_bytes': stem.with_suffix('.js').stat().st_size,
    'semantic_checks': len(values),
    'js_native_equal': True,
    'indexed_array_accesses_confirmed': True,
    'array_tree_split_calls': 0,
    'artifacts': str(out) if a.artifact_dir else None,
}
text = json.dumps(report, indent=2) + '\n'
if a.output:
    a.output.write_text(text)
print(text, end='')
if 'temp' in locals():
    temp.cleanup()
