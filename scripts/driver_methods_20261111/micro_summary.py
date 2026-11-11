#!/usr/bin/env python3
"""Compact derived evidence; raw/native outcomes remain under build/."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/driver-methods-20261111'
OUT=ROOT/'evidence/driver-methods-20261111'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def row(p,baseline=False):
    r=json.loads(p.read_text());case=r['case'];m=r.get('metrics',{});a=r.get('analysis',{});rx=a.get('full_receiver',{});el=a.get('electrical_receiver',{})
    result=dict(candidate=p.parents[2].name, baseline=baseline, route=case['route'],case=case,
        result=str(p.relative_to(ROOT)),result_sha256=sha(p),manifest_sha256=r['manifest_sha256'],engine_sha256=r['engine_sha256'],deck_sha256=r['deck_sha256'],
        simulation_ok=r['simulation_ok'],analysis_error=r.get('analysis_error'),raw_sha256=r.get('raw_sha256'),gzip_sha256=r.get('gzip_sha256'))
    if case.get('kind')=='dc':
        result.update(kind='dc',pass_screen=r.get('DC_screen_pass'),current_uA=m.get('i_led_A',0)*1e6,error_percent=m.get('current_error_percent'),power_mW=m.get('DC_power_W',0)*1e3,terminal_pass=m.get('device_voltage_passed'),body_forward_V=m.get('max_body_forward_V'))
    else:
        result.update(kind='transient',pass_screen=a.get('combined_screen_pass'),full_receiver=rx,electrical_receiver=el,
            energy_pJ=a.get('energy_pJ_per_attempted_payload_bit'),port_energy_pJ={k:{q:v[q+'_J']*1e12/4096 for q in ['positive','returned','net']} for k,v in m.get('energy',{}).items()},
            mean_current_uA=m.get('mean_LED_current_A',0)*1e6,current_range_uA=a.get('current_range_uA'),
            terminal_pass=a.get('terminal_screen_pass'),body_forward_V=a.get('max_body_forward_V'),body_pass=a.get('body_screen_pass'),static_domain_pass=a.get('static_IV_domain_pass'))
    return result

def main():
    rows=[]
    for name in ['a-rin1wide-core03-matched','B_wide_ff31p275']:
        for p in sorted((ROOT/'build/ab-improvement-20261111'/name/'cases').glob('*/result.json')):
            if json.loads(p.read_text())['case']['net_rate_Gbps'] in [.8,1.2,1.6,1.8,2.,2.4,3.2]:rows.append(row(p,True))
    for p in sorted(BUILD.glob('[AB]_*/cases/*/result.json')):rows.append(row(p))
    def transient(name,rate,steps=40):
        return next((r for r in rows if r['candidate']==name and r['kind']=='transient' and r['case']['net_rate_Gbps']==rate and r['case']['steps_per_symbol']==steps),None)
    comparisons=[]
    for new,old in [('A_rcff31p275','a-rin1wide-core03-matched'),('B_vin3p3_dummy50k_control','B_wide_ff31p275'),('B_vin3p3_dummy27p6k','B_wide_ff31p275'),('B_vin3p3_dummy27p6k','B_vin3p3_dummy50k_control')]:
        a=transient(new,1.6);b=transient(old,1.6)
        if a and b:
            comparisons.append(dict(new_candidate=new,baseline_candidate=old,rate_Gbps=1.6,new_result_sha256=a['result_sha256'],baseline_result_sha256=b['result_sha256'],energy_positive_percent=(a['energy_pJ']['positive']/b['energy_pJ']['positive']-1)*100,timing_delta_ps=a['full_receiver']['one_sided_margin_ps']-b['full_receiver']['one_sided_margin_ps'],amplitude_delta_uAeq=a['full_receiver']['worst_signed_margin_uAeq']-b['full_receiver']['worst_signed_margin_uAeq'],mean_current_delta_uA=a['mean_current_uA']-b['mean_current_uA']))
    half_steps=[]
    for r in rows:
        if r['baseline'] or r['kind']!='transient' or r['case']['steps_per_symbol']!=80:continue
        b=transient(r['candidate'],r['case']['net_rate_Gbps'])
        if b:
            half_steps.append(dict(candidate=r['candidate'],rate_Gbps=r['case']['net_rate_Gbps'],S40_result_sha256=b['result_sha256'],S80_result_sha256=r['result_sha256'],same_pass_outcome=b['pass_screen']==r['pass_screen'],amplitude_delta_uAeq=r['full_receiver']['worst_signed_margin_uAeq']-b['full_receiver']['worst_signed_margin_uAeq'],timing_delta_ps=r['full_receiver']['one_sided_margin_ps']-b['full_receiver']['one_sided_margin_ps'],energy_positive_delta_percent=(r['energy_pJ']['positive']/b['energy_pJ']['positive']-1)*100))
    data=dict(schema='microled-driver-methods-derived-v1',protocol=json.loads((OUT/'micro-protocol.json').read_text()),
        source_script_sha256=sha(Path(__file__)),records=rows,
        same_rate_comparisons=comparisons,half_step_checks=half_steps,
        derived_causal_evidence=dict(path=str((OUT/'micro-causal.json').relative_to(ROOT)),sha256=sha(OUT/'micro-causal.json')) if (OUT/'micro-causal.json').exists() else None,
        limitations=['Schematic transistor simulation; new physical layout, DRC, LVS and PEX not completed.',
                     'Synthetic 20um load and 200ps optical/1GHz RX held fixed; no device bandwidth claim.',
                     'Failed-case pJ denominates attempted payload, not successfully transmitted useful bits.',
                     'No random noise, measured BER, startup/disable, PVT or production qualification.',
                     'Positive seven-port supply energy reported; returned energy is separately retained and no perfect converter recovery is assumed.'])
    OUT.mkdir(exist_ok=True,parents=True);(OUT/'micro-summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    columns=['candidate','baseline','kind','route','rate_Gbps','level','steps','vin_V','passed','Epositive_pJ','Enet_pJ','errors','amplitude_uAeq','timing_ps','timing_UI','current_uA','body_V']
    with (OUT/'micro-summary.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
        for x in rows:
            c=x['case'];rx=x.get('full_receiver',{});e=x.get('energy_pJ',{})
            writer.writerow(dict(candidate=x['candidate'],baseline=x['baseline'],kind=x['kind'],route=x['route'],rate_Gbps=c['net_rate_Gbps'],level=c.get('level'),steps=c['steps_per_symbol'],vin_V=c.get('vin_V',5),passed=x['pass_screen'],Epositive_pJ=e.get('positive'),Enet_pJ=e.get('net'),errors=rx.get('errors'),amplitude_uAeq=rx.get('worst_signed_margin_uAeq'),timing_ps=rx.get('one_sided_margin_ps'),timing_UI=rx.get('one_sided_margin_bit_UI'),current_uA=x.get('current_uA'),body_V=x.get('body_forward_V')))

if __name__=='__main__':main()
