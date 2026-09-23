#!/usr/bin/env python3
"""Build an isolated candidate from a reviewed Bend compiler ref.

The candidate reapplies this repository's static-callback specialization, then
adds the optional memoization, scoped-facts and call-site diagnostics
experiments. The default stays on the fork ref until upstream gates pass. The
sibling Bend checkout is read through `git archive` and never modified.
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
EXPECTED_COMP_SHAS = {
    '0939b98d013ab58d82619e35c0d4900b72c9d8e5b478f0e1df7822fe713c9b48',
    '10afb08dd55a52bfbb88fdf84534cebdc000bdf7820c69cee1d6bb3fcfaf7d7b',
}

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir', type=Path)
parser.add_argument('--base-ref', default='origin/main',
                    help='local Bend git ref to archive (default: origin/main)')
parser.add_argument('--facts', action='store_true',
                    help='also enable the scoped constructor-match fact pass')
parser.add_argument('--diagnostics', action='store_true',
                    help='emit structured call-site records during compilation')
args = parser.parse_args()

base_commit = subprocess.run(
    ['git', '-C', str(BEND_REPO), 'rev-parse', '--verify',
     f'{args.base_ref}^{{commit}}'], capture_output=True, text=True,
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
assert source_comp_sha in EXPECTED_COMP_SHAS, (
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
    jump_emit_anchor = 'function emit_jump(fl: File, args: string[], k: Bend.Name): void {\n'
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

if args.facts:
    args_anchor = 'function emit_args(fl: File, ck: Call, jump = false, fork = false): string[] {'
    assert patched.count(args_anchor) == 1
    patched = patched.replace(args_anchor,
        'function emit_args(fl: File, ck: Call, jump = false, fork = false,\n'
        '  out?: Val[]): string[] {', 1)
    args_val_anchor = '    const v = val_to(fl, b, lays[i]);\n    return !brw[i] ? val_own(fl, v)'
    assert patched.count(args_val_anchor) == 1
    patched = patched.replace(args_val_anchor,
        '    const v = val_to(fl, b, lays[i]);\n'
        '    out?.push(v);\n'
        '    return !brw[i] ? val_own(fl, v)', 1)
    fuse_anchor = '  const ws = emit_args(fl, ck, tail && !flat);\n  if (!flat) {\n    const vs = sig_def(fl, ck.k).lays.map((lay) =>\n      val_new(ws.splice(0, lay.ks.length), lay));'
    assert patched.count(fuse_anchor) == 1
    patched = patched.replace(fuse_anchor,
        '  const arg_vals: Val[] = [];\n'
        '  const ws = emit_args(fl, ck, tail && !flat, false, arg_vals);\n'
        '  if (!flat) {\n'
        '    let at = 0;\n'
        '    const vs = arg_vals.map((src, i) => {\n'
        '      const lay = sig_def(fl, ck.k).lays[i];\n'
        '      const got = ws.slice(at, at + lay.ks.length);\n'
        '      at += lay.ks.length;\n'
        '      return val_new(got, lay, false, src.fact === undefined\n'
        '        ? undefined : fact_rebind(src.fact, got));\n'
        '    });', 1)
    # Facts are valid while the current body is being emitted. A native helper
    # is cached and shared by multiple callers, so caller-specific facts must
    # stop at that boundary. Passing them into the helper specializes it for
    # whichever call happened to be emitted first and can produce wrong code
    # for the next call.
    native_call_anchor = '  const name = emit_native(fl, ck, ers);'
    assert patched.count(native_call_anchor) == 1
    native_sig_anchor = 'function emit_native(fl: File, ck: Call, ers: HTerm[]): string {'
    assert patched.count(native_sig_anchor) == 1
    # Keep the helper's original signature and formal-value initialization.
    # The local `arg_vals` facts still flow through non-flat inlining above;
    # they are intentionally absent from the cached native specialization.
    val_anchor = 'type Val = { ws: string[]; lay: Lay; stat: boolean };'
    assert patched.count(val_anchor) == 1
    patched = patched.replace(val_anchor,
        'type Fact = { k: Bend.Name; lay: Lay; fields: Val[] };\n'
        'type Val = { ws: string[]; lay: Lay; stat: boolean; fact?: Fact };', 1)
    val_new_anchor = 'function val_new(ws: string[], lay: Lay, stat = false): Val {\n  return { ws, lay, stat };\n}'
    assert patched.count(val_new_anchor) == 1
    patched = patched.replace(val_new_anchor,
        'function val_new(ws: string[], lay: Lay, stat = false,\n'
        '  fact?: Fact): Val {\n'
        '  return { ws, lay, stat, fact };\n}', 1)
    helper_anchor = 'function val_field(v: Val, f: Field): Val {'
    assert patched.count(helper_anchor) == 1
    helper_code = '''function fact_rebind(f: Fact, ws: string[]): Fact | undefined {
  const arm = f.lay.arms?.find((a) => a.k === f.k);
  if (arm === undefined || arm.fs.length !== f.fields.length
      || f.lay.ks.length !== ws.length) return undefined;
  const fields = f.fields.map((src, i) => {
    const field = arm.fs[i];
    if (!lay_eq(src.lay, field.lay)) return undefined;
    const at = field.at;
    const n = field.lay.ks.length;
    const out = val_new(ws.slice(at, at + n), src.lay, src.stat,
      src.fact === undefined ? undefined : fact_rebind(src.fact,
        ws.slice(at, at + n)));
    return out;
  });
  return fields.some((v) => v === undefined)
    ? undefined : { k: f.k, lay: f.lay, fields: fields as Val[] };
}

'''
    patched = patched.replace(helper_anchor, helper_code + helper_anchor, 1)
    field_anchor = 'function val_field(v: Val, f: Field): Val {\n  return val_new(v.ws.slice(f.at, f.at + f.lay.ks.length), f.lay, v.stat);\n}'
    assert patched.count(field_anchor) == 1
    patched = patched.replace(field_anchor,
        'function val_field(v: Val, f: Field): Val {\n'
        '  // A projection changes the representation and pattern position.\n'
        '  // Drop the constructor provenance rather than guessing that a\n'
        '  // layout identity is enough to recover it.\n'
        '  return val_new(v.ws.slice(f.at, f.at + f.lay.ks.length), f.lay, v.stat);\n}', 1)
    hold_anchor = 'function val_hold(fl: File, v: Val, k: string): Val {\n  return val_new(v.ws.map((w, j) => emit_alias(fl, w, k, v.lay.ks[j])),\n    v.lay);\n}'
    assert patched.count(hold_anchor) == 1
    patched = patched.replace(hold_anchor,
        'function val_hold(fl: File, v: Val, k: string): Val {\n'
        '  const ws = v.ws.map((w, j) => emit_alias(fl, w, k, v.lay.ks[j]));\n'
        '  return val_new(ws, v.lay, false, v.fact === undefined ? undefined\n'
        '    : fact_rebind(v.fact, ws));\n}', 1)
    ctr_anchor = '  const stat = vs.every((v) => v.stat);\n'
    assert patched.count(ctr_anchor) == 1
    patched = patched.replace(ctr_anchor,
        '  const stat = vs.every((v) => v.stat);\n'
        '  const fact = { k: x.k, lay, fields: vs };\n', 1)
    node_anchor = '    return val_new([node_build(fl, x.k, vs)], BOX, stat);'
    assert patched.count(node_anchor) == 1
    patched = patched.replace(node_anchor,
        '    return val_new([node_build(fl, x.k, vs)], BOX, stat, fact);', 1)
    final_anchor = '  return val_new(ws, lay, stat);\n}'
    assert patched.count(final_anchor) == 1
    patched = patched.replace(final_anchor,
        '  return val_new(ws, lay, stat, fact);\n}', 1)
    match_anchor = '  const total = Bend.book_adt(fl.book, adt, Bend.Emp()).c.length;\n  const { arms, end } = mat_arms(x);\n'
    assert patched.count(match_anchor) == 1
    match_code = '''  FACT_STATS.matches++;
  const { arms, end } = mat_arms(x);
  const known = args[0].fact;
  if (known !== undefined) FACT_STATS.known++;
  const usable = known !== undefined && !lay_box(args[0].lay)
    && known.fields.every((v) => v.stat && !v.lay.ks.includes("box"));
  if (known !== undefined && !usable) FACT_STATS.rejected++;
  if (usable) {
    const selected = arms.find(([k]) => k === known.k);
    if (selected !== undefined) {
      FACT_STATS.selected++;
      return emit_body(fl, selected[1], null, ers,
        [...known.fields, ...rest], dst);
    }
  }
  FACT_STATS.refused++;
'''
    patched = patched.replace(match_anchor,
        '  const total = Bend.book_adt(fl.book, adt, Bend.Emp()).c.length;\n'
        + match_code, 1)
    stats_anchor = '// Mat\n// ===\n'
    assert patched.count(stats_anchor) == 1
    stats_code = '''// Scoped constructor facts are attached to the actual emitted
// value and consumed only when all fields are static. The generic match remains
// the fallback for dynamic or affine fields.
const FACT_STATS = { matches: 0, known: 0, selected: 0, rejected: 0, refused: 0 };
if (process.env.BEND_FACT_REPORT) {
  process.on("exit", () => fs.writeFileSync(process.env.BEND_FACT_REPORT!,
    JSON.stringify(FACT_STATS) + "\\n"));
}

'''
    patched = patched.replace(stats_anchor, stats_code + stats_anchor, 1)
(out / 'comp.ts').write_text(patched)
candidate_comp_sha = hashlib.sha256(patched.encode()).hexdigest()
(out / 'prepare-static.json').write_text(json.dumps({
    'base_ref': args.base_ref,
    'base_commit': base_commit,
    'base_comp_sha256': source_comp_sha,
    'reapplied_specialization_from': 'b1f9c93684411b16881632a6633f5d0082447449',
    'specialization_source_sha256': hashlib.sha256(
        (HERE / 'static_callback_pass.ts.inc').read_bytes()).hexdigest(),
    'candidate_comp_sha256': candidate_comp_sha,
    'memoized_static_evaluation': True,
    'scoped_constructor_facts': args.facts,
    'structured_callsite_diagnostics': args.diagnostics,
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
print(f'base {args.base_ref} {base_commit}')
print(out / 'main.ts')
