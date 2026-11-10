#!/usr/bin/env python3
"""Predeclared PRBS-window holdout; fixed selected VCSEL circuit, no retuning."""
from pathlib import Path
import copy
import hashlib
import json
import re
import shutil
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
EXECUTION_SOURCE=Path(__file__).read_bytes()
EXECUTION_SHA=hashlib.sha256(EXECUTION_SOURCE).hexdigest()
sys.path.insert(0,str(ROOT/'scripts/highspeed_workbench_20261110'))
import vcsel_x10_run as run
import vcsel_x10_analyze as analysis
PROTOCOL=ROOT/'evidence/ab-improvement-20261111/holdout-protocol.json'
SELECTED=ROOT/'build/ab-improvement-20261111/VCSEL/vc-atten50-steer20/net6.4-edge20-s40'
FOLDER=SELECTED.parent/'holdout-seed317e-net6.4-s40'
OUT=ROOT/'evidence/ab-improvement-20261111/vcsel-holdout.json'


def emit(p,x):
    Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def prepare():
    protocol=run.read_json(PROTOCOL)
    assert protocol['holdout_seed']==0x317e and protocol['baseline_seed']==0x5ace
    assert protocol['frame_bits']==4736 and protocol['payload_validation_bits']==4096
    phase=protocol['phase_offset_in_PRBS15_period_bits']
    state=protocol['baseline_seed']
    for _ in range(phase):state=((state<<1)&0x7fff)|(((state>>14)^(state>>13))&1)
    assert state==protocol['holdout_seed']
    assert 4736<=phase and phase+4736<=32767,'Holdout period window overlaps baseline/wrap'
    baseline=run.read_json(SELECTED/'manifest.json');solved=run.read_json(SELECTED/'result.json')
    selected=run.read_json(SELECTED/'analysis.json')
    assert selected['combined_screen_pass'] and baseline['net_Gbps']==6.4 and baseline['steps_per_UI']==40
    assert run.sha(SELECTED/'result.json')==selected['result_sha256']
    assert run.sha(SELECTED/'testbench.spice')==baseline['deck_sha256']
    for file in ['design.ngspice','sm141064.ngspice','vcsel.spice','driver.spice']:
        assert run.sha(SELECTED/file)==baseline['source_sha256'][file]
    if FOLDER.exists():
        m=run.read_json(FOLDER/'manifest.json')
        assert m['holdout_protocol_sha256']==run.sha(PROTOCOL)
        assert m['selected_case_manifest_sha256']==run.sha(SELECTED/'manifest.json')
        assert run.sha(FOLDER/'testbench.spice')==m['deck_sha256']
        assert run.sha(FOLDER/'stimulus.json')==m['stimulus_sha256']
        for file in ['design.ngspice','sm141064.ngspice','vcsel.spice','driver.spice']:
            assert run.sha(FOLDER/file)==m['source_sha256'][file]
        return m
    FOLDER.mkdir(parents=True,exist_ok=False)
    for file in ['design.ngspice','sm141064.ngspice','vcsel.spice','driver.spice']:
        shutil.copy2(SELECTED/file,FOLDER/file)
    legacy=run.module(run.LEGACY,'vcsel_holdout_seed_generator')
    rx0=run.module(ROOT/'scripts/fair_driver_v1/receiver_equal_latency_v2.py','vcsel_holdout_stimulus')
    st=legacy.seeded_stimulus(protocol['holdout_seed'],rx0)
    assert len(st['bits'])==4736 and st['seed']==0x317e
    emit(FOLDER/'stimulus.json',st)
    deck=(SELECTED/'testbench.spice').read_text();ui=baseline['end_s']/4736
    for port,node,bits in [('VD','d_src',st['bits']),('VDB','db_src',[1-b for b in st['bits']])]:
        deck,count=re.subn(rf'(?m)^{port} {node} 0 PWL\([^)]*\)',f'{port} {node} 0 '+legacy.pwl(bits,ui,3.3,20e-12),deck)
        assert count==1
    (FOLDER/'testbench.spice').write_text(deck)
    (FOLDER/'execution-source.py').write_bytes(EXECUTION_SOURCE)
    helpers=[Path(run.__file__),Path(analysis.__file__),run.LEGACY,run.ENERGY,analysis.OPTO_PATH,analysis.RX_PATH]
    helper_records={}
    helper_dir=FOLDER/'execution-sources';helper_dir.mkdir()
    for i,p in enumerate(helpers):
        name=f'{i}-{p.name}';shutil.copy2(p,helper_dir/name)
        helper_records[str(p.relative_to(ROOT))]={'copy':name,'sha256':run.sha(p)}
    m=copy.deepcopy(baseline)
    m.update(case=FOLDER.name,holdout=True,holdout_seed=st['seed'],holdout_protocol_sha256=run.sha(PROTOCOL),
        selected_case_manifest_sha256=run.sha(SELECTED/'manifest.json'),selected_case_result_sha256=run.sha(SELECTED/'result.json'),
        original_stimulus_sha256=baseline['stimulus_sha256'],stimulus_sha256=run.sha(FOLDER/'stimulus.json'),
        deck_sha256=run.sha(FOLDER/'testbench.spice'),execution_source_sha256=EXECUTION_SHA,execution_helpers=helper_records,
        scope='Predeclared nonoverlapping PRBS15 window, fixed selected6.4G driver/load/RX. No circuit or threshold retuning; same training-only delay rule. Not random-independent BER or PVT qualification.')
    emit(FOLDER/'manifest.json',m);return m


def main():
    m=prepare()
    if not (FOLDER/'result.json').exists():run.solve(FOLDER,m)
    rx=run.module(analysis.RX_PATH,'vcsel_holdout_rx');opto=run.module(analysis.OPTO_PATH,'vcsel_holdout_opto')
    met,traces=analysis.analyze(FOLDER,rx,opto,False,128)
    obs=met['observed'];full=met['pathways']['actual_graph_5GHzRX']
    combined=bool(full['screen_pass'] and obs['terminal_screen_pass'] and obs['max_body_forward_V']<=.3 and obs['within_calibrated_electrical_and_optical_current_range'])
    met.update(candidate='vc-atten50-steer20',holdout_seed=m['holdout_seed'],holdout=True,
        combined_screen_pass=combined,DC_calibration_pass=True,result_sha256=run.sha(FOLDER/'result.json'),
        manifest_sha256=run.sha(FOLDER/'manifest.json'),wrapper_sha256=EXECUTION_SHA)
    emit(FOLDER/'analysis.json',met);emit(FOLDER/'excerpt.json',{k:v.tolist() for k,v in traces.items()})
    out=dict(schema='vcsel-predeclared-holdout-v1',candidate=met['candidate'],net_Gbps=6.4,steps_per_UI=40,
        seed=m['holdout_seed'],protocol=run.read_json(PROTOCOL),protocol_sha256=run.sha(PROTOCOL),
        combined_screen_pass=combined,full_receiver=full,observed=obs,
        energy_pJ_per_attempted_bit=met['source_energy_pJ_per_attempted_net_bit'],source_case=str(FOLDER.relative_to(ROOT)),
        source_analysis_sha256=run.sha(FOLDER/'analysis.json'),result_sha256=run.sha(FOLDER/'result.json'),
        deck_sha256=m['deck_sha256'],driver_sha256=m['source_sha256']['driver.spice'],stimulus_sha256=m['stimulus_sha256'],
        selected_case_driver_sha256=run.read_json(SELECTED/'manifest.json')['source_sha256']['driver.spice'],
        source_execution_sha256=EXECUTION_SHA,no_post_holdout_circuit_or_threshold_retuning=True,
        scope='Independent PRBS phase window held out from candidate selection. Same deterministic simulation contract; not physical BER, noise, PVT or complete PHY qualification.')
    assert out['driver_sha256']==out['selected_case_driver_sha256']
    emit(OUT,out)
    print('HOLDOUT',combined,full['errors'],full['worst_signed_margin_uAeq'],full['one_sided_margin_UI'],met['source_energy_pJ_per_attempted_net_bit']['positive'],flush=True)

if __name__=='__main__':main()
