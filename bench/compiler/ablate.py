#!/usr/bin/env python3
"""Compare C ablations or an isolated automatic compiler against original/direct controls."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--samples', type=int, default=5)
p.add_argument('--output', type=Path)
p.add_argument('--early', action='store_true', help='Take 32 with varying source offsets')
p.add_argument('--variants', nargs='+', help='Candidate names; original and direct always included')
p.add_argument('--automatic-compiler', type=Path,
               help='Compile the unchanged pipeline with an isolated automatic pass instead of C replacement')
p.add_argument('--loop-version', action='store_true', help='Program-specific loop-entry versioning diagnostic; requires automatic compiler')
p.add_argument('--linkage-ablation', action='store_true', help='With automatic compiler, compare noinline-only/inline fallback declarations in generated C')
a = p.parse_args()
assert a.samples > 0
assert not a.loop_version or a.automatic_compiler, '--loop-version requires --automatic-compiler'
assert not a.linkage_ablation or a.automatic_compiler, '--linkage-ablation requires --automatic-compiler'
out = Path(tempfile.mkdtemp(prefix='bend-ablation-')).resolve()
print(out, flush=True)
compiler = ROOT.parent / 'bend/bend2/main.ts'
env = {**os.environ, 'BEND_NO_TELEMETRY': '1'}
def command(args):
    r = subprocess.run(args, env=env, text=True, capture_output=True, timeout=90)
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout
source = (ROOT / 'bench/range.bend').read_text().split('def main()')[0]
source = source.replace('import ../transduce.bend as T', 'import ./' + os.path.relpath(ROOT / 'transduce.bend', out) + ' as T')
report = {'artifacts': str(out), 'compiler_sha256': hashlib.sha256((compiler.parent/'comp.ts').read_bytes()).hexdigest(),
          'clang': command(['clang', '--version']).splitlines()[0],
          'scope': 'Program-specific C replacement of filter/take/sum helper; source, mapping, predicate and driver unchanged; runtime threshold; sequential CPU',
          'timing': 'IO.now milliseconds; one warmup per process; two reversed-order rounds',
          'early': a.early, 'library_sha256': hashlib.sha256((ROOT/'transduce.bend').read_bytes()).hexdigest(),
          'results': []}
if a.automatic_compiler:
    report['scope'] = 'Automatic typed scalar specialization of unchanged public pipeline; original/direct controls'
    report['automatic_compiler_sha256'] = hashlib.sha256((a.automatic_compiler.parent/'comp.ts').read_bytes()).hexdigest()
    report['linkage_ablation'] = a.linkage_ablation
    report['program_specific_loop_version'] = a.loop_version
    if a.loop_version:
        report['scope'] += '; loop_version and loop_bailout are program-specific caller-cloning diagnostics, not automatic compiler passes'
for mixed in [True, False]:
    label = ('mixed' if mixed else 'simple') + ('_early' if a.early else '')
    take, repeats = (32, 1000000) if a.early else (2000000, 32)
    threshold = 2147483647 if mixed else 1
    base = source.replace('  U32.is_gt(x, t)', '  U32.is_gt(work(3n, x), t)') if mixed else source
    def program(body):
        return base + f'''
def repeat(+n: Nat, acc: U32, +threshold: U32) -> U32:
  match n:
    case 0n:
      acc
    case 1n+p:
      +offset = {{ {'U32.and(U32.from_nat(p), 65535)' if a.early else '0'} : U32 }}
      repeat(p, (acc + {body} : U32), threshold)
def measure(n: Nat, +threshold: U32) -> IO(Unit):
  match n:
    case 0n:
      IO.pure(Unit, Unit{{}})
    case 1n+p:
      do IO<Unit>:
        before : Nat <- IO.now()
        answer : U32 = repeat!({repeats}n, 0, threshold)
        after : Nat <- IO.now()
        IO.print(U32.show(answer) ++ ":" ++ Nat.show(Nat.sub(after, before)))
        measure(p, threshold)
def parsed(v: Maybe<&2, U32>) -> U32:
  match v:
    case None{{}}:
      0
    case Some{{n}}:
      n
def argument(xs: List<String>) -> U32:
  match xs:
    case Nil{{}}:
      0
    case h <> t:
      parsed(U32.read(h))
def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    measure({a.samples+1}n, argument(args))
'''
    codes = {}
    for name, body in {
        'original': f'T.transduce(~T.over_range(~U32, ~pipeline()), (threshold, ({take}n, 0)), T.range_between(offset, 2000000))',
        'direct': f'direct(U32.to_nat((2000000 - offset : U32)), offset, Running{{{take}n, 0}}, threshold)',
    }.items():
        stem = out / f'{label}-{name}'
        stem.with_suffix('.bend').write_text(program(body))
        command(['bun', str(compiler), str(stem.with_suffix('.bend')), '-o', str(stem.with_suffix('.c'))])
        codes[name] = stem.with_suffix('.c').read_text()
    c = codes['original']
    # Exact, workload-specific scalar signature and field bindings. Refuse drift.
    matches = list(re.finditer(r'INLINE Term (spin_\d+)\(Env e, THR Term\* o, u32 r0, u32 r1, Term r2, u32 r3, u32 r4, u32 r5\) \{.*?\n\}', c, re.S))
    matches = [m for m in matches if 'u32 keep_0 = r0;' in m[0] and 'Term inner_0 = r2;' in m[0]]
    assert len(matches) == 1
    match = matches[0]
    name = match[1]
    header = match[0].split('{', 1)[0] + '{\n'
    prefix = '  u32 keep = r0, tag = r3, sum = r4, x = r5;\n  Term n = r2;\n  o[1] = r1; o[3] = tag;\n'
    suffix = '\n  return 1;\n}'
    special = '  if (n == 0 || tag != 0) { o[0] = keep; o[2] = n; o[4] = sum; return 1; }\n'
    bodies = {
        'flat_branch': '  if (!keep) { o[0]=0; o[2]=n; o[4]=sum; } else {\n    if (n != 0 && tag == 0) { n--; sum = (u32)(sum+x); }\n    o[0]=(n==0 || tag!=0); o[2]=n; o[4]=sum; }',
        'select_all': '  u32 accepted = keep && n != 0 && tag == 0;\n  o[0] = keep && (n <= 1 || tag != 0); o[2] = accepted ? n-1 : n; o[4] = accepted ? (u32)(sum+x) : sum;',
        'guarded_select': special + '  o[0] = keep && n == 1; o[2] = keep ? n-1 : n; o[4] = keep ? (u32)(sum+x) : sum;',
        'guarded_branch': special + '  o[0] = keep && n == 1;\n  if (keep) { o[2]=n-1; o[4]=(u32)(sum+x); } else { o[2]=n; o[4]=sum; }',
        'guarded_nexttag': special + '  n = keep ? n-1 : n; o[0] = n == 0; o[2] = n; o[4] = keep ? (u32)(sum+x) : sum;',
        'guarded_likely': special.replace('n == 0 || tag != 0', '__builtin_expect(n == 0 || tag != 0, 0)') + '  n = keep ? n-1 : n; o[0] = n == 0; o[2] = n; o[4] = keep ? (u32)(sum+x) : sum;',
        'guarded_cold': f'  if (n == 0 || tag != 0) return {name}_slow(e, o, r0, r1, r2, r3, r4, r5);\n' + '  n = keep ? n-1 : n; o[0] = n == 0; o[2] = n; o[4] = keep ? (u32)(sum+x) : sum;',
        'guarded_cold_invariants': f'  if (n == 0 || tag != 0) {{ if (!{name}_slow(e, o, r0, r1, r2, r3, r4, r5)) return 0; o[1]=r1; o[3]=r3; return 1; }}\n' + '  n = keep ? n-1 : n; o[0] = n == 0; o[2] = n; o[4] = keep ? (u32)(sum+x) : sum;',
    }
    if a.variants:
        assert set(a.variants) <= set(bodies), a.variants
        bodies = {k: v for k, v in bodies.items() if k in a.variants}
    if a.automatic_compiler:
        stem = out / f'{label}-automatic'
        command(['bun', str(a.automatic_compiler), str(out/f'{label}-original.bend'), '-o', str(stem.with_suffix('.c'))])
        automatic = stem.with_suffix('.c').read_text()
        assert automatic.count('/* guarded_scalar:') == 1, 'Expected one discovered region in this benchmark'
        assert name+'_guarded_fallback(' in automatic, 'Helper numbering changed; review differential harness'
        untouched = match[0].replace('INLINE Term', 'static __attribute__((noinline, cold)) Term', 1)
        untouched = untouched.replace(name+'(', name+'_guarded_fallback(', 1)
        assert untouched in automatic, 'Fallback must be the original compiler output, apart from its declaration'
        bodies = {'automatic': ''}
        automatic_variants = {'automatic': automatic}
        if a.linkage_ablation:
            for variant_label, decl in [('no_cold', 'static __attribute__((noinline))'), ('inline', 'INLINE')]:
                automatic_variants[variant_label] = automatic.replace('static __attribute__((noinline, cold)) Term', decl+' Term')
                bodies[variant_label] = ''
    for variant, body in bodies.items():
        replacement = header + prefix + body + suffix
        if variant.startswith('guarded_cold'):
            slow = match[0].replace('INLINE Term', 'static __attribute__((noinline, cold)) Term', 1).replace(name+'(', name+'_slow(', 1)
            replacement = slow + '\n' + replacement
        codes[variant] = c[:match.start()] + replacement + c[match.end():]
        # Compare original helper against candidate over all tags and boundary
        # counts, plus seeded random full states; original predicate is outside.
        harness = '#define main bend_main\n' + c[:match.start()] + replacement.replace(name+'(', 'candidate(', 1) + '\n' + c[match.start():] + '\n#undef main\n' + r'''
int main(void) {
  Env e = {0}; Term original[5], changed[5];
  u64 seed = 1, counts[] = {0, 1, 2, 3, 281474976710655ull};
  for (u32 i=0; i<200000; ++i) {
    seed = seed * 6364136223846793005ull + 1;
    Term n = i < 1000 ? counts[(i/4)%5] : seed & 281474976710655ull;
    u32 keep=i&1, tag=(i>>1)&1, sum=(u32)(seed>>16), x=(u32)seed;
    if (i<1000) { sum=(i&8)?0:4294967295u; x=(i&16)?1:4294967295u; }
    if (!HELPER(e, original, keep, 17, n, tag, sum, x)
      || !candidate(e, changed, keep, 17, n, tag, sum, x)) return 2;
    for (u32 j=0; j<5; ++j) if (original[j] != changed[j]) return 3;
  }
  puts("PASS 200000 full-state comparisons"); return 0;
}
'''.replace('HELPER(', name+'(')
        if a.automatic_compiler:
            codes[variant] = automatic_variants[variant]
            harness = ('#define main bend_main\n' + codes[variant] + '\n#undef main\n'
                       + harness.split('\n#undef main\n', 1)[1]
                         .replace(name+'(e, original', name+'_guarded_fallback(e, original')
                         .replace('candidate(e, changed', name+'(e, changed'))
        check = out / f'{label}-{variant}-check'
        check.with_suffix('.c').write_text(harness)
        command(['clang', '-std=c11', '-O3', str(check.with_suffix('.c')), '-lpthread', '-lm', '-o', str(check)])
        assert command([str(check)]).strip() == 'PASS 200000 full-state comparisons'
        if a.automatic_compiler:
            command(['clang', '-std=c11', '-O1', '-fsanitize=undefined', '-fno-sanitize-recover=all',
                     str(check.with_suffix('.c')), '-lpthread', '-lm', '-o', str(check)+'-ubsan'])
            assert command([str(check)+'-ubsan']).strip() == 'PASS 200000 full-state comparisons'
    if a.loop_version:
        from loop_version import version_range
        codes['loop_version'] = version_range(c, automatic)
        codes['loop_bailout'] = version_range(c, automatic, bailout=True)
    expected = 0
    offsets = Counter(i & 65535 for i in range(repeats)) if a.early else {0: repeats}
    for offset, multiplicity in offsets.items():
        total = accepted = 0
        for i in range(offset, 2000000):
            if accepted == take: break
            x = ((i ^ (i >> 13)) + 1) & 0xffffffff
            key = x
            if mixed:
                for _ in range(3): key = ((((key*1664525)&0xffffffff) ^ (key>>13)) + 1013904223) & 0xffffffff
            if key > threshold:
                total = (total+x)&0xffffffff
                accepted += 1
        expected = (expected + total*multiplicity) & 0xffffffff
    row = {'case': label, 'expected': expected, 'samples_ms': {k: [] for k in codes}, 'c_sha256': {}}
    for variant, code in codes.items():
        stem = out / f'{label}-{variant}'
        stem.with_suffix('.c').write_text(code)
        row['c_sha256'][variant] = hashlib.sha256(code.encode()).hexdigest()
        command(['clang', '-std=c11', '-O3', str(stem.with_suffix('.c')), '-lpthread', '-lm', '-o', str(stem)])
        command(['clang', '-std=c11', '-O3', '-S', str(stem.with_suffix('.c')), '-o', str(stem.with_suffix('.s'))])
    for order in [list(codes), list(reversed(codes))]:
        for variant in order:
            lines = command([str(out/f'{label}-{variant}'), '--threads', '1', '--gpu', 'off', '--', str(threshold)]).splitlines()
            values = [list(map(int, line.split(':'))) for line in lines]
            assert len(values) == a.samples+1 and all(v == expected for v, ms in values), (variant, values)
            row['samples_ms'][variant].extend(ms for v, ms in values[1:])
    row['median_ms'] = {k: statistics.median(v) for k,v in row['samples_ms'].items()}
    report['results'].append(row)
    print(label, row['median_ms'], flush=True)
    (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    if a.output: a.output.write_text(json.dumps(report, indent=2)+'\n')
