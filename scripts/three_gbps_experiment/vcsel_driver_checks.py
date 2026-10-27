#!/usr/bin/env python3
"""Focused receiver/reference integrity checks, not a physical link test."""
import json, math
from pathlib import Path
import numpy as np
from vcsel_driver_run import ROOT, BUILD, sha, emit, module
from vcsel_driver_analyze import rx_filter


def main():
    checks={}
    rx=module(ROOT/'scripts/fair_driver_v1/receiver_equal_latency_v2.py','vcsel_test_rx')
    optical=module(ROOT/'scripts/three_gbps_experiment/vcsel_model.py','vcsel_test_model')
    lo,hi=optical.static_power(np.array([.003,.007])); eq=25e-6+(np.array([lo,hi])-lo)*75e-6/(hi-lo)
    checks['affine_target_endpoints']=bool(np.allclose(eq,[25e-6,100e-6],rtol=0,atol=1e-18))
    checks['fixed_threshold_and_margin']=bool(math.isclose(float((hi-lo)*.1),.00022393822393822394,abs_tol=1e-16))
    t=np.arange(1001)*1e-12;x=t*1e6;f=rx_filter(t,x,5e9);tau=1/(2*np.pi*5e9);expected=1e6*(t-tau*(1-np.exp(-t/tau)))
    checks['rx_ramp_exact_integration']=bool(np.max(abs(f-expected))<1e-15)
    stim=rx.make_stimulus();ui=32/37/3.2e9;t=np.linspace(0,4736*ui,4736*40+1)
    idx=np.minimum(np.floor(t/ui+1e-8).astype(int),4735);bits=np.asarray(stim['bits']);ideal=25e-6+75e-6*bits[idx]
    rx.filter_trace=lambda t,c:(np.asarray(c),np.asarray(c))
    positive=rx.analyze(t,ideal,stim,'NRZ',3.2)
    checks['ideal_3p2_positive_control']=positive['passed']
    constant=rx.analyze(t,np.zeros(len(t))+25e-6,stim,'NRZ',3.2)
    checks['constant_negative_control']=not constant['passed'] and constant['validation']['bit_errors']==int(bits[576:4672].sum())
    tampered=ideal.copy();tampered[t>=576*ui]=125e-6-tampered[t>=576*ui]
    changed=rx.analyze(t,tampered,stim,'NRZ',3.2)
    checks['validation_cannot_train_delay']=positive['sampling']['delay_s']==changed['sampling']['delay_s']
    lock=json.loads((ROOT/'analog/models/pdk-lock.json').read_text())
    checks['pinned_model_hashes']=all(sha(ROOT/'.cache/pdk/gf180mcu'/Path(name).name)==digest for name,digest in lock['files'].items())
    out=ROOT/'evidence/three-gbps-experiment-20261027/vcsel-driver-checks.json';out.parent.mkdir(parents=True,exist_ok=True)
    record=dict(checks=checks,passed=all(checks.values()),script_sha256=sha(Path(__file__)),positive_control=dict(errors=positive['validation']['bit_errors'],margin_ps=positive['horizontal_margin']['min_ps']),negative_control_errors=constant['validation']['bit_errors'],boundary='Synthetic algorithm controls only, not driver or device measurements')
    emit(out,record);print(json.dumps(record));assert record['passed']


if __name__=='__main__':main()
