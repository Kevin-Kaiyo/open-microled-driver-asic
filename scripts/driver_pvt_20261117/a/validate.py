#!/usr/bin/env python3
"""Independent actual-deck connectivity and identity validation for new A cases.

Numerical integrity is separate from circuit pass; DC-fit failures are retained.
DC currents/power/stress recomputed from native raw. Transient full-MOS native
scalars are recomputed in SPICE by the producer, audited against actual terminals.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,re
import numpy as np
import run as a
def inventory(folder):
 deck=(folder/'testbench.spice').read_text();route=(folder.parent/'inputs/route_a.spice').read_text()
 line=next(l for l in deck.splitlines() if l.startswith('XDRV ')).split();head=next(l for l in route.splitlines() if l.startswith('.subckt ')).split();ports=head[2:head.index('params:')];i=line.index('fair_a');assert len(ports)==i-1;mapping=dict(zip([x.lower() for x in ports],[x.lower() for x in line[1:i]]));out={}
 for source,prefix in [(deck,''),(route,'xdrv.')]:
  for l in source.splitlines():
   t=l.split()
   if len(t)>6 and t[0].startswith('X') and t[5] in ['nfet_03v3','pfet_03v3','nfet_06v0','pfet_06v0']:
    nodes=[n.lower() if not prefix else mapping.get(n.lower(),prefix+n.lower()) for n in t[1:5]];out[prefix+t[0].lower()]=dict(nodes=nodes,model=t[5])
 return out
def main(final=False):
 rows=[];fail=[]
 for p in sorted(a.BUILD.glob('*/*/result.json')):
  try:
   folder=p.parent;r=a.read(p);m=a.read(folder/'manifest.json');effective={**r,**(a.read(folder/'reanalysis.json') if (folder/'reanalysis.json').exists() else {})};deck=(folder/'testbench.spice').read_text()
   assert r['manifest_sha256']==a.sha(folder/'manifest.json');assert r['deck_sha256']==m['deck_sha256']==a.sha(folder/'testbench.spice');assert m['execution_sha256']==a.sha(folder/'execution-source.py');assert a.sha(folder/'stimulus.json')==m['stimulus_sha256']
   for name,sha in m['inputs'].items():assert a.sha(folder.parent/'inputs'/name)==sha
   for src,h in m['execution_helpers'].items():assert a.sha(folder/h['path'])==h['sha256']
   assert a.sha(folder/'ngspice.log')==r['log_sha256'];assert a.sha(folder/'waveform.dat.gz')==r['gzip_sha256']
   inv=inventory(folder);meta={d['instance']:dict(nodes=d['nodes'],model=d['model']) for d in m['devices']};assert inv==meta
   assert re.search(r'(?m)^\.lib "../inputs/pdk/sm141064.ngspice" '+m['pvt']['corner']+'$',deck);assert f'.temp {m["pvt"]["temp_C"]}' in deck;assert '.lib "../inputs/pdk/sm141064.ngspice" res_typical' in deck
   assert re.search(r'(?m)^VREF vref_src 0 2.5$',deck);assert 'CLED led_a led_k 2e-13' in deck and 'RPKG led_k pk 1' in deck and 'LPKG pk out .5n' in deck
   assert a.sha(folder.parent/'inputs/led.spice')==a.sha(a.FROZEN/'inputs/led.spice')
   assert set(m['sources'])=={'VIN','VDD','VREF','VLED','VD0','VD1','VDISABLE'}
   for source,value in m['rails_V'].items():assert float(re.search(r'(?m)^'+source+r' \w+ 0 ([^\n]+)$',deck)[1])==value
   level=m['case'].get('level');native_rows=None
   if level is not None:
    raw=np.loadtxt(folder/'waveform.dat.gz',skiprows=1,ndmin=2);ix=m['vectors'];native_rows=len(raw);cur=raw[-1,ix['iled_cond']]*1e6;assert abs(cur-r['current_uA'])<1e-8
    assert r['DC_pass']==(abs(cur/(25+75*level)-1)<=.01 and r['terminal_pass'] and r['body_pass'])
    for port in m['sources']:assert abs(-raw[-1,ix[port+'_voltage']]*raw[-1,ix[port+'_current']]*1e3-r['power_mW'][port])<1e-10
    for d,s in zip(m['devices'],r['stress']):
     vv=[np.zeros(len(raw)) if n=='0' else raw[:,ix[n]] for n in d['nodes']];peak=max(np.abs(vv[j]-vv[k]).max() for j in range(4) for k in range(j+1,4));assert abs(float(peak)-s['peak_pair_V'])<1e-9
     body=max(0.,max(float((vv[3]-vv[j] if d['model'].startswith('nfet') else vv[j]-vv[3]).max()) for j in [0,2]));assert abs(body-s['body_forward_V'])<1e-9
   else:
    source=(a.ROOT/m['source_case']/'testbench.spice').read_text()
    for port in ['VD0','VD1','VDISABLE']:
     oldline=re.search(r'(?m)^'+port+r' \w+ 0 ([^\n]+)$',source)[1];new=re.search(r'(?m)^'+port+r' \w+ 0 ([^\n]+)$',deck)[1]
     if oldline.startswith('PWL('):
      x=np.array([float(v) for v in oldline[4:-1].split()]);y=np.array([float(v) for v in new[4:-1].split()]);assert len(x)==len(y);assert np.allclose(x[::2],y[::2],rtol=1e-14,atol=1e-22);assert np.allclose(x[1::2]*m['pvt']['supply_scale'],y[1::2],rtol=1e-14,atol=1e-14)
    assert m['case']['net_rate_Gbps']==1.6 and m['frame_duration_s']==4096/1.6e9
    if 'fault' in m:assert m['fault']['off_current_screen_uA']==.1 and m['fault']['settle_allowance_ns']==20 and m['fault']['recovery_allowance_us']==1
    # Stress expressions must refer to the new gates, not inherited VH/VL metadata.
    block=a.old.stress_commands(m['devices']);assert block in deck
    if not effective.get('original_analysis_error') and r.get('analysis_error'):raise AssertionError('Unresolved analysis error')
    assert effective['MOS']==len(inv)==len(effective['stress'])
    sc={k:float(v) for k,v in re.findall(r'^([a-z][a-z0-9]*)\s*=\s*([-+0-9.eE]+)\s*$',(folder/'ngspice.log').read_text(),re.M)}
    for k,(dev,stress) in enumerate(zip(m['devices'],effective['stress'])):
     assert dev['instance']==stress['instance'];assert abs(stress['peak_pair_V']-max(sc[f'fs{k}x{j}'] for j in range(6)))<1e-12
     assert abs(stress['body_forward_V']-max(0.,sc[f'fb{k}x0'],sc[f'fb{k}x2']))<1e-12
    assert effective['terminal_pass']==all(s['terminal_pass'] for s in effective['stress']);assert effective['body_pass']==all(s['body_pass'] for s in effective['stress'])
    for k,port in enumerate(m['sources']):
     for metric,key in [('positive_J','p'),('returned_J','r')]:
      reconstructed=sum(f['source_energy_J'][port][metric] for f in effective['frames']);assert abs(reconstructed-sc[f'fe{k}{key}'])<1e-18
    for f in effective['frames']:
     for metric in ['positive','returned','net']:
      value=sum(e[metric+'_J'] for e in f['source_energy_J'].values())/4096*1e12;assert abs(value-f['energy_pJ_per_attempted_payload_bit'][metric])<1e-9
     assert f['full_receiver']['validation_bits']==4096
   rows.append(dict(path=str(folder.relative_to(a.ROOT)),result_sha256=a.sha(p),actual_MOS=len(inv),native_rows=native_rows,kind='DC' if level is not None else 'fault',integrity_pass=True,circuit_DC_pass=effective.get('DC_pass'),analysis_corrected=(folder/'reanalysis.json').exists()))
  except Exception as e:fail.append(dict(path=str(p.relative_to(a.ROOT)),error=repr(e)))
 required=[a.BUILD/v/(g+'-fault-s40')/'result.json' for v,g in [('baseline','SShotlow'),('trackwide4gm5-fixed','TT'),('trackwide4gm5-fixed','SShotlow'),('trackwide4gm5-fixed','FFcoldhigh')]]
 required += [a.BUILD/v/'TT-continuous-f1-s40/result.json' for v in ['trackwide4gm5pre2-fixed','trackwide4gm5buf2-fixed']]
 pending=[str(p.relative_to(a.ROOT)) for p in required if not p.exists()]
 out=dict(schema='a-pvt-integrity-audit-v1',requested_final=final,complete=bool(final and not pending and not fail),integrity_pass=not fail,audited_cases=len(rows),cases=rows,pending=pending,failures=fail,scope='Scientific traceability and actual connectivity check. Passing this audit is not passing PVT/DC/RX/fault criteria; transient stresses use native fulltrace scalar expressions audited against actual devices. No new layout/PEX.',validator_sha256=a.sha(Path(__file__)))
 a.emit(a.EV/'validation.json',out);print(dict(complete=out['complete'],audited_cases=len(rows),pending=len(pending),failures=fail));return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');main(p.parse_args().final)
