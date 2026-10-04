"""Characterize the actual analog input and its actual routed buf_2 driver.

The six-MOS standard-cell SPICE is a schematic view, not cell PEX. The analog
RC is actual extracted geometry. Its dynamic LED remains a synthetic model;
the measured-static + 2pF variant is an explicitly hypothetical charge probe.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PDK = ROOT / 'build/layout/pdk/gf180mcuD'
CELL = 'gf180mcu_fd_sc_mcu7t5v0__buf_2'
LEFT, RIGHT, STOP = 514.5e-6, 1538.5e-6, 1540.5e-6
ENVELOPES = {
    'tt': dict(corner='typical', temperature_c=27, logic_v=3.3, led_v=5),
    'ss': dict(corner='ss', temperature_c=85, logic_v=2.97, led_v=4.5),
    'ff': dict(corner='ff', temperature_c=0, logic_v=3.63, led_v=5.5),
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(args, folder, log):
    p = subprocess.run([str(x) for x in args], cwd=folder, capture_output=True, text=True)
    (folder/log).write_text(p.stdout+p.stderr)
    if p.returncode:
        raise RuntimeError(f'{args[0]} exit {p.returncode}: {folder/log}')
    if args[0] == 'ngspice' and re.search(r'(?im)^Error:|timestep too small|simulation interrupted', p.stdout+p.stderr):
        raise RuntimeError(f'ngspice diagnostic failure: {folder/log}')
    return p.stdout


def clipped(t, y, left, right):
    if np.any(np.diff(t) <= 0) or not np.isfinite(y).all() or t[0] > left or t[-1] < right:
        raise RuntimeError('Invalid waveform or integration interval')
    mask = (t > left) & (t < right)
    return np.r_[left, t[mask], right], np.r_[np.interp(left, t, y), y[mask], np.interp(right, t, y)]


def integral(t, y, left=LEFT, right=RIGHT):
    x, v = clipped(t, y, left, right)
    return float(np.sum(np.diff(x)*(v[:-1]+v[1:])/2))


def crossings(t, y, level, rising):
    mask = ((y[:-1] < level) & (y[1:] >= level)) if rising else ((y[:-1] > level) & (y[1:] <= level))
    k = np.flatnonzero(mask)
    return t[k] + (level-y[k])*(t[k+1]-t[k])/(y[k+1]-y[k])


def edges(t, y, supply):
    results = {}
    for rising in (True, False):
        a = crossings(t, y, supply*(.3 if rising else .7), rising)
        b = crossings(t, y, supply*(.7 if rising else .3), rising)
        mids = crossings(t, y, supply*.5, rising)
        intervals = []
        for middle in mids[(mids > LEFT) & (mids < RIGHT)]:
            aa, bb = a[a <= middle], b[b >= middle]
            if not len(aa) or not len(bb):
                raise RuntimeError('Incomplete transition thresholds')
            intervals.append(float((bb[0]-aa[-1])*1e9))
        results['rise' if rising else 'fall'] = intervals
    rises = crossings(t, y, supply*.5, True)
    falls = crossings(t, y, supply*.5, False)
    pulses = {}
    for kind, a, b in (('high', rises, falls), ('low', falls, rises)):
        widths = []
        for x in a[(a > LEFT) & (a < RIGHT)]:
            next_b = b[b > x]
            if len(next_b) and next_b[0] < RIGHT:
                widths.append(float((next_b[0]-x)*1e9))
        pulses[kind+'_pulse_min_ns'] = min(widths) if widths else None
    return dict(rise_30_70_ns=max(results['rise']) if results['rise'] else None,
                fall_70_30_ns=max(results['fall']) if results['fall'] else None,
                rise_edges=len(results['rise']), fall_edges=len(results['fall']), **pulses)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--joint-link', type=Path, help='Optional actual PWM-only subckt pwm_link_rc A Y VDD VSS; A=analog, Y=digital')
    args = parser.parse_args()
    layout_lock = json.loads((ROOT/'layout/pdk-lock.json').read_text())
    physical_lock = json.loads((ROOT/'scripts/physical/pdk-lock.json').read_text())
    # Validate all SPICE dependencies actually consumed, including the library.
    checked = {}
    names = ['libs.tech/ngspice/design.ngspice', 'libs.tech/ngspice/sm141064.ngspice',
             'libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice']
    for name in names:
        expected = layout_lock['files'].get(name, physical_lock['files'].get(name))
        if sha(PDK/name) != expected:
            raise RuntimeError('PDK input differs from existing lock: '+name)
        checked[name] = expected
    sc = (PDK/names[-1]).read_text()
    a = sc.index('.SUBCKT '+CELL+' '); b = sc.index('.ENDS', a)+5
    subset = (ROOT/'scripts/interface/buf_2.spice').read_text()
    if sc[a:b] not in subset:
        raise RuntimeError('Public buf_2 subset differs from the locked full library')
    mapped = (ROOT/'evidence/physical/digital/nl/pixel_pwm.nl.v').read_text()
    if not re.search(r'__buf_2 output12 \(\.I\(net12\),\s*\.Z\(pwm\)\)', mapped):
        raise RuntimeError('Mapped final buffer changed; update mapping explicitly')
    liberty = PDK/'libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib'
    text = liberty.read_text()
    for key, value in [('slew_lower_threshold_pct_fall', 30), ('slew_lower_threshold_pct_rise', 30),
                       ('slew_upper_threshold_pct_fall', 70), ('slew_upper_threshold_pct_rise', 70)]:
        if not re.search(rf'{key}\s*:\s*{value}\s*;', text):
            raise RuntimeError('Liberty threshold changed')
    checked[str(liberty.relative_to(PDK))] = sha(liberty)
    (ROOT/'build/interface').mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='driver-', dir=ROOT/'build/interface'))
    inputs = ['scripts/interface/run.py', 'scripts/interface/buf_2.spice', 'rtl/pixel_pwm.v',
              'sim/rtl/tb_pixel_pwm.v', 'evidence/layout/pixel_driver_rc.spice',
              'evidence/physical/digital/nl/pixel_pwm.nl.v',
              'evidence/physical/digital/spef/nom/pixel_pwm.nom.spef',
              'analog/models/microled.spice', 'analog/models/measured-led/lin2026-yellow20-dc.spice',
              'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv',
              'layout/pdk-lock.json', 'scripts/physical/pdk-lock.json', 'scripts/characterization/measured_load.py']
    if args.joint_link:
        args.joint_link=args.joint_link.resolve()
        inputs.append(str(args.joint_link.relative_to(ROOT)))
        metadata=args.joint_link.with_name('link-rc.json')
        if metadata.exists():inputs.append(str(metadata.relative_to(ROOT)))
    hashes = {}
    for name in inputs:
        dest = work/'inputs'/name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, dest); hashes[name] = sha(dest)
    frozen = work/'inputs'
    joint_hash = None
    if args.joint_link:
        args.joint_link = args.joint_link.resolve()
        if not re.search(r'(?im)^\.subckt pwm_link_rc A Y VDD VSS\s*$', args.joint_link.read_text()):
            raise RuntimeError('Joint link interface must be pwm_link_rc A Y VDD VSS')
        shutil.copyfile(args.joint_link, work/'joint-link.spice'); joint_hash = sha(work/'joint-link.spice')
    version = run(['ngspice', '--version'], work, 'ngspice-version.log')
    helper_spec=importlib.util.spec_from_file_location('frozen_measured_load',frozen/'scripts/characterization/measured_load.py')
    measured_helper=importlib.util.module_from_spec(helper_spec);helper_spec.loader.exec_module(measured_helper)
    with (frozen/'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv').open() as f:curve=list(csv.DictReader(f))
    curve_v=np.array([float(r['voltage_V']) for r in curve]);curve_i=np.array([float(r['current_A']) for r in curve])
    # Synthetic diode calibration remains independent of MOS corners and drivers.
    vt = 8.617333262145e-5*300.15
    led_is = 100e-6/math.expm1((2.8-100e-6*50)/(3*vt))
    calibration = work/'calibration'; calibration.mkdir()
    deck = f'''Synthetic LED independent DC calibration\n.param LED_IS={led_is:.17g}
.include "{frozen/'analog/models/microled.spice'}"
IREF 0 anode 100u
XLED anode 0 microled
.options reltol=1e-9 abstol=1e-14 vntol=1e-10
.control
set numdgt=15
set wr_singlescale
set wr_vecnames
op
wrdata values.dat v(anode)
quit
.endc
.end
'''
    (calibration/'testbench.spice').write_text(deck)
    run(['ngspice','-b','testbench.spice'], calibration,'ngspice.log')
    calibrated_v = float(np.loadtxt(calibration/'values.dat', skiprows=1)[1])
    if abs(calibrated_v-2.8) > 1e-5:
        raise RuntimeError('Synthetic DC calibration failed')
    def folder_for(name):
        folder = work/name; folder.mkdir()
        for f in names[:2]:
            (folder/Path(f).name).symlink_to(os.path.relpath(PDK/f, folder))
        return folder
    def base(condition, led='synthetic'):
        ledpart = (f'.include "{frozen/"analog/models/microled.spice"}"\nXLED led_a led_k microled' if led=='synthetic'
                   else f'.include "{frozen/"analog/models/measured-led/lin2026-yellow20-dc.spice"}"\nXLED led_a led_k lin2026_yellow20_dc\nCASSUMED led_a led_k 2p')
        return f'''.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0 LED_IS={led_is:.17g}
.lib sm141064.ngspice {condition['corner']}
.include "{frozen/'evidence/layout/pixel_driver_rc.spice'}"
.include "{frozen/'scripts/interface/buf_2.spice'}"
.temp {condition['temperature_c']}
VDD led_a 0 {condition['led_v']}
VLOGIC vlogic 0 {condition['logic_v']}
VBUFFER vbuffer 0 {condition['logic_v']}
IREF vlogic bias 100u
{ledpart}
XPIXEL 0 bias gate pwm pwm_b led_k vlogic pixel_driver_layout
.options reltol=1e-7 abstol=1e-14 vntol=1e-9
'''
    # Static full-on absolute-current checks for both ideal and transistor drivers.
    def dc(case):
        c = ENVELOPES[case['envelope']]; folder = folder_for(case['name'])
        driver = ('VPWM pwm 0 '+str(c['logic_v']*case['level']) if case['driver']=='ideal'
                  else f'VIN input 0 {c["logic_v"]*case["level"]}\nXBUF input pwm vbuffer vbuffer 0 0 {CELL}')
        (folder/'testbench.spice').write_text(f'''Interface DC\n{base(c)}
{driver}
.control
set numdgt=15
set wr_singlescale
set wr_vecnames
op
wrdata values.dat i(VDD) i(VLOGIC) i(VBUFFER) v(pwm) v(led_k) v(gate) v(bias)
quit
.endc
.end
''')
        run(['ngspice','-b','testbench.spice'], folder,'ngspice.log')
        a = np.loadtxt(folder/'values.dat', skiprows=1)
        return case|dict(**c, led_current_uA=-float(a[1])*1e6, analog_logic_current_uA=-float(a[2])*1e6,
                         buffer_supply_current_uA=-float(a[3])*1e6, pwm_v=float(a[4]), led_k_v=float(a[5]),
                         gate_v=float(a[6]), bias_v=float(a[7]))
    dc_cases = [dict(name=f'dc_{e}_{d}_{level}', envelope=e, driver=d, level=level)
                for e in ENVELOPES for d in ['ideal','buffer'] for level in [0,1]]
    with ThreadPoolExecutor(max_workers=4) as pool: dc_results = list(pool.map(dc, dc_cases))
    # AC Y is bias/frequency dependent. It is not a single extracted cell C.
    ac_results = []
    for fraction in [0,.25,.5,.75,1]:
        c = ENVELOPES['tt']; folder=folder_for(f'ac_{fraction}')
        (folder/'testbench.spice').write_text(f'''Analog PWM small signal Y\n{base(c)}
VPWM pwm 0 DC {fraction*c['logic_v']} AC 1
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
ac dec 10 100k 1g
let conductance = real(-i(VPWM))
let susceptance = imag(-i(VPWM))
wrdata admittance.dat conductance susceptance
quit
.endc
.end
''')
        run(['ngspice','-b','testbench.spice'],folder,'ngspice.log')
        data=np.loadtxt(folder/'admittance.dat',skiprows=1)
        for freq in [1e5,1e6,1e7,1e8,1e9]:
            row=data[np.argmin(abs(data[:,0]-freq))]
            ac_results.append(dict(pwm_dc_v=fraction*c['logic_v'],frequency_hz=float(row[0]),
                                   conductance_s=float(row[1]), susceptance_s=float(row[2]),
                                   effective_parallel_capacitance_f=float(row[2]/(2*np.pi*row[0]))))
    # Complete transition charging, through all input-connected MOS and actual RC.
    def charge_probe(ramp_ns):
        c=ENVELOPES['tt']; folder=folder_for(f'charge_{ramp_ns}')
        points=f'0 0 100n 0 {100+ramp_ns:.12g}n 3.3 1100n 3.3 {1100+ramp_ns:.12g}n 0 2000n 0'
        (folder/'testbench.spice').write_text(f'''Analog PWM port charge\n{base(c)}
VPWM pwm 0 PWL({points})
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
tran .1n 2u 0 .1n
wrdata waveform.dat i(VPWM) v(pwm) v(gate) v(pwm_b) i(VDD)
quit
.endc
.end
''')
        run(['ngspice','-b','testbench.spice'],folder,'ngspice.log')
        a=np.loadtxt(folder/'waveform.dat',skiprows=1);t=a[:,0];i=-a[:,1]
        qr=integral(t,i,99e-9,1000e-9);qf=integral(t,i,1099e-9,1950e-9)
        short_r=integral(t,i,99e-9,300e-9);short_f=integral(t,i,1099e-9,1300e-9)
        return dict(input_full_ramp_ns=ramp_ns,rise_signed_charge_c=qr,fall_signed_charge_c=qf,
                    rise_charge_equivalent_cap_f=qr/3.3,fall_charge_equivalent_cap_f=-qf/3.3,
                    maximum_source_current_uA=float(i.max()*1e6),minimum_source_current_uA=float(i.min()*1e6),
                    source_energy_rise_j=integral(t,i*a[:,2],99e-9,1000e-9),
                    source_energy_fall_j=integral(t,i*a[:,2],1099e-9,1950e-9),
                    rise_short_window_signed_charge_c=short_r,fall_short_window_signed_charge_c=short_f,
                    rise_long_minus_short_relative=(qr-short_r)/abs(qr),fall_long_minus_short_relative=(qf-short_f)/abs(qf),
                    after_edge_max_abs_input_current_a=float(max(abs(i[(t>950e-9)&(t<1000e-9)]).max(),abs(i[(t>1900e-9)&(t<1950e-9)]).max())))
    with ThreadPoolExecutor(max_workers=3) as pool: charges=list(pool.map(charge_probe,[.25,1,10]))
    binary=work/'pwm.vvp'
    run(['iverilog','-g2012','-s','tb_pixel_pwm','-o',binary,frozen/'rtl/pixel_pwm.v',
         frozen/'sim/rtl/tb_pixel_pwm.v'],work,'rtl-compile.log')
    events={}
    for duty in [0,1,64,255,256]:
        out=work/f'events-{duty}.csv'
        log=run(['vvp',binary,f'+OUT={out}',f'+DUTY={duty}','+ENABLE=1','+TRACE_ONLY=1'],work,f'rtl-{duty}.log')
        if 'TRACE first_frame_ns=2500 measure_start_ns=514500 measure_end_ns=1538500' not in log:
            raise RuntimeError('RTL measurement window changed')
        with out.open() as f: events[duty]=[(float(r['time_ns'])*1e-9,int(r['pwm'])) for r in csv.DictReader(f)]
    # Retain the actual nominal digital output net RC; ground the quiet coupling
    # endpoint rather than pretending the neighboring input waveform was simulated.
    spef=(frozen/'evidence/physical/digital/spef/nom/pixel_pwm.nom.spef').read_text()
    if '*R_UNIT 1 OHM' not in spef or '*C_UNIT 1 PF' not in spef:
        raise RuntimeError('SPEF units changed')
    net=spef[spef.index('*D_NET *14 '):];net=net[:net.index('*END')]
    if not all(v in net for v in ['0.000315849','0.000503421','12.375']):
        raise RuntimeError('Digital output route RC changed; update parser mapping')
    def transient(case):
        c=ENVELOPES[case['envelope']];folder=folder_for(case['name'])
        ramp=10e-9 if case['driver']=='ideal' else 1e-9
        pwl=[(0,0)];previous=0
        for stamp,value in events[case['duty']]:
            if value!=previous:pwl.extend([(stamp,previous*c['logic_v']),(stamp+ramp,value*c['logic_v'])])
            previous=value
        pwl.append((STOP,previous*c['logic_v']))
        points='\n'.join(f'+ {t:.15g} {v:.15g}' for t,v in pwl)
        if case['driver']=='ideal': driver=f'VPWM pwm 0 PWL(\n{points}\n+)'
        else:
            route_target='macro_pwm' if case['driver']=='buffer_joint' else 'pwm'
            driver=f'''VIN input 0 PWL(
{points}
+)
XBUF input driver vbuffer vbuffer 0 0 {CELL}
CDIGNEAR driver 0 .315849f
RDIGITAL driver {route_target} 12.375
CDIGFAR {route_target} 0 .819270f'''
            if case['driver']=='buffer_joint':
                driver+=f'\n.include "{work/"joint-link.spice"}"\nXLINK pwm macro_pwm vlogic 0 pwm_link_rc'
        (folder/'testbench.spice').write_text(f'''RTL to actual output buffer to actual analog RC\n{base(c,case['led'])}
{driver}
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
tran 10n {STOP:.15g} 0 {case['maxstep_ns']}n
wrdata waveform.dat i(VDD) i(VLOGIC) i(VBUFFER) v(pwm) v(led_k) v(gate) v(bias) v(pwm_b)
quit
.endc
.end
''')
        run(['ngspice','-b','testbench.spice'],folder,'ngspice.log')
        a=np.loadtxt(folder/'waveform.dat',skiprows=1)
        if a.shape[1]!=9 or not np.isfinite(a).all():raise RuntimeError(str(folder))
        t=a[:,0];led=-a[:,1];analog=-a[:,2];buf=-a[:,3]
        current=integral(t,led)/(RIGHT-LEFT)
        transition=edges(t,a[:,4],c['logic_v'])
        samples=clipped(t,a[:,4],LEFT,RIGHT)[1]
        domain=(measured_helper.domain_integrals(t,c['led_v']-a[:,5],curve_v,curve_i) if case['led']!='synthetic' else None)
        return case|dict(**c,input_full_ramp_ns=ramp*1e9,average_led_current_uA=current*1e6,
                         average_led_rail_power_uW=current*c['led_v']*1e6,
                         average_analog_logic_power_uW=integral(t,analog)/(RIGHT-LEFT)*c['logic_v']*1e6,
                         average_buffer_power_uW=integral(t,buf)/(RIGHT-LEFT)*c['logic_v']*1e6,
                         buffer_supply_charge_c=integral(t,buf),pwm_min_v=float(samples.min()),pwm_max_v=float(samples.max()),
                         LED_voltage_min_v=float(clipped(t,c['led_v']-a[:,5],LEFT,RIGHT)[1].min()),
                         LED_voltage_max_v=float(clipped(t,c['led_v']-a[:,5],LEFT,RIGHT)[1].max()),
                         measured_LED_outside_domain_time_fraction=(domain['outside_measured_domain_time_fraction'] if domain else None),
                         measured_LED_outside_domain_signed_charge_fraction=(domain['outside_measured_domain_signed_conduction_charge_fraction'] if domain else None),
                         **transition)
    cases=[dict(name=f'{e}_{d}_d{duty}',envelope=e,driver=d,duty=duty,led='synthetic',maxstep_ns=10)
           for e in ENVELOPES for d in ['ideal','buffer'] for duty in [0,1,64,255,256]]
    cases += [dict(name=f'measured_{d}_d{duty}',envelope='tt',driver=d,duty=duty,led='measured_static_2pF_assumed',maxstep_ns=10)
              for d in ['ideal','buffer'] for duty in [1,64,256]]
    cases += [dict(name='tt_buffer_d1_fine',envelope='tt',driver='buffer',duty=1,led='synthetic',maxstep_ns=1),
              dict(name='measured_buffer_d1_fine',envelope='tt',driver='buffer',duty=1,led='measured_static_2pF_assumed',maxstep_ns=1)]
    if args.joint_link:
        cases += [dict(name=f'{e}_joint_d{duty}',envelope=e,driver='buffer_joint',duty=duty,led='synthetic',maxstep_ns=10)
                  for e in ENVELOPES for duty in [0,1,64,255,256]]
        cases += [dict(name='tt_joint_d1_fine',envelope='tt',driver='buffer_joint',duty=1,led='synthetic',maxstep_ns=1)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(transient,cases))
    checks=[]
    for r in results:
        full=next(x for x in results if x['envelope']==r['envelope'] and x['driver']==r['driver'] and x['led']==r['led'] and x['duty']==256)
        r['area_error_pct']=(r['average_led_current_uA']/(full['average_led_current_uA']*r['duty']/256)-1)*100 if r['duty'] else None
        if r['duty']==256:
            checks.append(dict(name=r['name']+'_absolute_5pct',value_uA=r['average_led_current_uA'],passed=abs(r['average_led_current_uA']/100-1)<=.05))
        if r['duty']==1:
            checks.append(dict(name=r['name']+'_lowest_area_2pct',value_pct=r['area_error_pct'],passed=abs(r['area_error_pct'])<=2))
        if r['duty']==0:
            checks.append(dict(name=r['name']+'_off_model_1nA',value_uA=r['average_led_current_uA'],passed=abs(r['average_led_current_uA'])<.001))
        if r['driver']!='ideal' and r['duty'] not in [0,256]:
            checks.append(dict(name=r['name']+'_actual_slew_3ns',threshold_definition='30-70 percent from actual TT Liberty',
                               rise_ns=r['rise_30_70_ns'],fall_ns=r['fall_70_30_ns'],
                               passed=r['rise_30_70_ns']<=3 and r['fall_70_30_ns']<=3))
            checks.append(dict(name=r['name']+'_minimum_pulse_950ns',high_ns=r['high_pulse_min_ns'],low_ns=r['low_pulse_min_ns'],
                               passed=(r['high_pulse_min_ns'] is None or r['high_pulse_min_ns']>=950) and
                               (r['low_pulse_min_ns'] is None or r['low_pulse_min_ns']>=950)))
    for fine in [r for r in results if r['name'].endswith('_fine')]:
        coarse=next(r for r in results if r['envelope']==fine['envelope'] and r['driver']==fine['driver'] and r['led']==fine['led'] and r['duty']==1 and not r['name'].endswith('_fine'))
        change=abs(fine['average_led_current_uA']-coarse['average_led_current_uA'])/abs(coarse['average_led_current_uA'])
        checks.append(dict(name=fine['name']+'_step_refinement_0p2pct',relative_change=change,passed=change<=.002))
    destination=ROOT/'evidence/interface';destination.mkdir(exist_ok=True)
    for filename,rows in [('dc.csv',dc_results),('ac.csv',ac_results),('input-charge.csv',charges),('transients.csv',results)]:
        with (destination/filename).open('w') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=dict(schema_version=1,status='actual final buffer schematic transistors + actual analog extracted RC; isolated output-stage electrical validation',
                 passed=all(c['passed'] for c in checks),run_directory=str(work.relative_to(ROOT)),ngspice=version,
                 scope=dict(full_digital_transistor_simulation=False,output_standard_cell_PEX=False,
                            analog_cell_PEX=True,joint_link_PEX=bool(args.joint_link),silicon_or_optical_measurement=False,
                            dynamic_LED_qualification=False,preceding_digital_CQ_and_logic_delay_included=False),
                 source_hashes=hashes,pdk_inputs_sha256=checked,actual_analog_rc_sha256=hashes['evidence/layout/pixel_driver_rc.spice'],
                 joint_link_sha256=joint_hash,output_buffer=dict(instance='output12',cell=CELL,transistors=6,
                 ports=['I','Z','VDD','VNW','VPW','VSS'],well_ties='VNW=VDD; VPW=VSS'),
                 conditions=dict(envelopes=ENVELOPES,frame_period_s=256e-6,measurement_window_s=[LEFT,RIGHT],
                                 measured_frames=4,reference_uA=100,buffer_input_full_ramp_ns=1,ideal_pwm_full_ramp_ns=10,
                                 input_ramp_interpretation='declared stimulus at final buffer input; actual preceding FF waveform is not transistor-simulated',
                                 actual_liberty_slew_thresholds_pct=[30,70],transition_limit_ns=3,
                                 charge_integral_windows_s=dict(rise=[99e-9,1000e-9],fall=[1099e-9,1950e-9],
                                                               short_rise=[99e-9,300e-9],short_fall=[1099e-9,1300e-9]),
                                 digital_output_route=dict(source='actual nominal SPEF pwm output12:Z net',R_ohm=12.375,
                                                          near_C_fF=.315849,far_C_fF=.819270,
                                                          coupling_C_fF=.503421,coupling_endpoint='quiet AC-ground assumption; neighbor transient not simulated'),
                                 static_LED_temperature='unreported, never scaled; measured-static + 2pF capacitor is a hypothesis'),
                 synthetic_DC_calibration=dict(target_uA=100,target_v=2.8,actual_v=calibrated_v,passed=abs(calibrated_v-2.8)<=1e-5),
                 original_STA_load_fF=72.91,AC_interpretation='Cparallel=Im(Y)/(2*pi*f) about each DC PWM bias, includes responding coupled nodes; not a physical constant or Liberty pin extraction',
                 charge_interpretation='signed source-port integral over complete transition and settling; Q/DeltaV is operating/slew-dependent charge equivalent, not a bias-independent C',
                 buffer_SPICE_limitations='upstream schematic subckt omits explicit source/drain AD/AS/PD/PS; intrinsic model C remains but it is not a junction/metal PEX view. No missing parasitic was silently fitted to match Liberty.',
                 dc_runs=len(dc_results),AC_runs=5,input_charge_runs=len(charges),transient_runs=len(results),
                 dc_results=dc_results,ac_results=ac_results,input_charge_results=charges,transient_results=results,checks=checks,
                 sources=[dict(url='https://gf180mcu-pdk.readthedocs.io/en/latest/digital/standard_cells/gf180mcu_fd_sc_mcu7t5v0/cells/buf/gf180mcu_fd_sc_mcu7t5v0__buf_2.html',
                               use='official function and cell identity; no unconditioned web delay reused',accessed='2026-10-04'),
                          dict(url='https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_sc_mcu7t5v0',
                               use='public standard-cell source locator; implemented compiled library identified by locked file hash')])
    summary['raw_artifacts_sha256']={str(p.relative_to(work)):sha(p) for p in sorted(work.rglob('*'))
                                     if p.is_file() and not p.is_symlink() and 'inputs' not in p.relative_to(work).parts
                                     and p.name not in ['summary.json'] and p.suffix in ['.spice','.dat','.csv','.log']}
    (work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (destination/'summary.json').write_bytes((work/'summary.json').read_bytes())
    shutil.copyfile(work/'ngspice-version.log',destination/'ngspice-version.log')
    manifest={str(p.relative_to(ROOT)):sha(p) for p in sorted(destination.glob('*')) if p.is_file() and p.name!='manifest.json'}
    (destination/'manifest.json').write_text(json.dumps(dict(files_sha256=manifest),indent=2)+'\n')
    print(json.dumps(dict(passed=summary['passed'],run_directory=summary['run_directory'],transient_runs=len(results),
                         charge_fF=[dict(ramp_ns=x['input_full_ramp_ns'],rise=x['rise_charge_equivalent_cap_f']*1e15,
                                        fall=x['fall_charge_equivalent_cap_f']*1e15) for x in charges],
                         failed=[x for x in checks if not x['passed']]),indent=2))
    if not summary['passed']:raise RuntimeError('Interface guard failed; retain evidence and inspect')


if __name__=='__main__':main()
