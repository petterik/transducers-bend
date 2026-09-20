#!/usr/bin/env python3
"""Check the typed loop pass on a boxed List source and scalar reducer state."""
import argparse
import hashlib
import json
from pathlib import Path
import os
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--bend-main', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
out = Path(tempfile.mkdtemp(prefix='bend-list-driver-tests-')).resolve()
source = HERE / 'fixtures/list_transducer.bend'
env = {**os.environ, 'BEND_NO_TELEMETRY': '1'}

def run(cmd, ok=True):
    result = subprocess.run(list(map(str, cmd)), env=env, text=True,
                            capture_output=True, timeout=90)
    if ok:
        assert result.returncode == 0, (cmd, result.stdout, result.stderr)
    return result

report = {
    'artifacts': str(out),
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'compiler_sha256': hashlib.sha256((a.bend_main.parent / 'comp.ts').read_bytes()).hexdigest(),
}
observed = {}
for label, compiler in [('original', ROOT.parent / 'bend/bend2/main.ts'),
                        ('automatic', a.bend_main)]:
    stem = out / label
    run(['bun', compiler, source, '-o', stem.with_suffix('.c')])
    c = stem.with_suffix('.c').read_text()
    observed[label] = c.count('/* guarded_loop:')
    if label == 'original':
        assert observed[label] == 0
    else:
        assert observed[label] == 1
        assert 'Clo.apply' not in c
    run(['clang', '-std=c11', '-O3', stem.with_suffix('.c'), '-lpthread', '-lm', '-o', stem])
    native = run([stem, '--threads', '1', '--gpu', 'off'])
    assert native.stdout.strip() == '0:0:495:2820030815', native.stdout

report['guarded_loop_comments'] = observed
report['result'] = '0:0:495:2820030815'
a.output.write_text(json.dumps(report, indent=2) + '\n')
print('PASS boxed List source driver')
