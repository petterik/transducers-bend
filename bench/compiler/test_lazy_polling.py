#!/usr/bin/env python3
"""Diagnostic handoff checks at 4096-iteration polling boundaries, with forced failures."""
import argparse,json,re,subprocess,tempfile
from pathlib import Path
from short_loop_policy import policies
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--report',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--policy',choices=['lazy','lazy_gate','peel'],required=True)
a=p.parse_args();r=json.loads(a.report.read_text());src=Path(r['artifacts'])
out=Path(tempfile.mkdtemp(prefix='bend-policy-poll-')).resolve()
code=policies((src/'simple-original.c').read_text(),(src/'simple-automatic.c').read_text())[a.policy]
code,n=re.subn(r'#define err_spun\(H, n\)[^\n]*','#define err_spun(H, n) test_poll(n)',code);assert n==1
code,n=re.subn(r'INLINE Term spin_3\([^\n]*\) \{.*?\n\}',r'''INLINE Term spin_3(Env e, THR Term* o, u32 r0, u32 r1) {
  o[0] = ++predicate_calls > trigger_after;
  return 1;
}''',code,count=1,flags=re.S);assert n==1
h=r'''
static unsigned predicate_calls, trigger_after, poll_events, fail_at;
static unsigned long long poll_fingerprint;
static int test_poll(unsigned* n) {
  if((++*n & 4095)!=0)return 0;
  poll_events++;poll_fingerprint=poll_fingerprint*65537+predicate_calls;
  return fail_at && poll_events==fail_at;
}
#define main bend_main
'''+code+r'''
#undef main
int main(void) {
 Env e={0};Term got[5],want[5];
 unsigned triggers[]={0,1,4093,4094,4095,4096,4097,8190,8191,8192,15000};
 for(unsigned t=0;t<11;t++)for(unsigned f=0;f<3;f++) {
  trigger_after=triggers[t];fail_at=f;
  predicate_calls=poll_events=0;poll_fingerprint=0;
  Term ok=spin_10(e,got,10000,0,0,20000,0,0,10000);
  unsigned pc=predicate_calls,pe=poll_events;unsigned long long pf=poll_fingerprint;
  predicate_calls=poll_events=0;poll_fingerprint=0;
  Term ref=spin_10_loop_generic(e,want,10000,0,0,20000,0,0,10000);
  if(ok!=ref||pc!=predicate_calls||pe!=poll_events||pf!=poll_fingerprint) {
   fprintf(stderr,"trigger=%u failure=%u callbacks=%u/%u polls=%u/%u\n",trigger_after,fail_at,pc,predicate_calls,pe,poll_events);return 2;
  }
  if(ok)for(unsigned j=0;j<5;j++)if(got[j]!=want[j])return 3;
 }
 puts("PASS 33 polling-boundary and forced-failure cases");return 0;
}
'''
file=out/'check.c';file.write_text(h);binary=out/'check'
subprocess.run(['clang','-std=c11','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',str(file),'-lpthread','-lm','-o',str(binary)],check=True,capture_output=True)
r=subprocess.run([str(binary)],capture_output=True,text=True);assert r.returncode==0,(r.stdout,r.stderr)
a.output.write_text(json.dumps({'scope':'program-specific policy; controlled predicate and polling-failure injection; not actual asynchronous cancellation or GPU execution','policy':a.policy,'artifacts':str(out),'cases':33,'ubsan':True,'stdout':r.stdout.strip()},indent=2)+'\n');print(r.stdout.strip())
