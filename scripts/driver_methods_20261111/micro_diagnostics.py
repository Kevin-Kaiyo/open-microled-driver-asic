#!/usr/bin/env python3
"""Native-node causal extracts; plotting interpolation never enters RX analysis."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'evidence/driver-methods-20261111'
SOURCES=[('A_before','ab-improvement-20261111','a-rin1wide-core03-matched'),
         ('A_RCFF','driver-methods-20261111','A_rcff31p275'),
         ('B_before','ab-improvement-20261111','B_wide_ff31p275'),
         ('B_VIN_only','driver-methods-20261111','B_vin3p3_dummy50k_control'),
         ('B_VIN_Rdummy','driver-methods-20261111','B_vin3p3_dummy27p6k')]

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def read(p):return json.loads(p.read_text())

def main():
    records=[];dc=[];edges=[]
    for label,stage,name in SOURCES:
        w=ROOT/'build'/stage/name
        for level in [0,1]:
            p=w/'cases'/f'DC-L{level}'
            if not (p/'result.json').exists():continue
            r=read(p/'result.json');v=r['metadata']['vectors'];a=np.loadtxt(gzip.open(p/'waveform.dat.gz','rt'),skiprows=1,ndmin=2)[0]
            nodes={k:float(a[ix]) for k,ix in v.items() if k in ['vin','xdrv.dummy','xdrv.vx','xdrv.bias','xdrv.sense','xdrv.vh','xdrv.vl','xdrv.ff','xdrv.n1','xdrv.ctrl','out']}
            d=dict(label=label,level=level,nodes_V=nodes,current_uA=r['metrics']['i_led_A']*1e6,result_sha256=sha(p/'result.json'))
            if label.startswith('B'):
                rdummy=27600 if label=='B_VIN_Rdummy' else 50000
                d['dummy_resistance_Ohm']=rdummy;d['dummy_current_uA']=(nodes['vin']-nodes['xdrv.dummy'])/rdummy*1e6
            dc.append(d)
        p=w/'cases/TT-net1.6-C200-S40'
        if not (p/'result.json').exists():continue
        r=read(p/'result.json');v=r['metadata']['vectors'];ui=(32/37)/1.6e9;stop=136*ui+1.8e-9
        data=[]
        with gzip.open(p/'waveform.dat.gz','rt') as f:
            next(f)
            for line in f:
                a=[float(x) for x in line.split()]
                data.append(a)
                if a[0]>=stop:break
        a=np.array(data);t=a[:,0]
        for transition,k in [('0->1',136),('1->0',116)]:
            dt=np.arange(-200,1801,10,dtype=float);times=k*ui+dt*1e-12
            values={n:np.interp(times,t,a[:,ix]) for n,ix in v.items()}
            for i,rel in enumerate(dt):
                d=dict(label=label,transition=transition,frame_bit=k,time_ps=rel,current_uA=values['iled_cond'][i]*1e6)
                for n in ['d0','out','xdrv.n1','xdrv.ctrl','xdrv.ff','xdrv.gb','xdrv.gp','xdrv.vx','xdrv.dummy']:
                    d[n.replace('xdrv.','')+'_V']=values[n][i] if n in values else None
                if label=='A_RCFF':d['CFF_FF_plate_fC']=31.275*(values['xdrv.ff'][i]-values['out'][i])
                edges.append(d)
        record=dict(label=label,source=str(p.relative_to(ROOT)),result_sha256=sha(p/'result.json'),raw_sha256=r['raw_sha256'],gzip_sha256=r['gzip_sha256'],native_prefix_rows=len(a))
        if label!='A_before':
            with gzip.open(p/'waveform.dat.gz','rt') as f:
                next(f);first=[float(x) for x in next(f).split()]
                for line in f:last_line=line
            last=[float(x) for x in last_line.split()]
            plate='xdrv.ff' if label=='A_RCFF' else 'xdrv.gb'
            vi=first[v[plate]]-first[v['out']];vf=last[v[plate]]-last[v['out']]
            ei=.5*31.275e-15*vi*vi;ef=.5*31.275e-15*vf*vf
            record['CFF_storage']=dict(capacitance_fF=31.275,plate=plate,initial_voltage_V=vi,final_voltage_V=vf,initial_energy_pJ=ei*1e12,final_energy_pJ=ef*1e12,delta_energy_pJ=(ef-ei)*1e12,delta_pJ_per_attempted_payload_bit=(ef-ei)*1e12/4096,scope='This explicitly instantiated CFF only; not a full-circuit stored-energy audit.')
        records.append(record)
    cols=['label','transition','frame_bit','time_ps','current_uA','d0_V','out_V','n1_V','ctrl_V','ff_V','gb_V','gp_V','vx_V','dummy_V','CFF_FF_plate_fC']
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'micro-edge-extract.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(edges)
    (OUT/'micro-causal.json').write_text(json.dumps(dict(schema='native-node-causal-extract-v1',net_rate_Gbps=1.6,DC=dc,sources=records,edges=dict(rising_bit=136,falling_bit=116,stable_before_bits=4,stable_after_bits=4,interval_ps=[-200,1800],display_step_ps=10),limitations='Only display curves interpolated; full native receiver/stress calculations retained in result.json. Illustrative edges are not worst-case eye statistics.'),ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
