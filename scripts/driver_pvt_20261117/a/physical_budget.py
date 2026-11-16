#!/usr/bin/env python3
"""Local I-V interpolation and the passive DC equations, without new fit data."""
import re
import numpy as np
import run as a
p=a.FROZEN/'inputs/led.spice';s=p.read_text();body=s.split('I = pwl(v(anode,cathode),',1)[1].split(')',1)[0].replace('+','');nums=[float(v) for v in re.findall(r'[-]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',body)];v=np.array(nums[::2]);i=np.array(nums[1::2]);assert len(v)==101
out=[]
for current in [25e-6,100e-6]:
 v0=float(np.interp(current,i,v));lo,hi=np.interp([current*.99,current*1.01],i,v);j=np.searchsorted(i,current);rd=(v[j]-v[j-1])/(i[j]-i[j-1]);vfshift=v0*.001;estimate=vfshift/rd/current*100
 out.append(dict(target_uA=current*1e6,voltage_V=v0,local_dV_dI_ohm=float(rd),minus1percent_voltage_mV=float((lo-v0)*1e3),plus1percent_voltage_mV=float((hi-v0)*1e3),reference_0p1percent_error_linearized_current_error_percent=float(estimate),interpretation='The ±1% interval is mathematical interpolation of the same LED table, not evidence that the measured I-V or current can be known to ±1%.'))
cal=a.read(a.EV/'trackwide4gm5-calibration.json')
a.emit(a.EV/'physical-budget.json',dict(source_LED_sha256=a.sha(p),equations=['HSENSE=a*VH+bH*VREF with a=0.25 and bH=(1/RH_REF)/1uS','HSET=a*LEDREF; ideal servo therefore LEDREF-VH=(bH/a)*VREF','VLED_AK=LEDREF-Vrail-I*(R_ISO+R_OUT+RPKG) approximately, with state-dependent R_OUT and nonlinear MOS R_ISO','Finite OTA input error is divided by a; current accuracy also depends on reference and matching of passive ratios.'],targets=out,load_thermal_scope='Table independent of .temp; no VCSEL/MicroLED junction self-heating in these cases.',selected_calibration=dict(RH_ohm=cal['RH_ohm'],RL_ohm=cal['RL_ohm']),geometry_change=dict(output_MOS_W_multiplier=4,OTA_input_pair_W_multiplier=5,output_channel_area_before_um2=(10+15.72)*.28,output_channel_area_after_um2=(40+62.88)*.28,OTA_input_pair_channel_area_before_um2=4*20*4,OTA_input_pair_channel_area_after_um2=4*100*4,scope='Sum W*L only, not die area, device active area, capacitance extraction or placement footprint.'),net_Gbps=1.6,line_Gbps=1.6*37/32,line_UI_ps=1e3/(1.6*37/32),transient_gate='All waveforms preserve optical200ps and RX1GHz, 7.5uAeq amplitude and0.37lineUI timing; off<=0.1uA after20ns and recovery<=1us with>=1us verified observation.'))
print(out)
