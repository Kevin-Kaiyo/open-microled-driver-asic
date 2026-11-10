#!/usr/bin/env python3
"""Fixed-frame rate/load envelope, same training-only receiver for A/B/C.

Pass screens are research criteria, not standardized BER qualification.
0.37 line-bit UI equals 100 ps at the historical 3.2 Gb/s net operating point.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/highspeed_workbench_20261110'))
from replay import module, read_json, sha
import vcsel_x10_analyze as vca
from sweep import BUILD, MICRO, OLD, emit

EV = ROOT / 'evidence/blue-emitter-speed-review-20261110'
RXPATH = ROOT / 'scripts/fair_driver_v1/receiver_equal_latency_v2.py'
DYNAMIC = ROOT / 'scripts/microled_dynamic_v1/analyze.py'
ETA = 4096/4736


def receive(t, signal_uA, stimulus, route, rate, rx):
    """No validation-label fitting, uniform time allowance across modulation."""
    width = 2 if route=='C' else 1
    bits = np.asarray(stimulus['bits'])
    symbols = np.asarray(stimulus['symbols_C' if width==2 else 'symbols_N'])
    thresholds = np.array([37.5,62.5,87.5] if width==2 else [62.5])
    bit_ui = ETA/(rate*1e9)
    ui = width*bit_ui
    train_idx = np.arange(64//width,512//width)
    val_idx = np.arange(576//width,4672//width)
    delay_units = np.arange(513)/64
    delays = delay_units*bit_ui
    sample_train_t = train_idx[None,:]*ui+delays[:,None]
    train_end = 576*bit_ui
    assert sample_train_t.max()<train_end
    prefix = t<train_end
    tt, yy = t[prefix],signal_uA[prefix]
    samples = np.interp(sample_train_t,tt,yy)
    expected_train = symbols[train_idx]
    signed = rx._signed_margin(samples,expected_train,thresholds)
    amplitudes = signed.min(axis=1)
    time_min = np.full(len(delays),np.inf)
    events_by_level = rx._crossing_events(tt,yy,thresholds)
    for level, events in enumerate(events_by_level):
        columns = expected_train==level
        timestamps = sample_train_t[:,columns]
        if len(events):
            positions = np.searchsorted(events,timestamps,side='right')
            previous = np.where(positions>0,events[np.maximum(positions-1,0)],64*bit_ui)
            following = np.where(positions<len(events),events[np.minimum(positions,len(events)-1)],tt[-1])
        else:
            previous,following = 64*bit_ui,tt[-1]
        distance = np.minimum(timestamps-np.maximum(previous,64*bit_ui),
                              np.minimum(following,tt[-1])-timestamps)
        distance = np.where(signed[:,columns]>0,np.maximum(distance,0),0)
        time_min = np.minimum(time_min,distance.min(axis=1))
    scores = np.minimum(amplitudes/7.5,time_min/(.37*bit_ui))
    selected = int(scores.argmax())
    selected_train = rx._decode(samples[selected],thresholds)
    train_errors = int(np.count_nonzero(rx._bits(selected_train,width==2)!=rx._bits(expected_train,width==2)))
    sample_t = val_idx*ui+delays[selected]
    expected = symbols[val_idx]
    sample = np.interp(sample_t,t,signal_uA)
    decoded = rx._decode(sample,thresholds)
    errors = int(np.count_nonzero(rx._bits(decoded,width==2)!=bits[576:4672]))
    amp = float(rx._signed_margin(sample,expected,thresholds).min())
    timing = rx._horizontal(t,signal_uA,sample_t,sample,expected,thresholds,
                            0,len(bits)*bit_ui,ui,bit_ui)
    correct = errors==train_errors==0
    transitions = Counter(zip(symbols[val_idx-1],expected))
    wrong_transitions = Counter(zip(symbols[val_idx-1][decoded!=expected],expected[decoded!=expected]))
    return dict(errors=errors,validation_bits=4096,symbol_errors=int(np.count_nonzero(decoded!=expected)),
                train_errors=train_errors,delay_bit_UI=float(delay_units[selected]),
                delay_ps=float(delays[selected]*1e12),worst_signed_margin_uAeq=amp,
                one_sided_margin_ps=timing['min_ps'],one_sided_margin_bit_UI=timing['min_bit_UI'],
                one_sided_margin_symbol_UI=timing['min_symbol_UI'],zero_error=correct,
                research_margin_pass=bool(correct and amp>=7.5 and timing['min_bit_UI']>=.37),
                historical_100ps_pass=bool(correct and amp>=7.5 and timing['min_ps']>=100),
                transition_symbol_errors={f'{a}->{b}':dict(errors=wrong_transitions[a,b],occurrences=n)
                                          for (a,b),n in sorted(transitions.items())})


def micro_analyze(folder, rx, dyn, stimulus):
    result = read_json(folder/'result.json')
    assert result['simulation_ok'] and not result.get('analysis_error')
    wave = folder/'waveform.dat.gz'
    assert sha(wave)==result['gzip_sha256']
    with gzip.open(wave,'rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==result['raw_sha256']
    t,current = np.loadtxt(wave,skiprows=1,usecols=(0,1)).T
    assert np.all(np.diff(t)>0)
    case = result['case']
    rate,route = case['net_rate_Gbps'],case['route']
    assert abs(t[-1]-4096/(rate*1e9))<1e-14
    _, received = dyn.cascade_pwl(t,current,200e-12,1/(2*np.pi*1e9))
    full = receive(t,received*1e6,stimulus,route,rate,rx)
    electrical = receive(t,current*1e6,stimulus,route,rate,rx)
    metric = result['metrics']
    stress = max(metric['stress'],key=lambda x:x['max_pair_V']/x['limit_V'])
    body_peak=metric['max_body_forward_V']
    native_scalars={k:float(v) for k,v in re.findall(r'^([a-z][a-z0-9]*)\s*=\s*([-+0-9.eE]+)\s*$',
                                                    (folder/'ngspice.log').read_text(),flags=re.M)}
    body_pairs=[]
    for k,device in enumerate(result['metadata']['devices']):
        for terminal in [0,2]:
            key=f'fb{k}x{terminal}'
            if key in native_scalars and abs(native_scalars[key]-body_peak)<1e-9:
                body_pairs.append(dict(instance=device['instance'],model=device['model'],
                                       terminal='drain' if terminal==0 else 'source',
                                       terminal_node=device['nodes'][terminal],body_node=device['nodes'][3],
                                       positive_definition='terminal minus body' if device['model'].startswith('pfet') else 'body minus terminal',
                                       native_log_scalar=key,forward_peak_V=native_scalars[key]))
    energy = metric['total_energy']
    out = dict(family='MicroLED',route=route,net_Gbps=rate,line_Gbps=rate/ETA,
               symbol_GBd=rate/ETA/(2 if route=='C' else 1),capacitance_fF=case['led_cap_F']*1e15,
               steps_per_symbol=case['steps_per_symbol'],row_kind='rate' if abs(case['led_cap_F']-200e-15)<1e-22 else 'capacitance_sensitivity',
               original_current_targets_uA=[25,50,75,100] if route=='C' else [25,100],
               optical_tau_ps=200,receiver_GHz=1,full_receiver=full,electrical_only=electrical,
               energy_pJ_per_attempted_payload_bit={k:energy[k+'_pJ_per_payload_bit'] for k in ['positive','returned','net']},
               mean_source_positive_power_mW=energy['positive_J']/t[-1]*1e3,
               terminal_screen_pass=metric['device_voltage_passed'],worst_terminal=stress,
               max_body_forward_V=metric['max_body_forward_V'],
               body_forward_screen_pass=bool(metric['max_body_forward_V']<=.3),
               worst_body=dict(peak_forward_V=body_peak,research_screen_V=.3,pairs=body_pairs,
                               log_sha256=sha(folder/'ngspice.log'),scope='Peak only; internal node waveform and duration are not exported in the compact MicroLED trace.'),
               current_range_uA=[float(current.min()*1e6),float(current.max()*1e6)],
               static_IV_domain_pass=bool(current.min()>=.1e-6 and current.max()<=.032),
               solver_exit_code=result['exit_code'],native_samples=len(t),max_step_ps=float(np.diff(t).max()*1e12),
               solver_elapsed_s=result['simulation_elapsed_s'],
               source_case=str(folder.relative_to(ROOT)),result_sha256=sha(folder/'result.json'),
               source_manifest_sha256=result['manifest_sha256'],
               waveform_gzip_sha256=sha(wave),waveform_raw_sha256=result['raw_sha256'],deck_sha256=result['deck_sha256'])
    out['combined_research_screen_pass'] = bool(full['research_margin_pass'] and out['terminal_screen_pass']
                                               and out['body_forward_screen_pass'] and out['static_IV_domain_pass'])
    window = (t>=576*ETA/rate/1e9)&(t<=592*ETA/rate/1e9)
    emit(BUILD/'analysis'/'microled'/f'{folder.name}.json',out)
    return out,dict(time_bit_UI=(t[window]/(ETA/rate/1e9)-576).tolist(),
                    current_uA=(current[window]*1e6).tolist(),received_uAeq=(received[window]*1e6).tolist())


def vcsel_analyze(folder, frozen=False):
    rx = module(vca.RX_PATH,'rate_vcsel_rx')
    opto = module(vca.OPTO_PATH,'rate_vcsel_opto')
    m,traces = vca.analyze(folder,rx,opto,frozen,128)
    manifest=read_json(folder/'manifest.json')
    solved=read_json(folder/'result.json')
    if frozen:
        m['steps_per_UI']=manifest['config']['steps']
    full = m['pathways']['actual_graph_5GHzRX']
    out = dict(family='VCSEL',route='r10-NRZ',net_Gbps=m['net_Gbps'],line_Gbps=m['line_GBd'],
               symbol_GBd=m['line_GBd'],capacitance_fF=150,steps_per_symbol=m['steps_per_UI'],
               full_receiver={**full,'research_margin_pass':full['screen_pass'],'zero_error':full['errors']==full['train_errors']==0,
                              'one_sided_margin_bit_UI':full['one_sided_margin_UI']},
               electrical_only=m['pathways']['actual_electrical'],stages=m['stages'],
               energy_pJ_per_attempted_payload_bit=m['source_energy_pJ_per_attempted_net_bit'],
               mean_source_positive_power_mW=m['source_energy_pJ_per_attempted_net_bit']['positive']*m['net_Gbps'],
               terminal_screen_pass=m['observed']['terminal_screen_pass'],worst_terminal=m['observed']['terminal_peak'],
               max_body_forward_V=m['observed']['max_body_forward_V'],
               body_forward_screen_pass=bool(m['observed']['max_body_forward_V']<=.3),
               current_range_mA=m['observed']['electrical_current_range_mA'],
               static_IV_domain_pass=m['observed']['within_calibrated_electrical_and_optical_current_range'],
               source_case=str(folder.relative_to(ROOT)),result_sha256=sha(folder/'result.json'),
               waveform_gzip_sha256=m['waveform']['sha256'],waveform_raw_sha256=m['waveform']['raw_sha256'],
               deck_sha256=m['deck_sha256'],full_analysis=m)
    out['solver_elapsed_s']=solved.get('solve_s',solved.get('elapsed_s'))
    out['worst_body']=dict(peak_forward_V=solved['max_body_forward_V'],research_screen_V=.3,
                          instances=[s for s in solved['stress'] if abs(s['max_body_forward_V']-solved['max_body_forward_V'])<1e-9])
    out['combined_research_screen_pass']=bool(full['screen_pass'] and out['terminal_screen_pass']
                                             and out['body_forward_screen_pass'] and out['static_IV_domain_pass'])
    emit(BUILD/'analysis'/'vcsel'/f'{folder.name}.json',out)
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--family',choices=['microled','vcsel','all'],default='all')
    args=ap.parse_args()
    rows=[]
    if args.family in ('microled','all'):
        rx=module(RXPATH,'rate_rx')
        dyn=module(DYNAMIC,'rate_dynamics')
        stimulus=read_json(OLD/'stimulus.json')
        folders=sorted((MICRO/'cases').glob('*')) if (MICRO/'cases').exists() else []
        folders += [OLD/'cases'/f'TT-{r}-C200fF-S40' for r in 'ABC']
        folders += [OLD/'cases'/f'TT-B-C{c}fF-S40' for c in [0,10,50,800]]
        for folder in folders:
            if not (folder/'result.json').exists(): continue
            m,_=micro_analyze(folder,rx,dyn,stimulus)
            rows.append(m)
            print('MicroLED',m['route'],m['net_Gbps'],m['capacitance_fF'],m['full_receiver']['errors'],
                  m['full_receiver']['worst_signed_margin_uAeq'],m['full_receiver']['one_sided_margin_ps'],flush=True)
    if args.family in ('vcsel','all'):
        folders=[(vca.SAVED,True),(vca.SAVED.parent/'frame-TT-halfstep-r10',True)]
        folders += [(p,False) for p in sorted((BUILD/'vcsel').glob('*')) if p.is_dir()]
        folders += [(vca.BUILD/'net16-edge20-s40',False),(vca.BUILD/'net32-edge20-s40',False)]
        for folder,frozen in folders:
            if not (folder/'result.json').exists(): continue
            m=vcsel_analyze(folder,frozen)
            rows.append(m)
            print('VCSEL',m['net_Gbps'],m['full_receiver']['errors'],m['full_receiver']['one_sided_margin_ps'],flush=True)
    envelopes=[]
    for family,route,cap in [('MicroLED',r,200) for r in 'ABC']+[('VCSEL','r10-NRZ',150)]:
        group=sorted([r for r in rows if r['family']==family and r['route']==route
                      and abs(r['capacitance_fF']-cap)<1e-8 and r['steps_per_symbol']==40],key=lambda r:r['net_Gbps'])
        if not group:continue
        passed=[r['net_Gbps'] for r in group if r['combined_research_screen_pass']]
        receiver_passed=[r['net_Gbps'] for r in group if r['full_receiver']['research_margin_pass']]
        zero=[r['net_Gbps'] for r in group if r['full_receiver']['zero_error']]
        maximum=max(passed) if passed else None
        above=[r['net_Gbps'] for r in group if maximum is not None and r['net_Gbps']>maximum
               and not r['combined_research_screen_pass']]
        envelopes.append(dict(family=family,route=route,capacitance_fF=cap,
                              tested_rates_Gbps=[r['net_Gbps'] for r in group],
                              highest_passing_tested_rate_Gbps=maximum,
                              highest_receiver_margin_passing_tested_rate_Gbps=max(receiver_passed) if receiver_passed else None,
                              next_tested_failing_rate_Gbps=min(above) if above else None,
                              highest_zero_error_tested_rate_Gbps=max(zero) if zero else None,
                              interpretation='Discrete tested nominal envelope only; no interpolation, monotonicity proof, PVT, BER or physical device maximum.'))
    convergence=[]
    for fine in [r for r in rows if r['steps_per_symbol']==80]:
        match=[r for r in rows if r['steps_per_symbol']==40 and
               (r['family'],r['route'],r['net_Gbps'])==(fine['family'],fine['route'],fine['net_Gbps'])
               and abs(r['capacitance_fF']-fine['capacitance_fF'])<1e-8]
        if len(match)!=1:continue
        coarse=match[0]
        convergence.append(dict(family=fine['family'],route=fine['route'],net_Gbps=fine['net_Gbps'],
                                cap_fF=fine['capacitance_fF'],coarse_case=coarse['source_case'],fine_case=fine['source_case'],
                                coarse_errors=coarse['full_receiver']['errors'],fine_errors=fine['full_receiver']['errors'],
                                combined_screen_unchanged=coarse['combined_research_screen_pass']==fine['combined_research_screen_pass'],
                                signed_margin_delta_uAeq=fine['full_receiver']['worst_signed_margin_uAeq']-coarse['full_receiver']['worst_signed_margin_uAeq'],
                                time_margin_delta_ps=fine['full_receiver']['one_sided_margin_ps']-coarse['full_receiver']['one_sided_margin_ps'],
                                energy_relative_delta_percent=100*(fine['energy_pJ_per_attempted_payload_bit']['positive']/coarse['energy_pJ_per_attempted_payload_bit']['positive']-1)))
    protocol=dict(schema='rate-sweep-provenance-v1',
                  inheritance='The MicroLED work manifest preserves the historical schema, creation time and assumptions.rates=3.2 as frozen source identity. They are not this sweep operating rates. Per-case case.json/result.case and VCSEL per-case manifest timing are authoritative.',
                  frozen_microled_work_manifest=str((MICRO/'manifest.json').relative_to(ROOT)),
                  frozen_microled_work_manifest_sha256=sha(MICRO/'manifest.json'),
                  original_microled_manifest=str((OLD/'manifest.json').relative_to(ROOT)),
                  original_microled_manifest_sha256=sha(OLD/'manifest.json'),
                  analysis_family=args.family,
                  cases=[dict(source_case=r['source_case'],family=r['family'],route=r['route'],net_Gbps=r['net_Gbps'],
                              capacitance_fF=r['capacitance_fF'],steps_per_symbol=r['steps_per_symbol'],
                              reused_native_anchor=not r['source_case'].startswith('build/blue-emitter-speed-review-20261110/'),
                              result_sha256=r['result_sha256'],deck_sha256=r['deck_sha256']) for r in rows])
    emit(EV/'speed-sweep-protocol.json',protocol)
    payload=dict(schema='real-transistor-rate-envelope-v1',
                 scope='Every new rate has its own native ngspice trace. Existing 3.2/16/32 anchors reused with hashes. No rescaled circuit waveform, no blue emitter model or measured link claim.',
                 conditions=dict(training_scored_bits=[64,512],validation_bits=[576,4672],frame_bits=4736,
                                 net_efficiency=ETA,source_edge_ps=20,delay_range_line_bit_UI=[0,8],
                                 delay_step_line_bit_UI=1/64,thresholds_uAeq={'NRZ':[62.5],'PAM4':[37.5,62.5,87.5]},
                                 minimum_amplitude_uAeq=7.5,minimum_time_line_bit_UI=.37,
                                 maximum_body_forward_screen_V=.3,
                                 selection='Maximize min(training signed amplitude/7.5uAeq, training time/(0.37 line-bit UI)); earliest exact tie; freeze on disjoint validation.',
                                 limitations='TT schematic nominal screen. Fixed deterministic frame, no random noise/CDR/FEC/BER qualification; max passing tested point only.'),
                 source_hashes={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),Path(__file__).with_name('sweep.py'),RXPATH,DYNAMIC,Path(vca.__file__),OLD/'stimulus.json']},
                 sum_solver_elapsed_s_new_cases=sum(r['solver_elapsed_s'] or 0 for r in rows if r['source_case'].startswith('build/blue-emitter-speed-review-20261110/')),
                 protocol_receipt='evidence/blue-emitter-speed-review-20261110/speed-sweep-protocol.json',
                 protocol_receipt_sha256=sha(EV/'speed-sweep-protocol.json'),
                 envelopes=envelopes,half_step_checks=convergence,rows=rows)
    emit(EV/f'speed-sweep-{args.family}.json',payload)


if __name__=='__main__':
    main()
