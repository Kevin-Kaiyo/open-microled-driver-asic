#!/usr/bin/env python3
"""Actual-PEX startup screen; separate from frozen communication RX analysis."""
import datetime,json
import numpy as np
import experiment as e
import run as r
ANALYSIS_BYTES=__import__('pathlib').Path(__file__).read_bytes()
ANALYSIS_SHA=__import__('hashlib').sha256(ANALYSIS_BYTES).hexdigest()

def main():
 e.freeze(e.WORK)
 snapshot=e.WORK/'execution-sources'/('startup-'+ANALYSIS_SHA+'.py');snapshot.write_bytes(ANALYSIS_BYTES)
 cs=[e.make('startup_'+q,co,t,v,dc_bit=1,startup={'stop_s':100e-6,'maxstep_s':10e-9}) for q,co,t,v in [('TT','typical',27,3.3),('SS','ss',125,2.95),('FF','ff',-40,3.65)]]
 cs += [e.make('startup_late_anchor',dc_bit=1,startup={'stop_s':100e-6,'maxstep_s':10e-9,'anchor_delay_s':10e-6}),e.make('startup_loadstep',dc_bit=1,startup={'stop_s':100e-6,'maxstep_s':10e-9,'kind':'loadstep'})]
 plan=e.WORK/'plan-startup-full.json'
 if plan.exists():assert json.loads(plan.read_text())['cases']==cs
 else:r.emit(plan,{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs,'acceptance':{'current_peak_max_A':125e-6,'final_current_target_A':100e-6,'final_current_tolerance_percent':5,'vreg_final_V':3.3,'vreg_tolerance_percent':2,'last10us_vreg_pp_max_V':.033},'scope':'Primary startup current is conductiveLED viaVSENSE; supplycurrent includesCLED charging and is not conflated withconductiveLED. No receiverstatistics onstartup.'})
 rows=[]
 for c in cs:
  result=r.run_case(e.WORK,c,timeout=240);f=e.WORK/'cases'/c['name'];row={'name':c['name'],'simulation_ok':result['simulation_ok']}
  if result['simulation_ok']:
   r.module(e.WORK/'inputs/legacy/metrics.py','metrics')
   a=r.module(e.WORK/'inputs/legacy/analyze.py','start_analysis');a.ROOT=r.ROOT
   trace,_=a.load_trace(result,f/'result.json');stress=a.stress_metrics(trace,result);t=trace[:,0];vec=result['vectors'];last=t>90e-6
   current=trace[:,vec['iled_cond']];vreg=trace[:,vec['vreg_voltage']];limits=[(6 if '06v0' in d['model'] else 3.63)-d['max_abs_terminal_V'] for d in stress['all_devices']]
   row.update(current_min_A=float(current.min()),current_max_A=float(current.max()),current_final_A=float(current[-1]),vreg_final_V=float(vreg[-1]),vreg_max_V=float(vreg.max()),vreg_last10us_pp_V=float(np.ptp(vreg[last])),minimum_device_margin_V=min(limits),device_screen_passed=min(limits)>=0)
   if c['startup'].get('kind')!='loadstep':
    errors=(np.abs(vreg-3.3)>.066)|(np.abs(current-100e-6)>5e-6)
    indices=np.flatnonzero(errors);row['last_outside_settled_time_s']=float(t[indices[-1]]) if len(indices) else 0
    row['startup_screen_passed']=bool(current.max()<=125e-6 and abs(current[-1]-100e-6)<=5e-6 and abs(vreg[-1]-3.3)<=.066 and np.ptp(vreg[last])<.033 and min(limits)>=0)
   r.emit(f/'startup-analysis.json',{'row':row,'stress':stress,'result_sha256':r.sha(f/'result.json'),'analysis_source_sha256':ANALYSIS_SHA,'analysis_source':r.rel(snapshot)})
  rows.append(row);print(json.dumps(row),flush=True)
 r.emit(r.EVIDENCE/'startup-full-r1.json',{'work':r.rel(e.WORK),'rows':rows})
if __name__=='__main__':main()
