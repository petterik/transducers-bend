#!/usr/bin/env python3
"""Automatic loop discovery: reordered layouts, shared callers and refusal cases."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--bend-main',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--source-gate',action='store_true',help='Require the inferred source gate on reordered positive fixtures')
a=p.parse_args()
out=Path(tempfile.mkdtemp(prefix='bend-auto-loop-tests-')).resolve()
base=(HERE/'fixtures/reordered.bend').read_text().split('def exercise')[0]
loop='''
def spin(+x: U32, +n: Nat, c: Envelope) -> Envelope:
  match n c:
    case n Finished{memory}:
      Finished{memory}
    case 0n Ready{memory}:
      Ready{memory}
    case 1n+p Ready{memory}:
      spin(x, p, route(x, memory, U32.is_gt(x, 0)))

def exercise(+x: U32) -> Envelope:
  spin(x, 8n, Ready{Memory{Open{4294967295}, 2n, 17}})
def unrelated(+x: U32) -> Envelope:
  route(x, Memory{Closed{13}, 0n, 91}, U32.is_gt(x, 0))
def main() -> List<Envelope>:
  List.append(&1, Envelope, List.map(~U32, ~Envelope, ~(x => exercise(x)), [0, 1, 2]), List.map(~U32, ~Envelope, ~(x => unrelated(x)), [0, 1, 2]))
'''
positive=base+loop
negative=positive.replace('Memory{Open{sum}, 1n+p, cookie}}','Memory{Closed{sum}, 1n+p, cookie}}').replace('Finished{Memory{Open{sum}, 0n, cookie}}','Finished{Memory{Closed{sum}, 0n, cookie}}')
# The same helper is called twice with a mutated state in one iteration. Its
# second guard is not the original entry guard, so the bounded analysis refuses.
double=positive.replace('spin(x, p, route(x, memory, U32.is_gt(x, 0)))', 'spin(x, p, twice(route(x, memory, U32.is_gt(x, 0)), x))')
double=double.replace('def spin(', '''def twice(c: Envelope, +x: U32) -> Envelope:
  match c:
    case Ready{memory}:
      route(x, memory, U32.is_gt(x, 0))
    case Finished{memory}:
      Finished{memory}
def spin(''')
# Unknown scalar work may fail, but must remain in the original order. A checked
# Nat successor lives outside the pure candidate and is never evaluated by guard.
checked=positive.replace('def spin(', 'def read(x: Nat) -> U32:\n  U32.from_nat(1n+x)\ndef spin(').replace('def spin(+x: U32', 'def spin(+x: Nat').replace('route(x, memory, U32.is_gt(x, 0)))', 'route(read(x), memory, U32.is_gt(U32.from_nat(x), 0)))')
checked=checked.replace('spin(x, 8n, Ready', 'spin(U32.to_nat(x), 8n, Ready')
checked=checked[:checked.index('def main()')]+'''def main() -> Envelope:
  spin(Nat.add(Nat.mul(4294967295n, 65536n), 65535n), 8n, Ready{Memory{Open{0}, 2n, 17}})
'''
tiny=positive.replace('spin(x, 8n, Ready', 'spin(x, 1n, Ready')
cases=[('reordered_shared',positive,1),('literal_one',tiny,1),('noninductive',negative,0),('second_step',double,0),('checked_failure',checked,1)]
report={'artifacts':str(out),'compiler_sha256':hashlib.sha256((a.bend_main.parent/'comp.ts').read_bytes()).hexdigest(),'checks':[]}
def run(args,extra=None):
    r=subprocess.run(list(map(str,args)),env={**os.environ,'BEND_NO_TELEMETRY':'1',**(extra or {})},capture_output=True,text=True,timeout=60)
    return r
for label,source,expected in cases:
    src=out/(label+'.bend');src.write_text(source)
    observations=[]
    for mode,compiler in [('original',ROOT.parent/'bend/bend2/main.ts'),('automatic',a.bend_main)]:
        stem=out/(label+'-'+mode)
        log=Path(str(stem)+'.jsonl')
        r=run(['bun',compiler,src,'-o',str(stem)+'.c','-o',str(stem)+'.js'],{'BEND_LOOP_REPORT':str(log)})
        assert r.returncode==0,(label,mode,r.stdout,r.stderr)
        c=Path(str(stem)+'.c').read_text()
        if mode=='automatic':
            assert c.count('/* guarded_loop:')==expected,(label,c.count('/* guarded_loop:'),out)
            assert 'guarded_fallback' not in c
            records=[json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            if a.source_gate and expected:
                assert any(x.get('callee')=='spin' and x.get('sourceGateSlot')==1 for x in records),records
            if label=='noninductive': assert any(x.get('rejected')=='non-inductive guard' for x in records),records
            if label=='second_step': assert any('rejected' in x for x in records),records
            if label=='literal_one': assert any(x.get('trivialCaller') for x in records),records
            old=(out/(label+'-original.c')).read_text()
            helper=re.search(r'INLINE Term spin_\d+\([^\n]*\) \{(?:(?!\n\}).)*?u32 permit_0 = r5;.*?\n\}',old,re.S)
            if label in ['reordered_shared','literal_one']:
                assert helper and helper[0] in c,'Generic shared helper changed'

        r=run(['clang','-std=c11','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',str(stem)+'.c','-lpthread','-lm','-o',stem])
        assert r.returncode==0,r.stderr
        native=run([stem,'--threads','1','--gpu','off'])
        js=run(['bun',str(stem)+'.js'])
        observations.append(((native.returncode,native.stdout,native.stderr),(js.returncode,js.stdout,js.stderr)))
    assert observations[0][0]==observations[1][0],(label,observations)
    # JS generated text must be identical; error stack paths can differ at runtime.
    assert (out/(label+'-original.js')).read_text()==(out/(label+'-automatic.js')).read_text()
    if label=='checked_failure': assert observations[1][0][0]!=0
    else:
        assert observations[1][0][0]==0 and observations[1][1][0]==0
        assert observations[1][0][1]==observations[1][1][1]
    # Select only this pass's device fallback using the CPU runtime. This catches
    # missing conditional declarations/aliases; it is not a GPU execution gate.
    if expected:
        c=(out/(label+'-automatic.c')).read_text()
        host='#if !defined(__METAL_VERSION__) && !defined(__CUDACC__) && !defined(__CUDACC_RTC__)'
        fallback=out/(label+'-device-fallback.c');fallback.write_text(c.replace(host,'#if 0'))
        binary=fallback.with_suffix('')
        r=run(['clang','-std=c11','-O1',fallback,'-lpthread','-lm','-o',binary])
        assert r.returncode==0,r.stderr
        r=run([binary,'--threads','1','--gpu','off'])
        assert (r.returncode,r.stdout,r.stderr)==observations[0][0],(label,r.stdout,r.stderr)
    states=0
    if label in ['reordered_shared','literal_one']:
        name=next(x['name'] for x in records if x.get('callee')=='spin' and 'name' in x)
        c=(out/(label+'-automatic.c')).read_text()
        harness='#define main bend_main\n'+c+'\n#undef main\n'+r"""
int main(void) {
  Env e={0};Term got[5],want[5];u64 seed=11;
  const u64 counts[]={0,1,2,3,281474976710655ull};
  for(u32 i=0;i<200000;i++) {
    seed=seed*6364136223846793005ull+1;
    u32 x=(u32)seed, outer=i&1, inner=(i>>1)&1, sum=(u32)(seed>>16), cookie=(u32)(seed>>32);
    u64 remaining=(i>>2)&15,n=i<1000?counts[(i/4)%5]:seed&281474976710655ull;
    if(i<1000) {x=i&8?0:4294967295u;sum=i&16?0:4294967295u;}
    if(!DRIVER(e,got,x,remaining,outer,inner,sum,n,cookie)
      ||!DRIVER_loop_generic(e,want,x,remaining,outer,inner,sum,n,cookie)) return 2;
    for(u32 j=0;j<5;j++)if(got[j]!=want[j])return 3;
  }
  puts("PASS 200000 reordered driver states");return 0;
}
""".replace('DRIVER',name)
        hp=out/(label+'-states.c');hp.write_text(harness)
        binary=hp.with_suffix('')
        r=run(['clang','-std=c11','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',hp,'-lpthread','-lm','-o',binary])
        assert r.returncode==0,r.stderr
        r=run([binary]);assert r.returncode==0,(r.stdout,r.stderr)
        states=200000
    report['checks'].append({'case':label,'optimized_loops':expected,'native_matches_baseline':True,'js_identical':True,'ubsan':True,'native_status':observations[1][0][0],'proof_records':records,'full_driver_states':states,'device_branch_checked_on_cpu':bool(expected)})
    print('PASS',label,flush=True)
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(out)
