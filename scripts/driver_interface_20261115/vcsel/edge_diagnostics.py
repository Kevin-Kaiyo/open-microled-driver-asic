#!/usr/bin/env python3
"""Native-wave edge extraction against each case's paired DC endpoints."""
import gzip,json,sys
import numpy as np
sys.dont_write_bytecode=True
import run
def crossing(t,y,target,rise):
 k=np.flatnonzero(((y[:-1]<target)&(y[1:]>=target)) if rise else ((y[:-1]>target)&(y[1:]<=target)))
 if not len(k):return None
 j=k[0];return float(t[j]+(target-y[j])/(y[j+1]-y[j])*(t[j+1]-t[j]))
def main():
 rows=[]
 for p in sorted(run.BUILD.glob('*/*/analysis.json')):
  folder=p.parent;m=run.read(folder/'manifest.json');a=run.read(p);cfg=m['interface_config']
  if cfg['steps_per_UI']!=40 or cfg['holdout']:continue
  dc=[run.read(folder.parent/f'DC-L{i}/result.json') for i in [0,1]]
  nodes=['v(d_src)','v(db_src)','v(xdrv.di)','v(xdrv.dbi)','v(d_cmd)','v(db_cmd)','v(vphy)'];cols=[0]+[m['expressions'].index(n)+1 for n in nodes]
  assert run.sha(folder/'waveform.dat.gz')==a['waveform']['sha256']
  with gzip.open(folder/'waveform.dat.gz','rt') as f:raw=np.loadtxt(f,skiprows=1,usecols=cols)
  t=raw[:,0];ui=m['end_s']/4736;bits=run.read(folder/'stimulus.json')['bits'];nr=[]
  for j,node in enumerate(nodes[:-1],start=1):
   low=dc[0]['nodes_final_V'][node];high=dc[1]['nodes_final_V'][node];normalized=(raw[:,j]-low)/(high-low);out={}
   for rise in [True,False]:
    values=[];latency=[];eligible=0
    for n in range(576,4669):
     if bits[n]==bits[n-1] or bool(bits[n])!=rise or len(set(bits[n-3:n]))!=1 or len(set(bits[n:n+3]))!=1:continue
     eligible+=1;lo,hi=np.searchsorted(t,[(n-.15)*ui,(n+2.95)*ui]);tt=t[lo:hi];yy=normalized[lo:hi]
     x=crossing(tt,yy,.1 if rise else .9,rise);z=crossing(tt,yy,.9 if rise else .1,rise);mid=crossing(tt,yy,.5,rise)
     if x is not None and z is not None and z>x:values.append((z-x)*1e12)
     if mid is not None:latency.append((mid-n*ui)*1e12)
    out['data_rise' if rise else 'data_fall']={'eligible_long_run_transitions':eligible,'complete_10_90_count':len(values),'missing_10_90_count':eligible-len(values),'edge_ps_quantiles':dict(zip(['p05','median','p95'],np.quantile(values,[.05,.5,.95]).tolist())) if values else None,'command_boundary_to_halflevel_ps_median':float(np.median(latency)) if latency else None}
   nr.append({'node':node,'DC_at_data0_V':low,'DC_at_data1_V':high,'physical_min_max_V':[float(raw[:,j].min()),float(raw[:,j].max())],'edges':out})
  mask=(t>=576*ui)&(t<=592*ui);np.savetxt(folder/'interface-native-excerpt.csv',np.column_stack([t[mask]/ui-576,raw[mask,1:]]),delimiter=',',header='time_UI,'+','.join(nodes),comments='',fmt='%.12g')
  rows.append({'candidate':cfg['candidate'],'net_Gbps':cfg['net_Gbps'],'case':str(folder.relative_to(run.ROOT)),'analysis_sha256':run.sha(p),'native_excerpt_sha256':run.sha(folder/'interface-native-excerpt.csv'),'nodes':nr,'VPHY_native_range_V':[float(raw[:,-1].min()),float(raw[:,-1].max())]})
  print(cfg['candidate'],cfg['net_Gbps'],'DI',nr[2]['edges'],flush=True)
 run.emit(run.EV/'vcsel-interface-edges.json',{'schema':'vcsel-finite-interface-native-edges-v1','rows':rows,'method':'Native adaptive points; 10–90% referenced to each node paired DC endpoints, not to assumed3.3V. Only transitions preceded and followed by>=3 equal bits within validation576..4671; searches[-.15,+2.95]UI about command boundary, no trace shifts. Data polarity normalized even on complementary nodes. Counts disclose incomplete crossings; this is descriptive edge timing, not RX phase optimization.'})
if __name__=='__main__':main()
