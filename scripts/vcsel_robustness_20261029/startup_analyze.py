#!/usr/bin/env python3
"""Startup judged against independently solved DC current AND regulated-rail targets."""
import json
import numpy as np
from run import ROOT,BUILD,EV,sha,emit

def analyze(case,dc_case):
 w=BUILD/case;m=json.loads((w/'manifest.json').read_text());r=json.loads((w/'result.json').read_text())
 d=BUILD/dc_case;dr=json.loads((d/'result.json').read_text())
 assert r['simulation_ok'] and dr['simulation_ok']
 out=w/'startup-review.json'
 if out.exists():
  old=json.loads(out.read_text());assert old['waveform_sha256']==r['waveform']['sha256'] and old['dc_result_sha256']==sha(d/'result.json');return old
 a=np.loadtxt(ROOT/r['waveform']['path'],skiprows=1);t=a[:,0];ix={e:i+1 for i,e in enumerate(m['expressions'])};end=t[-1]
 channels={'current_mA':(a[:,1]*1000,dr['current_mA'],.05),'laser_rail_V':(a[:,ix['v(vl)']],dr['nodes_final_V']['vl'],.01),'buffer_rail_V':(a[:,ix['v(xdrv.dr)']],dr['nodes_final_V']['xdrv.dr'],.01)}
 metrics={}
 for name,(v,target,tol) in channels.items():
  good=np.abs(v-target)<=tol*abs(target);bad=np.flatnonzero(~good)
  settled=bool(good[-1]);settle=float(t[bad[-1]+1]*1e6) if settled and len(bad) else 0. if settled else None
  metrics[name]=dict(dc_target=float(target),relative_band=tol,final=float(v[-1]),min=float(v.min()),max=float(v.max()),final_relative_error=float((v[-1]-target)/target),last_20percent_peak_to_peak=float(np.ptp(v[t>.8*end])),entered_and_stayed_in_dc_band_us=settle,final_in_dc_band=settled)
 worst=max(((val,s['instance'],pair) for s in r['stress'] for pair,val in s['max_abs_terminal_V'].items()))
 passed=all(x['final_in_dc_band'] and x['last_20percent_peak_to_peak']<2*x['relative_band']*abs(x['dc_target']) for x in metrics.values()) and r['device_screen_passed']
 res=dict(case=case,dc_case=dc_case,dc_result_sha256=sha(d/'result.json'),waveform_sha256=r['waveform']['sha256'],startup_joint_screen_passed=passed,metrics=metrics,stress_max=dict(V=worst[0],instance=worst[1],pair=worst[2],margin_to_3p63_V=3.63-worst[0]),scope='Synchronous supply/reference/input ramp, data held at logic1; a successful result does not validate asynchronous sequencing or high-speed traffic during startup')
 tt=np.unique(np.r_[np.linspace(0,min(end,2e-6),1001),np.linspace(0,end,2001)])
 traces={n:np.interp(tt,t,a[:,ix['v('+n+')']]) for n in ['vl','xdrv.dr','vlaser','vdd','xdrv.lctrl','xdrv.dctrl','xdrv.bctrl','xdrv.tctrl','xdrv.sbase','xdrv.stail']}
 np.savez_compressed(w/'startup-plot.npz',time_s=tt,current_mA=np.interp(tt,t,a[:,1])*1000,**traces)
 res['plot_sha256']=sha(w/'startup-plot.npz');emit(out,res);print(json.dumps(res),flush=True);return res
if __name__=='__main__':
 import sys
 analyze(*sys.argv[1:])
