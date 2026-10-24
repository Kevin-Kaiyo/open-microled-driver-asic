#!/usr/bin/env python3
"""Bounded AC-informed compensation plus passive startup voltage protection."""
from pathlib import Path
import datetime,json,shutil
import run as r
import validate as v
import direct_raw as d
WORK=r.BUILD/'clamped-r2'
def main():
 assert not WORK.exists();WORK.mkdir()
 srcwork=r.BUILD/'clamped-r1'
 shutil.copytree(srcwork/'inputs',WORK/'inputs');shutil.copy2(srcwork/'stimulus.json',WORK/'stimulus.json')
 m=json.loads((srcwork/'manifest.json').read_text());m['created']=datetime.datetime.now().isoformat();m['parent_manifest_sha256']=r.sha(srcwork/'manifest.json')
 m['variants']['B']['REFERENCE']['keeper_ohm']=1.8e6
 m['source_hashes']={str(p.relative_to(WORK/'inputs')):r.sha(p) for p in (WORK/'inputs').rglob('*') if p.is_file()};r.emit(WORK/'manifest.json',m)
 common={'variant':'REFERENCE','dc_bit':1,'compensation':'shunt','vi_comp_F':150e-12}
 cs=[v.case(WORK,'B','shunt150_only_control','ff',-40,3.65,keeper_ohm=1e7,startup={'stop_s':100e-6,'maxstep_s':10e-9,'disable_release_s':20e-6},**common)]
 for label,co,t,vdd in [('TT','typical',27,3.3),('SS','ss',125,2.95),('FF','ff',-40,3.65)]:
  cs.append(v.case(WORK,'B','keeper1p8M_start_'+label,co,t,vdd,startup={'stop_s':100e-6,'maxstep_s':10e-9,'disable_release_s':20e-6},**common))
 for label,release in [('late_anchor',50e-6),('early_release_NEG',20e-6)]:
  cs.append(v.case(WORK,'B',label,'typical',27,3.3,startup={'stop_s':100e-6,'maxstep_s':10e-9,'anchor_delay_s':30e-6,'disable_release_s':release},**common))
 r.emit(WORK/'plan.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs,'hypothesis':'FF local two-injection estimate: Miller3p phase margin -0.23deg, shunt15p -3.09deg, shunt150p 66.31deg. First case isolates compensation with old10M keeper. Selected1.8M keeper shortens CLED passive discharge scale2us to0.36us; originalLED/RX unchanged.','contract':'External DISABLE asserted3.3V via100ohm before supplies; release20us after anchor begins1us rise. Cold supply ramp1us. This is an external sequencing condition, not autonomous POR.','acceptance':{'current_peak_A':125e-6,'current_final_A':[95e-6,105e-6],'last10us_current_pp_A':1e-6,'03pairs_V':3.63,'06pairs_V':6.0},'evidence_level':'11MOS prelayout plus old B actual fullRC; not integrated PEX','negative_controls':['old10M keeper with improved compensation','release before late anchor']})
 d.WORK=WORK;shutil.copy2(__file__,WORK/'clamped_refinement-executed.py');shutil.copy2(Path(d.__file__),WORK/'direct_raw-analysis-executed.py')
 rows=[]
 for c in cs:
  res=r.run_case(WORK,c);row=d.analyze_start(c,res) if res['simulation_ok'] else {'name':c['name'],'simulation_ok':False};rows.append(row);print(json.dumps(row),flush=True)
 r.emit(r.EVIDENCE/'clamped-r2.json',{'rows':rows})
if __name__=='__main__':main()
