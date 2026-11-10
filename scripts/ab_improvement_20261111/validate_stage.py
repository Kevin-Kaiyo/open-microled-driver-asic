#!/usr/bin/env python3
"""Independent evidence audit; never edits raw runs or previous-stage evidence.

This checks inventories, arithmetic, native log measurements, file identities,
frame construction and decision contracts. It does not independently solve SPICE
or turn nominal simulated screens into BER/physical/silicon qualification.
"""
import argparse, datetime, gzip, hashlib, importlib.util, itertools, json, re, sys
from pathlib import Path
import numpy as np
sys.dont_write_bytecode=True
EXECUTION_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/ab-improvement-20261111'; EV=ROOT/'evidence/ab-improvement-20261111'
BASE=ROOT/'build/blue-emitter-speed-review-20261110/microled'
CACHE=BUILD/'audit/waveform-validation-cache.json'
ETA=32/37
PORTS={'VIN':'vin_src','VDD':'vdd_src','VREF':'vref_src','VLED':'led_src','VD0':'data0_src','VD1':'data1_src','VDISABLE':'disable'}
MOS={'nfet_03v3','pfet_03v3','nfet_06v0','pfet_06v0'}

def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def close(a,b,rtol=2e-10,atol=1e-18):
 assert np.isclose(a,b,rtol=rtol,atol=atol),(a,b)
def num(s):
 m=re.fullmatch(r'([+-]?(?:\d*\.\d+|\d+\.?\d*)(?:e[+-]?\d+)?)([a-z]*)',s.lower());assert m,s
 return float(m[1])*{'':1,'t':1e12,'g':1e9,'meg':1e6,'k':1e3,'m':1e-3,'u':1e-6,'n':1e-9,'p':1e-12,'f':1e-15}[m[2]]
def module(p,name):
 sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def lines(text):
 out=[]
 for line in text.splitlines():
  line=line.strip()
  if not line or line.startswith('*'):continue
  if line.startswith('+'):out[-1]+=' '+line[1:]
  else:out.append(line)
 return out

def inventory(work,deck):
 """Expand the actually instantiated design subcircuits, independently of runner metadata."""
 defs={}
 for p in [work/'inputs/common.spice',work/f'inputs/route_{read(work/"manifest.json")["route"].lower()}.spice']:
  current=None
  for line in lines(p.read_text()):
   ts=line.lower().split()
   if ts[0]=='.subckt':
    current=ts[1];end=ts.index('params:') if 'params:' in ts else len(ts);defs[current]=(ts[2:end],[])
   elif ts[0]=='.ends':current=None
   elif current:defs[current][1].append(ts)
 top=next(x.lower().split() for x in lines(deck) if x.upper().startswith('XDRV ')); devices=[];passives=[]
 def expand(ts,prefix,pinmap):
  no=lambda n:'0' if n=='0' else pinmap.get(n,prefix+'.'+n)
  plain=[x for x in ts[1:] if '=' not in x];model=plain[-1];nodes=plain[:-1];inst=prefix+'.'+ts[0] if prefix else ts[0]
  mapped=[no(n) if prefix else n for n in nodes]
  if model in MOS:
   assert len(nodes)==4
   devices.append(dict(instance=inst,nodes=mapped,model=model));return
  if model=='ppolyf_u_1k_6p0':passives.append(dict(instance=inst,model=model,nodes=mapped));return
  assert model in defs,('Unknown subckt',model)
  pins,body=defs[model];assert len(pins)==len(mapped)
  local=dict(zip(pins,mapped))
  for child in body:
   if child[0].startswith('x'):expand(child,inst,local)
   elif child[0].startswith(('r','c','l')):passives.append(dict(instance=inst+'.'+child[0],model=child[0][0],nodes=[local.get(n,inst+'.'+n) if n!='0' else '0' for n in child[1:3]],value=child[3]))
   elif child[0].startswith('.'):continue
   else:raise AssertionError(('Unexpected internal active source/device',child))
 expand(top,'',{})
 return devices,passives

def wave_audit(folder,r,cache):
 p=folder/'waveform.dat.gz';gzsha=sha(p);assert gzsha==r['gzip_sha256']
 key=gzsha;old=cache.get(key)
 if old and old['raw_sha256']==r['raw_sha256']:return {**old,'cache_reused_for_identical_gzip_bytes':True}
 with gzip.open(p,'rb') as f:rawsha=hashlib.file_digest(f,'sha256').hexdigest()
 assert rawsha==r['raw_sha256']
 # Only time/current are needed for frame and domain checks. Full data for OP.
 dc=r['case'].get('kind')=='dc'
 a=np.loadtxt(p,skiprows=1,ndmin=2,usecols=None if dc else (0,1));assert np.isfinite(a).all()
 info=dict(raw_sha256=rawsha,gzip_sha256=gzsha,samples=len(a),time_first=float(a[0,0]),time_last=float(a[-1,0]),
           current_min_A=float(a[:,1].min()),current_max_A=float(a[:,1].max()),
           max_step_s=float(np.diff(a[:,0]).max()) if len(a)>1 else None,
           mean_current_A=float(np.trapezoid(a[:,1],a[:,0])/a[-1,0]) if len(a)>1 else float(a[0,1]))
 if dc:info['OP_values']=a[0].tolist()
 else:assert np.all(np.diff(a[:,0])>0)
 cache[key]=info;CACHE.parent.mkdir(parents=True,exist_ok=True);CACHE.write_text(json.dumps(cache)+'\n')
 return {**info,'cache_reused_for_identical_gzip_bytes':False}

def frame_audit(work,deck,c,st):
 assert len(st['bits'])==4736 and st['symbols_N']==st['bits']
 assert st['ranges_bits']['training_scoring']==[64,512] and st['ranges_bits']['validation']==[576,4672]
 assert st['ranges_bits']['training']==[64,576];close(st['eta'],ETA)
 state=st['seed'];bits=[]
 for _ in range(4736):bits.append((state>>14)&1);state=((state<<1)&0x7fff)|(((state>>14)^(state>>13))&1)
 assert bits==st['bits'],'PRBS labels mismatch'
 defs={x.split()[0].upper():x for x in lines(deck)}
 libs=[x.split()[-1] for x in lines(deck) if x.lower().startswith('.lib ')];assert libs==[c['corner'],'res_'+c.get('res_corner',c['corner'])]
 includes=[x.split()[1].strip(chr(34)) for x in lines(deck) if x.lower().startswith('.include ')];assert includes==['../../inputs/pdk/design.ngspice','../../inputs/common.spice','../../inputs/route_'+c['route'].lower()+'.spice','../../inputs/led.spice']
 assert 'sw_stat_global=0 sw_stat_mismatch=0' in deck
 assert float(defs['.TEMP'].split()[1])==c['temp_C']
 assert defs['RPKG'].lower()=='rpkg led_k pk 1';close(num(defs['LPKG'].split()[-1]),.5e-9)
 assert defs['CLED'].split()[1:3]==['led_a','led_k'];close(num(defs['CLED'].split()[3]),c['led_cap_F']);close(c['led_cap_F'],200e-15)
 for port,node in PORTS.items():assert defs[port].split()[1:3]==[node,'0']
 voltages={'VIN':c.get('vin_V',5),'VDD':c['vdd_V'],'VREF':2.5*(1+c.get('reference_error',0)),'VLED':c.get('vled_V',5),'VDISABLE':0}
 for port,value in voltages.items():close(num(defs[port].split()[3]),value)
 for port in ['RD0','RD1']:close(num(defs[port].split()[3]),100)
 assert {x.split()[0].upper() for x in lines(deck) if x[0].upper()=='V'}==set(PORTS)|{'VSENSE'}
 if c.get('kind')=='dc':
  close(num(defs['VD0'].split()[3]),c['level']*c['vdd_V']);close(num(defs['VD1'].split()[3]),0);assert 'op' in defs['OP'].lower();return
 ui=ETA/c['net_rate_Gbps']/1e9;end=4736*ui
 tr=list(map(num,defs['TRAN'].split()[1:]));np.testing.assert_allclose(tr,[ui/c['steps_per_symbol'],end,0,ui/c['steps_per_symbol']],rtol=2e-14,atol=1e-23)
 expected=[0,bits[0]*c['vdd_V']]
 for k in range(1,len(bits)):
  if bits[k]!=bits[k-1]:expected.extend([k*ui,bits[k-1]*c['vdd_V'],k*ui+20e-12,bits[k]*c['vdd_V']])
 expected.extend([end,bits[-1]*c['vdd_V']])
 for port,want in [('VD0',expected),('VD1',[0,0,end,0])]:
  raw=re.search(r'PWL\((.*)\)',defs[port],re.I);assert raw
  got=list(map(float,raw[1].split()));np.testing.assert_allclose(got,want,rtol=1e-13,atol=1e-23)


def case_audit(p,cache,manifest_cache):
 folder=p.parent;work=p.parents[2];r=read(p);c=r['case'];m=read(work/'manifest.json');meta=r['metadata'];deck=(folder/'testbench.spice').read_text();st=read(work/'stimulus.json')
 assert sha(work/'manifest.json')==r['manifest_sha256'];assert sha(folder/'testbench.spice')==r['deck_sha256'];assert read(folder/'case.json')==c
 if work.name not in manifest_cache:
  for name,h in m['inputs'].items():assert sha(work/'inputs'/name)==h,(work.name,name)
  for name,h in m['execution_sources'].items():assert sha(work/'execution-sources'/name)==h,(work.name,name)
  assert sha(work/'stimulus.json')==m['stimulus_sha256'];assert m['inputs']['led.spice']==read(BASE/'manifest.json')['inputs']['led.spice']
  assert sha(ROOT/'scripts/blue_emitter_speed_20261110/analyze.py')==m['receiver_sha256'];assert sha(ROOT/'scripts/microled_dynamic_v1/analyze.py')==m['dynamics_sha256']
  manifest_cache[work.name]=True
 source=folder/r['execution_source'] if 'execution_source'in r else work/'execution-sources/improvement-engine.py'
 assert sha(source)==r['engine_sha256'];frame_audit(work,deck,c,st)
 dev,passives=inventory(work,deck);assert dev==meta['devices'];assert meta['sources']==PORTS
 pars={**m['parameters'][c['route']],**c.get('parameters',{})};assert pars==meta['parameters']
 xline=next(x for x in lines(deck) if x.startswith('XDRV '));actual={k.upper():num(v) for k,v in re.findall(r'(\w+)=([^ ]+)',xline)}
 assert set(actual)==set(pars)
 for k,v in pars.items():close(actual[k],v)
 out=dict(candidate=work.name,case=c['name'],route=c['route'],kind=c.get('kind','transient'),source_case=str(folder.relative_to(ROOT)),result_sha256=sha(p),manifest_sha256=sha(work/'manifest.json'),deck_sha256=sha(folder/'testbench.spice'),execution_sha256=sha(source),MOS_count=len(dev),passive_count=len(passives),energy_port_count=len(PORTS),actual_inventory_sha256=hashlib.sha256(json.dumps(dev,sort_keys=True).encode()).hexdigest())
 if not r['simulation_ok'] or r.get('analysis_error'):return {**out,'retained_solver_failure':True,'reason':r.get('analysis_error',r['exit_code'])}
 w=wave_audit(folder,r,cache);metric=r['metrics'];close(w['mean_current_A'],metric['i_led_A'] if c.get('kind')=='dc' else metric['mean_LED_current_A'],rtol=2e-9)
 assert w['samples']==metric['sample_count'];out.update(waveform_gzip_sha256=w['gzip_sha256'],waveform_raw_sha256=w['raw_sha256'],native_samples=w['samples'])
 expr=next(x for x in lines(deck) if x.startswith('wrdata waveform.dat ')).split()[2:]
 for key,col in meta['vectors'].items():
  desired='i(vsense)' if key=='iled_cond' else ('v('+PORTS[key[:-8]]+')' if key.endswith('_voltage') else ('i('+key[:-8]+')' if key.endswith('_current') else 'v('+key+')'))
  assert expr[col-1].lower()==desired.lower(),(key,expr[col-1],desired)
 scalars={k:float(v) for k,v in re.findall(r'^([a-z][a-z0-9]*)\s*=\s*([-+0-9.eE]+)\s*$',(folder/'ngspice.log').read_text(),re.M)}
 dc=c.get('kind')=='dc';stress=[];vec=meta['vectors'];op=w.get('OP_values')
 for k,d in enumerate(dev):
  if dc:
   v=[0 if n=='0' else op[vec[n]] for n in d['nodes']];peak=max(abs(v[a]-v[b]) for a,b in itertools.combinations(range(4),2));body=max((v[3]-v[i])*(1 if d['model'].startswith('nfet') else -1) for i in [0,2])
  else:
   def voltage(n):return '0' if n=='0' else f'v({n})'
   for j,(a,b) in enumerate(itertools.combinations(d['nodes'],2)):
    assert f'let fs{k}x{j}=vecmax(abs({voltage(a)}-{voltage(b)}))' in deck
   for i in [0,2]:assert f'let fb{k}x{i}=vecmax({1 if d["model"].startswith("nfet") else -1}*({voltage(d["nodes"][3])}-{voltage(d["nodes"][i])}))' in deck
   peak=max(scalars[f'fs{k}x{j}'] for j in range(6));body=max(scalars[f'fb{k}x{i}'] for i in [0,2])
  limit=3.63 if '03v3' in d['model'] else 6.;s=metric['stress'][k]
  assert s['instance']==d['instance'] and s['model']==d['model'];close(s['max_pair_V'],peak,atol=2e-12);close(s['max_body_forward_V'],body,atol=2e-12);close(s['limit_V'],limit);assert s['passed']==(peak<=limit)
  stress.append((peak<=limit,body))
 terminal=all(x[0] for x in stress);bodymax=max(x[1] for x in stress);assert metric['device_voltage_passed']==terminal;close(metric['max_body_forward_V'],bodymax,atol=2e-12)
 assert set(metric['energy'])==set(PORTS)
 if dc:
  total=0
  for port in PORTS:
   power=-op[vec[port+'_voltage']]*op[vec[port+'_current']];close(metric['energy'][port]['DC_power_W'],power,rtol=2e-9);total+=power
  close(metric['DC_power_W'],total,rtol=2e-9);target=[25e-6,100e-6][c['level']];err=100*(op[1]/target-1);close(metric['target_A'],target);close(metric['current_error_percent'],err,atol=1e-9)
  passed=abs(err)<=1 and terminal and bodymax<=.3;assert r['DC_screen_pass']==passed
  out.update(current_uA=op[1]*1e6,DC_error_percent=err,DC_screen_pass=passed)
 else:
  end=4096/(c['net_rate_Gbps']*1e9);close(w['time_last'],end,rtol=2e-13);close(meta['frame_duration_s'],end);assert w['max_step_s']<=ETA/(c['net_rate_Gbps']*1e9*c['steps_per_symbol'])*(1+1e-6)
  energy={k:0. for k in ['positive','returned','net']}
  for j,(port,node) in enumerate(PORTS.items()):
   assert f'let fp=-v({node})*i({port})' in deck
   e=metric['energy'][port]
   for k,token in [('positive','p'),('returned','r')]:close(e[k+'_J'],scalars[f'fe{j}{token}']);assert e[k+'_J']>=-1e-22
   close(e['net_J'],e['positive_J']-e['returned_J']);close(e['native_clipped_trapezoid_crossing_correction_J'],scalars[f'fe{j}c'])
   for k in energy:energy[k]+=e[k+'_J']
  a=r['analysis']
  for k,total in energy.items():close(metric['total_energy'][k+'_J'],total);close(metric['total_energy'][k+'_pJ_per_payload_bit'],total*1e12/4096);close(a['energy_pJ_per_attempted_payload_bit'][k],total*1e12/4096)
  close(a['current_range_uA'][0],w['current_min_A']*1e6);close(a['current_range_uA'][1],w['current_max_A']*1e6)
  domain=w['current_min_A']>=.1e-6 and w['current_max_A']<=.032
  for receiver in ['full_receiver','electrical_receiver']:
   q=a[receiver];assert q['validation_bits']==4096;correct=q['errors']==q['train_errors']==0;passed=correct and q['worst_signed_margin_uAeq']>=7.5 and q['one_sided_margin_bit_UI']>=.37
   assert q['zero_error']==correct and q['research_margin_pass']==passed;close(q['one_sided_margin_ps'],q['one_sided_margin_bit_UI']*ETA/c['net_rate_Gbps']*1000,atol=1e-8);close(q['delay_bit_UI']*64,round(q['delay_bit_UI']*64));assert 0<=q['delay_bit_UI']<=8
   assert sum(v['occurrences'] for v in q['transition_symbol_errors'].values())==4096;assert sum(v['errors'] for v in q['transition_symbol_errors'].values())==q['symbol_errors']
  combined=a['full_receiver']['research_margin_pass'] and terminal and bodymax<=.3 and domain
  assert a['combined_screen_pass']==combined and a['body_screen_pass']==(bodymax<=.3) and a['terminal_screen_pass']==terminal and a['static_IV_domain_pass']==domain
  out.update(rate_Gbps=c['net_rate_Gbps'],line_Gbps=c['net_rate_Gbps']/ETA,frame_s=end,source_positive_J=energy['positive'],source_positive_pJ=energy['positive']*1e12/4096,mean_source_positive_mW=energy['positive']/end*1e3,combined_screen_pass=combined,steps=c['steps_per_symbol'])
 out['integrity_pass']=True;return out


def training_control():
 sys.path.insert(0,str(ROOT/'scripts/blue_emitter_speed_20261110'))
 a=module(ROOT/'scripts/blue_emitter_speed_20261110/analyze.py','audit_receive');controls=module(ROOT/'scripts/blue_emitter_speed_20261110/receiver_controls.py','audit_rx_control');rx=module(BASE/'execution-sources/receiver_equal_latency_v2.py','audit_helpers');st=read(BASE/'stimulus.json');t,y,ui=controls.synthetic_trace(st,'A',3.2);base=a.receive(t,y,st,'A',3.2,rx);damaged=y.copy();mask=t>=576*ui;damaged[mask]=62.5+300*np.sin(t[mask]/ui);other=a.receive(t,damaged,st,'A',3.2,rx)
 assert base['research_margin_pass'] and other['errors']>0 and other['delay_bit_UI']==base['delay_bit_UI'] and other['train_errors']==base['train_errors']
 return dict(passed=True,validation_only_waveform_change_keeps_training_phase=True,baseline_errors=base['errors'],counterfactual_errors=other['errors'],phase_bit_UI=base['delay_bit_UI'],source_sha256=sha(ROOT/'scripts/blue_emitter_speed_20261110/analyze.py'))


def vcsel_identities(cache):
 records=[]
 for p in sorted((BUILD/'VCSEL').glob('*/*/result.json')):
  folder=p.parent;m=read(folder/'manifest.json');r=read(p);wave=folder/'waveform.dat.gz';gzsha=sha(wave)
  assert gzsha==r['waveform']['sha256'];rawsha=r['waveform']['raw_sha256'];key='vcsel:'+gzsha
  if not(cache.get(key) and cache[key]['raw_sha256']==rawsha):
   with gzip.open(wave,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==rawsha
   cache[key]={'raw_sha256':rawsha};CACHE.write_text(json.dumps(cache)+'\n')
  assert sha(folder/'testbench.spice')==m['deck_sha256'];assert sha(folder/'ngspice.log')==r['log_sha256']
  for name,h in m['source_sha256'].items():assert sha(ROOT/'scripts/vcsel_robustness_20261029/run_r10.py' if name=='runner.py' else folder/name)==h
  assert sha(ROOT/'scripts/highspeed_workbench_20261110/vcsel_x10_run.py')==m['run_script_sha256'];assert sha(ROOT/'scripts/highspeed_workbench_20261110/vcsel_x10_analyze.py')==m['analysis_sha256'];assert sha(ROOT/'scripts/ab_improvement_20261111/vcsel_improve.py')==m['wrapper_sha256']
  if 'execution_source_sha256' in m:
   assert sha(folder/'execution-source.py')==m['execution_source_sha256']
   for helper in m['execution_helpers'].values():assert sha(folder/'execution-sources'/helper['copy'])==helper['sha256']
  assert sha(folder/'stimulus.json')==m['stimulus_sha256']
  deck=(folder/'testbench.spice').read_text();defs={x.split()[0].upper():x for x in lines(deck)};st=read(folder/'stimulus.json')
  assert defs['.TEMP'].split()[1]=='25' and defs['.LIB'].split()[-1]=='typical'
  assert defs['XVCSEL'].split()[1:5]==['vl','vc_k','jmon','vcsel_research'];close(num(defs['XVCSEL'].split()[5].split('=')[1]),150e-15)
  assert defs['RPKG'].split()[1:3]==['vc_k','vc_a'];close(num(defs['RPKG'].split()[3]),.5)
  assert defs['LPKG'].split()[1:3]==['vc_a','out'];close(num(defs['LPKG'].split()[3]),.2e-9)
  for port,value in [('VLASER',3.3),('VDD',3.3),('VREF',3.3),('VSET',.15),('VREGSET',.3263157894736842)]:close(num(defs[port].split()[3]),value)
  assert len(st['bits'])==4736 and st['ranges_bits']['training_scoring']==[64,512] and st['ranges_bits']['validation']==[576,4672]
  if not folder.name.startswith('DC'):
   ui=ETA/m['net_Gbps']/1e9;end=4736*ui;np.testing.assert_allclose(list(map(num,defs['TRAN'].split()[1:])),[ui/m['steps_per_UI'],end,0,ui/m['steps_per_UI']],rtol=1e-13,atol=1e-23)
   for port,bits in [('VD',st['bits']),('VDB',[1-b for b in st['bits']])]:
    expected=[0,3.3*bits[0]]
    for k in range(1,len(bits)):
     if bits[k]!=bits[k-1]:expected.extend([k*ui,3.3*bits[k-1],k*ui+20e-12,3.3*bits[k]])
    expected.extend([end,3.3*bits[-1]]);got=list(map(float,re.search(r'PWL\((.*)\)',defs[port],re.I)[1].split()));np.testing.assert_allclose(got,expected,rtol=1e-13,atol=1e-23)
  driver={ts[0]:ts for line in (folder/'driver.spice').read_text().splitlines() if (ts:=line.split()) and len(ts)>5 and ts[5] in ['nmos_3p3','pmos_3p3']}
  assert len(driver)==len(m['devices'])==len(r['stress'])==73
  top=next(x.lower().split() for x in lines((folder/'testbench.spice').read_text()) if x.lower().startswith('xdrv '));definition=next(x.lower().split() for x in lines((folder/'driver.spice').read_text()) if x.lower().startswith('.subckt '));pins=definition[2:definition.index('params:')];mapping=dict(zip(pins,top[1:1+len(pins)]))
  for d,sr in zip(m['devices'],r['stress']):
   words=driver[d['instance']];nodes=[mapping.get(x.lower(),'xdrv.'+x.lower()) if x!='0' else '0' for x in words[1:5]]
   assert nodes==d['nodes'] and words[5]==d['model'] and words[6:]==d['parameters'];assert sr['instance']==d['instance'];assert len(sr['max_abs_terminal_V'])==6
   assert sr['screen_pass']==(all(x<=3.63 for x in sr['max_abs_terminal_V'].values()) and sr['max_body_forward_V']<=.3)
  assert r['terminal_screen_pass']==all(s['screen_pass'] for s in r['stress']);close(r['max_body_forward_V'],max(s['max_body_forward_V'] for s in r['stress']))
  if not folder.name.startswith('DC'):
   a=read(folder/'analysis.json');assert a['result_sha256']==sha(p);assert a['manifest_sha256']==sha(folder/'manifest.json');close(m['line_GBd'],m['net_Gbps']/ETA);close(m['end_s'],4096/(m['net_Gbps']*1e9));assert m['frame_bits']==4736 and m['attempted_payload_bits']==4096
   assert len(m['ports'])==len(r['energy_by_port'])==7
   for kind in ['positive','returned','net']:
    total=sum(x[kind+'_J'] for x in r['energy_by_port'].values());close(r['total_energy'][kind+'_J'],total);close(a['source_energy_pJ_per_attempted_net_bit'][kind],total*1e12/4096)
  records.append(dict(source_case=str(folder.relative_to(ROOT)),result_sha256=sha(p),manifest_sha256=sha(folder/'manifest.json'),waveform_gzip_sha256=gzsha,waveform_raw_sha256=rawsha,MOS_count=73,passed=True))
 return records


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--final',action='store_true');args=ap.parse_args();cache=read(CACHE) if CACHE.exists() else {};errors=[];pending=[];rows=[];manifest_cache={}
 initial_result_paths=sorted(BUILD.glob('*/cases/*/result.json'))
 for p in initial_result_paths:
  try:rows.append(case_audit(p,cache,manifest_cache));print('CHECK',str(p.parent.relative_to(BUILD)),flush=True)
  except Exception as e:errors.append(dict(path=str(p.relative_to(ROOT)),error=repr(e)));print('FAIL',p,e,flush=True)
 for p in BUILD.glob('*/cases/*/case.json'):
  if not (p.parent/'result.json').exists():pending.append('unfinished case: '+str(p.parent.relative_to(ROOT)))
 try:control=training_control()
 except Exception as e:control={'passed':False};errors.append(dict(check='training control',error=repr(e)))
 summary_path=EV/'summary.json';summary_bytes=summary_path.read_bytes() if summary_path.exists() else None;summary=json.loads(summary_bytes) if summary_bytes is not None else None;summary_hash=hashlib.sha256(summary_bytes).hexdigest() if summary_bytes is not None else None
 if summary:
  indexed={x['source_case']:x for x in rows}
  for group in ['DC','transient','solver_failures']:
   for x in summary[group]:
    try:
     y=indexed[x['source_case']];assert y['result_sha256']==x['result_sha256'];assert y['manifest_sha256']==x['manifest_sha256'];assert y['deck_sha256']==x['deck_sha256']
     for k in ['waveform_gzip_sha256','waveform_raw_sha256']:
      if k in y:assert y[k]==x[k]
     if group=='DC':close(y['current_uA'],x['current_uA']);close(y['DC_error_percent'],x['error_percent'],atol=1e-8);assert y['DC_screen_pass']==x['DC_screen_pass']
     elif group=='transient':
      assert x['MOS_count']==y['MOS_count'];close(x['energy_pJ_per_attempted_payload_bit']['positive'],y['source_positive_pJ']);c=x['case'];dc=[d for d in summary['DC'] if d['candidate']==x['candidate'] and d['case'].get('parameters',{})==c.get('parameters',{}) and all(d['case'].get(k)==c.get(k) for k in ['corner','temp_C','vdd_V','vin_V','vled_V','reference_error','res_corner'])];match=all(any(d['case']['level']==level and d['DC_screen_pass'] for d in dc) for level in [0,1]);assert x['matched_DC_levels_pass']==match;assert x['joint_screen_pass']==(match and y['combined_screen_pass'])
    except Exception as e:errors.append(dict(check='summary mapping',source=x['source_case'],error=repr(e)))
  represented={x['source_case'] for g in ['DC','transient','solver_failures'] for x in summary[g]};expected={x['source_case'] for x in rows if 'holdout' not in x['candidate']}
  if represented!=expected:pending.append('summary does not cover all completed development cases')
 else:pending.append('summary.json missing')
 baseline=[]
 for candidate,route,rate in [('a-base','A',1.6),('B_baseline','B',.8)]:
  try:
   p=BUILD/candidate/'cases'/f'TT-net{rate:g}-C200-S40/result.json';new=read(p);old=read(BASE/'cases'/f'TT-{route}-net{rate:g}-C200fF-S40/result.json');checks={}
   for key in ['i_led_A','max_body_forward_V']:close(new['metrics'][key],old['metrics'][key],rtol=1e-8,atol=1e-12)
   for key in ['positive_J','returned_J','net_J']:close(new['metrics']['total_energy'][key],old['metrics']['total_energy'][key],rtol=1e-8)
   assert new['metadata']['devices']==old['metadata']['devices'];baseline.append(dict(candidate=candidate,rate=rate,passed=True,old_result_sha256=sha(BASE/'cases'/f'TT-{route}-net{rate:g}-C200fF-S40/result.json')))
  except Exception as e:errors.append(dict(check='baseline reproduction',candidate=candidate,error=repr(e)))
 protocol=read(EV/'holdout-protocol.json');state=protocol['baseline_seed']
 for _ in range(protocol['phase_offset_in_PRBS15_period_bits']):state=((state<<1)&0x7fff)|(((state>>14)^(state>>13))&1)
 if state!=protocol['holdout_seed'] or not (4736<=protocol['phase_offset_in_PRBS15_period_bits']<=32767-4736):errors.append(dict(check='holdout PRBS phase',error='phase/window mismatch'))
 selection_path=EV/'selection.json';selection_bytes=selection_path.read_bytes() if selection_path.exists() else None;selection=json.loads(selection_bytes) if selection_bytes is not None else None;selection_hash=hashlib.sha256(selection_bytes).hexdigest() if selection_bytes is not None else None;selected_checks=[]
 if selection and summary:
  for route in ['A','B']:
   try:
    s=selection[route];candidate=s['candidate'];rate=s['highest_passing_Gbps'];envelope=next(x for x in summary['envelopes'] if x['candidate']==candidate);assert envelope['highest_passing_tested_Gbps']==rate;assert envelope['next_failing_tested_Gbps']==s['next_failing_Gbps']
    sweep=[x for x in summary['transient'] if x['candidate']==candidate and x['case']['steps_per_symbol']==40 and x['case']['corner']=='typical' and x['case']['temp_C']==27 and x['case']['vdd_V']==3.3 and abs(x['case']['led_cap_F']-200e-15)<1e-25];assert max(x['case']['net_rate_Gbps'] for x in sweep if x['joint_screen_pass'])==rate;higher_fail=[x['case']['net_rate_Gbps'] for x in sweep if x['case']['net_rate_Gbps']>rate and not x['joint_screen_pass']];assert (min(higher_fail) if higher_fail else None)==s['next_failing_Gbps']
    target=next(x for x in summary['transient'] if x['candidate']==candidate and x['case']['net_rate_Gbps']==3.2 and x['case']['steps_per_symbol']==40)
    selected=[x for x in summary['transient'] if x['candidate']==candidate and x['case']['net_rate_Gbps']==rate];coarse=next(x for x in selected if x['case']['steps_per_symbol']==40);fine=next(x for x in selected if x['case']['steps_per_symbol']==80);assert coarse['joint_screen_pass'] and fine['joint_screen_pass']
    def normstep(t):return re.sub(r'(?m)^tran .*$', '<tran>',t).splitlines()[1:]
    assert normstep((ROOT/coarse['source_case']/'testbench.spice').read_text())==normstep((ROOT/fine['source_case']/'testbench.spice').read_text())
    h=read(EV/f'{route.lower()}-holdout.json');assert h['candidate']==candidate and h['rate_Gbps']==rate and h['analysis']['combined_screen_pass'];hp=ROOT/h['source_case'];assert sha(hp/'result.json')==h['result_sha256'];hm=read(hp.parents[1]/'manifest.json');cm=read(BUILD/candidate/'manifest.json');assert hm['inputs']==cm['inputs'];assert hm['holdout_provenance']['source_manifest_sha256']==sha(BUILD/candidate/'manifest.json');assert hm['holdout_provenance']['source_result_sha256']==coarse['result_sha256'];assert hm['holdout_provenance']['protocol_sha256']==sha(EV/'holdout-protocol.json');assert read(hp.parents[1]/'stimulus.json')['seed']==0x317e
    norm=lambda t:re.sub(r'(?m)^VD[01] data[01]_src 0 .*$', '<data>',t)
    assert norm((hp/'testbench.spice').read_text())==norm((ROOT/coarse['source_case']/'testbench.spice').read_text())
    selected_checks.append(dict(route=route,candidate=candidate,highest_tested_Gbps=rate,halfstep_pass=True,holdout_pass=True,target_3p2_tested=True,target_3p2_pass=target['joint_screen_pass']))
   except (FileNotFoundError,StopIteration,KeyError) as e:pending.append('selected candidate validation incomplete '+route+': '+repr(e))
   except Exception as e:errors.append(dict(check='selected candidate',route=route,error=repr(e)))
 else:pending.append('selection.json missing')
 for name in ['vcsel-validation.json','energy-storage-audit.json','ideal-bounds.json']:
  if not (EV/name).exists():pending.append(name+' missing')
 try:
  vc=read(EV/'vcsel-validation.json');assert vc.get('passed',vc.get('all_passed',False))
  for path,h in vc['source_hashes'].items():assert sha(ROOT/path)==h
  vcsel_records=vcsel_identities(cache)
 except Exception as e:vcsel_records=[];errors.append(dict(check='VCSEL delegated independent audit',error=repr(e)))
 if initial_result_paths!=sorted(BUILD.glob('*/cases/*/result.json')):pending.append('completed case set changed during audit; rerun after stage freeze')
 if summary_path.exists() and sha(summary_path)!=summary_hash:pending.append('summary changed during audit; rerun after stage freeze')
 if selection_path.exists() and sha(selection_path)!=selection_hash:pending.append('selection changed during audit; rerun after stage freeze')
 obj=dict(schema='driver-improvement-scientific-validation-v1',generated_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),final_requested=args.final,integrity_pass=not errors,complete=bool(args.final and not errors and not pending),passed=bool(args.final and not errors and not pending),errors=errors,pending=pending,case_count=len(rows),vcsel_native_case_count=len(vcsel_records),vcsel_native_cases=vcsel_records,manifest_count=len(manifest_cache),cases=rows,training_counterfactual=control,baseline_reproduction=baseline,selected_controls=selected_checks,summary_sha256=summary_hash,selection_sha256=selection_hash,script_sha256=EXECUTION_SHA,limits=['No independent second SPICE solution; native exported integrals/stress are checked against actual expressions and recomputed arithmetic.','Raw waveform content hashes are freshly checked, or reuse a previous full decompression only after freshly matching the exact compressed bytes.','Fixed-frame research screens are not measured BER, PVT robustness, post-layout validation or manufacturing qualification.','A partial run never claims completion, even if all currently available evidence is consistent.'])
 (EV/'scientific-validation.json').write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n');print(json.dumps({k:obj[k] for k in ['integrity_pass','complete','case_count','errors','pending']},ensure_ascii=False));return 1 if errors or (args.final and pending) else 0
if __name__=='__main__':raise SystemExit(main())
