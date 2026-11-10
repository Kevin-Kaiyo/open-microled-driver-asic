#!/usr/bin/env python3
"""Receiver-only ideal-current controls for A/B improvement, not device limits.

No transistor, charging feasibility, driver energy, thermal, noise or BER claim
is made. The current stays at 25/100 uA without pre-emphasis. A real waveform
with overshoot/pre-emphasis can differ, so this is not an absolute upper bound.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import inspect
import json
import math
import re
import sys

import numpy as np

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT/'scripts/blue_emitter_speed_20261110'
sys.path.insert(0,str(STAGE))

def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

analysis=module(STAGE/'analyze.py','ideal_bounds_rate_analysis')
dynamic=module(ROOT/'scripts/microled_dynamic_v1/analyze.py','ideal_bounds_dynamic')
rx=module(analysis.RXPATH,'ideal_bounds_receiver')
ETA=4096/4736
TAU_OPT=200e-12
TAU_RX=1/(2*math.pi*1e9)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def step_response(bits,ui,grid):
    """Closed-form state response to instantaneous prescribed input steps.

    Each bit has constant u. The optical and receiver states are continuous at
    the edge, initialized to the first bit's DC level. Dense output samples are
    used only for the shared receiver's interpolation/crossing search.
    """
    levels=25e-6+75e-6*np.asarray(bits)
    offsets=np.arange(grid)*ui/grid
    ea=np.exp(-offsets/TAU_OPT);eb=np.exp(-offsets/TAU_RX)
    coupling=TAU_OPT/(TAU_OPT-TAU_RX)*(ea-eb)
    ea1=np.exp(-ui/TAU_OPT);eb1=np.exp(-ui/TAU_RX)
    c1=TAU_OPT/(TAU_OPT-TAU_RX)*(ea1-eb1)
    optical=received=float(levels[0]);out=np.empty(len(bits)*grid+1)
    for k,u in enumerate(levels):
        out[k*grid:(k+1)*grid]=u+eb*(received-u)+coupling*(optical-u)
        optical,received=(u+ea1*(optical-u),u+eb1*(received-u)+c1*(optical-u))
    out[-1]=received
    time=np.arange(len(out))*ui/grid
    return time,out


def ramp_response(bits,ui,grid,edge=20e-12):
    """Prescribed finite current slope; exact PWL two-pole state integration."""
    assert 0<edge<ui
    levels=25e-6+75e-6*np.asarray(bits)
    boundaries=np.arange(len(bits)+1)*ui
    time=np.unique(np.r_[np.arange(len(bits)*grid+1)*ui/grid,
                         boundaries[:-1]+edge,boundaries])
    index=np.minimum(np.searchsorted(boundaries,time,side='right')-1,len(bits)-1)
    prev=levels[np.maximum(index-1,0)]
    current=prev+np.clip((time-boundaries[index])/edge,0,1)*(levels[index]-prev)
    _,out=dynamic.cascade_pwl(time,current,TAU_OPT,TAU_RX)
    return time,out


def control(bits,stimulus,rate,edge,grid):
    ui=ETA/(rate*1e9)
    t,y=(step_response(bits,ui,grid) if edge==0 else ramp_response(bits,ui,grid,edge*1e-12))
    r=analysis.receive(t,y*1e6,stimulus,'A',rate,rx)
    return {'net_Gbps':rate,'line_Gbps':rate/ETA,'line_bit_UI_ps':ui*1e12,
            'current_edge_ps':edge,'samples_per_bit_UI':grid,'samples':len(t),
            'full_receiver':r,'scope':'Ideal prescribed conduction current; receiver screen only.'}


def charge_budget():
    p=ROOT/'build/blue-emitter-speed-review-20261110/microled/inputs/led.spice'
    s=p.read_text().split('I = pwl(v(anode,cathode),',1)[1].split(')',1)[0]
    nums=[float(x) for x in re.findall(r'(?<!\w)[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?',s,re.I)]
    points=np.array(nums).reshape(-1,2)
    v0,v1=np.interp([25e-6,100e-6],points[:,1],points[:,0]);dv=v1-v0
    local=[]
    for current in [25e-6,100e-6]:
        k=int(np.searchsorted(points[:,1],current))
        resistance=(points[k,0]-points[k-1,0])/(points[k,1]-points[k-1,1])
        local.append({'current_uA':current*1e6,'local_differential_resistance_ohm':float(resistance),
                      'C200fF_times_rd_ps':float(resistance*200e-15*1e12),
                      'scope':'Local linearization of frozen static I-V with 200 fF; excludes driver output admittance, package and large-signal time variation.'})
    rows=[]
    for cap in [200,800]:
        charge=cap*1e-15*dv
        for rate in [.4,.8,1.2,1.6,2.,2.4,3.2]:
            budget=.5*ETA/(rate*1e9)
            rows.append({'capacitance_fF':cap,'net_Gbps':rate,'half_line_bit_UI_ps':budget*1e12,
                         'charge_fC':charge*1e15,'mean_net_displacement_current_uA':charge/budget*1e6})
    return {'source':str(p.relative_to(ROOT)),'source_sha256':sha(p),'current_levels_uA':[25,100],
            'LED_forward_voltage_levels_V':[float(v0),float(v1)],'delta_LED_voltage_V':float(dv),'local_RC_estimates':local,'rows':rows,
            'interpretation':'C*dV/dt is displacement current additional to LED conduction. The half-UI transition is an illustrative budget, not a sufficient eye opening criterion or measured transistor peak current.'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--grid',type=int,default=128);args=ap.parse_args()
    assert args.grid>=64
    p=ROOT/'build/blue-emitter-speed-review-20261110/microled/stimulus.json'
    stimulus=json.loads(p.read_text());bits=stimulus['bits']
    assert len(bits)==4736 and stimulus['eta']==ETA
    rows=[]
    for edge in [0,20]:
        for rate in [.4,.8,1.2,1.6,2.,2.4,3.2]:
            row=control(bits,stimulus,rate,edge,args.grid);rows.append(row)
            r=row['full_receiver'];print(edge,rate,r['errors'],r['worst_signed_margin_uAeq'],r['one_sided_margin_bit_UI'],r['research_margin_pass'],flush=True)
    fine=[]
    for edge in [0,20]:
        for rate in [2.,2.4,3.2]:
            r=control(bits,stimulus,rate,edge,args.grid*2)
            base=next(x for x in rows if x['current_edge_ps']==edge and x['net_Gbps']==rate)
            b,f=base['full_receiver'],r['full_receiver']
            checks={'same_errors':b['errors']==f['errors'],'same_training_errors':b['train_errors']==f['train_errors'],
                    'same_pass':b['research_margin_pass']==f['research_margin_pass'],
                    'amplitude_delta_below_0p02_uAeq':abs(b['worst_signed_margin_uAeq']-f['worst_signed_margin_uAeq'])<.02,
                    'timing_delta_below_0p1_ps':abs(b['one_sided_margin_ps']-f['one_sided_margin_ps'])<.1}
            fine.append({'base_grid':args.grid,'fine':r,'checks':checks,'passed':all(checks.values()),
                         'amplitude_delta_uAeq':f['worst_signed_margin_uAeq']-b['worst_signed_margin_uAeq'],
                         'timing_delta_ps':f['one_sided_margin_ps']-b['one_sided_margin_ps']})
    assert all(x['passed'] for x in fine)
    # Different phase resolution is an explicitly separate diagnostic, never
    # substituted for the frozen 1/64 UI contract or circuit ranking.
    source=inspect.getsource(analysis.receive)
    assert 'np.arange(513)/64' in source
    source=source.replace('def receive(', 'def receive_fine_phase(').replace('np.arange(513)/64','np.arange(4097)/512')
    namespace=dict(analysis.__dict__);exec(source,namespace)
    phase=[]
    for edge in [0,20]:
        ui=ETA/(2.4e9)
        t,y=step_response(bits,ui,args.grid*2) if edge==0 else ramp_response(bits,ui,args.grid*2,edge*1e-12)
        r=namespace['receive_fine_phase'](t,y*1e6,stimulus,'A',2.4,rx)
        phase.append({'net_Gbps':2.4,'current_edge_ps':edge,'delay_grid_bit_UI':1/512,'full_receiver':r})
    out={'schema':'ideal-current-receiver-envelope-v1','scope':'Mathematical diagnostic, not an absolute bandwidth bound, transistor result, energy result or BER qualification.',
         'contract':{'levels_uA':[25,100],'optical_tau_ps':200,'receiver_single_pole_GHz':1,'eta':ETA,'frame_bits':4736,'validation_bits':4096,
                     'amplitude_gate_uAeq':7.5,'one_sided_timing_gate_line_bit_UI':.37,'training_only_delay_selection':True,
                     'zero_edge_method':'Exact closed-form two-pole state update for each constant NRZ bit.',
                     'twenty_ps_method':'Exact-PWL existing cascade; prescribed 20 ps current ramp, no transistor driver.'},
         'rows':rows,'sampling_controls':fine,
         'phase_grid_diagnostic':{'scope':'Outside frozen receiver contract. Only changes training delay grid from 1/64 to 1/512 UI. Both 2.4G ideal signals pass with finer phase, confirming that the tiny pass/fail inversion at 2.4G is not a physical advantage of slower edges. This does not promote real circuit results.','rows':phase},
         'charge_budget':charge_budget(),
         'source_hashes':{str(q.relative_to(ROOT)):sha(q) for q in [Path(__file__).resolve(),Path(analysis.__file__).resolve(),Path(dynamic.__file__).resolve(),analysis.RXPATH,p]},
         'limits':['No CLED/driver charging model in prescribed-current controls. Charge budget is a separate necessary-current estimate.',
                   'No pre-emphasis or overshoot; a real waveform with edge boost may alter the receiver envelope.',
                   'No noise, clock recovery, supply/PVT variation, startup, energy or measured optical calibration.',
                   'Pass/fail brackets are sampled points; not a continuous maximum or topology selection.']}
    target=ROOT/'evidence/ab-improvement-20261111/ideal-bounds.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print('WROTE',target.relative_to(ROOT),flush=True)

if __name__=='__main__':main()
