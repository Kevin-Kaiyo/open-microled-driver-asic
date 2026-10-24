#!/usr/bin/env python3
"""External-sequenced realclamp+10Mohmkeeper; oldMillerVI retained."""
from pathlib import Path
import datetime,json,shutil
import experiment as e
import run as r
import validate as v
import direct_raw as d
WORK=r.BUILD/'clamped-r1'
def main():
 assert not WORK.exists();WORK.mkdir();srcwork=d.WORK;shutil.copytree(srcwork/'inputs',WORK/'inputs');shutil.copy2(srcwork/'stimulus.json',WORK/'stimulus.json')
 src=r.ROOT/'analog/nrz_reference_v2/vi_reference_clamped.spice';shutil.copy2(src,WORK/'inputs/physical/N-clamped-prelayout.spice');core=WORK/'inputs/physical/B-reference-RC.spice';e.combine(WORK/'inputs/physical/B-AFTER.spice',WORK/'inputs/physical/N-clamped-prelayout.spice',core)
 m=json.loads((srcwork/'manifest.json').read_text());m['created']=datetime.datetime.now().isoformat();m['parent_manifest_sha256']=r.sha(srcwork/'manifest.json');m['variants']['B']['REFERENCE'].update(sha256=r.sha(core),disable_clamp=True,keeper_ohm=1e7,reference_control='11MOSVI+externalDISABLEclamp prelayout .44umdiffusion; oldBfullRC',source_blocks=[{'path':r.rel(WORK/'inputs/physical/B-AFTER.spice'),'sha256':r.sha(WORK/'inputs/physical/B-AFTER.spice')},{'path':r.rel(src),'sha256':r.sha(src)}]);m['source_hashes']={str(p.relative_to(WORK/'inputs')):r.sha(p) for p in (WORK/'inputs').rglob('*') if p.is_file()};r.emit(WORK/'manifest.json',m)
 cs=[]
 for label,co,t,vdd in [('TT','typical',27,3.3),('SS','ss',125,2.95),('FF','ff',-40,3.65)]:
  cs.append(v.case(WORK,'B','clamped_start_'+label,co,t,vdd,variant='REFERENCE',dc_bit=1,compensation='miller',vi_comp_F=3e-12,startup={'stop_s':100e-6,'maxstep_s':10e-9,'disable_release_s':20e-6}))
 cs += [v.case(WORK,'B','clamped_late_anchor','typical',27,3.3,variant='REFERENCE',dc_bit=1,compensation='miller',vi_comp_F=3e-12,startup={'stop_s':100e-6,'maxstep_s':10e-9,'anchor_delay_s':30e-6,'disable_release_s':50e-6}),v.case(WORK,'B','clamped_early_release_NEG','typical',27,3.3,variant='REFERENCE',dc_bit=1,compensation='miller',vi_comp_F=3e-12,startup={'stop_s':100e-6,'maxstep_s':10e-9,'anchor_delay_s':30e-6,'disable_release_s':20e-6})]
 r.emit(WORK/'plan.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs,'contract':'ExternalDISABLE3.3Vthrough100ohmassertedbeforeVIN;release20usafteranchorstable, edge100ns. NotautonomousPOR. KeeperOUTtoGND10Mohm addsresidualcurrentandpower.','acceptance':{'startup_cond_LED_peak_A':125e-6,'final_A':[95e-6,105e-6],'03maxpairs_V':3.63,'06maxpairs_V':6.0},'negative_control':'Anchorlate30uswhileDISABLEreleased20us intentionallyviolatesexternalcontract; mustretain.'})
 d.WORK=WORK;shutil.copy2(__file__,WORK/'clamped_pilot-executed.py');shutil.copy2(Path(d.__file__),WORK/'direct_raw-analysis-executed.py')
 rows=[]
 for c in cs:
  res=r.run_case(WORK,c);row=d.analyze_start(c,res) if res['simulation_ok'] else {'name':c['name'],'simulation_ok':False};rows.append(row);print(json.dumps(row),flush=True)
 r.emit(r.EVIDENCE/'clamped-r1.json',{'rows':rows})
if __name__=='__main__':main()
