#!/usr/bin/env python3
"""Full driver-state and callback-order checks for the program-specific diagnostic."""
import argparse
import json
from pathlib import Path
import re
import subprocess

from loop_version import version_range
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--report',type=Path,required=True,help='Full-range ablate.py --loop-version report')
p.add_argument('--output',type=Path,required=True)
p.add_argument('--inject-failure',action='store_true',help='Inject callback failure returns and verify propagation/order')
p.add_argument('--automatic-loop',action='store_true',help='Validate actual compiler-emitted loop against its untouched generic copy')
p.add_argument('--bailout',action='store_true')
p.add_argument('--break-induction',action='store_true',help='Perturb both generic and fast transitions so an accepted Continue changes the inner tag')
a=p.parse_args()
assert not a.automatic_loop or (not a.bailout and not a.break_induction)
r=json.loads(a.report.read_text());out=Path(r['artifacts'])
checks=[]
for row in r['results']:
    label=row['case']
    original=(out/(label+'-original.c')).read_text()
    auto=(out/(label+'-automatic.c')).read_text()
    code=auto if a.automatic_loop else version_range(original,auto,bailout=a.bailout)
    if a.break_induction:
        # Both functions retain the same one-step semantics on the fast domain,
        # but may leave it while still returning outer Continue. Entry-only
        # versioning is therefore illegal; per-step bailout must still work.
        for name,old,new in [
            ('spin_4','o[3] = v_11;','o[3] = (v_8 == 0 && keep_0 ? 1 : v_11);'),
            ('spin_4_version_fast','o[3] = g3;','o[3] = (g2 != 0 && r0 ? 1 : g3);')]:
            m=re.search(r'INLINE Term '+name+r'\([^\n]*\) \{.*?\n\}',code,re.S)
            assert m and m[0].count(old)==1
            code=code.replace(m[0],m[0].replace(old,new))
    # Trace function entries before optimization; scalar arithmetic stays intact.
    for name,event,args in [('spin_6',1,'r0, r1'),('spin_7',2,'r0, 0'),('spin_3',3,'r0, r1')]:
        code,n=re.subn(r'(INLINE Term '+name+r'\([^\n]*\) \{)',r'\1\n  event('+str(event)+', '+args+');',code,count=1)
        assert n==1,name
        if a.inject_failure:
            code=code.replace('  event('+str(event)+', '+args+');', '  event('+str(event)+', '+args+');\n  if ((r0 & 7) == '+str(event)+') return 0;', 1)
    h=r'''
static unsigned long long events, fingerprint;
static void event(unsigned k, unsigned long long a, unsigned long long b) {
  events++; fingerprint=(fingerprint*6364136223846793005ull)^(a*17+b*31+k);
}
#define main bend_main
'''+code+r'''
#undef main
int main(void) {
  Env e={0}; Term got[5],want[5];
  u64 seed=7,counts[]={0,1,2,3,281474976710655ull};
  for(u32 i=0;i<200000;i++) {
    seed=seed*6364136223846793005ull+1;
    u32 outer=i&1, inner=(i>>1)&1, threshold=(u32)(seed>>16), sum=(u32)seed;
    Term n=i<1000?counts[(i/4)%5]:seed&281474976710655ull;
    Term remaining=(i>>2)&15;
    u32 end=i&64 ? 4294967295u : 16;
    if(i<1000) {sum=i&8?0:4294967295u;threshold=i&16?0:4294967295u;}
    events=fingerprint=0;
    Term ok=spin_10(e,got,remaining,outer,threshold,n,inner,sum,end);
    u64 actual_events=events, actual_fingerprint=fingerprint;
    events=fingerprint=0;
    Term reference=spin_10_version_generic(e,want,remaining,outer,threshold,n,inner,sum,end);
    if(ok!=reference || actual_events!=events || actual_fingerprint!=fingerprint) {
      fprintf(stderr,"i=%u remaining=%llu outer=%u n=%llu inner=%u threshold=%u events=%llu expected_events=%llu count=%llu expected_count=%llu sum=%llu expected_sum=%llu\n",i,remaining,outer,n,inner,threshold,actual_events,events,got[2],want[2],got[4],want[4]);
      return 2;
    }
    if(ok) for(u32 j=0;j<5;j++) if(got[j]!=want[j]) return 3;
  }
  puts("PASS 200000 driver states and event traces");return 0;
}
'''
    if a.automatic_loop:
        h=h.replace('spin_10_version_generic(', 'spin_10_loop_generic(')
    c=out/(label+('-noninductive' if a.break_induction else '')+('-bailout' if a.bailout else '-entry')+'-loop-check.c'); c.write_text(h)
    binary=c.with_suffix('')
    subprocess.run(['clang','-std=c11','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',str(c),'-lpthread','-lm','-o',str(binary)],check=True,capture_output=True)
    answer=subprocess.run([str(binary)],text=True,capture_output=True)
    if a.break_induction and not a.bailout:
        assert answer.returncode in [2,3],(answer.stdout,answer.stderr)
        checks.append({'case':label,'counterexample_found':True,'status':answer.returncode,'counterexample':answer.stderr.strip()})
    else:
        assert answer.returncode==0 and answer.stdout.strip()=='PASS 200000 driver states and event traces',(answer.stdout,answer.stderr)
        checks.append({'case':label,'driver_states':200000,'event_order_and_count':True,'ubsan':True,'injected_callback_failure':a.inject_failure})
    print('PASS',label,flush=True)
a.output.write_text(json.dumps({'scope':'automatic compiler-emitted loop' if a.automatic_loop else 'program-specific range driver clone; not automatic loop discovery/proof','artifacts':str(out),'bailout':a.bailout,'deliberately_noninductive':a.break_induction,'checks':checks},indent=2)+'\n')
