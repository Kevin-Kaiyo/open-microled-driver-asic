#!/usr/bin/env python3
"""Read-only native PVT diagnostics; no altered circuit or receiver conditions."""
from pathlib import Path
import gzip,hashlib,json,sys
import numpy as np
sys.dont_write_bytecode=True
import run

def selected(folder,nodes):
 m=run.read(folder/'manifest.json');r=run.read(folder/'result.json');p=folder/'waveform.dat.gz'
 assert run.sha(p)==r['waveform']['sha256']
 with gzip.open(p,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['waveform']['raw_sha256']
 names=[n for n in nodes if n in m['expressions']]
 a=np.loadtxt(p,skiprows=1,usecols=[0]+[m['expressions'].index(n)+1 for n in names]);return m,r,a[:,0],dict(zip(names,a[:,1:].T))

def crossing(t,y,level,rise):
 k=np.flatnonzero((y[:-1]<level)&(y[1:]>=level) if rise else (y[:-1]>level)&(y[1:]<=level))
 if not len(k):return None
 j=k[0];return float(t[j]+(level-y[j])/(y[j+1]-y[j])*(t[j+1]-t[j]))

def main():
 events=[];edges=[]
 ref=run.BUILD/'frozen/sshotlow/short-net8.8-s40'
 _,_,rt,rv=selected(ref,['v(d_src)']);common_time=float(rt[np.argmin(rv['v(d_src)'])])
 for f in sorted(run.BUILD.glob('*/*/*/result.json')):
  folder=f.parent;m=run.read(folder/'manifest.json');r=run.read(f)
  if m['kind']=='dc' or not r['simulation_ok']:continue
  names=['v(d_src)','v(db_src)','v(xdrv.di)','v(xdrv.dbi)','v(xdrv.gp)','v(xdrv.gn)','v(d_cmd)','v(db_cmd)','v(phy_d_gate)','v(phy_db_gate)','v(vphy)','v(jmon)']
  m,r,t,v=selected(folder,names);ui=m['UI_ps']*1e-12
  # Earliest absolute minimum is the exact adaptive-grid event, not a preview grid.
  j=int(np.argmin(v['v(d_src)']));mask=(t>t[j]-50e-12)&(t<t[j]+90e-12)
  event={'case':str(folder.relative_to(run.ROOT)),'manifest_sha256':run.sha(folder/'manifest.json'),'result_sha256':run.sha(f),'event_time_s':float(t[j]),'event_nodes_V':{n:float(q[j]) for n,q in v.items() if n!='v(jmon)'},'event_current_mA':float(v['v(jmon)'][j]*1e3),'native_sample_index':j,'terminal_peak':r['terminal_peak'],'max_body_forward_V':r['max_body_forward_V']}
  excerpt=folder/'minimum-event.npz';np.savez_compressed(excerpt,time_s=t[mask],**{n:q[mask] for n,q in v.items()});event['excerpt_sha256']=run.sha(excerpt);events.append(event)
  if m['pvt_config']['corner']=='sshotlow' and m['kind']=='short':
   common=(t>common_time-50e-12)&(t<common_time+90e-12);cp=folder/'comparison-event.npz'
   np.savez_compressed(cp,time_s=t[common],**{n:q[common] for n,q in v.items()});event['comparison_event_sha256']=run.sha(cp);event['comparison_reference_time_s']=common_time
  if m['kind']!='full' or m['steps_per_UI']!=40:continue
  dcs=[run.read(folder.parent/f'DC-L{l}/result.json') for l in [0,1]];bits=run.read(folder/'stimulus.json')['bits'];nr=[]
  for node in ['v(d_src)','v(xdrv.di)','v(xdrv.gp)']:
   low=dcs[0]['node_ranges_V'][node][0];high=dcs[1]['node_ranges_V'][node][0];y=(v[node]-low)/(high-low);rr={}
   for rise in [True,False]:
    durations=[];delay=[];eligible=0
    for n in range(576,4669):
     if bits[n]==bits[n-1] or bool(bits[n])!=rise or len(set(bits[n-3:n]))!=1 or len(set(bits[n:n+3]))!=1:continue
     eligible+=1;lo,hi=np.searchsorted(t,[(n-.15)*ui,(n+2.95)*ui]);tt=t[lo:hi];yy=y[lo:hi]
     a=crossing(tt,yy,.1 if rise else .9,rise);b=crossing(tt,yy,.9 if rise else .1,rise);mid=crossing(tt,yy,.5,rise)
     if a is not None and b is not None and b>a:durations.append((b-a)*1e12)
     if mid is not None:delay.append((mid-n*ui)*1e12)
    rr['data_rise' if rise else 'data_fall']=dict(eligible=eligible,complete_count=len(durations),missing_count=eligible-len(durations),edge_ps_p05_median_p95=np.quantile(durations,[.05,.5,.95]).tolist() if durations else None,command_to_halflevel_ps_median=float(np.median(delay)) if delay else None)
   nr.append(dict(node=node,DC0_V=low,DC1_V=high,edges=rr))
  edges.append(dict(case=str(folder.relative_to(run.ROOT)),nodes=nr))
 run.emit(run.EV/'native-diagnostics.json',dict(schema='vcsel-pvt-native-diagnostics-v1',script_sha256=run.sha(Path(__file__)),events=events,edges=edges,method='All events from original adaptive samples, never downsampled previews. Edge10/90 refers to paired DC endpoint values, data-polarity normalized. >=3 equal bits each side; validation576..4671; fixed search[-.15,+2.95]UI; no waveform shifting. Event excerpts retain all original native samples within the stated window.'))
if __name__=='__main__':main()
