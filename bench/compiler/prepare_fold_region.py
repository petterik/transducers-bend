#!/usr/bin/env python3
"""Build and validate the isolated typed producer/fold candidate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PASS = HERE / 'fold_region_pass.ts.inc'
BASE_PREPARER = HERE / 'prepare_static.py'

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir', type=Path, required=True,
                    help='new directory for the isolated compiler candidate')
args = parser.parse_args()

out = args.output_dir.resolve()
env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
subprocess.run([sys.executable, str(BASE_PREPARER), '--output-dir', str(out)],
               env=env, check=True, timeout=60)

compiler = out / 'main.ts'
comp = out / 'comp.ts'
source = comp.read_text()
body_anchor = 'function def_body(cb: Carb, k: Name): TLD | undefined {\n'
assert source.count(body_anchor) == 1, 'upstream def_body anchor changed'
source = source.replace(body_anchor, PASS.read_text() + '\n' + body_anchor, 1)

old = '''    const h = Bend.term_higher(Bend.term_lower(
      specialize(cb.book, Bend.term_higher(tld.e))));
    const n = tld.n + Math.min(def_raise(cb.book, h, tld.n),
      tele_unbind(cb.book, tld.T).doms.length - tld.n);
    cb.book.tlds[k] = { ...tld, n, h };'''
new = '''    const h0 = Bend.term_higher(Bend.term_lower(
      specialize(cb.book, Bend.term_higher(tld.e))));
    // Publish the checked body before analyzing calls in it. This breaks
    // recursive def_body lookups during structural analysis.
    cb.book.tlds[k] = { ...tld, h: h0 };
    const h = fold_region_rewrite(cb, h0);
    const n = tld.n + Math.min(def_raise(cb.book, h, tld.n),
      tele_unbind(cb.book, tld.T).doms.length - tld.n);
    cb.book.tlds[k] = { ...tld, n, h };'''
assert source.count(old) == 1, 'static callback body anchor changed'
source = source.replace(old, new, 1)
comp.write_text(source)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_fixture(name, source_path, expected, reports_dir):
    stem = reports_dir / name
    report_path = reports_dir / (name + '-fold-region.json')
    fixture_env = {**env, 'BEND_FOLD_REGION_REPORT': str(report_path)}
    subprocess.run(['bun', str(compiler), str(source_path),
                    '-o', str(stem) + '.js', '-o', str(stem)],
                   env=fixture_env, check=True, capture_output=True,
                   text=True, timeout=30)
    outputs = [
        subprocess.run(['bun', str(stem) + '.js'], env=env, check=True,
                       capture_output=True, text=True, timeout=15).stdout.strip(),
        subprocess.run([str(stem), '--threads', '1', '--gpu', 'off'],
                       env=env, check=True, capture_output=True, text=True,
                       timeout=15).stdout.strip(),
    ]
    assert outputs == [expected, expected], (name, outputs, expected)
    stats = json.loads(report_path.read_text())
    return {'output': outputs[0], 'fold_region_stats': stats}


verification = out / 'fold-region-verification'
verification.mkdir()
subprocess.run([sys.executable, str(ROOT / 'tests/run.py'),
                '--bend-main', str(compiler)], env=env, check=True, timeout=180)

results = {
    'custom_producer_fold': check_fixture(
        'custom-producer-fold', ROOT / 'tests/custom_producer_fold.bend',
        '(True{}, True{})', verification),
    'dynamic_map_fold': check_fixture(
        'dynamic-map-fold', ROOT / 'bench/array_partition/dynamic_map_fold_probe.bend',
        '(True{}, True{})', verification),
    'independent_source_adapter': check_fixture(
        'fold-region-source-adapter', ROOT / 'tests/fold_region_source_adapter.bend',
        '(True{}, True{})', verification),
    'affine_elements': check_fixture(
        'fold-region-affine', ROOT / 'tests/fold_region_affine.bend',
        'True{}', verification),
    'type_changing_map_fold': check_fixture(
        'fold-region-type-changing',
        ROOT / 'tests/fold_region_type_changing.bend',
        '(True{}, True{}, True{}, True{}, True{}, True{})', verification),
    'retention_and_unknown_consumer_bailout': check_fixture(
        'fold-region-bailouts', ROOT / 'tests/fold_region_bailouts.bend',
        '(True{}, True{}, True{}, True{}, True{})', verification),
}
for key in ('custom_producer_fold', 'dynamic_map_fold',
            'independent_source_adapter', 'affine_elements',
            'type_changing_map_fold'):
    stats = results[key]['fold_region_stats']
    assert stats['fused'] > 0 and stats['helpers'] >= 2 \
        and stats['rechecked'] == stats['helpers'], (key, stats)
bailout_stats = results['retention_and_unknown_consumer_bailout']['fold_region_stats']
assert bailout_stats['fused'] == 0 and bailout_stats['helpers'] == 0 \
    and bailout_stats['rechecked'] == 0, bailout_stats
assert bailout_stats['refusals'].get('producer-call-shape', 0) > 0, bailout_stats

baseline = json.loads((out / 'prepare-static.json').read_text())
metadata = {
    'base_commit': baseline['base_commit'],
    'base_comp_sha256': baseline['base_comp_sha256'],
    'static_callback_candidate_comp_sha256': baseline['candidate_comp_sha256'],
    'fold_region_pass_sha256': sha256(PASS),
    'fold_region_candidate_comp_sha256': sha256(comp),
    'fold_region': 'single-use direct recursive List producer into a structurally checked tail fold',
    'callback_gate': 'closed checked definitions; reject unsafe, foreign, parallel, dynamic closure calls, and non-whitelisted intrinsic calls',
    'type_gate': 'producer input/output List element types may differ; producer output List must match fold input List',
    'generated_helper_check': 'Bend.def_check validates each synthesized recursive helper before it is installed',
    'verification': results,
}
(out / 'prepare-fold-region.json').write_text(json.dumps(metadata, indent=2) + '\n')
print(json.dumps(metadata, indent=2))
