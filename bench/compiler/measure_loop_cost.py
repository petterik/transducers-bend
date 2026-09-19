#!/usr/bin/env python3
"""Measure isolated compiler launch+emission cost and generated/native file sizes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
import time
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--bend-main',type=Path,required=True)
p.add_argument('--report',type=Path,required=True,help='Full-range ablate.py report with retained source')
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();out=Path(tempfile.mkdtemp(prefix='bend-loop-cost-')).resolve()
r=json.loads(a.report.read_text());sources=Path(r['artifacts'])
compilers={'original':ROOT.parent/'bend/bend2/main.ts','automatic':a.bend_main}
report={'artifacts':str(out),'compiler_sha256':hashlib.sha256((a.bend_main.parent/'comp.ts').read_bytes()).hexdigest(),
 'scope':'local Bun launch plus C emission; one warmup then eight alternating-order samples; emitted C and complete native file size, not hot-code size','results':[]}
def run(args):
 r=subprocess.run(list(map(str,args)),env={**os.environ,'BEND_NO_TELEMETRY':'1'},text=True,capture_output=True,timeout=60)
 assert r.returncode==0,(args,r.stdout,r.stderr)
 return r.stdout
for label in ['mixed','simple']:
 row={'case':label,'samples_ms':{k:[] for k in compilers},'c_bytes':{},'native_file_bytes':{}}
 for iteration in range(9):
  for key in (list(compilers) if iteration%2 else list(reversed(compilers))):
   c=out/(label+'-'+key+'.c');start=time.perf_counter()
   run(['bun',compilers[key],sources/(label+'-original.bend'),'-o',c])
   if iteration:row['samples_ms'][key].append((time.perf_counter()-start)*1000)
 for key in compilers:
  c=out/(label+'-'+key+'.c');binary=c.with_suffix('')
  row['c_bytes'][key]=c.stat().st_size
  run(['clang','-std=c11','-O3',c,'-lpthread','-lm','-o',binary])
  row['native_file_bytes'][key]=binary.stat().st_size
 row['median_ms']={k:statistics.median(v) for k,v in row['samples_ms'].items()}
 report['results'].append(row)
 print(label,row['median_ms'],row['c_bytes'],row['native_file_bytes'],flush=True)
a.output.write_text(json.dumps(report,indent=2)+'\n')
