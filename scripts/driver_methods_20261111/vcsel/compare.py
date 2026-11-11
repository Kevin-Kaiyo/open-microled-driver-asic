#!/usr/bin/env python3
"""Compact same-rate VCSEL method comparison, with source/storage scope."""
from pathlib import Path
import hashlib,json,sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run
ROOT=run.ROOT;EV=run.EV
BASE=ROOT/'build/ab-improvement-20261111/VCSEL/vc-atten50-steer20'
def summarize_case(p,label):
 m=run.engine.read_json(p/'manifest.json');a=run.engine.read_json(p/'analysis.json');r=run.engine.read_json(p/'result.json');full=a['pathways']['actual_graph_5GHzRX']
 assert run.sha(p/'testbench.spice')==m['deck_sha256']
 return dict(label=label,source_case=str(p.relative_to(ROOT)),net_Gbps=a['net_Gbps'],steps_per_UI=a['steps_per_UI'],MOS=len(m['devices']),combined_screen_pass=a['combined_screen_pass'],receiver_errors=full['errors'],amplitude_uAeq=full['worst_signed_margin_uAeq'],timing_UI=full['one_sided_margin_UI'],timing_ps=full['one_sided_margin_ps'],energy_pJ_per_attempted_payload_bit=a['source_energy_pJ_per_attempted_net_bit'],energy_by_source=a['energy_by_source_pJ_per_attempted_net_bit'],I_range_mA=a['observed']['electrical_current_range_mA'],max_body_forward_V=a['observed']['max_body_forward_V'],terminal_peak=a['observed']['terminal_peak'],within_calibrated_current_range=a['observed']['within_calibrated_electrical_and_optical_current_range'],analysis_sha256=run.sha(p/'analysis.json'),driver_sha256=m['source_sha256']['driver.spice'])
def main():
 rows=[];pairs=[]
 for rate in [6.4,7.2,8.0,8.8,9.6,10.4]:
  old=BASE/f'net{rate:g}-edge20-s40'
  if (old/'analysis.json').exists():rows.append(summarize_case(old,'baseline73MOS'))
  for name in ['vc-ff20','vc-dr65','vc-single','vc-single-r100','vc-single-r150']:
   p=run.BUILD/name/f'net{rate:g}-s40'
   if (p/'analysis.json').exists():rows.append(summarize_case(p,name))
  new=run.BUILD/'vc-single-r150'/f'net{rate:g}-s40'
  if not (old/'analysis.json').exists() or not (new/'analysis.json').exists():continue
  a,b=summarize_case(old,'baseline'),summarize_case(new,'selected')
  m=run.engine.read_json(old/'manifest.json');m['candidate_spec']={'CFF_fF':0}
  storage_a=run.storage(old,m,run.engine.read_json(old/'result.json'));storage_b=run.engine.read_json(new/'storage.json')
  epa=a['energy_pJ_per_attempted_payload_bit']['positive'];epb=b['energy_pJ_per_attempted_payload_bit']['positive'];dU=storage_b['explicit_cap_delta_J']-storage_a['explicit_cap_delta_J'];saving=(epa-epb)*4096e-12
  pairs.append(dict(net_Gbps=rate,old_combined=a['combined_screen_pass'],new_combined=b['combined_screen_pass'],old_Eplus_pJ=epa,new_Eplus_pJ=epb,Eplus_change_percent=100*(epb/epa-1),source_positive_saving_J=saving,explicit_cap_delta_old_J=storage_a['explicit_cap_delta_J'],explicit_cap_delta_new_J=storage_b['explicit_cap_delta_J'],explicit_delta_new_minus_old_J=dU,absolute_storage_delta_over_source_saving=abs(dU)/abs(saving),partial_net_minus_cap_saving_J=(storage_a['source_net_J']-storage_a['explicit_cap_delta_J'])-(storage_b['source_net_J']-storage_b['explicit_cap_delta_J'])))
 s=run.summarize();selected=[x for x in s['rows'] if x['candidate']=='vc-single-r150' and x['steps_per_UI']==40 and not x['holdout']];passed=[x['net_Gbps'] for x in selected if x['combined_screen_pass']];hi=max(passed) if passed else None;fails=[x['net_Gbps'] for x in selected if hi is not None and x['net_Gbps']>hi and not x['combined_screen_pass']]
 out=dict(schema='vcsel-methods-comparison-v1',rows=rows,matched_pairs=pairs,selected_nominal_envelope={'highest_tested_pass_Gbps':hi,'next_tested_fail_Gbps':min(fails) if fails else None},limits=['All source energies divide by4096attemptedpayloadbits; failedreceiverpoints are not useful transmitted-bit efficiency.','VSET/VREGSET remain external precision voltage boundaries, not implementedbandgaps. InputPHY and external source IC internal overheads excluded; all instantiatedsourceportenergiescounted.','Explicit-cap correction excludes MOS intrinsic charge, VCSEL junctionC and inductors; it is not full dissipation or periodic steady-state closure.','Model proxy current range2to7.5mA and body-forward0.3V remain binding.','No newPVT/startup/layout/PEX/silicon/opticalmeasurement or physicalBER qualification.']);run.emit(EV/'vcsel-comparison.json',out);print('Comparison',len(rows),'rows',hi,min(fails) if fails else None)
if __name__=='__main__':main()
