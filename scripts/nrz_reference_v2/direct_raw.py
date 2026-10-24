#!/usr/bin/env python3
"""Selected architectural simplification pilot:10MOSVI + actual5Vraw/RDUMMY."""
from pathlib import Path
import datetime,json,shutil
import numpy as np
import experiment as e
import run as r
import validate as v
WORK=r.BUILD/'direct-r1'

def freeze():
 assert not WORK.exists();WORK.mkdir();shutil.copytree(e.WORK/'inputs',WORK/'inputs');shutil.copy2(e.WORK/'stimulus.json',WORK/'stimulus.json')
 src=r.ROOT/'analog/nrz_reference_v2/vi_reference_selected.spice';shutil.copy2(src,WORK/'inputs/physical/N-direct-prelayout.spice')
 core=WORK/'inputs/physical/B-reference-RC.spice';e.combine(WORK/'inputs/physical/B-AFTER.spice',WORK/'inputs/physical/N-direct-prelayout.spice',core)
 m=json.loads((e.WORK/'manifest.json').read_text());m['parent_manifest_sha256']=r.sha(e.WORK/'manifest.json');m['created']=datetime.datetime.now().isoformat();m['variants']['B']['REFERENCE'].update(sha256=r.sha(core),direct_raw=True,rdummy_ohm=50000,reference_control='10MOSVIprelayout.44umdiffusion+oldBfullRC;rawVINsuppliesRDUMMY;LDOremoved')
 m['source_hashes']={str(p.relative_to(WORK/'inputs')):r.sha(p) for p in (WORK/'inputs').rglob('*') if p.is_file()};r.emit(WORK/'manifest.json',m)

def analyze_start(c,res):
 f=WORK/'cases'/c['name'];r.module(WORK/'inputs/legacy/metrics.py','metrics');a=r.module(WORK/'inputs/legacy/analyze.py','direct_start');a.ROOT=r.ROOT
 trace,src=a.load_trace(res,f/'result.json');stress=a.stress_metrics(trace,res);t=trace[:,0];vec=res['vectors'];i=trace[:,vec['iled_cond']];limits=[(6 if '06v0' in d['model'] else 3.63)-d['max_abs_terminal_V'] for d in stress['all_devices']]
 last=t>90e-6;error=np.abs(i-100e-6)>5e-6;ix=np.flatnonzero(error)
 row={'name':c['name'],'simulation_ok':True,'current_peak_A':float(i.max()),'current_final_A':float(i[-1]),'current_last10us_pp_A':float(np.ptp(i[last])),'last_outside5pct_s':float(t[ix[-1]]) if len(ix) else 0,'minimum_device_margin_V':min(limits),'startup_passed':bool(i.max()<=125e-6 and abs(i[-1]-100e-6)<=5e-6 and np.ptp(i[last])<1e-6 and min(limits)>=0)}
 r.emit(f/'startup-analysis.json',{'row':row,'stress':stress,'sources':src,'analysis_source_sha256':r.sha(__file__)});return row

def main():
 freeze();shutil.copy2(__file__,WORK/'direct_raw-executed.py')
 pvt=[('TT','typical',27,3.3),('SS','ss',125,2.95),('FF','ff',-40,3.65)]
 cs=[]
 for label,co,t,vdd in pvt:
  for bit in [0,1]:cs.append(v.case(WORK,'B','direct_DC_'+label,co,t,vdd,variant='REFERENCE',dc_bit=bit))
  cs.append(v.case(WORK,'B','direct_start_'+label,co,t,vdd,variant='REFERENCE',dc_bit=1,startup={'stop_s':100e-6,'maxstep_s':10e-9}))
 cs.append(v.case(WORK,'B','direct_miller_control','typical',27,3.3,variant='REFERENCE',dc_bit=1,compensation='miller',vi_comp_F=3e-12,startup={'stop_s':100e-6,'maxstep_s':10e-9}))
 cs.append(v.case(WORK,'B','direct_late_anchor','typical',27,3.3,variant='REFERENCE',dc_bit=1,startup={'stop_s':100e-6,'maxstep_s':10e-9,'anchor_delay_s':10e-6}))
 r.emit(WORK/'plan.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs,'architecture_authorization':'parent selectedraw5V/RDUMMY;idealVDUMMY removed,unnecessaryLDO removed,10MOSVI retained','compensation_hypothesis':'PWMagent same-topology N2-toVSSshunt releasesCTRLcommonmoderamp; try15p vsold3pMillerTTcontrol; noassumptionoftransferability','acceptance':{'startup_peak_LED_A':125e-6,'final_LED_A':[95e-6,105e-6],'last10us_pp_A':1e-6},'scope':'newVIprelayoutuntilactual10MOSmodulePEX;oldBfullRCunchanged'})
 rows=[]
 for c in cs:
  res=r.run_case(WORK,c);row=analyze_start(c,res) if c.get('startup') and res['simulation_ok'] else v.analyze(WORK,res);rows.append(row);print(json.dumps(row),flush=True)
 r.emit(r.EVIDENCE/'direct-r1.json',{'rows':rows})
if __name__=='__main__':main()
