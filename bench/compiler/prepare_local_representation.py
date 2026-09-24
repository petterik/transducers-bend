#!/usr/bin/env python3
"""Prepare the isolated constructor-shape candidate from bendlang/main."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
PREPARE_STATIC = HERE / 'prepare_static.py'
PATCH = HERE / 'checked-shape-fold-prototype.patch'

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir', type=Path, required=True,
                    help='new, empty directory for the isolated candidate')
args = parser.parse_args()

out = args.output_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
assert not any(out.iterdir()), 'Refuse to overwrite an existing directory'
subprocess.run([sys.executable, str(PREPARE_STATIC), '--output-dir', str(out)],
               check=True, timeout=180)
patch_bytes = PATCH.read_bytes()
subprocess.run(['patch', '-p1'], cwd=out, input=patch_bytes, check=True,
               timeout=30)

metadata = json.loads((out / 'prepare-static.json').read_text())
compiler = out / 'comp.ts'
metadata.update({
    'local_representation_patch_sha256': hashlib.sha256(patch_bytes).hexdigest(),
    'candidate_comp_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
    'patch_application': 'checked-shape-fold-prototype.patch applied to the static-callback candidate',
})
(out / 'prepare-local-representation.json').write_text(
    json.dumps(metadata, indent=2) + '\n')
print(json.dumps(metadata, indent=2))
