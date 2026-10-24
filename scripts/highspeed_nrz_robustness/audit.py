#!/usr/bin/env python3
"""Readback all retained deck, source, logs and gzip bytes before compact delivery."""
from pathlib import Path
import argparse,datetime,gzip,hashlib,json
import run as r
import validate as v
p=argparse.ArgumentParser();p.add_argument('--work',required=True);p.add_argument('--full-waveforms',action='store_true');a=p.parse_args();w=r.ROOT/a.work;m=v.verify(w)
checks=[]
for path in sorted((w/'cases').glob('*/result.json')):
 x=json.loads(path.read_text());record={'case':x['case']['name'],'simulation_ok':x['simulation_ok'],'administrative_interruption':x.get('exit_code') is None and not x.get('error'),'checks':{}}
 for key,hashkey in [('runner_source','runner_source_sha256'),('log','log_sha256'),('waveform','waveform_sha256')]:
  if x.get(key):
   f=r.ROOT/x[key];actual=r.sha(f);assert actual==x[hashkey],str(f);record['checks'][key]=True
 if x.get('deck_sha256'):assert r.sha(path.with_name('testbench.spice'))==x['deck_sha256'];record['checks']['deck']=True
 for f,h in x.get('input_identity',{}).items():assert r.sha(w/'inputs'/f)==h
 record['checks']['included_frozen_inputs']=True
 if x.get('waveform') and a.full_waveforms:
  h=hashlib.sha256()
  with gzip.open(r.ROOT/x['waveform'],'rb') as f:
   for chunk in iter(lambda:f.read(1024**2),b''):h.update(chunk)
  assert h.hexdigest()==x['uncompressed_sha256'];record['checks']['gzip_full_readback']=True
 ap=path.with_name('analysis-verified.json');ap=ap if ap.exists() else path.with_name('analysis.json')
 if ap.exists():
  an=json.loads(ap.read_text());assert an['analysis_identity']['result_sha256']==r.sha(path)
  if an['analysis_identity'].get('analyzer_source'):assert r.sha(r.ROOT/an['analysis_identity']['analyzer_source'])==an['analysis_identity']['custom_analyzer_sha256']
  if an.get('device_specific_screen'):
   for d in an['device_specific_screen']['devices']:
    assert d['limit_V']==(6.0 if '06v0' in d['model'] else 3.63)
    assert d['passed']==(d['max_abs_terminal_V']<=d['limit_V'])
  record['checks']['analysis_identity_and_device_limits']=True
 checks.append(record)
output={'at':datetime.datetime.now().isoformat(),'work':r.rel(w),'manifest_sha256':r.sha(w/'manifest.json'),'full_waveform_readback':a.full_waveforms,'checks':checks,'all_checks_passed':True,'all_case_results_count':len(checks),'retained_failed_simulations':sum(not c['simulation_ok'] and not c['administrative_interruption'] for c in checks),'administrative_interrupted_results':sum(c['administrative_interruption'] for c in checks),'meaning':'Identity and integrity only; not functional/device pass.'}
r.emit(w/'readback-audit.json',output);r.emit(r.EVIDENCE/(w.name+'-readback-audit.json'),output);print(json.dumps({k:z for k,z in output.items() if k!='checks'}))
