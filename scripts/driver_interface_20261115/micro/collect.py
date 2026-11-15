#!/usr/bin/env python3
"""Compact evidence index; does not rerun or mutate frozen simulation cases."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BUILD=ROOT/'build/driver-interface-20261115/MicroLED';EV=ROOT/'evidence/driver-interface-20261115'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def main(final=False):
 rows=[]
 for p in sorted(BUILD.glob('*/*/result.json')):
  r=read(p);m=read(p.with_name('manifest.json'));variant=p.parent.parent.name.split('-',1)[1]
  row=dict(route=r['case']['route'],variant=variant,case_name=p.parent.name,source_case=str(p.parent.relative_to(ROOT)),result_sha256=sha(p),manifest_sha256=sha(p.with_name('manifest.json')),waveform_gzip_sha256=r.get('gzip_sha256'),result=r)
  effective=dict(r)
  if p.with_name('provenance-correction.json').exists():row['helper_provenance_correction']=dict(path=str(p.with_name('provenance-correction.json').relative_to(ROOT)),sha256=sha(p.with_name('provenance-correction.json')))
  if p.with_name('reanalysis.json').exists():
   correction=read(p.with_name('reanalysis.json'));row['correction']=dict(path=str(p.with_name('reanalysis.json').relative_to(ROOT)),sha256=sha(p.with_name('reanalysis.json')),record=correction)
   effective.update(stress=correction['corrected_stress'],terminal_pass=correction['terminal_pass'],body_pass=correction['body_pass'],body_forward_V=correction['body_forward_V'],stress_provenance='append-only actual-deck native-waveform reanalysis')
  if p.with_name('diagnostic.json').exists():
   diagnostic=read(p.with_name('diagnostic.json'));row['completion_diagnostic']=dict(path=str(p.with_name('diagnostic.json').relative_to(ROOT)),sha256=sha(p.with_name('diagnostic.json')),record=diagnostic);effective.update(simulation_ok=False,simulation_complete=False,failure_classification=diagnostic['failure_classification'])
  if 'correction' in row or 'completion_diagnostic' in row:row['corrected_effective_result']=effective
  if effective.get('case',{}).get('kind')=='dc':good=effective.get('DC_pass',False)
  elif effective.get('case',{}).get('mode')=='fault':good=effective.get('shutdown',{}).get('off_current_screen_pass',False) and effective.get('shutdown',{}).get('recovery_within_1us_verified',False) and effective.get('shutdown',{}).get('last_frame_full_rx_pass',False)
  else:good=bool(effective.get('frames')) and all(x['full_receiver']['research_margin_pass'] and x['first_frame_phase_receiver']['research_margin_pass'] for x in effective.get('frames',[]))
  row['combined_research_screen_pass']=bool(good and effective.get('simulation_ok',False) and not effective.get('analysis_error') and effective.get('terminal_pass',False) and effective.get('body_pass',False));rows.append(row)
 selections={};by_case={x['source_case']:x for x in rows}
 for route in ['A','B']:
  variant={'A':'protected_v3r','B':'protected_v6r'}[route];prefix=f'build/driver-interface-20261115/MicroLED/{route}-{variant}/'
  selection=dict(variant=variant,dc_cases=[prefix+'DC-L0',prefix+'DC-L1'],continuous_case=prefix+'continuous-f4-net1.6-s40',fault_case=prefix+'fault-f2-net1.6-s40',half_step_case=prefix+'fault-f2-net1.6-s80',holdout_case=prefix+'fault-f2-net1.6-s40-holdout8192')
  if final:
   for key,value in selection.items():
    if key=='variant':continue
    for path in value if isinstance(value,list) else [value]:
     r=read(ROOT/path/'result.json');assert r['simulation_ok'] and not r.get('analysis_error') and by_case[path]['combined_research_screen_pass'],path
     if key=='continuous_case':assert r['steady_screen']['finite_window_pass'],path
   fp=EV/f'micro-selection-{route}.json';assert fp.exists();selection['parameter_freeze']=dict(path=str(fp.relative_to(ROOT)),sha256=sha(fp))
  selections[route]=selection
 result=dict(schema_version=1,status='frozen' if final else 'in_progress',protocol=dict(path='evidence/driver-interface-20261115/micro-protocol.json',sha256=sha(EV/'micro-protocol.json')),selections=selections,rows=rows,boundaries=[
 '20 um yellow MicroLED static I-V model; 200 fF, 0.5 nH / 1 ohm, TT27; optical tau200 ps and 1 GHz receiver remain fixed. No measured optical or thermal behavior.',
 'Frames repeat the same actual 4736 PRBS15 bits without interruption; they are not statistically independent bit counts. Filter states continue across all frames.',
 'All seven signed source ports are counted. Capacitor and inductor endpoint energies are explicit; intrinsic MOS charge and dissipation are not a complete energy-conservation closure.',
 'A baseline DISABLE was unimplemented. B baseline DISABLE clamps reference but does not isolate capacitive feed-forward. Protected B keeps reference running; off power remains charged.',
 'Below0.1 uA and reverse LED current are outside calibrated static I-V range; residual off values are numerical electrical diagnostics, not physical leakage or darkness qualification.',
 'Shutdown is externally commanded; no autonomous overcurrent/temperature detector, POR or safety state machine is implemented. READY RC is open-loop delay, not measured power-good.',
 'Recovery assumes known frame timing and fixed first-frame sample phase. It is not measured CDR or protocol reacquisition; initial OP to data operation is not a cold-power startup experiment.',
 'Finite repeated-frame electrical convergence screens are not device thermal steady state or BER qualification. New schematic does not inherit prior layout/DRC/LVS/PEX signoff.'
 ])
 (EV/'micro-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print('cases',len(rows),'status',result['status'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');main(p.parse_args().final)
