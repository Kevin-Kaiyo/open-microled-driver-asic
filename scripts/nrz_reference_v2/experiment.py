#!/usr/bin/env python3
"""Immutable phase plans for true-PEX current servo/LDO + old B core."""
from pathlib import Path
import argparse,datetime,json,shutil
import run as r
import validate as v
OLD=r.ROOT/'build/highspeed-nrz-robustness/selected-a8-b58-r4'
WORK=r.BUILD/'selected-r1'

def combine(bpath,npath,out):
    ports=[]
    for path,rename in [(bpath,{}),(npath,{'IOUT':'BIAS'})]:
        declared=next(x.split() for x in path.read_text().splitlines() if x.lower().startswith('.subckt'))[2:]
        for name in declared:
            name=rename.get(name.upper(),name.upper())
            if name not in ports:ports.append(name)
    lines=['* Hierarchical modules flattened for simulation. Each block has independently extracted RC.', '* Cross-block connections are explicit ideal top-level wires, not newly routed on-chip PEX.', '.subckt nrz_b_reference_v2 '+' '.join(ports)]
    for path,prefix,rename in [(bpath,'B',{}),(npath,'N',{'IOUT':'BIAS'})]:
        txt=r.re.sub(r'\n\s*\+\s*',' ',path.read_text());decl=next(x.split() for x in txt.splitlines() if x.lower().startswith('.subckt'))
        mapped={x.lower():rename.get(x.upper(),x.upper()) for x in decl[2:]}
        def node(n):return '0' if n=='0' else mapped.get(n.lower(),prefix+'_'+n)
        for line in txt.splitlines():
            p=line.split()
            if not p or p[0].startswith(('*','.')):continue
            if p[0][0].lower() in ['r','c']:count=2
            elif p[0][0].lower()=='x':count=3 if p[4].lower()=='ppolyf_u_1k_6p0' else 4
            else:raise ValueError('Unexpected physical element '+line)
            p[0]=p[0][0]+prefix+'_'+p[0][1:];p[1:1+count]=[node(n) for n in p[1:1+count]];lines.append(' '.join(p))
    lines.append('.ends nrz_b_reference_v2');out.write_text('\n'.join(lines)+'\n')

def freeze(work):
    if (work/'manifest.json').exists():return v.verify(work)
    assert not work.exists();work.mkdir(parents=True);shutil.copytree(OLD/'inputs',work/'inputs');shutil.copy2(OLD/'stimulus.json',work/'stimulus.json')
    m=json.loads((OLD/'manifest.json').read_text());m['parent_manifest_sha256']=r.sha(OLD/'manifest.json');m['created']=datetime.datetime.now().isoformat()
    inp=work/'inputs';newsrc=r.ROOT/'build/reference-v2-layout/nrz-r1/N/full-rc/nrz_bias_power_rc.spice'
    shutil.copy2(newsrc,inp/'physical/N-reference-RC.spice')
    shutil.copy2(r.ROOT/'build/reference-v2-layout/nrz-r1/N/physical-contract.json',inp/'physical/N-contract.json')
    combined=inp/'physical/B-reference-RC.spice';combine(inp/'physical/B-AFTER.spice',inp/'physical/N-reference-RC.spice',combined)
    m['variants']={'B':{'BASELINE':m['variants']['B']['AFTER'],'REFERENCE':{'path':'physical/B-reference-RC.spice','sha256':r.sha(combined),'reference_v2':True,'source_blocks':[{'path':str(OLD/'inputs/physical/B-AFTER.spice'),'sha256':r.sha(inp/'physical/B-AFTER.spice')},{'path':r.rel(newsrc),'sha256':r.sha(newsrc)}],'top_level_interconnect':'Ideal explicit module interconnect; no integrated wholechiplayoutclaim'}}}
    m['source_hashes']={str(p.relative_to(inp)):r.sha(p) for p in inp.rglob('*') if p.is_file()};m['scope_v2']=json.loads((r.EVIDENCE/'scope.json').read_text());r.emit(work/'manifest.json',m);return v.verify(work)

def make(label,co='typical',temp=27,vdd=3.3,variant='REFERENCE',**kw):
    return v.case(WORK,'B',label,co,temp,vdd,variant=variant,**kw)

def plans(stage):
    cs=[];pvt=[('TT','typical',27,3.3),('SS','ss',125,2.95),('FF','ff',-40,3.65)]
    if stage in ['dc','nrz']:
        for label,co,t,vdd in pvt:
            for bit in ([0,1] if stage=='dc' else [None]):
                cs.append(make(label+'_'+stage,co,t,vdd,**({'dc_bit':bit} if bit is not None else {})))
    elif stage=='baseline_resistors':
        for label,co,t,vdd in pvt:
            for bit in [0,1]:cs.append(make('old_'+label,co,t,vdd,variant='BASELINE',dc_bit=bit))
            for resistor in ['RREF','RDUMMY']:
                for error in [-.01,.01]:
                    for tc in [-100,100]:
                        for bit in [0,1]:cs.append(make(f'old_{label}_{resistor}_{error}_{tc}',co,t,vdd,variant='BASELINE',dc_bit=bit,resistor_errors={resistor:error},resistor_tc_ppm={resistor:tc}))
        for resistor in ['RREF','RDUMMY']:
            for error in [-.05,.05]:
                for bit in [0,1]:cs.append(make(f'old_{resistor}_neg5_{error}',variant='BASELINE',dc_bit=bit,resistor_errors={resistor:error}))
    else:raise ValueError(stage)
    return cs

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['dc','nrz','baseline_resistors'],required=True);a=p.parse_args();freeze(WORK)
    cs=plans(a.stage);plan=WORK/f'plan-{a.stage}.json'
    if plan.exists():assert json.loads(plan.read_text())['cases']==cs
    else:r.emit(plan,{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs,'source_sha256':r.sha(__file__)})
    for c in cs:
        row=v.analyze(WORK,r.run_case(WORK,c));print(json.dumps(row),flush=True)
    v.summarize(WORK)
if __name__=='__main__':main()
