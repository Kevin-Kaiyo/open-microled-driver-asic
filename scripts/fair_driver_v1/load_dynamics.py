#!/usr/bin/env python3
"""Exact PWL load-only current-step calculation; never a transistor candidate."""
from pathlib import Path
import csv,json,re
import numpy as np
import run as e

def segment_time(i0,i1,target,ci,cv,cap):
 if i0==i1:return 0.
 assert (i0-target)*(i1-target)>0 and abs(i1-target)<abs(i0-target)
 lo,hi=sorted((i0,i1));knots=ci[(ci>lo)&(ci<hi)];bounds=np.r_[lo,knots,hi];answer=0.
 for a,b in zip(bounds[:-1],bounds[1:]):
  k=int(np.searchsorted(ci,(a+b)/2)-1);rd=(cv[k+1]-cv[k])/(ci[k+1]-ci[k]);answer+=cap*rd*abs(np.log(abs((a-target)/(b-target))))
 return float(answer)
def main():
 path=e.ROOT/'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv';rows=list(csv.DictReader(path.open()));ci=np.array([float(x['current_A']) for x in rows]);cv=np.array([float(x['voltage_V']) for x in rows]);cap=200e-15
 frozen=(e.BUILD/'matched-r2/inputs/led.spice').read_text();body=frozen.split('),0,0,',1)[1].split(')',1)[0];points=np.array([float(x) for x in re.findall(r'[-+]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][-+]?[0-9]+)?',body)]).reshape(-1,2)
 assert np.array_equal(points[:,0],cv) and np.array_equal(points[:,1],ci),'CSV/frozenPWL drift'
 assert abs(segment_time(100e-6,50e-6,25e-6,np.array([0.,.001]),np.array([0.,1.]),1e-12)-1e-9*np.log(3))<1e-20
 levels=[]
 for i in [25e-6,50e-6,75e-6,100e-6]:
  k=int(np.searchsorted(ci,i)-1);rd=(cv[k+1]-cv[k])/(ci[k+1]-ci[k]);levels.append({'I_uA':i*1e6,'VF_V':float(np.interp(i,ci,cv)),'local_r_d_ohm':float(rd),'tau_rdC_ns':float(rd*cap*1e9)})
 samples=[]
 for i in np.r_[100e-6,25e-6+np.geomspace(75e-6-.0001e-6,.0001e-6,1600)]:samples.append([segment_time(100e-6,float(i),25e-6,ci,cv,cap),float(i)])
 # Discrete points are exact segment integrals of C*dV/dt=I_sink-I_cond(V).
 result={'level':'calculation, not measured dynamics and not a powered circuit comparison','model_csv_sha256':e.sha(path),'frozen_LED_spice_sha256':e.sha(e.BUILD/'matched-r2/inputs/led.spice'),'capacitance_F':cap,'equation':'C*dVF/dt=I_sink-I_LED(VF); ideal instantaneous sink100uA->25uA; same static PWL, no driver/gate/reference/package/optical/RX poles','method':'Exact integral sum C*rd(segment)*log(abs((Istart-Itarget)/(Iend-Itarget))) across every PWL segment. Piecewise-resistance analytic control, no fitted lifetime.','levels':levels,'step_100to25':{'VF_delta_V':levels[3]['VF_V']-levels[0]['VF_V'],'charge_delta_fC':(levels[3]['VF_V']-levels[0]['VF_V'])*cap*1e15,'time_to_32p5uA_ns':segment_time(100e-6,32.5e-6,25e-6,ci,cv,cap)*1e9,'time_to_30uA_ns':segment_time(100e-6,30e-6,25e-6,ci,cv,cap)*1e9,'current_at_3p892ns_uA':float(np.interp(3.892e-9,np.array(samples)[:,0],np.array(samples)[:,1])*1e6)},'limits':['The200fF is a shared sensitivity assumption, not a fitted measured capacitance.','Package/driver conductance and transient gate/reference effects omitted; this is an isolation control, not proof of sole causality.','A voltage-output candidate can supply displacement current; this ideal fixed-current sink control does not describe A.','Full-frame transistor results continue to use real references/rails, never this ideal sink.'],'self_test':'Constant-r analytic C*r*ln3 fixture passed'}
 e.emit(e.ROOT/'evidence/fair-driver-v1/load-dynamics.json',result);e.emit(e.BUILD/'load-only-step.json',{'time_current_A':samples,'result':result});print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
