#!/usr/bin/env python3
"""Restore only frozen inputs into a new work directory and rerun one DC case."""
from pathlib import Path
import argparse,datetime,json,shutil
import run as r
import validate as v
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source-work',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--smoke-dc',action='store_true',required=True);a=ap.parse_args()
 source=a.source_work.resolve();out=a.out.resolve();assert out.is_relative_to(r.BUILD.resolve()),'Output must stay in owned build/nrz-reference-v2';assert not out.exists(),'Refuse to overwrite a work directory'
 original=v.verify(source);cases=[c for p in source.glob('plan-*.json') for c in json.loads(p.read_text())['cases'] if c['kind']=='DC_TT' and c.get('dc_bit')==1];assert len(cases)==1
 c=cases[0];oldresult=source/'cases'/c['name']/'result.json';oldanalysis=oldresult.with_name('analysis.json');reference=json.loads(oldanalysis.read_text())['row']
 expected=json.loads(oldresult.read_text());runner_path=r.ROOT/expected['runner_source'];assert r.sha(runner_path)==expected['runner_source_sha256']
 frozen=r.module(runner_path,'frozen_reproduction_runner');frozen.ROOT=r.ROOT;frozen.BUILD=out;frozen.EVIDENCE=out/'evidence'
 out.mkdir(parents=True);shutil.copytree(source/'inputs',out/'inputs');shutil.copy2(source/'stimulus.json',out/'stimulus.json')
 m=dict(original);m['reproduction']={'created':datetime.datetime.now().isoformat(),'source_work':r.rel(source),'parent_manifest_sha256':r.sha(source/'manifest.json'),'copied':'inputs+stimulus only; no oldcases/raw'};r.emit(out/'manifest.json',m)
 r.emit(out/'plan-reproduction.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':[c],'source_sha256':r.sha(__file__)})
 result=frozen.run_case(out,c);row=v.analyze(out,result);difference=row.get('LED_current_A',0)-reference['LED_current_A'];passed=result['simulation_ok'] and row['analysis_ok'] and abs(difference)<1e-12
 receipt={'source_manifest_sha256':r.sha(source/'manifest.json'),'new_manifest_sha256':r.sha(out/'manifest.json'),'copied_files':len(original['source_hashes'])+1,'case':c,'source_analysis_sha256':r.sha(oldanalysis),'new_analysis_sha256':r.sha(out/'cases'/c['name']/'analysis.json'),'source_current_A':reference['LED_current_A'],'new_current_A':row.get('LED_current_A'),'current_difference_A':difference,'reproduction_passed':passed,'scope':'Samehost frozen-input DC smoke; not new fullmatrix/EDA/optical test','entry_source_sha256':r.sha(__file__)}
 r.emit(out/'reproduction-check.json',receipt);print(json.dumps(receipt,indent=2));assert passed
if __name__=='__main__':main()
