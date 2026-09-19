#!/usr/bin/env python3
"""Mutate scalar transitions and compare complete states to the original compiler."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--bend-main',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
out=Path(tempfile.mkdtemp(prefix='bend-adversarial-')).resolve()
print(out,flush=True)
env={**os.environ,'BEND_NO_TELEMETRY':'1'}
def run(args):
    r=subprocess.run(list(map(str,args)),env=env,text=True,capture_output=True,timeout=60)
    assert not r.returncode,(args,r.stdout,r.stderr)
    return r.stdout
base=(HERE/'fixtures/reordered.bend').read_text()
closed='Finished{Memory{Closed{sum}, n, cookie}}'
zero='Finished{Memory{Open{sum}, 0n, cookie}}'
variants={
    'original':base,
    'closed_changes_cookie':base.replace(closed,'Finished{Memory{Closed{sum}, n, (cookie + 1 : U32)}}'),
    'zero_changes_cookie':base.replace(zero,'Finished{Memory{Open{sum}, 0n, (cookie + 1 : U32)}}'),
    'closed_changes_sum':base.replace(closed,'Finished{Memory{Closed{(sum + x : U32)}, n, cookie}}'),
    'closed_changes_count':base.replace(closed,'Finished{Memory{Closed{sum}, 0n, cookie}}'),
    'accepted_changes_inner_tag':base.replace('def advance', 'def advance',1).replace('Memory{Open{sum}, 1n+p, cookie}}','Memory{Closed{sum}, 1n+p, cookie}}').replace(zero,'Finished{Memory{Closed{sum}, 0n, cookie}}'),
    'sum_twice':base.replace('Open{sum}, 1n+p, cookie}:','Open{+sum}, 1n+p, cookie}:').replace('(sum + x : U32)','(sum + (sum + x : U32) : U32)'),
    'wrapping_constant':base.replace('(sum + x : U32)','((sum + x : U32) + 4294967295 : U32)'),
    'constant_sum':base.replace('(sum + x : U32)','4294967295'),
    'reverse_outer_tags':base.replace('  Ready{memory: Memory}\n  Finished{memory: Memory}','  Finished{memory: Memory}\n  Ready{memory: Memory}'),
    'no_decrement':base.replace('package(p,','package(1n+p,'),
}
# Change fields on the rejected path; any summary must include that path too.
helper='''def rejected(memory: Memory) -> Envelope:
  match memory:
    case Memory{cell, n, cookie}:
      Ready{Memory{cell, n, (cookie + 1 : U32)}}

'''
variants['rejected_changes_cookie']=base.replace('def route',helper+'def route').replace('      Ready{memory}','      rejected(memory)')
# Independent fallback-only changes combined with different accepted arithmetic.
for i,(label,source) in enumerate(list(variants.items())[1:5]):
    variants[label+'_extra_add']=source.replace('(sum + x : U32)','((sum + x : U32) + 17 : U32)')
report={'artifacts':str(out),'compiler_sha256':hashlib.sha256((a.bend_main.parent/'comp.ts').read_bytes()).hexdigest(),'results':[]}
for label,source in variants.items():
    stem=out/label
    stem.with_suffix('.bend').write_text(source)
    codes={}
    for mode,compiler in [('original',ROOT.parent/'bend/bend2/main.ts'),('automatic',a.bend_main)]:
        c=out/(label+'-'+mode+'.c')
        run(['bun',compiler,stem.with_suffix('.bend'),'-o',c])
        codes[mode]=c.read_text()
    original=codes['original']; auto=codes['automatic']
    root=re.search(r'INLINE Term (spin_\d+)\([^\n]*\) \{(?:(?!\n\}).)*?u32 permit_0 = r5;.*?\n\}',original,re.S)
    assert root,label
    name=root[1]
    regions=auto.count('/* guarded_scalar:')
    assert regions<=1,(label,regions)
    if regions:
        region=re.search(r'#if !defined\(__METAL_VERSION__\).*?/\* guarded_scalar:.*?\n#endif',auto,re.S)
        assert region
        assert original.replace(root[0],'REGION')==auto.replace(region[0],'REGION'),label
    else:
        assert original==auto,label
    reference=root[0].replace(name+'(','reference_route(',1)
    insertion=region.start() if regions else auto.index(root[0])
    auto=auto[:insertion]+reference+'\n'+auto[insertion:]
    harness='#define main bend_main\n'+auto+'\n#undef main\n'+r'''
int main(void) {
  Env e={0}; Term got[5], want[5];
  u64 seed=7, counts[]={0,1,2,3,281474976710655ull};
  for (u32 i=0;i<200000;i++) {
    seed=seed*6364136223846793005ull+1;
    u32 tag=(i>>1)&1, permit=i&1, x=(u32)seed, sum=(u32)(seed>>16), cookie=(u32)(seed>>32);
    Term n=i<1000?counts[(i/4)%5]:seed&281474976710655ull;
    if(i<1000) {sum=(i&8)?0:4294967295u; x=(i&16)?1:4294967295u; cookie=(i&32)?0:4294967295u;}
    if(!HELPER(e,got,x,tag,sum,n,cookie,permit) || !reference_route(e,want,x,tag,sum,n,cookie,permit)) return 2;
    for(u32 j=0;j<5;j++) if(got[j]!=want[j]) {
      fprintf(stderr,"mismatch i=%u field=%u n=%llu tag=%u permit=%u got=%llu want=%llu\n",i,j,n,tag,permit,got[j],want[j]);
      return 3;
    }
  }
  puts("PASS 200000"); return 0;
}
'''.replace('HELPER',name)
    check=out/(label+'-check.c');check.write_text(harness)
    run(['clang','-std=c11','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',check,'-lpthread','-lm','-o',stem])
    assert run([stem]).strip()=='PASS 200000'
    report['results'].append({'case':label,'optimized_regions':regions,'states':200000,'ubsan':True})
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',label,'regions',regions,flush=True)
print('PASS',len(variants),'adversarial variants')
