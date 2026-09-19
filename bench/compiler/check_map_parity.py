#!/usr/bin/env python3
"""Check three-map/single-map/original timed assembly using retained benchmark sources."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--bend-main',type=Path,required=True)
p.add_argument('--composition-report',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
out=Path(tempfile.mkdtemp(prefix='bend-loop-map-check-')).resolve()
old=json.loads(a.composition_report.read_text());sources=Path(old['artifacts'])
functions=[]
for label,compiler,source in [
    ('original',ROOT.parent/'bend/bend2/main.ts',sources/'three_maps-transducers.bend'),
    ('three_maps',a.bend_main,sources/'three_maps-transducers.bend'),
    ('single_map',a.bend_main,sources/'three_maps-single_map.bend')]:
    c=out/(label+'.c');asm=out/(label+'.s')
    subprocess.run(list(map(str,['bun',compiler,source,'-o',c])),check=True,capture_output=True)
    subprocess.run(list(map(str,['clang','-std=c11','-O3','-S',c,'-o',asm])),check=True,capture_output=True)
    m=re.search(r'^_?WL_FID_REPEAT:.*?^\s*\.cfi_endproc',asm.read_text(),re.M|re.S)
    assert m,'Timed function missing; inspect platform assembly'
    functions.append(m[0])
assert functions[0]==functions[1]==functions[2]
report={'artifacts':str(out),'compiler_sha256':hashlib.sha256((a.bend_main.parent/'comp.ts').read_bytes()).hexdigest(),
    'source_report':str(a.composition_report),'timed_function_identical':True,'assembly_sha256':hashlib.sha256(functions[0].encode()).hexdigest()}
a.output.write_text(json.dumps(report,indent=2)+'\n')
print('PASS map-chain assembly parity')
