#!/usr/bin/env python3
"""Append-only schematic improvement experiments, unchanged receiver contract."""
import datetime
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT/'build/ab-improvement-20261111'
BASE = ROOT/'build/blue-emitter-speed-review-20261110/microled'
sys.path.insert(0,str(ROOT/'scripts/blue_emitter_speed_20261110'))
from analyze import receive

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def read(p):return json.loads(Path(p).read_text())

def emit(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def module(p,name):
    spec=importlib.util.spec_from_file_location(name,p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def init_candidate(name,route,route_text,parameters=None,notes=None,common_text=None):
    assert route in 'AB' and '/' not in name and name not in ['.','..']
    work=BUILD/name
    old=read(BASE/'manifest.json')
    for p,h in old['inputs'].items():assert sha(BASE/'inputs'/p)==h,p
    assert sha(BASE/'stimulus.json')==old['stimulus_sha256']
    if (work/'manifest.json').exists():
        m=read(work/'manifest.json')
        assert (work/'inputs'/f'route_{route.lower()}.spice').read_text()==route_text
        assert m['parameters'][route]==(parameters or old['parameters'][route])
        verify(work);return work
    work.mkdir(parents=True,exist_ok=False)
    shutil.copytree(BASE/'inputs',work/'inputs',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (work/'execution-sources').mkdir()
    for source in ['legacy_engine.py','receiver_equal_latency_v2.py']:
        shutil.copy2(BASE/'execution-sources'/source,work/'execution-sources'/source)
    shutil.copy2(Path(__file__),work/'execution-sources/improvement-engine.py')
    (work/'inputs'/f'route_{route.lower()}.spice').write_text(route_text)
    if common_text is not None:(work/'inputs/common.spice').write_text(common_text)
    shutil.copy2(BASE/'stimulus.json',work/'stimulus.json')
    params=old['parameters'];params[route]=parameters or params[route]
    m=dict(schema='driver-improvement-20261111',created=datetime.datetime.now(datetime.timezone.utc).isoformat(),
           name=name,route=route,parameters=params,notes=notes,baseline_manifest_sha256=sha(BASE/'manifest.json'),
           common=old['common'],stimulus_sha256=sha(work/'stimulus.json'),
           inputs={str(p.relative_to(work/'inputs')):sha(p) for p in (work/'inputs').rglob('*') if p.is_file()},
           execution_sources={p.name:sha(p) for p in (work/'execution-sources').glob('*.py')},
           receiver_sha256=sha(ROOT/'scripts/blue_emitter_speed_20261110/analyze.py'),
           dynamics_sha256=sha(ROOT/'scripts/microled_dynamic_v1/analyze.py'),
           assumptions=dict(C_fF=200,optical_tau_ps=200,RX_GHz=1,net_efficiency=32/37,
                            scope='New schematic only; no new layout or optical measurement',
                            DC_target_uA=[25,100],DC_tolerance_percent=1,
                            source_boundary='Seven instantiated source ports, including data; excluding upstream conversion, RX and clock overhead'))
    emit(work/'manifest.json',m);return work

def verify(work):
    m=read(work/'manifest.json')
    for name,h in m['inputs'].items():assert sha(work/'inputs'/name)==h,name
    for name,h in m['execution_sources'].items():assert sha(work/'execution-sources'/name)==h,name
    assert sha(work/'stimulus.json')==m['stimulus_sha256']
    assert sha(ROOT/'scripts/blue_emitter_speed_20261110/analyze.py')==m['receiver_sha256']
    assert sha(ROOT/'scripts/microled_dynamic_v1/analyze.py')==m['dynamics_sha256']
    return m

def run_case(work,rate=0.8,level=None,steps=40,cap_fF=200,label=None,**overrides):
    work=Path(work);m=verify(work);route=m['route']
    case=dict(name=label or (f'DC-L{level}' if level is not None else f'TT-net{rate:g}-C{cap_fF:g}-S{steps}'),
              route=route,corner='typical',temp_C=27,vdd_V=3.3,led_cap_F=cap_fF*1e-15,
              net_rate_Gbps=rate,steps_per_symbol=steps,timeout_s=900)
    if level is not None:case.update(kind='dc',level=level)
    case.update(overrides);folder=work/'cases'/case['name']
    if (folder/'result.json').exists():
        r=read(folder/'result.json');assert r['case']==case
        if r.get('gzip_sha256'):assert sha(folder/'waveform.dat.gz')==r['gzip_sha256']
        return r
    folder.mkdir(parents=True,exist_ok=False)
    e=module(work/'execution-sources/legacy_engine.py','improvement_legacy_'+work.name);e.ROOT=ROOT
    text,meta=e.deck(work,case)
    if level is None:
        wanted=['d0','out','led_a','led_k','pk','vin','vdd','vref']
        wanted += ['xdrv.'+n for n in (['di','n1','ctrl','vh','vl','hset','lset','hg','lg'] if route=='A' else ['di','gb','gp','vx','dummy','bias','sense'])]
        text=text.replace('wrdata waveform.dat i(VSENSE)\n','wrdata waveform.dat i(VSENSE) '+' '.join(f'v({n})' for n in wanted)+'\n')
        meta['vectors']={'iled_cond':1,**{n:k+2 for k,n in enumerate(wanted)}}
    text=text.replace(str(work/'inputs'),'../../inputs')
    assert str(ROOT) not in text
    (folder/'testbench.spice').write_text(text);emit(folder/'case.json',case)
    start=time.monotonic();print('START',work.name,case['name'],flush=True)
    with (folder/'ngspice.log').open('w') as log:
        try:code=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=log,stderr=subprocess.STDOUT,timeout=case['timeout_s']).returncode
        except subprocess.TimeoutExpired:code=None
    raw=folder/'waveform.dat'
    r=dict(case=case,metadata=meta,simulation_ok=code==0 and raw.exists(),exit_code=code,
           simulation_elapsed_s=time.monotonic()-start,deck_sha256=sha(folder/'testbench.spice'),
           manifest_sha256=sha(work/'manifest.json'),engine_sha256=sha(Path(__file__)))
    if r['simulation_ok']:
        try:
            metrics=e.evaluate(raw,meta,case,work);r['metrics']=metrics
            if level is None:
                a=np.loadtxt(raw,skiprows=1);t=a[:,0];current=a[:,1]
                assert np.isfinite(a).all() and np.all(np.diff(t)>0)
                assert abs(t[-1]-4096/(rate*1e9))<1e-14
                dyn=module(ROOT/'scripts/microled_dynamic_v1/analyze.py','improvement_dynamics')
                rx=module(work/'execution-sources/receiver_equal_latency_v2.py','improvement_receiver')
                _,filtered=dyn.cascade_pwl(t,current,200e-12,1/(2*np.pi*1e9))
                st=read(work/'stimulus.json')
                full=receive(t,filtered*1e6,st,route,rate,rx)
                electrical=receive(t,current*1e6,st,route,rate,rx)
                body=metrics['max_body_forward_V']<=.3
                domain=bool(current.min()>=.1e-6 and current.max()<=.032)
                r['analysis']=dict(full_receiver=full,electrical_receiver=electrical,
                    energy_pJ_per_attempted_payload_bit={k:metrics['total_energy'][k+'_pJ_per_payload_bit'] for k in ['positive','returned','net']},
                    terminal_screen_pass=metrics['device_voltage_passed'],max_body_forward_V=metrics['max_body_forward_V'],body_screen_pass=bool(body),static_IV_domain_pass=domain,
                    combined_screen_pass=bool(full['research_margin_pass'] and metrics['device_voltage_passed'] and body and domain),
                    current_range_uA=[float(current.min()*1e6),float(current.max()*1e6)],
                    native_samples=len(t),max_step_ps=float(np.diff(t).max()*1e12))
                r['observables']={n:dict(min=float(a[:,i].min()),max=float(a[:,i].max()),mean=float(np.trapezoid(a[:,i],t)/t[-1])) for n,i in meta['vectors'].items()}
            else:
                r['DC_screen_pass']=bool(abs(metrics['current_error_percent'])<=1 and metrics['device_voltage_passed'] and metrics['max_body_forward_V']<=.3)
        except Exception as err:r['analysis_error']=repr(err)
    if raw.exists():
        r['raw_sha256']=sha(raw);gz=folder/'waveform.dat.gz'
        with raw.open('rb') as src,gzip.open(gz,'wb',compresslevel=5) as dst:shutil.copyfileobj(src,dst)
        with gzip.open(gz,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['raw_sha256']
        r['gzip_sha256']=sha(gz);r['gzip_bytes']=gz.stat().st_size;raw.unlink()
    r['elapsed_s']=time.monotonic()-start;emit(folder/'result.json',r)
    print('DONE',work.name,case['name'],r.get('analysis',{}).get('combined_screen_pass',r.get('DC_screen_pass')),r.get('analysis_error'),flush=True)
    return r
