#!/usr/bin/env python3
"""Final consistency gate. Delivery integrity is distinct from circuit success."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote,urlsplit
import hashlib,json,math,xml.etree.ElementTree as ET
import run as e

class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  for k,v in attrs:
   if k in ['href','src']:self.links.append(v)

def main():
 root=e.ROOT;ev=root/'evidence/fair-driver-v1';index=json.loads((ev/'rx-equal-latency-v2-index.json').read_text());assert index['complete'] and index['counts']=={'baseline':45,'controls':11};assert not index['no_successful_electrical'] and not index['unanalysed'];checked=[];errors=0;maxbody=0.;combined=[]
 for folder in ['matched-r2','controls-r1']:e.verify(e.BUILD/folder)
 rxwork=e.BUILD/'rx-equal-latency-v2-final-r1';m=json.loads((rxwork/'manifest.json').read_text())
 for f,h in m['files'].items():assert e.sha(rxwork/f)==h
 for item in index['records']:
  p=root/item['path'];assert e.sha(p)==item['sha256'];r=json.loads(p.read_text());original_path=root/r['source_result'];assert e.sha(original_path)==r['source_result_sha256'];o=json.loads(original_path.read_text());m0=o['metrics'];rx=r['receiver'];assert o['simulation_ok'] and 'analysis_error' not in o
  assert e.sha(original_path.with_name('testbench.spice'))==o['deck_sha256'];assert e.sha(original_path.with_name('waveform.dat.gz'))==r['source_gzip_sha256']==o['gzip_sha256'];assert (original_path.parent/'ngspice.log').exists()
  assert r['analysis_execution_sha256']==m['execution_sha256'];assert r['helper_run_sha256']==m['helper_run_sha256'];assert r['v2_receiver_sha256']==m['files']['receiver.py'] and r['v2_contract_sha256']==m['files']['contract.md'] and r['v2_stimulus_sha256']==m['files']['stimulus.json']
  assert rx['sampling']['absolute_delay_budget_ns']==8 and rx['sampling']['absolute_delay_grid_ps']==5 and rx['sampling']['training_scored_bits']==448 and rx['sampling']['training_guard_bits']==64
  assert rx['ranges_bits']['validation']==[576,4672] and rx['validation']['bit_count']==4096 and rx['rates']['transmitted_bits']==4736 and rx['sampling']['training_to_validation_slack_s']>0
  assert rx['proxy']['thresholds_uA']==([37.5,62.5,87.5] if o['case']['route']=='C' else [62.5]);assert abs(rx['rates']['frame_duration_s']-4096/(o['case']['net_rate_Gbps']*1e9))<1e-17
  assert len(m0['stress'])=={'A':20,'B':21,'C':49}[o['case']['route']];assert set(m0['energy'])=={'VIN','VDD','VREF','VLED','VD0','VD1','VDISABLE'}
  for q in ['positive_J','returned_J','net_J']:assert abs(sum(x[q] for x in m0['energy'].values())-m0['total_energy'][q])<1e-20
  assert abs(m0['total_energy']['positive_J']-m0['total_energy']['returned_J']-m0['total_energy']['net_J'])<1e-20
  assert abs(m0['total_energy']['positive_J']/4096*1e12-m0['total_energy']['positive_pJ_per_payload_bit'])<1e-10
  if item['group']=='baseline':errors+=not r['communication_screen_passed'];maxbody=max(maxbody,m0['max_body_forward_V'])
  checked.append({'group':item['group'],'canonical_case':item['canonical_case'],'analysis_sha256':item['sha256'],'native_gzip_sha256':o['gzip_sha256']})
 dc=[]
 for p in (e.BUILD/'matched-r2/cases').glob('DC-*/result.json'):
  r=json.loads(p.read_text());assert r['simulation_ok'];assert e.sha(p.with_name('waveform.dat.gz'))==r['gzip_sha256'];dc.append(r)
 assert len(dc)==24;assert all(abs(r['metrics']['current_error_percent'])<=1 for r in dc if '-TT-' in r['case']['name'])
 assert len(list((e.BUILD/'controls-r1/cases').glob('DC-*/result.json')))==32
 figures=json.loads((ev/'circuit-figure-manifest.json').read_text())
 for path,h in figures['sources'].items():assert e.sha(root/path)==h
 assert figures['checks']['all_route_mos_represented'] and figures['checks']['all_mos_have_D_G_S_B']
 figure_symbols=0
 assert len(figures['figures'])==8
 for f in figures['figures']:
  path=root/f['file'];assert e.sha(path)==f['svg_sha256'];assert e.sha(root/f['png'])==f['png_sha256']
  symbols={x.attrib['data-device']:x.attrib for x in ET.parse(path).getroot().iter() if 'data-device' in x.attrib}
  for name,device in f['devices'].items():
   assert symbols[name]['data-terminal-order']=='D G S B' and symbols[name]['data-nets'].split()==device['nets'];figure_symbols+=1
 # Inspect any additional generic recorded digests.
 def walk(x):
  if isinstance(x,dict):
   if 'path' in x and 'sha256' in x and isinstance(x['path'],str) and (root/x['path']).is_file():assert e.sha(root/x['path'])==x['sha256']
   for v in x.values():walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
 walk(figures)
 diag=json.loads((ev/'load-diagnostic-figures.json').read_text());assert e.sha(root/diag['plotter_source_snapshot'])==diag['plotter_sha256']
 for name,h in diag['figures'].items():assert e.sha(root/'docs/research/fair-driver-comparison-20261025/figures'/name)==h
 report=root/'docs/research/fair-driver-comparison-20261025/index.html';parser=Links();parser.feed(report.read_text());missing=[]
 for raw in parser.links:
  x=urlsplit(raw)
  if x.scheme or x.netloc or not x.path:continue
  path=(report.parent/unquote(x.path)).resolve()
  if not path.exists():missing.append(raw)
 assert not missing,missing
 summary=json.loads((ev/'summary.json').read_text());assert summary['status']=='complete';assert len(summary['selected_case_map'])==69
 controls=json.loads((ev/'controls-summary.json').read_text());assert len(controls['numerical_comparison'])==3 and all(x['numerical_control_passed'] for x in controls['numerical_comparison'])
 receipt={'delivery_integrity_passed':True,'script_sha256':e.sha(Path(__file__)),'baseline_DC':24,'baseline_RX':45,'control_DC':32,'control_RX':11,'v2_canonical_unique':56,'baseline_RX_criterion_failures_preserved':int(errors),'maximum_observed_body_forward_V':maxbody,'numeric_controls_40_to80_passed':3,'source_bound_circuit_figures':8,'individual_MOS_symbols_checked':figure_symbols,'local_report_links_checked':len(parser.links),'missing_links':missing,'report_sha256':e.sha(report),'summary_sha256':e.sha(ev/'summary.json'),'v2_index_sha256':e.sha(ev/'rx-equal-latency-v2-index.json'),'checked_native_files':checked,'boundary':'Integrity/consistency of recorded experiments, not all-circuit functional success, physical qualification, opticalBER or production acceptance.'}
 e.emit(ev/'delivery-check.json',receipt);print(json.dumps({k:v for k,v in receipt.items() if k!='checked_native_files'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
