"""Schematic-only 0.1-7 mA geometry/headroom study; preserve the old baseline."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import csv, hashlib, json, math, os, re, shutil, subprocess, tempfile
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
PDK=ROOT/'build/layout/pdk/gf180mcuD'
EVIDENCE=ROOT/'evidence/current-range'
VECTORS=['v(bias)','v(gate)','v(led_k)','v(pwm)','i(VLED)','i(VLOG)','i(VREF)']
LEFT,RIGHT=514.5e-6,1026.5e-6

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,folder,name):
    p=subprocess.run([str(x) for x in args],cwd=folder,capture_output=True,text=True)
    (folder/name).write_text(p.stdout+p.stderr)
    if p.returncode or re.search(r'(?im)^Error:|timestep too small|simulation interrupted',p.stdout+p.stderr):
        raise RuntimeError(str(folder/name))
    return p.stdout
def integral(t,y,left,right):
    if np.any(np.diff(t)<=0) or not np.isfinite(y).all() or t[0]>left or t[-1]<right:
        raise ValueError('Uncovered or invalid integral window')
    mask=(t>left)&(t<right)
    x=np.r_[left,t[mask],right];v=np.r_[np.interp(left,t,y),y[mask],np.interp(right,t,y)]
    return float(np.sum(np.diff(x)*(v[:-1]+v[1:])/2))

def main():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    (ROOT/'build/current-range').mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='range-',dir=ROOT/'build/current-range'))
    inputs=['scripts/current_range/run.py','analog/current_range/pixel_bank.spice',
            'scripts/interface/buf_2.spice','analog/models/microled.spice',
            'analog/models/measured-led/lin2026-yellow20-dc.spice',
            'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv',
            'rtl/pixel_pwm.v','sim/rtl/tb_pixel_pwm.v','layout/pdk-lock.json']
    frozen=work/'inputs';hashes={}
    for name in inputs:
        target=frozen/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target);hashes[name]=sha(target)
    lock=json.loads((frozen/'layout/pdk-lock.json').read_text())
    for name in ['libs.tech/ngspice/design.ngspice','libs.tech/ngspice/sm141064.ngspice']:
        if sha(PDK/name)!=lock['files'][name]:raise ValueError('PDK lock mismatch: '+name)
        hashes['build/layout/pdk/gf180mcuD/'+name]=sha(PDK/name)
    version=run(['ngspice','--version'],work,'ngspice-version.log')
    binary=work/'pwm.vvp'
    run(['iverilog','-g2012','-s','tb_pixel_pwm','-o',binary,frozen/'rtl/pixel_pwm.v',frozen/'sim/rtl/tb_pixel_pwm.v'],work,'rtl-compile.log')
    traces={}
    for duty in [0,1,64,256]:
        path=work/f'duty{duty}.csv'
        run(['vvp',binary,f'+OUT={path}',f'+DUTY={duty}','+ENABLE=1','+TRACE_ONLY=1'],work,f'rtl-{duty}.log')
        events=[(float(x['time_ns'])*1e-9,int(x['pwm'])) for x in csv.DictReader(path.open())]
        points=[(0,0)];previous=0
        for t,v in events:
            if t+1e-9>=RIGHT+2e-6:break
            if v!=previous:points.extend([(t,previous),(t+1e-9,v)])
            previous=v
        points.append((RIGHT+2e-6,previous))
        traces[duty]='PWL(\n'+'\n'.join(f'+ {t:.16g} {v*3.3:.16g}' for t,v in points)+'\n+)'
    led_is=100e-6/math.expm1((2.8-100e-6*50)/(3*8.617333262145e-5*300.15))
    def calibrate(load,current):
        folder=work/f'calibration_{load}_{current:g}A';folder.mkdir()
        model=frozen/('analog/models/microled.spice' if load=='synthetic' else 'analog/models/measured-led/lin2026-yellow20-dc.spice')
        subckt='microled' if load=='synthetic' else 'lin2026_yellow20_dc'
        (folder/'testbench.spice').write_text(f'''Independent LED calibration {load}
.param LED_IS={led_is:.17g}
.temp 27
.include "{model}"
ICAL 0 anode {current:.17g}
XLED anode 0 {subckt}
.options reltol=1e-8 abstol=1e-14 vntol=1e-9
.control
set numdgt=15
set wr_singlescale
set wr_vecnames
op
wrdata calibration.dat v(anode)
quit
.endc
.end
''')
        run(['ngspice','-b','testbench.spice'],folder,'ngspice.log')
        a=np.atleast_2d(np.loadtxt(folder/'calibration.dat',skiprows=1))
        return dict(load=load,current_A=current,VF_V=float(a[0,1]))
    independent_calibrations=[calibrate('synthetic',100e-6)]+[calibrate('measured_static',i) for i in [100e-6,1e-3,7e-3]]
    def simulate(case):
        folder=work/case['name'];folder.mkdir()
        for name in ['design.ngspice','sm141064.ngspice']:
            (folder/name).symlink_to(os.path.relpath(PDK/'libs.tech/ngspice'/name,folder))
        measured=case['load']=='measured_static'
        led=(f'.include "{frozen/"analog/models/measured-led/lin2026-yellow20-dc.spice"}"\nXLED led_a led_k lin2026_yellow20_dc' if measured else
             f'.include "{frozen/"analog/models/microled.spice"}"\nXLED led_a led_k microled')
        transient='duty' in case
        control=(f'tran 20n {RIGHT+2e-6:.16g} 0 {case.get("maxstep_ns",20)}n' if transient else 'op')
        stimulus=traces[case['duty']] if transient else '3.3'
        reference=('VBIAS ref_probe 0 1.37222785180938' if case.get('bias_mode')=='ideal_voltage' else 'IREF vlogic ref_probe 100u')
        deck=f'''Current range geometry experiment {case['name']}
.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0 LED_IS={led_is:.17g}
.lib sm141064.ngspice typical
.temp 27
.include "{frozen/'analog/current_range/pixel_bank.spice'}"
.include "{frozen/'scripts/interface/buf_2.spice'}"
VLOG vlogic 0 3.3
VLED led_a 0 {case['led_v']}
VREF ref_probe bias 0
{reference}
VINPUT input 0 {stimulus}
XBUF input pwm vlogic vlogic 0 0 gf180mcu_fd_sc_mcu7t5v0__buf_2
XPIX led_k pwm vlogic bias gate pwm_b pixel_bank UNIT_COUNT={case['units']} SWITCH_SCALE={case.get('switch_scale',1)}
{led}
.options reltol=1e-7 abstol=1e-14 vntol=1e-9
.control
set numdgt=15
set wr_singlescale
set wr_vecnames
{control}
wrdata result.dat {' '.join(VECTORS)}
quit
.endc
.end
'''
        (folder/'testbench.spice').write_text(deck);run(['ngspice','-b','testbench.spice'],folder,'ngspice.log')
        data=np.atleast_2d(np.loadtxt(folder/'result.dat',skiprows=1))
        if data.shape[1]!=len(VECTORS)+1 or not np.isfinite(data).all():raise ValueError('Bad vectors')
        current=-data[:,5]
        target=case['units']*100e-6
        if transient:
            avg=integral(data[:,0],current,LEFT,RIGHT)/(RIGHT-LEFT)
            result=case|dict(current_average_A=avg,minimum_gate_V=float(data[:,2].min()),maximum_gate_V=float(data[:,2].max()),
                waveform_path=str((folder/'result.dat').relative_to(ROOT)))
            # Compact proof still retains all adaptive samples, no decimation.
            dest=EVIDENCE/(case['name']+'.csv')
            with dest.open('w') as f:
                w=csv.writer(f);w.writerow(['time_s','bias_V','gate_V','led_k_V','pwm_V','LED_branch_A','logic_source_A','reference_A'])
                for row in data:w.writerow([row[0],*row[1:5],-row[5],-row[6],row[7]])
            result['evidence_waveform']=str(dest.relative_to(ROOT));result['waveform_sha256']=sha(dest)
        else:
            a=data[0];actual=float(current[0]);vf=case['led_v']-a[3]
            result=case|dict(target_A=target,current_A=actual,error_pct=(actual/target-1)*100,
                            reference_A=float(a[7]),bias_V=float(a[1]),gate_V=float(a[2]),LED_V=float(vf),output_VDS_V=float(a[3]),
                            LED_rail_power_W=case['led_v']*actual)
        return result
    # Freeze absolute accuracy 5% and PWM area 2% before running; failures stay.
    cases=[dict(name=f'dc_measured_{v:g}V_n{n}',load='measured_static',led_v=v,units=n)
           for v in [5,6] for n in range(1,71)]
    cases += [dict(name=f'dc_synthetic_n{n}',load='synthetic',led_v=5,units=n) for n in [1,10,70]]
    cases += [dict(name=f'pwm_n{n}_d{d}_step{s}',load='synthetic',led_v=5,units=n,duty=d,maxstep_ns=s)
              for n in [1,70] for d in [0,1,64,256] for s in ([20,5] if d==1 else [20])]
    cases += [dict(name=f'pwm70_{mode}_switch{scale}_d{d}',load='synthetic',led_v=5,units=70,
                   duty=d,maxstep_ns=5,bias_mode=mode,switch_scale=scale)
              for mode,scale in [('ideal_current',10),('ideal_voltage',1),('ideal_voltage',10)] for d in [1,256]]
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(simulate,cases))
    dc=[x for x in results if 'duty' not in x];trans=[x for x in results if 'duty' in x]
    for row in dc:row['within_predeclared_5pct']=abs(row['error_pct'])<=5
    for row in trans:
        full=next(x['current_average_A'] for x in trans if x['units']==row['units'] and x['duty']==256
                  and x.get('bias_mode','ideal_current')==row.get('bias_mode','ideal_current')
                  and x.get('switch_scale',1)==row.get('switch_scale',1))
        row['area_error_pct']=(row['current_average_A']/(full*row['duty']/256)-1)*100 if row['duty'] else None
        row['within_predeclared_2pct']=abs(row['area_error_pct'])<=2 if row['duty'] else abs(row['current_average_A'])<1e-9
    points=[(float(r['current_A']),float(r['voltage_V'])) for r in csv.DictReader((frozen/inputs[5]).open())]
    def vf_at(i):
        for (i0,v0),(i1,v1) in zip(points,points[1:]):
            if i0<=i<=i1:return v0+(v1-v0)*(i-i0)/(i1-i0)
        raise ValueError('Outside measured static domain')
    calibrations={str(i):vf_at(i) for i in [100e-6,1e-3,7e-3]}
    with (EVIDENCE/'dc.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(dc[0]));w.writeheader();w.writerows(dc)
    summary=dict(study_date='2026-10-13',stage='new schematic transistor simulation plus static measured-data replay',
                 completed=True,qualified_entire_0p1_to_7mA_range=False,work_directory=str(work.relative_to(ROOT)),
                 conditions=dict(MOS_corner='typical',temperature_C=27,logic_V=3.3,reference_A=100e-6,
                     static_data_temperature='unspecified',geometry_parameter='UNIT_COUNT 1..70 is not an implemented DAC',
                     LED_rails_V=[5,6],new_layout=False,full_PG=False,optical_measurement=False),
                 predeclared_thresholds=dict(absolute_current_pct=5,PWM_charge_pct=2,off_current_A=1e-9),
                 dc_calibration=dict(synthetic_target_V_at_100uA=2.8,LED_IS=led_is,
                     measured_static_V_by_current_A=calibrations,independent_SPICE=independent_calibrations),DC=dc,PWM=trans,
                 source_hashes=hashes,tools=dict(ngspice=version.splitlines()[:6]),
                 limitations=['Ideal IREF is intentionally retained to isolate output geometry/compliance.',
                     '6 V LED rail is an exploratory model condition, not a device or tapeout qualification.',
                     'Measured static curve has no dynamic/temperature/optical model.',
                     'Synthetic 7mA PWM is a hypothetical load experiment; no LED allowed current/current density is certified.',
                     'UNIT_COUNT increases transistor model area/capacitance, not a completed thermometer decoder/switch bank.',
                     'Ideal voltage bias is an A/B mechanism control, not an implemented voltage reference or buffer.',
                     'No new bank RC extraction, array gradients, thermal network, package or reliability signoff.'])
    (EVIDENCE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    shutil.copyfile(work/'ngspice-version.log',EVIDENCE/'ngspice-version.log')
    print(json.dumps(dict(DC_runs=len(dc),PWM_runs=len(trans),samples7mA=[x for x in dc if x['units']==70],
                         PWM70=[x for x in trans if x['units']==70],calibration=calibrations),ensure_ascii=False))

if __name__=='__main__':main()
