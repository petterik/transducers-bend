#!/usr/bin/env python3
"""Build an isolated compiler experiment; never modify the sibling checkout."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
source = ROOT.parent / 'bend/bend2'
expected = '96c997a7d4700a7aaa7bb5a7f27ea810394168cb50fd7f6d267d45156f2e3df3'
assert hashlib.sha256((source / 'comp.ts').read_bytes()).hexdigest() == expected, 'Compiler changed; rebase and review the experimental patch first'
out = Path(tempfile.mkdtemp(prefix='bend-scalar-select-')).resolve()
for name in ['main.ts', 'comp.ts', 'bend.ts', 'base.bend']:
    shutil.copy2(source / name, out / name)
shutil.copytree(source / 'effs', out / 'effs')
shutil.copy2(HERE / 'scalar_select.ts', out / 'scalar_select.ts')
subprocess.run(['patch', '-p1', '-i', str(HERE / 'scalar-select.patch')], cwd=out, check=True)
subprocess.run(['bun', str(HERE / 'scalar_select.test.ts')], check=True)
subprocess.run(['bun', str(out / 'main.ts'), str(ROOT / 'tests/scalar_codegen.bend'),
                '-o', str(out / 'smoke.c')], check=True)
assert '/* scalar_select: total unboxed Boolean arms */' in (out / 'smoke.c').read_text(), 'Optimization did not fire'
print(out / 'main.ts')
