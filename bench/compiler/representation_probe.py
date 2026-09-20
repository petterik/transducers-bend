#!/usr/bin/env python3
"""Inspect residual representation costs without claiming allocation freedom."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
out = Path(tempfile.mkdtemp(prefix='bend-representation-probe-')).resolve()
cases = {
    'scalar': (ROOT / 'tests/pipeline.bend',
               '\n'.join(line[2:] for line in
                         (ROOT / 'tests/pipeline.bend').read_text().splitlines()
                         if line.startswith('#|'))),
    'buffered': (ROOT / 'tests/keep_partition.bend',
                 '\n'.join(line[2:] for line in
                           (ROOT / 'tests/keep_partition.bend').read_text().splitlines()
                           if line.startswith('#|'))),
}

def run(command):
    result = subprocess.run(list(map(str, command)), env=env,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result

report = {
    'compiler_sha256': hashlib.sha256(
        (args.bend_main.parent / 'comp.ts').read_bytes()).hexdigest(),
    'cases': {}, 'artifacts': str(out),
}
for name, (source, expected) in cases.items():
    stem = out / name
    run(['bun', args.bend_main, source, '-o', stem.with_suffix('.c'),
         '-o', stem.with_suffix('.js')])
    c_text = stem.with_suffix('.c').read_text()
    js_text = stem.with_suffix('.js').read_text()
    run(['clang', '-std=c11', '-O3', stem.with_suffix('.c'), '-lpthread',
         '-lm', '-o', stem])
    native = run([stem, '--threads', '1', '--gpu', 'off']).stdout.strip()
    js = run(['bun', stem.with_suffix('.js')]).stdout.strip()
    assert native == js == expected, (name, native, js, expected)
    records = js_text.count('{$: "Reducer"') + js_text.count('{$: "Reduction"')
    report['cases'][name] = {
        'source': str(source),
        'native': native,
        'js': js,
        'records_js': records,
        'clo_apply_c': c_text.count('Clo.apply'),
        'heap_alloc_calls_c': c_text.count('heap_alloc('),
        'term_pack_calls_c': c_text.count('term_pak('),
        'c_bytes': len(c_text),
        'js_bytes': len(js_text),
    }
    assert records == 0 and report['cases'][name]['clo_apply_c'] == 0
args.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
