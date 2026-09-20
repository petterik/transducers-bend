#!/usr/bin/env python3
"""Compare delayed and eager reducer binding on Array and extensions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
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
out = Path(tempfile.mkdtemp(prefix='bend-static-eager-')).resolve()

def run(command, extra=None):
    result = subprocess.run(list(map(str, command)),
                            env={**env, **(extra or {})},
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result

def expected(source):
    return '\n'.join(line[2:] for line in source.read_text().splitlines()
                     if line.startswith('#|'))

def prepare(root, eager):
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'tests', root / 'tests')
    shutil.copytree(ROOT / 'examples', root / 'examples')
    source = (ROOT / 'transduce.bend').read_text()
    if eager:
        source = source.replace('~recipe: Unit -> Reducer<A, R>',
                                '~recipe: Reducer<A, R>')
        source = source.replace('recipe(Unit{})', 'recipe')
        source = source.replace('~(u => r),', '~r,')
    (root / 'transduce.bend').write_text(source)
    if eager:
        tree = (root / 'examples/tree.bend').read_text()
        (root / 'examples/tree.bend').write_text(tree.replace('~(u => r),', '~r,'))

def build_case(root, source_name, lane):
    source = root / 'tests' / source_name
    stem = out / f'{lane}-{source.stem}'
    stats = stem.with_suffix('.stats.json')
    run(['bun', args.bend_main, source, '-o', stem.with_suffix('.c'),
         '-o', stem.with_suffix('.js')],
        {**env, 'BEND_STATIC_REPORT': str(stats)})
    c_text = stem.with_suffix('.c').read_text()
    js_text = stem.with_suffix('.js').read_text()
    run(['clang', '-std=c11', '-O2', stem.with_suffix('.c'), '-lpthread',
         '-lm', '-o', stem])
    native = run([stem, '--threads', '1', '--gpu', 'off']).stdout.strip()
    js = run(['bun', stem.with_suffix('.js')]).stdout.strip()
    want = expected(source)
    assert native == js == want, (lane, source_name, native, js, want)
    static_stats = json.loads(stats.read_text()) if stats.exists() else None
    return {
        'expected': want,
        'native': native,
        'js': js,
        'reducer_records_js': js_text.count('{$: "Reducer"'),
        'reduction_records_js': js_text.count('{$: "Reduction"'),
        'closure_dispatch_transfers_c': c_text.count('WL_JMP(FID_CLO_APPLY)'),
        'c_bytes': len(c_text),
        'js_bytes': len(js_text),
        'static_fun_stats': static_stats,
    }

delayed_root = out / 'delayed'
eager_root = out / 'eager'
prepare(delayed_root, False)
prepare(eager_root, True)
results = {'compiler_sha256': hashlib.sha256(
    (args.bend_main.parent / 'comp.ts').read_bytes()).hexdigest(),
    'cases': {}, 'artifacts': str(out)}
for source_name in ['array.bend', 'keep_partition.bend', 'api_surface.bend']:
    results['cases'][source_name] = {
        'delayed': build_case(delayed_root, source_name, 'delayed'),
        'eager': build_case(eager_root, source_name, 'eager'),
    }
args.output.write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
