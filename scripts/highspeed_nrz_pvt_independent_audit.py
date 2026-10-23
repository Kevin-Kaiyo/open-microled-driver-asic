#!/usr/bin/env python3
"""Independent delivery audit: frozen contract, grid set logic, raw energy/stress.

No SPICE is executed. Power integration and stress arithmetic below are locally
implemented rather than calling the production integrator. Receiver filtering
uses the exact frozen baseline filter; only fixed-sample decisions are recalculated.
"""
from pathlib import Path
import hashlib,importlib.util,itertools,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'build/highspeed-nrz-pvt/final-r4';BASE=ROOT/'build/highspeed-nrz-pex/run-0m3zyewc';OUT=ROOT/'evidence/highspeed-nrz-pvt/independent-audit.json'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return str(p.relative_to(ROOT))
def module(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m

def integrate(t,p,start,end):
 # Same saved-sample PWL-power convention. Integrate signed segments analytically,
 # splitting positive/negative triangles exactly at their zero crossing.
 mask=(t>start)&(t<end);tt=np.r_[start,t[mask],end];pp=np.r_[np.interp(start,t,p),p[mask],np.interp(end,t,p)]
 h=np.diff(tt);a=pp[:-1];b=pp[1:];net=float(np.sum(.5*(a+b)*h));draw=0.;returned=0.
 pos=(a>=0)&(b>=0);neg=(a<=0)&(b<=0);draw+=float(np.sum(.5*(a[pos]+b[pos])*h[pos]));returned+=float(np.sum(-.5*(a[neg]+b[neg])*h[neg]))
 cross=(a*b)<0
 for aa,bb,hh in zip(a[cross],b[cross],h[cross]):
  positive=max(aa,bb);negative=min(aa,bb);slope_abs=abs(bb-aa)/hh
  draw+=.5*positive**2/slope_abs;returned+=.5*negative**2/slope_abs
 assert abs(net-(draw-returned))<1e-22
 return {'draw_J':draw,'returned_J':returned,'net_J':net}

def main():
 summary=json.loads((ROOT/'evidence/highspeed-nrz-pvt/summary.json').read_text());manifest=json.loads((WORK/'manifest.json').read_text());baseline=json.loads((BASE/'manifest.json').read_text())
 checks={};frozen=['legacy/run.py','legacy/metrics.py','legacy/analyze.py','led.spice','pdk/design.ngspice','pdk/sm141064.ngspice']
 hashes={p:{'final':sha(WORK/'inputs'/p),'baseline':sha(BASE/'inputs'/p)} for p in frozen}
 checks['byte_identical_contract_files']=all(x['final']==x['baseline']for x in hashes.values());checks['byte_identical_stimulus']=sha(WORK/'stimulus.json')==sha(BASE/'stimulus.json');checks['same_common_contract']=manifest['common']==baseline['common']
 corechecks={}
 for rt in 'AB':
  for var in ['BEFORE','AFTER']:
   definition=manifest['variants'][rt][var];path=WORK/'inputs'/definition['path'];corechecks[rt+'/'+var]=sha(path)==definition['sha256']
 checks['core_hashes']=all(corechecks.values())
 rows=[r for r in summary['rows'] if r['kind']in['nominal','slow_hot','fast_cold'] and r['variant']in['BEFORE','AFTER']]
 rates=[.1,.25,.5,1,2,4,8];kinds=['nominal','slow_hot','fast_cold'];expected=set(itertools.product('AB',['BEFORE','AFTER'],kinds,rates));got=[(r['route'],r['variant'],r['kind'],r['rate_Gbps'])for r in rows]
 checks['main_grid_84_exact_unique']=len(got)==84 and len(set(got))==84 and set(got)==expected
 rows_by={g:r for g,r in zip(got,rows)};c_contract=[];sourcechecks=[]
 for r in rows:
  p=ROOT/r['result_json'];result=json.loads(p.read_text());a=json.loads((ROOT/r['analysis_json']).read_text());case=result['case'];cond={'nominal':('typical',27,3.3),'slow_hot':('ss',125,3),'fast_cold':('ff',-40,3.6)}[r['kind']]
  flags={'result_success':result['simulation_ok'],'analysis_success':a['analysis_ok'],'conditions':(case['corner'],case['temp_C'],case['vdd_V'])==cond,'load_fixed':case['cap_F']==200e-15 and case['r_pkg']==1 and case['l_pkg']==.5e-9 and case['edge_s']==20e-12,'deck_hash':sha(p.parent/'testbench.spice')==result['deck_sha256']}
  if r['route']=='B':
   deck=(p.parent/'testbench.spice').read_text();wanted='vdd' if r['variant']=='BEFORE' else 'vdummy'
   flags['reference_source']=f'RREF_EXT {wanted} bias 88386.1064910889' in deck
   flags['all_supply_ports_accounted']=set(result['rails'])=={'VLED','VDD','VDUMMY'}
  else:flags['all_supply_ports_accounted']=set(result['rails'])=={'VLED','VDD','VH','VL'}
  sourcechecks.append({'case':r['name'],'result_sha256':sha(p),'flags':flags})
 checks['all_main_case_contracts']=all(all(x['flags'].values())for x in sourcechecks)
 sets=[]
 for rt in 'AB':
  for var in ['BEFORE','AFTER']:
   entry={'route':rt,'variant':var,'per_condition':{},'all_three_joint_pass_rates_Gbps':[]}
   for kind in kinds:
    rx=[f for f in rates if rows_by[rt,var,kind,f]['comparison_screen_passed']];joint=[f for f in rx if rows_by[rt,var,kind,f]['max_abs_terminal_V']<=3.63]
    entry['per_condition'][kind]={'receiver_pass_rates_Gbps':rx,'receiver_and_stress_pass_rates_Gbps':joint}
   entry['all_three_joint_pass_rates_Gbps']=[f for f in rates if all(f in entry['per_condition'][k]['receiver_and_stress_pass_rates_Gbps']for k in kinds)]
   entry['highest_joint_discrete_pass_Gbps']=max(entry['all_three_joint_pass_rates_Gbps'],default=None);sets.append(entry)
 comparisons=[]
 for rt,f in [('A',1),('B',.5)]:
  for kind in kinds:
   b=rows_by[rt,'BEFORE',kind,f];a=rows_by[rt,'AFTER',kind,f];k='rail_plus_DATA_positive_draw_fJ_per_gross_bit'
   comparisons.append({'route':rt,'rate_Gbps':f,'condition':kind,'before':{z:b[z]for z in ['errors','threshold_margin_normalized','timing_min_margin_ui','max_abs_terminal_V',k]},'after':{z:a[z]for z in ['errors','threshold_margin_normalized','timing_min_margin_ui','max_abs_terminal_V',k]},'positive_draw_change_percent':100*(a[k]/b[k]-1),'after_voltage_screen_headroom_mV':(3.63-a['max_abs_terminal_V'])*1000})
 cross_route=[]
 for var,kind in itertools.product(['BEFORE','AFTER'],kinds):
  ab={rt:rows_by[rt,var,kind,.5] for rt in 'AB'};energy='rail_plus_DATA_positive_draw_fJ_per_gross_bit'
  cross_route.append({'variant':var,'condition':kind,'common_rate_Gbps':.5,'A':{k:ab['A'][k]for k in ['comparison_screen_passed','max_abs_terminal_V',energy]},'B':{k:ab['B'][k]for k in ['comparison_screen_passed','max_abs_terminal_V',energy]},'B_minus_A_positive_draw_percent':100*(ab['B'][energy]/ab['A'][energy]-1),'both_receiver_and_voltage_screens_pass':all(z['comparison_screen_passed'] and z['max_abs_terminal_V']<=3.63 for z in ab.values())})
 metrics=module(WORK/'inputs/legacy/metrics.py','metrics');analyzer=module(WORK/'inputs/legacy/analyze.py','independent_raw_loader');analyzer.ROOT=ROOT;stim=json.loads((WORK/'stimulus.json').read_text());rawchecks=[]
 for kind in ['nominal','slow_hot']:
  row=rows_by['B','AFTER',kind,.5];rp=ROOT/row['result_json'];result=json.loads(rp.read_text());record=json.loads((ROOT/row['analysis_json']).read_text());trace,source=analyzer.load_trace(result,rp);t=trace[:,0];vec=result['vectors'];ui=2e-9;start=stim['validation_start_bit']*ui;end=stim['validation_end_bit']*ui
  ports={}
  for name,rail in result['rails'].items():ports[name]=integrate(t,-rail['voltage_V']*trace[:,vec[name.lower()+'_current']],start,end)
  ports['DATA']=integrate(t,-trace[:,vec['data']]*trace[:,vec['data_current']],start,end)
  total={k:sum(z[k]for z in ports.values()) for k in ['draw_J','returned_J','net_J']};decl=record['transient']['energy']['rail_plus_ideal_DATA_total']
  delta={'draw_fJ_per_bit':(total['draw_J']/511-decl['positive_draw_J_per_gross_bit'])*1e15,'returned_fJ_per_bit':(total['returned_J']/511-decl['returned_J_per_gross_bit'])*1e15,'net_fJ_per_bit':(total['net_J']/511-decl['net_J_per_gross_bit'])*1e15}
  nv=lambda n:np.zeros(len(t))if n=='0'else trace[:,vec[n]]
  stress=0.;worst=None
  for dev in result['devices']:
   dd,gg,ss,bb=[nv(n)for n in dev['nodes']]
   for name,value in {'VGS':gg-ss,'VGD':gg-dd,'VGB':gg-bb,'VDS':dd-ss,'VDB':dd-bb,'VSB':ss-bb}.items():
    maximum=float(np.max(abs(value)))
    if maximum>stress:stress=maximum;worst={'instance':dev['instance'],'pair':name}
  rx=metrics.receiver_proxy(t,trace[:,vec['iled_cond']])['receiver_proxy_A'];sm=record['transient']['sampler'];bits=np.array(stim['validation_bits']);samples=np.interp(start+np.arange(len(bits))*ui+sm['sample_delay_s'],t,rx)
  errors=int(np.sum((samples>=62.5e-6)!=bits));margin=float(min(min(samples[bits==1])-62.5e-6,62.5e-6-max(samples[bits==0]))/75e-6)
  flags={'energy_matches':max(abs(x)for x in delta.values())<1e-8,'stress_matches':abs(stress-row['max_abs_terminal_V'])<1e-12,'fixed_sample_decisions_match':errors==row['errors'] and abs(margin-row['threshold_margin_normalized'])<1e-12}
  flags={k:bool(v)for k,v in flags.items()}
  rawchecks.append({'case':row['name'],'source':source,'ports_energy_J':ports,'total_fJ_per_gross_bit':{k.removesuffix('_J'):v/511*1e15 for k,v in total.items()},'energy_delta_from_pipeline_fJ_per_bit':delta,'independent_max_terminal_V':stress,'worst':worst,'independent_fixed_sample_errors':errors,'independent_fixed_sample_margin':margin,'flags':flags})
 checks['selected_raw_recalculation']=all(all(r['flags'].values())for r in rawchecks)
 numerical=[];byname={x['name']:x for x in summary['rows']}
 declared=json.loads((ROOT/'evidence/highspeed-nrz-pvt/numerical-controls.json').read_text())
 for control in declared:
  a=byname[control['name']];b=byname[control['reference']];ek='rail_plus_DATA_positive_draw_fJ_per_gross_bit'
  pct=100*(a[ek]/b[ek]-1);same=(a['errors']==b['errors'] and (a['comparison_screen_passed'] and a['max_abs_terminal_V']<=3.63)==(b['comparison_screen_passed'] and b['max_abs_terminal_V']<=3.63))
  numerical.append({'case':a['name'],'energy_delta_percent':pct,'terminal_delta_V':a['max_abs_terminal_V']-b['max_abs_terminal_V'],'same_errors_and_joint_screen':bool(same),'matches_declared_delta':abs(pct-control['energy_change_percent'])<1e-10})
 checks['10_numerical_controls_consistent']=len(numerical)==10 and all(x['same_errors_and_joint_screen'] and x['matches_declared_delta']for x in numerical)
 placement=[];pdecl=json.loads((ROOT/'evidence/highspeed-nrz-pvt/cap-placement-control.json').read_text())
 for control in pdecl['controls']:
  a=control['row'];b=byname[control['reference']];ek='rail_plus_DATA_positive_draw_fJ_per_gross_bit';pct=100*(a[ek]/b[ek]-1)
  placement.append({'case':a['name'],'energy_delta_percent':pct,'same_errors_and_joint_screen':bool(a['errors']==b['errors'] and a['combined_screen_passed']==b['combined_screen_passed']),'matches_declared_delta':abs(pct-control['energy_change_percent'])<1e-10})
 checks['4_cap_placement_controls_consistent']=len(placement)==4 and all(x['same_errors_and_joint_screen'] and x['matches_declared_delta']for x in placement)
 limitations=['84 grid points are finite-pattern deterministic simulations, not BER or a continuous maximum-speed proof.','Route A2Gb/s remains failed after modification; the accepted three-condition envelope is derated to1Gb/s.','B reference moves to existing fixed ideal3.3V VDUMMY rail. This rail dependency is explicit and its terminal current is included; upstream regulation losses are excluded.','Receiver filter implementation is reused byte-for-byte; independent recomputation covers fixed sample decisions, source-power integration and terminal differences.','The main grid freezes MOS SS/FF and resistor SS/FF together. Independent cross-corners, LED temperature dependence, mismatch and measured optical receiver remain unverified.']
 out={'script':rel(Path(__file__)),'script_sha256':sha(Path(__file__)),'work':rel(WORK),'manifest_sha256':sha(WORK/'manifest.json'),'summary_snapshot_sha256':sha(ROOT/'evidence/highspeed-nrz-pvt/summary.json'),'snapshot_counts':summary['counts'],'checks':checks,'pass':all(checks.values()),'frozen_files':hashes,'core_checks':corechecks,'main_case_checks':sourcechecks,'pass_sets':sets,'same_rate_comparisons':comparisons,'cross_route_common_0p5G_comparisons':cross_route,'raw_recalculations':rawchecks,'numerical_controls':numerical,'cap_placement_controls':placement,'limitations':limitations}
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({'pass':out['pass'],'checks':checks,'pass_sets':sets,'raw_checks':[{k:x[k]for k in ['case','total_fJ_per_gross_bit','energy_delta_from_pipeline_fJ_per_bit','flags']}for x in rawchecks]},ensure_ascii=False,indent=2))
 if not out['pass']:raise SystemExit(1)
if __name__=='__main__':main()
