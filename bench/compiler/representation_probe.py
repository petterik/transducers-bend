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
    # Deliberately retains affine function application. This is the negative
    # control for the native dispatch detector: a report that claims zero
    # dispatch sites must fail on this program.
    'dynamic_dispatch_control': (ROOT / 'tests/ownership.bend',
                                 '\n'.join(line[2:] for line in
                                           (ROOT / 'tests/ownership.bend').read_text().splitlines()
                                           if line.startswith('#|'))),
}

def run(command, extra=None):
    result = subprocess.run(list(map(str, command)),
                            env={**env, **(extra or {})},
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result

report = {
    'compiler_sha256': hashlib.sha256(
        (args.bend_main.parent / 'comp.ts').read_bytes()).hexdigest(),
    'library_sha256': hashlib.sha256(
        (ROOT / 'transduce.bend').read_bytes()).hexdigest(),
    'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'attribution': 'compiler-emitted call sites; site counts, not execution frequency',
    'cases': {}, 'artifacts': str(out),
}
for name, (source, expected) in cases.items():
    stem = out / name
    callsite_path = out / (name + '-callsite.json')
    run(['bun', args.bend_main, source, '-o', stem.with_suffix('.c'),
         '-o', stem.with_suffix('.js')],
        {'BEND_CALLSITE_REPORT': str(callsite_path)})
    c_text = stem.with_suffix('.c').read_text()
    js_text = stem.with_suffix('.js').read_text()
    run(['clang', '-std=c11', '-O3', stem.with_suffix('.c'), '-lpthread',
         '-lm', '-o', stem])
    native = run([stem, '--threads', '1', '--gpu', 'off']).stdout.strip()
    js = run(['bun', stem.with_suffix('.js')]).stdout.strip()
    assert native == js == expected, (name, native, js, expected)
    records = js_text.count('{$: "Reducer"') + js_text.count('{$: "Reduction"')
    closure_dispatch = c_text.count('WL_JMP(FID_CLO_APPLY)')
    callsites = json.loads(callsite_path.read_text())
    known_calls = [r for r in callsites if r.get('caller') and r.get('target')]
    unknown_calls = [r for r in callsites
                     if not r.get('caller') or not r.get('target')]
    dynamic_calls = [r for r in known_calls if r['target'] == 'Clo.apply']
    targets = {}
    for record in known_calls:
        key = record['target']
        targets[key] = targets.get(key, 0) + 1
    report['cases'][name] = {
        'source': str(source),
        'native': native,
        'js': js,
        'records_js': records,
        # `Clo.apply` is an internal compiler label and is not emitted in
        # native C. The runtime transfer is FID_CLO_APPLY; keep both fields so
        # old reports remain interpretable, but use the latter for conclusions.
        'clo_apply_label_c': c_text.count('Clo.apply'),
        'closure_dispatch_transfers_c': closure_dispatch,
        'callsite_records': len(callsites),
        'known_callsite_records': len(known_calls),
        'unknown_callsite_records': len(unknown_calls),
        'dynamic_callsite_records': len(dynamic_calls),
        'callsite_target_counts': targets,
        'callsite_attribution': ('inconclusive' if unknown_calls
                                 else 'known compiler-emitted caller/target sites'),
        'heap_alloc_calls_c': c_text.count('heap_alloc('),
        'term_pack_calls_c': c_text.count('term_pak('),
        'c_bytes': len(c_text),
        'js_bytes': len(js_text),
    }
    if name != 'dynamic_dispatch_control':
        assert records == 0
    else:
        assert records > 0, 'negative control unexpectedly specialized all reducer records'
        assert closure_dispatch > 0, 'negative control did not retain closure dispatch'
        assert dynamic_calls, 'negative control did not report Clo.apply call sites'
    assert not unknown_calls, 'call-site report contains an unattributed record'
args.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
