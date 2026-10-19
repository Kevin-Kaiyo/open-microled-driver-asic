"""Paired hypothetical junction geometry; never replaces frozen zero-area source."""
from pathlib import Path
import json,re,shutil,tempfile
import numpy as np
import probe as p
import servo as s
import run as b
from servo_boundaries import stress
ROOT=p.ROOT;E=ROOT/'evidence/reference'
DEVICES=['pbias','ptail','pd1','pd2','nd1','nd2','nstage','pload','preg','pout']
def main():
    main=json.loads((E/'servo-summary.json').read_text());base=ROOT/main['workdir']/'inputs'
    w=Path(tempfile.mkdtemp(prefix='junction-sensitivity-',dir=ROOT/'build/reference'));f=w/'inputs';f.mkdir()
    names=['analog/reference/vset_servo_with_junctions.spice','scripts/reference/junction_sensitivity.py','scripts/reference/servo_boundaries.py',
           'scripts/reference/servo.py','scripts/reference/probe.py','scripts/reference/run.py','evidence/layout/pixel_driver_rc.spice','analog/models/microled.spice','rtl/pixel_pwm.v','sim/rtl/tb_pixel_pwm.v']
    hashes={}
    for name in names:
        src=ROOT/name
        if name in main['source_hashes'] and p.sha(src)!=main['source_hashes'][name]:raise RuntimeError('Paired source identity changed')
        dst=f/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst);hashes[name]=p.sha(dst)
    for name in ['design.ngspice','sm141064.ngspice']:
        dst=f/'pdk'/name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(base/'pdk'/name,dst);hashes['PDK/'+name]=p.sha(dst)
    p.REF=f/'analog/reference/vset_servo_with_junctions.spice';p.PDK=f/'pdk';p.PIXEL=f/'evidence/layout/pixel_driver_rc.spice';p.LED=f/'analog/models/microled.spice'
    original_body=s.body
    s.body=lambda *args,**kwargs:original_body(*args,**kwargs).replace(' vset_reference\n',' vset_reference_junctions\n')
    original_run=p.run
    vectors=[f'@m.xref.x{name}.m0[{j}]' for name in DEVICES for j in ['ibd','ibs']]
    def run_with_junction_currents(folder,body,control,*args,**kwargs):
        if re.search(r'(?m)^save ',control):control=re.sub(r'(?m)^save (.*)$',lambda m:'save '+m[1]+' '+' '.join(vectors),control)
        lets='\n'.join(f'let j{k}={v}' for k,v in enumerate(vectors))
        control=re.sub(r'(?m)^wrdata data.dat (.*)$',lambda m:lets+'\nwrdata data.dat '+m[1]+' '+' '.join(f'j{k}' for k in range(len(vectors))),control)
        return original_run(folder,body,control,*args,**kwargs)
    p.run=run_with_junction_currents
    nominal=s.op(w/'nominal',s.STATE['tt'])
    dc=[]
    for name,c in s.STATE.items():dc.append(dict(envelope=name,**s.op(w/f'dc-{name}',c,pixel=True)))
    startup=[]
    for name in ['tt','fast']:
        c=s.STATE[name]
        for kind,initial in [('cold','low'),('initial','low'),('initial','high')]:
            row=s.tran(w/f'{kind}-{name}-{initial}',c,kind=kind,initial=initial)
            a=np.loadtxt(ROOT/row['raw_waveform'],skiprows=1)
            currents=a[:,-20:]
            diode={n:{j:dict(min_a=float(currents[:,k*2+q].min()),max_a=float(currents[:,k*2+q].max()),max_abs_a=float(np.abs(currents[:,k*2+q]).max())) for q,j in enumerate(['ibd','ibs'])} for k,n in enumerate(DEVICES)}
            startup.append(dict(envelope=name,**row,terminal_stress=stress(a),model_reported_junction_currents=diode))
    binary=w/'pwm.vvp';p.command(['iverilog','-g2012','-s','tb_pixel_pwm','-o',binary,f/'rtl/pixel_pwm.v',f/'sim/rtl/tb_pixel_pwm.v'],w,'iverilog.log')
    path=w/'pwm-1.csv';p.command(['vvp',binary,f'+OUT={path}','+DUTY=1','+ENABLE=1','+TRACE_ONLY=1'],w,'rtl.log');events=b.read_events(path)
    waves=[]
    for name,c in s.STATE.items():
        full=next(row['iout_a'] for row in dc if row['envelope']==name)
        for step in [10e-9,2e-9]:
            a=s.tran(w/f'pwm-{name}-{step}',c,kind='pwm',events=events,duty=1,maxstep=step)
            err=[100*(q/(full*1e-6)-1) for q in a['frame_charge_c']]
            paired=next(r for r in main['pwm'] if r['envelope']==name and r['duty']==1 and r['maxstep_s']==step)
            waves.append(dict(envelope=name,dc_full_a=full,charge_error_pct=err,charge_budget_pass=max(map(abs,err))<=2,
                              average_difference_vs_zero_area_pct=100*(a['average_current_a']/paired['average_current_a']-1),**a))
    summary=dict(status='complete_sensitivity_not_physical_signoff',workdir=str(w.relative_to(ROOT)),paired_zero_area_summary_sha256=p.sha(E/'servo-summary.json'),source_hashes=hashes,
                 hypothesis='Each of 10 reference MOS has per-side diffusion length0.44um: AD=AS=W*0.44um, PD=PS=2*(W+0.44um). All W/L,VSET,RSET,RBIAS,CCOMP unchanged. Not extracted layout.',
                 nominal=nominal,nominal_zero_area=main['nominal'],coupled_dc=dc,startup=startup,pwm=waves,
                 current_vector_note='PDK/ngspice BSIM4 @m.xref.xNAME.m0[ibd]/[ibs], signed model-reported drain/source junction current; recorded with physical node voltages. Not measured substrate injection or SOA.',
                 limitations=['Hypothetical diffusion geometry, not DRC/LVS/PEX or reliability signoff. Does not replace frozen source or safety evidence.',
                              'Standalone startup MREF load unchanged at as/ad/ps/pd defaults zero, isolating new reference geometry; coupled PWM uses existing actual pixel PEX geometry.',
                              'MOS intrinsic capacitance plus hypothetical diffusion included; layout interconnect, substrate/well impedance, guard-ring and package absent.'])
    for name,h in hashes.items():
        if not name.startswith('PDK/') and p.sha(ROOT/name)!=h:raise RuntimeError('Input changed')
    b.save(w/'junction-sensitivity.json',summary);shutil.copyfile(w/'junction-sensitivity.json',E/'junction-sensitivity.json')
    print(json.dumps(dict(nominal=nominal,dc=dc,startup=[{k:v for k,v in r.items() if k not in ['terminal_stress','model_reported_junction_currents']} for r in startup],pwm=waves),indent=2))
if __name__=='__main__':main()
