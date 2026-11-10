#!/usr/bin/env python3
"""Independent identity, accounting, geometry and holdout checks for this stage."""
from pathlib import Path
import hashlib
import json
import math
import re

ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/ab-improvement-20261111'
BUILD=ROOT/'build/ab-improvement-20261111/VCSEL'


def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    checks=[]
    def check(name,passed,detail=None):checks.append(dict(name=name,passed=bool(passed),detail=detail))
    results=sorted(BUILD.glob('*/DC-L*/result.json'))+sorted(BUILD.glob('*/net*/result.json'))+sorted(BUILD.glob('*/holdout*/result.json'))
    errors=[];counts={'DC':0,'development_frames':0,'holdout_frames':0}
    for p in results:
        folder=p.parent;r=read(p);m=read(folder/'manifest.json')
        mode='DC' if folder.name.startswith('DC') else ('holdout_frames' if folder.name.startswith('holdout') else 'development_frames')
        counts[mode]+=1
        if not r['simulation_ok'] or r['exit_code']!=0:errors.append(str(p)+' solver')
        if sha(folder/'testbench.spice')!=m['deck_sha256']:errors.append(str(p)+' deck')
        if sha(folder/'stimulus.json')!=m['stimulus_sha256']:errors.append(str(p)+' stimulus')
        for name in ['driver.spice','vcsel.spice','design.ngspice','sm141064.ngspice']:
            if sha(folder/name)!=m['source_sha256'][name]:errors.append(str(p)+' '+name)
        driver={w[0]:w for line in (folder/'driver.spice').read_text().splitlines() if (w:=line.split()) and len(w)>5 and w[5] in ['nmos_3p3','pmos_3p3']}
        if len(driver)!=73 or len(m['devices'])!=73 or len(m['ports'])!=7:errors.append(str(p)+' inventory')
        for d in m['devices']:
            if driver[d['instance']][6:]!=d['parameters']:errors.append(str(p)+' geometry inventory')
        if mode=='DC':
            expected=(abs(r['error_percent'])<=1 and r['terminal_screen_pass'] and r['max_body_forward_V']<=.3)
            if r['DC_screen_pass']!=expected or not expected:errors.append(str(p)+' DC')
            continue
        a=read(folder/'analysis.json');f=a['pathways']['actual_graph_5GHzRX'];o=a['observed']
        expected=(f['train_errors']==f['errors']==0 and f['worst_signed_margin_uAeq']>=7.5 and f['one_sided_margin_UI']>=.37 and o['terminal_screen_pass'] and o['max_body_forward_V']<=.3 and o['within_calibrated_electrical_and_optical_current_range'])
        if a['combined_screen_pass']!=bool(expected):errors.append(str(p)+' combined')
        if f['validation_bits']!=4096 or not math.isclose(m['end_s']*m['net_Gbps']*1e9,4096,rel_tol=1e-12):errors.append(str(p)+' bit denominator')
        if sha(p)!=a['result_sha256']:errors.append(str(p)+' result identity')
        for key in ['positive','returned','net']:
            total=sum(row[key+'_J'] for row in r['energy_by_port'].values())
            if not math.isclose(total*1e12/4096,a['source_energy_pJ_per_attempted_net_bit'][key],abs_tol=1e-12):errors.append(str(p)+' energy '+key)
        if not r['waveform']['roundtrip_verified']:errors.append(str(p)+' raw compression')
    check('native_case_identity_geometry_and_accounting',not errors,dict(counts=counts,errors=errors))
    check('expected_case_count',counts=={'DC':6,'development_frames':7,'holdout_frames':1},counts)
    hold=read(EV/'vcsel-holdout.json');selected=BUILD/'vc-atten50-steer20/net6.4-edge20-s40';folder=ROOT/hold['source_case']
    sanitize=lambda s:re.sub(r'(?m)^(VD|VDB) (d_src|db_src) 0 PWL\([^)]*\)',r'\1 \2 0 PWL(DATA)',s)
    check('holdout_changes_only_two_data_PWL_sources',sanitize((selected/'testbench.spice').read_text())==sanitize((folder/'testbench.spice').read_text()))
    check('holdout_keeps_identical_driver',sha(selected/'driver.spice')==sha(folder/'driver.spice')==hold['driver_sha256'])
    protocol=read(EV/'holdout-protocol.json');state=protocol['baseline_seed']
    for _ in range(protocol['phase_offset_in_PRBS15_period_bits']):state=((state<<1)&0x7fff)|(((state>>14)^(state>>13))&1)
    check('predeclared_nonoverlapping_PRBS_phase',state==protocol['holdout_seed']==read(folder/'stimulus.json')['seed'] and 4736<=protocol['phase_offset_in_PRBS15_period_bits']<=32767-4736)
    check('holdout_source_capture',sha(folder/'execution-source.py')==read(folder/'manifest.json')['execution_source_sha256'])
    causal=read(EV/'vcsel-causal-comparison.json');hs=causal['halfstep_control']
    check('halfstep_conclusion_and_numeric_agreement',hs['identical_pass'] and hs['identical_errors'] and abs(hs['timing_delta_ps'])<.1 and abs(hs['amplitude_delta_uAeq'])<.02 and abs(hs['energy_relative_delta_percent'])<.01,hs)
    regression=read(BUILD/'vc-atten50-steer20/net4.8-edge20-s40/analysis.json')
    check('old_passing_rate_regression',regression['combined_screen_pass'])
    check('heldout_frame_passes_without_retuning',hold['combined_screen_pass'] and hold['no_post_holdout_circuit_or_threshold_retuning'])
    evidence=[EV/n for n in ['vcsel-improvement.json','vcsel-causal-comparison.json','vcsel-holdout.json','holdout-protocol.json']]
    out=dict(schema='vcsel-improvement-independent-checks-v1',passed=all(x['passed'] for x in checks),checks=checks,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in evidence+[Path(__file__).resolve()]},
        scope='Repository identity/accounting and fixed nominal circuit simulations. Does not establish hardware BER, PVT/startup reliability, new layout/PEX or production qualification.')
    (EV/'vcsel-validation.json').write_text(json.dumps(out,indent=2)+'\n')
    print('VCSEL validation',out['passed'],counts)
    assert out['passed']

if __name__=='__main__':main()
