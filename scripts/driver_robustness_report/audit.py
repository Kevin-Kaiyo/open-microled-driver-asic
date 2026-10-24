#!/usr/bin/env python3
"""Independent read-only terminal and energy recomputation for report evidence.

Does not call the simulation analyzer. Failing engineering cases are valid evidence;
only missing/corrupt inputs or inconsistent computations fail this audit.
"""
from pathlib import Path
import argparse, gzip, hashlib, itertools, json
import numpy as np
ROOT=Path(__file__).resolve().parents[2]

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(p.read_text())
def integral_window(t,p,start,end,positive=False):
    inside=(t>start)&(t<end)
    x=np.r_[start,t[inside],end];y=np.r_[np.interp(start,t,p),p[inside],np.interp(end,t,p)]
    if positive:
        crossing=np.flatnonzero(y[:-1]*y[1:]<0)
        if len(crossing):
            zeros=x[crossing]-y[crossing]*(x[crossing+1]-x[crossing])/(y[crossing+1]-y[crossing])
            order=np.argsort(np.r_[x,zeros]);x=np.r_[x,zeros][order];y=np.r_[y,np.zeros(len(zeros))][order]
        y=np.maximum(y,0)
    return float(np.trapezoid(y,x))
def check_row(row):
    p=ROOT/row['result_json'];result=read(p);folder=p.parent
    assert result['simulation_ok'], 'selected audit row must have an actual completed simulation'
    assert sha(folder/'testbench.spice')==result['deck_sha256']
    assert sha(ROOT/result['log'])==result['log_sha256']
    raw=ROOT/result['waveform'];assert sha(raw)==result['waveform_sha256']
    with gzip.open(raw,'rb') as f:payload=f.read()
    assert hashlib.sha256(payload).hexdigest()==result['uncompressed_sha256']
    import io
    a=np.atleast_2d(np.loadtxt(io.BytesIO(payload),skiprows=1));del payload
    vec=result['vectors'];t=a[:,0]
    assert np.isfinite(a).all() and np.all(np.diff(t)>0)
    def voltage(node):return np.zeros(len(a)) if node=='0' else a[:,vec[node]]
    worst={'voltage_V':-1};device_margins=[];gate_max=-1
    for device in result['devices']:
        maximum=0
        for i,j in itertools.combinations(range(4),2):
            v=voltage(device['nodes'][i])-voltage(device['nodes'][j]);k=int(np.argmax(np.abs(v)));peak=abs(float(v[k]));maximum=max(maximum,peak)
            if i==1 or j==1:gate_max=max(gate_max,peak)
            if peak>worst['voltage_V']:worst={'voltage_V':peak,'instance':device['instance'],'pair':'DGSB'[i]+'DGSB'[j],'time_s':float(t[k])}
        limit=6.0 if '06v0' in device['model'] else 3.63
        device_margins.append(limit-maximum)
    assert abs(worst['voltage_V']-row['max_abs_terminal_V'])<1e-10
    if 'minimum_device_specific_margin_V' in row:assert abs(min(device_margins)-row['minimum_device_specific_margin_V'])<1e-10
    work=folder.parents[1];stim=read(work/'stimulus.json');ui=1/(row['rate_Gbps']*1e9)
    start,end=stim['validation_start_bit']*ui,stim['validation_end_bit']*ui
    bits=len(stim['validation_bits']);pos=neg=net=0
    for rail in result['rails']:
        power=-a[:,vec[rail.lower()+'_voltage']]*a[:,vec[rail.lower()+'_current']]
        pos+=integral_window(t,power,start,end,True);neg+=integral_window(t,-power,start,end,True);net+=integral_window(t,power,start,end)
    power=-a[:,vec['data']]*a[:,vec['data_current']]
    pos+=integral_window(t,power,start,end,True);neg+=integral_window(t,-power,start,end,True);net+=integral_window(t,power,start,end)
    assert abs(pos-neg-net)<max(1e-20,abs(pos)*1e-10)
    energy=pos/bits*1e15;reported=row['rail_plus_DATA_positive_draw_fJ_per_gross_bit']
    assert abs(energy-reported)<max(1e-6,abs(reported)*1e-7),(energy,reported)
    expected=row['errors']==0 and row['threshold_margin_normalized']>=.1 and row['timing_min_margin_ui']>=.1 and min(device_margins)>=0
    assert expected==row['combined_screen_passed']
    return {'case':row['name'],'result_sha256':sha(p),'waveform_sha256':sha(raw),'worst_terminal':worst,'maximum_gate_to_other_V':gate_max,'minimum_device_specific_margin_V':min(device_margins),'positive_energy_fJ_per_gross_bit':energy,'reported_energy_fJ_per_gross_bit':reported,'energy_difference_fJ':energy-reported,'combined_screen_passed':expected,'readback_and_independent_recalculation_passed':True}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--summary',required=True);ap.add_argument('--kinds',required=True);ap.add_argument('--output',required=True);args=ap.parse_args()
    p=ROOT/args.summary;s=read(p);s=s.get('selected',s);kinds=args.kinds.split(',');rows=[r for r in s['rows'] if r['kind'] in kinds and r.get('analysis_ok') and 'dc_bit' not in r]
    assert rows,'empty audit selection'
    out={'summary':args.summary,'summary_sha256':sha(p),'auditor_sha256':sha(Path(__file__)),'selected_kinds':kinds,'rows':[check_row(r) for r in rows]}
    out['count']=len(rows);out['passed']=True;q=ROOT/args.output;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'count':out['count'],'passed':True,'output':args.output}))
if __name__=='__main__':main()
