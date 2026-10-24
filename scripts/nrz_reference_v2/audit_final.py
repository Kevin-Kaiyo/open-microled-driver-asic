#!/usr/bin/env python3
"""Read-only final case identity/coverage audit and separated metric summaries."""
from pathlib import Path
import argparse,datetime,gzip,hashlib,json
import run as r
import validate as v
import final_v2 as f
def audit(work,deep=False):
 m=v.verify(work);checks=[];records=[];rows=[];planned={};stages={}
 for p in sorted(work.glob('plan-*.json')):
  data=json.loads(p.read_text());checks.append({'path':r.rel(p),'sha256':r.sha(p)})
  for c in data['cases']:
   assert c['name'] not in planned or planned[c['name']]==c
   planned[c['name']]=c;stages[c['name']]=p.stem.removeprefix('plan-')
 results={p.parent.name:p for p in (work/'cases').glob('*/result.json')}
 missing=sorted(set(planned)-set(results));extra=sorted(set(results)-set(planned))
 for name,p in sorted(results.items()):
  q=json.loads(p.read_text());folder=p.parent;assert name in planned and q['case']==planned[name]
  rec={'name':name,'result_sha256':r.sha(p),'stage':stages[name],'simulation_ok':q['simulation_ok']}
  assert r.sha(r.ROOT/q['runner_source'])==q['runner_source_sha256']
  assert r.sha(folder/'testbench.spice')==q['deck_sha256'];assert r.sha(r.ROOT/q['log'])==q['log_sha256']
  for path,h in q['input_identity'].items():assert r.sha(work/'inputs'/path)==h
  assert q['stimulus_sha256']==m['stimulus_sha256'];assert q['candidate_definition']==m['variants']['B']['REFERENCE']
  if q.get('waveform'):
   wave=r.ROOT/q['waveform'];assert r.sha(wave)==q['waveform_sha256'];rec['compressed_sha256']=q['waveform_sha256'];rec['compressed_bytes']=wave.stat().st_size
   if deep:
    h=hashlib.sha256();count=0
    with gzip.open(wave,'rb') as raw:
     for block in iter(lambda:raw.read(1024**2),b''):h.update(block);count+=len(block)
    assert h.hexdigest()==q['uncompressed_sha256'];assert count==q['uncompressed_bytes'];rec['deep_roundtrip_verified']=True
  output='startup-analysis.json' if stages[name]=='startup' else 'slow-analysis.json' if stages[name]=='slow' else 'analysis.json'
  ap=folder/output
  if ap.exists():
   a=json.loads(ap.read_text());row=dict(a['row']);row['stage']=stages[name];row['result_json']=r.rel(p);row['analysis_json']=r.rel(ap);row['case']=q['case'];rec['analysis_sha256']=r.sha(ap)
   for key in ['kind','route','corner','temp_C','vdd_V','rate_Gbps','dc_bit']:
    if key in q['case']:row.setdefault(key,q['case'][key])
   row['maximum_recorded_body_forward_V']=a.get('stress',{}).get('maximum_recorded_body_forward_V')
   if 'LED_current_error_percent' in row:row['current_target_passed']=abs(row['LED_current_error_percent'])<=5
   if 'rail_net_fJ_per_gross_bit' in row:row['rail_plus_DATA_net_fJ_per_gross_bit']=row['rail_net_fJ_per_gross_bit']+row['ideal_DATA_net_fJ_per_gross_bit']
   rows.append(row)
  else:rec['analysis_missing']=True
  records.append(rec)
 counts={'planned':len(planned),'results':len(results),'analyzed':len(rows),'simulation_failures':sum(not x['simulation_ok'] for x in records),'analysis_failures':sum(x.get('analysis_missing',False) for x in records)+sum(not x.get('analysis_ok',False) for x in rows),'DC_current_target_failures':sum(x.get('current_target_passed') is False for x in rows),'NRZ_receiver_failures':sum(x['stage']=='nrz' and x.get('comparison_screen_passed') is False for x in rows),'device_screen_failures':sum(x.get('device_specific_screen_passed',x.get('device_screen_passed',True)) is False for x in rows),'startup_contract_failures':sum(x.get('startup_passed') is False for x in rows),'slow_response_failures':sum(x.get('slow_passed') is False for x in rows)}
 amendment=json.loads((work/'budget-amendment.json').read_text()) if (work/'budget-amendment.json').exists() else None
 counts['administrative_interruptions']=len(amendment.get('administrative_records',[])) if amendment else 0
 ac=[]
 for path in sorted(r.BUILD.glob('vi-loop-*-final-r2*/result.json')):
  item=json.loads(path.read_text());folder=path.parent
  for record in item['records']:
   sub=folder/record['method'];assert r.sha(sub/'testbench.spice')==record['deck_sha256'];assert r.sha(sub/'core.spice')==record['core_sha256'];assert r.sha(sub/'ngspice.log')==record['log_sha256']
  ac.append({'path':r.rel(path),'sha256':r.sha(path),'case':item['case'],'crossings':item['crossings'],'op_max_delta':item['closed_injected_op_max_delta'],'loop_csv_sha256':r.sha(folder/'loop.csv')})
 result={'created':datetime.datetime.now().isoformat(),'work':r.rel(work),'manifest_sha256':r.sha(work/'manifest.json'),'scope':m['scope'],'budget_amendment':amendment,'rows':rows,'counts':counts,'coverage':{'missing':missing,'unplanned':extra,'stage_counts':{s:sum(x==s for x in stages.values()) for s in sorted(set(stages.values()))}},'AC_separate':{'count':len(ac),'expected':7,'rows':ac,'method':'localtwo-injectionestimate,notstrictTianallloops'},'identity_audit':{'all_checks_passed':not missing and not extra and len(rows)==len(planned) and len(ac)==7,'deep_gzip_roundtrip':deep,'records':records,'plans':checks,'audit_source_sha256':r.sha(__file__)},'interpretation':'Identity/coverage does not imply allfunction/current/devicepass. DC currenttarget,NRZreceiver,device,externalstartupcontract,slowresponse counted separately; expectednegativecontrols remain failures.'}
 result['qualification_limits']={'restart':'ResidualLED/reference RAWrestart meetsoriginalfunctional/six-pairabsolutevoltagecriteria but records0.746649V forwardbodyjunction. Junctioninjectioncurrent,latchup/SOA notquantified/closed; do not callrestartfullyqualified.','maximum_recorded_body_forward_V':max(x['maximum_recorded_body_forward_V'] or 0 for x in rows)}
 snapshot=work/'execution-sources'/('audit-'+r.sha(__file__)+'.py')
 if not snapshot.exists():snapshot.write_bytes(Path(__file__).read_bytes())
 r.emit(work/'summary-verified.json',result);r.emit(r.EVIDENCE/(work.name+'-summary-verified.json'),result);return result
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--deep',action='store_true');a=ap.parse_args();out=audit(f.WORK,a.deep);print(json.dumps({'counts':out['counts'],'coverage':out['coverage']},indent=2))
if __name__=='__main__':main()
