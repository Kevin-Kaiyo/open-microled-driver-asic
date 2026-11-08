#!/usr/bin/env python3
"""Append-only dynamic-load sensitivity, frozen schematic inputs, no route retuning.

Use build/layout/venv/bin/python scripts/microled_dynamic_v1/run.py --phase init|run|summary.
Reproduce: --phase reproduce --case TT-A-C200fF-S40 [--work build/.../reproduce-ID].
Frozen source snapshots and relative ngspice includes make each run restorable.
"""
from pathlib import Path
import argparse, concurrent.futures, datetime, gzip, hashlib, importlib.util, json, os, platform, re, shutil, subprocess, sys, tempfile, time
sys.dont_write_bytecode=True
import numpy as np
EXECUTION_SOURCE=Path(__file__).read_bytes()
EXECUTION_SHA=hashlib.sha256(EXECUTION_SOURCE).hexdigest()

ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'build/microled-dynamic-v1/electrical'
DEFAULT_WORK=STAGE/'run-r1'
EVIDENCE=ROOT/'evidence/microled-dynamic-v1'
ORIGINAL=ROOT/'build/fair-driver-v1/matched-r2'
DIAG=ROOT/'build/three-gbps-experiment-20261027/microled/run-r1'
NGSPICE=shutil.which('ngspice') or '/opt/homebrew/bin/ngspice'
EXPECTED={
 'route_a.spice':'02ba88d9b7654b68b11b4db15bd8bbf316271123c8d377944335602763657a53',
 'route_b.spice':'9572b2bc5f659391c48d3a69d3ab84cef8a2eebc37e582437803c2ddebd3c3c7',
 'route_c.spice':'096ecd179eadf8193896b6c1177d845c666bbe93903ccf5a99020593c6da8b1d',
 'common.spice':'280abc05195bc5ddc665379023999b55f4ec4a29d007eabd87c2f5ed9cc03fc8',
 'led.spice':'51dabe11ee4a3fbbb7bf387e422eaa4faa0203d149a3c5701ab1dfaeba9734cc',
 'pdk/design.ngspice':'091cb530bf85160a1f07878fb81f789ca367d018991c8ab41a584cd1a85c6692',
 'pdk/sm141064.ngspice':'677822db50bf8968f77854bb455006ac5c245deb46ecfc8b352934e752135c46'}

def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def emit(path,value):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(p)

def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def plan():
 cases=[]
 # First three are the historical200fF anchor, all routes treated alike.
 for cap in [200,0,10,50,800]:
  for r in 'ABC':cases.append(dict(name=f'TT-{r}-C{cap}fF-S40',route=r,corner='typical',temp_C=27,vdd_V=3.3,led_cap_F=cap*1e-15,net_rate_Gbps=3.2,steps_per_symbol=40,timeout_s=900,group='TT_capacitance'))
 for cap in [200,10]:
  for r in 'ABC':
   for level in range(4 if r=='C' else 2):cases.append(dict(name=f'DC-TT-{r}-C{cap}fF-L{level}',kind='dc',route=r,corner='typical',temp_C=27,vdd_V=3.3,led_cap_F=cap*1e-15,level=level,timeout_s=900,group='DC_calibration'))
 for cap in [200,10]:
  for r in 'ABC':cases.append(dict(name=f'TT-{r}-C{cap}fF-S80',route=r,corner='typical',temp_C=27,vdd_V=3.3,led_cap_F=cap*1e-15,net_rate_Gbps=3.2,steps_per_symbol=80,timeout_s=900,group='half_step'))
 for label,corner,temp,vdd in [('SS','ss',125,2.95),('FF','ff',-40,3.65)]:
  for cap in [200,10]:
   for r in 'ABC':cases.append(dict(name=f'{label}-{r}-C{cap}fF-S40',route=r,corner=corner,temp_C=temp,vdd_V=vdd,led_cap_F=cap*1e-15,net_rate_Gbps=3.2,steps_per_symbol=40,timeout_s=900,group='PVT_sensitivity'))
 return cases

def verify(work):
 m=json.loads((work/'manifest.json').read_text())
 for name,value in m['inputs'].items():assert sha(work/'inputs'/name)==value,'Frozen input drift '+name
 for name,value in m['source_snapshots'].items():assert sha(work/'execution-sources'/name)==value,'Frozen source drift '+name
 assert sha(work/'stimulus.json')==m['stimulus_sha256']
 assert sha(work/'plan.json')==m['plan_sha256']
 return m

def initialize(work):
 work=Path(work).resolve();assert work.is_relative_to(STAGE.resolve())
 if (work/'manifest.json').exists():return verify(work)
 assert not work.exists(),'Refuse partial/existing work '+str(work)
 # Both input identities are checked independently; never use an old absolute path in a deck.
 old=json.loads((ORIGINAL/'manifest.json').read_text())
 for parent in [ORIGINAL,DIAG]:
  pm=json.loads((parent/'manifest.json').read_text())
  for name,want in pm['inputs'].items():assert sha(parent/'inputs'/name)==want,'Parent input drift '+str(parent/name)
  assert sha(parent/'stimulus.json')==pm['stimulus_sha256']
  for name,want in EXPECTED.items():assert pm['inputs'][name]==want
 assert old['parameters']==json.loads((DIAG/'manifest.json').read_text())['parameters']
 work.mkdir(parents=True);dest=work/'inputs';dest.mkdir();snaps=work/'execution-sources';snaps.mkdir()
 for name,want in EXPECTED.items():
  out=dest/name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ORIGINAL/'inputs'/name,out);assert sha(out)==want
 source_files={'wrapper.py':Path(__file__),'legacy_engine.py':ROOT/'scripts/fair_driver_v1/run.py','receiver_equal_latency_v2.py':ROOT/'scripts/fair_driver_v1/receiver_equal_latency_v2.py','circuits.py':ROOT/'scripts/fair_driver_v1/circuits.py','microled_diagnosis.py':ROOT/'scripts/three_gbps_experiment/microled_diagnosis.py'}
 for name,src in source_files.items():shutil.copy2(src,snaps/name)
 shutil.copy2(snaps/'receiver_equal_latency_v2.py',dest/'receiver.py')
 assert sha(dest/'receiver.py')==json.loads((DIAG/'manifest.json').read_text())['inputs']['receiver.py']
 rx=module(dest/'receiver.py','dynamic_rx_initialize');stim=rx.make_stimulus()
 assert stim['bits']==json.loads((ORIGINAL/'stimulus.json').read_text())['bits'] and stim['eta']==32/37
 emit(work/'stimulus.json',stim);emit(work/'plan.json',plan())
 m={**old,'schema':'microled-dynamic-electrical-v1','created':datetime.datetime.now().astimezone().isoformat(),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'inputs':{name:sha(dest/name) for name in [*EXPECTED,'receiver.py']},'source_snapshots':{p.name:sha(p) for p in snaps.iterdir()},'stimulus_sha256':sha(work/'stimulus.json'),'plan_sha256':sha(work/'plan.json'),'parent_identities':{str(p.relative_to(ROOT)):sha(p/'manifest.json') for p in [ORIGINAL,DIAG]},'ngspice_version':subprocess.check_output([NGSPICE,'--version'],text=True),'execution_environment':{'Python':sys.version,'NumPy':np.__version__,'platform':platform.platform()},'execution':{'jobs_maximum':2,'timeout_s':900,'relative_include_paths':True,'native_sample_export':True,'compression':'gzip level5; decompressed SHA256 checked before deleting this-stage text raw'},'assumptions':{'LED_static_source':'Lin et al.2026 / Zenodo10.5281/zenodo.20034288;20um square yellow InGaN on diamond; source temperature unspecified','LED_static_IV':EXPECTED['led.spice'],'LED_C_fF':[0,10,50,200,800],'C_status':'constant parallel capacitance sensitivity assumption, not measured device capacitance','package_R_ohm':1.,'package_L_H':.5e-9,'driver_parameters':'Original matched-r2 TT single calibration, no new fitting or per-corner tuning','RX':'Frozen v2 historical result only here; independent dynamic-family offline analysis consumes identical conduction current','rates':{'net_Gbps':3.2,'line_Gbps':3.7,'payload_bits':4096,'frame_bits':4736,'eta':32/37},'energy':'Native seven-port source power -V*I; positive delivered, returned magnitude and signed net separately; divide full-frame energy by4096 attempted payload bits. No RX/sourceIC/host/clock internal energy.','physical_level':'New schematic transistor simulation only, no inherited layout/PEX/silicon/optical qualification'}}
 emit(work/'manifest.json',m);return m

def engine(work):
 e=module(work/'execution-sources/legacy_engine.py','dynamic_frozen_engine');e.ROOT=ROOT;return e

def deck(work,case):
 e=engine(work);text,meta=e.deck(work,case)
 # Instrumentation only: keep native solve and native energy/stress calculations.
 if case.get('kind')!='dc':
  extra=[('led_a','v(led_a)'),('led_k','v(led_k)'),('out','v(out)'),('pk','v(pk)'),('vin','v(vin)'),('vdd','v(vdd)'),('vref','v(vref)')]
  needle='wrdata waveform.dat i(VSENSE)\n';assert needle in text
  text=text.replace(needle,'wrdata waveform.dat i(VSENSE) '+' '.join(v for n,v in extra)+'\n')
  meta['vectors']={'iled_cond':1,**{n:k+2 for k,(n,v) in enumerate(extra)}}
 text=text.replace(str(work/'inputs'),'../../inputs')
 assert str(ROOT) not in text,'Deck must be independently restorable'
 meta['voltage_definitions']={'LED_terminal_V':'led_a-led_k','package_V':'led_k-out','package_R_V':'led_k-pk','package_L_V':'pk-out'}
 meta['current_definition']='i(VSENSE) = static LED conduction branch only; parallel CLED displacement current excluded'
 return text,meta

def compress(raw):
 before=sha(raw);out=raw.with_suffix(raw.suffix+'.gz')
 with raw.open('rb') as src,gzip.open(out,'wb',compresslevel=5) as dst:shutil.copyfileobj(src,dst)
 with gzip.open(out,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==before,'gzip roundtrip mismatch'
 rec={'raw_sha256':before,'gzip_sha256':sha(out),'gzip_bytes':out.stat().st_size,'raw_bytes':raw.stat().st_size,'gzip_roundtrip_verified':True}
 raw.unlink();return rec

def run_one(work,case,folder=None):
 verify(work);folder=folder or work/'cases'/case['name'];result_path=folder/'result.json'
 if result_path.exists():
  r=json.loads(result_path.read_text());assert r['case']==case
  if (folder/'waveform.dat.gz').exists():assert sha(folder/'waveform.dat.gz')==r['gzip_sha256']
  return r
 assert not folder.exists(),'Refuse partial case overwrite: '+str(folder)
 assert shutil.disk_usage(work).free>10*1024**3,'Storage guard10GiB'
 folder.mkdir(parents=True);text,meta=deck(work,case);(folder/'testbench.spice').write_text(text);emit(folder/'case.json',case)
 execution_path=work/'execution-sources'/('runner-'+EXECUTION_SHA+'.py')
 if not execution_path.exists():
  with tempfile.NamedTemporaryFile(dir=execution_path.parent,prefix='.runner-',suffix='.tmp',delete=False) as f:
   f.write(EXECUTION_SOURCE);temporary=Path(f.name)
  temporary.replace(execution_path)
 assert sha(execution_path)==EXECUTION_SHA,'Execution source snapshot drift'
 start=time.time();timed_out=False
 try:
  proc=subprocess.run([NGSPICE,'-b','testbench.spice'],cwd=folder,capture_output=True,text=True,timeout=case.get('timeout_s',900));output=proc.stdout+proc.stderr;code=proc.returncode
 except subprocess.TimeoutExpired as err:
  timed_out=True;output='TIMEOUT after '+str(case.get('timeout_s',900))+'s\n'+''.join(x.decode(errors='replace') if isinstance(x,bytes) else (x or '') for x in [err.stdout,err.stderr]);code=None
 (folder/'ngspice.log').write_text(output);raw=folder/'waveform.dat'
 rec={'case':case,'metadata':meta,'runner_sha256':EXECUTION_SHA,'runner_source_path':str(execution_path.relative_to(work)),'frozen_runner_sha256':verify(work)['source_snapshots']['wrapper.py'],'deck_sha256':sha(folder/'testbench.spice'),'exit_code':code,'timed_out':timed_out,'simulation_elapsed_s':time.time()-start,'simulation_ok':code==0 and raw.exists(),'manifest_sha256':sha(work/'manifest.json')}
 if rec['simulation_ok']:
  try:
   rec['metrics']=engine(work).evaluate(raw,meta,case,work)
   rec['metrics']['receiver_scope']='Historical unchanged v2 two-pole screen only; dynamic sensitivity family is evaluated independently offline'
   if case.get('kind')!='dc':
    a=np.loadtxt(raw,skiprows=1,ndmin=2);v=meta['vectors'];t=a[:,0]
    assert np.isfinite(a).all() and np.all(np.diff(t)>0)
    assert abs(t[-1]-meta['frame_duration_s'])<max(1e-15,meta['frame_duration_s']*1e-10),'Truncated native frame'
    rec['native_time']={'first_s':float(t[0]),'last_s':float(t[-1]),'max_step_ps':float(np.diff(t).max()*1e12),'strictly_increasing':True,'rows':len(t)}
    obs={n:a[:,v[n]] for n in ['iled_cond','led_a','led_k','out','pk','vin','vdd','vref']};obs.update(LED_terminal_V=obs['led_a']-obs['led_k'],package_V=obs['led_k']-obs['out'],package_R_V=obs['led_k']-obs['pk'],package_L_V=obs['pk']-obs['out'])
    rec['observables']={n:{'min':float(x.min()),'max':float(x.max()),'mean_time_weighted':float(np.trapezoid(x,t)/(t[-1]-t[0]))} for n,x in obs.items()}
  except Exception as err:rec['analysis_error']=repr(err)
 if raw.exists():rec.update(compress(raw))
 rec['elapsed_s']=time.time()-start;emit(result_path,rec);return rec

def summary(work):
 manifest=verify(work);records=[];missing=[];failures=[];dc=[]
 for case in json.loads((work/'plan.json').read_text()):
  p=work/'cases'/case['name']/'result.json'
  if not p.exists():missing.append(case['name']);continue
  r=json.loads(p.read_text());m=r.get('metrics',{});rec={'name':case['name'],'case':case,'route':case['route'],'group':case['group'],'result_path':str(p.relative_to(ROOT)),'waveform_path':str(p.with_name('waveform.dat.gz').relative_to(ROOT)) if r.get('gzip_sha256') else None,'result_sha256':sha(p),'raw_sha256':r.get('raw_sha256'),'gzip_sha256':r.get('gzip_sha256'),'deck_sha256':r['deck_sha256'],'runner_sha256':r['runner_sha256'],'runner_source_path':r.get('runner_source_path','execution-sources/wrapper.py' if r['runner_sha256']==manifest['source_snapshots']['wrapper.py'] else None),'simulation_ok':r['simulation_ok'],'analysis_error':r.get('analysis_error'),'elapsed_s':r['elapsed_s'],'metadata':r['metadata'],'metrics':m,'native_time':r.get('native_time'),'observables':r.get('observables')};records.append(rec)
  if not r['simulation_ok'] or 'analysis_error' in r:failures.append({'name':case['name'],'result_path':rec['result_path'],'timed_out':r['timed_out'],'exit_code':r['exit_code'],'analysis_error':r.get('analysis_error')})
  elif case.get('kind')=='dc':dc.append({'name':case['name'],'route':case['route'],'level':case['level'],'C_fF':case['led_cap_F']*1e15,'current_uA':m['i_led_A']*1e6,'target_uA':m['target_A']*1e6,'error_percent':m['current_error_percent'],'device_voltage_passed':m['device_voltage_passed']})
 checks=[]
 for r in 'ABC':
  for level in range(4 if r=='C' else 2):
   pair=[d for d in dc if d['route']==r and d['level']==level]
   if len(pair)==2:checks.append({'route':r,'level':level,'C200_minus_C10_current_uA':pair[0]['current_uA']-pair[1]['current_uA'],'DC_cap_invariance_passed':abs(pair[0]['current_uA']-pair[1]['current_uA'])<1e-6})
 out={'schema':'microled-dynamic-electrical-registry-v1','report_generator_sha256':EXECUTION_SHA,'created':datetime.datetime.now().astimezone().isoformat(),'work_path':str(work.relative_to(ROOT)),'manifest_sha256':sha(work/'manifest.json'),'assumptions':manifest['assumptions'],'parameters':manifest['parameters'],'input_sha256':manifest['inputs'],'semantic_input_sha256':{n:h for n,h in manifest['inputs'].items() if '__pycache__' not in n},'derived_cache_sha256':{n:h for n,h in manifest['inputs'].items() if '__pycache__' in n},'source_sha256':manifest['source_snapshots'],'records':records,'dc':dc,'dc_capacitance_checks':checks,'planned':len(plan()),'completed':len(records),'missing':missing,'failures':failures,'stage_status':'complete' if not missing and not failures else 'in_progress_or_blocked','limits':['Schematic transistor+synthetic parallel capacitance only; no measured dynamic LED/optical response.','TT/SS/FF changes MOS/resistor corners and temperature; static measured LED IV has no fitted temperature model.','Native7-port positive/returned/net full-frame energy is normalized by attempted4096payload bits, independent of RX pass/fail.','MOS pair-voltage stress screen only; no lifetime/reliability qualification.']}
 previous_path=work/'summary.json'
 if previous_path.exists():
  previous=json.loads(previous_path.read_text())
  if {k:v for k,v in previous.items() if k!='created'}=={k:v for k,v in out.items() if k!='created'}:out['created']=previous['created']
 emit(work/'summary.json',out)
 if work.resolve()==DEFAULT_WORK.resolve():
  emit(EVIDENCE/'electrical-registry.json',out)
  emit(EVIDENCE/'electrical-summary.json',{k:v for k,v in out.items() if k!='records'}|{'records':[{k:v for k,v in r.items() if k not in ['metadata','metrics']}|{'total_energy':r['metrics'].get('total_energy'),'energy_ports':r['metrics'].get('energy'),'device_voltage_passed':r['metrics'].get('device_voltage_passed'),'max_body_forward_V':r['metrics'].get('max_body_forward_V')} for r in records]})
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['init','run','summary','reproduce'],required=True);ap.add_argument('--work',type=Path);ap.add_argument('--only',default='');ap.add_argument('--case');ap.add_argument('--jobs',type=int,default=2);a=ap.parse_args();assert 1<=a.jobs<=2
 work=(a.work or DEFAULT_WORK).resolve()
 if a.phase=='reproduce':
  assert a.case,'--case required';source=DEFAULT_WORK;verify(source)
  work=(a.work or STAGE/('reproduce-'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S'))).resolve();assert work.is_relative_to(STAGE.resolve()) and not work.exists()
  work.mkdir(parents=True)
  for name in ['inputs','execution-sources']:shutil.copytree(source/name,work/name)
  for name in ['manifest.json','stimulus.json','plan.json']:shutil.copy2(source/name,work/name)
  case=next(c for c in plan() if c['name']==a.case);r=run_one(work,case);emit(work/'reproduction.json',{'source_work':str(source.relative_to(ROOT)),'source_result_sha256':sha(source/'cases'/case['name']/'result.json'),'raw_SHA256_matches':r.get('raw_sha256')==json.loads((source/'cases'/case['name']/'result.json').read_text()).get('raw_sha256'),'deck_SHA256_matches':r['deck_sha256']==json.loads((source/'cases'/case['name']/'result.json').read_text())['deck_sha256'],'result':r});print(json.dumps({'work':str(work.relative_to(ROOT)),'simulation_ok':r['simulation_ok'],'analysis_error':r.get('analysis_error'),'current_uA':r.get('metrics',{}).get('i_led_A',0)*1e6,'elapsed_s':r['elapsed_s']}))
  if not r['simulation_ok'] or r.get('analysis_error'):raise SystemExit('Reproduction failed; retain result and logs')
  return
 initialize(work)
 if a.phase=='init':summary(work);print(json.dumps({'work':str(work.relative_to(ROOT)),'planned':len(plan()),'manifest_sha256':sha(work/'manifest.json')}));return
 if a.phase=='summary':
  s=summary(work);print(json.dumps({k:s[k] for k in ['planned','completed','missing','failures','stage_status']}));return
 selected=[c for c in plan() if (a.only in c['name'] and (not a.case or a.case==c['name']))]
 assert selected,'No selected cases; check --only/--case'
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
  futures={pool.submit(run_one,work,c):c for c in selected}
  for fut in concurrent.futures.as_completed(futures):
   c=futures[fut]
   try:
    r=fut.result();m=r.get('metrics',{});print(json.dumps({'name':c['name'],'simulation_ok':r['simulation_ok'],'elapsed_s':round(r['elapsed_s'],2),'analysis_error':r.get('analysis_error'),'mean_current_uA':m.get('mean_LED_current_A',m.get('i_led_A',0))*1e6,'positive_pJ_per_attempted_payload_bit':m.get('total_energy',{}).get('positive_pJ_per_payload_bit'),'device_voltage_passed':m.get('device_voltage_passed')}),flush=True)
   except Exception as err:print(json.dumps({'name':c['name'],'wrapper_error':repr(err)}),flush=True)
   summary(work)
 final=summary(work);selected_names={c['name'] for c in selected}
 bad=[r['name'] for r in final['records'] if r['name'] in selected_names and (not r['simulation_ok'] or r.get('analysis_error'))]+[n for n in final['missing'] if n in selected_names]
 if bad:raise SystemExit('Selected cases incomplete or failed: '+','.join(bad))
if __name__=='__main__':main()
