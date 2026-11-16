#!/usr/bin/env python3
"""Compact completed-case matrix. Failed/calibration cases remain addressable."""
import datetime,re
from pathlib import Path
import run as a
def compact(p):
 r=a.read(p);m=a.read(p.parent/'manifest.json');level=r['case'].get('level');correction=p.parent/'reanalysis.json'
 if correction.exists():r.update(a.read(correction));r['analysis_error']=None
 row=dict(case_path=str(p.parent.relative_to(a.ROOT)),variant=r['variant'],point=m['pvt']['label'],kind='dc' if level is not None else r['case']['mode'],level=level,simulation_ok=r['simulation_ok'],analysis_error=r.get('analysis_error'),MOS=r.get('MOS'),terminal_pass=r.get('terminal_pass'),body_pass=r.get('body_pass'),result_sha256=a.sha(p),manifest_sha256=a.sha(p.parent/'manifest.json'),deck_sha256=a.sha(p.parent/'testbench.spice'),trim_ohm=m['trim_ohm'])
 if correction.exists():row.update(reanalysis_path=str(correction.relative_to(a.ROOT)),reanalysis_sha256=a.sha(correction),original_analysis_error=r['original_analysis_error'])
 if level is not None:
  row.update(current_uA=r.get('current_uA'),target_uA=r.get('target_uA'),DC_error_percent=r.get('DC_error_percent'),DC_pass=r.get('DC_pass'),source_net_power_mW=sum(r.get('power_mW',{}).values()),nodes_V={k:r.get('nodes_V',{}).get(k) for k in ['led_feed','led_a','out','xdrv.vh','xdrv.vl','xdrv.hset','xdrv.lset','xdrv.hsense','xdrv.lsense']})
 else:
  row['frames']=[dict(frame=f['frame'],receiver=f['full_receiver'],frozen_phase=f['first_frame_phase_receiver'],energy_pJ_per_attempted_payload_bit=f['energy_pJ_per_attempted_payload_bit'],current_range_uA=f['current_range_uA']) for f in r.get('frames',[])]
  row['shutdown']={k:r.get('shutdown',{}).get(k) for k in ['off_current_screen_pass','max_abs_current_uA','recovery_within_1us_verified','recovery_screen','last_frame_full_rx_pass']}
  row['transient_joint_pass']=bool(r.get('terminal_pass') and r.get('body_pass') and row['shutdown']['off_current_screen_pass'] and row['shutdown']['recovery_within_1us_verified'] and row['frames'][-1]['receiver']['research_margin_pass'] and row['frames'][-1]['frozen_phase']['research_margin_pass']) if row['frames'] else False
  if row['kind']=='continuous':row['transient_joint_pass']=bool(r.get('terminal_pass') and r.get('body_pass') and r.get('normal_current_IV_domain_pass') and all(f['receiver']['research_margin_pass'] and f['frozen_phase']['research_margin_pass'] for f in row['frames']))
  row['qualification_note']='Transient joint screen does not include the separately required DC ±1% screen; fault frame1 deliberately includes disabled data.'
 return row
def main():
 rows=[compact(p) for p in sorted(a.BUILD.glob('*/*/result.json'))]
 for r in rows:
  if r['kind']=='dc':continue
  dc=[x for x in rows if x['kind']=='dc' and x['variant']==r['variant'] and x['point']==r['point']]
  r['paired_DC_cases']=[x['case_path'] for x in dc];r['paired_DC_pass']=len(dc)==2 and all(x['DC_pass'] for x in dc);r['joint_with_DC_pass']=bool(r['transient_joint_pass'] and r['paired_DC_pass']);r['protection_checked']=r['kind']=='fault'
 family=[]
 for v in ['baseline','track-fixed','tracklong-fixed','trackwide4-fixed','trackwide4gm5-fixed','trackwide4gm5a37-fixed','trackwide4gm5pre2-fixed','trackwide4gm5buf2-fixed']:
  dc=[r for r in rows if r['variant']==v and r['kind']=='dc'];wave=[r for r in rows if r['variant']==v and r['kind']!='dc']
  family.append(dict(variant=v,DC_cases=len(dc),DC_passes=sum(bool(r['DC_pass']) for r in dc),max_abs_DC_error_percent=max((abs(r['DC_error_percent']) for r in dc),default=None),fixed_parameters_shared_across_grid=len({str(r['trim_ohm']) for r in dc})==1,transient_cases=len(wave),transient_joint_passes=sum(r['transient_joint_pass'] for r in wave)))
 out=dict(schema='microled-A-pvt-compact-v1',generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),grid=a.GRID,scope='Deterministic MOS PVT and supply grid; fixed measured LED IV at unspecified source temperature, synthetic200fF/200ps, RX1GHz. No resistor tolerance/TC/mismatch, LEDthermal/opticalmeasurement, newlayout/PEX qualification.',supplies='VIN/VDD/VLED ±5%; VREF fixed2.5V; DATA andDISABLE high followVDD; res_typical always.',families=family,cases=[r for r in rows if '-cal' not in r['variant']],calibration_case_count=sum('-cal' in r['variant'] for r in rows),all_completed_case_paths=[r['case_path'] for r in rows],calibration_record_paths=[str(p.relative_to(a.ROOT)) for p in sorted(a.EV.glob('*-calibration.json'))])
 a.emit(a.EV/'matrix.json',out);print([(v['variant'],v['DC_passes'],v['max_abs_DC_error_percent'],v['transient_joint_passes']) for v in family])
if __name__=='__main__':main()
