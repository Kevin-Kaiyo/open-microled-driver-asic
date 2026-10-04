"""Frozen paired output-stage PEX and exploratory power/control boundaries.

Only the stage contract may select post model pins. No unknown pin is grounded
automatically. Pre and post use the same RTL, LED/reference and input ramps;
post replaces buffer, analog RC and both old routing models as one joint cutout.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
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

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
PDK=ROOT/'build/layout/pdk/gf180mcuD'
LEFT,RIGHT=514.5e-6,1026.5e-6
FRAME=256e-6
ENVELOPES={'tt':dict(corner='typical',temperature_c=27,logic_v=3.3,led_v=5),
           'ss':dict(corner='ss',temperature_c=85,logic_v=2.97,led_v=4.5),
           'ff':dict(corner='ff',temperature_c=0,logic_v=3.63,led_v=5.5)}
VECTORS=['v(pwm)','v(gate)','v(bias)','v(led_k)','v(logic_rail)','v(led_a)','v(input)',
         'i(VLEDLOAD)','i(VLANA)','i(VLREF)','i(VLBUF)','i(VSUPLOG)','i(VSUPLED)',
         'i(BVIN)','v(raw_pwm)','v(ref_enable)','neighborcurrent']
INDEX={name:i+1 for i,name in enumerate(VECTORS)}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(args,folder,log):
    p=subprocess.run([str(a) for a in args],cwd=folder,capture_output=True,text=True)
    (folder/log).write_text(p.stdout+p.stderr)
    if p.returncode or (args[0]=='ngspice' and re.search(r'(?im)^Error:|timestep too small|simulation interrupted',p.stdout+p.stderr)):
        raise RuntimeError(f'Command failed: {folder/log}')
    return p.stdout


def clip(t,y,left,right):
    # numdgt=15 decimal serialization can move a stop by a few float ULPs.
    # Permit only this representation error, never a missing transient interval.
    left_ulp=8*abs(np.spacing(max(abs(t[0]),abs(left))))
    right_ulp=8*abs(np.spacing(max(abs(t[-1]),abs(right))))
    if not np.isfinite(y).all() or np.any(np.diff(t)<=0) or t[0]>left+left_ulp or t[-1]<right-right_ulp:
        raise RuntimeError('Incomplete/nonfinite waveform')
    mask=(t>left)&(t<right)
    return np.r_[left,t[mask],right],np.r_[np.interp(left,t,y),y[mask],np.interp(right,t,y)]


def integral(t,y,left,right):
    x,v=clip(t,y,left,right)
    return float(np.sum(np.diff(x)*(v[:-1]+v[1:])/2))


def product_integral(t,a,b,left,right):
    """Exact product integral of the two saved piecewise-linear waveforms."""
    x,av=clip(t,a,left,right);_,bv=clip(t,b,left,right)
    panels=np.diff(x)*(2*av[:-1]*bv[:-1]+av[:-1]*bv[1:]+av[1:]*bv[:-1]+2*av[1:]*bv[1:])/6
    return float(panels.sum())


def negative_product_energy(t,a,b,left,right):
    """Signed integral where the two linearly saved factors' product is negative."""
    x,av=clip(t,a,left,right);_,bv=clip(t,b,left,right)
    additional=[]
    for factor in (av,bv):
        indices=np.flatnonzero(factor[:-1]*factor[1:]<0)
        additional.extend((x[indices]-factor[indices]*(x[indices+1]-x[indices])/(factor[indices+1]-factor[indices])).tolist())
    refined=np.unique(np.r_[x,additional]);aa=np.interp(refined,x,av);bb=np.interp(refined,x,bv)
    panels=np.diff(refined)*(2*aa[:-1]*bb[:-1]+aa[:-1]*bb[1:]+aa[1:]*bb[:-1]+2*aa[1:]*bb[1:])/6
    negative=(aa[:-1]+aa[1:])*(bb[:-1]+bb[1:])<0
    return float(panels[negative].sum())


def crossing(t,y,threshold,rising):
    mask=((y[:-1]<threshold)&(y[1:]>=threshold)) if rising else ((y[:-1]>threshold)&(y[1:]<=threshold))
    k=np.flatnonzero(mask)
    return t[k]+(threshold-y[k])*(t[k+1]-t[k])/(y[k+1]-y[k])


def edge_metrics(t,v,supply,left,right):
    output={}
    for name,rising in [('rise',True),('fall',False)]:
        a=crossing(t,v,supply*(.3 if rising else .7),rising)
        b=crossing(t,v,supply*(.7 if rising else .3),rising)
        mid=crossing(t,v,supply*.5,rising)
        widths=[]
        for x in mid[(mid>left)&(mid<right)]:
            earlier=a[a<=x];later=b[b>=x]
            if len(earlier) and len(later):widths.append((later[0]-earlier[-1])*1e9)
        output[('rise_30_70_ns' if rising else 'fall_70_30_ns')]=float(max(widths)) if widths else None
        output[name+'_edges_in_window']=int(len(mid[(mid>left)&(mid<right)]))
    rises=crossing(t,v,supply*.5,True);falls=crossing(t,v,supply*.5,False)
    for name,a,b in [('high',rises,falls),('low',falls,rises)]:
        widths=[]
        for x in a[(a>left)&(a<right)]:
            later=b[(b>x)&(b<right)]
            if len(later):widths.append((later[0]-x)*1e9)
        output[name+'_pulse_min_ns']=float(min(widths)) if widths else None
    return output


def pwl(points):
    return 'PWL(\n'+'\n'.join(f'+ {t:.16g} {v:.16g}' for t,v in points)+'\n+)'


def ramp(start,top,stop):
    if start is None:return str(top)
    if start==0:return pwl([(0,0),(100e-9,top),(stop,top)])
    return pwl([(0,0),(start,0),(start+100e-9,top),(stop,top)])


def pwm_points(events,stop):
    result=[(0,0)];previous=0
    for t,v in events:
        if t+1e-9>=stop:break
        if v!=previous:result.extend([(t,previous),(t+1e-9,v)])
        previous=v
    result.append((stop,previous));return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract',type=Path,required=True)
    parser.add_argument('--group',choices=['probe','main','boundary'],required=True)
    args=parser.parse_args()
    contract_path=args.contract.resolve();contract=json.loads(contract_path.read_text())
    post_path=ROOT/contract['model_path']
    if sha(post_path)!=contract['model_sha256']:raise RuntimeError('Explicit post-model hash does not match')
    text=post_path.read_text();definition=re.search(r'(?im)^\.subckt\s+(\S+)\s+(.+)$',text)
    ports=definition[2].split()
    if definition[1]!=contract['subckt'] or ports!=contract['ports_order'] or set(ports)!=set(contract['pin_bindings']):
        raise RuntimeError('Post cutout ports differ from the explicitly reviewed contract')
    if not contract['replaces_old_analog_buf_spef_link']:raise RuntimeError('Joint cutout must not be stacked with old RC')
    for path,h in contract.get('required_inputs_sha256',{}).items():
        if sha(ROOT/path)!=h:raise RuntimeError('Contract provenance changed: '+path)
    for lock in ['layout/pdk-lock.json','scripts/physical/pdk-lock.json']:
        values=json.loads((ROOT/lock).read_text())['files']
        for name in ['libs.tech/ngspice/design.ngspice','libs.tech/ngspice/sm141064.ngspice']:
            if name in values and sha(PDK/name)!=values[name]:raise RuntimeError('PDK model differs from existing lock')
    (ROOT/'build/robustness').mkdir(exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix=args.group+'-',dir=ROOT/'build/robustness'))
    inputs=['scripts/robustness/run.py','scripts/robustness/tb_controls.v','scripts/robustness/reference_boundary.spice',
            'docs/specifications/electrical-v0.4.md','rtl/pixel_pwm.v','sim/rtl/tb_pixel_pwm.v',
            'analog/models/microled.spice','analog/models/measured-led/lin2026-yellow20-dc.spice',
            'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv','scripts/interface/buf_2.spice',
            'evidence/layout/pixel_driver_rc.spice','evidence/integration/pwm_link_rc.spice',
            'evidence/physical/digital/spef/nom/pixel_pwm.nom.spef','layout/pdk-lock.json','scripts/physical/pdk-lock.json',
            str(contract_path.relative_to(ROOT)),contract['model_path']]
    inputs+=list(contract.get('required_inputs_sha256',{}));inputs=list(dict.fromkeys(inputs))
    for variant in contract.get('post_variants',{}).values():
        if sha(ROOT/variant['model_path'])!=variant['model_sha256']:raise RuntimeError('Alternative physical model identity changed')
        inputs.append(variant['model_path'])
    inputs=list(dict.fromkeys(inputs))
    hashes={}
    for name in inputs:
        source=ROOT/name;before=sha(source);target=work/'inputs'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        if sha(target)!=before or sha(source)!=before:raise RuntimeError('Input changed during freeze: '+name)
        hashes[name]=before
    frozen=work/'inputs';post=frozen/contract['model_path']
    ngspice=execute(['ngspice','--version'],work,'ngspice-version.log')
    binary=work/'pwm.vvp'
    execute(['iverilog','-g2012','-s','tb_pixel_pwm','-o',binary,frozen/'rtl/pixel_pwm.v',frozen/'sim/rtl/tb_pixel_pwm.v'],work,'rtl-compile.log')
    events={}
    for duty in [0,1,64,255,256]:
        filename=work/f'duty-{duty}.csv'
        log=execute(['vvp',binary,f'+OUT={filename}',f'+DUTY={duty}','+ENABLE=1','+TRACE_ONLY=1'],work,f'rtl-{duty}.log')
        if 'measure_start_ns=514500' not in log:raise RuntimeError('RTL frame origin changed')
        with filename.open() as f:events[str(duty)]=[(float(r['time_ns'])*1e-9,int(r['pwm'])) for r in csv.DictReader(f)]
    controls=work/'controls.vvp'
    execute(['iverilog','-g2012','-s','tb_controls','-o',controls,frozen/'rtl/pixel_pwm.v',frozen/'scripts/robustness/tb_controls.v'],work,'control-compile.log')
    for n,name in enumerate(['reset','enable']):
        filename=work/f'{name}.csv'
        execute(['vvp',controls,f'+OUT={filename}',f'+INPUTS={work/(name+"-inputs.csv")}',f'+CASE={n}'],work,name+'-rtl.log')
        with filename.open() as f:events[name]=[(float(r['time_ns'])*1e-9,int(r['pwm'])) for r in csv.DictReader(f)]
    expected={'reset':[(500e-9,0),(2500e-9,1),(20500e-9,0),(30500e-9,1)],
              'enable':[(500e-9,0),(2500e-9,1),(258500e-9,0),(514500e-9,1)]}
    for name,value in expected.items():
        actual=events[name]
        if len(actual)!=len(value) or any(abs(a[0]-b[0])>1e-15 or a[1]!=b[1] for a,b in zip(actual,value)):
            raise RuntimeError('Actual RTL control event semantics differ: '+name)
    led_is=100e-6/math.expm1((2.8-100e-6*50)/(3*8.617333262145e-5*300.15))
    def folder_for(name):
        folder=work/name;folder.mkdir()
        for filename in ['design.ngspice','sm141064.ngspice']:
            (folder/filename).symlink_to(os.path.relpath(PDK/'libs.tech/ngspice'/filename,folder))
        return folder
    def case_deck(case,dc=False):
        c=ENVELOPES[case.get('envelope','tt')];stop=case.get('stop_s',RIGHT+2e-6)
        reference=case.get('reference','ideal');iref_start=case.get('reference_start_s')
        led_start=case.get('led_start_s');logic_start=case.get('logic_start_s')
        rlogic=case.get('rlogic_ohm',0);rled=case.get('rled_ohm',0);decap=case.get('decap_f',0)
        selected_post=(frozen/contract['post_variants'][case['post_rc_style']]['model_path']) if case.get('post_rc_style') else post
        driver=(f'.include "{selected_post}"\nXJOINT '+ ' '.join(contract['pin_bindings'][p] for p in ports)+' '+contract['subckt'])
        if case['view']=='pre':
            driver=f'''.include "{frozen/'scripts/interface/buf_2.spice'}"
.include "{frozen/'evidence/layout/pixel_driver_rc.spice'}"
.include "{frozen/'evidence/integration/pwm_link_rc.spice'}"
XBUF input driver vbuffer vbuffer 0 0 gf180mcu_fd_sc_mcu7t5v0__buf_2
CDIGNEAR driver 0 .315849f
RDIG driver macro_pwm 12.375
CDIGFAR macro_pwm 0 .819270f
XLINK pwm macro_pwm vlogic 0 pwm_link_rc
XPIXEL 0 bias gate pwm pwm_b led_k vlogic pixel_driver_layout'''
        neighbors='\n'.join(f'BNEIGHBOR{n} {row["node"]} 0 V={{v(logic_rail)*{case.get("neighbor_fraction_override",row["quiet_voltage_fraction"])}}}'
                            for n,row in enumerate(contract.get('neighbor_sources',[])))
        led=(f'.include "{frozen/"analog/models/measured-led/lin2026-yellow20-dc.spice"}"\nXLED led_anode led_k lin2026_yellow20_dc'
             if case.get('led_model')=='measured_static' else
             f'.include "{frozen/"analog/models/microled.spice"}"\nXLED led_anode led_k microled')
        if dc:raw=str(case.get('level',1))
        else:raw=pwl(pwm_points(events[case.get('trace',str(case.get('duty',256)))],stop))
        log_drop=(f'RLOG vsuplog logic_rail {rlogic}' if rlogic else 'VLOGDROP vsuplog logic_rail 0')
        led_drop=(f'RLED vsupled led_a {rled}' if rled else 'VLEDDROP vsupled led_a 0')
        reference_part=('BIREF refrail bias I={100u*v(ref_enable)}' if reference=='ideal' else
                        f'.include "{frozen/"scripts/robustness/reference_boundary.spice"}"\nXREF refrail bias ref_enable reference_boundary')
        return f'''Frozen {args.group} {case['view']} {case['name']}
.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0 LED_IS={led_is:.17g}
.lib sm141064.ngspice {c['corner']}
.temp {c['temperature_c']}
VSUPLOG vsuplog 0 {ramp(logic_start,c['logic_v'],stop)}
VSUPLED vsupled 0 {ramp(led_start,c['led_v'],stop)}
{log_drop}
{led_drop}
VLANA logic_rail vlogic 0
VLREF logic_rail refrail 0
VLBUF logic_rail vbuffer 0
VLEDLOAD led_a led_anode 0
{('CLOG logic_rail 0 '+str(decap)) if decap else ''}
{('CDECAPLED led_a 0 '+str(decap)) if decap else ''}
VREFENABLE ref_enable 0 {ramp(iref_start,1,stop)}
{reference_part}
VRAW raw_pwm 0 {raw}
BVIN input 0 V={{v(raw_pwm)*v(logic_rail)}}
{led}
{neighbors}
{driver}
.options reltol=1e-7 abstol=1e-14 vntol=1e-9
'''
    def simulate(case,dc=False):
        folder=folder_for(case['name']);stop=case.get('stop_s',RIGHT+2e-6)
        neighbor_current=' - '.join(f'i(BNEIGHBOR{n})*{case.get("neighbor_fraction_override",row["quiet_voltage_fraction"])}'
                                    for n,row in enumerate(contract.get('neighbor_sources',[]))
                                    if case.get('neighbor_fraction_override',row['quiet_voltage_fraction'])!=0)
        neighbor_current=('-'+neighbor_current) if neighbor_current else 'v(raw_pwm)*0'
        control=('op\nwrdata values.dat '+' '.join(VECTORS) if dc else
                 f'tran 10n {stop:.16g} 0 {case.get("maxstep_ns",10)}n\nwrdata waveform.dat '+' '.join(VECTORS))
        control=control.replace('wrdata',f'let neighborcurrent = {neighbor_current}\nwrdata')
        (folder/'testbench.spice').write_text(case_deck(case,dc)+f'''.control
set numdgt=15
set wr_vecnames
set wr_singlescale
{control}
quit
.endc
.end
''')
        execute(['ngspice','-b','testbench.spice'],folder,'ngspice.log')
        data=np.atleast_2d(np.loadtxt(folder/('values.dat' if dc else 'waveform.dat'),skiprows=1))
        if data.shape[1]!=len(VECTORS)+1 or not np.isfinite(data).all():raise RuntimeError('Invalid output dimensions: '+str(folder))
        if dc:
            a=data[0];return case|dict(current_uA=float(a[INDEX['i(VLEDLOAD)']]*1e6),
                                      logic_pin_v=float(a[INDEX['v(logic_rail)']]),LED_anode_v=float(a[INDEX['v(led_a)']]),
                                      bias_v=float(a[INDEX['v(bias)']]),pwm_v=float(a[INDEX['v(pwm)']]),
                                      reference_uA=float(a[INDEX['i(VLREF)']]*1e6),
                                      load_power_uW=float(a[INDEX['v(led_a)']]*a[INDEX['i(VLEDLOAD)']]*1e6))
        t=data[:,0];left=case.get('left_s',LEFT);right=case.get('right_s',RIGHT);duration=right-left
        y={name:data[:,n] for name,n in INDEX.items()};c=ENVELOPES[case.get('envelope','tt')]
        current=y['i(VLEDLOAD)'];average=integral(t,current,left,right)/duration
        energies={
            'LED_source_generated_j':product_integral(t,-y['i(VSUPLED)'],(np.full_like(t,c['led_v']) if case.get('led_start_s') is None else np.minimum(1,np.maximum(0,(t-case['led_start_s'])/100e-9))*c['led_v']),left,right),
            'logic_source_generated_j':product_integral(t,-y['i(VSUPLOG)'],(np.full_like(t,c['logic_v']) if case.get('logic_start_s') is None else np.minimum(1,np.maximum(0,(t-case['logic_start_s'])/100e-9))*c['logic_v']),left,right),
            'LED_load_absorbed_j':product_integral(t,current,y['v(led_a)'],left,right),
            'logic_joint_load_absorbed_j':product_integral(t,y['i(VLANA)']+y['i(VLBUF)'],y['v(logic_rail)'],left,right),
            'reference_rail_absorbed_j':product_integral(t,y['i(VLREF)'],y['v(logic_rail)'],left,right),
            'reference_B_source_absorbed_j':product_integral(t,y['i(VLREF)'],y['v(logic_rail)']-y['v(bias)'],left,right),
            'input_stimulus_generated_j':product_integral(t,-y['i(BVIN)'],y['v(input)'],left,right),
            'neighbor_stimulus_generated_j':product_integral(t,y['neighborcurrent'],y['v(logic_rail)'],left,right),
            'logic_series_R_loss_j':product_integral(t,y['i(VSUPLOG)'],y['i(VSUPLOG)'],left,right)*case.get('rlogic_ohm',0),
            'LED_series_R_loss_j':product_integral(t,y['i(VSUPLED)'],y['i(VSUPLED)'],left,right)*case.get('rled_ohm',0)}
        cap=case.get('decap_f',0)
        energies['logic_decap_stored_energy_change_j']=.5*cap*(float(np.interp(right,t,y['v(logic_rail)']))**2-float(np.interp(left,t,y['v(logic_rail)']))**2)
        energies['LED_decap_stored_energy_change_j']=.5*cap*(float(np.interp(right,t,y['v(led_a)']))**2-float(np.interp(left,t,y['v(led_a)']))**2)
        states={n:dict(start_v=float(np.interp(left,t,y[n])),end_v=float(np.interp(right,t,y[n])))
                for n in ['v(pwm)','v(gate)','v(bias)','v(led_k)']}
        extrema={n:dict(min=float(clip(t,y[n],left,right)[1].min()),max=float(clip(t,y[n],left,right)[1].max()))
                 for n in ['v(pwm)','v(gate)','v(bias)','v(led_k)','v(logic_rail)','v(led_a)']}
        frame_means=[]
        if abs(duration-2*FRAME)<1e-12:
            frame_means=[integral(t,current,a,b)/(b-a)*1e6 for a,b in [(left,left+FRAME),(left+FRAME,right)]]
        mask=(t>=left)&(t<=right);off=(y['v(raw_pwm)'][mask]<.5)
        max_off=float(current[mask][off].max()*1e6) if off.any() else None
        result=case|dict(current_uA=average*1e6,LED_load_charge_c=average*duration,measurement_window_s=[left,right],
                         measurement_duration_s=duration,energies_j=energies,powers_uW={k:v/duration*1e6 for k,v in energies.items()},
                         frame_average_currents_uA=frame_means,observed_endpoints=states,extrema=extrema,
                         peak_LED_branch_current_uA=float(current[mask].max()*1e6),minimum_LED_branch_current_uA=float(current[mask].min()*1e6),
                         command_low_peak_LED_branch_current_uA=max_off,
                         PWM_below_ground_min_v=float(clip(t,y['v(pwm)'],left,right)[1].min()),
                         PWM_above_live_logic_max_v=float(clip(t,y['v(pwm)']-y['v(logic_rail)'],left,right)[1].max()),
                         bias_above_reference_rail_max_v=float(clip(t,y['v(bias)']-y['v(logic_rail)'],left,right)[1].max()),
                         minimum_reference_B_source_power_absorbed_uW=float(clip(t,y['i(VLREF)']*(y['v(logic_rail)']-y['v(bias)']),left,right)[1].min()*1e6),
                         reference_B_source_active_delivery_energy_j=-negative_product_energy(t,y['i(VLREF)'],y['v(logic_rail)']-y['v(bias)'],left,right),
                         PWM_voltage_50pct_rise_s=crossing(t,y['v(pwm)'],c['logic_v']*.5,True).tolist(),
                         PWM_voltage_50pct_fall_s=crossing(t,y['v(pwm)'],c['logic_v']*.5,False).tolist(),
                         **edge_metrics(t,y['v(pwm)'],c['logic_v'],left,right))
        return result
    calibration=folder_for('independent_LED_calibration')
    (calibration/'testbench.spice').write_text(f'''Synthetic independent calibration
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
wrdata values.dat v(anode)
quit
.endc
.end
''')
    execute(['ngspice','-b','testbench.spice'],calibration,'ngspice.log')
    cal_v=float(np.loadtxt(calibration/'values.dat',skiprows=1)[1])
    if abs(cal_v-2.8)>1e-5:raise RuntimeError('Synthetic independent calibration failed')
    dc_cases=[dict(name=f'dc_{e}_{view}_{level}',envelope=e,view=view,level=level) for e in ENVELOPES for view in ['pre','post'] for level in [0,1]]
    cases=[]
    if args.group=='probe':
        cases=[dict(name=f'short_{e}_{view}',envelope=e,view=view,duty=1,stop_s=20e-6,left_s=2.5e-6,right_s=20e-6,maxstep_ns=2)
               for e in ENVELOPES for view in ['pre','post']]
        cases += [dict(name='short_rc_'+style,envelope='tt',view='post',post_rc_style=style,duty=1,
                       stop_s=20e-6,left_s=2.5e-6,right_s=20e-6,maxstep_ns=2)
                  for style in contract.get('post_variants',{}) if style!='nominal']
    elif args.group=='main':
        cases=[dict(name=f'{e}_{view}_d{duty}',envelope=e,view=view,duty=duty,maxstep_ns=10)
               for e in ENVELOPES for view in ['pre','post'] for duty in [0,1,64,255,256]]
        cases += [dict(name=f'{e}_post_d1_fine',envelope=e,view='post',duty=1,maxstep_ns=1) for e in ENVELOPES]
        for style,e in [('hrhc','ss'),('lrlc','ff')]:
            if style in contract.get('post_variants',{}):
                cases += [dict(name=f'{e}_{style}_d{duty}',envelope=e,view='post',post_rc_style=style,duty=duty,maxstep_ns=10)
                          for duty in [1,256]]
    else:
        dc_cases=[dict(name=f'measured_static_R{r}',envelope='tt',view='post',level=1,led_model='measured_static',rled_ohm=r)
                  for r in [0,1000,5000,10000]]
        schedules={'simultaneous':(1e-6,1e-6),'logic_first':(1e-6,8e-6),'LED_first':(8e-6,1e-6)}
        for sequence,(ls,ds) in schedules.items():
            for reference,start in [('ideal_early',0),('ideal_late',ls+.2e-6),('compliant_early',0)]:
                cases.append(dict(name=sequence+'_'+reference,envelope='tt',view='post',duty=256,stop_s=20e-6,left_s=0,right_s=20e-6,
                                  logic_start_s=ls,led_start_s=ds,reference_start_s=start,
                                  reference='compliant' if reference.startswith('compliant') else 'ideal',maxstep_ns=2))
        cases += [dict(name='RTL_reset',envelope='tt',view='post',trace='reset',stop_s=100e-6,left_s=0,right_s=100e-6,maxstep_ns=10),
                  dict(name='RTL_enable',envelope='tt',view='post',trace='enable',stop_s=600e-6,left_s=0,right_s=600e-6,maxstep_ns=10)]
        for rlogic,rled in [(0,0),(10,100),(100,1000)]:
            for duty in [1,256]:
                cases.append(dict(name=f'impedance_{rlogic}_{rled}_d{duty}',envelope='tt',view='post',duty=duty,
                                  rlogic_ohm=rlogic,rled_ohm=rled,decap_f=1e-9,maxstep_ns=10))
        cases += [dict(name='logic_first_R100_RLED1000_decap',envelope='tt',view='post',duty=256,stop_s=20e-6,left_s=0,right_s=20e-6,
                       logic_start_s=1e-6,led_start_s=8e-6,reference_start_s=1.2e-6,reference='compliant',
                       rlogic_ohm=100,rled_ohm=1000,decap_f=1e-9,maxstep_ns=2)]
        cases += [dict(name='neighbors_all_live_high_LED_first',envelope='tt',view='post',duty=256,stop_s=20e-6,left_s=0,right_s=20e-6,
                       logic_start_s=8e-6,led_start_s=1e-6,reference_start_s=0,reference='compliant',
                       neighbor_fraction_override=1,maxstep_ns=2)]
    with ThreadPoolExecutor(max_workers=4) as pool:dc_results=list(pool.map(lambda c:simulate(c,True),dc_cases))
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(simulate,cases))
    checks=[]
    if args.group in ['probe','main']:
        for r in dc_results:
            passed=(95<=r['current_uA']<=105) if r['level'] else abs(r['current_uA'])<.001
            checks.append(dict(name=r['name']+'_DC_guard',passed=passed,current_uA=r['current_uA']))
    if args.group=='main':
        for r in results:
            full=next(x for x in results if x['envelope']==r['envelope'] and x['view']==r['view'] and x['duty']==256
                      and x.get('post_rc_style')==r.get('post_rc_style'))
            area=(r['current_uA']/(full['current_uA']*r['duty']/256)-1)*100 if r['duty'] else None
            r['area_error_pct']=area
            if r['duty']==256:checks.append(dict(name=r['name']+'_full_5pct',passed=95<=r['current_uA']<=105))
            if r['duty']==0:checks.append(dict(name=r['name']+'_off_1nA',passed=abs(r['current_uA'])<.001))
            if r['duty']==1:checks.append(dict(name=r['name']+'_area_2pct',passed=abs(area)<=2))
            if r['duty'] not in [0,256]:
                checks.append(dict(name=r['name']+'_slew_3ns',passed=r['rise_30_70_ns']<=3 and r['fall_70_30_ns']<=3))
                checks.append(dict(name=r['name']+'_pulse_950ns',passed=r['high_pulse_min_ns'] is not None and
                                   r['low_pulse_min_ns'] is not None and r['high_pulse_min_ns']>=950 and r['low_pulse_min_ns']>=950))
                checks.append(dict(name=r['name']+'_exact_two_rise_two_fall',passed=r['rise_edges_in_window']==2 and r['fall_edges_in_window']==2))
            frames=r['frame_average_currents_uA']
            spread=abs(frames[0]-frames[1]);tolerance=.001 if abs(r['current_uA'])<.001 else abs(r['current_uA'])*.002
            checks.append(dict(name=r['name']+'_two_frame_0p2pct',passed=spread<=tolerance,spread_uA=spread,tolerance_uA=tolerance))
            if r['name'].endswith('_fine'):
                baseline=next(x for x in results if x['name']==r['name'].replace('_fine',''))
                change=abs(r['current_uA']-baseline['current_uA']);allowed=.001 if abs(baseline['current_uA'])<.001 else abs(baseline['current_uA'])*.002
                checks.append(dict(name=r['name']+'_refinement',passed=change<=allowed,change_uA=change,tolerance_uA=allowed))
    public=ROOT/'evidence/robustness';public.mkdir(exist_ok=True)
    summary=dict(schema_version=1,group=args.group,passed=all(c['passed'] for c in checks),completed_numerically=True,
                 run_directory=str(work.relative_to(ROOT)),ngspice=ngspice,contract=contract,
                 scope=dict(joint_extracted_signal_RC_with_actual_MOS_junctions=True,full_joint_cell_PG_PEX=False,
                            PG_only_capacitance_included=False,body_PG_series_R_included=False,
                            startup_is_selected_signal_model_plus_external_R_C_probe=True,
                            full_digital_transistor=False,real_reference_generator=False,
                            real_LED_dynamic=False,full_PG_or_substrate=False,preceding_FF_waveform=False),
                 boundary_finding='v0.3 standalone analog RC formal at left; actual physical PWM enters at right; post replaces all old route/analog/buf views as joint cutout',
                 source_hashes=hashes,PDK_models_sha256={n:sha(PDK/'libs.tech/ngspice'/n) for n in ['design.ngspice','sm141064.ngspice']},
                 conditions=dict(envelopes=ENVELOPES,input_full_ramp_ns=1,frame_period_s=FRAME,warmup_frames=2,
                                 main_measurement_window_s=[LEFT,RIGHT],measured_frames=2,reference_uA=100,
                                 actual_Liberty_slew_percent=[30,70],LED_static_temperature='unknown; static table never temperature scaled',
                                 startup_inputs='actual RTL logical trace multiplied by live logic rail; no voltage-aware FF/POR implementation',
                                 current_metric='LED electrical branch includes diode displacement current; not optical flux',
                                 power_metric='signed energy / explicit duration; selected signal-path 12MOS shared logic rail, separate reference rail; pre buffer+analog summed before compare',
                                 excluded_startup_energy='actual PG-only metal/well charging, removed internal body/PG R and full cell/chip decap/source energy; assumed 1nF does not replace excluded PG capacitance'),
                 integration_method='current: trapezoid of saved piecewise-linear I; power: exact quadratic product of separately interpolated saved V and I; not a recovery of unrecorded continuous-time samples',
                 synthetic_LED_calibration=dict(actual_v=cal_v,target_v=2.8,target_uA=100,passed=True),
                 dc_runs=len(dc_results),transient_runs=len(results),dc_results=dc_results,results=results,checks=checks,
                 vector_columns=['time_s']+VECTORS,actual_RTL_control_events={k:events[k] for k in ['reset','enable']},
                 raw_artifacts_sha256={str(p.relative_to(work)):sha(p) for p in sorted(work.rglob('*')) if p.is_file() and not p.is_symlink()
                                       and 'inputs' not in p.relative_to(work).parts and p.suffix in ['.spice','.dat','.csv','.log']})
    (work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (public/(args.group+'-summary.json')).write_bytes((work/'summary.json').read_bytes())
    for label,rows in [('dc',dc_results),('transients',results)]:
        keys=sorted(set().union(*(r.keys() for r in rows)))
        with (public/(args.group+'-'+label+'.csv')).open('w') as f:
            writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
            writer.writerows([{k:json.dumps(v,sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in row.items()} for row in rows])
    print(json.dumps(dict(group=args.group,passed=summary['passed'],transient_runs=len(results),dc_runs=len(dc_results),
                         run_directory=summary['run_directory'],failed=[c for c in checks if not c['passed']]),indent=2))
    if not summary['passed']:raise RuntimeError('Normative guard failed; retain raw and reported evidence')


if __name__=='__main__':main()
