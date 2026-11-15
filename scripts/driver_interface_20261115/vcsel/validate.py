#!/usr/bin/env python3
"""Audit emitted interfaces, all MOS terminals, actual PWL and eight-port energies."""
import gzip,hashlib,math,re,sys
sys.dont_write_bytecode=True
import run
def main():
 checked=[];legacy=run.engine.module(run.engine.LEGACY,'interface_validation_stimulus')
 for mp in sorted(run.BUILD.glob('*/*/manifest.json')):
  p=mp.parent
  if not (p/'result.json').exists():continue
  m=run.read(mp);r=run.read(p/'result.json');cfg=m['interface_config'];spec=cfg['spec'];assert r['simulation_ok']
  if m['schema']=='vcsel-open-input-diagnostic-v1':
   source=run.ROOT/m['case_source'];parent=run.read(source/'manifest.json')
   assert run.sha(source/'manifest.json')==m['parent_manifest_sha256']
   expected,n=re.subn(r'(?m)^XPHY[^\n]*\n','',(source/'testbench.spice').read_text());assert n==4 and (p/'testbench.spice').read_text()==expected
   assert m['devices']==[x for x in parent['devices'] if not x['instance'].startswith('XPHY')]
   assert set(x['instance'] for x in m['devices'])==set(x['instance'] for x in r['stress'])
   for f in ['design.ngspice','sm141064.ngspice','vcsel.spice','driver.spice']:assert run.sha(p/f)==m['source_sha256'][f]
   for item in m['execution_helpers'].values():assert run.sha(p/'execution-sources'/item['copy'])==item['sha256']
   assert run.sha(p/'execution-source.py')==m['execution_source_sha256'] and run.sha(p/'testbench.spice')==m['deck_sha256']
   assert run.sha(p/'waveform.dat.gz')==r['waveform']['sha256']
   with gzip.open(p/'waveform.dat.gz','rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['waveform']['raw_sha256']
   assert r['pins_default_low'] and r['laser_is_not_shut_down']
   checked.append({'case':str(p.relative_to(run.ROOT)),'kind':m['diagnostic_kind'],'MOS':len(m['devices']),'manifest_sha256':run.sha(mp),'result_sha256':run.sha(p/'result.json'),'waveform':r['waveform']});continue
  assert run.sha(p/'testbench.spice')==m['deck_sha256'] and run.sha(p/'stimulus.json')==m['stimulus_sha256']
  assert run.sha(p/'execution-source.py')==m['execution_source_sha256']
  for item in m['execution_helpers'].values():assert run.sha(p/'execution-sources'/item['copy'])==item['sha256']
  for f in ['design.ngspice','sm141064.ngspice','vcsel.spice','driver.spice']:assert run.sha(p/f)==m['source_sha256'][f]
  baseline=run.ROOT/m['baseline_case'];assert run.sha(baseline/'driver.spice')==m['baseline_driver_sha256'] and run.sha(baseline/'manifest.json')==m['baseline_manifest_sha256']
  a_driver=(baseline/'driver.spice').read_text();b_driver=(p/'driver.spice').read_text()
  if 'shunt_R_ohm' in spec:
   expected,n=re.subn(r'(?m)^(RAD(?:B)?I \w+ VSS) 2500$',lambda q:q.group(1)+' '+str(spec['shunt_R_ohm']),a_driver);assert n==2 and b_driver==expected
  else:assert a_driver==b_driver
  deck=(p/'testbench.spice').read_text();lines=[x.split() for x in b_driver.splitlines() if x.startswith('X')]
  devices={d['instance']:d for d in m['devices']};top={'D':'d','DB':'db','OUT':'out','VLASER':'vlaser','VDD':'vdd','VREF':'vref','VSET':'vset','VREGSET':'vregset','VL':'vl','VSS':'0'}
  actual=[]
  for x in lines:actual.append((x,[top.get(n,'xdrv.'+n.lower()) for n in x[1:5]]))
  for s in deck.splitlines():
   if s.startswith('XPHY'):x=s.split();actual.append((x,x[1:5]))
  assert set(x[0] for x,n in actual)==set(devices)==set(s['instance'] for s in r['stress'])
  assert len(actual)==spec['core']+4
  for x,nodes in actual:
   d=devices[x[0]];assert d['nodes']==nodes and d['model']==x[5] and d['parameters']==x[6:]
   for n in nodes:
    if n!='0':assert 'v('+n+')' in m['expressions']
  assert m['ports']=={'VLASER':'laser_src','VDD':'vdd_src','VREF':'ref_src','VD':'d_cmd','VDB':'db_cmd','VSET':'set_src','VREGSET':'regset_src','VPHY':'phy_src'}
  assert 'RD d_src d 50\n' in deck and 'RDB db_src db 50\n' in deck
  assert set(re.findall(r'(?m)^(V[A-Z]+) \w+ 0 ',deck))==set(m['ports'])
  assert run.sha(p/'waveform.dat.gz')==r['waveform']['sha256']
  with gzip.open(p/'waveform.dat.gz','rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['waveform']['raw_sha256']
  if cfg['level'] is not None:
   assert r['DC_screen_pass'] and abs(r['error_percent'])<=1
  else:
   st=run.read(p/'stimulus.json');assert len(st['bits'])==4736
   ui=4096/4736/(cfg['net_Gbps']*1e9)
   for port,node,bits in [('VD','d_cmd',st['bits']),('VDB','db_cmd',[1-b for b in st['bits']])]:
    actual_pwl=re.search(rf'(?m)^{port} {node} 0 PWL\([^)]*\)',deck).group(0);assert actual_pwl==f'{port} {node} 0 '+legacy.pwl(bits,ui,3.3,20e-12),(p,port)
   assert set(r['energy_by_port'])==set(m['ports'])
   for k in ['positive_J','returned_J','net_J']:assert math.isclose(sum(v[k] for v in r['energy_by_port'].values()),r['total_energy'][k],rel_tol=1e-10,abs_tol=1e-22)
   assert math.isclose(r['total_energy']['positive_J']-r['total_energy']['returned_J'],r['total_energy']['net_J'],rel_tol=1e-10,abs_tol=1e-22)
   a=run.read(p/'analysis.json');assert a['result_sha256']==run.sha(p/'result.json') and a['manifest_sha256']==run.sha(mp)
   f=a['pathways']['actual_graph_5GHzRX'];o=a['observed'];assert f['validation_bits']==4096
   assert a['combined_screen_pass']==bool(f['screen_pass'] and o['terminal_screen_pass'] and o['max_body_forward_V']<=.3 and o['within_calibrated_electrical_and_optical_current_range'])
   if cfg['holdout']:
    assert m['holdout_protocol']==run.protocol();sel=run.read(run.EV/'vcsel-interface-selection.json');assert sel['parameters_frozen'] and cfg['candidate']==sel['candidate'] and spec==sel['spec']
    rx=run.engine.module(run.ROOT/'scripts/fair_driver_v1/receiver_equal_latency_v2.py','interface_validation_rx');assert st==legacy.seeded_stimulus(run.protocol()['holdout_seed'],rx)
  checked.append({'case':str(p.relative_to(run.ROOT)),'MOS':len(actual),'manifest_sha256':run.sha(mp),'result_sha256':run.sha(p/'result.json'),'waveform':r['waveform']})
 out={'status':'PASS','cases':checked,'checks':['Actual MOS D/G/S/B geometry equals stress inventory; all nodes saved','Source/helper/deck/model/manifest/command snapshots match byte hashes','Actual emitted command PWL matches 4736 bits,20ps edge and net32/37 convention','DC3/7mA within1percent','All8 source ports and positive/returned/net arithmetic','Compressed and decompressed native waveform SHA256','Only declared input-shunt mutation; baseline hash remains original','Frozen receiver and4096bit validation; holdout seed0x57ae phase8192'],'limits':'Consistency evidence only; not vendor PHY/PAD/ESD, PVT, layout, physical BER, optical calibration or continuous VCSEL thermal qualification.'}
 run.emit(run.EV/'vcsel-interface-validation.json',out);print('PASS',len(checked),'cases')
if __name__=='__main__':main()
