#!/usr/bin/env python3
"""Publish B diagnostic summaries and illustrative native-waveform excerpts.

All receiver/energy conclusions come from full-frame result.json. Only the
illustration is sampled onto a small time grid; it never feeds the receiver.
"""
from pathlib import Path
import csv
import gzip
import hashlib
import json
import re
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/ab-improvement-20261111'
EVIDENCE=ROOT/'evidence/ab-improvement-20261111'

def read(p):return json.loads(p.read_text())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def prefix(wave,stop):
    rows=[]
    with gzip.open(wave,'rt') as f:
        next(f)
        for line in f:
            words=line.split();rows.append(words)
            if float(words[0])>=stop:break
    a=np.asarray(rows,dtype=float)
    assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0) and a[-1,0]>=stop
    return a

def main():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    records=[];curves=[]
    for work in sorted(BUILD.glob('B_*')):
        if not (work/'manifest.json').exists():continue
        m=read(work/'manifest.json');stim=read(work/'stimulus.json');bits=np.asarray(stim['bits'])
        cap_match=re.search(r'^CFF\s+GB\s+OUT\s+([0-9.]+)f\s*$',(work/'inputs/route_b.spice').read_text(),flags=re.M|re.I)
        cap=float(cap_match.group(1)) if cap_match else 0
        # Netlist value is authoritative, including copied holdout candidates.
        notes=m.get('notes',{})
        if isinstance(notes,dict) and notes.get('notes',{}).get('cff_fF') is not None:
            assert cap==notes['notes']['cff_fF']
        for p in sorted((work/'cases').glob('*/result.json')):
            r=read(p);case=r['case'];metrics=r.get('metrics',{})
            row=dict(candidate=work.name,case=case,simulation_ok=r['simulation_ok'],analysis_error=r.get('analysis_error'),
                     result_path=str(p.relative_to(ROOT)),result_sha256=sha(p),manifest_sha256=r['manifest_sha256'],
                     deck_sha256=r['deck_sha256'],waveform_gzip_sha256=r.get('gzip_sha256'),waveform_raw_sha256=r.get('raw_sha256'),
                     CFF_fF=cap)
            if case.get('kind')=='dc':
                row.update(DC_screen_pass=r.get('DC_screen_pass'),current_uA=metrics.get('i_led_A',0)*1e6,
                           current_error_percent=metrics.get('current_error_percent'))
            elif r.get('analysis'):
                row.update(analysis=r['analysis'],mean_LED_current_uA=metrics['mean_LED_current_A']*1e6,
                           source_positive_pJ_per_attempted_bit={n:x['positive_J']*1e12/4096 for n,x in metrics['energy'].items()},
                           source_net_pJ_per_attempted_bit={n:x['net_J']*1e12/4096 for n,x in metrics['energy'].items()},
                           worst_body_device=max(metrics['stress'],key=lambda x:x['max_body_forward_V']))
                # Selected matched-rate native causal traces only. Higher-rate full
                # result metrics remain above; no interpolation is used for limits.
                if abs(case['net_rate_Gbps']-.8)<1e-12 and case['steps_per_symbol']==40:
                    ui=32/37/.8e9
                    indexes=[next(k for k in range(100,len(bits)-4) if np.all(bits[k-3:k]==a) and np.all(bits[k:k+3]==b)) for a,b in [(0,1),(1,0)]]
                    wave=p.with_name('waveform.dat.gz');assert sha(wave)==r['gzip_sha256']
                    data=prefix(wave,(max(indexes)+3)*ui);v=r['metadata']['vectors'];t=data[:,0]
                    transition_rows=[]
                    for k,(a,b) in zip(indexes,[(0,1),(1,0)]):
                        offset=np.arange(-100,2100+1,10)*1e-12;offset=offset[offset<3*ui-20e-12];times=k*ui+offset
                        values={n:np.interp(times,t,data[:,v[n]]) for n in ['iled_cond','out','led_a','led_k','xdrv.di','xdrv.gb','xdrv.gp','xdrv.vx','xdrv.dummy']}
                        current=values['iled_cond']*1e6;led_v=values['led_a']-values['led_k'];charge=cap*(values['xdrv.gb']-values['out'])
                        for j,dt in enumerate(offset):
                            curves.append(dict(candidate=work.name,transition=f'{a}->{b}',frame_bit=k,relative_time_ps=float(dt*1e12),
                                               current_uA=float(current[j]),led_terminal_V=float(led_v[j]),out_V=float(values['out'][j]),
                                               di_V=float(values['xdrv.di'][j]),gb_V=float(values['xdrv.gb'][j]),gp_V=float(values['xdrv.gp'][j]),
                                               vx_V=float(values['xdrv.vx'][j]),dummy_V=float(values['xdrv.dummy'][j]),CFF_fF=cap,CFF_GB_plate_charge_fC=float(charge[j])))
                        probes=[0,100,200,500,1000,2000]
                        transition_rows.append(dict(from_bit=a,to_bit=b,frame_bit=k,probe_time_ps=probes,
                            current_uA=np.interp(np.array(probes)*1e-12,offset,current).tolist(),
                            CFF_GB_plate_charge_fC=np.interp(np.array(probes)*1e-12,offset,charge).tolist()))
                    row['long_run_transition_probes']=transition_rows
            records.append(row)
    convergence=[]
    for fine in records:
        fc=fine['case']
        if fc.get('kind')=='dc' or fc.get('steps_per_symbol')!=80 or 'analysis' not in fine:continue
        coarse=next((r for r in records if r['candidate']==fine['candidate'] and r['case'].get('kind')!='dc' and r['case'].get('steps_per_symbol')==40 and r['case']['net_rate_Gbps']==fc['net_rate_Gbps'] and 'analysis' in r),None)
        if coarse is None:continue
        a,b=coarse['analysis'],fine['analysis'];ra,rb=a['full_receiver'],b['full_receiver']
        convergence.append(dict(candidate=fine['candidate'],net_Gbps=fc['net_rate_Gbps'],same_combined_decision=a['combined_screen_pass']==b['combined_screen_pass'],
            fine_minus_coarse_amplitude_uAeq=rb['worst_signed_margin_uAeq']-ra['worst_signed_margin_uAeq'],
            fine_minus_coarse_time_ps=rb['one_sided_margin_ps']-ra['one_sided_margin_ps'],
            positive_energy_relative_percent=100*(b['energy_pJ_per_attempted_payload_bit']['positive']/a['energy_pJ_per_attempted_payload_bit']['positive']-1),
            coarse_result=coarse['result_path'],fine_result=fine['result_path']))
    out=dict(schema='B-driver-improvement-diagnostics-v1',records=records,convergence=convergence,
             receiver_source='Full native frame, fixed 2026-11-10 training-only contract; plotted excerpts are never receiver input.',
             curve_scope='Native verified waveform interpolated at10ps only for illustration of selected net0.8Gb/s long-run transitions.',
             charge_definition='Q_GB=CFF*(V_GB-V_OUT); deltaQ is the integral of capacitor current from GB toward OUT. No derivative peak-current claim.',
             limitations=['Same DC25/100uA targets do not imply equal transient current peaks or equal mean optical power.','Positive and signed-net source energy differ because feed-forward can return charge to source ports.','No new layout/PEX, MIM realization, EM, PVT or optical measurement qualification.'])
    (EVIDENCE/'b-diagnostics.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    if curves:
        with (EVIDENCE/'b-transitions.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=curves[0].keys());w.writeheader();w.writerows(curves)
    print(json.dumps(dict(records=len(records),illustration_rows=len(curves))))

if __name__=='__main__':main()
