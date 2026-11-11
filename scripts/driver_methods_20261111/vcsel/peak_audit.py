#!/usr/bin/env python3
"""Native duration audit for gate-body excursions and laser-current peaks."""
from pathlib import Path
import gzip,hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[3];EV=ROOT/'evidence/driver-methods-20261111';BUILD=ROOT/'build/driver-methods-20261111/VCSEL'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def intervals(t,y,threshold):
 mask=y>threshold;d=np.diff(np.r_[False,mask,False].astype(int));starts=np.flatnonzero(d==1);ends=np.flatnonzero(d==-1)-1;dur=[]
 for a,b in zip(starts,ends):
  first=t[a] if a==0 else t[a-1]+(threshold-y[a-1])*(t[a]-t[a-1])/(y[a]-y[a-1])
  last=t[b] if b==len(t)-1 else t[b]+(threshold-y[b])*(t[b+1]-t[b])/(y[b+1]-y[b])
  dur.append(float((last-first)*1e12))
 return dict(threshold=float(threshold),count=len(dur),max_contiguous_ps=max(dur,default=0),total_ps=sum(dur),method='Linear interpolation of threshold crossings on native variable-step data; no debounce or smoothing.')
def main():
 cases={'baseline7.2':ROOT/'build/ab-improvement-20261111/VCSEL/vc-atten50-steer20/net7.2-edge20-s40'}
 cases.update({str(p.parent.name)+'/'+p.name:p for p in BUILD.glob('vc-single*/*') if (p/'analysis.json').exists()})
 rows={}
 for name,p in cases.items():
  m=json.loads((p/'manifest.json').read_text());r=json.loads((p/'result.json').read_text());wave=p/'waveform.dat.gz';assert sha(wave)==r['waveform']['sha256']
  nodes=['v(jmon)','v(xdrv.gp)','v(xdrv.gn)','v(xdrv.dr)','v(xdrv.di)','v(xdrv.dbi)','i(VD)','i(VDB)'];cols=[0]+[m['expressions'].index(n)+1 for n in nodes]
  with gzip.open(wave,'rt') as f:a=np.loadtxt(f,skiprows=1,usecols=cols)
  t=a[:,0];v=dict(zip(nodes,a[:,1:].T));body={}
  for gate in ['gp','gn']:
   for typ,signal in [('PMOS_drain_minus_body',v[f'v(xdrv.{gate})']-v['v(xdrv.dr)']),('NMOS_body_minus_drain',-v[f'v(xdrv.{gate})'])]:
    body[gate+'_'+typ]={'peak_V':float(max(signal.max(),0)),'above_0p2V':intervals(t,signal,.2),'above_0p25V':intervals(t,signal,.25),'above_0p3V':intervals(t,signal,.3)}
  cur=v['v(jmon)'];k=int(cur.argmax());near=(t>=t[k]-50e-12)&(t<=t[k]+50e-12)
  rows[name]={'case':str(p.relative_to(ROOT)),'net_Gbps':m['net_Gbps'],'steps_per_UI':m['steps_per_UI'],'holdout':m.get('method_config',{}).get('holdout',False),'Ipeak_mA':float(cur[k]*1e3),'Ipeak_time_ps':float(t[k]*1e12),'current_above_7p5mA':intervals(t,cur*1e3,7.5),'body_forward':body,'input_source_current_range_mA':{n:[float(v[n].min()*1e3),float(v[n].max()*1e3)] for n in ['i(VD)','i(VDB)']},'peak_window_native':{'time_ps_relative_peak':((t[near]-t[k])*1e12).tolist(),**{n:x[near].tolist() for n,x in v.items()}},'waveform_gzip_sha256':sha(wave),'waveform_raw_sha256':r['waveform']['raw_sha256']}
 out={'schema':'vcsel-gate-current-peak-audit-v1','rows':rows,'scope':'Current-domain and body-forward screening remain binding regardless of short duration. This is native waveform analysis, not time-dependent reliability or measured optical validity. Ideal input-source currents are metered but do not establish a realizable input PHY.'};(EV/'vcsel-peak-audit.json').write_text(json.dumps(out,indent=2)+'\n');print('audited',len(rows),'cases')
if __name__=='__main__':main()
