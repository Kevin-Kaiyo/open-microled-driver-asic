"""Independently recompute current, power, charge and edge metrics from raw data.

No functions from the simulation runner are imported. Published CSVs, circuit
mapping, actual model hashes and measurement windows are checked independently.
"""
from pathlib import Path
import csv
import hashlib
import json
import re

import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def integrate(t,y,left,right):
    # Independent cumulative primitive with exact partial linear segment panels.
    panels=np.diff(t)*(y[:-1]+y[1:])/2
    prefix=np.r_[0,np.cumsum(panels)]
    def primitive(x):
        k=min(max(int(np.searchsorted(t,x,side='right'))-1,0),len(t)-2)
        dx=x-t[k]
        return prefix[k]+y[k]*dx+(y[k+1]-y[k])*dx*dx/(2*(t[k+1]-t[k]))
    if t[0]>left or t[-1]<right or np.any(np.diff(t)<=0):raise RuntimeError('Incomplete waveform')
    return float(primitive(right)-primitive(left))


def crossing_times(t,v,level,rising):
    steps=np.diff(np.sign(v-level));indices=np.flatnonzero(steps>0 if rising else steps<0)
    return np.array([float(t[k]+(level-v[k])/(v[k+1]-v[k])*(t[k+1]-t[k])) for k in indices])


def main():
    summary=json.loads((ROOT/'evidence/interface/summary.json').read_text())
    work=ROOT/summary['run_directory']
    left,right=summary['conditions']['measurement_window_s'];duration=right-left
    assertions=[]
    def check(name,passed,**facts):
        assertions.append(dict(name=name,passed=bool(passed),**facts))
    mapping=json.loads((ROOT/'evidence/interface/input-mapping.json').read_text()) if (ROOT/'evidence/interface/input-mapping.json').exists() else None
    for path,h in summary['source_hashes'].items():
        if mapping and path in mapping['paths']:
            record=mapping['paths'][path]
            check('source_'+path+'_as_run_mapping',mapping['passed'] and mapping['electrical_graph_equal'] and
                  record['as_run_sha256']==h and sha(ROOT/path)==record['current_sha256'] and
                  sha(ROOT/record['snapshot_path'])==record['as_run_sha256'])
        else:check('source_'+path,sha(ROOT/path)==h)
    for path,h in summary['pdk_inputs_sha256'].items():check('PDK_'+path,sha(ROOT/'build/layout/pdk/gf180mcuD'/path)==h)
    for path,h in summary['raw_artifacts_sha256'].items():check('raw_'+path,sha(work/path)==h)
    subset=(ROOT/'scripts/interface/buf_2.spice').read_text()
    check('actual_buffer_six_MOS_and_pin_order',len(re.findall(r'(?m)^X_i_',subset))==6 and
          '.SUBCKT gf180mcu_fd_sc_mcu7t5v0__buf_2 I Z VDD VNW VPW VSS' in subset)
    check('actual_analog_RC_identity',summary['actual_analog_rc_sha256']==sha(ROOT/'evidence/layout/pixel_driver_rc.spice'))
    if summary['joint_link_sha256']:
        check('actual_joint_link_identity',summary['joint_link_sha256']==
              (mapping['paths']['evidence/integration/pwm_link_rc.spice']['as_run_sha256'] if mapping else sha(ROOT/'evidence/integration/pwm_link_rc.spice')))
    error_max=dict(current_uA=0.,power_uW=0.,charge_fF=0.,slew_ns=0.,pulse_width_ns=0.)
    for result in summary['transient_results']:
        data=np.loadtxt(work/result['name']/'waveform.dat',skiprows=1);t=data[:,0]
        current=-integrate(t,data[:,1],left,right)/duration*1e6
        difference=abs(current-result['average_led_current_uA']);error_max['current_uA']=max(error_max['current_uA'],difference)
        check(result['name']+'_independent_LED_rail_integral',difference<1e-7,current_uA=current)
        for col,power,key in [(2,result['average_analog_logic_power_uW'],'analog_logic'),(3,result['average_buffer_power_uW'],'buffer')]:
            p=-integrate(t,data[:,col],left,right)/duration*result['logic_v']*1e6
            delta=abs(power-p);error_max['power_uW']=max(error_max['power_uW'],delta)
            check(result['name']+'_independent_'+key+'_power',delta<1e-7)
        if result['duty']:
            full=next(r for r in summary['transient_results'] if r['envelope']==result['envelope'] and
                      r['driver']==result['driver'] and r['led']==result['led'] and r['duty']==256)
            area=(current/(full['average_led_current_uA']*result['duty']/256)-1)*100
            check(result['name']+'_independent_area',abs(area-result['area_error_pct'])<1e-5)
        else:check(result['name']+'_independent_off_guard',abs(current)<.001)
        if result['duty']==1:check(result['name']+'_independent_area_2pct',abs(area)<=2)
        if result['duty']==256:check(result['name']+'_independent_full_on_5pct',95<=current<=105)
        if result['driver']!='ideal' and result['duty'] not in (0,256):
            output=data[:,4];supply=result['logic_v']
            for name,rising in [('rise',True),('fall',False)]:
                aa=crossing_times(t,output,(.3 if rising else .7)*supply,rising)
                bb=crossing_times(t,output,(.7 if rising else .3)*supply,rising)
                found=[]
                for a in aa[(aa>left)&(aa<right)]:
                    later=bb[bb>a]
                    if len(later):found.append((later[0]-a)*1e9)
                slew=max(found)
                recorded=result['rise_30_70_ns' if rising else 'fall_70_30_ns']
                delta=abs(slew-recorded);error_max['slew_ns']=max(error_max['slew_ns'],delta)
                check(result['name']+'_independent_'+name+'_30_70',delta<1e-4 and slew<=3)
            up=crossing_times(t,output,.5*supply,True);down=crossing_times(t,output,.5*supply,False)
            for name,starts,ends in [('high',up,down),('low',down,up)]:
                widths=[]
                for x in starts[(starts>left)&(starts<right)]:
                    later=ends[(ends>x)&(ends<right)]
                    if len(later):widths.append((later[0]-x)*1e9)
                if widths:
                    minimum=min(widths);delta=abs(minimum-result[name+'_pulse_min_ns'])
                    error_max['pulse_width_ns']=max(error_max['pulse_width_ns'],delta)
                    check(result['name']+'_independent_'+name+'_pulse',delta<1e-4 and minimum>=950)
    for row in summary['input_charge_results']:
        data=np.loadtxt(work/f'charge_{row["input_full_ramp_ns"]}'/'waveform.dat',skiprows=1);t=data[:,0]
        for edge in ['rise','fall']:
            a,b=summary['conditions']['charge_integral_windows_s'][edge]
            q=-integrate(t,data[:,1],a,b);difference=abs(q-row[edge+'_signed_charge_c'])*1e15
            error_max['charge_fF']=max(error_max['charge_fF'],difference)
            check(f'charge_{row["input_full_ramp_ns"]}_{edge}_independent',difference<1e-6,
                  recomputed_signed_charge_fC=q*1e15)
            expected=(q/3.3 if edge=='rise' else -q/3.3)
            check(f'charge_{row["input_full_ramp_ns"]}_{edge}_unit_conversion',abs(expected-row[edge+'_charge_equivalent_cap_f'])<1e-22)
    for row in summary['ac_results']:
        converted=row['susceptance_s']/(2*np.pi*row['frequency_hz'])
        check(f'AC_{row["pwm_dc_v"]}_{row["frequency_hz"]}_unit',abs(converted-row['effective_parallel_capacitance_f'])<1e-25)
    for filename,rows in [('dc.csv',summary['dc_results']),('ac.csv',summary['ac_results']),
                          ('input-charge.csv',summary['input_charge_results']),('transients.csv',summary['transient_results'])]:
        with (ROOT/'evidence/interface'/filename).open() as f:published=list(csv.DictReader(f))
        check(filename+'_record_count',len(published)==len(rows))
        for i,(actual,expected) in enumerate(zip(published,rows)):
            for k,value in expected.items():
                if isinstance(value,(int,float)):
                    check(f'{filename}_{i}_{k}',math_isclose(float(actual[k]),float(value)))
                elif value is None:check(f'{filename}_{i}_{k}',actual[k]=='')
                else:check(f'{filename}_{i}_{k}',actual[k]==str(value))
    # Save a compact actual first nominal pulse with all recorded electrical data.
    name='tt_joint_d1' if summary['joint_link_sha256'] else 'tt_buffer_d1'
    data=np.loadtxt(work/name/'waveform.dat',skiprows=1)
    selected=data[(data[:,0]>=left-20e-9)&(data[:,0]<=left+1.5e-6)]
    np.savetxt(ROOT/'evidence/interface/nominal-pulse.csv',selected,delimiter=',',fmt='%.15e',comments='',
               header='time_s,LED_rail_supply_current_A,analog_logic_supply_current_A,buffer_supply_current_A,pwm_V,led_k_V,gate_V,bias_V,pwm_b_V')
    result=dict(passed=all(r['passed'] for r in assertions),method='independent cumulative linear-segment primitive; no simulation runner functions imported',
                checks=len(assertions),maximum_absolute_recompute_difference=error_max,
                summary_sha256=sha(ROOT/'evidence/interface/summary.json'),
                verifier_sha256=sha(Path(__file__)),pulse_sample=dict(case=name,window_s=[left-20e-9,left+1.5e-6],
                samples=len(selected),file_sha256=sha(ROOT/'evidence/interface/nominal-pulse.csv')),
                failures=[r for r in assertions if not r['passed']])
    (ROOT/'evidence/interface/validation.json').write_text(json.dumps(result,indent=2)+'\n')
    manifest={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'evidence/interface').glob('*'))
              if p.is_file() and p.name!='manifest.json'}
    (ROOT/'evidence/interface/manifest.json').write_text(json.dumps(dict(files_sha256=manifest),indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if not result['passed']:raise RuntimeError('Independent interface validation failed')


def math_isclose(a,b):return abs(a-b)<=max(abs(b)*1e-12,1e-22)


if __name__=='__main__':main()
