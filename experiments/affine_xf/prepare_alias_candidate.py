#!/usr/bin/env python3
"""Build an isolated static-callback compiler with the local-alias probe.

This is an experiment, not a proposed production compiler patch. It only
specializes inert, statically closed local aliases used in explicit ~ calls.
"""

import argparse
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ANCHOR = '  const xs = sp.slice(0, def.x);\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    subprocess.run(['python3', str(ROOT / 'bench/compiler/prepare_static.py'),
                    '--output-dir', str(out)], check=True)
    compiler = out / 'bend.ts'
    original = compiler.read_text()
    assert original.count(ANCHOR) == 1, 'review the template-instance anchor'
    compiler.write_text(original.replace(
        ANCHOR, (HERE / 'alias_patch.ts.inc').read_text(), 1))
    print(out / 'main.ts')


if __name__ == '__main__':
    main()
