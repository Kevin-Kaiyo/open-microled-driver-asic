#!/usr/bin/env python3
"""Inventory actual new simulator outputs separately from copied/reused case wrappers."""
import json,argparse,gzip,hashlib
from pathlib import Path
import run as r

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--verify-raw',action='store_true');args=parser.parse_args()
 records=[];unique={};counts={}
 for rp in sorted(r.BUILD.glob('*/cases/*/result.json')):
  result=json.loads(rp.read_text());group=rp.parents[2].name
  counts[group]=counts.get(group,0)+1
  entry={'result':r.rel(rp),'result_sha256':r.sha(rp),'case':result['case']['name'],'simulation_ok':result['simulation_ok'],'waveform':result.get('waveform'),'reused_wrapper':bool(result.get('reuse'))}
  records.append(entry)
  if result.get('waveform'):
   key=result['waveform'];identity={k:result[k] for k in ['waveform','waveform_sha256','uncompressed_sha256','uncompressed_bytes','compressed_bytes']}
   if key in unique and unique[key]!=identity:raise ValueError('Inconsistent same-waveform reference')
   unique[key]=identity
 new=[v for p,v in unique.items() if p.startswith('build/highspeed-nrz-pvt/')];old=[v for p,v in unique.items() if not p.startswith('build/highspeed-nrz-pvt/')]
 out={'schema_version':1,'case_wrapper_count':len(records),'wrapper_counts_by_work':counts,'unique_new_phase_waveforms':len(new),'unique_older_phase_waveforms_referenced':len(old),'new_uncompressed_bytes':sum(x['uncompressed_bytes'] for x in new),'new_compressed_bytes':sum(x['compressed_bytes'] for x in new),'actual_simulation_failures':[x for x in records if not x['simulation_ok']],'new_raw':new,'older_raw_references':old,'case_wrappers':records,'interpretation':'Unique waveform paths identify actual simulator outputs. Copied BEFORE results are references, not new simulations. Electrical/RXscreen failures are retained successful executions, not pipeline failure.'}
 r.emit(r.EVIDENCE/'phase-inventory.json',out)
 if args.verify_raw:
  checks=[]
  for record in new+old:
   path=r.ROOT/record['waveform'];h=hashlib.sha256();size=0
   with gzip.open(path,'rb') as f:
    for block in iter(lambda:f.read(1024**2),b''):h.update(block);size+=len(block)
   passed=r.sha(path)==record['waveform_sha256'] and h.hexdigest()==record['uncompressed_sha256'] and size==record['uncompressed_bytes']
   checks.append({'path':record['waveform'],'passed':passed})
  validation={'inventory_sha256':r.sha(r.EVIDENCE/'phase-inventory.json'),'checked_unique_archives':len(checks),'checks':checks,'passed':all(x['passed'] for x in checks)}
  r.emit(r.EVIDENCE/'phase-raw-validation.json',validation)
  if not validation['passed']:raise ValueError('Phase raw hash verification failed')
 print(json.dumps({k:v for k,v in out.items() if k not in ['new_raw','older_raw_references','case_wrappers']},indent=2))
if __name__=='__main__':main()
