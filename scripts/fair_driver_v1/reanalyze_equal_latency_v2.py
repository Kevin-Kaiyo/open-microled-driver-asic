#!/usr/bin/env python3
"""One absolute-latency RX contract; immutable SPICE data and strict denominators."""
import argparse,concurrent.futures,datetime,hashlib,json,shutil
from pathlib import Path
import numpy as np
import run as e
EXECUTION_SOURCE=Path(__file__).read_bytes()
EXECUTION_SHA=hashlib.sha256(EXECUTION_SOURCE).hexdigest()
DEST=e.BUILD/'rx-equal-latency-v2-final-r1'
SOURCE=e.ROOT/'scripts/fair_driver_v1/receiver_equal_latency_v2.py'
CONTRACT=e.ROOT/'evidence/fair-driver-v1/rx-equal-latency-v2-contract.md'
VERSION='equal-absolute-latency-v2'
GROUPS={'baseline':'matched-r2','controls':'controls-r1'}

def initialize():
 if (DEST/'manifest.json').exists():return verify()
 assert SOURCE.exists() and CONTRACT.exists(),'Wait for reviewed/frozen v2 source'
 DEST.mkdir(parents=True,exist_ok=True);(DEST/'execution-sources').mkdir()
 for src,name in [(SOURCE,'receiver.py'),(CONTRACT,'contract.md')]:shutil.copy2(src,DEST/name)
 for payload,name in [(EXECUTION_SOURCE,'reanalysis-'+EXECUTION_SHA+'.py'),(e.EXECUTION_SOURCE,'run-'+e.EXECUTION_SHA+'.py')]:
  (DEST/'execution-sources'/name).write_bytes(payload)
 rx=e.module(DEST/'receiver.py','rx_v2_init');st=rx.make_stimulus();old=json.loads((e.BUILD/'matched-r2/stimulus.json').read_text());assert st['bits']==old['bits'] and st['eta']==old['eta'] and st['symbols_C']==old['symbols_C'];e.emit(DEST/'stimulus.json',st)
 expected={}
 for group,folder in GROUPS.items():
  src=e.BUILD/folder/'plan.json';shutil.copy2(src,DEST/(group+'-plan.json'));plan=json.loads(src.read_text());expected[group]=sorted(c['name'] for c in plan if c.get('kind')!='dc');assert len(expected[group])==len(set(expected[group]))
 assert {k:len(v) for k,v in expected.items()}=={'baseline':45,'controls':11}
 paths=['receiver.py','contract.md','stimulus.json','baseline-plan.json','controls-plan.json']+[str(p.relative_to(DEST)) for p in (DEST/'execution-sources').glob('*.py')]
 m={'created':datetime.datetime.now().astimezone().isoformat(),'purpose':'Final global fairness correction: equal absolute0..8ns and5ps grid,448scored/64guard training bits; no route selection and no new electrical simulation. Earlier prototype and original v1 retained.','files':{p:e.sha(DEST/p) for p in paths},'execution_sha256':EXECUTION_SHA,'helper_run_sha256':e.EXECUTION_SHA,'expected_canonical_cases':expected,'source_electrical_frame_sha256':e.sha(e.BUILD/'matched-r2/stimulus.json'),'source_electrical_frame_rule':'Only RX training_scoring metadata/schema change; bits, Gray symbols, eta, circuit/energy/stress unchanged.'};e.emit(DEST/'manifest.json',m);return m

def verify():
 m=json.loads((DEST/'manifest.json').read_text())
 for n,h in m['files'].items():assert e.sha(DEST/n)==h,'v2 frozen source drift: '+n
 assert m['execution_sha256']==EXECUTION_SHA and m['helper_run_sha256']==e.EXECUTION_SHA,'Loaded execution identity changed; use a new work version'
 return m

def selection():
 m=verify();records=[];diagnostics={}
 for group,folder in GROUPS.items():
  expected=set(m['expected_canonical_cases'][group]);chosen={};seen=set();failures={}
  for p in sorted((e.BUILD/folder/'cases').glob('*/result.json')):
   r=json.loads(p.read_text());c=r['case']
   if c.get('kind')=='dc':continue
   key=c.get('retry_of',c['name']);assert key in expected,'Unplanned canonical case: '+key;seen.add(key)
   if r.get('simulation_ok') and r.get('metrics') and 'analysis_error' not in r:chosen[key]=p
   else:failures.setdefault(key,[]).append(str(p.relative_to(e.ROOT)))
  diagnostics[group]={'expected':len(expected),'successful_electrical_cases':len(chosen),'missing_electrical_case':sorted(expected-seen),'no_successful_electrical_case':sorted(expected-set(chosen)),'preserved_failed_attempts':failures}
  records += [(group,key,str(path)) for key,path in sorted(chosen.items())]
 return records,diagnostics

def binding(m,original,path,group,key):
 return {'analysis_version':VERSION,'group':group,'canonical_case':key,'source_result_sha256':e.sha(path),'source_gzip_sha256':original['gzip_sha256'],'v2_receiver_sha256':m['files']['receiver.py'],'v2_contract_sha256':m['files']['contract.md'],'v2_stimulus_sha256':m['files']['stimulus.json'],'analysis_execution_sha256':m['execution_sha256'],'helper_run_sha256':m['helper_run_sha256']}

def analyze_one(job):
 group,key,rpath=job;path=Path(rpath);original=json.loads(path.read_text());raw=path.with_name('waveform.dat.gz');m=verify();target=DEST/'cases'/group/original['case']['name'];out=target/'result.json';identity=binding(m,original,path,group,key)
 if out.exists():
  r=json.loads(out.read_text());assert all(r.get(k)==v for k,v in identity.items()),'Cached analysis binding mismatch';assert e.sha(raw)==identity['source_gzip_sha256'],'Cached gzip drift';return {'name':original['case']['name'],'cached':True,'group':group}
 assert e.sha(raw)==original['gzip_sha256'];assert original['metadata']['export_mode']=='native-led+native-energy-stress';assert original['metadata']['vectors']=={'iled_cond':1}
 a=np.loadtxt(raw,skiprows=1);assert len(a)==original['metrics']['sample_count'];receiver=e.module(DEST/'receiver.py','rx_v2_case');st=json.loads((DEST/'stimulus.json').read_text());rx=receiver.analyze(a[:,0],a[:,1],st,original['case']['route'],original['case']['net_rate_Gbps']);verify()
 result={**identity,'case':original['case'],'source_result':str(path.relative_to(e.ROOT)),'source_raw_sha256_recorded':original['raw_sha256'],'raw_hash_boundary':'Gzip bytes verified anew; original uncompressed SHA is recorded from the original round-trip verification, not newly independently rehashed.','native_samples':len(a),'original_energy_unchanged':True,'original_stress_unchanged':True,'receiver':rx,'communication_screen_passed':bool(original['metrics']['device_voltage_passed'] and rx['passed']),'old_v1_summary':{'passed':original['metrics']['receiver']['passed'],'errors':original['metrics']['receiver']['validation']['bit_errors'],'minimum_distance_uA':original['metrics']['receiver']['validation']['decision_distance_min_uA'],'minimum_time_ps':original['metrics']['receiver']['horizontal_margin']['min_ps'],'delay_s':original['metrics']['receiver']['sampling']['delay_s']}}
 e.emit(out,result);return {'name':original['case']['name'],'group':group,'errors':rx['validation']['bit_errors'],'margin_uA':rx['validation']['decision_distance_min_uA'],'time_ps':rx['horizontal_margin']['min_ps'],'delay_ns':rx['sampling']['delay_s']*1e9,'passed':rx['passed']}

def finalize():
 m=verify();jobs,diagnostics=selection();records=[];unanalysed=[];paths=set()
 for group,key,rpath in jobs:
  original=json.loads(Path(rpath).read_text());p=DEST/'cases'/group/original['case']['name']/'result.json'
  if not p.exists():unanalysed.append({'group':group,'canonical_case':key});continue
  r=json.loads(p.read_text());wanted=binding(m,original,Path(rpath),group,key);assert all(r.get(k)==v for k,v in wanted.items()),'Final binding drift';paths.add(p)
  records.append({'group':group,'canonical_case':key,'case':r['case']['name'],'path':str(p.relative_to(e.ROOT)),'sha256':e.sha(p),'passed':r['communication_screen_passed']})
 counts={g:sum(r['group']==g for r in records) for g in GROUPS};missing=[{'group':g,'canonical_case':k} for g,d in diagnostics.items() for k in d['no_successful_electrical_case']]
 summary={'manifest_sha256':e.sha(DEST/'manifest.json'),'analysis_execution_sha256':EXECUTION_SHA,'expected_counts':{k:len(v) for k,v in m['expected_canonical_cases'].items()},'counts':counts,'electrical_diagnostics':diagnostics,'unanalysed':unanalysed,'no_successful_electrical':missing,'records':records,'orphan_analysis_files_not_counted':[str(p.relative_to(e.ROOT)) for p in (DEST/'cases').glob('*/*/result.json') if p not in paths],'complete':not missing and not unanalysed and counts=={'baseline':45,'controls':11}}
 e.emit(DEST/'summary.json',summary);e.emit(e.ROOT/'evidence/fair-driver-v1/rx-equal-latency-v2-index.json',summary);return summary

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--jobs',type=int,default=2);ap.add_argument('--finalize',action='store_true');args=ap.parse_args();initialize();jobs,diagnostics=selection()
 with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as pool:
  for r in pool.map(analyze_one,jobs):print(json.dumps(r),flush=True)
 summary=finalize();print(json.dumps({'counts':summary['counts'],'complete':summary['complete'],'missing':summary['no_successful_electrical']}))
 if args.finalize:assert summary['complete'],'Cannot close the study with missing canonical v2 analyses'
if __name__=='__main__':main()
