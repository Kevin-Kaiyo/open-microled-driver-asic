"""Independent fault interlock: actual RTL plus new MOS gate / frozen joint PEX.

Every run freezes its input bytes. New safety CMOS is pre-layout and recovery
storage is RTL only; no existing electrical or physical evidence is overwritten.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
PDK=ROOT/'build/layout/pdk/gf180mcuD'
ENVS={'tt':('typical',27,3.3,5), 'ss':('ss',85,2.97,4.5), 'ff':('ff',0,3.63,5.5)}
VECTORS=['v(raw_pwm)','v(fault_pin)','v(permit)','v(input)','v(pwm)','v(gate)',
         'v(bias)','v(led_k)','i(VLEDLOAD)','i(VSUPSAFE)','i(VREFRAIL)',
         'i(VREFLOAD)','v(xsafe.fault_b)','v(xsafe.nand_n)',
         'v(xsafe.stack1)','v(xsafe.stack2)','v(xjoint.gate.t2)',
         'v(xjoint.led_k.t0)','v(xjoint.bias.t1)','v(xjoint.bias.t2)',
         'v(xjoint.ANALOG_PWM.t6)','v(xjoint.pwm_b.t2)','v(unused_safe)',
         'v(clamp_anode)','v(xclamp.fault_hb)','i(VCLAMPSUP)',
         '@d.xled.dled[id]','@d.xled.dled[capcur]','@m.xjoint.x10.m0[id]']
IDX={name:i+1 for i,name in enumerate(VECTORS)}
NEW_DEVICES=[
 ('XFN','fault_b','fault','0','0'),('XFP','fault_b','fault','vdd','vdd'),
 ('XNP0','nand_n','raw','vdd','vdd'),('XNP1','nand_n','permit','vdd','vdd'),
 ('XNP2','nand_n','fault_b','vdd','vdd'),('XNN0','nand_n','raw','stack1','0'),
 ('XNN1','stack1','permit','stack2','0'),('XNN2','stack2','fault_b','0','0'),
 ('XON','out','nand_n','0','0'),('XOP','out','nand_n','vdd','vdd')]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def command(args,folder,log):
    p=subprocess.run([str(a) for a in args],cwd=folder,text=True,capture_output=True)
    text=p.stdout+p.stderr;(folder/log).write_text(text)
    if p.returncode or (str(args[0])=='ngspice' and re.search(r'(?im)^Error:|timestep too small|simulation interrupted',text)):
        raise RuntimeError('Command failed: '+str(folder/log))
    return text

def clip(t,y,left,right):
    tol=8*abs(np.spacing(max(abs(right),abs(t[-1]))))
    if not np.isfinite(y).all() or np.any(np.diff(t)<=0) or t[0]>left+tol or t[-1]<right-tol:
        raise RuntimeError('Incomplete waveform window')
    m=(t>left)&(t<right)
    return np.r_[left,t[m],right],np.r_[np.interp(left,t,y),y[m],np.interp(right,t,y)]

def integral(t,y,left,right):
    x,v=clip(t,y,left,right)
    return float(np.sum(np.diff(x)*(v[:-1]+v[1:])/2))

def split_charge(t,y,left,right):
    x,v=clip(t,y,left,right)
    k=np.flatnonzero(v[:-1]*v[1:]<0)
    roots=x[k]-v[k]*(x[k+1]-x[k])/(v[k+1]-v[k])
    z=np.unique(np.r_[x,roots]);w=np.interp(z,x,v)
    q=np.diff(z)*(w[:-1]+w[1:])/2
    return {'signed_c':float(q.sum()),'positive_c':float(q[q>0].sum()),'negative_c':float(q[q<0].sum())}

def stable_below_time(t,y,start,end,threshold):
    x,v=clip(t,np.abs(y),start,end)
    k=np.flatnonzero(v>threshold)
    if not len(k):return start
    j=int(k[-1])
    if j+1==len(v):return None
    return float(x[j]+(threshold-v[j])*(x[j+1]-x[j])/(v[j+1]-v[j]))

def fall_crossing(t,y,start,end,threshold):
    x,v=clip(t,y,start,end)
    k=np.flatnonzero((v[:-1]>threshold)&(v[1:]<=threshold))
    if not len(k):return start if v[0]<=threshold else None
    j=int(k[0]);return float(x[j]+(threshold-v[j])*(x[j+1]-x[j])/(v[j+1]-v[j]))

def read_events(p):
    with p.open() as f:rows=list(csv.DictReader(f))
    # Several delta-cycle updates share a timestamp. Keep the last complete row.
    bytime={float(r['time_ns']):r for r in rows}
    return [bytime[t] for t in sorted(bytime)]

def pwl_signal(rows,key,voltage,stop_ns):
    initial=1 if key=='fault' else 0
    events=[(0.,initial)];state=initial
    for row in rows:
        if row[key] not in ['0','1']:continue
        value=int(row[key]);t=float(row['time_ns'])
        if value!=state:
            events.append((t,value));state=value
    points=[(0,events[0][1]*voltage)]
    for t,value in events[1:]:
        if t+10>=stop_ns:break
        points.extend([(t*1e-9,points[-1][1]),((t+10)*1e-9,value*voltage)])
    points.append((stop_ns*1e-9,points[-1][1]))
    return 'PWL(\n'+'\n'.join(f'+ {t:.17g} {v:.17g}' for t,v in points)+'\n+)'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish-evidence',action='store_true')
    parser.add_argument('--only',help='debug subset case-name; never published')
    parser.add_argument('--reference-path',type=Path)
    parser.add_argument('--servo-path',type=Path)
    parser.add_argument('--suite',choices=['core','servo','all'],default='all')
    args=parser.parse_args()
    if args.only and args.publish_evidence:raise RuntimeError('A debug subset cannot publish complete evidence')
    contract_path=ROOT/'evidence/safety/contract.json'
    safety_contract=json.loads(contract_path.read_text());limits=safety_contract['thresholds']
    clamp_contract=json.loads((ROOT/'evidence/safety/clamp-contract.json').read_text())
    stage_path=ROOT/'evidence/robustness/stage-contract.json'
    stage=json.loads(stage_path.read_text());model=ROOT/stage['model_path']
    if sha(model)!=stage['model_sha256']:raise RuntimeError('Old selected signal model changed')
    for p,h in stage['required_inputs_sha256'].items():
        if sha(ROOT/p)!=h:raise RuntimeError('Old extraction provenance changed: '+p)
    for lock in ['layout/pdk-lock.json','scripts/physical/pdk-lock.json']:
        for p,h in json.loads((ROOT/lock).read_text())['files'].items():
            if sha(PDK/p)!=h:raise RuntimeError('Pinned PDK changed: '+p)
    (ROOT/'build/safety').mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='fault-gate-',dir=ROOT/'build/safety'))
    sources=['scripts/safety/run.py','evidence/safety/contract.json','rtl/safety/pixel_safety.v',
             'sim/safety/tb_safety.v','sim/safety/normal_observer.v','analog/safety/fault_gate.spice',
             'analog/safety/fault_led_clamp.spice','evidence/safety/clamp-contract.json',
             'rtl/pixel_pwm.v','sim/rtl/tb_pixel_pwm.v','analog/models/microled.spice',
             'evidence/robustness/stage-contract.json',stage['model_path'],
             'layout/pdk-lock.json','scripts/physical/pdk-lock.json']
    sources+=list(stage['required_inputs_sha256'])
    references={}
    if args.reference_path:
        references['beta']=args.reference_path.resolve()
    if args.servo_path:
        references['servo']=args.servo_path.resolve()
    for reference in references.values():sources.append(str(reference.relative_to(ROOT)))
    hashes={}
    for name in dict.fromkeys(sources):
        src=ROOT/name;dst=work/'inputs'/name;dst.parent.mkdir(parents=True,exist_ok=True)
        h=sha(src);shutil.copyfile(src,dst)
        if sha(dst)!=h or sha(src)!=h:raise RuntimeError('Input changed during freeze: '+name)
        hashes[name]=h
    frozen=work/'inputs'
    (work/'input-manifest.json').write_text(json.dumps(hashes,indent=2)+'\n')
    tools={'ngspice':command(['ngspice','--version'],work,'ngspice-version.log'),
           'iverilog':command(['iverilog','-V'],work,'iverilog-version.log')}
    overall_checks=[]
    def check(name,passed,**more):
        overall_checks.append({'name':name,'passed':bool(passed),**more})
    if not args.only:
        normal=work/'normal-observer.vvp'
        command(['iverilog','-g2012','-s','tb_pixel_pwm','-s','safety_normal_observer','-o',normal,
                 frozen/'rtl/pixel_pwm.v',frozen/'sim/rtl/tb_pixel_pwm.v',
                 frozen/'rtl/safety/pixel_safety.v',frozen/'sim/safety/normal_observer.v'],work,'normal-compile.log')
        log=command(['vvp',normal,f'+OUT={work/"normal-base-events.csv"}'],work,'normal-rtl.log')
        check('Unmodified exhaustive PWM regression plus protected normal observation',
              'PASS pixel_pwm:' in log and 'SAFETY_NORMAL_PASS' in log)
    binary=work/'safety.vvp'
    command(['iverilog','-g2012','-s','tb_safety','-o',binary,frozen/'rtl/pixel_pwm.v',
             frozen/'rtl/safety/pixel_safety.v',frozen/'sim/safety/tb_safety.v'],work,'fault-compile.log')
    cases=[]
    for d in [0,1,64,255,256]:cases.append(dict(name=f'normal_d{d}',duty=d,fault_ns=-1,stop_ns=-1,stop_time_ns=1070000,envelope='tt'))
    for name,d,f in [('d1_phase125',1,514625),('d1_phase375',1,514875),('d64_phase250',64,530750),
                      ('d255_phase999',255,714999),('d256_phase123',256,520123),('d1_off_phase',1,517250)]:
        cases.append(dict(name='fault_'+name,duty=d,fault_ns=f,stop_ns=-1,stop_time_ns=f+16000,envelope='tt'))
    for name,stop,f in [('stop_high',17700,20125),('stop_low',18200,20999)]:
        cases.append(dict(name=name,duty=256,fault_ns=f,stop_ns=stop,stop_time_ns=f+16000,envelope='tt'))
    for env in ['ss','ff']:
        cases.append(dict(name='fault_'+env,duty=256,fault_ns=20125,stop_ns=-1,stop_time_ns=36125,envelope=env))
    cases.append(dict(name='disconnected_fault',duty=256,fault_ns=20125,stop_ns=-1,stop_time_ns=36125,envelope='tt',disconnect=True))
    cases.append(dict(name='negative_stopped_no_gate',duty=256,fault_ns=20125,stop_ns=18000,stop_time_ns=36125,envelope='tt',negative=True))
    cases.append(dict(name='direct_fault_stale_permit',duty=256,fault_ns=20125,stop_ns=18000,stop_time_ns=36125,envelope='tt',stale_permit=True))
    cases.append(dict(name='fault_d256_early',duty=256,fault_ns=20125,stop_ns=-1,stop_time_ns=36125,envelope='tt'))
    if 'beta' in references:cases.append(dict(name='reference_joint_fault',duty=256,fault_ns=520123,stop_ns=-1,stop_time_ns=536123,envelope='tt',reference='beta'))
    if 'servo' in references:
        cases.append(dict(name='servo_normal_d1',duty=1,fault_ns=-1,stop_ns=-1,stop_time_ns=1070000,envelope='tt',reference='servo'))
        cases.append(dict(name='servo_normal_d1_fine',duty=1,fault_ns=-1,stop_ns=-1,stop_time_ns=1070000,envelope='tt',reference='servo',maxstep_ns=2))
        cases.append(dict(name='servo_stopped_fault',duty=256,fault_ns=50125,stop_ns=47700,stop_time_ns=66125,envelope='tt',reference='servo'))
        cases.append(dict(name='servo_stopped_fault_fine',duty=256,fault_ns=50125,stop_ns=47700,stop_time_ns=66125,envelope='tt',reference='servo',maxstep_ns=2))
        cases.append(dict(name='servo_startup_default_fault',duty=256,fault_ns=-1,stop_ns=-1,stop_time_ns=40000,envelope='tt',reference='servo',reference_ramp=True,initial_fault_clear_ns=20000))
        cases.append(dict(name='servo_startup_default_fault_fine',duty=256,fault_ns=-1,stop_ns=-1,stop_time_ns=40000,envelope='tt',reference='servo',reference_ramp=True,initial_fault_clear_ns=20000,maxstep_ns=2))
    cases.append(dict(name='normal_d1_fine',duty=1,fault_ns=-1,stop_ns=-1,stop_time_ns=1026500,envelope='tt',maxstep_ns=1))
    cases.append(dict(name='fault_d256_fine',duty=256,fault_ns=20125,stop_ns=-1,stop_time_ns=36125,envelope='tt',maxstep_ns=1))
    if args.suite=='core':cases=[c for c in cases if c.get('reference')!='servo']
    if args.suite=='servo':cases=[c for c in cases if c.get('reference')=='servo']
    if args.only:cases=[c for c in cases if c['name']==args.only]
    if not cases:raise RuntimeError('Unknown --only case')
    for c in cases:
        target=work/c['name'];target.mkdir()
        rows_path=target/'rtl-events.csv'
        log=command(['vvp',binary,f'+DUTY={c["duty"]}',f'+FAULT_NS={c["fault_ns"]}',
                     f'+STOP_NS={c["stop_ns"]}',f'+STOP_TIME_NS={c["stop_time_ns"]}',
                     f'+INITIAL_FAULT_CLEAR_NS={c.get("initial_fault_clear_ns",100)}',f'+OUT={rows_path}'],target,'rtl.log')
        check('RTL assertion / hold / recovery '+c['name'],'SAFETY_CASE_PASS' in log)
        c['rows']=read_events(rows_path)
    led_is=100e-6/math.expm1((2.8-100e-6*50)/(3*8.617333262145e-5*300.15))
    def spice_folder(name):
        target=work/name;target.mkdir(exist_ok=True)
        for p in ['design.ngspice','sm141064.ngspice']:
            link=target/p
            if not link.exists():link.symlink_to(os.path.relpath(PDK/'libs.tech/ngspice'/p,target))
        return target
    cal=spice_folder('led-calibration')
    deck=f'''Independent inherited synthetic LED calibration
.param LED_IS={led_is:.17g}
.include "{frozen/'analog/models/microled.spice'}"
IREF 0 anode 100u
XLED anode 0 microled
.options reltol=1e-9 abstol=1e-14 vntol=1e-10
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
op
wrdata calibration.dat v(anode)
quit
.endc
.end
'''
    (cal/'testbench.spice').write_text(deck);command(['ngspice','-b','testbench.spice'],cal,'ngspice.log')
    cal_v=float(np.atleast_2d(np.loadtxt(cal/'calibration.dat',skiprows=1))[0,1])
    check('Unchanged synthetic LED calibrates at 100 uA / 27 C',abs(cal_v-2.8)<1e-5,voltage_v=cal_v)
    def make_deck(c,dc_level=None):
        mos,temp,logic,led=ENVS[c['envelope']];stop=c['stop_time_ns'];rows=c.get('rows',[])
        raw=pwl_signal(rows,'raw_pwm',logic,stop) if dc_level is None else str(logic*dc_level)
        fault=pwl_signal(rows,'fault',logic,stop) if dc_level is None else '0'
        permit=pwl_signal(rows,'permit',logic,stop) if dc_level is None else str(logic)
        if c.get('stale_permit'):permit=str(logic)
        fault_fixture=f'VFAULT fault_pin 0 {fault}'
        if c.get('disconnect'):
            f=c['fault_ns']*1e-9
            fault_fixture=f'''VFAULTDRIVE fault_drive 0 0
VCONNECT connect 0 PWL(0 {logic} {f:.17g} {logic} {f+10e-9:.17g} 0 {stop*1e-9:.17g} 0)
SFAULT fault_pin fault_drive connect 0 disconnect_switch
.model disconnect_switch SW(Ron=1 Roff=1e15 Vt={logic/2} Vh=0)'''
        ref='BIREF refrail refout I=100u'
        if c.get('reference'):
            reference=references[c['reference']]
            if c['reference']=='beta':ref=f'''.lib sm141064.ngspice res_typical
.include "{frozen/reference.relative_to(ROOT)}"
XREF refrail 0 refout beta_reference RL=13.5u'''
            else:ref=f'''.include "{frozen/reference.relative_to(ROOT)}"
VSET vset 0 .5
RSET sense 0 5k
XREF refrail 0 vset sense refout vset_reference'''
        neighbor='\n'.join(f'VN{n} {row["node"]} 0 0' for n,row in enumerate(stage['neighbor_sources']))
        pins=' '.join(stage['pin_bindings'][p] for p in stage['ports_order'])
        safe='XSAFE raw_pwm fault_pin permit input safety_vdd 0 fault_gate\nBUNUSED unused_safe 0 V=v(input)'
        if c.get('negative'):
            safe='* Deliberate no-protection negative control\nBNO input 0 V=v(raw_pwm)\nXSAFE raw_pwm fault_pin permit unused_safe safety_vdd 0 fault_gate'
        ctl='op' if dc_level is not None else f'tran 10n {stop}n 0 {c.get("maxstep_ns",10)}n'
        return f'''New pre-layout GF180 fault gate + frozen selected joint signal PEX
.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0 LED_IS={led_is:.17g}
.lib sm141064.ngspice {mos}
.temp {temp}
VSUPSAFE safety_vdd 0 {logic}
VLOGIC vbuffer 0 {logic}
VREFRAIL refrail 0 {'PWL(0 0 100n '+str(logic)+')' if c.get('reference_ramp') else str(logic)}
{ref}
VREFLOAD refout bias 0
VLED rail 0 {led}
VLEDLOAD rail led_anode 0
VCLAMPSUP rail clamp_anode 0
VRAW raw_pwm 0 {raw}
VPERMIT permit 0 {permit}
{fault_fixture}
RFAULTPULLUP safety_vdd fault_pin 1Meg
.include "{frozen/'analog/safety/fault_gate.spice'}"
{safe}
.include "{frozen/'analog/safety/fault_led_clamp.spice'}"
XCLAMP {'0' if c.get('negative') else 'fault_pin'} clamp_anode led_k 0 fault_led_clamp
.include "{frozen/'analog/models/microled.spice'}"
XLED led_anode led_k microled
{neighbor}
.include "{frozen/stage['model_path']}"
XJOINT {pins} {stage['subckt']}
.options reltol=1e-7 abstol=1e-14 vntol=1e-9 method=gear maxord=2
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
save all @d.xled.dled[id] @d.xled.dled[capcur] @m.xjoint.x10.m0[id]
{'option reltol=1e-6 abstol=1e-12 vntol=1e-7 method=trap' if c.get('reference')=='servo' and dc_level is None else '* Strict original numeric options retained'}
{ctl}
wrdata waveform.dat {' '.join(VECTORS)}
quit
.endc
.end
'''
    dc={}
    for env,kind in sorted(set((c['envelope'],c.get('reference','ideal')) for c in cases)):
        for level in [0,1]:
            c=dict(envelope=env,stop_time_ns=0)
            if kind!='ideal':c['reference']=kind
            target=spice_folder(f'dc_{env}_{kind}_{level}');(target/'testbench.spice').write_text(make_deck(c,level))
            command(['ngspice','-b','testbench.spice'],target,'ngspice.log')
            data=np.atleast_2d(np.loadtxt(target/'waveform.dat',skiprows=1));dc[env,kind,level]=float(data[0,IDX['i(VLEDLOAD)']])
            check(f'DC {env} {kind} level {level}',abs(dc[env,kind,level]/100e-6-1)<=.05 if level else abs(dc[env,kind,level])<1e-9,current_a=dc[env,kind,level])
    def run_case(c):
        target=spice_folder(c['name']);(target/'testbench.spice').write_text(make_deck(c))
        command(['ngspice','-b','testbench.spice'],target,'ngspice.log')
        data=np.atleast_2d(np.loadtxt(target/'waveform.dat',skiprows=1))
        if data.shape[1]!=len(VECTORS)+1:raise RuntimeError('Waveform columns changed')
        t=data[:,0];current=data[:,IDX['i(VLEDLOAD)']];full=dc[c['envelope'],c.get('reference','ideal'),1]
        out={'name':c['name'],'conditions':{k:v for k,v in c.items() if k!='rows'},'dc_full_a':full,'analog_input_slew_s':10e-9}
        checks=[]
        def chk(name,ok,**extra):checks.append(dict(name=name,passed=bool(ok),**extra))
        if c['fault_ns']<0 and not c.get('reference_ramp'):
            left=514.5e-6;right=1026.5e-6
            q=integral(t,current,left,right);avg=q/(right-left)
            err=None if c['duty']==0 else (avg/(full*c['duty']/256)-1)*100
            out.update(average_current_a=avg,charge_c=q,area_error_pct=err)
            chk('Normal off guard',abs(avg)<1e-9) if c['duty']==0 else chk('Normal same-condition charge area',abs(err)<=limits['normal_lowest_code_charge_relative_error']*100)
            # Measure real protected PWM threshold pulse widths, not raw RTL widths.
            x,y=clip(t,data[:,IDX['v(pwm)']],left,right);threshold=ENVS[c['envelope']][2]/2
            rises=[];falls=[]
            for j in np.flatnonzero((y[:-1]-threshold)*(y[1:]-threshold)<0):
                ct=x[j]+(threshold-y[j])*(x[j+1]-x[j])/(y[j+1]-y[j])
                (rises if y[j+1]>y[j] else falls).append(float(ct))
            widths=[]
            low_widths=[]
            for a in rises:
                b=next((b for b in falls if b>a),None)
                if b is not None:widths.append(b-a)
            for a in falls:
                b=next((b for b in rises if b>a),None)
                if b is not None:low_widths.append(b-a)
            out['normal_high_min_s']=min(widths) if widths else None
            out['normal_low_min_s']=min(low_widths) if low_widths else None
            if widths:chk('Normal high width >=950ns',min(widths)>=limits['normal_pwm_high_low_min_s'])
            if low_widths:chk('Normal low width >=950ns',min(low_widths)>=limits['normal_pwm_high_low_min_s'])
        elif c['fault_ns']>=0:
            f=c['fault_ns']*1e-9;hold_end=f+3e-6
            if c.get('disconnect'):hold_end=min(t[-1],f+6e-6)
            deadline=limits['fault_deadline_s'];q=split_charge(t,current,f,f+limits['fault_tail_window_s'])
            settle=stable_below_time(t,current,f,hold_end,limits['fault_safe_current_abs_a'])
            logic=ENVS[c['envelope']][2]
            fault_half=None if c.get('disconnect') else f+5e-9
            if c.get('disconnect'):
                x,v=clip(t,data[:,IDX['v(fault_pin)']],f,hold_end)
                k=np.flatnonzero((v[:-1]<logic/2)&(v[1:]>=logic/2))
                if len(k):j=int(k[0]);fault_half=float(x[j]+(logic/2-v[j])*(x[j+1]-x[j])/(v[j+1]-v[j]))
            gate_start=fault_half if fault_half is not None else f
            gate_fall=fall_crossing(t,data[:,IDX['v(input)']],gate_start,hold_end,logic/2)
            pwm_fall=fall_crossing(t,data[:,IDX['v(pwm)']],gate_start,hold_end,logic/2)
            led_half=fall_crossing(t,current,gate_start,hold_end,full/2)
            x,v=clip(t,current,f+deadline,f+2e-6)
            off_max=float(np.max(np.abs(v)))
            out.update(fault_input_half_v_time_s=fault_half,safety_gate_half_fall_s=gate_fall,
                       joint_pwm_half_fall_s=pwm_fall,LED_half_full_fall_s=led_half,
                       stable_safe_current_time_s=settle,fault_to_safe_current_s=None if settle is None else settle-f,
                       post_deadline_max_abs_current_a=off_max,tail_charge=q,
                       pre_fault_current_a=float(np.interp(f-20e-9,t,current)),
                       reference_current_while_fault_a=float(np.interp(f+2e-6,t,data[:,IDX['i(VREFLOAD)']])))
            guard=clamp_contract['new_teaching_guards']
            x,v=clip(t,current,f,f+guard['window_s'])
            neg_peak=float(max(0,-v.min()))
            led_voltage=ENVS[c['envelope']][3]-data[:,IDX['v(led_k)']]
            x,v=clip(t,led_voltage,f,f+guard['window_s'])
            reverse_peak=float(max(0,-v.min()))
            diode_total=data[:,IDX['@d.xled.dled[id]']]
            cap_current=data[:,IDX['@d.xled.dled[capcur]']]
            out.update(negative_LED_current_peak_a=neg_peak,LED_reverse_voltage_peak_v=reverse_peak,
                       model_LED_total_charge=split_charge(t,diode_total,f,f+deadline),
                       model_LED_capacitive_charge=split_charge(t,cap_current,f,f+deadline),
                       model_LED_conduction_charge=split_charge(t,diode_total-cap_current,f,f+deadline),
                       clamp_supply_charge=split_charge(t,data[:,IDX['i(VCLAMPSUP)']],f,f+deadline),
                       MOUT_model_drain_charge=split_charge(t,data[:,IDX['@m.xjoint.x10.m0[id]']],f,f+deadline))
            # A reference-joint experiment uses the candidate's achieved current.
            if c.get('reference'):
                chk('Candidate reference produces target current before fault',abs(out['pre_fault_current_a']/100e-6-1)<=.05)
            passed=settle is not None and settle-f<=deadline and off_max<limits['fault_safe_current_abs_a'] and q['positive_c']<=limits['fault_positive_tail_charge_c']
            if c.get('negative'):
                chk('Expected stopped-clock no-protection failure detected',not passed)
                out['expected_negative_control_failure']=not passed
            else:
                chk('Fault safe-current deadline',settle is not None and settle-f<=deadline)
                chk('Post-deadline held-fault off guard',off_max<limits['fault_safe_current_abs_a'])
                chk('Positive fault tail <=10pC',q['positive_c']<=limits['fault_positive_tail_charge_c'])
                chk('Negative fault tail <=20pC',abs(q['negative_c'])<=guard['negative_tail_charge_abs_c'])
                chk('Negative LED peak <=10mA',neg_peak<=guard['negative_LED_current_peak_abs_a'])
                chk('Synthetic LED reverse peak <=0.5V',reverse_peak<=guard['LED_reverse_voltage_peak_abs_v'])
        if c.get('reference_ramp'):
            stop=c['initial_fault_clear_ns']*1e-9
            x,v=clip(t,current,0,stop)
            diode_total=data[:,IDX['@d.xled.dled[id]']];cap_current=data[:,IDX['@d.xled.dled[capcur]']]
            x,cond=clip(t,diode_total-cap_current,0,stop)
            out['startup']={'held_external_fault_until_s':stop,'LED_max_abs_current_a':float(np.max(np.abs(v))),
                            'LED_charge':split_charge(t,current,0,stop),
                            'model_LED_conduction_max_abs_a':float(np.max(np.abs(cond))),
                            'model_LED_conduction_charge':split_charge(t,diode_total-cap_current,0,stop),
                            'model_LED_capacitive_charge':split_charge(t,cap_current,0,stop),
                            'reference_output_peak_a':float(np.max(data[t<=stop,IDX['i(VREFLOAD)']])),
                            'scope':'Only reference rail ramps 0->3.3V in100ns; logic and LED rails valid. External fault held high; no POR or brownout implementation.'}
            chk('External asserted fault blocks reference-startup LED current',float(np.max(np.abs(v)))<limits['fault_safe_current_abs_a'])
        # Explicit terminal differences, without manufacturing reliability claims.
        logic=ENVS[c['envelope']][2]
        node={'0':np.zeros(len(t)),'vdd':np.full(len(t),logic),'raw':data[:,IDX['v(raw_pwm)']],
              'fault':data[:,IDX['v(fault_pin)']],'permit':data[:,IDX['v(permit)']],
              'out':data[:,IDX['v(unused_safe)']]}
        for n in ['fault_b','nand_n','stack1','stack2']:node[n]=data[:,IDX[f'v(xsafe.{n})']]
        stress={}
        for name,d,g,s,b in NEW_DEVICES:
            entry={}
            for label,y in [('VGS',node[g]-node[s]),('VGD',node[g]-node[d]),('VDS',node[d]-node[s]),('VSB',node[s]-node[b]),('VDB',node[d]-node[b])]:
                entry[label]={'min_v':float(y.min()),'max_v':float(y.max()),'max_abs_v':float(np.max(np.abs(y)))}
            stress[name]=entry
        clamp_node={'0':np.zeros(len(t)),'fault':np.zeros(len(t)) if c.get('negative') else node['fault'],
                    'fault_b':np.full(len(t),logic) if c.get('negative') else node['fault_b'],
                    'anode':np.full(len(t),ENVS[c['envelope']][3]),'cathode':data[:,IDX['v(led_k)']],
                    'fault_hb':data[:,IDX['v(xclamp.fault_hb)']]}
        for name,d,g,s,b in [('XLN0','fault_hb','fault','0','0'),
                            ('XCP','cathode','fault_hb','anode','anode')]:
            stress[name]={label:{'min_v':float(y.min()),'max_v':float(y.max()),'max_abs_v':float(np.max(np.abs(y)))}
                          for label,y in [('VGS',clamp_node[g]-clamp_node[s]),('VGD',clamp_node[g]-clamp_node[d]),
                                          ('VDS',clamp_node[d]-clamp_node[s]),('VSB',clamp_node[s]-clamp_node[b]),('VDB',clamp_node[d]-clamp_node[b])]}
        stress['joint_MOUT_declared_ports']={}
        for label,y in [('VGS',data[:,IDX['v(xjoint.gate.t2)']]-data[:,IDX['v(xjoint.led_k.t0)']]),
                        ('VGD',data[:,IDX['v(xjoint.gate.t2)']]),('VDS',-data[:,IDX['v(xjoint.led_k.t0)']]),
                        ('VSB',data[:,IDX['v(xjoint.led_k.t0)']])]:
            stress['joint_MOUT_declared_ports'][label]={'min_v':float(y.min()),'max_v':float(y.max()),'max_abs_v':float(np.max(np.abs(y)))}
        out['terminal_stress']=stress
        out['stress_scope']='New pre-layout 12 MOS declared D/G/S/B plus extracted MOUT declared ports (D/S may be swapped by extraction); capture only, no HCI/TDDB/latch-up qualification.'
        # Compact exported waveform preserves all fault-near samples; full raw stays build.
        selected=np.unique(np.r_[np.linspace(0,len(t)-1,min(4000,len(t)),dtype=int),
                  np.flatnonzero((t>(c['fault_ns']*1e-9-200e-9))&(t<(c['fault_ns']*1e-9+300e-9)))])
        compact=target/'waveform.csv'
        with compact.open('w') as f:
            writer=csv.writer(f);writer.writerow(['time_s']+VECTORS)
            writer.writerows(data[selected].tolist())
        out['checks']=checks;out['passed']=all(c['passed'] for c in checks)
        out['raw_waveform_sha256']=sha(target/'waveform.dat');out['compact_waveform_sha256']=sha(compact)
        out['deck_sha256']=sha(target/'testbench.spice');out['rtl_events_sha256']=sha(target/'rtl-events.csv')
        (target/'result.json').write_text(json.dumps(out,indent=2)+'\n')
        return out
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(run_case,cases))
    for r in results:
        for row in r['checks']:check(r['name']+' / '+row['name'],row['passed'])
    lookup={r['name']:r for r in results}
    if not args.only:
        if 'normal_d1' in lookup:
            a,b=lookup['normal_d1'],lookup['normal_d1_fine']
            delta=abs(b['charge_c']/a['charge_c']-1)*100
            check('Normal lowest-code maxstep10->1ns convergence',delta<=limits['convergence_change_pct'],change_pct=delta)
            a,b=lookup['fault_d256_early'],lookup['fault_d256_fine']
            delta=abs(b['tail_charge']['positive_c']/a['tail_charge']['positive_c']-1)*100
            check('Fault positive tail maxstep10->1ns convergence',delta<=limits['convergence_change_pct'],change_pct=delta)
        if 'servo_normal_d1' in lookup:
            a,b=lookup['servo_normal_d1'],lookup['servo_normal_d1_fine']
            delta=abs(b['charge_c']/a['charge_c']-1)*100
            check('Servo normal lowest-code maxstep10->2ns convergence',delta<=limits['convergence_change_pct'],change_pct=delta)
            a,b=lookup['servo_stopped_fault'],lookup['servo_stopped_fault_fine']
            delta=abs(b['tail_charge']['positive_c']/a['tail_charge']['positive_c']-1)*100
            check('Servo stopped fault Q+ maxstep10->2ns convergence',delta<=limits['convergence_change_pct'],change_pct=delta)
            a,b=lookup['servo_startup_default_fault'],lookup['servo_startup_default_fault_fine']
            delta=abs(b['startup']['LED_charge']['positive_c']/a['startup']['LED_charge']['positive_c']-1)*100
            check('Servo startup Q+ maxstep10->2ns convergence',delta<=limits['convergence_change_pct'],change_pct=delta)
        check('Baseline input bytes unchanged',all(sha(ROOT/p)==h for p,h in hashes.items()))
    passed=all(c['passed'] for c in overall_checks)
    summary={'schema_version':1,'stage':'safety experiment v0.3 / new pre-layout 12-MOS gate and active LED clamp + frozen one-pixel selected signal PEX',
             'passed':passed,'date':datetime.now(ZoneInfo('Asia/Tokyo')).date().isoformat(),'raw_directory':str(work.relative_to(ROOT)),
             'suite':args.suite,
             'contract_sha256':hashes['evidence/safety/contract.json'],'source_sha256':hashes,'tools':tools,
             'checks':overall_checks,'check_count':len(overall_checks),'transient_runs':len(results),
             'dc_runs':len(dc),'LED_calibrations':1,'calibration_v':cal_v,
             'results':results,'reference_joint_included':bool(references),'reference_kinds_included':sorted(references),
             'limitations':safety_contract['fault']['not_implemented']+[
                 'Only the old 12-MOS signal cutout is layout-extracted; new gate/clamp are 12 schematic MOS and one ideal 100k resistor',
                 'Real PG/body/active neighbors absent; 34 neighbors ideal0V',
                 'Full digital FF transistor path absent; permit/recovery is actual RTL event replay',
                 'No optical extinction or physical fault sensor evidence',
                 'Clock-stop guarantee requires a valid powered safety rail and valid fault-high level',
                 'Reference remains on during fault; branch off is not whole-system power-off']}
    (work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if passed and args.publish_evidence:
        dest=ROOT/'evidence/safety';dest.mkdir(parents=True,exist_ok=True)
        for r in results:
            folder=dest/'waveforms'/r['name'];folder.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(work/r['name']/'waveform.csv',folder/'waveform.csv')
            shutil.copyfile(work/r['name']/'rtl-events.csv',folder/'rtl-events.csv')
            shutil.copyfile(work/r['name']/'result.json',folder/'result.json')
        (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        manifest={str(p.relative_to(ROOT)):sha(p) for p in sorted((dest/'waveforms').rglob('*')) if p.is_file()}
        manifest['evidence/safety/summary.json']=sha(dest/'summary.json')
        (dest/'output-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'passed':passed,'raw_directory':str(work.relative_to(ROOT)),'transient_runs':len(results),'checks':len(overall_checks),'failed_checks':[c for c in overall_checks if not c['passed']]},indent=2))
    if not passed:raise SystemExit(1)

if __name__=='__main__':main()
