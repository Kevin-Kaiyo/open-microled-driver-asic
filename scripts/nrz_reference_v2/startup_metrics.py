"""Separate startup/load-step metrics; no communication sampler retuning."""
from pathlib import Path
import hashlib,json
import numpy as np
import run as r
SOURCE_BYTES=Path(__file__).read_bytes();SOURCE_SHA=hashlib.sha256(SOURCE_BYTES).hexdigest()
def analyze(work,c,result):
 f=work/'cases'/c['name'];snapshot=work/'execution-sources'/('startup-metrics-'+SOURCE_SHA+'.py')
 if not snapshot.exists():snapshot.write_bytes(SOURCE_BYTES)
 row={'name':c['name'],'simulation_ok':result['simulation_ok']}
 if not result['simulation_ok']:return row
 r.module(work/'inputs/legacy/metrics.py','metrics');a=r.module(work/'inputs/legacy/analyze.py','start_analysis');a.ROOT=r.ROOT
 trace,sources=a.load_trace(result,f/'result.json');stress=a.stress_metrics(trace,result);t=trace[:,0];vec=result['vectors'];last=t>c['startup'].get('stop_s',100e-6)-10e-6
 current=trace[:,vec['iled_cond']];vreg=trace[:,vec['vreg_voltage']];limits=[(6 if '06v0' in d['model'] else 3.63)-d['max_abs_terminal_V'] for d in stress['all_devices']]
 row.update(current_min_A=float(current.min()),current_max_A=float(current.max()),current_final_A=float(current[-1]),vreg_final_V=float(vreg[-1]),vreg_max_V=float(vreg.max()),vreg_last10us_pp_V=float(np.ptp(vreg[last])),minimum_device_margin_V=min(limits),device_screen_passed=min(limits)>=0)
 if c['startup'].get('kind')!='loadstep':
  errors=(np.abs(vreg-3.3)>.066)|(np.abs(current-100e-6)>5e-6);indices=np.flatnonzero(errors)
  row['last_outside_settled_time_s']=float(t[indices[-1]]) if len(indices) else 0
  row['startup_screen_passed']=bool(current.max()<=125e-6 and abs(current[-1]-100e-6)<=5e-6 and abs(vreg[-1]-3.3)<=.066 and np.ptp(vreg[last])<.033 and min(limits)>=0)
 else:
  after=t>5e-6;row['loadstep_regulation_passed']=bool(np.max(np.abs(vreg[after]-3.3))<.066 and min(limits)>=0)
 r.emit(f/'startup-analysis.json',{'row':row,'stress':stress,'sources':sources,'analysis_source_sha256':SOURCE_SHA,'analysis_source':r.rel(snapshot)})
 return row
