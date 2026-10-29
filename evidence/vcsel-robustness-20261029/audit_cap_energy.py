#!/usr/bin/env python3
"""Independent explicit-capacitor endpoint energy audit; not total energy balance."""
from pathlib import Path
import argparse,gzip,json
import numpy as np
from audit_recheck import ROOT,EV,sha


def run(case):
    work=ROOT/'build/vcsel-robustness-20261029'/case
    m=json.loads((work/'manifest.json').read_text());r=json.loads((work/'result.json').read_text());c=m['config']
    assert sha(ROOT/r['waveform']['path'])==r['waveform']['sha256']
    first=None;last=None
    with gzip.open(ROOT/r['waveform']['path'],'rt') as f:
        next(f)
        for line in f:
            if first is None and float(line.split(None,1)[0])>=0:first=line
            last=line
    a=np.vstack([np.fromstring(first,sep=' '),np.fromstring(last,sep=' ')])
    assert a.shape[1]==len(m['expressions'])+1
    ix={e:k+1 for k,e in enumerate(m['expressions'])}
    specifications={
        'Lout':(10e-9,'xdrv.lcap',None),'Dout':(1e-9,'xdrv.dcap',None),
        'rawLaser':(1e-9,'laser_c',None),'rawDriver':(1e-9,'vdd_c',None),
        'Bcomp':(c['cc'],'xdrv.bn2','xdrv.bctrl'),'Tcomp':(c['cc'],'xdrv.tn2','xdrv.tctrl'),
        'Lcomp':(c['cldo'],'xdrv.lzc','xdrv.lctrl'),'Dcomp':(c['cldo'],'xdrv.dzc','xdrv.dctrl')}
    assert 'CLOUT Lcap VSS 10n' in (work/'inputs/driver.spice').read_text()
    values={}
    for name,(cap,p,n) in specifications.items():
        voltage=a[:,ix['v('+p+')']]-(a[:,ix['v('+n+')']] if n else 0)
        energy=cap*voltage*voltage/2
        row=dict(capacitance_F=cap,start_J=float(energy[0]),end_J=float(energy[1]),change_J=float(energy[1]-energy[0]))
        for k,v in row.items():assert abs(v-r['explicit_capacitor_energy']['capacitors'][name][k])<1e-19,(name,k)
        values[name]=row
    change=sum(v['change_J'] for v in values.values())
    assert abs(change-r['explicit_capacitor_energy']['change_J'])<1e-19
    frame=c['mode']=='frame'
    return dict(case=case,waveform_sha256=r['waveform']['sha256'],endpoint_times_s=a[:,0].tolist(),
        capacitors=values,total_explicit_delta_U_J=change,
        delta_U_pJ_per_offered_payload_bit=change/4096*1e12 if frame else None,
        energy_port_comparison=r.get('total_energy'),
        boundary='Positive delta U is charging, negative is release of stored energy. Includes listed explicit supply and compensation capacitors only; excludes MOS charge and load/package storage. This is not a complete balance or a steady-state correction to full-link pJ/bit.')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--case',required=True,action='append');ap.add_argument('--output',required=True);a=ap.parse_args()
    assert a.output.startswith('audit-') and '/' not in a.output and a.output.endswith('.json')
    rows=[]
    for case in a.case:
        row=run(case);rows.append(row);print(json.dumps({'case':case,'delta_U_pJ_per_offered_payload_bit':row['delta_U_pJ_per_offered_payload_bit']},indent=2),flush=True)
    (EV/a.output).write_text(json.dumps({'script_sha256':sha(__file__),'rows':rows},indent=2)+'\n')
