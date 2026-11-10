#!/usr/bin/env python3
"""Measure native node latencies on settled NRZ transitions; no receiver refit.

Run with one or more current-stage case directories. Compact output is written
to build/ab-improvement-20261111/A. These statistics are deterministic isolated
transition delays, not random-jitter measurements.
"""
from pathlib import Path
import hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'build/ab-improvement-20261111/A'
def read(p):return json.loads(Path(p).read_text())
def emit(p,value):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def crossings(t,y,q,rising):
 idx=np.flatnonzero((y[:-1]<q)&(y[1:]>=q) if rising else (y[:-1]>q)&(y[1:]<=q))
 return t[idx]+(q-y[idx])*(t[idx+1]-t[idx])/(y[idx+1]-y[idx])

def diagnose(folder):
 folder=folder.resolve();assert folder.is_relative_to(ROOT)
 r=read(folder/'result.json');assert r['case']['route']=='A' and r['simulation_ok'] and 'analysis_error' not in r
 assert sha(folder/'waveform.dat.gz')==r['gzip_sha256']
 a=np.loadtxt(folder/'waveform.dat.gz',skiprows=1);t=a[:,0];v=r['metadata']['vectors'];st=read(folder.parents[1]/'stimulus.json');bits=np.array(st['bits']);ui=st['eta']/(r['case']['net_rate_Gbps']*1e9)
 assert len(bits)==4736 and np.isfinite(a).all() and np.all(np.diff(t)>0)
 midpoint=r['case']['vdd_V']/2
 dc=[]
 for level in [0,1]:
  dp=folder.parents[1]/'cases'/f'DC-L{level}';dr=read(dp/'result.json');assert sha(dp/'waveform.dat.gz')==dr['gzip_sha256'];da=np.loadtxt(dp/'waveform.dat.gz',skiprows=1,ndmin=2);dc.append(float(da[-1,dr['metadata']['vectors']['out']]))
 rows=[]
 for bit in [0,1]:
  # Long settled runs on either side isolate each polarity from adjacent ISI.
  selected=[i for i in range(579,4669) if all(bits[i-3:i]==1-bit) and all(bits[i:i+3]==bit)]
  for name,q,positive in [('d0',midpoint,True),('xdrv.di',midpoint,True),('xdrv.n1',midpoint,False),('xdrv.ctrl',midpoint,True),('out',sum(dc)/2,False),('iled_cond',62.5e-6,True)]:
   tt=crossings(t,a[:,v[name]],q,positive if bit else not positive)
   delays=[];missing=[]
   for i in selected:
    hits=tt[(tt>=i*ui)&(tt<(i+3)*ui)]
    if len(hits):delays.append((hits[0]-i*ui)*1e12)
    else:missing.append(i)
   rows.append({'to_bit':bit,'node':name,'threshold':q,'event_count':len(selected),'measured_count':len(delays),'missing':missing,'median_delay_ps':float(np.median(delays)) if delays else None,'min_delay_ps':float(min(delays)) if delays else None,'max_delay_ps':float(max(delays)) if delays else None})
 return {'source':str(folder.relative_to(ROOT)),'source_sha256':sha(folder/'result.json'),'rate_Gbps':r['case']['net_rate_Gbps'],'scope':'Transition latency after at least 3 identical bits before and after; measured from PWL transition start, using fixed midpoints. Not jitter statistics.','rows':rows}

if __name__=='__main__':
 for arg in sys.argv[1:]:
  f=Path(arg);result=diagnose(f);emit(OUTPUT/(f.parents[1].name+'-'+f.name+'-edges.json'),result);print(json.dumps(result,ensure_ascii=False))
