#!/usr/bin/env python3
from pathlib import Path
import json,shutil
from run import ROOT,BUILD,CIR,EV,sha,emit

def capacitor_summary(r):
 cap=r.get('explicit_capacitor_energy')
 if cap is None:return None
 cap=dict(cap);items=list(cap['capacitors'].values())
 start=sum(x['start_J'] for x in items);end=sum(x['end_J'] for x in items)
 assert abs((end-start)-cap['change_J'])<1e-20
 cap.update(start_J=start,end_J=end,
            change_pJ_per_offered_payload_bit=cap['change_J']/4096*1e12 if r['config']['mode']=='frame' else None,
            interpretation='Positive deltaU is stored energy increase; negative deltaU is stored energy release. This partial explicit-capacitor ledger is neither complete device energy conservation nor a correction to optical-link efficiency.')
 return cap

def main():
 dc=[];frames=[];other=[];fail=[];ac=[]
 for f in sorted(BUILD.glob('*/result.json')):
  if not (f.parent/'manifest.json').exists():
   ar=json.loads(f.read_text())
   if 'unity_crossings' in ar:ac.append(ar)
   continue
  r=json.loads(f.read_text());m=json.loads((f.parent/'manifest.json').read_text());c=m['config'];base=dict(case=r['case'],variant=c['variant'],mode=c['mode'],corner=c['corner'],temp_C=c['temp'],supply_V=c['voltage'],config=c,result=str(f.relative_to(ROOT)),result_sha256=sha(f),manifest=str((f.parent/'manifest.json').relative_to(ROOT)),manifest_sha256=sha(f.parent/'manifest.json'),circuit_sha256=sha(f.parent/'inputs/driver.spice'))
  if not r['simulation_ok']:fail.append(dict(base,exit_code=r['exit_code'],log=str((f.parent/'ngspice.log').relative_to(ROOT))));continue
  base.update(current_range_mA=r['current_range_mA'],stress_max_V=r['max_terminal_V'],body_max_V=r['max_body_forward_V'],device_screen_passed=r['device_screen_passed'])
  if c['mode']=='dc':dc.append(dict(base,current_mA=r['current_mA'],base_current_mA=r['base_current_mA'],tail_current_mA=r['tail_current_mA'],nodes_V=r['nodes_final_V'],source_power_W=r['source_power_W']));continue
  if c['mode']!='frame':
   review=f.parent/'startup-review.json'
   other.append(dict(base,startup=r.get('startup'),startup_review=json.loads(review.read_text()) if review.exists() else None,energy_J={k:r['total_energy'][k] for k in ['positive_J','returned_J','net_J']},explicit_capacitor_energy=capacitor_summary(r),boundary='Not a4096payload frame; do not report pJ/bit for these runs'));continue
  analyses=list(f.parent.glob('analysis-*/result.json'))
  for af in sorted(analyses):
   a=json.loads(af.read_text());label=af.parent.name[len('analysis-'):];plot=EV/(r['case']+'-'+label+'-plot-data.npz');shutil.copy2(af.parent/'plot-data.npz',plot)
   frames.append(dict(base,analysis_label=label,analysis=str(af.relative_to(ROOT)),analysis_sha256=sha(af),errors=a['errors'],time_margin_ps=a['time_margin_ps'],min_signed_margin_uAeq=a['min_signed_margin_uAeq'],optical_margin_min_mW=a['optical_margin_min_mW'],energy=a['energy'],ports=a['energy_by_port'],domain=a['domain'],passed=a['combined_screen_passed'],plot_data=str(plot.relative_to(ROOT)),plot_sha256=sha(plot),explicit_capacitor_energy=capacitor_summary(r),continuous_run=r.get('continuous_run'),energy_window=dict(frame_relative_start_s=0.,frame_relative_end_s=m['end_s'],offered_payload_bits=4096,transmitted_bits=c['nbits'],startup_energy_included=False,original_continuous_frame_start_s=r.get('continuous_run',{}).get('frame_start_s'))))
 result=dict(scope='Frozen3.2Gnet transistor-level VCSEL reference/rail study; no optical measurement, no emitter temperature calibration, no PEX or BER qualification',dc=dc,cases=frames,transient_controls=other,failed_executions=fail,reference_boundary='ExternalVSET andVREGSET are ideal precision-voltage terminal boundaries with100ohm source resistance. Pin-current energy is counted; external reference-chip internal/static power is unknown and excluded. Rsense/passives ideal; explicit tolerance tests are separate.',energy_method='Exact PWL native port power with zero crossings; pJ per4096offeredpayloadbit only for full4736bit frames',source_hashes={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'scripts/vcsel_robustness_20261029/run.py',ROOT/'scripts/vcsel_robustness_20261029/analyze.py',ROOT/'scripts/three_gbps_experiment/vcsel_driver_receiver_v3.py',ROOT/'scripts/three_gbps_experiment/vcsel_model.py',ROOT/'scripts/fair_driver_v1/run.py',ROOT/'scripts/three_gbps_experiment/vcsel_driver_run.py',ROOT/'scripts/fair_driver_v1/receiver_equal_latency_v2.py']},freeze='analog/circuits/vcsel_robustness_20261029/frozen-r6.json')
 for item in ac:
  item['summary_evidence_classification']='Historical unvalidated series-injection ratio; not verified return ratio or stability evidence'
  item['use_for_stability_signoff']=False
 result['approximate_ldo_loop_ac']=ac
 audit_ac=EV/'audit-ac-all-crossings.json'
 result['approximate_ldo_loop_ac_boundary']=dict(
  original_values_preserved=True,
  finding='The previous helper enumerated descending0dB crossings only. All six r10 curves also cross upward near8.83-10.45MHz; capacitive input loading can create this term without an active feedback return loop. The saved voltage ratio is not a verified return ratio.',
  conclusion='Do not interpret first180+phase numbers as established phase margin or stability proof. This does not by itself prove high-frequency oscillation. r10 support is limited to the completed finite time-domain cases; full1Hz-1GHz complex data remain retained.',
  audit=dict(path=str(audit_ac.relative_to(ROOT)),sha256=sha(audit_ac)) if audit_ac.exists() else None)
 result['schema_version']=2
 result['schema_notes']='Frames retain each immutable raw result and analysis hash. explicit_capacitor_energy adds only sums and payload-normalized deltaU from recorded native endpoints; full startup/run energy remains separate. Failed and unfinished executions are never counted as passed.'
 result['pending_execution_inputs']=[dict(case=p.parent.name,manifest=str(p.relative_to(ROOT)),manifest_sha256=sha(p)) for p in sorted(BUILD.glob('*/manifest.json')) if not (p.parent/'result.json').exists()]
 result.pop('freeze',None)
 result['freezes']={p.stem:{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in sorted(CIR.glob('frozen-r*.json'))}
 result['primary_candidate']='r10' if (CIR/'frozen-r10.json').exists() else 'r8'
 for p in sorted((ROOT/'scripts/vcsel_robustness_20261029').glob('*.py')):result['source_hashes'][str(p.relative_to(ROOT))]=sha(p)
 emit(EV/'summary.json',result);print(json.dumps(dict(dc=len(dc),frame_analyses=len(frames),controls=len(other),failures=len(fail),loop_ac=len(ac)),ensure_ascii=False))
if __name__=='__main__':main()
