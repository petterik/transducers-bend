#!/usr/bin/env python3
"""Local CPU/JS compatibility checks; not the official distributed upstream gate."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT.parent/'bend'
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--bend-main',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--namespaces',nargs='+',default=['base','compile','flatten','reg','state'])
p.add_argument('--resume',action='store_true',help='Retain completed pass rows with the same compiler hash')
a=p.parse_args()
out=Path(tempfile.mkdtemp(prefix='bend-upstream-local-')).resolve()
env={**os.environ,'BEND_NO_TELEMETRY':'1','BUN_JSC_maxPerThreadStackUsage':'33554432'}
print(out,flush=True)
def run(args,timeout=40):
    try:
        r=subprocess.run(list(map(str,args)),env=env,text=True,capture_output=True,timeout=timeout)
        return {'status':r.returncode,'stdout':r.stdout.strip(),'stderr':r.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {'status':124,'stdout':'','stderr':'local test timeout'}
def check(file):
    relative=file.relative_to(SOURCE/'tests')
    stem=out/str(relative.with_suffix('')).replace('/','-')
    text=file.read_text()
    want='\n'.join(s[2:] for s in text.splitlines() if s.startswith('#|')).strip()
    row={'test':str(relative),'want':want}
    base=run(['bun',SOURCE/'bend2/main.ts',file,'-o',str(stem)+'-original.c'])
    auto=run(['bun',a.bend_main,file,'-o',str(stem)+'.c','-o',str(stem)+'.js'])
    if base['status'] and auto==base and 'cannot be printed' in base['stderr']:
        interp=run(['bun',a.bend_main,file])
        row.update(result='interpreter-only-pass' if interp['status']==0 and interp['stdout']==want else 'interpreter-mismatch',interpreter=interp)
        return row
    if base['status'] or auto['status']:
        row.update(result='baseline-build-failure' if base['status'] and auto==base else 'build-mismatch',original=base,automatic=auto)
        return row
    c=Path(str(stem)+'.c').read_text()
    row['regions']=c.count('/* guarded_scalar:')
    row['loops']=c.count('/* guarded_loop:')
    row['c_identical']=c==Path(str(stem)+'-original.c').read_text()
    build=run(['clang','-std=c11','-O3',str(stem)+'.c','-lpthread','-lm','-o',stem])
    if build['status']:
        if row['c_identical'] and 'bracket nesting level exceeded' in build['stderr']:
            row['native_extra_flag']='-fbracket-depth=4096'
            build=run(['clang','-std=c11','-O3','-fbracket-depth=4096',str(stem)+'.c','-lpthread','-lm','-o',stem])
        if build['status']:
            row.update(result='native-build-failure',build=build)
            return row
    native=run([stem,'--threads','1','--gpu','off'],10)
    js=run(['bun',str(stem)+'.js'],10)
    row['result']='pass' if all(r['status']==0 and r['stdout']==want for r in [native,js]) else 'output-mismatch'
    if row['result']!='pass':
        # Distinguish pre-existing failures using exactly the same local lane.
        basebuild=run(['clang','-std=c11','-O3',str(stem)+'-original.c','-lpthread','-lm','-o',str(stem)+'-original'])
        original=run([str(stem)+'-original','--threads','1','--gpu','off'],10) if not basebuild['status'] else basebuild
        run(['bun',SOURCE/'bend2/main.ts',file,'-o',str(stem)+'-original.js'])
        originaljs=run(['bun',str(stem)+'-original.js'],10)
        row.update(native=native,js=js,original_native=original,original_js=originaljs)
        if native==original and js==originaljs: row['result']='baseline-output-mismatch'
    return row
files=[]
for ns in a.namespaces:
    for f in sorted((SOURCE/'tests'/ns).glob('*.bend')):
        s=f.read_text()
        if re.search(r'^import Base$',s,re.M) and re.search(r'^def main\(',s,re.M) and '#|Error:' not in s:
            files.append(f)
report={'scope':'local native CPU and JS; runnable positive tests in selected namespaces; not cluster/GPU gate',
        'artifacts':str(out),'namespaces':a.namespaces,
        'compiler_sha256':hashlib.sha256((a.bend_main.parent/'comp.ts').read_bytes()).hexdigest(),'results':[]}
previous=json.loads(a.output.read_text()) if a.resume and a.output.exists() else None
if previous:
    assert previous['compiler_sha256']==report['compiler_sha256']
    report['previous_artifacts']=previous['artifacts']
    keep={r['test']:r for r in previous['results'] if r['result']=='pass'}
    report['results'].extend(keep.values())
    files=[f for f in files if str(f.relative_to(SOURCE/'tests')) not in keep]
with ThreadPoolExecutor(max_workers=2) as pool:
    for i,row in enumerate(pool.map(check,files),1):
        report['results'].append(row)
        if i%20==0 or row['result']!='pass': print(i,len(files),row['test'],row['result'],flush=True)
        a.output.write_text(json.dumps(report,indent=2)+'\n')
report['summary']={key:sum(r['result']==key for r in report['results']) for key in sorted({r['result'] for r in report['results']})}
report['optimized_regions']=sum(r.get('regions',0) for r in report['results'])
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['summary','optimized_regions']}),flush=True)
assert all(r['result'] in ['pass','interpreter-only-pass','baseline-build-failure','baseline-output-mismatch'] for r in report['results'])
