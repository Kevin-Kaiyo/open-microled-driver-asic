#!/usr/bin/env python3
"""Verify final AC decks and independently recompute voltage-injection diagnostics."""
from pathlib import Path
import json,math
import numpy as np
from audit_recheck import ROOT,EV,sha

base=ROOT/'build/vcsel-robustness-20261029';rows=[]
norm=lambda s:[line.split() for line in s.splitlines() if line.strip() and not line.lstrip().startswith('*')]
for corner in ['TT','SS','FF']:
    for branch in ['L','D']:
        work=base/f'ac-final-{corner}-{branch}-r10';r=json.loads((work/'result.json').read_text())
        source=base/r['source_case'];text=(work/'driver.spice').read_text()
        restored='\n'.join(line.replace(branch+'fb_test',branch+'fb') for line in text.splitlines() if not line.startswith('VLOOP'))
        assert norm(restored)==norm((source/'inputs/driver.spice').read_text())
        assert sha(source/'inputs/driver.spice')==r['source_circuit_sha256']
        for filename,key in [('driver.spice','modified_circuit_sha256'),('testbench.spice','deck_sha256'),('ac.dat','data_sha256')]:assert sha(work/filename)==r[key]
        a=np.loadtxt(work/'ac.dat',skiprows=1);f=a[:,0]
        return_ratio=-(a[:,1]+1j*a[:,2])/(a[:,3]+1j*a[:,4])
        db=20*np.log10(abs(return_ratio));phase=np.unwrap(np.angle(return_ratio))*180/math.pi
        cuts=[]
        for k in range(len(f)-1):
            if db[k]>=0 and db[k+1]<0:
                weight=db[k]/(db[k]-db[k+1]);hz=f[k]*(f[k+1]/f[k])**weight
                pm=180+phase[k]+weight*(phase[k+1]-phase[k]);cuts.append({'unity_Hz':float(hz),'phase_margin_deg':float(pm)})
        assert len(cuts)==len(r['unity_crossings'])
        for mine,saved in zip(cuts,r['unity_crossings']):
            assert abs(mine['unity_Hz']-saved['unity_Hz'])<1e-6 and abs(mine['phase_margin_deg']-saved['phase_margin_deg'])<1e-9
        rows.append({'case':work.name,'source_case':r['source_case'],'source_circuit_sha256':r['source_circuit_sha256'],
            'data_sha256':r['data_sha256'],'injection_restores_exact_original_netlist':True,'unity_crossings':cuts,
            'interpretation':'SS dropout; no regulation phase-margin claim' if corner=='SS' else 'Approximate high-impedance gate voltage injection at the frozen DC point; not full return-ratio or foundry stability signoff'})
(EV/'audit-r10-ac-recheck.json').write_text(json.dumps({'script_sha256':sha(__file__),'rows':rows},indent=2)+'\n')
print(json.dumps(rows,indent=2))
