#!/usr/bin/env python3
"""Verify executed netlists, actual transmitted PWL, immutable source snapshots and confirmations."""
import gzip,hashlib,json,re,sys
from pathlib import Path
import numpy as np
sys.dont_write_bytecode=True
import run

def canonical(deck):
 deck=re.sub(r'(?m)^tran .+$','tran STEP_REMOVED',deck)
 return deck

def main():
 rows=[]
 for p in sorted(run.BUILD.glob('*/*/*/manifest.json')):
  folder=p.parent;m=run.read(p);cfg=m['pvt_config'];r=run.read(folder/'result.json');deck=(folder/'testbench.spice').read_text();st=run.read(folder/'stimulus.json')
  assert run.sha(p)==r['manifest_sha256'] and run.sha(folder/'testbench.spice')==m['deck_sha256']==r['deck_sha256']
  assert run.sha(folder/'stimulus.json')==m['stimulus_sha256'] and run.sha(folder/'execution-source.py')==m['execution_source_sha256']
  for n,h in m['source_sha256'].items():assert run.sha(folder/n)==h
  for n,v in m['execution_helpers'].items():assert run.sha(folder/'execution-sources'/v['copy'])==v['sha256']
  assert r['simulation_ok'] and r['simulation_complete'] and r['exit_code']==0
  assert len(m['devices'])==73 and len(m['expressions'])==len(set(m['expressions']))
  for d in m['devices']:
   for n in d['nodes']:assert n=='0' or f'v({n})' in m['expressions']
  assert re.search(rf'(?m)^\.lib "sm141064.ngspice" {cfg["pvt"]["section"]}$',deck)
  assert re.search(rf'(?m)^\.temp {cfg["pvt"]["temp_C"]}$',deck)
  for port in ['VLASER','VDD','VREF','VPHY']:
   q=re.search(rf'(?m)^{port} \w+ 0 ([\d.]+)$',deck);assert q and abs(float(q.group(1))-3.3*cfg['pvt']['rail_scale'])<1e-12
  assert list(m['ports'])==['VLASER','VDD','VREF','VD','VDB','VSET','VREGSET','VPHY']
  for port,node,flip in [('VD','d_cmd',False),('VDB','db_cmd',True)]:
   if m['kind']=='dc':
    q=re.search(rf'(?m)^{port} {node} 0 ([\d.]+)$',deck);assert q and abs(float(q.group(1))-3.3*(1-cfg['level'] if flip else cfg['level']))<1e-12
   else:
    q=re.search(rf'(?m)^{port} {node} 0 PWL\(([^)]*)\)',deck);assert q
    a=np.asarray([float(v) for v in q.group(1).replace('+',' ').split()]).reshape(-1,2);assert np.all(np.diff(a[:,0])>0)
    bits=np.asarray(st['bits']);expected=(1-bits if flip else bits)*3.3;ui=m['UI_ps']*1e-12
    assert len(bits)==cfg['line_bits'] and np.allclose(np.interp((np.arange(len(bits))+.5)*ui,a[:,0],a[:,1]),expected,atol=1e-10,rtol=0)
    transitions=np.flatnonzero(np.diff(bits))+1;assert len(a)==2+2*len(transitions)
    assert np.allclose(a[1:-1:2,0],transitions*ui,rtol=0,atol=1e-17)
    assert np.allclose(a[2:-1:2,0]-a[1:-1:2,0],20e-12,rtol=0,atol=1e-17)
  waveform=folder/'waveform.dat.gz';assert run.sha(waveform)==r['waveform']['sha256']
  with gzip.open(waveform,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['waveform']['raw_sha256']
  row=dict(case=str(folder.relative_to(run.ROOT)),manifest_sha256=run.sha(p),result_sha256=run.sha(folder/'result.json'),waveform=r['waveform'],kind=m['kind'])
  if m['kind']=='full':
   a=run.read(folder/'analysis.json');q=a['pathways']['actual_graph_5GHzRX'];assert a['result_sha256']==row['result_sha256'] and a['manifest_sha256']==row['manifest_sha256']
   assert q['errors']>=0 and len(st['bits'])==4736 and m['attempted_payload_bits']==4096
   assert a['combined_screen_pass']==bool(a['DC_screen_pass'] and q['screen_pass'] and r['terminal_screen_pass'] and r['max_body_forward_V']<=.3 and r['current_min_mA']>=2 and r['current_max_mA']<=7.5)
   for k in ['positive','returned','net']:
    assert abs(a['source_energy_pJ_per_attempted_net_bit'][k]-sum(v[k+'_J'] for v in r['energy_by_port'].values())*1e12/4096)<1e-12
   row.update(analysis_sha256=run.sha(folder/'analysis.json'),combined_pass=a['combined_screen_pass'])
  rows.append(row)
 confirmations=[];limits=run.read(run.EV/'confirmation-protocol.json')['numerical_comparison_limits']
 for variant,corner,rate in run.read(run.EV/'confirmation-protocol.json')['half_step_cases']:
  ps=[run.BUILD/variant/corner/f'full-net{rate:g}-s{s}' for s in [40,80]];mm=[run.read(p/'manifest.json') for p in ps];aa=[run.read(p/'analysis.json') for p in ps];rr=[run.read(p/'result.json') for p in ps]
  assert mm[0]['stimulus_sha256']==mm[1]['stimulus_sha256'] and mm[0]['source_sha256']==mm[1]['source_sha256'] and mm[0]['devices']==mm[1]['devices'] and mm[0]['ports']==mm[1]['ports']
  assert canonical((ps[0]/'testbench.spice').read_text())==canonical((ps[1]/'testbench.spice').read_text())
  q0,q1=[a['pathways']['actual_graph_5GHzRX'] for a in aa]
  d=dict(positive_energy_relative_percent=abs(aa[1]['source_energy_pJ_per_attempted_net_bit']['positive']/aa[0]['source_energy_pJ_per_attempted_net_bit']['positive']-1)*100,time_margin_abs_UI=abs(q1['one_sided_margin_UI']-q0['one_sided_margin_UI']),amplitude_abs_uAeq=abs(q1['worst_signed_margin_uAeq']-q0['worst_signed_margin_uAeq']),max_terminal_abs_V=abs(rr[1]['terminal_peak']['value_V']-rr[0]['terminal_peak']['value_V']),max_body_abs_V=abs(rr[1]['max_body_forward_V']-rr[0]['max_body_forward_V']),current_extreme_abs_mA=max(abs(rr[1][k]-rr[0][k]) for k in ['current_min_mA','current_max_mA']))
  ok=all(a['combined_screen_pass'] for a in aa) and all(d[k]<=limits[k] for k in d);assert ok
  confirmations.append(dict(cases=[str(p.relative_to(run.ROOT)) for p in ps],differences=d,pass_=ok))
 sel=run.read(run.EV/'selection.json');hp=run.BUILD/'cmd-r330/sshotlow/holdout-full-net6.4-s40';hm=run.read(hp/'manifest.json');ha=run.read(hp/'analysis.json');assert hm['pvt_config']['holdout_protocol']==sel['holdout_protocol'] and ha['combined_screen_pass']
 q=dict(schema='vcsel-pvt-validation-v1',status='passed',script_sha256=run.sha(Path(__file__)),case_count=len(rows),cases=rows,half_step=confirmations,holdout=dict(case=str(hp.relative_to(run.ROOT)),analysis_sha256=run.sha(hp/'analysis.json'),pass_=True),limits=limits)
 run.emit(run.EV/'validation.json',q);print('VALIDATED',len(rows),'cases',len(confirmations),'half-step pairs plus holdout')
if __name__=='__main__':main()
