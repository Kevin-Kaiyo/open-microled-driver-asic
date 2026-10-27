#!/usr/bin/env python3
"""Frozen optical-power normalization and training-only v2 receiver analysis."""
from pathlib import Path
import argparse, json, math, shutil
import numpy as np
from vcsel_driver_run import ROOT, BUILD, sha, emit, module


def rx_filter(t,x,pole_hz):
    # Exact first-order evolution for piecewise-linear optical power samples.
    tau=1/(2*np.pi*pole_hz); out=np.empty(len(t)); out[0]=x[0]
    for k in range(1,len(t)):
        h=t[k]-t[k-1]; u=x[k-1]; slope=(x[k]-u)/h; decay=np.exp(-h/tau)
        out[k]=decay*out[k-1]+u*(-np.expm1(-h/tau))+slope*(h-tau*(-np.expm1(-h/tau)))
    return out


def analyze(case,label,response='figure3mA_proxy',rx_ghz=5,grid_ps=2.5,receiver_version='v2'):
    work=BUILD/case; m=json.loads((work/'manifest.json').read_text()); result=json.loads((work/'result.json').read_text())
    assert result['simulation_ok'] and m['args']['mode']=='frame'
    out=work/('analysis-'+label); assert not out.exists(), 'Analysis outputs immutable; choose another label'
    out.mkdir(); inp=out/'inputs'; inp.mkdir()
    sources=['scripts/three_gbps_experiment/vcsel_model.py','analog/models/vcsel_research_20261027/parameters.json',
             ('scripts/three_gbps_experiment/vcsel_driver_receiver_v3.py' if receiver_version=='v3' else 'scripts/fair_driver_v1/receiver_equal_latency_v2.py'),'scripts/three_gbps_experiment/vcsel_driver_analyze.py']
    if receiver_version=='v3': sources.append('analog/circuits/vcsel_research_20261027/receiver-feasibility-v3-diagnostic.json')
    for name in sources:
        p=inp/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,p)
    optical=module(inp/sources[0],'optical_'+case.replace('-','_')+label.replace('-','_'))
    rx=module(inp/sources[2],'rx_'+case.replace('-','_')+label.replace('-','_'))
    constants=optical.static_power(np.array([.003,.007])); low,high=map(float,constants); scale=(high-low)/75e-6
    plan=dict(case=case,label=label,response=response,rx_GHz=rx_ghz,grid_ps=grid_ps,receiver_version=receiver_version,sources={s:sha(inp/s) for s in sources},
              waveform_sha256=sha(ROOT/result['waveform']['path']),circuit_manifest_sha256=sha(work/'manifest.json'),
              normalization=dict(target_current_A=[.003,.007],static_power_W=[low,high],equivalent_current_A=[25e-6,100e-6],threshold_power_W=(low+high)/2,min_signed_power_margin_W=(high-low)*.1,
                                 expression='Ieq=25uA+(P-P(3mA))*75uA/(P(7mA)-P(3mA)); equivalent current is not photodiode current'),
              receiver=('Original v2 amplitude-first trainer' if receiver_version=='v2' else 'V3 diagnostic joint normalized amplitude/time objective, earliest exact tie')+';448bit score+64guard; explicit optical model followed by RX pole; fixed7.5uAeq and100ps gates',
              optical_response=optical.response_metadata(response),
              boundary='Magnitude-only figure proxy does not calibrate phase/group delay, large-signal behavior, temperature, optical coupling or real receiver noise/power. All resulting communication checks are conditional research screens.')
    emit(out/'plan.json',plan) # Declared before reading/processing transient data.
    a=np.loadtxt(ROOT/result['waveform']['path'],skiprows=1); ix={s:i+1 for i,s in enumerate(m['expressions'])}
    rate=m['args']['rate']; ui=32/37/(rate*1e9); end=4736*ui
    n=int(np.ceil(end/(grid_ps*1e-12))); t=np.linspace(0,end,n+1); current=np.interp(t,a[:,0],a[:,1])
    p=optical.optical_power(t,current,response=response); eq=25e-6+(p-low)/scale
    filt=rx_filter(t,eq,rx_ghz*1e9)
    rx.filter_trace=lambda ts,cur:(np.asarray(cur),rx_filter(np.asarray(ts),np.asarray(cur),rx_ghz*1e9))
    stim=json.loads((work/'stimulus.json').read_text()); receiver=rx.analyze(t,eq,stim,'NRZ',rate)
    receiver['proxy']=dict(input='Affine normalized optical-power proxy in Aeq, not photocurrent',normalization=plan['normalization'],optical_response=response,
                           optical_metadata=optical.response_metadata(response),rx_pole_Hz=rx_ghz*1e9,uniform_grid_ps=float(np.diff(t).max()*1e12),native_max_step_ps=result['max_timestep_ps'])
    receiver['limits'].append('Legacy uA field names mean uAeq here; conditional_noise_BER is normalized Gaussian diagnostic only, not physical RX BER.')
    sample_t=np.arange(576,4672)*ui+receiver['sampling']['delay_s']; samples=np.interp(sample_t,t,filt)
    recv_power=low+(filt-25e-6)*scale; sample_power=low+(samples-25e-6)*scale
    bits=np.asarray(stim['bits'])[576:4672]; threshold=(low+high)/2
    signed=(2*bits-1)*(sample_power-threshold)
    level_ranges={str(b):dict(min_mW=float(sample_power[bits==b].min()*1e3),max_mW=float(sample_power[bits==b].max()*1e3),mean_mW=float(sample_power[bits==b].mean()*1e3)) for b in (0,1)}
    domain=dict(IV_trusted_current_mA=[2,8],PI_upper_graph_current_mA=7.5,
                IV_outside_time_fraction=float(np.trapezoid(((current<.002)|(current>.008)).astype(float),t)/end),
                PI_above_graph_time_fraction=float(np.trapezoid((current>.0075).astype(float),t)/end),
                negative_optical_time_fraction=float(np.trapezoid((p<0).astype(float),t)/end),
                VCSEL_temperature_model=False,GF180_temperature_C=m['temp_C'])
    quantities=dict(optical_margin_min_mW=float(signed.min()*1e3),optical_eye_opening_mW=float((sample_power[bits==1].min()-sample_power[bits==0].max())*1e3),
                    normalized_margin_uAeq=receiver['validation']['decision_distance_min_uA'],levels_rx_power_proxy=level_ranges,
                    optical_range_mW=[float(p.min()*1e3),float(p.max()*1e3)],
                    base_mean_mA=float(np.trapezoid(a[:,ix['i(v.xdrv.vibase)']],a[:,0])/end*1e3),
                    tail_mean_mA=float(np.trapezoid(a[:,ix['i(v.xdrv.vitail)']],a[:,0])/end*1e3),
                    ref_mean_mA=float(np.trapezoid(-a[:,ix['i(VREF)']],a[:,0])/end*1e3))
    # Compact plot inputs: first160 validation bit eyes and first32bit waveforms.
    phase=np.linspace(-.5,1.5,161); eyes=np.array([np.interp((k+phase)*ui+receiver['sampling']['delay_s'],t,recv_power) for k in range(576,736)])
    trace_t=np.linspace(576*ui,608*ui,2561)
    np.savez_compressed(out/'plot-data.npz',eye_phase_UI=phase,eye_rx_power_W=eyes,eye_labels=bits[:160],trace_t_s=trace_t,
                        trace_current_A=np.interp(trace_t,t,current),trace_optical_W=np.interp(trace_t,t,p),trace_rx_W=np.interp(trace_t,t,recv_power),
                        trace_gp_V=np.interp(trace_t,a[:,0],a[:,ix['v(xdrv.gp)']]),trace_gn_V=np.interp(trace_t,a[:,0],a[:,ix['v(xdrv.gn)']]),
                        validation_samples_W=sample_power,validation_bits=bits)
    full=dict(plan_sha256=sha(out/'plan.json'),receiver=receiver,quantities=quantities,domain=domain,
              conditional_communication_screen=receiver['passed'],device_screen_passed=result['device_screen_passed'],
              bounded_model_domain_screen=domain['IV_outside_time_fraction']==0 and domain['PI_above_graph_time_fraction']==0 and domain['negative_optical_time_fraction']==0,
              plot_data_sha256=sha(out/'plot-data.npz'))
    full['combined_screen_passed']=full['conditional_communication_screen'] and full['device_screen_passed'] and full['bounded_model_domain_screen']
    emit(out/'result.json',full)
    print(json.dumps(dict(case=case,label=label,errors=receiver['validation']['bit_errors'],time_ps=receiver['horizontal_margin']['min_ps'],margin_uAeq=quantities['normalized_margin_uAeq'],margin_mW=quantities['optical_margin_min_mW'],communication=receiver['passed'],domain=domain,combined=full['combined_screen_passed']),ensure_ascii=False),flush=True)
    return full


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);ap.add_argument('--label',default='baseline');ap.add_argument('--response',default='figure3mA_proxy');ap.add_argument('--rx-ghz',type=float,default=5);ap.add_argument('--grid-ps',type=float,default=2.5);ap.add_argument('--receiver',choices=['v2','v3'],default='v2')
    args=ap.parse_args();analyze(args.case,args.label,args.response,args.rx_ghz,args.grid_ps,args.receiver)
