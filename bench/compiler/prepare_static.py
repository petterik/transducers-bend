#!/usr/bin/env python3
"""Build an isolated candidate from the bendlang/bend main ref.

The candidate reapplies this repository's bounded static-callback pass and
optional call-site diagnostics. The sibling Bend checkout is read through
`git archive` and never modified.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BEND_REPO = ROOT.parent / 'bend'
BEND_MAIN_REF = 'refs/remotes/bendlang/main'
EXPECTED_COMP_SHA = '10afb08dd55a52bfbb88fdf84534cebdc000bdf7820c69cee1d6bb3fcfaf7d7b'

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir', type=Path)
parser.add_argument('--diagnostics', action='store_true',
                    help='emit structured call-site records during compilation')
parser.add_argument('--identity-self-test', action='store_true',
                    help='inject and run bounded static-template identity checks')
args = parser.parse_args()

base_commit = subprocess.run(
    ['git', '-C', str(BEND_REPO), 'rev-parse', '--verify',
     f'{BEND_MAIN_REF}^{{commit}}'], capture_output=True, text=True,
    check=True).stdout.strip()
archive = subprocess.run(
    ['git', '-C', str(BEND_REPO), 'archive', '--format=tar', base_commit,
     'bend2'], capture_output=True, check=True).stdout

source_tmp = tempfile.TemporaryDirectory(prefix='bend-main-source-')
with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as bundle:
    bundle.extractall(source_tmp.name)
SOURCE = Path(source_tmp.name) / 'bend2'
original = (SOURCE / 'comp.ts').read_text()
source_comp_sha = hashlib.sha256(original.encode()).hexdigest()
assert source_comp_sha == EXPECTED_COMP_SHA, (
    f'Bend comp.ts changed at {base_commit} ({source_comp_sha}); '
    'review and update the isolated patches before continuing')

out = args.output_dir.resolve() if args.output_dir else Path(
    tempfile.mkdtemp(prefix='bend-static-cache-')).resolve()
out.mkdir(parents=True, exist_ok=True)
assert not any(out.iterdir()), 'Refuse to overwrite an existing directory'
for name in ['main.ts', 'bend.ts', 'base.bend']:
    shutil.copy2(SOURCE / name, out / name)
shutil.copytree(SOURCE / 'effs', out / 'effs')
source_tmp.cleanup()

# Reapply the specialization pass from this repository on the selected Bend
# ref. This keeps callback optimization out of the sibling checkout.
STATIC_CALLBACK_PASS = (HERE / 'static_callback_pass.ts.inc').read_text()
def_body_anchors = [
    'function def_body(cb: Carb, k: Bend.Name): TLD | undefined {',
    'function def_body(cb: Carb, k: Name): TLD | undefined {',
]
matching_def_body_anchors = [anchor for anchor in def_body_anchors
                             if original.count(anchor) == 1]
assert len(matching_def_body_anchors) == 1, (
    'expected exactly one reviewed def_body anchor for this compiler ref')
def_body_anchor = matching_def_body_anchors[0]
patched = original.replace(def_body_anchor,
    STATIC_CALLBACK_PASS + def_body_anchor, 1)
old_body = '    const h = Bend.term_higher(tld.e);'
assert patched.count(old_body) == 1
patched = patched.replace(old_body,
    '    // Materialize the bounded rewrite once; emission may open a body repeatedly.\n'
    '    const h = Bend.term_higher(Bend.term_lower(\n'
    '      specialize(cb.book, Bend.term_higher(tld.e))));', 1)

old = 'function static_fun(book: Book, t: HTerm): HTerm | null {'
assert patched.count(old) == 1
patched = patched.replace(old,
                           'function static_fun_uncached(book: Book, t: HTerm): HTerm | null {',
                           1)
anchor = '// Keep annotations and bind a dynamic argument once when eliminating a\n'
assert patched.count(anchor) == 1
cache = '''// Cache only closed heads. A lambda can capture an outer runtime variable,
// and term_key does not encode that variable's runtime environment. Open heads
// are evaluated without caching so one call site cannot reuse another's value.
function static_term_closed(term: Bend.LTerm): boolean {
  let fuel = 8192;
  const walk = (value: unknown, depth: number): boolean => {
    if (--fuel < 0) return false;
    if (Array.isArray(value)) return value.every((item) => walk(item, depth));
    if (value === null || typeof value !== "object") return true;
    const node = value as Record<string, unknown>;
    if (node.$ === "Var") {
      return typeof node.i === "number" && node.i >= 0 && node.i < depth;
    }
    if (node.$ === "Lam") return walk(node.f, depth + 1);
    if (node.$ === "All") {
      return walk(node.A, depth) && walk(node.B, depth + 1);
    }
    if (node.$ === "Let") {
      const count = Array.isArray(node.k) ? node.k.length : 0;
      return walk(node.v, depth) && walk(node.f, depth + count);
    }
    return Object.entries(node).every(([key, child]) =>
      key === "s" || key === "k" || key === "q" || key === "i"
        ? true : walk(child, depth));
  };
  return walk(term, 0);
}

// The checked Book and its template table are fixed during code generation.
// The normalized key retains annotations/instance structure and drops spans.
const STATIC_FUN_CACHE = new WeakMap<object, Map<string, HTerm | null>>();
const STATIC_FUN_STATS = { queries: 0, hits: 0, misses: 0, refusals: 0 };
if (process.env.BEND_STATIC_REPORT) {
  process.on("exit", () => fs.writeFileSync(process.env.BEND_STATIC_REPORT!,
    JSON.stringify(STATIC_FUN_STATS) + "\\n"));
}
function static_fun(book: Book, t: HTerm): HTerm | null {
  STATIC_FUN_STATS.queries++;
  const lowered = Bend.term_lower(t);
  if (!static_term_closed(lowered)) {
    STATIC_FUN_STATS.misses++;
    const result = static_fun_uncached(book, t);
    if (result === null) STATIC_FUN_STATS.refusals++;
    return result;
  }
  const book_key = book as object;
  const term_key = Bend.term_key(lowered);
  let cache = STATIC_FUN_CACHE.get(book_key);
  if (cache === undefined) {
    cache = new Map<string, HTerm | null>();
    STATIC_FUN_CACHE.set(book_key, cache);
  }
  if (cache.has(term_key)) {
    STATIC_FUN_STATS.hits++;
    return cache.get(term_key) ?? null;
  }
  STATIC_FUN_STATS.misses++;
  const result = static_fun_uncached(book, t);
  if (result === null) STATIC_FUN_STATS.refusals++;
  cache.set(term_key, result);
  return result;
}

'''
patched = patched.replace(anchor, cache + anchor, 1)

if args.diagnostics:
    emit_anchor = '// Emit\n// ====\n'
    assert patched.count(emit_anchor) == 1
    diagnostics = '''// Structured code-generation records. These describe emitted
// sites, not runtime execution counts. A record is only used for attribution
// when its caller and target are known; consumers must treat unknown edges as
// inconclusive rather than as zero cost.
const CALLSITE_REPORT: {
  kind: string; caller: string; target: string; segment: string;
  flat?: boolean; helper?: string;
}[] = [];
function callsite(kind: string, caller: string, target: string,
  segment: string, extra: { flat?: boolean; helper?: string } = {}): void {
  CALLSITE_REPORT.push({ kind, caller, target, segment, ...extra });
}
if (process.env.BEND_CALLSITE_REPORT) {
  process.on("exit", () => fs.writeFileSync(process.env.BEND_CALLSITE_REPORT!,
    JSON.stringify(CALLSITE_REPORT) + "\\n"));
}

'''
    patched = patched.replace(emit_anchor, diagnostics + emit_anchor, 1)
    fuse_emit_anchor = 'function emit_fuse(fl: File, ck: Call, dst: Dst, tail = false): void {\n'
    assert patched.count(fuse_emit_anchor) == 1
    patched = patched.replace(fuse_emit_anchor,
        fuse_emit_anchor + '  callsite("fuse", fl.seg.def, ck.k, fl.seg.fid,\n'
        '    { flat: flat_of(ck.k) });\n', 1)
    jump_emit_anchor = 'function emit_jump(fl: File, args: string[], k: Name,\n  bang?: boolean): void {\n'
    assert patched.count(jump_emit_anchor) == 1
    patched = patched.replace(jump_emit_anchor,
        jump_emit_anchor + '  callsite("jump", fl.seg.def, k, fl.seg.fid);\n', 1)
    native_emit_anchor = 'function emit_native(fl: File, ck: Call, ers: HTerm[]): string {\n'
    assert patched.count(native_emit_anchor) == 1
    patched = patched.replace(native_emit_anchor,
        native_emit_anchor + '  callsite("native", fl.seg.def, ck.k, fl.seg.fid);\n', 1)
    closure_emit_anchor = 'function emit_clo(fl: File, x: HTerm, ty: HTerm | null): Val {\n'
    assert patched.count(closure_emit_anchor) == 1
    patched = patched.replace(closure_emit_anchor,
        closure_emit_anchor + '  callsite("closure", fl.seg.def, "closure", fl.seg.fid);\n', 1)

if args.identity_self_test:
    identity_tests = (HERE / 'static_identity_selftest.ts.inc').read_text()
    assert patched.count(def_body_anchor) == 1
    patched = patched.replace(def_body_anchor, identity_tests + def_body_anchor, 1)

(out / 'comp.ts').write_text(patched)
candidate_comp_sha = hashlib.sha256(patched.encode()).hexdigest()
(out / 'prepare-static.json').write_text(json.dumps({
    'base_ref': 'bendlang/main',
    'base_commit': base_commit,
    'base_comp_sha256': source_comp_sha,
    'reapplied_specialization_from': 'b1f9c93684411b16881632a6633f5d0082447449',
    'specialization_source_sha256': hashlib.sha256(
        (HERE / 'static_callback_pass.ts.inc').read_bytes()).hexdigest(),
    'candidate_comp_sha256': candidate_comp_sha,
    'memoized_static_evaluation': True,
    'structured_callsite_diagnostics': args.diagnostics,
    'identity_self_test_injected': args.identity_self_test,
}, indent=2) + '\n')

smoke = out / 'smoke.js'
subprocess.run(['bun', str(out / 'main.ts'), str(ROOT / 'tests/pipeline.bend'),
                '-o', smoke], check=True)
assert smoke.exists()

specialization = out / 'specialization.js'
subprocess.run(['bun', str(out / 'main.ts'),
                str(ROOT / 'tests/api_surface.bend'), '-o', specialization],
               check=True)
specialized_js = specialization.read_text()
assert '{$: "Reducer"' not in specialized_js, (
    'static callback specialization left runtime Reducer records')
assert '{$: "Reduction"' not in specialized_js, (
    'static callback specialization left runtime Reduction records')

env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
for fixture in sorted((HERE / 'fixtures').glob('static_callback_*.bend')):
    expected = '\n'.join(line[2:] for line in fixture.read_text().splitlines()
                         if line.startswith('#|'))
    assert expected, f'{fixture.name}: missing expected output'
    stem = out / fixture.stem
    subprocess.run(['bun', str(out / 'main.ts'), str(fixture),
                    '-o', str(stem) + '.js', '-o', str(stem)],
                   env=env, check=True, capture_output=True, text=True)
    for lane, command in [
        ('JS', ['bun', str(stem) + '.js']),
        ('native', [str(stem), '--threads', '1', '--gpu', 'off']),
    ]:
        result = subprocess.run(command, env=env, check=True,
                                capture_output=True, text=True, timeout=20)
        assert result.stdout.strip() == expected, (
            fixture.name, lane, result.stdout, expected)
    print(f'PASS {fixture.name}')
print(f'base bendlang/main {base_commit}')
print(out / 'main.ts')
