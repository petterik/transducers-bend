#!/usr/bin/env python3
"""Exercise the guarded loop boundary on non-list sources and boxed state."""
import argparse
import hashlib
import json
from pathlib import Path
import os
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
a = parser.parse_args()

env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
out = Path(tempfile.mkdtemp(prefix='bend-source-shape-tests-')).resolve()

cases = {
    # String has one boxed recursive source input and scalar reducer state.  It
    # should use the same structural source proof as List without recognizing
    # the adapter name.
    'string': {
        'source': HERE / 'fixtures/string_transducer.bend',
        'guarded_loops': 1,
        'guarded_trees': 0,
        'output': '0:195:394',
    },
    # Array traversal has a tree-shaped source representation.  The candidate
    # can substitute a previously proved scalar callback chain while leaving
    # the source/control tree and generic fallback unchanged.
    'array': {
        'source': HERE / 'fixtures/array_transducer.bend',
        'guarded_loops': 0,
        'guarded_trees': 1,
        'output': '0:9:22',
    },
    # into_list keeps a boxed reducer state and result; scalar loop analysis
    # must refuse it while the generic list driver remains correct.
    'boxed_state': {
        'source': HERE / 'fixtures/boxed_state_transducer.bend',
        'guarded_loops': 0,
        'guarded_trees': 0,
        'output': '[]\n[4, 5]\n[4, 5]',
    },
}


def run(command, timeout=90):
    result = subprocess.run([str(part) for part in command], env=env,
                            capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result


report = {
    'artifacts': str(out),
    'compiler_sha256': hashlib.sha256((a.bend_main.parent / 'comp.ts').read_bytes()).hexdigest(),
    'cases': {},
}
for name, spec in cases.items():
    source = spec['source']
    stem = out / name
    run(['bun', a.bend_main, source, '-o', stem.with_suffix('.c'),
         '-o', stem.with_suffix('.js')])
    emitted = stem.with_suffix('.c').read_text()
    loops = emitted.count('/* guarded_loop:')
    trees = emitted.count('/* guarded_tree:')
    assert loops == spec['guarded_loops'], (name, loops, spec['guarded_loops'])
    assert trees == spec['guarded_trees'], (name, trees, spec['guarded_trees'])
    assert 'Clo.apply' not in emitted, name
    run(['clang', '-std=c11', '-O3', stem.with_suffix('.c'), '-lpthread', '-lm',
         '-o', stem])
    native = run([stem, '--threads', '1', '--gpu', 'off'])
    js = run(['bun', stem.with_suffix('.js')])
    assert native.stdout.strip() == spec['output'], (name, 'native', native.stdout)
    assert js.stdout.strip() == spec['output'], (name, 'js', js.stdout)
    report['cases'][name] = {
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'guarded_loop_comments': loops,
        'guarded_tree_comments': trees,
        'native_output': native.stdout.strip(),
        'js_output': js.stdout.strip(),
        'c_bytes': stem.with_suffix('.c').stat().st_size,
    }
    print('PASS', name, 'guarded_loop', loops, flush=True)

a.output.write_text(json.dumps(report, indent=2) + '\n')
print('PASS source-shape boundaries')
