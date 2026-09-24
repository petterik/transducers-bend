#!/usr/bin/env python3
"""Compare an isolated constructor-shape candidate with bendlang/main."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / 'fixtures/local_representation_fact.bend'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, required=True,
                    help='candidate compiler prepared from the pinned main ref')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
out = Path(tempfile.mkdtemp(prefix='bend-local-representation-')).resolve()
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

def build(compiler, stem):
    run(['bun', compiler, SOURCE, '-o', stem.with_suffix('.c'),
         '-o', stem.with_suffix('.js')])
    run(['clang', '-std=c11', '-O1', '-fsanitize=undefined',
         '-fno-sanitize-recover=all', stem.with_suffix('.c'), '-lpthread',
         '-lm', '-o', stem])

original = out / 'original'
candidate = out / 'candidate'
build(ROOT.parent / 'bend/bend2/main.ts', original)
build(args.bend_main, candidate)
original_native = run([original, '--threads', '1', '--gpu', 'off', '--', 'fact']).stdout.strip()
original_js = run(['bun', original.with_suffix('.js'), '--', 'fact']).stdout.strip()
candidate_native = run([candidate, '--threads', '1', '--gpu', 'off', '--', 'fact']).stdout.strip()
candidate_js = run(['bun', candidate.with_suffix('.js'), '--', 'fact']).stdout.strip()
base_comp = ROOT.parent / 'bend/bend2/comp.ts'
candidate_comp = args.bend_main.parent / 'comp.ts'
preparation_path = args.bend_main.parent / 'prepare-local-representation.json'
preparation = (json.loads(preparation_path.read_text())
               if preparation_path.exists() else {})
result = {
    'base_ref': 'bendlang/main',
    'base_commit': subprocess.run(
        ['git', '-C', str(ROOT.parent / 'bend'), 'rev-parse', 'HEAD'],
        check=True, capture_output=True, text=True).stdout.strip(),
    'base_comp_sha256': hashlib.sha256(base_comp.read_bytes()).hexdigest(),
    'candidate_comp_sha256': hashlib.sha256(candidate_comp.read_bytes()).hexdigest(),
    'candidate_patch_sha256': preparation.get(
        'local_representation_patch_sha256'),
    'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'artifacts': str(out),
    'expected': expected,
    'original_js': original_js,
    'original_native': original_native,
    'candidate_native': candidate_native,
    'candidate_js': candidate_js,
    'original_c_bytes': original.with_suffix('.c').stat().st_size,
    'candidate_c_bytes': candidate.with_suffix('.c').stat().st_size,
    'original_js_bytes': original.with_suffix('.js').stat().st_size,
    'candidate_js_bytes': candidate.with_suffix('.js').stat().st_size,
    'original_c_sha256': hashlib.sha256(original.with_suffix('.c').read_bytes()).hexdigest(),
    'candidate_c_sha256': hashlib.sha256(candidate.with_suffix('.c').read_bytes()).hexdigest(),
    'original_js_sha256': hashlib.sha256(original.with_suffix('.js').read_bytes()).hexdigest(),
    'candidate_js_sha256': hashlib.sha256(candidate.with_suffix('.js').read_bytes()).hexdigest(),
}
result['matches'] = (original_native == original_js == expected
                     and candidate_native == expected
                     and candidate_js == expected)
result['c_bytes_delta'] = (result['candidate_c_bytes']
                           - result['original_c_bytes'])
result['js_bytes_delta'] = (result['candidate_js_bytes']
                            - result['original_js_bytes'])
result['codegen_changed'] = (
    result['candidate_c_sha256'] != result['original_c_sha256']
    or result['candidate_js_sha256'] != result['original_js_sha256'])
args.output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
assert result['matches']
