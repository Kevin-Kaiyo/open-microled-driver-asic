"""Freeze and characterize the actual eight-MOS GF180 reference candidate.

Results may fail an engineering gate without invalidating a completed experiment.
Never tune dimensions after seeing PVT results; nominal calibration is separate.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import csv, itertools, json, math, shutil, tempfile
import numpy as np
import probe as p

ROOT=p.ROOT
LEFT=514.5e-6;FRAME=256e-6;RIGHT=LEFT+2*FRAME;STOP=RIGHT+2e-6
RL=13.5e-6
ENVS={'tt':('typical',27,3.3,5),'slow':('ss',85,2.97,4.5),'fast':('ff',0,3.63,5.5)}

def save(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def csvsave(path,rows):
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
def clip(t,y,l,r):
    if t[0]>l+8*abs(np.spacing(l)) or t[-1]<r-8*abs(np.spacing(r)) or np.any(np.diff(t)<=0):raise RuntimeError('Incomplete trace')
    k=(t>l)&(t<r)
    return np.r_[l,t[k],r],np.r_[np.interp(l,t,y),y[k],np.interp(r,t,y)]
def integ(t,y,l,r):
    x,v=clip(t,y,l,r);return float(np.sum(np.diff(x)*(v[:-1]+v[1:])/2))
def pwl(points):return 'PWL(\n'+'\n'.join(f'+ {t:.16g} {v:.16g}' for t,v in points)+'\n+)'
def read_events(path):
    with path.open() as f:return [(float(r['time_ns'])*1e-9,int(r['pwm'])) for r in csv.DictReader(f)]
def pwm(events,vdd,stop):
    pts=[(0,0)];last=0
    for t,v in events:
        if t+1e-9>=stop:break
        if v!=last:pts.extend([(t,last*vdd),(t+1e-9,v*vdd)])
        last=v
    pts.append((stop,last*vdd));return pwl(pts)
def led_part():
    isat=100e-6/math.expm1((2.8-100e-6*50)/(3*8.617333262145e-5*300.15))
    return f'.include "{p.LED}"\n.param LED_IS={isat:.17g}\nXLED led_a led_k microled\n'
def transient(folder,c,events=None,duty=1,maxstep=10e-9,kind='pwm',rise=100e-9,start=1):
    corner,temp,vdd,ledv=c
    stop=STOP if kind=='pwm' else (rise+100e-6 if kind=='cold' else 100e-6)
    rail=str(vdd) if kind in ['pwm','zero'] else pwl([(0,0),(1e-6,0),(1e-6+rise,vdd),(stop,vdd)])
    body=f'VDD vdd 0 {rail}\nVREFRAIL vdd refrail 0\nXREF refrail 0 out beta_reference RL={RL} START={start}\nVSENSE out bias 0\n'
    if kind=='pwm':
        body+=f'.include "{p.PIXEL}"\n'+led_part()+f'VLED led_a 0 {ledv}\nVPWM pwm 0 {pwm(events,vdd,stop)}\nXPIXEL 0 bias gate pwm pwm_b led_k vdd pixel_driver_layout\n'
        target='-i(vled)';additional='v(gate) v(pwm) v(led_k) i(vled)'
    else:
        body+='XLOAD bias bias 0 0 nfet_06v0 w=20u l=4u\n'
        target='i(vsense)';additional='v(bias) v(vdd) v(xref.rs)'
        # zero-state test explicitly initializes the undesired core equilibrium.
        body+=f'.ic v(vdd)={vdd if kind=="zero" else 0} v(refrail)={vdd if kind=="zero" else 0} v(out)=0 v(xref.pg)={vdd if kind=="zero" else 0} v(xref.nb)=0 v(xref.rs)=0 v(xref.su)=0 v(bias)=0\n'
    data=p.run(folder,body,f'''save v(bias) v(vdd) v(xref.pg) v(xref.nb) v(xref.rs) v(xref.su) i(vsense) i(vdd) i(vrefrail) {additional}
tran 10n {stop:.16g} 0 {maxstep:.16g} {'uic' if kind!='pwm' else ''}
let iout={target}
let isupply=-i(vdd)
let irefrail=i(vrefrail)
wrdata data.dat iout i(vsense) isupply irefrail v(bias) v(xref.pg) v(xref.nb) v(xref.rs) v(xref.su) v(vdd) {additional}
''',corner,'res_typical',temp)
    t=data[:,0];iout=data[:,1]
    if kind=='pwm':
        q=[integ(t,iout,LEFT+k*FRAME,LEFT+(k+1)*FRAME) for k in range(2)]
        return dict(duty=duty,maxstep_s=maxstep,frame_charge_c=q,average_current_a=sum(q)/(2*FRAME),
                    iref_mean_a=integ(t,data[:,2],LEFT,RIGHT)/(RIGHT-LEFT),
                    logic_total_power_w=vdd*integ(t,data[:,3],LEFT,RIGHT)/(RIGHT-LEFT),
                    reference_total_power_w=vdd*integ(t,data[:,4],LEFT,RIGHT)/(RIGHT-LEFT),
                    frame_repeatability_pct=100*abs(q[1]-q[0])/max(abs(sum(q)/2),1e-30),
                    iout_peak_a=float(iout.max()),bias_min_v=float(data[:,5].min()),bias_max_v=float(data[:,5].max()))
    endcurrent=integ(t,iout,stop-10e-6,stop)/10e-6
    relative=np.abs(iout-endcurrent)/max(abs(endcurrent),1e-30)
    after=(t>=(1e-6+rise if kind=='cold' else 0))
    bad=np.flatnonzero(after&(relative>.01))
    settled=(float(t[bad[-1]+1]) if len(bad) and bad[-1]+1<len(t) else None) if len(bad) else float(t[np.flatnonzero(after)[0]])
    delay=None if settled is None else max(0,settled-(1e-6+rise if kind=='cold' else 0))
    return dict(kind=kind,startup_enabled=bool(start),rise_s=rise if kind=='cold' else None,
                last_10us_mean_a=endcurrent,peak_a=float(iout.max()),minimum_a=float(iout.min()),
                settling_after_rail_s=delay,settles_within_20us=delay is not None and delay<=20e-6,
                nonzero_final=endcurrent>1e-6,bias_min_v=float(data[:,5].min()),bias_max_v=float(data[:,5].max()),
                bias_above_live_rail_max_v=float(np.max(data[:,5]-data[:,10])),
                raw_waveform=str((folder/'data.dat').relative_to(ROOT)))

def main():
    root=ROOT/'build/reference';root.mkdir(exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='run-',dir=root));frozen=work/'inputs';frozen.mkdir()
    inputs=['analog/reference/beta_multiplier.spice','scripts/reference/probe.py','scripts/reference/run.py',
            'evidence/layout/pixel_driver_rc.spice','analog/models/microled.spice','rtl/pixel_pwm.v','sim/rtl/tb_pixel_pwm.v','layout/pdk-lock.json']
    hashes={}
    for name in inputs:
        src=ROOT/name;dst=frozen/name;dst.parent.mkdir(parents=True,exist_ok=True);hashes[name]=p.sha(src);shutil.copyfile(src,dst)
        if p.sha(dst)!=hashes[name]:raise RuntimeError('freeze failed')
    lock=json.loads((ROOT/'layout/pdk-lock.json').read_text())
    for name in ['design.ngspice','sm141064.ngspice']:
        src=p.PDK/name
        if p.sha(src)!=lock['files']['libs.tech/ngspice/'+name]:raise RuntimeError('Locked PDK mismatch')
        dst=frozen/'pdk'/name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(src,dst)
        hashes['PDK/'+name]=p.sha(dst)
    p.PDK=frozen/'pdk';p.REF=frozen/'analog/reference/beta_multiplier.spice';p.PIXEL=frozen/'evidence/layout/pixel_driver_rc.spice';p.LED=frozen/'analog/models/microled.spice'
    version=p.command(['ngspice','--version'],work,'ngspice-version.log')
    gates=dict(nominal_reference_calibration_error_pct=.1,absolute_current_error_pct=5,lowest_code_charge_error_pct=2,
               off_current_a=1e-9,startup_settling_after_full_rail_s=20e-6,startup_settling_band_pct=1,fine_step_charge_difference_pct=.2)
    save(work/'plan.json',dict(gates=gates,rl_m=RL,resistor_width_m=2e-6,scope='Schematic eight MOS + PDK resistor reference; selected existing six MOS analog PEX, direct ideal PWM pin, no joint output buffer or reference layout'))
    # Calibrate only at TT/27C/3.3V with a declared 1.4V voltage-clamp load.
    calibration=[];lo,hi=12e-6,16e-6
    for k in range(15):
        mid=(lo+hi)/2;r=p.op(work/f'cal-{k}',rl=mid);calibration.append(dict(rl_m=mid,**r))
        if r['iref_a']>100e-6:lo=mid
        else:hi=mid
    chosen=round((lo+hi)/2/10e-9)*10e-9
    if abs(chosen-RL)>1e-15:raise RuntimeError('Nominal calibration no longer chooses declared 13.5um grid length')
    nominal=p.op(work/'nominal',rl=RL)
    # MOS corners and resistor corners are INDEPENDENT axes, not paired labels.
    conds=list(itertools.product(['typical','ff','ss','fs','sf'],['res_typical','res_ff','res_ss'],[0,27,85],[2.97,3.3,3.63]))
    def dcrun(item):
        k,(corner,res,temp,logic)=item
        r=p.op(work/f'pvt-{k:03d}',rl=RL,corner=corner,res=res,temp=temp,logic=logic)
        return dict(corner=corner,resistor_corner=res,temperature_c=temp,logic_v=logic,**r,
                    reference_error_pct=100*(r['iref_a']/100e-6-1),absolute_current_budget_pass=abs(r['iref_a']/100e-6-1)<=.05)
    with ThreadPoolExecutor(max_workers=4) as pool:pvt=list(pool.map(dcrun,enumerate(conds)))
    coupled=[]
    for name,c in ENVS.items():
        corner,temp,logic,ledv=c
        for res in ['res_typical','res_ff','res_ss']:
            for state in [0,1]:
                r=p.op(work/f'coupled-{name}-{res}-{state}',rl=RL,corner=corner,temp=temp,logic=logic,ledv=ledv,res=res,pixel=True,pwm=state)
                coupled.append(dict(envelope=name,resistor_corner=res,pwm_on=bool(state),**r,absolute_current_budget_pass=(abs(r['iout_a']/100e-6-1)<=.05 if state else abs(r['iout_a'])<1e-9)))
    compliance=[]
    for name,c in ENVS.items():
        corner,temp,logic,_=c
        baseline=p.op(work/f'compliance-base-{name}',rl=RL,corner=corner,temp=temp,logic=logic)
        for k,load in enumerate(np.linspace(0,logic,34)):
            r=p.op(work/f'compliance-{name}-{k}',rl=RL,corner=corner,temp=temp,logic=logic,load=float(load))
            compliance.append(dict(envelope=name,output_v=float(load),headroom_v=logic-float(load),relative_to_1p4v_pct=100*(r['iref_a']/baseline['iref_a']-1),**r))
    supply=[]
    for k,voltage in enumerate(np.arange(0,3.81,.1)):
        # Actual diode-connected MREF load, never back-power the output with clamp.
        r=p.op(work/f'supply-{k}',rl=RL,logic=float(voltage),pixel=True,pwm=0)
        supply.append(dict(logic_v=float(voltage),**r))
    startup=[]
    for name,c in ENVS.items():
        for rise in [100e-9,10e-6,1e-3]:
            r=transient(work/f'cold-{name}-{rise}',c,kind='cold',rise=rise,maxstep=min(rise/10,100e-9))
            startup.append(dict(envelope=name,**r))
        for enabled in [1,0]:
            r=transient(work/f'zero-{name}-{enabled}',c,kind='zero',start=enabled,maxstep=20e-9)
            startup.append(dict(envelope=name,**r))
    binary=work/'pwm.vvp';p.command(['iverilog','-g2012','-s','tb_pixel_pwm','-o',binary,frozen/'rtl/pixel_pwm.v',frozen/'sim/rtl/tb_pixel_pwm.v'],work,'iverilog.log')
    traces={}
    for duty in [0,1,64,256]:
        path=work/f'pwm-{duty}.csv';out=p.command(['vvp',binary,f'+OUT={path}',f'+DUTY={duty}','+ENABLE=1','+TRACE_ONLY=1'],work,f'rtl-{duty}.log')
        if 'measure_start_ns=514500' not in out:raise RuntimeError('RTL frame origin changed')
        traces[duty]=read_events(path)
    waves=[]
    for name,c in ENVS.items():
        full=next(r['iout_a'] for r in coupled if r['envelope']==name and r['resistor_corner']=='res_typical' and r['pwm_on'])
        for duty in [0,1,64,256]:
            r=transient(work/f'pwm-{name}-{duty}',c,events=traces[duty],duty=duty)
            charge_error=[100*(q/(full*duty*1e-6)-1) for q in r['frame_charge_c']] if duty else None
            waves.append(dict(envelope=name,dc_full_a=full,charge_error_pct=charge_error,charge_budget_pass=(max(map(abs,charge_error))<=2 if duty==1 else None),**r))
        r=transient(work/f'pwm-{name}-1-fine',c,events=traces[1],duty=1,maxstep=2e-9)
        coarse=next(x for x in waves if x['envelope']==name and x['duty']==1)
        waves.append(dict(envelope=name,dc_full_a=full,charge_error_pct=[100*(q/(full*1e-6)-1) for q in r['frame_charge_c']],
                          fine_step_delta_pct=100*(r['average_current_a']/coarse['average_current_a']-1),**r))
    files={'calibration.csv':calibration,'pvt.csv':pvt,'coupled-dc.csv':coupled,'compliance.csv':compliance,'supply.csv':supply,'startup.json':startup,'pwm.json':waves}
    for name,obj in files.items():csvsave(work/name,obj) if name.endswith('.csv') else save(work/name,obj)
    summary=dict(schema_version=1,status='experiment_complete_not_accuracy_qualified',workdir=str(work.relative_to(ROOT)),
        scope=json.loads((work/'plan.json').read_text())['scope'],source_hashes=hashes,ngspice_version=version,gates=gates,
        topology=dict(mos_count=8,resistor='GF180 ppolyf_u',resistor_width_m=2e-6,resistor_length_m=RL,output_direction='PMOS sources into pixel MREF bias',enable=False,por=False),
        nominal=nominal,nominal_calibration_pass=abs(nominal['iref_a']/100e-6-1)<=.001,
        pvt=dict(n=len(pvt),min_iref_a=min(r['iref_a'] for r in pvt),max_iref_a=max(r['iref_a'] for r in pvt),failed_absolute_budget=sum(not r['absolute_current_budget_pass'] for r in pvt),
                 worst_low=min(pvt,key=lambda r:r['iref_a']),worst_high=max(pvt,key=lambda r:r['iref_a'])),
        coupled_dc=coupled,startup=startup,pwm=waves,
        limitations=['No reference layout/PEX or loop AC stability signoff; finite cold/zero-state tests do not prove every basin or ramp.',
                     'Reference is pre-layout: MOS as/ad/ps/pd default zero; intrinsic BSIM charges present, unextracted diffusion/routing absent.',
                     'Resistor PDK includes body/end TC and substrate capacitance; local resistor mismatch is disabled (mis_r=0) in locked model, no yield claim.',
                     'No trim, bandgap, temperature compensation, enable, power monitor or POR.',
                     'Existing analog PEX load only; direct ideal pin replay excludes digital buffer and current joint cutout.',
                     'Synthetic LED dynamic model only; no optical, measured LED capacitance, package, ESD or thermal feedback.',
                     '0.1-7mA bank feasibility is separate root experiment; not qualified by 100uA reference.'],
        raw_failures=['build/reference/probe-8l6_9jw6: initial incorrect core drain topology; corrected before nominal calibration; snapshot in initial-topology-failure',
                      'build/reference/run-_scwsghb/zero-tt-1: incomplete UIC rail initialization produced timestep-too-small at 100ps; fixed testbench specifies both ideal rail nodes at 3.3V, no circuit change'],
        result_files_sha256={name:p.sha(work/name) for name in files})
    # Ensure published evidence has not silently changed inputs during the run.
    for name,h in hashes.items():
        if not name.startswith('PDK/') and p.sha(ROOT/name)!=h:raise RuntimeError('Source changed during run: '+name)
    save(work/'summary.json',summary)
    evidence=ROOT/'evidence/reference';evidence.mkdir(parents=True,exist_ok=True)
    for name in [*files,'summary.json','plan.json']:shutil.copyfile(work/name,evidence/name)
    print(json.dumps(dict(workdir=str(work),pvt=summary['pvt'],nominal=nominal,startup=startup,pwm=waves),indent=2))

if __name__=='__main__':main()
