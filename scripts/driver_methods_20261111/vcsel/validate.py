#!/usr/bin/env python3
"""Validate emitted VCSEL topology, metadata, hashes and energy arithmetic."""
from pathlib import Path
import hashlib,json,math
ROOT=Path(__file__).resolve().parents[3];BUILD=ROOT/'build/driver-methods-20261111/VCSEL';OUT=ROOT/'evidence/driver-methods-20261111/vcsel-validation.json'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 checked=[]
 for mp in sorted(BUILD.glob('*/*/manifest.json')):
  p=mp.parent
  if not (p/'result.json').exists():continue
  m=json.loads(mp.read_text());r=json.loads((p/'result.json').read_text());assert r['simulation_ok']
  assert sha(p/'testbench.spice')==m['deck_sha256'] and sha(p/'stimulus.json')==m['stimulus_sha256']
  assert sha(p/'execution-source.py')==m['execution_source_sha256']
  for item in m['execution_helpers'].values():assert sha(p/'execution-sources'/item['copy'])==item['sha256']
  for f in ['design.ngspice','sm141064.ngspice','vcsel.spice','driver.spice']:assert sha(p/f)==m['source_sha256'][f]
  lines=[x.split() for x in (p/'driver.spice').read_text().splitlines() if x.startswith('X')];devices={d['instance']:d for d in m['devices']}
  assert set(x[0] for x in lines)==set(devices)==set(s['instance'] for s in r['stress'])
  top={'D':'d','DB':'db','OUT':'out','VLASER':'vlaser','VDD':'vdd','VREF':'vref','VSET':'vset','VREGSET':'vregset','VL':'vl','VSS':'0'}
  for x in lines:
   expected=[top.get(n,'xdrv.'+n.lower()) for n in x[1:5]];d=devices[x[0]]
   assert d['nodes']==expected,(p.name,x[0],d['nodes'],expected)
   assert d['model']==x[5] and d['parameters']==x[6:]
   for n in expected:
    if n!='0':assert 'v('+n+')' in m['expressions'],(x[0],n)
  single=m['candidate_spec'].get('single_stage',False);assert len(lines)==(69 if single else 73)
  if single:assert all('v(xdrv.'+n+')' not in m['expressions'] for n in ['np','nn'])
  if m['method_config']['candidate']=='vc-single-r150':
   frozen=json.loads((ROOT/'evidence/driver-methods-20261111/vcsel-selection.json').read_text())
   assert m['candidate_spec']==frozen['candidate_spec_frozen']
   assert m['source_sha256']['driver.spice']==frozen['driver_sha256']
   assert next(x for x in (p/'testbench.spice').read_text().splitlines() if x.startswith('XDRV '))==frozen['xdrv_instance_line_frozen']
  assert len(m['ports'])==7
  if m['method_config']['level'] is not None:
   assert r['DC_screen_pass'] and abs(r['error_percent'])<=1
  else:
   assert set(r['energy_by_port'])==set(m['ports'])
   for k in ['positive_J','returned_J','net_J']:assert math.isclose(sum(v[k] for v in r['energy_by_port'].values()),r['total_energy'][k],rel_tol=1e-10,abs_tol=1e-22)
   assert math.isclose(r['total_energy']['positive_J']-r['total_energy']['returned_J'],r['total_energy']['net_J'],rel_tol=1e-10,abs_tol=1e-22)
   a=json.loads((p/'analysis.json').read_text());assert a['result_sha256']==sha(p/'result.json') and a['manifest_sha256']==sha(mp)
   assert a['pathways']['actual_graph_5GHzRX']['validation_bits']==4096
   assert sha(p/'waveform.dat.gz')==r['waveform']['sha256']
  checked.append({'case':str(p.relative_to(ROOT)),'MOS':len(lines),'manifest_sha256':sha(mp),'result_sha256':sha(p/'result.json')})
 out={'status':'PASS','cases':checked,'checks':['ActualMOSconnections/parameters==metadata==stressinventory','AllmeasuredMOSterminalnodesexported','Deck/stimulus/model/helper/executionsourcehashes','73or69MOSexact','DCwithin1percent','All7sourceportsandenergyarithmetic','Waveformgziphash','4096validationbits'],'limitations':'These consistency checks do not qualify PVT, layout, startup, BER, model accuracy or convergence at other settings.'};OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(out,indent=2)+'\n');print('PASS',len(checked),'cases')
if __name__=='__main__':main()
