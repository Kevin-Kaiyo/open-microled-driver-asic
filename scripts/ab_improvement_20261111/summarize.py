#!/usr/bin/env python3
"""Collect immutable completed experiments; failed screening is retained."""
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/ab-improvement-20261111'
EV=ROOT/'evidence/ab-improvement-20261111'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def read(p):return json.loads(p.read_text())

def main():
    rows=[];dc=[];solve_failures=[];candidates={}
    for p in sorted(BUILD.glob('*/cases/*/result.json')):
        r=read(p);work=p.parents[2];manifest=read(work/'manifest.json');case=r['case']
        if 'holdout_provenance' in manifest:continue
        candidates[work.name]={k:manifest[k] for k in ['route','parameters','notes']}
        source=dict(candidate=work.name,route=case['route'],case=case,source_case=str(p.parent.relative_to(ROOT)),
                    result_sha256=sha(p),manifest_sha256=sha(work/'manifest.json'),
                    deck_sha256=r['deck_sha256'],waveform_gzip_sha256=r.get('gzip_sha256'),
                    waveform_raw_sha256=r.get('raw_sha256'))
        if not r['simulation_ok'] or r.get('analysis_error'):
            solve_failures.append({**source,'simulation_ok':r['simulation_ok'],'analysis_error':r.get('analysis_error'),'exit_code':r['exit_code']});continue
        m=r['metrics']
        if case.get('kind')=='dc':
            dc.append({**source,'current_uA':m['i_led_A']*1e6,'target_uA':m['target_A']*1e6,
                       'error_percent':m['current_error_percent'],'DC_screen_pass':r['DC_screen_pass'],
                       'terminal_screen_pass':m['device_voltage_passed'],'max_body_forward_V':m['max_body_forward_V'],
                       'power_mW':m['DC_power_W']*1e3})
        else:
            assert sha(p.parent/'waveform.dat.gz')==r['gzip_sha256']
            rows.append({**source,**r['analysis'],'mean_LED_current_uA':m['mean_LED_current_A']*1e6,
                         'source_energy_by_port':m['energy'],'observables':r.get('observables'),
                         'stress':m['stress'],'MOS_count':len(r['metadata']['devices']),
                         'solver_elapsed_s':r['simulation_elapsed_s']})
    envelopes=[]
    for name,c in candidates.items():
        # Match DC parameter overrides to each transient before claiming the contract.
        for row in [r for r in rows if r['candidate']==name]:
            case=row['case'];parameters=case.get('parameters',{})
            matches=[r for r in dc if r['candidate']==name and r['case'].get('parameters',{})==parameters
                     and all(r['case'].get(k)==case.get(k) for k in ['corner','temp_C','vdd_V','vin_V','vled_V','reference_error','res_corner'])]
            row['matched_DC_levels_pass']=all(any(d['case']['level']==level and d['DC_screen_pass'] for d in matches) for level in [0,1])
            row['joint_screen_pass']=row['combined_screen_pass'] and row['matched_DC_levels_pass']
        group=sorted([r for r in rows if r['candidate']==name and r['case']['steps_per_symbol']==40
                      and abs(r['case']['led_cap_F']-200e-15)<1e-25 and r['case']['corner']=='typical'
                      and r['case']['temp_C']==27 and r['case']['vdd_V']==3.3],key=lambda x:x['case']['net_rate_Gbps'])
        passed=[r['case']['net_rate_Gbps'] for r in group if r['joint_screen_pass']]
        highest=max(passed) if passed else None
        fails=[r['case']['net_rate_Gbps'] for r in group if highest is not None and r['case']['net_rate_Gbps']>highest and not r['joint_screen_pass']]
        envelopes.append(dict(candidate=name,route=c['route'],tested_rates_Gbps=[r['case']['net_rate_Gbps'] for r in group],
                              highest_passing_tested_Gbps=highest,next_failing_tested_Gbps=min(fails) if fails else None))
    convergence=[]
    for fine in [r for r in rows if r['case']['steps_per_symbol']==80]:
        match=[r for r in rows if r['candidate']==fine['candidate'] and r['case']['steps_per_symbol']==40
               and all(r['case'].get(k)==fine['case'].get(k) for k in ['net_rate_Gbps','led_cap_F','corner','temp_C','vdd_V','parameters'])]
        if len(match)!=1:continue
        coarse=match[0];a,b=coarse['full_receiver'],fine['full_receiver']
        convergence.append(dict(candidate=fine['candidate'],rate_Gbps=fine['case']['net_rate_Gbps'],
            coarse_result_sha256=coarse['result_sha256'],fine_result_sha256=fine['result_sha256'],
            same_decision=coarse['joint_screen_pass']==fine['joint_screen_pass'],errors=[a['errors'],b['errors']],
            amplitude_delta_uAeq=b['worst_signed_margin_uAeq']-a['worst_signed_margin_uAeq'],
            timing_delta_ps=b['one_sided_margin_ps']-a['one_sided_margin_ps'],
            energy_positive_relative_percent=100*(fine['energy_pJ_per_attempted_payload_bit']['positive']/coarse['energy_pJ_per_attempted_payload_bit']['positive']-1)))
    obj=dict(schema='ab-improvement-20261111',candidates=candidates,DC=dc,transient=rows,
             envelopes=envelopes,half_step_controls=convergence,solver_failures=solve_failures,
             scope='Fixed-load schematic experiments. Nominal envelope only; no new physical verification, BER or optical measurement.')
    EV.mkdir(parents=True,exist_ok=True);(EV/'summary.json').write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps(dict(DC=len(dc),transient=len(rows),solver_failures=len(solve_failures),envelopes=envelopes),ensure_ascii=False))

if __name__=='__main__':main()
