#!/usr/bin/env python3
"""Compare valid Array entry states in JS and native; exit 1 on disagreement."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--bend-main', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
source = Path(__file__).with_name('tree-entry-control.bend').resolve()
compiler = a.bend_main.resolve()
out = Path(tempfile.mkdtemp(prefix='transducer-tree-entry-review-'))
env = {**os.environ, 'BEND_NO_TELEMETRY': '1'}

def run(command):
    r = subprocess.run(list(map(str, command)), env=env, text=True,
                       capture_output=True, timeout=60)
    assert r.returncode == 0, (command, r.stdout, r.stderr)
    return r.stdout.strip()

run(['bun', compiler, source, '-o', out/'probe.c', '-o', out/'probe.js'])
run(['clang', '-std=c11', '-O3', out/'probe.c', '-lpthread', '-lm',
     '-o', out/'probe'])
expected = next(line[2:] for line in source.read_text().splitlines()
                if line.startswith('#|'))
js = run(['bun', out/'probe.js'])
native = run([out/'probe', '--threads', '1', '--gpu', 'off'])
c = (out/'probe.c').read_text()
report = {
    'compiler_sha256': hashlib.sha256((compiler.parent/'comp.ts').read_bytes()).hexdigest(),
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'artifacts': str(out),
    'expected': expected, 'js': js, 'native': native,
    'guarded_tree_markers': c.count('/* guarded_tree:'),
    'matches': js == native == expected,
}
a.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['matches'] else 1)
