#!/usr/bin/env python3
"""Independent 6V-device hypothesis, preserves LED/RX and terminal energy accounting."""
import argparse,datetime,json,re,shutil
from pathlib import Path
import run as r
import validate as v

def source(route,poly_length=None):
    src=r.ROOT/'analog/highspeed_nrz_pvt'/('hs_voltage_pvt.spice' if route=='A' else 'hs_steering_pvt.spice')
    if not src.exists(): src=next(p for p in (r.ROOT/'analog/highspeed_nrz_pvt').glob('*.spice') if ('voltage' if route=='A' else 'steering') in p.name)
    lines=[]
    for line in src.read_text().splitlines():
        f=line.split()
        if len(f)>5 and f[5] in ['nfet_03v3','pfet_03v3'] and not (route=='B' and f[0] in ['XREF','XBASE','XTAIL']):
            typ=f[5][0]; old=float(re.search(r' w=([\d.]+)u',line)[1]);l=.7 if typ=='n' else .55;w=round(old*l/.28/.005)*.005
            line=' '.join(f[:5])+f' {typ}fet_06v0 w={w:g}u l={l:g}u ad={w*.44:g}p as={w*.44:g}p pd={2*(w+.44):g}u ps={2*(w+.44):g}u'
        if poly_length is not None and line.startswith('XRIN'):line=re.sub('r_length=[0-9.]+u',f'r_length={poly_length:g}u',line)
        lines.append(line)
    return '* HV hypothesis: 06v0 MOS for all full swing gates; W/L approximately preserved. Pre-layout estimates only.\n'+'\n'.join(lines)+'\n'

def add(work,poly_length=None):
    v.freeze(work);m=json.loads((work/'manifest.json').read_text())
    for q in 'AB':
        dst=work/'inputs/candidates'/f'{q}-HV.spice';dst.parent.mkdir(parents=True,exist_ok=True);txt=source(q,poly_length)
        if dst.exists() and dst.read_text()!=txt:raise ValueError('candidate drift')
        dst.write_text(txt)
        m['variants'][q]['HV']={'path':str(dst.relative_to(work/'inputs')),'sha256':r.sha(dst),'rref_source':'vdummy' if q=='B' else 'vdd','rref_ohm':88386.1064910889,'physical_status':'prelayout; all modified devices 06v0 minL N0.7/P0.55um; estimated diffusion geometry0.44um'}
        m['source_hashes'][str(dst.relative_to(work/'inputs'))]=r.sha(dst)
    m['scope']['candidate']='All A MOS and B inverter/switch MOS06v0. B REF/BASE/TAIL remain03v3. No rail reduction;06 conservative all-pair6.0V screening retains03 3.63V. Official condition limits distinct from olduniformscreen.'
    r.emit(work/'manifest.json',m)

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',default='build/highspeed-nrz-robustness/hv-r1');p.add_argument('--stage',choices=['targets','dc','stress'],default='targets');p.add_argument('--routes',default='AB');p.add_argument('--poly-length',type=float);a=p.parse_args();w=r.ROOT/a.work;add(w,a.poly_length)
    cs=[]
    for q in a.routes:
        for label,co,t,vd in [('FFplus50','ff',-40,3.65),('SS','ss',125,3.)]:
            c=v.case(w,q,label,co,t,vd,variant='HV')
            if a.stage=='dc':
                for bit in [0,1]:cs.append(c|{'name':c['name']+f'-dc{bit}','dc_bit':bit})
            else:cs.append(c)
    r.emit(w/f'plan-{a.stage}-{a.routes}.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs})
    for c in cs:print(json.dumps(v.analyze(w,r.run_case(w,c))),flush=True)
    v.summarize(w)
if __name__=='__main__':main()
