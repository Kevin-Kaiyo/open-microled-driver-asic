#!/usr/bin/env python3
"""Native voltage threshold propagation delay, separate from trained receiver phase."""
from pathlib import Path
import argparse,gzip,hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[3];EV=ROOT/'evidence/driver-pvt-20261117/b'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def events(t,x,sign):
 k=np.flatnonzero((x[:-1]<0)&(x[1:]>=0)) if sign==1 else np.flatnonzero((x[:-1]>0)&(x[1:]<=0));return t[k]-x[k]*(t[k+1]-t[k])/(x[k+1]-x[k])
def measure(case,frame):
 p=ROOT/case;m=json.loads((p/'manifest.json').read_text());r=json.loads((p/'result.json').read_text());ix=m['vectors'];a=np.loadtxt(gzip.open(p/'waveform.dat.gz','rt'),skiprows=1,usecols=[0,ix['d0'],ix['xdrv.gp'],ix['vdd']]);t=a[:,0];ui=(32/37)/1.6e9;start=(frame-1)*2.56e-6+576*ui;end=(frame-1)*2.56e-6+4672*ui
 rows={}
 for sign,name in [(1,'rising'),(-1,'falling')]:
  inp=events(t,a[:,1]-.5*a[:,3],sign);out=events(t,a[:,2]-.5*a[:,3],sign);inp=inp[(inp>=start)&(inp<end)];j=np.searchsorted(out,inp);ok=j<len(out);delay=np.full(len(inp),np.nan);delay[ok]=(out[j[ok]]-inp[ok])*1e12;ok &= delay<2*ui*1e12
  d=delay[ok];rows[name]={'input_edges':len(inp),'matched_edges':int(ok.sum()),'unmatched_edges':int((~ok).sum()),'min_ps':float(d.min()) if len(d) else None,'median_ps':float(np.median(d)) if len(d) else None,'max_ps':float(d.max()) if len(d) else None,'p05_ps':float(np.quantile(d,.05)) if len(d) else None,'p95_ps':float(np.quantile(d,.95)) if len(d) else None}
 return {'case':case,'frame':frame,'window_s':[start,end],'method':'D0 node after100ohm input to actual core GP, crossings at half instantaneous VDD. First following same-polarity output crossing within2lineUI; counts and failures retained. This propagation statistic is not CDR delay or BER jitter.','edges':rows,'result_sha256':sha(p/'result.json'),'raw_sha256':r['raw_sha256'],'gzip_sha256':r['gzip_sha256'],'generator_sha256':sha(Path(__file__))}
p=argparse.ArgumentParser();p.add_argument('case');p.add_argument('--frame',type=int,default=1);p.add_argument('--name',required=True);arg=p.parse_args();r=measure(arg.case,arg.frame);(EV/(arg.name+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r['edges'],indent=2))
