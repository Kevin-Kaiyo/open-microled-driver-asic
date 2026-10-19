"""Actual transistor VSET servo, with explicitly external precision V/R boundaries."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import itertools, json, shutil, tempfile
import numpy as np
import probe as p
import run as beta
ROOT=p.ROOT
SOURCE=ROOT/'analog/reference/vset_servo.spice'
STATE={'tt':('typical',27,3.3,5),'slow':('ss',85,2.97,4.5),'fast':('ff',0,3.63,5.5)}
NODES=['bias','sense','xref.n1','xref.n2','xref.ctrl','xref.tail','xref.pb','vdd','vset']

def body(c,v_error=0,r_error=0,pixel=False,level=1,clamp=1.4,rail=None,setpoint=None):
    corner,temp,vdd,ledv=c
    s=f'''VDD vdd 0 {vdd if rail is None else rail}
VREFRAIL vdd refrail 0
VSET vset 0 {.5*(1+v_error) if setpoint is None else setpoint}
XREF refrail 0 vset sense out vset_reference
RSET sense 0 {5000*(1+r_error):.16g}
VSENSE out bias 0
'''
    if pixel:
        s+=f'.include "{p.PIXEL}"\n'+beta.led_part()+f'VLED led_a 0 {ledv}\nVPWM pwm 0 {level}\nXPIXEL 0 bias gate pwm pwm_b led_k vdd pixel_driver_layout\n'
    elif clamp is None:s+='XLOAD bias bias 0 0 nfet_06v0 w=20u l=4u\n'
    else:s+=f'VLOAD bias 0 {clamp}\n'
    return s

def op(folder,c,v_error=0,r_error=0,pixel=False,level=None,clamp=1.4):
    text=body(c,v_error,r_error,pixel,c[2] if level is None else level,clamp)
    control=f'''op
let iout={'-i(vled)' if pixel else 'i(vsense)'}
let iref=i(vsense)
let supply=-i(vdd)
wrdata data.dat iout iref supply {' '.join('v('+n+')' for n in NODES)}
'''
    a=p.run(folder,text,control,c[0],'res_typical',c[1])[0,1:]
    names=['iout_a','iref_a','supply_a']+[n.replace('xref.','')+'_v' for n in NODES]
    result=dict(zip(names,map(float,a)));result['reference_error_pct']=100*(result['iref_a']/100e-6-1)
    result['sense_tracking_error_pct']=100*(result['sense_v']/(.5*(1+v_error))-1)
    result['absolute_current_error_pct']=100*(result['iout_a']/100e-6-1)
    return result

def tran(folder,c,kind='cold',rise=100e-9,initial='low',events=None,duty=1,maxstep=10e-9):
    vdd=c[2];stop=beta.STOP if kind=='pwm' else (rise+100e-6 if kind=='cold' else 100e-6)
    rail=str(vdd);vset='.5';level=vdd;clamp=None;pixel=kind=='pwm'
    if kind=='cold':
        rail=beta.pwl([(0,0),(1e-6,0),(1e-6+rise,vdd),(stop,vdd)])
        vset=beta.pwl([(0,0),(1e-6,0),(1e-6+rise,.5),(stop,.5)])
    if kind=='step':vset=beta.pwl([(0,.5),(20e-6,.5),(20.01e-6,.55),(50e-6,.55),(50.01e-6,.45),(80e-6,.45),(80.01e-6,.5),(stop,.5)])
    if kind=='pwm':level=beta.pwm(events,vdd,stop)
    text=body(c,pixel=pixel,level=level,clamp=clamp,rail=rail,setpoint=vset)
    if kind=='initial':
        # Test two opposing amplifier/output initial states with consistent rails.
        high=initial=='high'
        text+=f'.ic v(vdd)={vdd} v(refrail)={vdd} v(vset)=.5 v(sense)={vdd if high else 0} v(out)={vdd if high else 0} v(bias)={vdd if high else 0} v(xref.ctrl)={0 if high else vdd} v(xref.n2)={vdd if high else 0} v(xref.n1)=0 v(xref.tail)={vdd} v(xref.pb)={vdd}\n'
    if kind=='cold':text+='.ic '+' '.join(f'v({n})=0' for n in [*NODES,'out','refrail'])+'\n'
    save=' '.join('v('+n+')' for n in NODES)
    if pixel:save+=' i(vled) v(pwm) v(gate) v(led_k)'
    a=p.run(folder,text,f'''option reltol=1e-6 abstol=1e-12 vntol=1e-7
save {save} i(vsense) i(vdd) i(vrefrail)
tran 10n {stop:.16g} 0 {maxstep:.16g} {'uic' if kind in ['cold','initial'] else ''}
let iout={'-i(vled)' if pixel else 'i(vsense)'}
let iref=i(vsense)
let supply=-i(vdd)
let refrail=i(vrefrail)
wrdata data.dat iout iref supply refrail {' '.join('v('+n+')' for n in NODES)} {'v(pwm) v(gate) v(led_k)' if pixel else ''}
''',c[0],'res_typical',c[1])
    t=a[:,0];i=a[:,1];sense=a[:,6];vsetwave=a[:,13]
    # Column order: scale, Iout,Iref,Isupply,Irefrail, then NODES at 5..13.
    result=dict(kind=kind,maxstep_s=maxstep,peak_current_a=float(i.max()),min_current_a=float(i.min()),sense_min_v=float(sense.min()),sense_max_v=float(sense.max()),
                raw_waveform=str((folder/'data.dat').relative_to(ROOT)))
    if kind=='pwm':
        qs=[beta.integ(t,i,beta.LEFT+k*beta.FRAME,beta.LEFT+(k+1)*beta.FRAME) for k in range(2)]
        result.update(duty=duty,frame_charge_c=qs,average_current_a=sum(qs)/(2*beta.FRAME),
                      reference_total_power_w=vdd*beta.integ(t,a[:,4],beta.LEFT,beta.RIGHT)/(beta.RIGHT-beta.LEFT),
                      logic_total_power_w=vdd*beta.integ(t,a[:,3],beta.LEFT,beta.RIGHT)/(beta.RIGHT-beta.LEFT))
    elif kind=='step':
        result['step_windows']=[]
        for at,end in [(20.01e-6,50e-6),(50.01e-6,80e-6),(80.01e-6,stop)]:
            target=float(np.interp(end-1e-6,t,sense));mask=(t>at)&(t<end);idx=np.flatnonzero(mask&(np.abs(sense-target)>.01*abs(target)))
            settle=(max(0,float(t[idx[-1]+1])-at) if t[idx[-1]+1]<end else None) if len(idx) and idx[-1]+1<len(t) else (None if len(idx) else 0)
            result['step_windows'].append(dict(start_s=at,end_s=end,sense_final_v=target,settling_1pct_s=settle,settling_within_20us=settle is not None and settle<=20e-6,
                                              last_5us_current_a=beta.integ(t,i,end-5e-6,end)/5e-6))
    else:
        final=beta.integ(t,i,stop-10e-6,stop)/10e-6;origin=1e-6+rise if kind=='cold' else 0
        idx=np.flatnonzero((t>=origin)&(np.abs(i-final)>.01*abs(final)))
        settle=max(0,float(t[idx[-1]+1])-origin) if len(idx) and idx[-1]+1<len(t) else (None if len(idx) else 0)
        _,last=beta.clip(t,i,stop-10e-6,stop)
        result.update(initial_state=initial if kind=='initial' else None,rise_s=rise if kind=='cold' else None,last_10us_mean_a=final,
                      settling_after_rail_s=settle,settles_within_20us=settle is not None and settle<=20e-6,nonzero_final=final>1e-6,
                      last_10us_ripple_pp_pct=100*float(np.ptp(last))/max(abs(final),1e-30))
    return result

def main():
    work=Path(tempfile.mkdtemp(prefix='servo-',dir=ROOT/'build/reference'));f=work/'inputs';f.mkdir()
    paths=['analog/reference/vset_servo.spice','scripts/reference/servo.py','scripts/reference/probe.py','scripts/reference/run.py','evidence/layout/pixel_driver_rc.spice','analog/models/microled.spice','rtl/pixel_pwm.v','sim/rtl/tb_pixel_pwm.v','layout/pdk-lock.json']
    hashes={}
    for name in paths:
        src=ROOT/name;dst=f/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst);hashes[name]=p.sha(src)
        if p.sha(dst)!=hashes[name]:raise RuntimeError('freeze changed')
    lock=json.loads((ROOT/'layout/pdk-lock.json').read_text())
    for name in ['design.ngspice','sm141064.ngspice']:
        src=p.PDK/name
        if p.sha(src)!=lock['files']['libs.tech/ngspice/'+name]:raise RuntimeError('PDK differs from lock')
        dst=f/'pdk'/name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(src,dst);hashes['PDK/'+name]=p.sha(src)
    p.REF=f/'analog/reference/vset_servo.spice';p.PDK=f/'pdk';p.PIXEL=f/'evidence/layout/pixel_driver_rc.spice';p.LED=f/'analog/models/microled.spice'
    p.command(['ngspice','--version'],work,'ngspice-version.log')
    gates=dict(absolute_current_error_pct=5,lowest_code_charge_error_pct=2,off_current_a=1e-9,settling_band_pct=1,settling_limit_s=20e-6,
               fine_step_charge_delta_pct=.2,external_vset_error_pct=.1,external_rset_error_pct=.1)
    beta.save(work/'plan.json',dict(gates=gates,mos_count=10,vset_v=.5,rset_ohm=5000,rbias_ohm=100000,miller_compensation_f=3e-12,
                                  scope='Pre-layout actual 10MOS amplifier/source servo, external VSET/RSET/RBIAS and schematic CCOMP. No trim fitted to output.'))
    nominal=op(work/'nominal',STATE['tt'])
    cond=list(itertools.product(['typical','ff','ss','fs','sf'],[0,27,85],[2.97,3.3,3.63],[-.001,.001],[-.001,.001]))
    def worker(item):
        k,(corner,temp,vdd,ve,re)=item;c=(corner,temp,vdd,5)
        a=op(work/f'pvt-{k:03d}',c,ve,re)
        return dict(corner=corner,temperature_c=temp,logic_v=vdd,vset_error_fraction=ve,rset_error_fraction=re,**a,absolute_current_budget_pass=abs(a['reference_error_pct'])<=5)
    with ThreadPoolExecutor(max_workers=4) as pool:pvt=list(pool.map(worker,enumerate(cond)))
    coupled=[]
    for name,c in STATE.items():
        for level in [0,c[2]]:
            a=op(work/f'coupled-{name}-{int(level>0)}',c,pixel=True,level=level)
            coupled.append(dict(envelope=name,pwm_on=level>0,**a,absolute_current_budget_pass=(abs(a['absolute_current_error_pct'])<=5 if level else abs(a['iout_a'])<1e-9)))
    # Demonstrate external tolerance endpoints remain bounded with the actual pixel.
    for name,c in STATE.items():
        for ve,re in itertools.product([-.001,.001],repeat=2):
            a=op(work/f'coupled-bounds-{name}-{ve}-{re}',c,ve,re,pixel=True)
            coupled.append(dict(envelope=name,pwm_on=True,**a,absolute_current_budget_pass=abs(a['absolute_current_error_pct'])<=5))
    compliance=[]
    for name,c in STATE.items():
        center=op(work/f'compliance-base-{name}',c)
        for k,load in enumerate(np.linspace(0,c[2],34)):
            a=op(work/f'compliance-{name}-{k}',c,clamp=float(load))
            compliance.append(dict(envelope=name,output_v=float(load),headroom_v=c[2]-float(load),relative_to_1p4v_pct=100*(a['iref_a']/center['iref_a']-1),**a))
    startup=[]
    for name,c in STATE.items():
        for rise in [100e-9,10e-6,1e-3]:startup.append(dict(envelope=name,**tran(work/f'cold-{name}-{rise}',c,kind='cold',rise=rise,maxstep=min(100e-9,rise/10))))
        for initial in ['low','high']:startup.append(dict(envelope=name,**tran(work/f'initial-{name}-{initial}',c,kind='initial',initial=initial)))
        startup.append(dict(envelope=name,**tran(work/f'step-{name}',c,kind='step')))
    binary=work/'pwm.vvp';p.command(['iverilog','-g2012','-s','tb_pixel_pwm','-o',binary,f/'rtl/pixel_pwm.v',f/'sim/rtl/tb_pixel_pwm.v'],work,'iverilog.log')
    traces={}
    for duty in [0,1,64,256]:
        path=work/f'pwm-{duty}.csv';out=p.command(['vvp',binary,f'+OUT={path}',f'+DUTY={duty}','+ENABLE=1','+TRACE_ONLY=1'],work,f'rtl-{duty}.log')
        if 'measure_start_ns=514500' not in out:raise RuntimeError('RTL origin changed')
        traces[duty]=beta.read_events(path)
    waves=[]
    for name,c in STATE.items():
        full=next(r['iout_a'] for r in coupled if r['envelope']==name and r['pwm_on'])
        for duty in [0,1,64,256]:
            a=tran(work/f'pwm-{name}-{duty}',c,kind='pwm',events=traces[duty],duty=duty)
            err=[100*(q/(full*duty*1e-6)-1) for q in a['frame_charge_c']] if duty else None
            waves.append(dict(envelope=name,dc_full_a=full,charge_error_pct=err,charge_budget_pass=max(map(abs,err))<=2 if duty==1 else None,**a))
        a=tran(work/f'pwm-{name}-1-fine',c,kind='pwm',events=traces[1],duty=1,maxstep=2e-9)
        coarse=next(r for r in waves if r['envelope']==name and r['duty']==1)
        waves.append(dict(envelope=name,dc_full_a=full,charge_error_pct=[100*(q/(full*1e-6)-1) for q in a['frame_charge_c']],
                          fine_step_delta_pct=100*(a['average_current_a']/coarse['average_current_a']-1),**a))
    files={'servo-pvt.csv':pvt,'servo-coupled-dc.json':coupled,'servo-compliance.csv':compliance,'servo-startup.json':startup,'servo-pwm.json':waves}
    for name,obj in files.items():beta.csvsave(work/name,obj) if name.endswith('.csv') else beta.save(work/name,obj)
    summary=dict(schema_version=1,status='experiment_complete',candidate='external_vset_transistor_servo',workdir=str(work.relative_to(ROOT)),source_hashes=hashes,gates=gates,
                 scope=json.loads((work/'plan.json').read_text())['scope'],nominal=nominal,
                 pvt=dict(n=len(pvt),min_iref_a=min(r['iref_a'] for r in pvt),max_iref_a=max(r['iref_a'] for r in pvt),failed_absolute_budget=sum(not r['absolute_current_budget_pass'] for r in pvt),
                          worst_low=min(pvt,key=lambda r:r['iref_a']),worst_high=max(pvt,key=lambda r:r['iref_a'])),coupled_dc=coupled,startup=startup,pwm=waves,
                 limitations=['VSET 0.5V and RSET 5k precision +/-0.1% each are external declared boundaries, not a simulated chip bandgap or selected hardware part.',
                              'RBIAS100k and Miller C3p are schematic passive components with no implemented physical dimensions/TC or parasitic extraction.',
                              'No local mismatch/noise/PSRR/loop gain and phase-margin/ESD/layout/full system power qualification. Finite step tests are not AC stability signoff.',
                              'Reference MOS diffusion area/perimeter default zero; intrinsic BSIM charge retained. Pixel load is existing actual analog PEX.',
                              'Coupled dynamic LED synthetic. Reference has no enable or POR, and fault clamp remains independent.',
                              '0.1-7mA current-bank scaling is separately tested; does not upgrade this 100uA candidate to a 7mA driver.'],
                 numeric_options=dict(dc_reltol=1e-7,dc_abstol_a=1e-15,dc_vntol_v=1e-9,transient_reltol=1e-6,transient_abstol_a=1e-12,transient_vntol_v=1e-7,integration='default trapezoidal'),
                 raw_failures=['build/reference/servo-dynamic-probe-34nwnm7z: weak second stage (N10/4, Pload2/10) oscillated; initial erroneous settling field is superseded by waveform inspection. Actual failed netlist saved candidate-failed.spice. Increased second-stage transconductance/current: N20/1, Pload100/10. No fitted ideal amplifier.',
                               'build/reference/servo-y52vsir2/pwm-tt-1: 1fA/1nV tolerance hit timestep-too-small at first 1ns PWL edge; Gear2 at same tolerance also failed. Transient uses 1pA/0.1uV/reltol1e-6; DC remains strict. 10ns->2ns step convergence retained.',
                               'Hard initialized capacitor states may transiently drive sense below 0V; retain minima, do not label arbitrary initial states electrically safe.'],
                 result_files_sha256={name:p.sha(work/name) for name in files})
    for name,h in hashes.items():
        if not name.startswith('PDK/') and p.sha(ROOT/name)!=h:raise RuntimeError('Source changed during run: '+name)
    beta.save(work/'servo-summary.json',summary)
    out=ROOT/'evidence/reference';out.mkdir(exist_ok=True)
    for name in [*files,'servo-summary.json']:shutil.copyfile(work/name,out/name)
    shutil.copyfile(work/'plan.json',out/'servo-plan.json')
    beta.save(out/'summary.json',dict(status='two_candidates_complete',candidates={
        'beta':dict(summary='evidence/reference/beta-summary.json',status='experiment_complete_not_accuracy_qualified'),
        'vset_servo':dict(summary='evidence/reference/servo-summary.json',status='experiment_complete')}))
    print(json.dumps(dict(workdir=str(work),nominal=nominal,pvt=summary['pvt'],startup=startup,pwm=waves),indent=2))

if __name__=='__main__':main()
