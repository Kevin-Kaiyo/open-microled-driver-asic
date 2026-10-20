#!/usr/bin/env python3
"""Reuse completed traces only when their complete electrical inputs match."""
from pathlib import Path
import argparse
import json
import shutil
from run import ROOT, sha, rel, emit


def reuse(source, target):
    old=json.loads((source/'manifest.json').read_text())
    new=json.loads((target/'manifest.json').read_text())
    checks={}
    for key in ['common','route_a_rails']:
        checks[key]=old[key]==new[key]
    for name in ['legacy/run.py','legacy/analyze.py','legacy/metrics.py','led.spice',
                 'pdk/design.ngspice','pdk/sm141064.ngspice']:
        checks[name]=sha(source/'inputs'/name)==sha(target/'inputs'/name)
    checks['stimulus']=sha(source/'stimulus.json')==sha(target/'stimulus.json')
    if not all(checks.values()):raise ValueError('electrical contract changed; cannot reuse')
    records=[]
    for path in sorted((source/'cases').glob('*/result.json')):
        prior=json.loads(path.read_text());case=prior['case'];route=case['route'];variant=case['variant']
        if variant=='SCHEM' or not prior['simulation_ok']:continue
        dst=target/'cases'/case['name']
        if (dst/'result.json').exists():continue
        oldcore=source/'inputs'/old['variants'][route][variant]['path']
        newcore=target/'inputs'/new['variants'][route][variant]['path']
        if sha(oldcore)!=sha(newcore):continue
        if sha(ROOT/prior['waveform'])!=prior['waveform_sha256']:raise ValueError('waveform changed')
        if sha(path.parent/'testbench.spice')!=prior['deck_sha256']:raise ValueError('deck changed')
        result=prior|{'reuse':{'original_result':rel(path),'original_result_sha256':sha(path),
                             'rerun':False,'reason':'identical core bytes, model bytes, stimulus and frozen common contract',
                             'core_sha256':sha(newcore),'electrical_input_checks':checks}}
        dst.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path.parent/'testbench.spice',dst/'testbench.spice')
        shutil.copy2(path.parent/'case.json',dst/'case.json')
        emit(dst/'result.json',result)
        records.append({'case':case['name'],'waveform':prior['waveform'],'source_result':rel(path)})
    report={'from':rel(source),'to':rel(target),'input_checks':checks,'reused':records,
            'raw_bytes_copied':0,'rejected_and_interrupted_cases_retained_at_source':True}
    emit(target/'reused-cases.json',report)
    print(json.dumps({'reused':len(records),'from':rel(source),'to':rel(target)},indent=2))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--target',required=True)
    args=p.parse_args();reuse((ROOT/args.source).resolve(),(ROOT/args.target).resolve())
