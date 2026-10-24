#!/usr/bin/env python3
"""Retained-raw evidence window for supply/return package comparison."""
import argparse,csv,json
import numpy as np
import run as r
p=argparse.ArgumentParser();p.add_argument('--result',required=True);p.add_argument('--label',required=True);p.add_argument('--center-time',type=float);p.add_argument('--half-width-ns',type=float,default=2.);a=p.parse_args();path=r.ROOT/a.result;result=json.loads(path.read_text());work=path.parents[2]
r.module(work/'inputs/legacy/metrics.py','metrics');lg=r.module(work/'inputs/legacy/analyze.py','window_legacy');lg.ROOT=r.ROOT;trace,sources=lg.load_trace(result,path);stress=lg.stress_metrics(trace,result)
worst=next(d for d in stress['all_devices'] if d['instance']==stress['worst_instance']);pair=worst['worst_pair'];center=a.center_time if a.center_time is not None else worst['terminal_differences'][pair]['at_max_abs_time_s'];vec=result['vectors']
gates=[(d,p,d['terminal_differences'][p]) for d in stress['all_devices'] for p in ['VGS','VGD','VGB']];gd,gp,gv=max(gates,key=lambda x:x[2]['max_abs_V'])
def node(n):return np.zeros(len(trace)) if n=='0' else trace[:,vec[n]]
d,g,s,b=[node(n) for n in worst['nodes']];gate_wave=np.maximum.reduce([np.abs(g-s),np.abs(g-d),np.abs(g-b)])
cols={'time_s':trace[:,0],'time_UI':trace[:,0]*result['case']['rate_Gbps']*1e9,'source_VDD_V':trace[:,vec['vdd_voltage']],'die_VDD_V':trace[:,vec['die_vdd_voltage']],'die_VSS_V':trace[:,vec['die_vss_voltage']],'DATA_V':trace[:,vec['data']],'ILED_cond_A':trace[:,vec['iled_cond']],'worst_D_V':d,'worst_G_V':g,'worst_S_V':s,'worst_B_V':b,'worst_VDS_V':d-s,'worst_max_abs_gate_pair_V':gate_wave,'source_VDD_current_A':trace[:,vec['vdd_current']],'DATA_current_A':trace[:,vec['data_current']]}
all_gate=np.zeros(len(trace));all_vds=np.zeros(len(trace))
for dev in stress['all_devices']:
 dd,gg,ss,bb=[node(n) for n in dev['nodes']]
 all_gate=np.maximum(all_gate,np.maximum.reduce([np.abs(gg-ss),np.abs(gg-dd),np.abs(gg-bb)]))
 all_vds=np.maximum(all_vds,np.abs(dd-ss))
cols['all_MOS_max_abs_gate_pair_V']=all_gate;cols['all_MOS_max_abs_VDS_V']=all_vds
cols['die_VDD_minus_VSS_V']=cols['die_VDD_V']-cols['die_VSS_V']
idx=np.flatnonzero(np.abs(trace[:,0]-center)<=a.half_width_ns*1e-9);dest=r.EVIDENCE/f'{a.label}.csv';dest.parent.mkdir(exist_ok=True,parents=True)
with dest.open('w',newline='') as f:
 writer=csv.writer(f);writer.writerow(cols)
 for i in idx:writer.writerow([float(v[i]) for v in cols.values()])
meta={'source':sources,'case':result['case'],'csv':r.rel(dest),'csv_sha256':r.sha(dest),'rows':len(idx),'center_time_s':center,'half_width_ns':a.half_width_ns,'worst_device':worst,'overall_gate_peak':{'instance':gd['instance'],'model':gd['model'],'pair':gp,**gv},'waveform_columns':'worst D/G/S/B are the single worst all-terminal device; max_abs_gate_pair is this same device at each point. Global gate peak separately identified; all_MOS gate/VDS columns are per-time envelopes over every device.','interpretation':'Sampled node values; project screen, not physical breakdown or reliability signoff.'};r.emit(dest.with_suffix('.json'),meta);print(json.dumps({'csv':r.rel(dest),'center':center,'worst_instance':worst['instance'],'worst_pair':pair,'global_gate_peak':gv['max_abs_V']}))
