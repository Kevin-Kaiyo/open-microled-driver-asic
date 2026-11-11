#!/usr/bin/env python3
"""Freeze circuit, then apply the predeclared nonoverlapping PRBS15 window."""
import argparse
import copy
import re
import shutil
from micro_engine import ROOT, BUILD, emit, read, sha, module, verify, run_case
from micro_candidates import candidate

def run(name,rate):
    protocol_path=ROOT/'evidence/driver-methods-20261111/micro-protocol.json'
    protocol=read(protocol_path)
    source=BUILD/name;m=verify(source)
    source_case=source/'cases'/f'TT-net{rate:g}-C200-S40'
    assert read(source_case/'result.json')['analysis']['combined_screen_pass']
    for level in [0,1]:assert read(source/'cases'/f'DC-L{level}/result.json')['DC_screen_pass']
    target=BUILD/(name+'-holdout4c2d')
    if not target.exists():
        target.mkdir()
        for d in ['inputs','execution-sources']:shutil.copytree(source/d,target/d)
        gen=module(ROOT/'scripts/three_gbps_experiment/vcsel_driver_run.py','methods_holdout_generator')
        rx=module(source/'execution-sources/receiver_equal_latency_v2.py','methods_holdout_receiver')
        emit(target/'stimulus.json',gen.seeded_stimulus(protocol['holdout_seed'],rx))
        new=copy.deepcopy(m);new['name']=target.name;new['stimulus_sha256']=sha(target/'stimulus.json')
        new['holdout_provenance']=dict(source_manifest_sha256=sha(source/'manifest.json'),source_result_sha256=sha(source_case/'result.json'),protocol_sha256=sha(protocol_path),no_retuning=True)
        emit(target/'manifest.json',new)
    r=run_case(target,rate=rate,timeout_s=1800,**candidate(name)['case_overrides'])
    folder=target/'cases'/f'TT-net{rate:g}-C200-S40'
    normalize=lambda s:re.sub(r'(?m)^VD[01] data[01]_src 0 .*$', '<data source>',s)
    assert normalize((folder/'testbench.spice').read_text())==normalize((source_case/'testbench.spice').read_text())
    record=dict(candidate=name,rate_Gbps=rate,only_data_sources_changed=True,result_sha256=sha(folder/'result.json'),analysis=r.get('analysis'),protocol=protocol,source_result_sha256=sha(source_case/'result.json'))
    emit(ROOT/f'evidence/driver-methods-20261111/{name}-holdout-net{rate:g}.json',record)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--rate',required=True,type=float);a=p.parse_args();run(a.name,a.rate)
