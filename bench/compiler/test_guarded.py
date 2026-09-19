#!/usr/bin/env python3
"""Compiler experiment gates: layout independence, full states, rejected work/failures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--bend-main', type=Path, required=True)
p.add_argument('--output', type=Path)
p.add_argument('--composition-report', type=Path,
               help='Also verify map-chain assembly using retained composition benchmark artifacts')
a = p.parse_args()
out = Path(tempfile.mkdtemp(prefix='bend-guarded-tests-')).resolve()
print(out, flush=True)
env = {**os.environ, 'BEND_NO_TELEMETRY': '1'}
def run(args, success=True):
    r = subprocess.run(list(map(str,args)), env=env, text=True, capture_output=True, timeout=90)
    if success: assert r.returncode == 0, (args,r.stdout,r.stderr)
    return r

def compile_source(source, name, compiler=a.bend_main):
    stem=out/name
    stem.with_suffix('.bend').write_text(source)
    run(['bun',compiler,stem.with_suffix('.bend'),'-o',stem.with_suffix('.c')])
    return stem,stem.with_suffix('.c').read_text()

source=(HERE/'fixtures/reordered.bend').read_text()
report={'artifacts':str(out), 'compiler_sha256':hashlib.sha256((a.bend_main.parent/'comp.ts').read_bytes()).hexdigest(), 'checks':[]}
for label,text,optimized in [('reordered',source,True),
        ('callback',source.replace('(sum + x : U32)','(sum * x : U32)'),False)]:
    stem,c=compile_source(text,label)
    assert ('/* guarded_scalar:' in c) == optimized
    # Identification belongs only to this fixture's test harness, never to the pass.
    match=re.search(r'INLINE Term (spin_\d+)\([^\n]*\) \{(?:(?!\n\}).)*?u32 permit_0 = r5;',c,re.S)
    assert match
    name=match[1]
    if not optimized:
        # The callback contains an unsupported intrinsic. Count its evaluation
        # in generated C to ensure it runs only on accepted, active inputs.
        c,count=re.subn(r'(U32_BIN\(\w+, \*, \w+\))',r'(++callback_calls, \1)',c)
        assert count==1,count
    harness='static unsigned callback_calls;\n#define main bend_main\n'+c+'\n#undef main\n'+r'''
int main(void) {
  Env e={0}; Term got[5], old[5];
  u64 seed=7, counts[]={0,1,2,3,281474976710655ull};
  for (u32 i=0;i<200000;i++) {
    seed=seed*6364136223846793005ull+1;
    u32 tag=(i>>1)&1, permit=i&1, x=(u32)seed, sum=(u32)(seed>>16), cookie=(u32)(seed>>32);
    Term n=i<1000?counts[(i/4)%5]:seed&281474976710655ull;
    if(i<1000) {sum=(i&8)?0:4294967295u; x=(i&16)?1:4294967295u;}
    callback_calls=0;
    if(!HELPER(e,got,x,tag,sum,n,cookie,permit)) return 2;
    u32 active=permit && tag==1 && n!=0;
    Term next=n-active;
    Term want[]={permit && (tag==0 || next==0),tag,active?UPDATE:sum,next,cookie};
    for(u32 j=0;j<5;j++) if(got[j]!=want[j]) return 3;
    CHECK
  }
  puts("PASS 200000 reordered states"); return 0;
}
'''.replace('HELPER',name).replace('UPDATE','(u32)(sum+x)' if optimized else '(u32)(sum*x)')
    if optimized:
        check=f'''if (!{name}_guarded_fallback(e,old,x,tag,sum,n,cookie,permit)) return 4;
    for(u32 j=0;j<5;j++) if(got[j]!=old[j]) return 5;'''
    else:
        check='if(callback_calls != active) return 6;'
    harness=harness.replace('CHECK',check)
    hp=out/(label+'-check.c'); hp.write_text(harness)
    binary=out/(label+'-check')
    run(['clang','-std=c11','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',hp,'-lpthread','-lm','-o',binary])
    assert run([binary]).stdout.strip()=='PASS 200000 reordered states'
    report['checks'].append(label+': 200000 full states + UBSan'+(' + callback counts' if not optimized else ' + original fallback'))
    print('PASS',report['checks'][-1],flush=True)

# A successor on arbitrary Nat state can overflow. The entire region must be
# refused, even though some call sites dynamically reject that branch.
checked=source.replace('value: U32','value: Nat').replace('sum: U32','sum: Nat')
checked=checked.replace('(sum + x : U32)','1n+sum').replace('4294967295','max_nat()')
checked=checked.split('#|')[0].replace('def exercise', '''def max_nat() -> Nat:
  Nat.add(Nat.mul(4294967295n, 65536n), 65535n)

def exercise''')
for accepted in [False,True]:
    text=checked.replace('[0, 1, 2]', '[1]' if accepted else '[0]')
    observations=[]
    for mode,compiler in [('original',ROOT.parent/'bend/bend2/main.ts'),('automatic',a.bend_main)]:
        stem,c=compile_source(text,f'checked-{accepted}-{mode}',compiler)
        assert '/* guarded_scalar:' not in c
        run(['clang','-std=c11','-O3',stem.with_suffix('.c'),'-lpthread','-lm','-o',stem])
        r=run([stem,'--threads','1','--gpu','off'],success=False)
        observations.append((r.returncode,r.stdout,r.stderr))
    assert observations[0]==observations[1],observations
    status,stdout,stderr=observations[0]
    if accepted: assert status!=0 and 'Nat' in stderr,(status,stdout,stderr)
    else: assert status==0 and '281474976710655n' in stdout,(status,stdout,stderr)
    report['checks'].append('checked successor: '+('accepted overflow fails identically' if accepted else 'rejected overflow does not execute'))
    print('PASS',report['checks'][-1],flush=True)
if a.composition_report:
    composition=json.loads(a.composition_report.read_text())
    assert composition['compiler_sha256']==report['compiler_sha256']
    artifacts=Path(composition['artifacts'])
    functions=[]
    for label in ['transducers','single_map','original']:
        c=artifacts/('three_maps-'+label+'.c')
        if label=='original':
            c=out/'map-original.c'
            run(['bun',ROOT.parent/'bend/bend2/main.ts',artifacts/'three_maps-transducers.bend','-o',c])
        assembly=out/('map-'+label+'.s')
        run(['clang','-std=c11','-O3','-S',c,'-o',assembly])
        function=re.search(r'^_?WL_FID_REPEAT:.*?^\s*\.cfi_endproc',assembly.read_text(),re.M|re.S)
        assert function, 'Timed function not found; review assembly for this platform'
        functions.append(function[0])
    assert functions[0]==functions[1]==functions[2], 'Map-chain timed assembly changed'
    report['map_assembly_sha256']=hashlib.sha256(functions[0].encode()).hexdigest()
    report['checks'].append('three maps / single map / original compiler: identical timed-function assembly')
    print('PASS',report['checks'][-1],flush=True)
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
if a.output: a.output.write_text(json.dumps(report,indent=2)+'\n')
print('PASS guarded compiler gates')
