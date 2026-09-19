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
a = p.parse_args()
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
  const optimized = guarded_scalar(fl, ck, ers, name, emitted[1]);
  if (optimized !== null) emitted[1] = optimized;
  Object.assign(fl, outer);
  return name;
}'''
(out/'comp.ts').write_text(original.replace(anchor, integration) + '\n' + (HERE/'guarded_scalar.inc.ts').read_text())
subprocess.run(['bun', str(out/'main.ts'), str(ROOT/'bench/range.bend'), '-o', str(out/'smoke.c')], check=True)
c = (out/'smoke.c').read_text()
assert c.count('/* guarded_scalar:') == 1, 'Unchanged public pipeline did not specialize'
assert '_guarded_fallback(' in c and '== 0);' in c
print(out/'main.ts')
