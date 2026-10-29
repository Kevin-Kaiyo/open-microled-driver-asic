#!/usr/bin/env python3
"""All measured voltage-ratio crossings, without treating them as return-ratio proof."""
from pathlib import Path
import json,math
import numpy as np
from audit_recheck import ROOT,EV,sha

base=ROOT/'build/vcsel-robustness-20261029'
names=[f'ac-final-{c}-{b}-r10' for c in ['TT','SS','FF'] for b in ['L','D']]
names+=['ac-TT-D-rz0.0-bleed0.0-c1e-10','ac-final-TT-L-r8','ac-final-TT-D-r8']
rows=[]
for name in names:
    work=base/name;r=json.loads((work/'result.json').read_text());assert sha(work/'ac.dat')==r['data_sha256']
    a=np.loadtxt(work/'ac.dat',skiprows=1);freq=a[:,0]
    z=-(a[:,1]+1j*a[:,2])/(a[:,3]+1j*a[:,4])
    db=20*np.log10(abs(z));phase=np.unwrap(np.angle(z))*180/math.pi
    cross=[]
    for k in range(len(freq)-1):
        if db[k]*db[k+1]<=0 and db[k]!=db[k+1]:
            w=-db[k]/(db[k+1]-db[k]);f=freq[k]*(freq[k+1]/freq[k])**w
            ph=phase[k]+w*(phase[k+1]-phase[k]);direction='down' if db[k]>db[k+1] else 'up'
            cross.append(dict(frequency_Hz=float(f),direction=direction,voltage_ratio_phase_unwrapped_deg=float(ph),
                voltage_ratio_phase_principal_deg=float((ph+180)%360-180),
                old_180_plus_phase_indicator_deg=float(180+ph) if direction=='down' else None))
    rows.append(dict(case=name,data_sha256=r['data_sha256'],frequency_range_Hz=[float(freq[0]),float(freq[-1])],
        all_zero_dB_crossings=cross,high_frequency_endpoint=dict(frequency_Hz=float(freq[-1]),magnitude_dB=float(db[-1]),phase_principal_deg=float(np.angle(z[-1])*180/math.pi)),
        classification='Observed voltage-injection ratio only. Not established as the true return ratio; no Nyquist count, closed-loop stability verdict or qualified phase margin follows.'))
R=85000*10000/(85000+10000);C=2e-12
f=np.geomspace(1,1e9,1200);v_gate=1/(1+2j*np.pi*f*R*C);v_fb=v_gate-1
measured=-v_fb/v_gate;expected=2j*np.pi*f*R*C
assert np.max(abs(measured-expected))<1e-10
counterexample={'network':'No active feedback. Rth from feedback side to AC ground, Cin from gate side to AC ground, series source Vgate-Vfb=1.',
    'KCL':'Vfb/Rth + s Cin Vgate = 0', 'ratio':'-Vfb/Vgate = s Rth Cin',
    'Rth_ohm':R,'illustrative_Cin_F':C,'Cin_is_measured_or_extracted':False,
    'false_unity_frequency_Hz':1/(2*math.pi*R*C),'magnitude_at_1GHz_dB':float(20*np.log10(abs(expected[-1]))),
    'explanation':'A rising unity crossing can exist with no active return loop; this proves the observed ratio alone is not a generally valid stability measure. It does not uniquely decompose the actual transistor network.'}
out={'script_sha256':sha(__file__),'rows':rows,'passive_loading_counterexample':counterexample,
     'findings':['The previous helper only enumerated descending0dB crossings. All final curves also have ascending crossings near8.8-10.5MHz.','At1GHz the ratio is about40dB at approximately+87degrees, consistent with a capacitive loading term. Full frequency data remain retained.','The first descending-crossing180+phase values are arithmetic indicators under an unverified impedance/unilateral approximation, not independently established phase margins.','This audit does not claim high-frequency oscillation; actual return ratio and closed-loop poles are not determined by these two saved voltages.'],
     'next_validation':['Use a validated two-injection/two-port return-ratio method that retains loading and reverse transmission, or appropriate device-based gain nulling.','Check applicability to all relevant nested loops and DC/load states; retain all crossings and complex response.','Continue separate large-signal startup, line/load disturbance and long-pattern transient tests; finite transients alone do not prove unconditional stability.'],
     'primary_sources':[{'title':'Middlebrook1975 Measurement of loop gain in feedback systems','url':'https://www.venableinstruments.com/hubfs/Middlebrook_Measurement%20of%20loop%20gain%20in%20feedback%20systems.pdf','locator':'pp489,498; impedance requirement and arbitrary-impedance extension'},
       {'title':'Tian,Visvanathan,Hantgan,Kundert2001 Striving for Small-Signal Stability','url':'https://kenkundert.com/docs/cd2001-01.pdf','doi':'10.1109/101.900125','locator':'pp31-32 overview; loop-based two-port and device-based methods; forward/reverse transmission'}]}
(EV/'audit-ac-all-crossings.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'cases':len(rows),'r10_all_have_upward_crossings':all(any(c['direction']=='up' for c in r['all_zero_dB_crossings']) for r in rows[:6]),'counterexample_unity_MHz':counterexample['false_unity_frequency_Hz']/1e6},indent=2))
