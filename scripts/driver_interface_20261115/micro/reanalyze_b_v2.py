#!/usr/bin/env python3
"""Append-only correction of B-v2 reference gates; preserve original artifacts."""
import argparse,copy,gzip,hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(folder):
 folder=ROOT/folder;r=json.loads((folder/'result.json').read_text());m=json.loads((folder/'manifest.json').read_text());assert r['case']['route']=='B' and folder.parent.name=='B-protected_v2'
 dest=folder/'reanalysis.json'
 if dest.exists():return
 original=dict(manifest_sha256=sha(folder/'manifest.json'),result_sha256=sha(folder/'result.json'),deck_sha256=sha(folder/'testbench.spice'),gzip_sha256=sha(folder/'waveform.dat.gz'),raw_sha256=r['raw_sha256'])
 assert original['gzip_sha256']==r['gzip_sha256']
 with gzip.open(folder/'waveform.dat.gz','rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['raw_sha256']
 devices=copy.deepcopy(m['devices']);changed=[]
 for d in devices:
  if d['instance'].startswith('xdrv.') and 'disable' in d['nodes']:
   old=d['nodes'].copy();d['nodes']=['0' if n=='disable' else n for n in old];changed.append(dict(instance=d['instance'],old_nodes=old,new_nodes=d['nodes']))
 assert len(changed)==2,changed
 a=np.loadtxt(folder/'waveform.dat.gz',skiprows=1,ndmin=2);ix=m['vectors'];rows=[]
 for d in devices:
  vs=[np.zeros(len(a)) if n=='0' else a[:,ix[n]] for n in d['nodes']];peak=max(float(np.abs(vs[i]-vs[j]).max()) for i in range(4) for j in range(i+1,4));body=max(0.,max(float((vs[3]-vs[j] if d['model'].startswith('nfet') else vs[j]-vs[3]).max()) for j in [0,2]));limit=3.63 if '03v3' in d['model'] else 6.
  rows.append(dict(**d,peak_pair_V=peak,limit_V=limit,body_forward_V=body,terminal_pass=peak<=limit,body_pass=body<=.3))
 out=dict(schema_version='micro-device-node-reanalysis-v1',original=original,changed_connections=changed,corrected_devices=devices,corrected_stress=rows,terminal_pass=all(x['terminal_pass'] for x in rows),body_pass=all(x['body_pass'] for x in rows),body_forward_V=max(x['body_forward_V'] for x in rows),reason='B-v2 XDRV DISABLE port is physically tied to0 so reference remains running. Original metadata incorrectly retained disable signal at two nested reference gates. Corrected here by the actual expanded deck, without changing circuit or raw waveform.',scope='Supersedes only original device-node metadata/stress. Original deck/manifest/result/wave remain unchanged; DC/optical/conduction/source energy unchanged. New v3 generates correct nodes before simulation.',source_sha256=sha(Path(__file__)))
 if m['case'].get('mode')=='fault':
  t=a[:,0];off=m['fault']['assert_s'];on=m['fault']['release_s'];mask=(t>=off+20e-9)&(t<=on);ii=np.flatnonzero(mask);out['native_settled_off_nodes']={}
  for n in ['out','led_k','led_a','iso_g','iso_gb']:
   v=a[:,ix[n]];lo=ii[v[mask].argmin()];hi=ii[v[mask].argmax()];out['native_settled_off_nodes'][n]=dict(min_V=float(v[lo]),max_V=float(v[hi]),min_time_s=float(t[lo]),max_time_s=float(t[hi]))
 dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(dest)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('folder');run(p.parse_args().folder)
