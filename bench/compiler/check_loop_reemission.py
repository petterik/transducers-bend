#!/usr/bin/env python3
"""Recheck final compiler output against retained, runtime-tested benchmark/test artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--bend-main',type=Path,required=True)
p.add_argument('--upstream-report',type=Path,required=True)
p.add_argument('--benchmark-reports',type=Path,nargs='+',required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();out=Path(tempfile.mkdtemp(prefix='bend-loop-reemit-')).resolve()
report={'compiler_sha256':hashlib.sha256((a.bend_main.parent/'comp.ts').read_bytes()).hexdigest(),'artifacts':str(out),'checks':[]}
def run(args):
 r=subprocess.run(list(map(str,args)),env={**os.environ,'BEND_NO_TELEMETRY':'1','BUN_JSC_maxPerThreadStackUsage':'33554432'},text=True,capture_output=True,timeout=60)
 assert r.returncode==0,(args,r.stdout,r.stderr)
 return r
for file in a.benchmark_reports:
 r=json.loads(file.read_text());old=Path(r['artifacts'])
 for row in r['results']:
  label=row['case'];dest=out/(label+'.c')
  run(['bun',a.bend_main,old/(label+'-original.bend'),'-o',dest])
  assert dest.read_bytes()==(old/(label+'-automatic.c')).read_bytes(),label
  report['checks'].append({'case':label,'tested_report':str(file),'tested_compiler_sha256':r['automatic_compiler_sha256'],'c_identical':True,'c_sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
r=json.loads(a.upstream_report.read_text());old=Path(r['artifacts']);native=interpreted=0
for row in r['results']:
 source=ROOT.parent/'bend/tests'/row['test']
 if row['result']=='interpreter-only-pass':
  actual=run(['bun',a.bend_main,source]);assert actual.stdout.strip()==row['want'],row['test']
  interpreted+=1
 else:
  assert row['result']=='pass',row
  name=str(Path(row['test']).with_suffix('')).replace('/','-')
  c=out/(name+'.c');js=out/(name+'.js')
  run(['bun',a.bend_main,source,'-o',c,'-o',js])
  for f in [c,js]:assert f.read_bytes()==(old/f.name).read_bytes(),(row['test'],f.suffix)
  native+=1
report['upstream']={'tested_report':str(a.upstream_report),'tested_compiler_sha256':r['compiler_sha256'],'c_and_js_identical':native,'interpreter_rerun_pass':interpreted}
a.output.write_text(json.dumps(report,indent=2)+'\n')
print('PASS',len(report['checks']),'benchmarks,',native,'native/JS re-emissions,',interpreted,'interpreter runs')
