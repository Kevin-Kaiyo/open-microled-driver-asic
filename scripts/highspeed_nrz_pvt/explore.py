#!/usr/bin/env python3
"""Candidate experiments with immutable original load/stimulus/receiver contract."""
from pathlib import Path
import argparse,json,shutil,sys
import run as r
ROOT=r.ROOT
BASE=ROOT/'build/highspeed-nrz-pex/run-0m3zyewc'

def fet(name,d,g,s,b,typ,w,l=.28):
    return f'X{name} {d} {g} {s} {b} {typ}fet_03v3 w={w:g}u l={l:g}u ad={w*.44:g}p as={w*.44:g}p pd={2*(w+.44):g}u ps={2*(w+.44):g}u'

def circuit(route,cfg):
    allowed={'rin','poly_l','inv1','inv2','output','capw','rails','rref_source','rref_ohm','switch'}
    if set(cfg)-allowed:raise ValueError('Unknown candidate keys '+str(set(cfg)-allowed))
    if cfg.get('rin') and cfg.get('poly_l'):raise ValueError('rin and poly_l are mutually exclusive')
    if cfg.get('rref_source','vdd') not in ['vdd','vdummy']:raise ValueError('Unaccounted reference source')
    lines=['* Candidate: isolated diffusion geometry estimate 0.44um, not PEX.']
    if route=='A':
        lines+=['.subckt hs_voltage_pvt DATA OUT VDD VH VL VSS']
        n1,p1=cfg.get('inv1',[1,2]);n2,p2=cfg.get('inv2',[4,8]);no,po=cfg.get('output',[4,8])
        first='DATA'
        if cfg.get('rin'):
            lines+= [f'RIN DATA DI {cfg["rin"]}'];first='DI'
        if cfg.get('poly_l'):
            lines+=[f'XRIN DATA DI VSS ppolyf_u_1k_6p0 r_width=1u r_length={cfg["poly_l"]}u'];first='DI'
        for args in [('N1','N1',first,'VSS','VSS','n',n1),('P1','N1',first,'VDD','VDD','p',p1),('N2','CTRL','N1','VSS','VSS','n',n2),('P2','CTRL','N1','VDD','VDD','p',p2),('NOUT','OUT','CTRL','VL','VSS','n',no),('POUT','OUT','CTRL','VH','VH','p',po)]:lines.append(fet(*args))
        if cfg.get('capw'):lines.append(fet('CAP','VSS','N1','VSS','VSS','n',cfg['capw']))
        lines+=['.ends hs_voltage_pvt']
    else:
        lines+=['.subckt hs_steering_pvt DATA OUT VDD VSS BIAS DUMMY']
        n1,p1=cfg.get('inv1',[1,2]);n2,p2=cfg.get('inv2',[1,2]);ws=cfg.get('switch',1)
        first='DATA'
        if cfg.get('rin'):
            lines+= [f'RIN DATA DI {cfg["rin"]}'];first='DI'
        if cfg.get('poly_l'):
            lines+=[f'XRIN DATA DI VSS ppolyf_u_1k_6p0 r_width=1u r_length={cfg["poly_l"]}u'];first='DI'
        for args in [('REF','BIAS','BIAS','VSS','VSS','n',2,1),('BASE','OUT','BIAS','VSS','VSS','n',2,1),('TAIL','VX','BIAS','VSS','VSS','n',5.76,1),('LED','OUT','GP','VX','VSS','n',ws),('DUMMY','DUMMY','GB','VX','VSS','n',ws),('INV1N','GB',first,'VSS','VSS','n',n1),('INV1P','GB',first,'VDD','VDD','p',p1),('INV2N','GP','GB','VSS','VSS','n',n2),('INV2P','GP','GB','VDD','VDD','p',p2)]:lines.append(fet(*args))
        if cfg.get('capw'):lines.append(fet('CAP','VSS','GB','VSS','VSS','n',cfg['capw']))
        lines+=['.ends hs_steering_pvt']
    return '\n'.join(lines)+'\n'

def create(work):
    work.mkdir(parents=True,exist_ok=True)
    if (work/'manifest.json').exists():return
    old=json.loads((BASE/'manifest.json').read_text()); inputs=work/'inputs'
    for file in ['legacy/run.py','legacy/metrics.py','legacy/analyze.py','led.spice','pdk/design.ngspice','pdk/sm141064.ngspice']:
        dst=inputs/file;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BASE/'inputs'/file,dst)
    shutil.copy2(BASE/'stimulus.json',work/'stimulus.json')
    r.emit(work/'manifest.json',{'common':old['common'],'route_a_rails':old['route_a_rails'],'variants':{'A':{},'B':{}},'physical_contract':{},'inputs':{str(p.relative_to(inputs)):r.sha(p) for p in inputs.rglob('*') if p.is_file()},'baseline':r.rel(BASE)})

def add(work,route,label,cfg):
    create(work);m=json.loads((work/'manifest.json').read_text());dst=work/'inputs/candidates'/f'{route}-{label}.spice';dst.parent.mkdir(parents=True,exist_ok=True)
    txt=circuit(route,cfg)
    if dst.exists() and dst.read_text()!=txt:raise ValueError('Immutable candidate changed')
    definition={'path':str(dst.relative_to(work/'inputs')),'config':cfg,'rref_source':cfg.get('rref_source','vdd'),'rref_ohm':cfg.get('rref_ohm',88386.1064910889),'sha256':r.sha(dst) if dst.exists() else __import__('hashlib').sha256(txt.encode()).hexdigest()}
    if 'rails' in cfg:definition['rails']=cfg['rails']
    old=m['variants'][route].get(label)
    if old and any(old.get(k)!=definition.get(k) for k in ['config','path','sha256','rref_source']):raise ValueError('Immutable candidate definition changed')
    dst.write_text(txt);m['variants'][route][label]=definition
    r.emit(work/'manifest.json',m)

def metrics(work,result):
    path=work/'cases'/result['case']['name']/'result.json';cache=path.with_name('analysis.json')
    identity={'result_sha256':r.sha(path),'metrics_sha256':r.sha(work/'inputs/legacy/metrics.py'),'analyzer_sha256':r.sha(work/'inputs/legacy/analyze.py'),'stimulus_sha256':r.sha(work/'stimulus.json')}
    if cache.exists():
        old=json.loads(cache.read_text())
        if old.get('analysis_identity')==identity:return old['row']
        if old.get('analysis_identity'):raise ValueError('Cached analysis inputs changed')
        # Earlier exploratory cache has no identity: recompute from hash-checked trace.

    r.module(work/'inputs/legacy/metrics.py','metrics');a=r.module(work/'inputs/legacy/analyze.py','frozen_analysis');a.ROOT=ROOT
    rec={'case':result['case'],'simulation_ok':result['simulation_ok'],'analysis_ok':False}
    if result['simulation_ok']:
        trace,sources=a.load_trace(result,path);rec['sources']=sources;rec['stress']=a.stress_metrics(trace,result)
        rec['resistor_terminal_voltages']=[]
        for d in result.get('passives',[]):
            import numpy as np
            nv=[np.zeros(len(trace)) if n=='0' else trace[:,result['vectors'][n]] for n in d['nodes']]
            rec['resistor_terminal_voltages'].append(d|{'maximum_abs_terminal_difference_V':max(float(np.max(np.abs(nv[i]-nv[j]))) for i,j in [(0,1),(0,2),(1,2)]),'scope':'record only; no foundry reliability signoff'})
        if 'dc_bit' in result['case']:rec['dc']=a.dc_metrics(trace,result)
        else:rec['transient']=a.transient_metrics(trace,result,json.loads((work/'stimulus.json').read_text()))
        rec['analysis_ok']=True
    row=a.compact_row(rec);row['variant']=result['case']['variant'];row['result_json']=r.rel(path);row['analysis_json']=r.rel(cache)
    if 'comparison_screen_passed' in row:row['combined_screen_passed']=row['comparison_screen_passed'] and not row['above_3p63V_screen']
    rec['row']=row;rec['analysis_identity']=identity;r.emit(cache,rec);return row

def execute(work,route,label,conditions=None):
    conditions=conditions or [('slow_hot','ss',125,3.0),('fast_cold','ff',-40,3.6)]
    rows=[]
    for kind,corner,temp,vdd in conditions:
        c=r.case_spec(work,route,label,2 if route=='A' else .5,kind=kind,corner=corner,temp_C=temp,vdd_V=vdd)
        out=metrics(work,r.run_case(work,c));rows.append(out);print(json.dumps({k:out.get(k) for k in ['name','errors','threshold_margin_normalized','timing_min_margin_ui','max_abs_terminal_V','rail_plus_DATA_positive_draw_fJ_per_gross_bit','combined_screen_passed']}),flush=True)
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--route',choices=['A','B']);p.add_argument('--label');p.add_argument('--config',default='{}');p.add_argument('--work',default='build/highspeed-nrz-pvt/explore');a=p.parse_args();w=ROOT/a.work
    add(w,a.route,a.label,json.loads(a.config));execute(w,a.route,a.label)
if __name__=='__main__':main()
