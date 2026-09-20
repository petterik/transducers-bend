#!/usr/bin/env python3
"""Reproduce follow-up review findings; exit nonzero while either bug remains."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--bend-main', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
candidate = a.bend_main.resolve()
reference = ROOT.parent / 'bend/bend2/main.ts'
env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}

def run(cmd):
    r = subprocess.run(list(map(str, cmd)), env=env, capture_output=True,
                       text=True, timeout=90)
    assert r.returncode == 0, (cmd, r.stdout, r.stderr)
    return r.stdout.strip()

report = {'candidate_sha256': hashlib.sha256(
    candidate.with_name('comp.ts').read_bytes()).hexdigest(),
    'reference_sha256': hashlib.sha256(
        reference.with_name('comp.ts').read_bytes()).hexdigest(), 'cases': []}
with tempfile.TemporaryDirectory(prefix='followup-review-') as d:
    for fixture, scenarios in [
        ('shared_constructor_fact', [([], '112'), (['fact'], '213')]),
        ('keep_reference_boundary', [([], '1\n1')]),
    ]:
        source = ROOT / 'review' / (fixture + '.bend')
        for lane, compiler in [('reference', reference), ('candidate', candidate)]:
            stem = Path(d) / (fixture + '-' + lane)
            run(['bun', compiler, source, '-o', stem.with_suffix('.js'),
                 '-o', stem.with_suffix('.c')])
            run(['clang', '-std=c11', '-O1', '-fsanitize=undefined',
                 '-fno-sanitize-recover=all', stem.with_suffix('.c'),
                 '-lpthread', '-lm', '-o', stem])
            for argv, expected in scenarios:
                native = run([stem, '--threads', '1', '--gpu', 'off', '--', *argv])
                js = run(['bun', stem.with_suffix('.js'), *argv])
                report['cases'].append({'fixture': fixture, 'lane': lane,
                    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                    'argv': argv, 'expected': expected, 'native': native, 'js': js,
                    'passes': native == js == expected})
report['passes'] = all(c['passes'] for c in report['cases'])
a.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['passes'] else 1)
