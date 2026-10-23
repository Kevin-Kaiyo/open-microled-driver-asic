#!/usr/bin/env python3
"""Validate source identity, declared coverage, actual terminals and compressed raw evidence."""
import argparse,gzip,hashlib,json,math
from pathlib import Path
import formal
r=formal.r;ROOT=r.ROOT

def validate(work,raw=True):
 m=formal.verify(work);s=formal.summarize(work);base=json.loads((formal.OLD/'manifest.json').read_text());checks={}
 checks['common_contract_unchanged']=m['common']==base['common']
 checks['stimulus_unchanged']=r.sha(work/'stimulus.json')==r.sha(formal.OLD/'stimulus.json')
 checks['receiver_metrics_unchanged']=all(r.sha(work/'inputs/legacy'/f)==r.sha(formal.OLD/'inputs/legacy'/f) for f in ['metrics.py','analyze.py','run.py'])
 checks['all_declared_cases_analyzed']=s['completion']['all_planned_analyzed']
 coverage=[]
 for route in 'AB':
  for var in ['BEFORE','AFTER']:
   for kind,corner,temp,vdd in formal.CONDITIONS:
    rows=[x for x in s['rows'] if x['route']==route and x['variant']==var and x['kind']==kind]
    rates=sorted(x['rate_Gbps'] for x in rows);coverage.append({'route':route,'variant':var,'kind':kind,'rates_Gbps':rates,'complete':rates==r.RATES})
 checks['full_grid_complete']=all(c['complete'] for c in coverage)
 paths=list((work/'cases').glob('*/result.json'));waveforms={};case_checks=[];numerics=[]
 for rp in sorted(paths):
  result=json.loads(rp.read_text());ap=rp.with_name('analysis.json');analysis=json.loads(ap.read_text());c=result['case'];flags={}
  flags['deck_hash']=r.sha(rp.with_name('testbench.spice'))==result['deck_sha256']
  flags['analysis_ok']=analysis['analysis_ok'];flags['all_MOS_terminals_saved']=all(n=='0' or n in result['vectors'] for d in result['devices'] for n in d['nodes'])
  flags['MOS_count']=len(result['devices'])==(6 if c['route']=='A' else 9)
  flags['shared_case_contract']=all(c[k]==v for k,v in {'cap_F':2e-13,'r_pkg':1.,'l_pkg':5e-10,'edge_s':2e-11,'reltol':1e-5,'chgtol':1e-16}.items())
  if result.get('reuse'):
   flags['reuse_source_hash']=r.sha(ROOT/result['reuse']['original_result'])==result['reuse']['original_result_sha256']
   flags['reuse_analysis_hash']=r.sha(ROOT/result['reuse']['original_analysis'])==result['reuse']['original_analysis_sha256']
  else:
   flags['included_input_hashes']=all(r.sha(work/'inputs'/p)==h for p,h in result['input_identity'].items())
   flags['stimulus_hash']=result['stimulus_sha256']==m['stimulus_sha256']
   flags['all_passive_terminals_saved']=all(n=='0' or n in result['vectors'] for d in result.get('passives',[]) for n in d['nodes'])
  if 'transient' in analysis:
   energy=analysis['transient']['energy']['rail_plus_ideal_DATA_total'];flags['energy_identity']=math.isclose(energy['net_J'],energy['positive_draw_J']-energy['returned_J'],rel_tol=1e-10,abs_tol=1e-23)
   row=analysis['row'];flags['combined_screen_consistent']=row['combined_screen_passed']==(row['comparison_screen_passed'] and row['max_abs_terminal_V']<=3.63)
   if c['kind'].startswith('numerical_') or c['kind']=='integration_control':
    refs=[x for x in s['rows'] if x['route']==c['route'] and x['variant']==c['variant'] and x['rate_Gbps']==c['rate_Gbps'] and x['corner']==c['corner'] and x['temp_C']==c['temp_C'] and x['vdd_V']==c['vdd_V'] and x['kind'] in ['nominal','slow_hot','fast_cold']]
    if len(refs)!=1:raise ValueError('Missing unique numerical reference')
    ref=refs[0];energykey='rail_plus_DATA_positive_draw_fJ_per_gross_bit'
    numerics.append({'name':c['name'],'reference':ref['name'],'max_terminal_delta_V':row['max_abs_terminal_V']-ref['max_abs_terminal_V'],'energy_change_percent':100*(row[energykey]/ref[energykey]-1),'margin_delta':row['threshold_margin_normalized']-ref['threshold_margin_normalized'],'errors_changed':row['errors']!=ref['errors'],'joint_screen_changed':row['combined_screen_passed']!=ref['combined_screen_passed']})
  case_checks.append({'name':c['name'],'checks':flags,'passed':all(flags.values())});waveforms[result['waveform']]=result
 raw_checks=[]
 if raw:
  for name,result in sorted(waveforms.items()):
   p=ROOT/name;flags={'compressed_sha256':r.sha(p)==result['waveform_sha256']};h=hashlib.sha256();size=0
   with gzip.open(p,'rb') as f:
    for data in iter(lambda:f.read(1024**2),b''):h.update(data);size+=len(data)
   flags['uncompressed_sha256']=h.hexdigest()==result['uncompressed_sha256'];flags['uncompressed_size']=size==result['uncompressed_bytes'];raw_checks.append({'path':name,'checks':flags,'passed':all(flags.values())})
 checks['per_case_checks_passed']=all(c['passed'] for c in case_checks);checks['raw_archive_checks_passed']=all(c['passed'] for c in raw_checks) if raw else None
 out={'schema_version':1,'work':r.rel(work),'summary_sha256':r.sha(r.EVIDENCE/'summary.json'),'checks':checks,'coverage':coverage,'per_case':case_checks,'raw_checked':raw,'raw_archives':raw_checks,'numerical_controls':numerics,'counts':s['counts'],'passed':all(v for v in checks.values() if v is not None),'caution':'Passing validates declared experiment bookkeeping and finite sampled screens only; not foundry reliability, exhaustivePVT, opticalBER orsilicon.'}
 r.emit(r.EVIDENCE/'validation.json',out);r.emit(r.EVIDENCE/'numerical-controls.json',numerics);return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--work',required=True);p.add_argument('--no-raw',action='store_true');a=p.parse_args();out=validate(ROOT/a.work,not a.no_raw);print(json.dumps({'checks':out['checks'],'counts':out['counts'],'passed':out['passed']},indent=2));raise SystemExit(0 if out['passed'] else 1)
if __name__=='__main__':main()
