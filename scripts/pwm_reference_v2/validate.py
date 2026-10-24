#!/usr/bin/env python3
"""Read-only hash audit and acceptance summary; does not rerun simulations."""
from pathlib import Path
import gzip,hashlib,json,re
import numpy as np
ROOT=Path(__file__).resolve().parents[2];W=ROOT/'build/pwm-reference-v2/20261024';E=ROOT/'evidence/pwm-reference-v2/20261024'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 network=json.loads((ROOT/'analog/pwm_reference_v2/final-network.json').read_text());selected_prefix=network.get('selected_prefix','c15');prefix=selected_prefix+'_';selected_cf=network.get('selected_filter_c_nf',15)
 rows=[];exceptions=[];failures=[];checks=0
 for p in sorted(W.glob('*/result.json')):
  d=json.loads(p.read_text());c=d.get('case')
  if not c:continue
  folder=p.parent;name=c['name'];assert sha(folder/'testbench.spice')==d['deck_sha256'];assert sha(folder/'ngspice.log')==d['log_sha256'];checks+=2
  sid=d['executed_runner_sha256'];assert sha(W/'inputs/executed_sources'/sid/'run.py')==sid;checks+=1
  mp=W/'inputs/manifests'/(d['source_manifest_sha256']+'.json');assert sha(mp)==d['source_manifest_sha256'];m=json.loads(mp.read_text());checks+=1
  for n,v in m['files'].items():assert sha(W/'inputs'/n)==v['sha256'];checks+=1
  ident=m['executed_runner_sha256']==sid
  if not ident:exceptions.append({'case':name,'case_runner':sid,'manifest_runner':m['executed_runner_sha256'],'excluded_from_final_acceptance':True,'note':'Historical mutable manifest index race; exact deck/log/input bytes and actual executed-runner bytes remain verified. Original record unchanged.'})
  if name.startswith(('n2rl_','damped_','c47_','c15_')):assert ident
  if d['completed']:
   fn='ac.dat.gz' if c['kind']=='ac' else 'waveform.dat.gz';gp=folder/fn;assert sha(gp)==d['gzip_sha256'];h=hashlib.sha256()
   with gzip.open(gp,'rb') as f:
    while b:=f.read(1024*1024):h.update(b)
   assert h.hexdigest()==d['raw_sha256'];checks+=2
  else:failures.append({'case':name,'failure':d.get('failure'),'log':str((folder/'ngspice.log').relative_to(ROOT))})
  rows.append(d)
 selected=[x for x in rows if x['case']['name'].startswith(prefix)];direct=[x for x in selected if not x['case']['name'].startswith('n2rl_dc_')]
 numeric=[]
 for an,bn,kind in [(prefix+'startup_fullmesh',prefix+'startup_fullmesh_trap','startup'),(prefix+'step',prefix+'step_fine','step')]:
  a=next((x for x in rows if x['case']['name']==an),None);b=next((x for x in rows if x['case']['name']==bn),None)
  if not a or not b or not a['completed'] or not b['completed']:numeric.append({'pair':[an,bn],'completed':False});continue
  if kind=='startup':
   delta=abs(a['held_peak_a']-b['held_peak_a']);dq=max(abs(a['held_charge'][k]-b['held_charge'][k]) for k in a['held_charge']);dr=abs(a['recovered_a']/b['recovered_a']-1);ok=delta<=2e-12 and dq<=4e-17 and dr<=.002;numeric.append(dict(pair=[an,bn],completed=True,held_peak_delta_a=delta,held_charge_max_delta_c=dq,recovered_current_relative_delta=dr,passed=ok))
  else:
   rel=max(abs(a[k]/b[k]-1) for k in ['current_min_a','current_max_a'])
   charges=[]
   for rr in [a,b]:
    with gzip.open(W/rr['case']['name']/'waveform.dat.gz') as f:z=np.loadtxt(f,skiprows=1)
    mask=z[:,0]>=10e-6;t=z[mask,0];di=z[mask,1]-rr['baseline_current_a'];charges.append([float(np.trapezoid(np.maximum(di,0),t)),float(np.trapezoid(np.minimum(di,0),t))])
   charge_relative=max(abs(charges[0][k]/charges[1][k]-1) for k in [0,1]);ds=abs(a['settle_s']-b['settle_s']) if a['settle_s'] is not None and b['settle_s'] is not None else None;numeric.append(dict(pair=[an,bn],completed=True,peak_relative_delta=rel,disturbance_positive_negative_charge_c=charges,disturbance_charge_relative_delta=charge_relative,settle_delta_s=ds,passed=rel<=.002 and charge_relative<=.002 and ds is not None and ds<=2e-9))
 loops=[];loop_audits=[]
 for p in sorted(W.glob('loop_*/result.json')):
  d=json.loads(p.read_text());sid=d['executed_source_sha256']
  if d.get('complete_source_identity'):
   hm=W/'inputs/manifests'/(d['source_manifest_sha256']+'.json');assert sha(hm)==d['source_manifest_sha256'];mm=json.loads(hm.read_text());assert mm['executed_runner_sha256']==d['helper_runner_sha256'];assert sha(W/'inputs/executed_sources'/d['helper_runner_sha256']/'run.py')==d['helper_runner_sha256']
   for n,v in mm['files'].items():assert sha(W/'inputs'/n)==v['sha256'];checks+=1
  assert sha(W/'inputs/executed_sources'/sid/'loop.py')==sid
  for r in d['records']:
   q=p.parent/r['method'];assert sha(q/'testbench.spice')==r['deck_sha256'];assert sha(q/'dut.spice')==r['dut_sha256'];assert sha(q/'ngspice.log')==r['log_sha256'];checks+=3
  if d.get('complete_source_identity'):
   av=np.loadtxt(p.parent/'voltage/ac.dat',skiprows=1);ai=np.loadtxt(p.parent/'current/ac.dat',skiprows=1);assert np.array_equal(av[:,0],ai[:,0]);tv=-(av[:,1]+1j*av[:,2])/(av[:,3]+1j*av[:,4]);ti=(ai[:,1]+1j*ai[:,2])/(ai[:,3]+1j*ai[:,4]);ratio=(tv*ti-1)/(tv+ti+2);gain=20*np.log10(abs(ratio));phase=np.unwrap(np.angle(ratio))*180/np.pi;derived=np.c_[av[:,0],gain,phase];csv=E/(d['name']+'.csv');assert np.allclose(np.loadtxt(csv,delimiter=',',skiprows=1),derived,rtol=1e-13,atol=1e-12)
   oi=[np.loadtxt(p.parent/m/'op.dat',skiprows=1) for m in ['voltage','current','closed']];delta=max(float(np.max(abs(v-oi[-1]))) for v in oi[:-1]);assert abs(delta-d['closed_injected_op_max_delta_v'])<1e-16
   crossing_indices=np.flatnonzero((gain[:-1]>=0)&(gain[1:]<0));assert len(crossing_indices)==len(d['crossings'])
   for k,c in zip(crossing_indices,d['crossings']):
    frequency=10**np.interp(0,[gain[k+1],gain[k]],[np.log10(av[k+1,0]),np.log10(av[k,0])]);pm=180+np.interp(0,[gain[k+1],gain[k]],[phase[k+1],phase[k]]);assert abs(frequency/c['frequency_hz']-1)<1e-13 and abs(pm-c['phase_margin_deg'])<1e-10
   paths=[p,csv]+list(p.parent.glob('*/*.dat'));loop_audits.append(dict(name=d['name'],helper_runner_sha256=d['helper_runner_sha256'],executed_source_sha256=sid,source_manifest_sha256=d['source_manifest_sha256'],files={str(f.relative_to(ROOT)):sha(f) for f in paths},csv_recomputed_from_two_injection_raw=True,op_delta_recomputed=True,crossings_recomputed=True));checks+=len(paths)+3
  loops.append(d)
 final_loops=[x for x in loops if x.get('n2_pin_package') and x.get('comp_damp_ohm')==10 and selected_cf*.89<=x.get('filter_c_nf',100)<=selected_cf*1.11 and x.get('complete_source_identity')]
 required=[prefix+n for n in ['dc','step','step_fine','fault','pwm','ac','startup_fullmesh','startup_fullmesh_trap','startup_ss_slow','startup_ff_fast']];byname={r['case']['name']:r for r in rows};missing=[n for n in required if n not in byname];dynamic=[r for r in selected if r['case']['name'].startswith(prefix+'dyn_')];accepted=not missing and len(dynamic)==12 and all(r.get('passed') for r in selected) and all(n.get('passed') for n in numeric) and len(final_loops)==3 and all(x['crossings'] and all(c['phase_margin_deg']>=60 for c in x['crossings']) for x in final_loops)
 out=dict(schema_version=1,selected_prefix=selected_prefix,selected_filter_c_nf=selected_cf,unexecuted_decks=[str(p.relative_to(ROOT)) for p in W.glob('*/testbench.spice') if not (p.parent/'result.json').exists()],selected_acceptance=accepted,selected_missing_required=missing,retained_completed_negative_controls=[{'case':r['case']['name'],'checks':r.get('checks')} for r in rows if r['completed'] and not r.get('passed')],hash_checks=checks,all_case_count=len(rows),selected_case_count=len(selected),selected_completed=sum(x['completed'] for x in selected),selected_passed=sum(x.get('passed',False) for x in selected),identity_exceptions=exceptions,retained_incomplete=failures,numerical_comparisons=numeric,final_loop_count=len(final_loops),final_loop_identity_audit=[x for x in loop_audits if x['name'] in {d['name'] for d in final_loops}],final_loops=[{k:x[k] for k in ['name','crossings','closed_injected_op_max_delta_v']} for x in final_loops],selected_incomplete_or_failed=[{'case':x['case']['name'],'completed':x['completed'],'checks':x.get('checks'),'failure':x.get('failure')} for x in selected if not x.get('passed')],limits='This validates reported SPICE evidence. It does not establish optical output, autonomous POR, full pad/ESD/package, physical PDK re-signoff, foundry reliability, silicon or tapeout readiness.')
 (E/'validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['hash_checks','all_case_count','selected_case_count','selected_completed','selected_passed','numerical_comparisons','selected_incomplete_or_failed']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
