#!/usr/bin/env python3
"""Isolate extracted reference-moduleRC; preserve sameMOSactualGDSgeometry andoldBfullRC."""
import datetime,json,shutil
import experiment as e
import run as r
import validate as v
from startup_metrics import analyze

def main():
 work=r.BUILD/'geometry-control-r1';assert not work.exists();work.mkdir()
 shutil.copytree(e.WORK/'inputs',work/'inputs');shutil.copy2(e.WORK/'stimulus.json',work/'stimulus.json')
 src=r.ROOT/'build/reference-v2-layout/nrz-r1/N/geometry-only.spice';shutil.copy2(src,work/'inputs/physical/N-reference-GEOM.spice')
 e.combine(work/'inputs/physical/B-AFTER.spice',work/'inputs/physical/N-reference-GEOM.spice',work/'inputs/physical/B-reference-RC.spice')
 m=json.loads((e.WORK/'manifest.json').read_text());m['parent_manifest_sha256']=r.sha(e.WORK/'manifest.json');m['created']=datetime.datetime.now().isoformat();m['variants']['B']['REFERENCE']['sha256']=r.sha(work/'inputs/physical/B-reference-RC.spice');m['variants']['B']['REFERENCE']['reference_control']='19MOSactualgeometrywithoutPEXRC,oldBfullRCunchanged';m['source_hashes']={str(p.relative_to(work/'inputs')):r.sha(p) for p in (work/'inputs').rglob('*') if p.is_file()};r.emit(work/'manifest.json',m)
 cs=[v.case(work,'B','GEOM_'+kind,'typical',27,3.3,variant='REFERENCE',dc_bit=1,startup={'kind':kind,'stop_s':100e-6,'maxstep_s':10e-9}) for kind in ['ramp','loadstep']]
 r.emit(work/'plan.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs,'hypothesis':'Isolate19MOSextractedR/C effect onslowstartup/loadstep; nohardwarechangeclaimed','source_sha256':r.sha(__file__)})
 rows=[]
 for c in cs:
  row=analyze(work,c,r.run_case(work,c));rows.append(row);print(json.dumps(row),flush=True)
 r.emit(r.EVIDENCE/'geometry-control-r1.json',{'rows':rows})
if __name__=='__main__':main()
