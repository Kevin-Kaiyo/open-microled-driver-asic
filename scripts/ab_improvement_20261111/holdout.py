#!/usr/bin/env python3
"""Freeze a candidate, then test the predeclared nonoverlapping PRBS window."""
import argparse,copy,json,re,shutil,sys
from pathlib import Path
sys.dont_write_bytecode=True
from engine_checked import ROOT,BUILD,read,sha,emit,module,verify,run_case

def run(candidate,rate):
    protocol=read(ROOT/'evidence/ab-improvement-20261111/holdout-protocol.json')
    source=BUILD/candidate;m=verify(source)
    source_case=source/'cases'/f'TT-net{rate:g}-C200-S40'
    baseline=read(source_case/'result.json')
    assert baseline['analysis']['combined_screen_pass'],'Freeze a passing candidate before holdout'
    for level in [0,1]:assert read(source/'cases'/f'DC-L{level}'/'result.json')['DC_screen_pass']
    target=BUILD/(candidate+'-holdout317e')
    if not target.exists():
        target.mkdir()
        for name in ['inputs','execution-sources']:shutil.copytree(source/name,target/name)
        old=module(ROOT/'scripts/three_gbps_experiment/vcsel_driver_run.py','holdout_prbs')
        rx=module(source/'execution-sources/receiver_equal_latency_v2.py','holdout_frame')
        stimulus=old.seeded_stimulus(protocol['holdout_seed'],rx)
        emit(target/'stimulus.json',stimulus)
        new=copy.deepcopy(m);new['name']=target.name;new['stimulus_sha256']=sha(target/'stimulus.json')
        new['holdout_provenance']=dict(source_candidate=candidate,source_manifest_sha256=sha(source/'manifest.json'),
            source_result_sha256=sha(source_case/'result.json'),protocol_sha256=sha(ROOT/'evidence/ab-improvement-20261111/holdout-protocol.json'),
            hypothesis='Unseen development-frame window after frozen selection; no retuning to this result.')
        emit(target/'manifest.json',new)
    verify(target)
    result=run_case(target,rate=rate)
    folder=target/'cases'/f'TT-net{rate:g}-C200-S40'
    # For this NRZ frame only VD0 PWL changes; VD1 remains low.
    normalize=lambda s:re.sub(r'(?m)^VD[01] data[01]_src 0 .*$', '<data source>',s)
    assert normalize((folder/'testbench.spice').read_text())==normalize((source_case/'testbench.spice').read_text()),'Unexpected circuit/timing drift'
    record=dict(candidate=candidate,route=m['route'],rate_Gbps=rate,protocol=protocol,
        comparison_deck_only_data_sources_changed=True,identical_input_hashes=read(target/'manifest.json')['inputs']==m['inputs'],
        source_case=str(folder.relative_to(ROOT)),result_sha256=sha(folder/'result.json'),
        selected_source_result_sha256=sha(source_case/'result.json'),DC_reused_same_circuit=True,
        analysis=result.get('analysis'),simulation_ok=result['simulation_ok'],analysis_error=result.get('analysis_error'),
        scope='Nonoverlapping PRBS window, no random noise/BER/PVT claim; candidate not retuned after holdout.')
    emit(ROOT/f'evidence/ab-improvement-20261111/{m["route"].lower()}-holdout.json',record)
    print(json.dumps({'route':m['route'],'rate':rate,'analysis':record['analysis']},ensure_ascii=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('candidate');ap.add_argument('--rate',type=float,required=True);a=ap.parse_args();run(a.candidate,a.rate)
