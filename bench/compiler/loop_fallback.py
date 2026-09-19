#!/usr/bin/env python3
"""Loop-strategy stress test: frequent exceptional entry states and short sources."""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
import tempfile
from loop_version import version_range
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--report',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--automatic-loop',action='store_true',help='Compare actual compiler loop to original')
p.add_argument('--samples',type=int,default=3)
a=p.parse_args()
r=json.loads(a.report.read_text());artifacts=Path(r['artifacts'])
out=Path(tempfile.mkdtemp(prefix='bend-loop-fallback-')).resolve()
print(out,flush=True)
def run(args):
    r=subprocess.run(list(map(str,args)),text=True,capture_output=True,timeout=90)
    assert not r.returncode,(args,r.stdout,r.stderr)
    return r.stdout
original=(artifacts/'simple-original.c').read_text()
auto=(artifacts/'simple-automatic.c').read_text()
codes=({'original':original,'automatic_loop':auto} if a.automatic_loop else
       {'original':original,'outlined_helper':auto,'entry_version':version_range(original,auto),'loop_bailout':version_range(original,auto,bailout=True),'two_steps':version_range(original,auto,min_two=True)})
for name,c in codes.items():
    harness='#define main bend_main\n'+c+'\n#undef main\n'+r'''
#include <time.h>
static double ms(void) {struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec*1000.0+t.tv_nsec/1000000.0;}
int main(int argc,char**argv) {
  Env e={0};Term o[5];
  u32 frequency=atoi(argv[1]),stopped=atoi(argv[2]),length=atoi(argv[3]),samples=atoi(argv[4]);
  u32 threshold=(u32)strtoull(argv[5],0,10);
  for(u32 k=0;k<samples;k++) {
    u32 seed=17,checksum=0;
    double start=ms();
    for(u32 i=0;i<1000000;i++) {
      seed=seed*1664525u+1013904223u;
      u32 exceptional=(seed&255)<frequency;
      Term n=!stopped && exceptional ? 0 : 32;
      u32 inner=stopped && exceptional ? 1 : 0;
      if(!spin_10(e,o,length,0,threshold,n,inner,seed,1024+(seed&65535)))return 2;
      checksum+=(u32)(o[0]+o[1]+o[2]+o[3]+o[4]);
    }
    printf("%u:%.6f\n",checksum,ms()-start);
  }
}
'''
    c=out/(name+'.c');c.write_text(harness)
    run(['clang','-std=c11','-O3',c,'-lpthread','-lm','-o',out/name])
report={'scope':'one million complete range-driver calls per batch; runtime max-U32 threshold rejects all values; valid zero/stopped entry states; sequential CPU',
        'artifacts':str(out),'source_report':str(a.report),'results':[]}
for length in [1,32]:
    for stopped in [False,True]:
        for frequency in [0,64,256]:
            row={'length':length,'state':'stopped' if stopped else 'zero','fraction':frequency/256,'samples_ms':{n:[] for n in codes}}
            checks=[]
            for order in [list(codes),list(reversed(codes))]:
                for name in order:
                    values=[s.split(':') for s in run([out/name,frequency,int(stopped),length,a.samples+1,4294967295]).splitlines()]
                    checks.extend(int(v) for v,t in values)
                    row['samples_ms'][name].extend(float(t) for v,t in values[1:])
            assert len(set(checks))==1,(row,checks)
            # No input passes. The returned count, inner tag and sum are unchanged;
            # the outer tag is Continue even for a zero or stopped inner state.
            seed=17;want=0
            for i in range(1000000):
                seed=(seed*1664525+1013904223)&0xffffffff
                exceptional=(seed&255)<frequency
                n=0 if not stopped and exceptional else 32
                tag=1 if stopped and exceptional else 0
                want=(want+4294967295+n+tag+seed)&0xffffffff
            assert checks[0]==want,(checks[0],want)
            row['checksum']=want
            row['median_ms']={n:statistics.median(v) for n,v in row['samples_ms'].items()}
            report['results'].append(row)
            a.output.write_text(json.dumps(report,indent=2)+'\n')
            print(length,row['state'],row['fraction'],row['median_ms'],flush=True)
