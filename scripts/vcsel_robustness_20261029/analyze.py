#!/usr/bin/env python3
"""Fixed v3 receiver; original VCSEL normalization and optical/RX conditions."""
from pathlib import Path
import argparse,json,shutil
import numpy as np
from run import ROOT,BUILD,EV,sha,emit,mod

def rxfilter(t,x,hz=5e9):
 tau=1/(2*np.pi*hz);out=np.empty(len(t));out[0]=x[0]
 for k in range(1,len(t)):
  h=t[k]-t[k-1];u=x[k-1];s=(x[k]-u)/h;e=np.exp(-h/tau)
  out[k]=e*out[k-1]+u*(-np.expm1(-h/tau))+s*(h-tau*(-np.expm1(-h/tau)))
 return out

def analyze(case,grid_ps=2.5,label='fixed-v3'):
 work=BUILD/case;m=json.loads((work/'manifest.json').read_text());r=json.loads((work/'result.json').read_text());c=m['config']
 assert r['simulation_ok'] and c['mode']=='frame' and c['nbits']==4736
 out=work/('analysis-'+label)
 if out.exists():
  prior=json.loads((out/'plan.json').read_text());assert prior['grid_ps']==grid_ps, 'Immutable analysis grid mismatch'
  assert prior['waveform_sha256']==sha(ROOT/r['waveform']['path']), 'Immutable analysis waveform mismatch'
  return json.loads((out/'result.json').read_text())
 inp=out/'inputs';inp.mkdir(parents=True)
 names=['scripts/three_gbps_experiment/vcsel_model.py','analog/models/vcsel_research_20261027/parameters.json','scripts/three_gbps_experiment/vcsel_driver_receiver_v3.py','analog/circuits/vcsel_research_20261027/receiver-feasibility-v3-diagnostic.json','scripts/vcsel_robustness_20261029/analyze.py']
 for n in names:
  p=inp/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/n,p)
 optical=mod(inp/names[0],case.replace('-','_')+'_opto');rx=mod(inp/names[2],case.replace('-','_')+'_rx')
 low,high=map(float,optical.static_power(np.array([.003,.007])));scale=(high-low)/75e-6
 plan=dict(case=case,grid_ps=grid_ps,sources={n:sha(inp/n) for n in names},waveform_sha256=sha(ROOT/r['waveform']['path']),normalization=dict(low_W=low,high_W=high,scale_W_per_Aeq=scale),fixed_receiver='v3 unchanged;448training+64guard;4096validation;min7.5uAeq and100ps;5GHzRx',optical_response='figure3mA_proxy')
 emit(out/'plan.json',plan)
 a=np.loadtxt(ROOT/r['waveform']['path'],skiprows=1);native_t=a[:,0];ix={e:i+1 for i,e in enumerate(m['expressions'])}
 end=m['end_s'];ui=32/37/(c['rate']*1e9);t=np.linspace(0,end,int(np.ceil(end/(grid_ps*1e-12)))+1);current=np.interp(t,native_t,a[:,1])
 power=optical.optical_power(t,current,response='figure3mA_proxy');eq=25e-6+(power-low)/scale
 rx.filter_trace=lambda ts,x:(np.asarray(x),rxfilter(np.asarray(ts),np.asarray(x)))
 stim=json.loads((work/'stimulus.json').read_text());result=rx.analyze(t,eq,stim,'NRZ',c['rate']);recv_eq=rxfilter(t,eq);recv=low+(recv_eq-25e-6)*scale
 result['proxy']=dict(input='VCSEL graph-constrained optical power mapped to Aeq; not photodiode current',optical_response='figure3mA_proxy',optical_metadata=optical.response_metadata('figure3mA_proxy'),rx_pole_Hz=5e9,uniform_grid_ps=grid_ps,native_max_step_ps=r['max_timestep_ps'],normalization=plan['normalization'])
 samples=np.interp(np.arange(576,4672)*ui+result['sampling']['delay_s'],t,recv);bits=np.array(stim['bits'][576:4672]);margin=(2*bits-1)*(samples-(low+high)/2)
 domain=dict(min_current_mA=float(current.min()*1e3),max_current_mA=float(current.max()*1e3),IV_outside_fraction=float(np.trapezoid(((current<.002)|(current>.008)).astype(float),t)/end),PI_above_fraction=float(np.trapezoid((current>.0075).astype(float),t)/end),negative_optical_fraction=float(np.trapezoid((power<0).astype(float),t)/end))
 domain['native_min_current_mA']=r['current_range_mA'][0];domain['native_max_current_mA']=r['current_range_mA'][1]
 domain_ok=domain['IV_outside_fraction']==domain['PI_above_fraction']==domain['negative_optical_fraction']==0 and r['current_range_mA'][0]>=2 and r['current_range_mA'][1]<=7.5
 res=dict(case=case,variant=c['variant'],corner=c['corner'],temp_C=c['temp'],supply_V=c['voltage'],receiver=result,errors=result['validation']['bit_errors'],time_margin_ps=result['horizontal_margin']['min_ps'],min_signed_margin_uAeq=result['validation']['decision_distance_min_uA'],optical_margin_min_mW=float(margin.min()*1e3),domain=domain,device_screen_passed=r['device_screen_passed'],combined_screen_passed=bool(result['passed'] and domain_ok and r['device_screen_passed']),energy=r['total_energy'],energy_by_port=r['energy_by_port'],current_range_mA=r['current_range_mA'],stress_max_V=r['max_terminal_V'],body_max_V=r['max_body_forward_V'],plan_sha256=sha(out/'plan.json'))
 phase=np.linspace(-.5,1.5,161);eye=np.array([np.interp((k+phase)*ui+result['sampling']['delay_s'],t,recv) for k in range(576,736)]);tt=np.linspace(576*ui,608*ui,2561)
 trace={n:np.interp(tt,native_t,a[:,ix['v('+n+')']]) for n in ['vlaser','vdd','vref','xdrv.gp','xdrv.gn']}
 if c['variant']!='baseline':
  for n in ['vl','xdrv.dr','xdrv.bctrl','xdrv.tctrl','xdrv.sbase','xdrv.stail']:
   observed='vlaser' if n=='vl' and c['variant']=='reference' else n
   trace[n]=np.interp(tt,native_t,a[:,ix['v('+observed+')']])
 np.savez_compressed(out/'plot-data.npz',eye_phase_UI=phase,eye_rx_power_W=eye,eye_labels=bits[:160],trace_t_s=tt,trace_current_A=np.interp(tt,t,current),trace_optical_W=np.interp(tt,t,power),trace_rx_W=np.interp(tt,t,recv),validation_samples_W=samples,validation_bits=bits,**trace)
 res['plot_data_sha256']=sha(out/'plot-data.npz');emit(out/'result.json',res)
 print(json.dumps({k:res[k] for k in ['case','errors','time_margin_ps','min_signed_margin_uAeq','combined_screen_passed']},ensure_ascii=False),flush=True)
 return res
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('case');ap.add_argument('--grid-ps',type=float,default=2.5);ap.add_argument('--label',default='fixed-v3');a=ap.parse_args();analyze(a.case,a.grid_ps,a.label)
