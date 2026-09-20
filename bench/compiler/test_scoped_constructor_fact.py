#!/usr/bin/env python3
"""Validate the first scoped fact rewrite and its refusal boundary."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / 'fixtures/scoped_constructor_fact.bend'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
out = Path(tempfile.mkdtemp(prefix='bend-scoped-constructor-fact-')).resolve()
env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
expected = '\n'.join(line[2:] for line in SOURCE.read_text().splitlines()
                     if line.startswith('#|'))

def run(command, extra=None):
    result = subprocess.run(list(map(str, command)),
                            env={**env, **(extra or {})}, capture_output=True,
                            text=True, timeout=60)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result

def build(compiler, stem, report=None):
    extra = {'BEND_FACT_REPORT': str(report)} if report else None
    run(['bun', compiler, SOURCE, '-o', stem.with_suffix('.c'),
         '-o', stem.with_suffix('.js')], extra)
    run(['clang', '-std=c11', '-O1', '-fsanitize=undefined',
         '-fno-sanitize-recover=all', stem.with_suffix('.c'), '-lpthread',
         '-lm', '-o', stem])

original = out / 'original'
candidate = out / 'candidate'
report_path = out / 'facts.json'
build(ROOT.parent / 'bend/bend2/main.ts', original)
build(args.bend_main, candidate, report_path)
original_native = run([original, '--threads', '1', '--gpu', 'off', '--', 'fact']).stdout.strip()
candidate_native = run([candidate, '--threads', '1', '--gpu', 'off', '--', 'fact']).stdout.strip()
candidate_js = run(['bun', candidate.with_suffix('.js'), '--', 'fact']).stdout.strip()
facts = json.loads(report_path.read_text())
result = {
    'compiler_sha256': hashlib.sha256(
        (args.bend_main.parent / 'comp.ts').read_bytes()).hexdigest(),
    'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'artifacts': str(out),
    'expected': expected,
    'original_native': original_native,
    'candidate_native': candidate_native,
    'candidate_js': candidate_js,
    'facts': facts,
    'candidate_c_bytes': candidate.with_suffix('.c').stat().st_size,
    'original_c_bytes': original.with_suffix('.c').stat().st_size,
    'candidate_js_bytes': candidate.with_suffix('.js').stat().st_size,
    'original_js_bytes': original.with_suffix('.js').stat().st_size,
}
result['matches'] = (original_native == expected
                     and candidate_native == expected
                     and candidate_js == expected)
result['scoped_boundary'] = (facts['selected'] > 0 and facts['rejected'] > 0
                             and facts['known'] >= facts['selected'] + facts['rejected'])
args.output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
assert result['matches'] and result['scoped_boundary']
