#!/usr/bin/env python3
"""Collect validated route A improvement records without changing any results."""
from pathlib import Path
import csv,hashlib,json
ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/ab-improvement-20261111'
OUT=ROOT/'evidence/ab-improvement-20261111'
SELECTED='a-rin1wide-core03-matched'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
rows=[]
CANDIDATES=['a-base','a-rin1','a-rin1wide','a-rin1wide-buf03','a-rin1wide-buf03-out2-matched',SELECTED]
for name in CANDIDATES:
 work=BUILD/name
 assert json.loads((work/'stimulus.json').read_text())['seed']==0x5ACE
 for p in sorted((work/'cases').glob('TT-*/result.json')):
  r=json.loads(p.read_text());assert r['simulation_ok'] and not r.get('analysis_error')
  a=r['analysis'];f=a['full_receiver'];c=r['case']
  assert c['corner']=='typical' and c['temp_C']==27 and c['vdd_V']==3.3 and abs(c['led_cap_F']-200e-15)<1e-24
  assert sha(p.with_name('waveform.dat.gz'))==r['gzip_sha256']
  rows.append({'candidate':work.name,'net_Gbps':c['net_rate_Gbps'],'steps_per_UI':c['steps_per_symbol'],
   'all_screens_pass':a['combined_screen_pass'],'errors':f['errors'],'amplitude_uAeq':f['worst_signed_margin_uAeq'],
   'time_ps':f['one_sided_margin_ps'],'time_UI':f['one_sided_margin_bit_UI'],
   'electrical_errors':a['electrical_receiver']['errors'],'electrical_amplitude_uA':a['electrical_receiver']['worst_signed_margin_uAeq'],
   'electrical_time_ps':a['electrical_receiver']['one_sided_margin_ps'],'electrical_time_UI':a['electrical_receiver']['one_sided_margin_bit_UI'],'electrical_receiver_screen_pass':a['electrical_receiver']['research_margin_pass'],'positive_pJ_per_attempted_bit':a['energy_pJ_per_attempted_payload_bit']['positive'],
   'net_pJ_per_attempted_bit':a['energy_pJ_per_attempted_payload_bit']['net'],'current_min_uA':a['current_range_uA'][0],'current_max_uA':a['current_range_uA'][1],
   'body_forward_V':a['max_body_forward_V'],'terminal_pass':a['terminal_screen_pass'],
   'source_result':str(p.relative_to(ROOT)),'source_result_sha256':sha(p),'waveform_raw_sha256':r['raw_sha256'],'waveform_gzip_sha256':r['gzip_sha256']})
convergence=[]
for fine in [r for r in rows if r['candidate']==SELECTED and r['steps_per_UI']==80]:
 coarse=next(r for r in rows if r['candidate']==SELECTED and r['net_Gbps']==fine['net_Gbps'] and r['steps_per_UI']==40)
 convergence.append({'net_Gbps':fine['net_Gbps'],'decision_unchanged':fine['all_screens_pass']==coarse['all_screens_pass'],
  'amplitude_delta_uAeq':fine['amplitude_uAeq']-coarse['amplitude_uAeq'],'time_delta_ps':fine['time_ps']-coarse['time_ps'],
  'positive_energy_relative_delta_percent':100*(fine['positive_pJ_per_attempted_bit']/coarse['positive_pJ_per_attempted_bit']-1)})
assert all(x['decision_unchanged'] for x in convergence)
selected=[r for r in rows if r['candidate']==SELECTED and r['steps_per_UI']==40]
passed=[r['net_Gbps'] for r in selected if r['all_screens_pass']];highest=max(passed)
fail_above=[r['net_Gbps'] for r in selected if not r['all_screens_pass'] and r['net_Gbps']>highest]
baseline12=next(r for r in rows if r['candidate']=='a-base' and r['net_Gbps']==1.2)
selected12=next(r for r in selected if r['net_Gbps']==1.2)
result={'schema':'A-improvement-summary-v1','selected_candidate':SELECTED,'highest_passing_sampled_net_Gbps':highest,
 'next_failing_sampled_net_Gbps':min(fail_above) if fail_above else None,'target3p2_test_complete':any(r['net_Gbps']==3.2 for r in selected),
 'common1p2_energy_delta_percent':100*(selected12['positive_pJ_per_attempted_bit']/baseline12['positive_pJ_per_attempted_bit']-1),
 'convergence':convergence,'records':rows,'scope':'Fixed initial-state PRBS15 seed0x5ACE, TT27C, synthetic200fF/200ps load,1GHzRX. New nominal schematic only; no physical fmax, BER/PVT or continuous-periodic-energy claim.',
 'script_path':str(Path(__file__).relative_to(ROOT)),'script_sha256':sha(Path(__file__))}
OUT.mkdir(exist_ok=True,parents=True)
(OUT/'a-improvement-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
with (OUT/'a-improvement-summary.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
print(json.dumps({k:v for k,v in result.items() if k!='records'},ensure_ascii=False))
