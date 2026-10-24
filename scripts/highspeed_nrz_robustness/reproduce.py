#!/usr/bin/env python3
"""Create a fresh run from this milestone's restored inputs, without old runs/raw."""
from pathlib import Path
import argparse,datetime,json,shutil
import run as r
import validate as v

def restore(source,target):
    source=Path(source).resolve();target=Path(target).resolve();m=v.verify(source)
    if target.exists() and any(target.iterdir()):raise ValueError('Reproduction destination must be new or empty; existing evidence is never overwritten')
    if (target/'cases').exists():raise ValueError('Existing case directory is forbidden')
    target.mkdir(parents=True,exist_ok=True)
    shutil.copytree(source/'inputs',target/'inputs');shutil.copy2(source/'stimulus.json',target/'stimulus.json')
    m=m|{'created':datetime.datetime.now().isoformat(),'reproduction_identity':{'source_manifest_sha256':r.sha(source/'manifest.json'),'source_manifest_locator':r.rel(source/'manifest.json'),'source_work':r.rel(source),'target_work':r.rel(target),'copied':['inputs/**','stimulus.json'],'not_copied':['cases/**','waveform.dat.gz','execution-sources/**'],'historical_baseline_and_physical_work_paths':'Historical provenance only, not required for simulation after restored inputs are verified.','new_deck_paths':'Rendered for this target workspace; original absolute deck paths are not reused.'}}
    r.emit(target/'manifest.json',m);v.verify(target)
    return m

def main():
    p=argparse.ArgumentParser();p.add_argument('--source-work',required=True);p.add_argument('--work',required=True);p.add_argument('--smoke-dc',action='store_true');a=p.parse_args()
    source=Path(a.source_work);source=source if source.is_absolute() else r.ROOT/source
    target=Path(a.work);target=target if target.is_absolute() else r.ROOT/target
    restore(source,target)
    result={'source_work':r.rel(source),'work':r.rel(target),'manifest_sha256':r.sha(target/'manifest.json'),'source_hashes_verified':True,'no_old_stage_or_raw_required':True}
    if a.smoke_dc:
        c=v.case(target,'A','restored_inputs_DC','ff',-40,3.65,dc_bit=1)
        r.emit(target/'plan-smoke-dc.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':[c]})
        row=v.analyze(target,r.run_case(target,c));result['smoke_row']=row
        if not row['analysis_ok']:raise RuntimeError('Restored-input DC smoke failed')
        v.summarize(target)
    r.emit(target/'reproduction-check.json',result);print(json.dumps(result))
if __name__=='__main__':main()
