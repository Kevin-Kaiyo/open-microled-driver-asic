#!/usr/bin/env python3
"""Append-only real VCSEL driver improvements at unchanged load/RX conditions.

Change input attenuation or output-switch geometry; preserve all reference,
rail, optical and receiver assumptions. No ideal added gate source is used.
"""
from pathlib import Path
import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import time

import numpy as np

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/highspeed_workbench_20261110'))
import vcsel_x10_run as run
import vcsel_x10_analyze as analysis
BUILD=ROOT/'build/ab-improvement-20261111/VCSEL'
EV=ROOT/'evidence/ab-improvement-20261111'
SPECS={
 'vc-base':dict(atten_ohm=200.,steer_width_um=40.,hypothesis='Unmodified r10 schematic control.'),
 'vc-atten50':dict(atten_ohm=50.,steer_width_um=40.,hypothesis='Reduce two input attenuation series resistors from200 to50ohm; test input RC while retaining all transistor dimensions.'),
 'vc-steer20':dict(atten_ohm=200.,steer_width_um=20.,hypothesis='Halve only two steering MOS widths40to20um, including estimated diffusions; test gate/output capacitive load versus on-resistance and current compliance.'),
 'vc-atten50-steer20':dict(atten_ohm=50.,steer_width_um=20.,hypothesis='Combine the two independently tested modifications; preserve real reference and rail circuits.')}


def emit(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def driver(spec):
    original=run.R10.read_text();lines=[]
    for line in original.splitlines():
        if line.startswith(('XSTEER_0 ','XDUMP_0 ')):
            w=spec['steer_width_um'];p=line.split()
            if w!=40.:
                line=' '.join(p[:6])+f' w={w:g}u l=0.28u ad={w*.44:g}p as={w*.44:g}p pd={2*(w+.44):g}u ps={2*(w+.44):g}u'
        lines.append(line)
    return '\n'.join(lines)+'\n'


def prepare(name,rate,steps,level=None):
    spec=SPECS[name]
    folder=BUILD/name/(f'DC-L{level}' if level is not None else f'net{rate:g}-edge20-s{steps}')
    config=dict(candidate=name,spec=spec,net_Gbps=rate,steps=steps,level=level)
    if folder.exists():
        m=run.read_json(folder/'manifest.json');assert m['improvement_config']==config
        for file,h in m['source_sha256'].items():
            if file=='runner.py':continue
            assert run.sha(folder/file)==h,file
        assert run.sha(folder/'testbench.spice')==m['deck_sha256']
        assert run.sha(folder/'stimulus.json')==m['stimulus_sha256']
        return folder,m
    folder.mkdir(parents=True,exist_ok=False)
    m=run.make_deck(folder,rate,20,steps)
    m['baseline_source_sha256']=copy.deepcopy(m['source_sha256'])
    text=driver(spec);(folder/'driver.spice').write_text(text)
    lines={line.split()[0]:line.split() for line in text.splitlines() if line.startswith('X')}
    for d in m['devices']:
        if d['instance'] in lines:d['parameters']=lines[d['instance']][6:]
    deck=(folder/'testbench.spice').read_text()
    # Only the top-level instance override changes. Subckt default remains
    # visible as historical baseline and is overridden explicitly in every deck.
    deck,count=re.subn(r'(?m)^(XDRV[^\n]*\bATTEN=)[^ ]+',lambda x:x.group(1)+str(spec['atten_ohm']),deck)
    assert count==1
    if level is not None:
        for port,node,value in [('VD','d_src',level*3.3),('VDB','db_src',(1-level)*3.3)]:
            deck,count=re.subn(rf'(?m)^{port} {node} 0 PWL\([^)]*\)',f'{port} {node} 0 {value}',deck);assert count==1
        deck,count=re.subn(r'(?m)^tran .+$','op',deck);assert count==1
    (folder/'testbench.spice').write_text(deck)
    m.update(improvement_config=config,source_sha256={**m['source_sha256'],'driver.spice':run.sha(folder/'driver.spice')},
             deck_sha256=run.sha(folder/'testbench.spice'),candidate_spec=spec,
             wrapper_sha256=run.sha(Path(__file__)),analysis_sha256=run.sha(Path(analysis.__file__)),
             scope='New r10-derived schematic. Fixed850nm optical proxy,150fF,0.5ohm/0.2nH package,3/7mA targets,5GHz RX,25C TT and20ps input. Candidate changes only listed ATTEN/switch geometry; no new layout or PVT claim.')
    emit(folder/'manifest.json',m)
    return folder,m


def dc(name,level):
    folder,m=prepare(name,3.2,40,level)
    if (folder/'result.json').exists():return run.read_json(folder/'result.json')
    start=time.monotonic()
    with (folder/'ngspice.log').open('w') as f:
        code=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=f,stderr=subprocess.STDOUT,timeout=120).returncode
    raw=folder/'waveform.dat';r=dict(simulation_ok=code==0 and raw.exists(),exit_code=code,solve_s=time.monotonic()-start)
    if r['simulation_ok']:
        a=np.atleast_2d(np.loadtxt(raw,skiprows=1));assert np.isfinite(a).all()
        ix={expr:k+1 for k,expr in enumerate(m['expressions'])};assert a.shape[1]==len(ix)+1
        legacy=run.module(run.LEGACY,'vcsel_improvement_DC_stress')
        stress=legacy.stress(a,ix,m['devices']);current=float(a[-1,1]*1e3);target=3+4*level
        r.update(current_mA=current,target_mA=target,error_percent=100*(current/target-1),stress=stress,
                 terminal_screen_pass=all(s['screen_pass'] for s in stress),max_body_forward_V=max(s['max_body_forward_V'] for s in stress),
                 source_power_W={port:float(-a[-1,ix[f'v({node})']]*a[-1,ix[f'i({port})']]) for port,node in m['ports'].items()},
                 nodes_final_V={expr:float(a[-1,i]) for expr,i in ix.items() if expr.startswith('v(')},
                 waveform=legacy.compress(raw))
        r['DC_screen_pass']=bool(abs(r['error_percent'])<=1 and r['terminal_screen_pass'] and r['max_body_forward_V']<=.3)
    r.update(manifest_sha256=run.sha(folder/'manifest.json'),deck_sha256=run.sha(folder/'testbench.spice'),log_sha256=run.sha(folder/'ngspice.log'))
    emit(folder/'result.json',r);print('DC',name,level,r.get('current_mA'),r.get('DC_screen_pass'),flush=True)
    return r


def frame(name,rate,steps):
    for level in [0,1]:
        result=dc(name,level)
        if not result.get('DC_screen_pass'):raise RuntimeError('DC calibration/stress failed; retain evidence '+name)
    folder,m=prepare(name,rate,steps)
    if not (folder/'result.json').exists():run.solve(folder,m)
    result=run.read_json(folder/'result.json');assert result['simulation_ok']
    if (folder/'analysis.json').exists():
        met=run.read_json(folder/'analysis.json')
        assert met['result_sha256']==run.sha(folder/'result.json')
        return met
    rx=run.module(analysis.RX_PATH,'vcsel_improvement_rx');opto=run.module(analysis.OPTO_PATH,'vcsel_improvement_opto')
    met,traces=analysis.analyze(folder,rx,opto,False,128)
    obs=met['observed'];full=met['pathways']['actual_graph_5GHzRX']
    met.update(candidate=name,candidate_spec=SPECS[name],DC_calibration_pass=True,
               combined_screen_pass=bool(full['screen_pass'] and obs['terminal_screen_pass'] and obs['max_body_forward_V']<=.3 and obs['within_calibrated_electrical_and_optical_current_range']),
               result_sha256=run.sha(folder/'result.json'),manifest_sha256=run.sha(folder/'manifest.json'),wrapper_sha256=run.sha(Path(__file__)))
    emit(folder/'analysis.json',met)
    emit(folder/'excerpt.json',{k:v.tolist() for k,v in traces.items()})
    print('FRAME',name,rate,steps,'PASS',met['combined_screen_pass'],'err',full['errors'],'amp',full['worst_signed_margin_uAeq'],'UI',full['one_sided_margin_UI'],'pJ',met['source_energy_pJ_per_attempted_net_bit']['positive'],'range',obs['electrical_current_range_mA'],flush=True)
    return met


def summarize():
    rows=[];dcs=[]
    for p in sorted(BUILD.glob('*/DC-L*/result.json')):
        r=run.read_json(p);m=run.read_json(p.parent/'manifest.json')
        dcs.append(dict(candidate=m['improvement_config']['candidate'],level=m['improvement_config']['level'],source=str(p.relative_to(ROOT)),result_sha256=run.sha(p),**{k:r.get(k) for k in ['simulation_ok','current_mA','target_mA','error_percent','DC_screen_pass','terminal_screen_pass','max_body_forward_V']}))
    for p in sorted(BUILD.glob('*/net*/analysis.json')):
        r=run.read_json(p);full=r['pathways']['actual_graph_5GHzRX'];obs=r['observed']
        rows.append(dict(candidate=r['candidate'],net_Gbps=r['net_Gbps'],steps_per_UI=r['steps_per_UI'],combined_screen_pass=r['combined_screen_pass'],DC_calibration_pass=r['DC_calibration_pass'],full_receiver=full,
                         electrical_receiver=r['pathways']['actual_electrical'],stages=r['stages'],source_energy_pJ_per_attempted_net_bit=r['source_energy_pJ_per_attempted_net_bit'],observed=obs,
                         source_analysis=str(p.relative_to(ROOT)),analysis_sha256=run.sha(p),source_case=r['run'],result_sha256=r['result_sha256'],deck_sha256=r['deck_sha256'],waveform=r['waveform']))
    out=dict(schema='vcsel-real-driver-improvement-v1',scope='Same850nm load/optical proxy and5GHz RX; no new PVT/startup/layout/BER qualification.',
             candidates=SPECS,dc=dcs,rows=rows,source_sha256=run.sha(Path(__file__)),
             energy_scope='All7instantiated source port energies. Driver/reference/rail MOS included. External reference/regulator IC overhead, clock and RX not included.')
    emit(EV/'vcsel-improvement.json',out)
    return out


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',choices=SPECS);ap.add_argument('--rates',nargs='+',type=float);ap.add_argument('--steps',type=int,default=40);ap.add_argument('--summary',action='store_true');args=ap.parse_args()
    assert args.steps>=40
    if args.candidate:
        for level in [0,1]:dc(args.candidate,level)
        for rate in args.rates or []:frame(args.candidate,rate,args.steps)
    summarize()

if __name__=='__main__':main()
