#!/usr/bin/env python3
"""Check a manually supplied loop feedback map using the pass's typed path facts.
Not automatic loop/caller recognition. Does not change lowering or production files.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--bend-main',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
out=Path(tempfile.mkdtemp(prefix='bend-induction-')).resolve()
for name in ['main.ts','comp.ts','bend.ts','base.bend']:shutil.copy2(a.bend_main.parent/name,out/name)
shutil.copytree(a.bend_main.parent/'effs',out/'effs')
comp=(out/'comp.ts').read_text()
anchor='            const guard = pc.map('
assert comp.count(anchor)==1
hook=r'''
            if (process.env.BEND_INDUCTION_REPORT) {
              // The two diagnostic fixtures use the same numeric feedback map.
              // This map and continuing output tag are provided by the investigator,
              // NOT inferred from field names/layouts or a generic Control record.
              const feedback = new Map([[1,1],[2,2],[3,3],[4,4]]);
              const replace = (x:GX, row:GR):GX => x.op === "var" && feedback.has(x.id!)
                ? row.v.xs[feedback.get(x.id!)!] : {...x, a:x.a.map(a=>replace(a,row))};
              const evidence = rows.map(row => {
                const facts:GP = [...row.pc,...pc];
                const inconsistent = pc.some(([c,y]) => {
                  const value=simp(c,row.pc); return value.op==="lit" && !!value.n!==y;
                });
                const continuing = simp(row.v.xs[0],facts);
                if (inconsistent || (continuing.op==="lit" && continuing.n!==0))
                  return {applicable:false};
                const results = pc.map(([c,y]) => {
                  const next=simp(replace(c,row),facts);
                  return {condition:c, wanted:y, next, proved:next.op==="lit" && !!next.n===y};
                });
                return {applicable:true, path:row.pc, outputs:row.v.xs, results,
                  proved:results.every(x=>x.proved)};
              });
              fs.appendFileSync(process.env.BEND_INDUCTION_REPORT, JSON.stringify({
                callee:ck.k, feedback:[...feedback], continuing_output:{index:0,value:0},
                fast_guard:pc, induction: evidence.every(x=>!x.applicable || x.proved), evidence
              })+"\n");
            }
'''
comp=comp.replace(anchor,hook+'\n'+anchor)
(out/'comp.ts').write_text(comp)
base=(HERE/'fixtures/reordered.bend').read_text()
negative=base.replace('Memory{Open{sum}, 1n+p, cookie}}','Memory{Closed{sum}, 1n+p, cookie}}').replace('Finished{Memory{Open{sum}, 0n, cookie}}','Finished{Memory{Closed{sum}, 0n, cookie}}')
(out/'breaks_induction.bend').write_text(negative)
cases=[('public_pipeline',ROOT/'bench/range.bend',True),('reordered',HERE/'fixtures/reordered.bend',True),('breaks_induction',out/'breaks_induction.bend',False)]
report={'scope':'typed scalar-path induction with manually supplied caller feedback and continuation tag; not automatic caller analysis','artifacts':str(out),'cases':[]}
for label,source,expected in cases:
    log=out/(label+'.jsonl')
    r=subprocess.run(['bun',str(out/'main.ts'),str(source),'-o',str(out/(label+'.c'))],env={**os.environ,'BEND_NO_TELEMETRY':'1','BEND_INDUCTION_REPORT':str(log)},text=True,capture_output=True)
    assert r.returncode==0,(label,r.stdout,r.stderr)
    # The existing compiler may emit multiple fixed-point analysis rounds.
    records=[json.loads(s) for s in sorted({json.dumps(json.loads(line),sort_keys=True) for line in log.read_text().splitlines()})]
    assert len(records)==1 and records[0]['induction']==expected,(label,records)
    report['cases'].append({'case':label,**records[0]})
    print(label,'inductive' if expected else 'rejected',flush=True)
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(out)
