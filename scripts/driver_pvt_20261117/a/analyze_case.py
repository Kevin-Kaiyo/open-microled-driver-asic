#!/usr/bin/env python3
"""Append-only reanalysis: the frozen Nov15 recovery loop omitted an empty-crossing guard.

Normal receiver, training phases, thresholds, energy and stress are unchanged.
Empty events use start/end boundaries; incorrectly decoded bits retain zero margin.
Original raw, manifests and result.json stay frozen, including analysis_error.
"""
from pathlib import Path
import importlib.util,json,hashlib,numpy as np
ROOT=Path(__file__).resolve().parents[3]
p=ROOT/'scripts/driver_interface_20261115/micro/run.py'
s=importlib.util.spec_from_file_location('a_pvt_frozen_analysis',p);base=importlib.util.module_from_spec(s);s.loader.exec_module(base)
read,stress,sliced,receive,fixed_receive=base.read,base.stress,base.sliced,base.receive,base.fixed_receive
rx,dyn,legacy,CAPS,CAPCOMMON=base.rx,base.dyn,base.legacy,base.CAPS,base.CAPCOMMON
ETA=base.ETA
def summarize_case(folder,m,a):
 route=m['case']['route'];level=m['case'].get('level');ix=m['vectors'];t=a[:,0];cur=a[:,1];device=stress(a,m,folder,level is not None)
 result=dict(case=m['case'],MOS=len(device),stress=device,terminal_pass=all(x['terminal_pass'] for x in device),body_pass=all(x['body_pass'] for x in device),body_forward_V=max(x['body_forward_V'] for x in device),current_range_uA=[float(cur.min()*1e6),float(cur.max()*1e6)])
 source_power={name:-a[:,ix[name+'_voltage']]*a[:,ix[name+'_current']] for name in m['sources']}
 if level is not None:
  current=float(cur[-1]*1e6);target=25+75*level
  result.update(current_uA=current,target_uA=target,DC_error_percent=100*(current/target-1),DC_pass=abs(current/target-1)<=.01 and result['terminal_pass'] and result['body_pass'],power_mW={k:float(v[-1]*1e3) for k,v in source_power.items()},nodes_V={k:float(a[-1,v]) for k,v in ix.items() if k not in ['iled_cond'] and '_current' not in k})
  return result
 st=read(folder/'stimulus.json');rate=m['case']['net_rate_Gbps'];T=m['frame_duration_s'];assert abs(t[-1]-m['end_s'])<1e-14
 _,filtered=dyn.cascade_pwl(t,cur,200e-12,1/(2*np.pi*1e9));frame_rows=[];first_delay=None
 # Derived display-only trace: exact native points near edges; sparse overview is not used for scoring.
 vdiff=a[:,ix['led_a']]-a[:,ix['led_k']];preview_idx=np.linspace(0,len(t)-1,8000,dtype=int)
 for edge in ([m['fault']['assert_s'],m['fault']['release_s']] if 'fault' in m else []):preview_idx=np.r_[preview_idx,np.flatnonzero(np.abs(t-edge)<=30e-9)]
 if 'ready_rc' in ix and 'fault' in m:
  edge=m['fault']['release_s'];preview_idx=np.r_[preview_idx,np.flatnonzero((t>=edge-30e-9)&(t<=edge+250e-9))]
 preview_idx=np.unique(preview_idx);preview={key:a[preview_idx,col] for key,col in ix.items() if key in ['iled_cond','ipkg','out','led_a','led_k','disable','iso_g','iso_gb','iso_p','ready_rc','data_safe','data_gate','nand_o','nand_s','xdrv.bias','xdrv.vh','xdrv.vl','d0']}
 preview.update(time_s=t[preview_idx],received_uAeq=filtered[preview_idx]*1e6,icled_derivative_A=(200e-15*np.gradient(vdiff,t))[preview_idx]);np.savez_compressed(folder/'preview.npz',**preview)
 caps=CAPCOMMON+CAPS[route]+m.get('extra_caps',[])
 for k in range(m['frames']):
  start=k*T;stop=(k+1)*T;tt,b=sliced(t,a,start,stop);local=tt-start;signal=np.interp(tt,t,filtered)*1e6
  full=receive(local,signal,st,route,rate,rx)
  if first_delay is None:first_delay=full['delay_ps']*1e-12
  fixed=fixed_receive(local,signal,st,rate,first_delay)
  energy={name:legacy.signed_integrals(tt,-b[:,ix[name+'_voltage']]*b[:,ix[name+'_current']]) for name in m['sources']}
  storage={}
  for name,c,p,n in caps:
   v=b[[0,-1],ix[p]]-(b[[0,-1],ix[n]] if n!='0' else 0)
   storage[name]=dict(C_F=c,initial_V=float(v[0]),final_V=float(v[1]),delta_pJ=float(.5*c*(v[1]**2-v[0]**2)*1e12))
  # Include external package inductors, not intrinsic MOS charge models.
  inductors={}
  for name,L,port in [('VIN',.5e-9,'VIN'),('VDD',2e-9,'VDD'),('LPKG',.5e-9,'package')]:
   i=b[[0,-1],ix['ipkg' if port=='package' else port+'_current']];inductors[name]=dict(L_H=L,delta_pJ=float(.5*L*(i[1]**2-i[0]**2)*1e12))
  total={s:sum(v[s+'_J'] for v in energy.values())/4096*1e12 for s in ['positive','returned','net']}
  frame_rows.append(dict(frame=k+1,start_s=start,end_s=stop,full_receiver=full,first_frame_phase_receiver=fixed,energy_pJ_per_attempted_payload_bit=total,source_energy_J=energy,explicit_storage_caps=storage,explicit_storage_inductors=inductors,mean_current_uA=float(np.trapezoid(b[:,1],tt)/(stop-start)*1e6),current_range_uA=[float(b[:,1].min()*1e6),float(b[:,1].max()*1e6)],rail_endpoints_V={n:[float(b[0,ix[n]]),float(b[-1,ix[n]])] for n in (['xdrv.vh','xdrv.vl','vin','vdd'] if route=='A' else ['xdrv.bias','xdrv.sense','vin','vdd'])}))
 result.update(normal_current_IV_domain_pass=bool(cur.min()>=.1e-6 and cur.max()<=.032) if m['case']['mode']!='fault' else None,frames=frame_rows,native_samples=len(t),frame_duration_s=T,mode=m['case']['mode'],steady_state_qualified=False,steady_screen=dict(criterion='last2frames E+ relative change<=0.1%, all monitored rail endpoint changes<=0.1mV, explicit capacitor energy change<=0.1% of source net energy per frame; deterministic finite window only',energy_change_percent=100*(frame_rows[-1]['energy_pJ_per_attempted_payload_bit']['positive']/frame_rows[-2]['energy_pJ_per_attempted_payload_bit']['positive']-1) if len(frame_rows)>1 else None))
 if len(frame_rows)>1:
  last=frame_rows[-1];drift=max(abs(v[1]-v[0]) for v in last['rail_endpoints_V'].values());storage_abs=sum(abs(v['delta_pJ']) for v in last['explicit_storage_caps'].values());net=last['energy_pJ_per_attempted_payload_bit']['net']*4096
  result['steady_screen'].update(max_monitored_rail_endpoint_delta_mV=drift*1e3,absolute_explicit_cap_delta_fraction_of_source_net=storage_abs/net,finite_window_pass=abs(result['steady_screen']['energy_change_percent'])<=.1 and drift<=1e-4 and storage_abs/net<=.001)
 if m['case']['mode']=='fault':
  fault=m['fault'];off=fault['assert_s'];on=fault['release_s'];guard=20e-9;mask=(t>=off+guard)&(t<=on);window=cur[mask];above=np.flatnonzero((t>=off)&(t<on)&(np.abs(cur)>.1e-6));last_above=float(t[above[-1]]-off) if len(above) else 0
  off_tt,off_b=sliced(t,a,off+guard,on);off_energy={name:legacy.signed_integrals(off_tt,-off_b[:,ix[name+'_voltage']]*off_b[:,ix[name+'_current']]) for name in m['sources']}
  q=legacy.signed_integrals(t[mask],cur[mask]);vdiff=a[:,ix['led_a']]-a[:,ix['led_k']]
  result['shutdown']=dict(**fault,post_guard_current_range_uA=[float(window.min()*1e6),float(window.max()*1e6)],max_abs_current_uA=float(np.abs(window).max()*1e6),off_current_screen_pass=bool(np.abs(window).max()<=.1e-6),last_above_threshold_ns=last_above*1e9,post_guard_charge_fC={k.replace('_J','_fC'):v*1e15 for k,v in q.items()},LED_voltage_range_off_V=[float(vdiff[mask].min()),float(vdiff[mask].max())],low_current_model_boundary='Below0.1uA and reverse behavior are unmeasured linear extension. Shutdown result is numerical electrical diagnostic, not leakage/optical-darkness qualification.')
  result['shutdown']['source_energy_during_settled_off_J']=off_energy
  result['shutdown']['average_source_power_during_settled_off_mW']={name:1000*e['net_J']/(on-off-guard) for name,e in off_energy.items()}
  result['shutdown']['total_source_positive_power_during_settled_off_mW']=1000*sum(e['positive_J'] for e in off_energy.values())/(on-off-guard)
  # Frame 2 is fully after release+1us at 1.6Gb/s; first frame training precedes fault.
  result['shutdown']['last_frame_full_rx_pass']=frame_rows[-1]['full_receiver']['research_margin_pass']
  complete=[f for f in frame_rows if f['start_s']>=on+1e-6 and f['full_receiver']['research_margin_pass'] and f['first_frame_phase_receiver']['research_margin_pass']]
  result['shutdown']['first_complete_recovered_frame_start_after_release_us']=(complete[0]['start_s']-on)*1e6 if complete else None
  result['shutdown']['complete_recovered_frames']=[f['frame'] for f in complete]
  result['shutdown']['recovery_within_1us_verified']=False
  # Native-grid dV/dt estimates explicit LED capacitance current; package current also includes the protection clamp path.
  cap_current=200e-15*np.gradient(vdiff,t)
  result['shutdown']['displacement_definition']='200fF * native-grid nonuniform central derivative of LED A-K voltage; peak is numerical approximation, charge uses exact endpoint C*deltaV.'
  result['shutdown']['capacitive_charge_off_fC']=float(200e-15*(vdiff[mask][-1]-vdiff[mask][0])*1e15)
  result['shutdown']['package_current_off_range_uA']=[float(a[mask,ix['ipkg']].min()*1e6),float(a[mask,ix['ipkg']].max()*1e6)]
  result['shutdown']['capacitive_current_off_range_uA']=[float(cap_current[mask].min()*1e6),float(cap_current[mask].max()*1e6)]
  result['shutdown']['protection_nodes_off_V']={n:[float(a[mask,ix[n]].min()),float(a[mask,ix[n]].max())] for n in ['out','led_a','led_k','disable']+(['iso_g','iso_gb','en','led_feed'] if 'iso_g' in ix else [])+(['iso_p'] if 'iso_p' in ix else [])+(['ready_rc','data_safe'] if 'ready_rc' in ix else [])}
  result['shutdown']['settled_off_stress']=[]
  for dev in m['devices']:
   vv=[np.zeros(mask.sum()) if n=='0' else a[mask,ix[n]] for n in dev['nodes']];peak=max(float(np.abs(vv[i]-vv[j]).max()) for i in range(4) for j in range(i+1,4));body=max(0.,max(float((vv[3]-vv[j] if dev['model'].startswith('nfet') else vv[j]-vv[3]).max()) for j in [0,2]));result['shutdown']['settled_off_stress'].append(dict(instance=dev['instance'],peak_pair_V=peak,body_forward_V=body))
  result['shutdown']['transitions']={}
  for label,edge in [('assert',off),('release',on)]:
   edge_mask=(t>=edge-10e-9)&(t<=edge+30e-9)
   row=dict(window_relative_ns=[-10,30],conduction_range_uA=[float(cur[edge_mask].min()*1e6),float(cur[edge_mask].max()*1e6)],LED_AK_voltage_range_V=[float(vdiff[edge_mask].min()),float(vdiff[edge_mask].max())],VLED_delivered_current_range_mA=[float((-a[edge_mask,ix['VLED_current']]).min()*1e3),float((-a[edge_mask,ix['VLED_current']]).max()*1e3)],package_current_range_mA=[float(a[edge_mask,ix['ipkg']].min()*1e3),float(a[edge_mask,ix['ipkg']].max()*1e3)])
   row['protection_MOS_stress']=[]
   for dev in m['devices']:
    if not dev['instance'].startswith('xdrv.'):
     vv=[np.zeros(edge_mask.sum()) if node=='0' else a[edge_mask,ix[node]] for node in dev['nodes']];peak=max(float(np.abs(vv[i]-vv[j]).max()) for i in range(4) for j in range(i+1,4));row['protection_MOS_stress'].append(dict(instance=dev['instance'],peak_pair_V=peak,limit_V=3.63 if '03v3' in dev['model'] else 6.))
   result['shutdown']['transitions'][label]=row
  # Resume at the original frame-1 training phase; no post-fault phase fitting.
  ui=ETA/rate/1e9;nbits=m['frames']*4736;idx=np.arange(nbits);sample_t=idx*ui+first_delay
  valid=(sample_t>=on+fault['edge_s'])&(sample_t<=t[-1]-8*ui);idx=idx[valid];sample_t=sample_t[valid]
  expected=np.tile(st['bits'],m['frames'])[idx];sample=np.interp(sample_t,t,filtered)*1e6;sgn=rx._signed_margin(sample,expected,np.array([62.5]));margins=np.zeros(len(idx));events=rx._crossing_events(t,filtered*1e6,np.array([62.5]))
  for lev,ev in enumerate(events):
   ixlev=np.flatnonzero((expected==lev)&(sgn>0));ts=sample_t[ixlev]
   if len(ev):
    pos=np.searchsorted(ev,ts,side='right');previous=np.where(pos>0,ev[np.maximum(pos-1,0)],0);following=np.where(pos<len(ev),ev[np.minimum(pos,len(ev)-1)],t[-1])
   else:
    previous=np.zeros(len(ts));following=np.full(len(ts),t[-1])
   margins[ixlev]=np.maximum(0,np.minimum(ts-previous,following-ts))
  failed=(sgn<7.5)|(margins<.37*ui);last_bad=float(sample_t[failed][-1]) if failed.any() else on+fault['edge_s'];recovery=(last_bad+ui-on)
  result['shutdown'].update(recovery_screen=dict(definition='Last post-release amplitude/timing failure plus one line UI at the frozen first-frame training phase; all later sampled bits through end-minus8UI satisfy the normal margins. Finite-trace settling diagnostic, not synchronization protocol.',postrelease_scored_bits=int(len(idx)),postrelease_failed_margin_bits=int(failed.sum()),upper_bound_ns=recovery*1e9,all_subsequent_observation_ns=(sample_t[-1]-last_bad)*1e9,recovery_within_1us_verified=bool(recovery<=1e-6 and sample_t[-1]-last_bad>=1e-6)))
  result['shutdown']['recovery_within_1us_verified']=result['shutdown']['recovery_screen']['recovery_within_1us_verified']

 return result
