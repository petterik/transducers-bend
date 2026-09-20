#!/usr/bin/env python3
"""Check that guarded facts remain scoped and retain a generic fallback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
out = Path(tempfile.mkdtemp(prefix='bend-scoped-facts-')).resolve()
source = HERE / 'fixtures/scoped_fact_boundary.bend'
env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}

def run(command, extra=None):
    result = subprocess.run(list(map(str, command)),
                            env={**env, **(extra or {})}, capture_output=True,
                            text=True, timeout=60)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result

def build(compiler, stem, report=None):
    extra = {'BEND_LOOP_REPORT': str(report)} if report else None
    run(['bun', compiler, source, '-o', stem.with_suffix('.c'),
         '-o', stem.with_suffix('.js')], extra)
    run(['clang', '-std=c11', '-O1', '-fsanitize=undefined',
         '-fno-sanitize-recover=all', stem.with_suffix('.c'), '-lpthread',
         '-lm', '-o', stem])

original = out / 'original'
candidate = out / 'candidate'
report_path = out / 'candidate.jsonl'
build(ROOT.parent / 'bend/bend2/main.ts', original)
build(args.bend_main, candidate, report_path)
expected = next(line[2:] for line in source.read_text().splitlines()
                if line.startswith('#|'))
original_js = original.with_suffix('.js').read_text()
candidate_js = candidate.with_suffix('.js').read_text()
candidate_c = candidate.with_suffix('.c').read_text()
original_run = run([original, '--threads', '1', '--gpu', 'off'])
candidate_run = run([candidate, '--threads', '1', '--gpu', 'off'])
candidate_js_run = run(['bun', candidate.with_suffix('.js')])
records = [json.loads(line) for line in report_path.read_text().splitlines()]
loop_records = [r for r in records if r.get('callee') == 'spin' and 'name' in r]
generic_names = re.findall(r'\b(spin_\d+)_loop_generic\b', candidate_c)
result = {
    'compiler_sha256': hashlib.sha256(
        (args.bend_main.parent / 'comp.ts').read_bytes()).hexdigest(),
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'artifacts': str(out),
    'expected': expected,
    'original_native': original_run.stdout.strip(),
    'candidate_native': candidate_run.stdout.strip(),
    'candidate_js': candidate_js_run.stdout.strip(),
    'guarded_loop_markers': candidate_c.count('/* guarded_loop:'),
    'generic_fallback_names': sorted(set(generic_names)),
    'proof_records': loop_records,
    'js_byte_identical': original_js == candidate_js,
}
result['matches'] = (result['original_native'] == expected
                     and result['candidate_native'] == expected
                     and result['candidate_js'] == expected)
result['scoped_fallback'] = (result['guarded_loop_markers'] == 1
                             and bool(result['generic_fallback_names'])
                             and bool(loop_records))
args.output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
assert result['matches'] and result['scoped_fallback']
