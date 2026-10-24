#!/usr/bin/env python3
"""Only enable the protective OUT resistor while external DISABLE is asserted."""
from pathlib import Path
import datetime,json,shutil
import run as r
import validate as v
import experiment as e
import final_v2 as f
import vi_startup
WORK=r.BUILD/'clamped-r3'
def main():
 assert not WORK.exists();WORK.mkdir();old=r.BUILD/'clamped-r2';shutil.copytree(old/'inputs',WORK/'inputs');shutil.copy2(old/'stimulus.json',WORK/'stimulus.json')
 src=r.ROOT/'analog/nrz_reference_v2/vi_reference_switched_keeper.spice';dest=WORK/'inputs/physical/N-switched-keeper.spice';shutil.copy2(src,dest);core=WORK/'inputs/physical/B-reference-RC.spice';e.combine(WORK/'inputs/physical/B-AFTER.spice',dest,core)
 m=json.loads((old/'manifest.json').read_text());m['created']=datetime.datetime.now().isoformat();m['parent_manifest_sha256']=r.sha(old/'manifest.json');m['variants']['B']['REFERENCE'].update(sha256=r.sha(core),switched_keeper=True,reference_control='12MOS VI/clamp/conditionalkeeper prelayout +oldBfullRC',source_blocks=[{'path':r.rel(src),'sha256':r.sha(src)}]);m['source_hashes']={str(p.relative_to(WORK/'inputs')):r.sha(p) for p in (WORK/'inputs').rglob('*') if p.is_file()};r.emit(WORK/'manifest.json',m)
 f.WORK=WORK;cs=[c for c in f.plan('dc') if c['kind'] in ['DC_TT','DC_SS','DC_FF','DC_SS_joint','DC_FF_joint']]
 cs.extend(c for c in f.plan('startup') if c['kind'] in ['startup_TT','startup_SS','startup_FF','startup_late_anchor','restart_FF_residual_LED_anchor'])
 r.emit(WORK/'plan.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs,'motivation':'Actual20MOSfullRC FFjoint errorsI0+6.485%/I1+5.919%; constantkeeper addsnormalLEDoffset. Addone06MOS andKRETboardport todisconnect1.8M whenDISABLE deasserted. Oldphysicalandfailurespreserved.','acceptance':'OriginalDC25/100uA targeterrors separately; startuphold<=2uA,release2us to100±5%,peak125uA,sixpairmodel-specificscreen; noRSETretune.'})
 shutil.copy2(__file__,WORK/'switched_keeper-executed.py');rows=[]
 for c in cs:
  res=r.run_case(WORK,c);row=vi_startup.analyze(WORK,c,res) if c.get('startup') else v.analyze(WORK,res);rows.append(row);print(json.dumps(row),flush=True)
 r.emit(r.EVIDENCE/'clamped-r3.json',{'rows':rows})
if __name__=='__main__':main()
