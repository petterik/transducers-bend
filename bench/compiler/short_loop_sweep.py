#!/usr/bin/env python3
"""Paired short-loop policy diagnostics with varied lengths, states and selectivity."""
import argparse,json,statistics,subprocess,tempfile
from functools import lru_cache
from pathlib import Path
from short_loop_policy import policies
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--report',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--samples',type=int,default=5)
p.add_argument('--variants',nargs='+')
p.add_argument('--known-budget',type=int,choices=[1,32],help='Make active entry state a C compile-time constant while keeping lengths dynamic')
p.add_argument('--independent',action='store_true',help='Use disjoint seed bits for source length, budget, exceptional state and source offset')
p.add_argument('--stable',action='store_true',help='Longer short-case batches; normalize milliseconds to 2^20 reductions')
p.add_argument('--automatic-report',type=Path,help='Also compare an actual compiler-emitted policy to the diagnostic')
p.add_argument('--full',action='store_true',help='Include varying lengths and budgets, all-pass and mixed filters')
a=p.parse_args();r=json.loads(a.report.read_text());src=Path(r['artifacts'])
out=Path(tempfile.mkdtemp(prefix='bend-short-policy-')).resolve();print(out,flush=True)
codes=policies((src/'simple-original.c').read_text(),(src/'simple-automatic.c').read_text())
actual=None
if a.automatic_report:
 actual=json.loads(a.automatic_report.read_text())
 codes['automatic_gate']=(Path(actual['artifacts'])/'simple-automatic.c').read_text()
 assert codes['automatic_gate']==codes['source_gate'],'Automatic source gate differs from the screened policy; inspect before timing'
if a.variants:codes={k:v for k,v in codes.items() if k in a.variants}
def run(args):
 r=subprocess.run(list(map(str,args)),text=True,capture_output=True,timeout=90)
 assert not r.returncode,(args,r.stdout,r.stderr)
 return r.stdout
h=r'''
#include <time.h>
static double ms(void) {struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec*1000.0+t.tv_nsec/1000000.0;}
int main(int argc,char**argv) {
 Env e={0};Term o[5];
 u32 iterations=atoi(argv[6]),independent=atoi(argv[7]);
 u32 mode=atoi(argv[1]),threshold=strtoull(argv[2],0,10),budget=atoi(argv[3]),exception=atoi(argv[4]),samples=atoi(argv[5]);
 for(u32 k=0;k<samples;k++) {
  u32 seed=17,checksum=0;double start=ms();
  for(u32 i=0;i<iterations;i++) {
   seed=seed*1664525u+1013904223u;u32 low=seed&255;
   u32 lenbits=independent?((seed>>8)&31):low, budgetbits=independent?((seed>>13)&3):((low>>2)&3), exbits=independent?((seed>>15)&3):(low&3);
   Term length=mode<128?mode:mode==128?(lenbits&1):mode==129?(lenbits&3):mode==130?(1u<<(lenbits&3)):mode==131?((lenbits&7)?1:32):(lenbits&31);
   Term n=budget==99?budgetbits:budget;
   u32 inner=exception==2 && exbits==0;
   if(exception==1 && exbits==0)n=0;
   if(!spin_10(e,o,length,0,threshold,n,inner,seed,1024+low))return 2;
   checksum+=(u32)(o[0]+o[1]+o[2]+o[3]+o[4]);
  }
  printf("%u:%.6f\n",checksum,ms()-start);
 }
}
'''
if a.known_budget is not None:
 h=h.replace('Term n=budget==99?budgetbits:budget;',f'Term n={a.known_budget};').replace('u32 inner=exception==2 && exbits==0;','u32 inner=0;').replace('if(exception==1 && exbits==0)n=0;','')
for name,c in codes.items():
 path=out/(name+'.c');path.write_text('#define main bend_main\n'+c+'\n#undef main\n'+h)
 run(['clang','-std=c11','-O3',path,'-lpthread','-lm','-o',out/name])
# Every low byte occurs equally often in a full LCG period. High bits influence
# only the additive initial sum; compute that sum independently once.
def lcg_sum(n):
 # Affine composition of seed and cumulative sum, modulo U32.
 def power(n):
  if not n:return (1,0,0,0)
  A,B,C,D=power(n//2)
  A,B,C,D=(A*A)&0xffffffff,(A*B+B)&0xffffffff,(C*A+C)&0xffffffff,(C*B+2*D)&0xffffffff
  if n&1:A,B,C,D=(1664525*A)&0xffffffff,(1664525*B+1013904223)&0xffffffff,(C+1664525*A)&0xffffffff,(D+1664525*B+1013904223)&0xffffffff
  return A,B,C,D
 A,B,C,D=power(n);return (C*17+D)&0xffffffff
seed=17;total=0
for _ in range(1024):seed=(seed*1664525+1013904223)&0xffffffff;total=(total+seed)&0xffffffff
assert lcg_sum(1024)==total
@lru_cache(maxsize=200000)
def delta(length,threshold,n,inner,low):
 outer=0;added=0
 for x in range(1024+low-length,1024+low):
  mapped=((x^(x>>13))+1)&0xffffffff
  if mapped>threshold:
   if inner or not n:outer=1;break
   n-=1;added=(added+mapped)&0xffffffff
   if not n:outer=1;break
 return outer+threshold+n+inner+added

def oracle(mode,threshold,budget,exception,iterations):
 total=0;period=131072 if a.independent else 256
 for state in range(period):
  low=state&255
  lb=(state>>8)&31 if a.independent else low
  bb=(state>>13)&3 if a.independent else (low>>2)&3
  eb=(state>>15)&3 if a.independent else low&3
  length=mode if mode<128 else lb&1 if mode==128 else lb&3 if mode==129 else 1<<(lb&3) if mode==130 else (1 if lb&7 else 32) if mode==131 else lb&31
  n=bb if budget==99 else budget;inner=int(exception==2 and eb==0)
  if exception==1 and eb==0:n=0
  total+=delta(length,threshold,n,inner,low)
 return (lcg_sum(iterations)+(iterations//period)*total)&0xffffffff
rows=[(length,4294967295,32,exception) for length in [0,1,2,4,8,32] for exception in [0,1,2]]
if a.full:
 rows += [(mode,threshold,budget,ex) for mode in [1,2,32,128,129,130,131,132] for threshold,budget,ex in [(0,32,0),(0,1,0),(1152,32,0),(1152,99,1),(4294967295,32,2)]]
if a.known_budget is not None:
 rows=list(dict.fromkeys((mode,threshold,a.known_budget,0) for mode,threshold,budget,ex in rows))
report={'scope':'program-specific C policy diagnostics; one million driver calls; warmup then paired alternating order; uniform or per-call varying lengths; independent periodic checksum oracle','artifacts':str(out),'source_report':str(a.report),'automatic_report':str(a.automatic_report) if a.automatic_report else None,'automatic_compiler_sha256':actual['automatic_compiler_sha256'] if actual else None,'normalized_to_calls':1048576,'longer_batches':a.stable,'independent_fields':a.independent,'known_budget':a.known_budget,'results':[]}
for mode,threshold,budget,exception in rows:
 iterations=(1<<24 if mode in [0,1,128] else 1<<23 if mode in [2,129] or (threshold==0 and budget==1) else 1<<22 if mode in [4,130,131] or budget==99 else 1<<20) if a.stable else 1<<20
 row={'iterations':iterations,'length_mode':mode,'threshold':threshold,'budget':budget,'exception':exception,'samples_ms':{n:[] for n in codes}}
 want=oracle(mode,threshold,budget,exception,iterations)
 for round in range(2):
  for name in (list(codes) if not round else list(reversed(codes))):
   values=[s.split(':') for s in run([out/name,mode,threshold,budget,exception,a.samples+1,iterations,int(a.independent)]).splitlines()]
   assert all(int(v)==want for v,t in values),(name,row,values,want)
   row['samples_ms'][name].extend(float(t)*1048576/iterations for v,t in values[1:])
 row['checksum']=want;row['median_ms']={n:statistics.median(v) for n,v in row['samples_ms'].items()}
 report['results'].append(row);a.output.write_text(json.dumps(report,indent=2)+'\n')
 print(mode,threshold,budget,exception,row['median_ms'],flush=True)
