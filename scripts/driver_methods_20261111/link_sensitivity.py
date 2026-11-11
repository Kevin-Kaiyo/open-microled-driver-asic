#!/usr/bin/env python3
"""Conditional optical/RX budget on frozen native 3.2 Gb/s current traces.

This is a model sensitivity calculation, not a new driver simulation, emitter
measurement, receiver design or end-to-end energy result. The original 200 ps /
1 GHz point must exactly reproduce the frozen prior result before publication.
"""
from pathlib import Path
import gzip,hashlib,importlib.util,json,sys,time
import numpy as np

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/blue_emitter_speed_20261110'))
from analyze import receive
EV=ROOT/'evidence/driver-methods-20261111'
WORK=ROOT/'build/driver-methods-20261111/link-sensitivity'
GRID=dict(optical_tau_ps=[0,50,100,200],receiver_GHz=[1,2,4,8],net_Gbps=3.2)
CANDIDATES={'A':'a-rin1wide-core03-matched','B':'B_wide_ff31p275'}
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def emit(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def module(p,name):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
    WORK.mkdir(parents=True,exist_ok=True)
    protocol=WORK/'protocol.json'
    if not protocol.exists():emit(protocol,dict(grid=GRID,scope=__doc__,candidate=CANDIDATES,script_sha256=sha(Path(__file__))))
    assert read(protocol)['grid']==GRID
    dyn=module(ROOT/'scripts/microled_dynamic_v1/analyze.py','link_sensitivity_dynamics')
    output=[];sources=[]
    for route,name in CANDIDATES.items():
        old=ROOT/'build/ab-improvement-20261111'/name
        case=old/'cases/TT-net3.2-C200-S40';r=read(case/'result.json');m=read(old/'manifest.json')
        wave=case/'waveform.dat.gz';assert sha(wave)==r['gzip_sha256']
        with gzip.open(wave,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['raw_sha256']
        rx=module(old/'execution-sources/receiver_equal_latency_v2.py','link_sensitivity_rx_'+route)
        st=read(old/'stimulus.json');assert sha(old/'stimulus.json')==m['stimulus_sha256']
        t,current=np.loadtxt(wave,skiprows=1,usecols=(0,1)).T
        assert np.all(np.diff(t)>0) and abs(t[-1]-4096/3.2e9)<1e-14
        sources.append(dict(route=route,candidate=name,case=str(case.relative_to(ROOT)),result_sha256=sha(case/'result.json'),waveform_gzip_sha256=sha(wave),waveform_raw_sha256=r['raw_sha256'],stimulus_sha256=sha(old/'stimulus.json'),native_samples=len(t),driver_energy_pJ_per_attempted_payload_bit=r['analysis']['energy_pJ_per_attempted_payload_bit'],receiver_and_optical_hardware_power='not_modelled'))
        for tau in GRID['optical_tau_ps']:
            for bandwidth in GRID['receiver_GHz']:
                dest=WORK/f'{route}-tau{tau}-RX{bandwidth}.json'
                if dest.exists():
                    row=read(dest)
                    assert row['route']==route and row['candidate']==name
                    assert row['net_Gbps']==3.2 and row['optical_tau_ps']==tau and row['receiver_GHz']==bandwidth
                    assert row['source_result_sha256']==sha(case/'result.json'),'Cached current-source identity changed'
                else:
                    start=time.monotonic()
                    _,received=dyn.cascade_pwl(t,current,tau*1e-12,1/(2*np.pi*bandwidth*1e9))
                    full=receive(t,received*1e6,st,route,3.2,rx)
                    row=dict(route=route,candidate=name,net_Gbps=3.2,optical_tau_ps=tau,receiver_GHz=bandwidth,full_receiver=full,
                        scope='Conditional sensitivity at fixed native current; not a calibrated emitter/RX or hardware improvement.',source_result_sha256=sha(case/'result.json'),elapsed_s=time.monotonic()-start)
                    emit(dest,row)
                if tau==200 and bandwidth==1:
                    base=r['analysis']['full_receiver'];got=row['full_receiver']
                    assert got['errors']==base['errors'] and got['train_errors']==base['train_errors']
                    for key in ['worst_signed_margin_uAeq','one_sided_margin_ps','delay_ps']:assert abs(got[key]-base[key])<1e-7,(route,key)
                output.append(row);print(route,tau,bandwidth,row['full_receiver']['errors'],row['full_receiver']['research_margin_pass'],flush=True)
    emit(EV/'link-sensitivity.json',dict(grid=GRID,protocol_sha256=sha(protocol),rows=output,sources=sources,
        source_code_sha256={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'scripts/blue_emitter_speed_20261110/analyze.py',ROOT/'scripts/microled_dynamic_v1/analyze.py']},
        baseline_reproduction_pass=True,limits=['No new SPICE or electrical change in this matrix.','Higher RX bandwidth can change noise and power; neither is modeled.','Optical tau is an assumed scalar, not calibrated device physics.','One deterministic frame and a fixed research margin contract; no BER inference.']))
if __name__=='__main__':main()
