#!/usr/bin/env python3
"""Compare only an existing completed prefix; never pad incomplete simulations."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[3];BUILD=ROOT/'build/driver-interface-20261115/MicroLED';EV=ROOT/'evidence/driver-interface-20261115'
def read(p):return json.loads(p.read_text())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(route):
 variants={'A':('protected_v3','protected_v3r'),'B':('protected_v6','protected_v6r')}[route];cases=[BUILD/f'{route}-{v}'/'fault-f2-net1.6-s40' for v in variants];traces=[];sources=[];names=['iled_cond','out','disable','iso_p','led_a']
 for p in cases:
  m=read(p/'manifest.json');r=read(p/'result.json');w=p/'waveform.dat.gz';assert sha(w)==r['gzip_sha256'];a=np.loadtxt(w,skiprows=1,usecols=[0]+[m['vectors'][n] for n in names]);traces.append(a);sources.append(dict(case=str(p.relative_to(ROOT)),manifest_sha256=sha(p/'manifest.json'),result_sha256=sha(p/'result.json'),waveform_gzip_sha256=r['gzip_sha256'],raw_sha256=r['raw_sha256']))
 old,new=traces;end=min(old[-1,0],new[-1,0]);mask=old[:,0]<=end;t=old[mask,0];x=old[mask,1:];y=np.column_stack([np.interp(t,new[:,0],new[:,k+1]) for k in range(len(names))]);delta=y-x;edgefree=(np.abs(t-.64e-6)>25e-9)&(np.abs(t-1.28e-6)>25e-9);summary={}
 for label,sel in [('entire_common_prefix',np.ones(len(t),dtype=bool)),('outside_control_edge_windows',edgefree)]:
  rows={}
  for j,n in enumerate(names):
   d=delta[:,j];idx=np.flatnonzero(sel);rows[n]=dict(max_abs_difference=float(np.abs(d[sel]).max()),rms_sample_difference=float(np.sqrt(np.mean(d[sel]**2))),unit='A' if n=='iled_cond' else 'V',max_time_s=float(t[idx[np.abs(d[sel]).argmax()]]))
  summary[label]=rows
 out=dict(schema_version='micro-control-source-prefix-comparison-v1',route=route,sources=sources,common_end_s=float(end),original_required_end_s=5.12e-6,original_prefix_points=len(t),replacement_complete_end_s=float(new[-1,0]),metrics=summary,method='Replacement native-time signal interpolated only at existing original-prefix samples. RMS is sample-weighted diagnostic, not time-integrated power. No data after the old abort point is invented. Both whole prefix and outside +/-25ns control-edge windows are shown; DATA continues toggling.',scope='Confirms numerical-prefix consistency after explicitly changing ideal control source to100ohm. It does not make the truncated original run complete or qualify the model.',source_sha256=sha(Path(__file__)))
 (EV/f'micro-source-impedance-{route}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(route,summary)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('route',choices=['A','B']);run(p.parse_args().route)
