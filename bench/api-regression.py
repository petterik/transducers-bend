"""Compare pre-source-API and current reducers on identical workloads."""
from pathlib import Path
import subprocess, os, tempfile, statistics, json, argparse, hashlib, platform

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--samples', type=int, default=3)
p.add_argument('--bend-main', type=Path, default=root.parent / 'bend/bend2/main.ts')
a = p.parse_args()
if a.samples < 1:
    p.error('samples must be positive')
out = Path(tempfile.mkdtemp(prefix='api-compare-')).resolve()
print(out, flush=True)
compiler = a.bend_main.resolve()
old_revision = subprocess.check_output(['git', 'rev-parse', '357a8f4'], cwd=root, text=True).strip()
old_source = subprocess.check_output(['git', 'show', old_revision + ':transduce.bend'], cwd=root, text=True)
old_lib = out / 'before-api.bend'
old_lib.write_text(old_source + '\n' + "def legacy_range(~R: Type, ~r: Reducer<U32, R>, +n: Nat, c: Control<State(U32, R, r)>, +end: U32) -> R:\n  match n c:\n    case n Stop{s}:\n      finish(U32, R, r, s)\n    case 0n Continue{s}:\n      finish(U32, R, r, s)\n    case 1n+p Continue{s}:\n      legacy_range(~R, ~r, p, step(U32, R, r, s, (end - U32.from_nat(1n+p) : U32)), end)\n\ndef legacy_transduce(~r: Reducer<U32, U32>, config: Config(U32, U32, r), +end: U32) -> U32:\n  legacy_range(~U32, ~r, U32.to_nat(end), start(U32, U32, r, config), end)" + '\n')
env = {**os.environ, 'BEND_NO_TELEMETRY':'1', 'CLANG_MODULE_CACHE_PATH':'/tmp/bend-clang-modules'}
base = (root / 'bench/range.bend').read_text().split('def main()')[0]
base += '''
def build(+n: Nat, xs: List<U32>) -> List<U32>:
  match n:
    case 0n:
      xs
    case 1n+p:
      build(p, U32.from_nat(p) <> xs)

def direct_list(xs: List<U32>, state: Running, +threshold: U32) -> U32:
  match xs state:
    case xs Running{0n, acc}:
      acc
    case Nil{} Running{left, acc}:
      acc
    case h <> t Running{1n+p, acc}:
      direct_list(t, feed(threshold, 1n+p, acc, transform(h)), threshold)
'''
reports=[]
report={'old_revision': old_revision,
        'old_library_sha256': hashlib.sha256(old_source.encode()).hexdigest(),
        'new_library_sha256': hashlib.sha256((root/'transduce.bend').read_bytes()).hexdigest(),
        'compiler_sha256': hashlib.sha256((compiler.parent/'comp.ts').read_bytes()).hexdigest(),
        'platform': platform.platform(),
        'timing': 'IO.now milliseconds; CPU threads=1 GPU off; includes list construction; warmup discarded each process; reverse-order second round',
        'results': reports}
cases=[('list_uniform_cheap','list',262144,16,0,False,True,1),
       ('list_uniform_heavy','list',65536,4,256,False,True,1),
       ('list_mixed','list',200000,32,0,True,False,2147483647),
       ('range_mixed','range',2000000,32,0,True,False,2147483647)]
for label,kind,end,repeats,work,mixed,uniform,threshold in cases:
    src=base
    if uniform:
        src=src.replace('U32.from_nat(p) <> xs', '1 <> xs')
        src=src.replace('  cheap(x)\n', '  (x + 1 : U32)\n')
    if work:
        src=src.replace('  (x + 1 : U32)\n', f'  work({work}n, x)\n')
    if mixed:
        src=src.replace('  U32.is_gt(x, t)', '  U32.is_gt(work(3n, x), t)')
    expected=0
    for i in range(end):
        x=1 if uniform else i
        if work:
            for _ in range(work):
                x=((((x*1664525)&0xffffffff)^(x>>13))+1013904223)&0xffffffff
        else:
            x=x+1 if uniform else ((x^(x>>13))+1)&0xffffffff
        key=x
        if mixed:
            for _ in range(3):
                key=((((key*1664525)&0xffffffff)^(key>>13))+1013904223)&0xffffffff
        if key>threshold: expected=(expected+x)&0xffffffff
    expected=expected*repeats&0xffffffff
    config=f'(threshold, ({end}n, 0))'
    if kind=='list':
        bodies={'old':f'T.transduce(~U32, ~U32, ~pipeline(), {config}, build({end}n, []))',
                'new':f'T.transduce(~T.over_list(~U32, ~U32, ~pipeline()), {config}, build({end}n, []))',
                'direct':f'direct_list(build({end}n, []), Running{{{end}n, 0}}, threshold)'}
    else:
        bodies={'old_style':f'T.legacy_transduce(~pipeline(), {config}, {end})',
                'new':f'T.transduce(~T.over_range(~U32, ~pipeline()), {config}, T.range({end}))',
                'direct':f'direct({end}n, 0, Running{{{end}n, 0}}, threshold)'}
    row={'case':label,'count':end,'repeats':repeats,'threshold':threshold,'work_rounds':work,'mixed_predicate':mixed,'uniform_ones':uniform,'expected':expected,'samples_ms':{name:[] for name in bodies}}
    for name,body in bodies.items():
        lib=old_lib if name.startswith('old') else root/'transduce.bend'
        program=src.replace('import ../transduce.bend as T', 'import ./'+os.path.relpath(lib,out)+' as T')
        program+=f'''
def repeat(n: Nat, acc: U32, +threshold: U32) -> U32:
  match n:
    case 0n:
      acc
    case 1n+p:
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
        stem=out/(label+'-'+name)
        stem.with_suffix('.bend').write_text(program)
        result=subprocess.run(['bun',str(compiler),str(stem.with_suffix('.bend')),'-o',str(stem),'-o',str(stem.with_suffix('.c')),'-o',str(stem.with_suffix('.js'))],env=env,text=True,capture_output=True,timeout=60)
        assert result.returncode==0,result.stdout+result.stderr
        emitted=stem.with_suffix('.js').read_text()
        assert '{$: "Reducer"' not in emitted and '{$: "Reduction"' not in emitted, name
    for names in (list(bodies),list(reversed(bodies))):
        for name in names:
            output=subprocess.check_output([str(out/(label+'-'+name)),'--threads','1','--gpu','off','--',str(threshold)],text=True,timeout=60)
            pairs=[list(map(int,line.split(':'))) for line in output.splitlines()]
            assert len(pairs)==a.samples+1 and all(value==expected for value,ms in pairs),(label,name,output,expected)
            row['samples_ms'][name].extend(ms for value,ms in pairs[1:])
    row['medians_ms']={name:statistics.median(samples) for name,samples in row['samples_ms'].items()}
    reports.append(row)
    print(row,flush=True)
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
