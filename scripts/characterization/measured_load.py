"""Couple the measured static LED I-V to the locked pixel RC circuit.

The dataset does not identify temperature or charge dynamics. MOS temperature
is fixed at 27 C; the imported I-V table is never temperature-scaled. Optional
parallel capacitances are declared engineering probes, not fitted LED values.
"""
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path
import csv
import hashlib
import json
import os
import subprocess
import tempfile

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
LEFT,RIGHT,STOP=514.5e-6,1538.5e-6,1540.5e-6
FRAME=256e-6
MEASURE_FRAMES=4
PDK=ROOT/'build/layout/pdk/gf180mcuD'


def execute(args, folder, log):
    p=subprocess.run([str(x) for x in args],cwd=folder,capture_output=True,text=True)
    (folder/log).write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError(f'Command failed {p.returncode}: {folder/log}')
    return p.stdout


def window(t,y,left=LEFT,right=RIGHT):
    if (not np.isfinite(t).all() or not np.isfinite(y).all()
            or np.any(np.diff(t)<=0) or t[0]>left or t[-1]<right or right<=left):
        raise RuntimeError('Invalid/incomplete waveform')
    mask=(t>left)&(t<right)
    return np.r_[left,t[mask],right],np.r_[np.interp(left,t,y),y[mask],np.interp(right,t,y)]


def mean(t,y,left=LEFT,right=RIGHT):
    x,v=window(t,y,left,right)
    return float(np.sum(np.diff(x)*(v[:-1]+v[1:])*.5)/(right-left))


def domain_integrals(t,led_voltage,curve_voltage,curve_current,left=LEFT,right=RIGHT):
    """Integrate static I(V) along the piecewise-linear saved voltage waveform.

    Insert every model-knot crossing before trapezoidal integration. This is
    exact for that interpolated waveform, not a recovery of unrecorded SPICE
    time points or a physical qualification of its unmeasured extension.
    """
    if (len(curve_voltage)<2 or len(curve_voltage)!=len(curve_current)
            or not np.isfinite(curve_voltage).all() or not np.isfinite(curve_current).all()
            or curve_voltage[0]<=0 or curve_current[0]<=0
            or np.any(np.diff(curve_voltage)<=0) or np.any(np.diff(curve_current)<=0)):
        raise RuntimeError('Invalid measured curve for transient reconstruction')
    # This origin knot and end-segment extrapolation match the measured B source.
    knots=np.r_[0.,curve_voltage];currents=np.r_[0.,curve_current]
    x,v=window(t,led_voltage,left,right)
    additions=[]
    for threshold in knots:
        crossed=np.flatnonzero(((v[:-1]<threshold)&(v[1:]>threshold))
                              |((v[:-1]>threshold)&(v[1:]<threshold)))
        additions.extend((x[crossed]+(x[crossed+1]-x[crossed])
                          *(threshold-v[crossed])/(v[crossed+1]-v[crossed])).tolist())
    refined_t=np.unique(np.r_[x,additions])
    refined_v=np.interp(refined_t,x,v)
    static_i=np.interp(refined_v,knots,currents)
    below_origin=refined_v<knots[0];above_last=refined_v>knots[-1]
    static_i[below_origin]=(currents[0]+(refined_v[below_origin]-knots[0])
                            *(currents[1]-currents[0])/(knots[1]-knots[0]))
    static_i[above_last]=(currents[-1]+(refined_v[above_last]-knots[-1])
                          *(currents[-1]-currents[-2])/(knots[-1]-knots[-2]))
    dt=np.diff(refined_t)
    interval_v=(refined_v[:-1]+refined_v[1:])*.5
    charge=dt*(static_i[:-1]+static_i[1:])*.5
    below=interval_v<curve_voltage[0];above=interval_v>curve_voltage[-1]
    outside=below|above
    total_charge=float(charge.sum());outside_charge=float(charge[outside].sum())
    return dict(
        method='all PWL-knot crossings inserted along saved piecewise-linear V(t); signed static I(V) integrated separately from rail displacement current',
        voltage_domain_v=[float(curve_voltage[0]),float(curve_voltage[-1])],
        current_domain_a=[float(curve_current[0]),float(curve_current[-1])],
        window_voltage_min_v=float(refined_v.min()),window_voltage_max_v=float(refined_v.max()),
        outside_measured_domain_time_fraction=float(dt[outside].sum()/(right-left)),
        below_measured_domain_time_fraction=float(dt[below].sum()/(right-left)),
        above_measured_domain_time_fraction=float(dt[above].sum()/(right-left)),
        static_conduction_charge_c=total_charge,
        outside_measured_domain_signed_conduction_charge_c=outside_charge,
        outside_measured_domain_signed_conduction_charge_fraction=(outside_charge/total_charge if total_charge!=0 else None),
        signed_charge_fraction_note='ratio of signed charges, not absolute charge; no clamping to [0,1]; null if net conduction charge is zero',
        reconstructed_static_conduction_average_uA=total_charge/(right-left)*1e6,
        inserted_knot_crossings=len(refined_t)-len(x),
        dynamic_qualification=False)


def periodicity(t,rail_current,states):
    """Report four-frame repeatability; no unapproved settling threshold."""
    boundaries=LEFT+np.arange(MEASURE_FRAMES+1)*FRAME
    boundaries[-1]=RIGHT
    frame_means=[mean(t,rail_current,a,b)*1e6 for a,b in zip(boundaries[:-1],boundaries[1:])]
    average=mean(t,rail_current)*1e6
    state_metrics={}
    for name,values in states.items():
        samples=np.interp(boundaries,t,values)
        state_metrics[name]=dict(boundary_values_v=samples.tolist(),
                                peak_to_peak_v=float(np.ptp(samples)),
                                maximum_adjacent_frame_delta_v=float(np.max(np.abs(np.diff(samples)))),
                                end_minus_start_v=float(samples[-1]-samples[0]))
    return dict(frame_count=MEASURE_FRAMES,frame_period_s=FRAME,
                frame_boundaries_s=boundaries.tolist(),frame_average_rail_current_uA=frame_means,
                frame_average_peak_to_peak_uA=float(np.ptp(frame_means)),
                frame_average_relative_spread=(float(np.ptp(frame_means))/abs(average) if average!=0 else None),
                observed_node_same_phase_states=state_metrics,
                pass_threshold=None,passed=None,
                interpretation='reported numerical repeatability, no hidden pass threshold; same-phase observed voltages do not prove every internal charge state is periodic')


def main():
    lock=json.loads((ROOT/'layout/pdk-lock.json').read_text())
    for p,h in lock['files'].items():
        if hashlib.sha256((PDK/p).read_bytes()).hexdigest()!=h:
            raise RuntimeError('PDK differs from lock: '+p)
    (ROOT/'build/characterization').mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='measured-',dir=ROOT/'build/characterization'))
    inputs=['scripts/characterization/measured_load.py','rtl/pixel_pwm.v','sim/rtl/tb_pixel_pwm.v',
            'layout/pdk-lock.json','evidence/layout/pixel_driver_rc.spice',
            'analog/models/measured-led/lin2026-yellow20-dc.spice',
            'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv']
    hashes={}
    for name in inputs:
        p=work/'inputs'/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes((ROOT/name).read_bytes())
        hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    source=work/'inputs'
    with (source/'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv').open() as f:
        curve=list(csv.DictReader(f))
    curve_voltage=np.array([float(r['voltage_V']) for r in curve])
    curve_current=np.array([float(r['current_A']) for r in curve])
    version=execute(['ngspice','--version'],work,'ngspice-version.log')
    includes=f'''.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0
.include "{source/'analog/models/measured-led/lin2026-yellow20-dc.spice'}"
.include "{source/'evidence/layout/pixel_driver_rc.spice'}"
.temp 27
'''
    def folder_for(name):
        folder=work/name;folder.mkdir()
        for n in ['design.ngspice','sm141064.ngspice']:
            (folder/n).symlink_to(os.path.relpath(PDK/'libs.tech/ngspice'/n,folder))
        return folder
    def dc(case):
        folder=folder_for(case['name'])
        deck=f'''Measured static I-V coupled DC
{includes}
.lib sm141064.ngspice {case['corner']}
VDD led_a 0 {case['vled_v']}
VLOGIC vlogic 0 {case['vlogic_v']}
VPWM pwm 0 {case['vlogic_v']}
IREF vlogic bias {case['iref_uA']}u
XLED led_a led_k lin2026_yellow20_dc
XPIXEL 0 bias gate pwm pwm_b led_k vlogic pixel_driver_layout
.options reltol=1e-7 abstol=1e-14 vntol=1e-9
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
op
let branch = -i(VDD)
let logic = -i(VLOGIC)
wrdata values.dat branch v(led_k) v(bias) logic
quit
.endc
.end
'''
        (folder/'testbench.spice').write_text(deck)
        execute(['ngspice','-b','testbench.spice'],folder,'ngspice.log')
        data=np.atleast_2d(np.loadtxt(folder/'values.dat',skiprows=1))
        if data.shape!=(1,5) or not np.isfinite(data).all():raise RuntimeError(str(folder))
        current,cathode,bias,logic=data[0,1:]
        return case|dict(current_uA=float(current*1e6),error_pct=float((current/100e-6-1)*100),
                         led_v=float(case['vled_v']-cathode),cathode_v=float(cathode),bias_v=float(bias),
                         led_rail_power_uW=float(case['vled_v']*current*1e6),
                         logic_rail_power_uW=float(case['vlogic_v']*logic*1e6),
                         current_within_measured_domain=bool(1e-7<=current<=.032))
    cases=[dict(name=f'{c}_{v:.2f}_{l:.2f}_{i}',group='matrix',corner=c,vled_v=v,vlogic_v=l,iref_uA=i)
           for c,v,l,i in product(['typical','ff','ss','fs','sf'],[4.5,5,5.5],[2.97,3.3,3.63],[99.5,100,100.5])]
    cases += [dict(name=f'headroom_{v:.2f}',group='headroom',corner='typical',vled_v=v,vlogic_v=3.3,iref_uA=100)
              for v in [4,4.1,4.2,4.3,4.4,4.5,4.6,4.7,4.8,4.9,5,5.2,5.5]]
    with ThreadPoolExecutor(max_workers=4) as pool:dc_results=list(pool.map(dc,cases))
    binary=work/'pwm.vvp'
    execute(['iverilog','-g2012','-s','tb_pixel_pwm','-o',binary,source/'rtl/pixel_pwm.v',
             source/'sim/rtl/tb_pixel_pwm.v'],work,'rtl-compile.log')
    events={}
    for duty in [1,64,256]:
        p=work/f'events-{duty}.csv'
        execute(['vvp',binary,f'+OUT={p}',f'+DUTY={duty}','+ENABLE=1','+TRACE_ONLY=1'],work,f'rtl-{duty}.log')
        with p.open() as f:events[duty]=[(float(r['time_ns'])*1e-9,int(r['pwm'])) for r in csv.DictReader(f)]
    def transient(case):
        folder=folder_for(case['name'])
        pwl=[(0,0)];previous=0
        for t,v in events[case['duty']]:
            if v!=previous:pwl.extend([(t,previous*3.3),(t+10e-9,v*3.3)])
            previous=v
        pwl.append((STOP,previous*3.3))
        points='\n'.join(f'+ {t:.15g} {v:.15g}' for t,v in pwl)
        deck=f'''Measured static I-V with EXPLICIT ASSUMED parallel capacitor
{includes}
.lib sm141064.ngspice typical
VDD led_a 0 5
VLOGIC vlogic 0 3.3
VPWM pwm 0 PWL(
{points}
+)
IREF vlogic bias 100u
XLED led_a led_k lin2026_yellow20_dc
CASSUMED led_a led_k {case['assumed_cap_pF']}p
XPIXEL 0 bias gate pwm pwm_b led_k vlogic pixel_driver_layout
.options reltol=1e-7 abstol=1e-14 vntol=1e-9
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
tran 20n {STOP:.15g} 0 {case['maxstep_ns']}n
wrdata waveform.dat i(VDD) v(led_k) v(gate) v(bias) v(pwm_b)
quit
.endc
.end
'''
        (folder/'testbench.spice').write_text(deck)
        execute(['ngspice','-b','testbench.spice'],folder,'ngspice.log')
        data=np.loadtxt(folder/'waveform.dat',skiprows=1)
        if data.ndim!=2 or data.shape[1]!=6 or not np.isfinite(data).all():raise RuntimeError(str(folder))
        t=data[:,0];rail=-data[:,1];led_voltage=5-data[:,2]
        average=mean(t,rail)
        domain=domain_integrals(t,led_voltage,curve_voltage,curve_current)
        delta_v=float(np.interp(RIGHT,t,led_voltage)-np.interp(LEFT,t,led_voltage))
        capacitor_charge=case['assumed_cap_pF']*1e-12*delta_v
        charge_balance=dict(
            rail_charge_c=average*(RIGHT-LEFT),
            assumed_capacitor_end_minus_start_charge_c=capacitor_charge,
            rail_minus_reconstructed_static_and_capacitor_charge_c=(average*(RIGHT-LEFT)
                -domain['static_conduction_charge_c']-capacitor_charge),
            interpretation='diagnostic reconstruction residual; interpolated V(t) is approximate between saved SPICE steps; no pass threshold')
        repeatability=periodicity(t,rail,dict(led_k=data[:,2],gate=data[:,3],bias=data[:,4],pwm_b=data[:,5]))
        return case|dict(average_current_uA=average*1e6,
                         current_metric='mean LED rail current, including assumed capacitor displacement current',
                         measured_domain=domain,charge_balance=charge_balance,periodicity=repeatability,
                         dynamic_qualification=False)
    trans_cases=[dict(name=f'cap_{c}_d{d}',assumed_cap_pF=c,duty=d,maxstep_ns=20)
                 for c,d in product([.2,2,20],[1,64,256])]
    trans_cases += [dict(name='cap_20_d1_fine',assumed_cap_pF=20,duty=1,maxstep_ns=2)]
    with ThreadPoolExecutor(max_workers=4) as pool:trans_results=list(pool.map(transient,trans_cases))
    for r in trans_results:
        full=next(x['average_current_uA'] for x in trans_results if x['assumed_cap_pF']==r['assumed_cap_pF'] and x['duty']==256)
        r['area_error_pct']=(r['average_current_uA']/(full*r['duty']/256)-1)*100
    base=next(x for x in trans_results if x['name']=='cap_20_d1')['average_current_uA']
    fine=next(x for x in trans_results if x['name']=='cap_20_d1_fine')['average_current_uA']
    matrix=[r for r in dc_results if r['group']=='matrix']
    summary=dict(status='measured STATIC I-V coupled electrical model, not real dynamic/temperature qualification',
                 dynamic_qualification=False,
                 transient_interpretation='hypothetical constant capacitor plus measured static curve with unmeasured low-current/reverse/high-current extensions; area target is a probe criterion, not real LED dynamic qualification',
                 run_directory=str(work.relative_to(ROOT)),ngspice=version,source_hashes=hashes,
                 conditions=dict(mos_temperature_c=27,led_measurement_temperature='not reported',
                                 LED_temperature_scaling=False,reference='ideal 99.5/100/100.5 uA probes',
                                 transient=dict(corner='typical',vled_v=5,vlogic_v=3.3,iref_uA=100,
                                                input_ramp_ns=10,frame_period_s=FRAME,
                                                measurement_window_s=[LEFT,RIGHT],measured_frames=MEASURE_FRAMES,
                                                periodicity_pass_threshold=None)),
                 dc_runs=len(dc_results),matrix_runs=len(matrix),transient_runs=len(trans_results),
                 dc_results=dc_results,assumed_capacitance_transients=trans_results,
                 matrix_current_min_uA=min(r['current_uA'] for r in matrix),
                 matrix_current_max_uA=max(r['current_uA'] for r in matrix),
                 absolute_5percent_target_all_matrix_passed=all(abs(r['error_pct'])<=5 for r in matrix),
                 dc_all_currents_within_measured_domain=all(r['current_within_measured_domain'] for r in dc_results),
                 capacitance_probe_2percent_area_target_passed=all(abs(r['area_error_pct'])<=2 for r in trans_results),
                 refinement_relative_delta=abs(fine-base)/abs(base))
    (work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    destination=ROOT/'evidence/characterization/measured-load-summary.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes((work/'summary.json').read_bytes())
    print(json.dumps({k:v for k,v in summary.items() if k not in ['source_hashes','dc_results','assumed_capacitance_transients','ngspice']},indent=2))


if __name__=='__main__':main()
