#!/usr/bin/env python3
"""Build an isolated compiler with memoized static-function resolution.

The sibling Bend checkout is never modified. The generated copy is a small
compiler workset used to test whether repeated static-head evaluation is the
actual cause of the reduced eager-composition blocker.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT.parent / 'bend/bend2'
EXPECTED = '96c997a7d4700a7aaa7bb5a7f27ea810394168cb50fd7f6d267d45156f2e3df3'

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir', type=Path)
parser.add_argument('--facts', action='store_true',
                    help='also enable the scoped constructor-match fact pass')
args = parser.parse_args()

original = (SOURCE / 'comp.ts').read_text()
assert hashlib.sha256(original.encode()).hexdigest() == EXPECTED, (
    'Compiler changed; review integration before rebasing')

out = args.output_dir.resolve() if args.output_dir else Path(
    tempfile.mkdtemp(prefix='bend-static-cache-')).resolve()
out.mkdir(parents=True, exist_ok=True)
assert not any(out.iterdir()), 'Refuse to overwrite an existing directory'
for name in ['main.ts', 'bend.ts', 'base.bend']:
    shutil.copy2(SOURCE / name, out / name)
shutil.copytree(SOURCE / 'effs', out / 'effs')

old = 'function static_fun(book: Book, t: HTerm): HTerm | null {'
assert original.count(old) == 1
patched = original.replace(old,
                           'function static_fun_uncached(book: Book, t: HTerm): HTerm | null {',
                           1)
anchor = '// Keep annotations and bind a dynamic argument once when eliminating a\n'
assert patched.count(anchor) == 1
cache = '''// Static results are immutable within one compilation. Scope the cache
// by Book so a result cannot leak across source/type environments; key by the
// normalized term structure rather than a storage layout or function name.
const STATIC_FUN_CACHE = new WeakMap<object, Map<string, HTerm | null>>();
const STATIC_FUN_STATS = { queries: 0, hits: 0, misses: 0, refusals: 0 };
if (process.env.BEND_STATIC_REPORT) {
  process.on("exit", () => fs.writeFileSync(process.env.BEND_STATIC_REPORT!,
    JSON.stringify(STATIC_FUN_STATS) + "\\n"));
}
function static_fun(book: Book, t: HTerm): HTerm | null {
  STATIC_FUN_STATS.queries++;
  const book_key = book as object;
  // term_key erases source spans but retains the static term structure. The
  // static evaluator still refuses dynamic/unsafe values before returning a
  // result; the Book scope prevents cross-compilation reuse.
  const term_key = Bend.term_key(Bend.term_lower(t));
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
    native_call_anchor = '  const name = emit_native(fl, ck, ers);'
    assert patched.count(native_call_anchor) == 1
    patched = patched.replace(native_call_anchor,
        '  const name = emit_native(fl, ck, ers, arg_vals);', 1)
    native_sig_anchor = 'function emit_native(fl: File, ck: Call, ers: HTerm[]): string {'
    assert patched.count(native_sig_anchor) == 1
    patched = patched.replace(native_sig_anchor,
        'function emit_native(fl: File, ck: Call, ers: HTerm[],\n'
        '  arg_vals?: Val[]): string {', 1)
    native_vals_anchor = '  const vals = emit_open(fl, ck.k);\n  const seg = fl.seg;'
    assert patched.count(native_vals_anchor) == 1
    patched = patched.replace(native_vals_anchor,
        '  const vals = emit_open(fl, ck.k);\n'
        '  arg_vals?.forEach((src, i) => {\n'
        '    if (src.fact !== undefined && vals[i] !== undefined) {\n'
        '      vals[i] = { ...vals[i], fact: fact_rebind(src.fact, vals[i].ws) };\n'
        '    }\n'
        '  });\n'
        '  const seg = fl.seg;', 1)
    val_anchor = 'type Val = { ws: string[]; lay: Lay; stat: boolean };'
    assert patched.count(val_anchor) == 1
    patched = patched.replace(val_anchor,
        'type Fact = { k: Bend.Name; fields: Val[] };\n'
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
  let at = 0;
  const fields = f.fields.map((src) => {
    const n = src.ws.length;
    if (at + n > ws.length) return undefined;
    const out = val_new(ws.slice(at, at + n), src.lay, src.stat,
      src.fact === undefined ? undefined : fact_rebind(src.fact,
        ws.slice(at, at + n)));
    at += n;
    return out;
  });
  return fields.some((v) => v === undefined) || at !== ws.length
    ? undefined : { k: f.k, fields: fields as Val[] };
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
        '  const fact = { k: x.k, fields: vs };\n', 1)
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

smoke = out / 'smoke.js'
subprocess.run(['bun', str(out / 'main.ts'), str(ROOT / 'tests/pipeline.bend'),
                '-o', smoke], check=True)
assert smoke.exists()
print(out / 'main.ts')
