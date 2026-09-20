#!/usr/bin/env python3
"""Build the typed guarded-scalar experiment in an isolated compiler copy."""
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
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output-dir', type=Path)
p.add_argument('--loop', action='store_true', help='Automatic bounded loop-entry specialization; generic helpers remain original')
p.add_argument('--source-gate', action='store_true', help='With --loop, route dynamic zero/one countdowns to the original loop')
a = p.parse_args()
if a.source_gate and not a.loop:
    p.error('--source-gate requires --loop')
original = (SOURCE/'comp.ts').read_text()
assert hashlib.sha256(original.encode()).hexdigest() == EXPECTED, 'Compiler changed; review integration before rebasing'
out = a.output_dir.resolve() if a.output_dir else Path(tempfile.mkdtemp(prefix='bend-guarded-scalar-')).resolve()
out.mkdir(parents=True, exist_ok=True)
assert not any(out.iterdir()), 'Refuse to overwrite an existing directory'
for name in ['main.ts', 'bend.ts', 'base.bend']:
    shutil.copy2(SOURCE/name, out/name)
shutil.copytree(SOURCE/'effs', out/'effs')
anchor = '  Object.assign(fl, outer);\n  return name;\n}'
assert original.count(anchor) == 1
integration = '''  const emitted = fl.spins[fl.spins.length - 1];
  gl_finish(fl, ck, ers, name, emitted);
  Object.assign(fl, outer);
  return name;
}'''
key_anchor = '''  const key = [ck.k, ...ers.map((e) => JSON.stringify(lay_of(fl.book, e)))]
    .join("|");'''
assert original.count(key_anchor) == 1
patched = original.replace(anchor, integration).replace(key_anchor, '  const key = gl_native_key(fl, ck, ers);')
assert patched.count('function emit_native(') == 1
patched = patched.replace('function emit_native(', 'function emit_native_core(', 1)
call_anchor = '  const name = emit_native(fl, ck, ers);'
assert patched.count(call_anchor) == 1
patched = patched.replace(call_anchor, '  const name = gl_call_name(fl, emit_native(fl, ck, ers), ck);')
match_anchor = "  const spares = fl.spares;\n  const arms2 = lv.map(([, h, fs]) => () => {"
assert patched.count(match_anchor) == 1
patched = patched.replace(match_anchor, "  gl_tree_match_rewrite(fl, x, lay, args, lv);\n  const spares = fl.spares;\n  const arms2 = lv.map(([, h, fs]) => () => {")
flat_anchor = '  const flat = flat_of(ck.k);'
assert patched.count(flat_anchor) == 1
call_flat_anchor = '  return ck !== null && ck.bang !== true && flat_of(ck.k);'
assert patched.count(call_flat_anchor) == 1

# Tree drivers deliberately remain non-flat.  Their recursive source is
# lowered to the ordinary work-loop FID; the guarded pass re-emits that FID
# with the proven callback chain below.  Treating the driver as flat here
# would route it through a recursive native helper instead.
compile_anchor = '''  fl.segs.push(fl.seg);
  emit_body(fl, tld.h as HTerm, tld.T, [], vals, null);'''
assert patched.count(compile_anchor) == 1
patched = patched.replace(compile_anchor, '''  fl.segs.push(fl.seg);
  gl_compile_def(fl, k, tld, vals);''')
loop_code = (HERE/'guarded_loop.inc.ts').read_text()
if a.loop:
    loop_code = loop_code.replace('const GL_ENABLE_LOOP = false;', 'const GL_ENABLE_LOOP = true;')
if a.source_gate:
    loop_code = loop_code.replace('const GL_SOURCE_GATE = false;', 'const GL_SOURCE_GATE = true;')
(out/'comp.ts').write_text(patched + '\n' + (HERE/'guarded_scalar.inc.ts').read_text() + '\n' + loop_code)
subprocess.run(['bun', str(out/'main.ts'), str(ROOT/'bench/range.bend'), '-o', str(out/'smoke.c')], check=True)
c = (out/'smoke.c').read_text()
if a.loop:
    assert c.count('/* guarded_loop:') == 1, 'Unchanged public pipeline did not specialize'
    assert '_guarded_fallback(' not in c
else:
    assert c.count('/* guarded_scalar:') == 1, 'Unchanged public pipeline did not specialize'
    assert '_guarded_fallback(' in c and '== 0);' in c
print(out/'main.ts')
