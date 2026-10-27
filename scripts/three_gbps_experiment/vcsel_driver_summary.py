#!/usr/bin/env python3
"""Collect compact reproducible evidence; original waveforms remain in build."""
from pathlib import Path
import json, shutil
import numpy as np
from vcsel_driver_run import ROOT, BUILD, sha, emit, module

EV=ROOT/'evidence/three-gbps-experiment-20261027'


def exact_energy(work,m,r):
    helper=ROOT/'scripts/fair_driver_v1/run.py';legacy=module(helper,'vcsel_signed_energy')
    a=np.loadtxt(ROOT/r['waveform']['path'],skiprows=1);ix={s:i+1 for i,s in enumerate(m['expressions'])};t=a[:,0]
    port_nodes=dict(VLASER='laser_src',VDD='vdd_src',VREF='ref_src',VD='d_src',VDB='db_src')
    ledger={p:legacy.signed_integrals(t,-a[:,ix['v('+n+')']]*a[:,ix['i('+p+')']]) for p,n in port_nodes.items()}
    sums={k:sum(v[k] for v in ledger.values()) for k in ['positive_J','returned_J','net_J']}
    sums.update(positive_pJ_per_offered_payload_bit=sums['positive_J']/4096*1e12,net_pJ_per_offered_payload_bit=sums['net_J']/4096*1e12)
    delta=sums['positive_pJ_per_offered_payload_bit']-r['total_energy']['positive_pJ_per_offered_payload_bit']
    evidence=dict(method='Exact signed integral of piecewise-linear native port power, splitting every zero crossing; identical helper to fair-driver-v1',helper_sha256=sha(helper),waveform_sha256=r['waveform']['sha256'],energy_by_port=ledger,total_energy=sums,
                  initial_clipped_trapezoid_positive_pJ=r['total_energy']['positive_pJ_per_offered_payload_bit'],exact_minus_initial_positive_pJ=delta,relative_difference_ppm=delta/r['total_energy']['positive_pJ_per_offered_payload_bit']*1e6,
                  source_result_unchanged_sha256=sha(work/'result.json'))
    emit(work/'energy-exact.json',evidence)
    return evidence


def timing(work):
    m=json.loads((work/'manifest.json').read_text());r=json.loads((work/'result.json').read_text())
    a=np.loadtxt(ROOT/r['waveform']['path'],skiprows=1);t=a[:,0];current=a[:,1];ix={s:i+1 for i,s in enumerate(m['expressions'])}
    bits=json.loads((work/'stimulus.json').read_text())['bits'];ui=32/37/(m['args']['rate']*1e9)
    i0=json.loads((BUILD/'dc-final-TT-low/result.json').read_text())['current_mA']*1e-3
    i1=json.loads((BUILD/'dc-final-TT-high/result.json').read_text())['current_mA']*1e-3
    def cross(t,y,v,rising):
        ids=np.flatnonzero((y[:-1]<v)&(y[1:]>=v) if rising else (y[:-1]>v)&(y[1:]<=v))
        if not len(ids):return None
        k=ids[0];return float(t[k]+(t[k+1]-t[k])*(v-y[k])/(y[k+1]-y[k]))
    events=[]
    for k in range(578,4669):
        if not(bits[k-2]==bits[k-1] and bits[k-1]!=bits[k] and bits[k]==bits[k+1]==bits[k+2]):continue
        sel=(t>=k*ui)&(t<(k+1)*ui);tt=t[sel];yy=current[sel];rising=bits[k]==1
        levels=[.1,.5,.9] if rising else [.9,.5,.1]
        ct=[cross(tt,yy,i0+(i1-i0)*v,rising) for v in levels]
        gate=cross(tt,a[sel,ix['v(xdrv.gp)']],m['supply_V']/2,rising)
        if all(v is not None for v in ct):events.append(dict(bit=k,direction='rise' if rising else 'fall',current_10_90_ps=(ct[2]-ct[0])*1e12,current_50_delay_ps=(ct[1]-(k*ui+10e-12))*1e12,gate_50_delay_ps=None if gate is None else (gate-(k*ui+10e-12))*1e12))
    stats={}
    for d in ['rise','fall']:
        x=[e for e in events if e['direction']==d]
        stats[d]=dict(count=len(x))
        for key in ['current_10_90_ps','current_50_delay_ps','gate_50_delay_ps']:
            vals=[e[key] for e in x if e[key] is not None];stats[d][key]=dict(min=min(vals),median=float(np.median(vals)),max=max(vals))
    return dict(case=work.name,definition='Electrical conduction current10-90% of frozen TT DC endpoints; first directional crossings; previous2/following3identicalbits; input source50% atbit_boundary+10ps; all qualifying validation transitions',thresholds_A=[i0,i1],statistics=stats,events=events)


def main():
    EV.mkdir(parents=True,exist_ok=True);rows=[];dc=[];fail=[]
    for f in sorted(BUILD.glob('*/result.json')):
        r=json.loads(f.read_text());m=json.loads((f.parent/'manifest.json').read_text())
        if not r['simulation_ok']:fail.append(dict(case=f.parent.name,result=str(f.relative_to(ROOT)),exit_code=r['exit_code']));continue
        sequence_role=('nonoverlapping deterministic PRBS window confirmation' if f.parent.name=='frame-TT-3p2-nonoverlap1' else 'fresh-seed overlapping PRBS phase control; not independent holdout' if f.parent.name=='frame-TT-3p2-holdout1' else 'original PRBS frame')
        base=dict(case=f.parent.name,result=str(f.relative_to(ROOT)),result_sha256=sha(f),manifest_sha256=sha(f.parent/'manifest.json'),args=m['args'],stimulus_seed=json.loads((f.parent/'stimulus.json').read_text())['seed'],sequence_role=sequence_role,circuit_sha256=m['sources']['driver.spice'],model_sha256=m['sources']['vcsel.spice'])
        if m['args']['mode']=='dc':
            dc.append(dict(base,current_mA=r['current_mA'],reference_current_mA=r['reference_current_mA'],base_current_mA=r['base_current_mA'],tail_current_mA=r['tail_current_mA'],source_power_W=r['source_power_W'],device_screen_passed=r['device_screen_passed']));continue
        exact=exact_energy(f.parent,m,r)
        for ar in sorted(f.parent.glob('analysis-*/result.json')):
            s=json.loads(ar.read_text());rx=s['receiver'];p=json.loads((ar.parent/'plan.json').read_text())
            plotdst=EV/(f"vcsel-driver-{f.parent.name}-{p['label']}-plot-data.npz");shutil.copy2(ar.parent/'plot-data.npz',plotdst)
            rows.append(dict(base,analysis_label=p['label'],analysis=str(ar.relative_to(ROOT)),analysis_sha256=sha(ar),analysis_plan_sha256=sha(ar.parent/'plan.json'),plot_data=str(plotdst.relative_to(ROOT)),plot_data_sha256=sha(plotdst),
                receiver_version=p.get('receiver_version','v2'),net_rate_Gbps=m['args']['rate'],corner=m['args']['pvt'],optical_response=p['response'],rx_GHz=p['rx_GHz'],grid_ps=p['grid_ps'],errors=rx['validation']['bit_errors'],validation_bits=4096,
                min_signed_margin_uAeq=rx['validation']['decision_distance_min_uA'],time_margin_ps=rx['horizontal_margin']['min_ps'],delay_ps=rx['sampling']['delay_s']*1e12,
                current_range_mA=r['current_range_mA'],device_screen_passed=r['device_screen_passed'],
                maximum_device_terminal_V=max(max(d['max_abs_terminal_V'].values()) for d in r['stress']),maximum_body_forward_V=max(d['max_body_forward_V'] for d in r['stress']),
                energy=exact['total_energy'],energy_by_port=exact['energy_by_port'],energy_method='exact piecewise-linear native port-power zero crossings',energy_exact_minus_initial_positive_pJ=exact['exact_minus_initial_positive_pJ'],energy_relative_difference_ppm=exact['relative_difference_ppm'],domain=s['domain'],quantities=s['quantities'],checks=rx['checks'],combined_screen_passed=s['combined_screen_passed']))
    timing_data=timing(BUILD/'frame-TT-0p8-r1');emit(EV/'vcsel-driver-electrical-timing.json',timing_data)
    manifest=json.loads((BUILD/'frame-TT-3p2-r1/manifest.json').read_text())
    emit(EV/'vcsel-driver-device-inventory.json',dict(devices=manifest['devices'],args=manifest['args'],source_sha256=manifest['sources']['driver.spice'],source='analog/circuits/vcsel_research_20261027/vcsel_bias_mod.spice',MOS_count=13,
        topology='resistor-diode reference + baseline sink + tail sink + differential steering pair +2x two-stage CMOS buffer',model_names=['nmos_3p3','pmos_3p3'],model_pin='analog/models/pdk-lock.json',junction_geometry='W*.44um and2*(W+.44um) schematic estimate'))
    evidence=dict(status='bounded schematic milestone; original v2 TT3.2 fails100ps; separately frozen v3 joint-objective diagnostic passes TT conditional screens; SS and FF fail combined screens',
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'analog/circuits/vcsel_research_20261027/vcsel_bias_mod.spice',ROOT/'scripts/three_gbps_experiment/vcsel_driver_run.py',ROOT/'scripts/three_gbps_experiment/vcsel_driver_analyze.py',ROOT/'scripts/three_gbps_experiment/vcsel_driver_receiver_v3.py',ROOT/'analog/circuits/vcsel_research_20261027/receiver-feasibility-v3-diagnostic.json',Path(__file__)]},
        calibration='Only TT DC calibrated once: RREF6.9k, WBASE60um/L1um,WTAIL84um/L1um. No corner or transient retuning; nominal external resistor, +/-1% controls separate from MOS process corners.',
        startup='All normal frames begin at DC operating point; not a startup or protection qualification.',
        power_scope=manifest['power_scope'],frame='4736transmittedbits/4096payload,eta32/37;3.2Gnet implies3.7Gbaud;failedcaseenergy is per offered payloadbit',
        receiver_scope='Original v2 amplitude-first results retained. Independently frozen v3 diagnostic maximizes min(training_signedmargin/7.5uAeq,training_time/100ps), earliest exact tie; all1601delays,448train+64guard, no validation leakage. Same calibrated affine P(3mA)/P(7mA), thresholds and gates. No calibrated opticalcoupling/photodiode/noise or physicalRX power.',
        v3_method_selection_limit='Post-hoc diagnostic motivated by v2 results; same4096validationbits reused, so not independent end-to-end confirmation. Within each v3 run validation is not used to choose delay. Inherited amplitude_plateau_tolerance_uA metadata is unused in v3.',
        new_frame_confirmation=dict(phase_control='frame-TT-3p2-holdout1/seed0x1ACE has1582validationbits overlapping original PRBS period and must not be called independent',nonoverlap='frame-TT-3p2-nonoverlap1/seed0x57AE offsets8192bits, frame andvalidation intersections0; frozen method, unchanged circuit/models. Same deterministicPRBS period, not random BER trial',contract='analog/circuits/vcsel_research_20261027/holdout-nonoverlap-contract.json',contract_sha256=sha(ROOT/'analog/circuits/vcsel_research_20261027/holdout-nonoverlap-contract.json')),
        boundary='Figure-constrained25C VCSEL static and magnitude-only dynamic proxy; Cj/package assumptions; GF180 transistor model subset only; no fullphysicalPDK, layout, DRC/LVS/PEX, silicon, opticalmeasurement or BERqualification.',
        dc=dc,cases=rows,failed_executions=fail,electrical_timing=str((EV/'vcsel-driver-electrical-timing.json').relative_to(ROOT)),
        postprocess_recovery='TT andSS frame result serialization initially failed after completed ngspice; preserved waveforms recovered without rerun. Four resistor DC records recovered after summarizer scope error; source/log hashes retained.')
    emit(EV/'vcsel-driver-summary.json',evidence);print(json.dumps(dict(dc=len(dc),analyses=len(rows),failures=fail,timing=timing_data['statistics']),ensure_ascii=False))


if __name__=='__main__':main()
