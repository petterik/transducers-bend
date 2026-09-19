#!/usr/bin/env python3
"""Measure the unchanged scalar helper across controlled fallback frequencies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import tempfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--bend-main',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--samples',type=int,default=5)
p.add_argument('--linkage-ablation',action='store_true',help='Also test generated-C noinline-only and inline fallback declarations')
a=p.parse_args()
assert a.samples>0
out=Path(tempfile.mkdtemp(prefix='bend-fallback-')).resolve()
print(out,flush=True)
env={**os.environ,'BEND_NO_TELEMETRY':'1'}
def run(args):
    r=subprocess.run(list(map(str,args)),env=env,text=True,capture_output=True,timeout=90)
    assert not r.returncode,(args,r.stdout,r.stderr)
    return r.stdout
bins={}
for mode,compiler in [('original',ROOT.parent/'bend/bend2/main.ts'),('automatic',a.bend_main)]:
    c=out/(mode+'.c')
    run(['bun',compiler,HERE/'fixtures/reordered.bend','-o',c])
    code=c.read_text()
    m=re.search(r'INLINE Term (spin_\d+)\([^\n]*\) \{(?:(?!\n\}).)*?u32 permit_0 = r5;',code,re.S)
    assert m
    h='#define main bend_main\n'+code+'\n#undef main\n'+r'''
#include <time.h>
static double ms(void) {struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec*1000.0+t.tv_nsec/1000000.0;}
int main(int argc, char **argv) {
  Env e={0}; Term o[5];
  u32 frequency=atoi(argv[1]), stopped=atoi(argv[2]), samples=atoi(argv[3]);
  for (u32 sample=0;sample<samples;sample++) {
    u32 seed=17,sum=0,checksum=0;
    double before=ms();
    for (u32 i=0;i<10000000;i++) {
      seed=seed*1664525u+1013904223u;
      u32 exceptional=(seed&255)<frequency;
      Term n=(!stopped && exceptional)?0:32;
      u32 tag=(stopped && exceptional)?0:1;
      if(!HELPER(e,o,seed,tag,sum,n,17,seed>>31)) return 2;
      sum=(u32)o[2];
      checksum += (u32)(o[0]+o[1]+o[2]+o[3]+o[4]);
    }
    printf("%u:%.6f\n",checksum,ms()-before);
  }
}
'''.replace('HELPER',m[1])
    c.write_text(h)
    binary=out/mode
    run(['clang','-std=c11','-O3',c,'-lpthread','-lm','-o',binary])
    bins[mode]=binary
    if mode=='automatic' and a.linkage_ablation:
        for label,decl in [('no_cold','static __attribute__((noinline))'),('inline','INLINE')]:
            variant=out/label
            variant.with_suffix('.c').write_text(h.replace('static __attribute__((noinline, cold)) Term',decl+' Term'))
            run(['clang','-std=c11','-O3',variant.with_suffix('.c'),'-lpthread','-lm','-o',variant])
            bins[label]=variant
report={'scope':'10 million helper calls per batch; independent state inputs; mixed decisions; sequential CPU; fallback frequency uses low 8 bits of LCG',
        'artifacts':str(out),'linkage_ablation':a.linkage_ablation,'compiler_sha256':hashlib.sha256((a.bend_main.parent/'comp.ts').read_bytes()).hexdigest(),'results':[]}
for stopped in [False,True]:
    for frequency in [0,1,64,128,256]:
        row={'state':'stopped' if stopped else 'zero','fallback_fraction':frequency/256,'samples_ms':{k:[] for k in bins}}
        checks=[]
        for order in [list(bins),list(reversed(bins))]:
            for mode in order:
                values=[s.split(':') for s in run([bins[mode],frequency,int(stopped),a.samples+1]).splitlines()]
                checks.extend(int(v) for v,t in values)
                row['samples_ms'][mode].extend(float(t) for v,t in values[1:])
        assert len(set(checks))==1,(row,checks)
        row['checksum']=checks[0]
        row['median_ms']={k:statistics.median(v) for k,v in row['samples_ms'].items()}
        report['results'].append(row)
        a.output.write_text(json.dumps(report,indent=2)+'\n')
        print(row['state'],row['fallback_fraction'],row['median_ms'],flush=True)
