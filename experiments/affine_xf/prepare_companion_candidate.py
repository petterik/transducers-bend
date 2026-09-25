#!/usr/bin/env python3
"""Build an isolated owner-companion conversion probe atop AUTO inference."""

import argparse
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
INFER = 'function infer_template_autos(book: Book, lhs: LHS, tm: Extract<HTerm, { $: "Ref" }>,\n'
CHECK = 'export function term_check(book: Book, lhs: LHS, tm: HTerm, qt: Quant, ty: HTerm, ctx: Ctx, d: number): Check {\n'
UNIFY = '''    if (!unify(h.A, actual)) {
      throw Err(book, ctx, "~?AUTO solved by a unique structural type match", actual, tm.s, lhs.def);
    }
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    subprocess.run(['python3', str(HERE / 'prepare_infer_candidate.py'),
                    '--output-dir', str(out)], check=True)
    compiler = out / 'bend.ts'
    original = compiler.read_text()
    for anchor in (INFER, CHECK, UNIFY):
        assert original.count(anchor) == 1, anchor
    patched = original.replace(INFER,
        (HERE / 'companion_patch.ts.inc').read_text() + INFER, 1)
    patched = patched.replace(UNIFY, '''    if (!unify(h.A, actual)) {
      const method = companion_method(book, actual, h.A);
      if (method === null) {
        throw Err(book, ctx, "~?AUTO solved by a unique structural type match", actual, tm.s, lhs.def);
      }
      const converted = companion_call(book, method, arg);
      const converted_type = term_infer(book, lhs, converted, Lone(), ctx, d).ty;
      if (!unify(h.A, converted_type)) {
        throw Err(book, ctx, "a companion returning the expected type", converted_type, tm.s, lhs.def);
      }
    }
''', 1)
    patched = patched.replace(CHECK, CHECK + '''  // Reuse the already checked inference result on ordinary inferable forms.
  // Inferring an application twice can instantiate templates twice.
  if (qt.$ === "Lone" && tm.$ === "Ctr") {
    const expected = term_strip(term_wnf(book, ty));
    if (expected.$ === "ADT" && book.tlds[expected.k + ".allow_companion"] !== undefined) {
      const converted = companion_constructor(book, tm, expected,
        expected.x[0] ?? Typ(Qua(Lone())));
      if (converted !== null) {
        return term_check(book, lhs, converted, qt, ty, ctx, d);
      }
    }
  }
  if (qt.$ === "Lone" && (tm.$ === "Var" || tm.$ === "App"
    || tm.$ === "Ann" || tm.$ === "Ref")) {
    const expected = term_strip(term_wnf(book, ty));
    if (expected.$ === "ADT" && book.tlds[expected.k + ".allow_companion"] !== undefined) {
      const inferred = term_infer(book, lhs, tm, qt, ctx, d);
      const method = companion_method(book, inferred.ty, expected);
      if (method !== null) {
        return term_check(book, lhs, companion_call(book, method, tm), qt, ty, ctx, d);
      }
      if (term_compare("LE", book, inferred.ty, ty, d)) {
        return { tm: inferred.tm, us: inferred.us };
      }
      throw Err(book, ctx, ty, inferred.ty, tm.s, lhs.def);
    }
  }
''', 1)
    compiler.write_text(patched)
    print(out / 'main.ts')


if __name__ == '__main__':
    main()
