#!/usr/bin/env python3
"""Build an isolated static-callback compiler with ~?AUTO type inference."""

import argparse
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ANCHOR = 'export function def_inst(book: Book, lhs: LHS, tm: Extract<HTerm, { $: "Ref" }>, def: Def, sp: HTerm[], ctx: Ctx, d: number): Name {\n'
XS = '  const xs = sp.slice(0, def.x);\n'
CALL = '      const xs = ts.concat(parse_term_args(p, ")"));\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    subprocess.run(['python3', str(ROOT / 'bench/compiler/prepare_static.py'),
                    '--output-dir', str(out)], check=True)
    compiler = out / 'bend.ts'
    original = compiler.read_text()
    assert original.count(ANCHOR) == 1
    assert original.count(XS) == 1
    assert original.count(CALL) == 1
    patched = original.replace(XS,
        '  const xs = infer_template_autos(book, lhs, tm, def, sp, ctx, d);\n', 1)
    patched = patched.replace(CALL,
        '      // Missing trailing ~ arguments may be inferred from checked\n'
        '      // runtime-argument types; reject ambiguous or open cases.\n'
        '      const autos = ts.length < x\n'
        '        ? Array.from({ length: x - ts.length }, () => Hol("AUTO", out.s))\n'
        '        : [];\n'
        '      const xs = ts.concat(autos, parse_term_args(p, ")"));\n', 1)
    patched = patched.replace(ANCHOR,
        (HERE / 'infer_patch.ts.inc').read_text() + ANCHOR, 1)
    compiler.write_text(patched)
    print(out / 'main.ts')


if __name__ == '__main__':
    main()
