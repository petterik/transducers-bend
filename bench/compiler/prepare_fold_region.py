#!/usr/bin/env python3
"""Build and validate the isolated typed producer/fold candidate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
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
        '(True{}, True{}, True{}, True{}, True{}, True{}, True{})', verification),
    'single_use_let_alias': check_fixture(
        'fold-region-let-alias', ROOT / 'tests/fold_region_let_alias.bend',
        'True{}', verification),
    'map_filter_skip_experiment': check_fixture(
        'fold-region-map-filter', ROOT / 'tests/fold_region_map_filter.bend',
        '(True{}, True{}, True{}, True{}, True{})', verification),
    'callback_totality_bailout': check_fixture(
        'fold-region-totality', ROOT / 'tests/fold_region_totality_bailout.bend',
        '(True{}, True{}, True{})', verification),
    'map_filter_retains_values': check_fixture(
        'fold-region-map-filter-retains',
        ROOT / 'tests/fold_region_map_filter_retains.bend',
        'True{}', verification),
    'map_filter_type_change': check_fixture(
        'fold-region-map-filter-type-change',
        ROOT / 'tests/fold_region_map_filter_type_change.bend',
        'True{}', verification),
    'retention_and_unknown_consumer_bailout': check_fixture(
        'fold-region-bailouts', ROOT / 'tests/fold_region_bailouts.bend',
        '(True{}, True{}, True{}, True{}, True{}, True{})', verification),
}
for key in ('custom_producer_fold', 'dynamic_map_fold',
            'independent_source_adapter', 'affine_elements',
            'type_changing_map_fold'):
    stats = results[key]['fold_region_stats']
    assert stats['fused'] > 0 and stats['helpers'] >= 2 \
        and stats['rechecked'] == stats['helpers'], (key, stats)
let_stats = results['single_use_let_alias']['fold_region_stats']
assert let_stats['let_alias_fused'] > 0 and let_stats['helpers'] >= 1 \
    and let_stats['rechecked'] == let_stats['helpers'], let_stats
map_filter_stats = results['map_filter_skip_experiment']['fold_region_stats']
assert map_filter_stats['fused'] > 0 and map_filter_stats['helpers'] > 0 \
    and map_filter_stats['rechecked'] == map_filter_stats['helpers'], map_filter_stats
region = map_filter_stats['region']
assert region['extracted'] > 0 and region['branches'] > 0 \
    and region['emits'] > 0 and region['skips'] > 0, region
assert region['shapes'].get('1:0:1:0>1:1:1:1', 0) > 0, region['shapes']
assert map_filter_stats['refusals'].get('generated-helper-typecheck', 0) == 0, \
    map_filter_stats
bailout_stats = results['retention_and_unknown_consumer_bailout']['fold_region_stats']
assert bailout_stats['fused'] == 0 and bailout_stats['helpers'] == 0 \
    and bailout_stats['rechecked'] == 0, bailout_stats
assert bailout_stats['let_alias_fused'] == 0, bailout_stats
assert bailout_stats['refusals'].get('producer-call-shape', 0) > 0, bailout_stats

totality_stats = results['callback_totality_bailout']['fold_region_stats']
assert totality_stats['fused'] > 0 and totality_stats['helpers'] > 0 \
    and totality_stats['rechecked'] == totality_stats['helpers'], totality_stats
assert totality_stats['region']['refusals'].get(
    'region-emit-shape-or-totality', 0) > 0, totality_stats
assert totality_stats['region']['refusals'].get(
    'region-total-callback:recursive_zero', 0) > 0, totality_stats
assert totality_stats['region']['refusals'].get(
    'region-total-callback:multiply_by_five', 0) > 0, totality_stats

retained_stats = results['map_filter_retains_values']['fold_region_stats']
assert retained_stats['fused'] > 0 and retained_stats['helpers'] > 0 \
    and retained_stats['rechecked'] == retained_stats['helpers'], retained_stats
assert retained_stats['region']['branches'] > 0 \
    and retained_stats['region']['skips'] > 0, retained_stats
type_change_stats = results['map_filter_type_change']['fold_region_stats']
assert type_change_stats['fused'] > 0 and type_change_stats['helpers'] > 0 \
    and type_change_stats['rechecked'] == type_change_stats['helpers'], \
    type_change_stats

# Structural code-generation check: the source fixture's static input leaves
# no dynamic Con allocation. Upstream allocates producer List cells here, while
# the fused candidate emits none; closure/task allocations are measured later.
map_filter_fixture = ROOT / 'tests/fold_region_map_filter.bend'
upstream_main = ROOT.parent / 'bend' / 'bend2' / 'main.ts'
upstream_c = verification / 'map-filter-upstream.c'
candidate_c = verification / 'map-filter-fold-region.c'
subprocess.run(['bun', str(upstream_main), str(map_filter_fixture),
                '-o', str(upstream_c)], env=env, check=True, timeout=30)
candidate_c_report = verification / 'map-filter-codegen-fold-region.json'
subprocess.run(['bun', str(compiler), str(map_filter_fixture),
                '-o', str(candidate_c)],
               env={**env, 'BEND_FOLD_REGION_REPORT': str(candidate_c_report)},
               check=True, timeout=30)
upstream_code = upstream_c.read_text()
candidate_code = candidate_c.read_text()
dynamic_cons = re.compile(r'term_ctr\(CID_CON,\s*_nd_\d+\)')
upstream_dynamic_cons = len(dynamic_cons.findall(upstream_code))
candidate_dynamic_cons = len(dynamic_cons.findall(candidate_code))
assert upstream_dynamic_cons > 0 and candidate_dynamic_cons == 0, {
    'upstream_dynamic_list_cons_sites': upstream_dynamic_cons,
    'candidate_dynamic_list_cons_sites': candidate_dynamic_cons,
}

baseline = json.loads((out / 'prepare-static.json').read_text())
metadata = {
    'base_commit': baseline['base_commit'],
    'base_comp_sha256': baseline['base_comp_sha256'],
    'static_callback_candidate_comp_sha256': baseline['candidate_comp_sha256'],
    'fold_region_pass_sha256': sha256(PASS),
    'fold_region_candidate_comp_sha256': sha256(comp),
    'fold_region': 'direct recursive List producers with zero-or-one per-item Emit/Skip stages into a checked full tail fold; map-only aliases remain supported',
    'callback_gate': 'closed checked definitions; reject unsafe, foreign, parallel, dynamic closure calls, and non-whitelisted intrinsic calls',
    'type_gate': 'producer input/output List element types may differ; producer output List must match fold input List',
    'let_gate': 'only one binding, exactly one use, and immediate use as the fold input; otherwise keep the original term',
    'map_filter_experiment': 'a checked reusable custom map producer followed by List.filter and List.foldl; empty, all-rejected, step-count, ordered-hash, retained-value, and type-changing Nat-to-U32 cases pass on JS/native; the typed region lowers Bind/Emit followed by Branch(Emit|Skip)',
    'producer_step_region': 'bounded checked region; values retain stable Probe identities and element types; helper calls are expanded by applying their checked body, with call-graph cycle, effect, intrinsic-totality, ownership, and node-budget checks; zero-or-one output per path',
    'callback_totality_bailout': 'recursive and potentially overflowing Nat mappers both execute successfully on these finite fixtures but remain unfused; a guarded U32.shln mapper fuses, confirming the audited operation is total',
    'map_filter_api_constraint': 'standard List.map returns List<&1, B>, while List.filter requires List<&2, A>; the composed test uses a checked producer returning a reusable list',
    'generated_helper_check': 'Bend.def_check validates each synthesized recursive helper before it is installed',
    'map_filter_codegen': {
        'upstream_dynamic_list_cons_sites': upstream_dynamic_cons,
        'candidate_dynamic_list_cons_sites': candidate_dynamic_cons,
        'upstream_c_bytes': len(upstream_code.encode()),
        'candidate_c_bytes': len(candidate_code.encode()),
        'interpretation': 'the generated producer List cells are absent; generated closure/task allocations remain and require a separate allocation/timing measurement',
    },
    'verification': results,
}
(out / 'prepare-fold-region.json').write_text(json.dumps(metadata, indent=2) + '\n')
print(json.dumps(metadata, indent=2))
