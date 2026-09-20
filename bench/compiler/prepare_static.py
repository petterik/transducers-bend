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
(out / 'comp.ts').write_text(patched)

smoke = out / 'smoke.js'
subprocess.run(['bun', str(out / 'main.ts'), str(ROOT / 'tests/pipeline.bend'),
                '-o', smoke], check=True)
assert smoke.exists()
print(out / 'main.ts')
