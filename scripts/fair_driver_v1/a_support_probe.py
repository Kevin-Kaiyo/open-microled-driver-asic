#!/usr/bin/env python3
"""Bounded exploratory A support-rail probe; no physical/BER/qualification claim."""
from __future__ import annotations
import argparse
import fcntl
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'build/fair-driver-v1-a-probe'
SOURCE = ROOT / 'analog/fair_driver_v1/route_a.spice'
PDK = ROOT / 'build/nrz-reference-v2/selected-final-r2/inputs/pdk'
LED = ROOT / 'analog/models/measured-led/lin2026-yellow20-dc.spice'
LIMIT = 200 * 1024**2
MIN_FREE = 5 * 1024**3
LOCK = '/tmp/open-microled-nrz-ngspice.lock'
NODES = ['vh','vl','hset','lset','hpb','lpb','htail','ltail','hn1','ln1','hg','lg','di','n1','ctrl']

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def emit(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def usage():
    return sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()) if WORK.exists() else 0

def guard():
    if shutil.disk_usage(ROOT).free < MIN_FREE:
        raise RuntimeError('free space < 5 GiB; no simulation started')
    if usage() > LIMIT:
        raise RuntimeError('probe directory exceeds 200 MiB; preserve evidence and stop')

def freeze():
    guard()
    inputs = WORK / 'inputs'
    inputs.mkdir(parents=True, exist_ok=True)
    for src, dest in [(PDK/'design.ngspice',inputs/'design.ngspice'),
                      (PDK/'sm141064.ngspice',inputs/'sm141064.ngspice'),(LED,inputs/'led.spice')]:
        if dest.exists() and sha(src) != sha(dest):
            raise RuntimeError('frozen dependency drift: '+str(src))
        if not dest.exists():
            shutil.copy2(src,dest)
    return inputs

def run(name, rh, rl, mode='dc', bit=0, corner='typical', temp=27, vdd=3.3):
    inputs=freeze()
    folder=WORK/name
    folder.mkdir(exist_ok=False)
    shutil.copy2(SOURCE,folder/'route_a.spice')
    shutil.copy2(Path(__file__),folder/'executed_a_support_probe.py')
    # Only external stimulus sources/zero-V current sense exist in the testbench.
    if mode=='dc':
        data=str(bit*vdd); control='op'
    elif mode=='fast':
        data=f'PULSE(0 {vdd} 2n 100p 100p 1.9n 4n)'
        control='tran 10p 200n 0 10p'
    elif mode=='step':
        data=f'PULSE(0 {vdd} 10u 100p 100p 20u 40u)'
        control='tran 5n 50u 0 5n'
    elif mode=='startup':
        data=f'PWL(0 0 1u {bit*vdd})'
        control='tran 1u 1m 0 1u'
    else:
        raise ValueError(mode)
    vectors=['v(d0)','v(out)','v(led_k)','i(VSENSE)','i(LPKG)','i(VIN)','i(VDD)','i(VREF)','i(VD0)']
    vectors += [f'v(xa.{n})' for n in NODES]
    supplies={'VIN':'5','VDD':str(vdd),'VREF':'2.5'}
    if mode=='startup':
        supplies={k:f'PWL(0 0 1u {v})' for k,v in supplies.items()}
    deck=f'''A dissipative actual-MOS support rails {name}
.include "{inputs/'design.ngspice'}"
.param sw_stat_global=0 sw_stat_mismatch=0
.lib "{inputs/'sm141064.ngspice'}" {corner}
.lib "{inputs/'sm141064.ngspice'}" res_{corner}
.include "route_a.spice"
.include "{inputs/'led.spice'}"
.temp {temp}
VIN vin 0 {supplies['VIN']}
VDD vdd 0 {supplies['VDD']}
VREF vref 0 {supplies['VREF']}
VD0 d0 0 {data}
XA d0 0 out vin vdd vref 0 0 fair_a RH={rh:.16g} RL={rl:.16g}
XLED vin led_dc_k lin2026_yellow20_dc
VSENSE led_dc_k led_k 0
CLED vin led_k 200f
RPKG led_k pkg 1
LPKG pkg out .5n
.options reltol=1e-4 abstol=1e-13 vntol=1e-7 chgtol=1e-18 method=gear maxord=2
.control
set numdgt=15
set wr_singlescale
set wr_vecnames
{control}
wrdata waveform.dat {' '.join(vectors)}
quit
.endc
.end
'''
    (folder/'testbench.spice').write_text(deck)
    result=dict(name=name,mode=mode,bit=bit,RH_ohm=rh,RL_ohm=rl,corner=corner,temp_C=temp,vdd_V=vdd,
                source_sha256=sha(folder/'route_a.spice'),deck_sha256=sha(folder/'testbench.spice'),
                runner_sha256=sha(__file__),dependencies={p.name:sha(p) for p in inputs.iterdir()},vectors=vectors)
    start=time.monotonic()
    with open(LOCK,'a') as lock, (folder/'ngspice.log').open('w') as log:
        fcntl.flock(lock,fcntl.LOCK_EX)
        guard()
        result['lock_wait_s']=time.monotonic()-start
        try:
            p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=log,stderr=subprocess.STDOUT,timeout=90)
            result['exit_code']=p.returncode
        except subprocess.TimeoutExpired:
            result['exit_code']='timeout'
    result['elapsed_s']=time.monotonic()-start
    result['log_sha256']=sha(folder/'ngspice.log')
    raw=folder/'waveform.dat'
    if raw.exists():
        result['raw_sha256']=sha(raw);result['raw_bytes']=raw.stat().st_size
        a=np.loadtxt(raw,skiprows=1,ndmin=2)
        result['rows']=len(a)
        values={key:a[:,i+1] for i,key in enumerate(vectors)}
        result['last']={k:float(v[-1]) for k,v in values.items()}
        result['ranges']={k:[float(v.min()),float(v.max())] for k,v in values.items()}
        p_total=-5*values['i(VIN)']-vdd*values['i(VDD)']-2.5*values['i(VREF)']-values['v(d0)']*values['i(VD0)']
        if mode=='dc':
            result['power_W']=float(p_total[-1])
        else:
            t=a[:,0];mask=t>=t[-1]/2
            result['power_mean_second_half_W']=float(np.trapezoid(p_total[mask],t[mask])/(t[mask][-1]-t[mask][0]))
            result['window_s']=[float(t[mask][0]),float(t[mask][-1])]
            for rail,v in [("VIN",5),("VDD",vdd),("VREF",2.5)]:
                power=-v*values[f'i({rail})'][mask]
                result[f'{rail}_mean_second_half_W']=float(np.trapezoid(power,t[mask])/(t[mask][-1]-t[mask][0]))
            if mode=='startup':
                target=(25e-6,100e-6)[bit]
                outside=(np.abs(values['i(VSENSE)']-target)>.05*target)&(t>=1e-6)
                result['startup_current_target_A']=target
                result['startup_sampled_peak_A']=float(values['i(VSENSE)'].max())
                result['startup_last_outside_after_rails_full_s']=float(t[outside][-1]-1e-6) if outside.any() else 0.
                result['startup_end_in_band']=bool(abs(values['i(VSENSE)'][-1]/target-1)<=.05)
                result['startup_boundary']='Common 1us source ramp; 1us maximum step, sampled peak, 1ms endpoint; no autonomous protection implemented.'
        with raw.open('rb') as src,gzip.open(folder/'waveform.dat.gz','wb',compresslevel=6) as dst:
            shutil.copyfileobj(src,dst)
        result['gzip_sha256']=sha(folder/'waveform.dat.gz')
        raw.unlink()
    emit(folder/'result.json',result)
    if result['exit_code']!=0 or 'last' not in result:
        raise RuntimeError('failed probe retained: '+str(folder))
    guard()
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('action',choices=['dc','calibrate','fast','step','startup'])
    ap.add_argument('--name',required=True)
    ap.add_argument('--rh',type=float,default=180000)
    ap.add_argument('--rl',type=float,default=88000)
    ap.add_argument('--bit',type=int,choices=[0,1],default=0)
    args=ap.parse_args()
    if args.action!='calibrate':
        result=run(args.name,args.rh,args.rl,args.action,args.bit)
        print(json.dumps({k:result[k] for k in ['name','last','power_W','power_mean_second_half_W'] if k in result},indent=2))
        return
    # One TT calibration only; RH targets I0, RL targets I1. No PVT retuning.
    rh,rl=args.rh,args.rl
    history=[]
    for iteration in range(4):
        r0=run(f'{args.name}-{iteration}-b0',rh,rl,bit=0)
        r1=run(f'{args.name}-{iteration}-b1',rh,rl,bit=1)
        measured=np.array([r0['last']['i(VSENSE)'],r1['last']['i(VSENSE)']])
        target=np.array([25e-6,100e-6]);error=measured-target
        history.append(dict(iteration=iteration,RH_ohm=rh,RL_ohm=rl,current_A=measured.tolist(),error_fraction=(error/target).tolist()))
        print(json.dumps(history[-1]),flush=True)
        if np.max(np.abs(error/target))<0.001:
            break
        # Small fixed fractional perturbations determine the local two-knob Jacobian.
        dH=rh*.001;dL=rl*.001
        h0=run(f'{args.name}-{iteration}-dh0',rh+dH,rl,bit=0)
        h1=run(f'{args.name}-{iteration}-dh1',rh+dH,rl,bit=1)
        l0=run(f'{args.name}-{iteration}-dl0',rh,rl+dL,bit=0)
        l1=run(f'{args.name}-{iteration}-dl1',rh,rl+dL,bit=1)
        jac=np.column_stack(((np.array([h0['last']['i(VSENSE)'],h1['last']['i(VSENSE)']])-measured)/dH,
                             (np.array([l0['last']['i(VSENSE)'],l1['last']['i(VSENSE)']])-measured)/dL))
        change=np.linalg.solve(jac,-error)
        if np.any(np.abs(change/np.array([rh,rl]))>.2):
            raise RuntimeError('TT calibration step exceeds 20%; retained candidate needs review')
        rh+=float(change[0]);rl+=float(change[1])
    emit(WORK/(args.name+'-calibration.json'),dict(history=history,RH_ohm=history[-1]['RH_ohm'],RL_ohm=history[-1]['RL_ohm'],
         pass_current=bool(np.max(np.abs(np.array(history[-1]['error_fraction'])))<0.001),calibration_scope='TT27C only; no PVT per-point tuning'))

if __name__=='__main__':
    main()
