#!/usr/bin/env python3
"""Independent read-only scientific audit of driver-methods native evidence.

Only this script's scientific-validation.json is written. No case, waveform,
prior-stage receipt or experimental circuit is modified. --final requests a
stable complete set; ordinary invocations explicitly remain partial.
"""
import argparse, datetime, gzip, hashlib, importlib.util, io, itertools, json, re, sys, traceback
from pathlib import Path
import numpy as np
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/driver-methods-20261111';EV=ROOT/'evidence/driver-methods-20261111'
OUT=EV/'scientific-validation.json';ETA=32/37
AUDIT_VERSION='driver-methods-independent-v1'

def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def module(p,name):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def close(a,b,rtol=3e-9,atol=1e-20):assert np.isclose(a,b,rtol=rtol,atol=atol),(a,b)
def finite(x):assert np.isfinite(x).all()
old=module(ROOT/'scripts/ab_improvement_20261111/validate_stage.py','prior_independent_audit')
old.CACHE=None
lines=old.lines;num=old.num

def waveform_audit(folder,r,cache):
 """Pure replacement for the old audit's disk cache; no old build writes."""
 p=folder/'waveform.dat.gz';h=sha(p);assert h==r['gzip_sha256']
 if h in cache:return cache[h]
 with gzip.open(p,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['raw_sha256']
 dc=r['case'].get('kind')=='dc'
 a=np.loadtxt(p,skiprows=1,ndmin=2,usecols=None if dc else (0,1));finite(a)
 w=dict(raw_sha256=r['raw_sha256'],gzip_sha256=h,samples=len(a),time_first=float(a[0,0]),time_last=float(a[-1,0]),current_min_A=float(a[:,1].min()),current_max_A=float(a[:,1].max()),max_step_s=float(np.diff(a[:,0]).max()) if len(a)>1 else None,mean_current_A=float(np.trapezoid(a[:,1],a[:,0])/a[-1,0]) if len(a)>1 else float(a[0,1]))
 if dc:w['OP_values']=a[0].tolist()
 else:assert np.all(np.diff(a[:,0])>0)
 cache[h]=w;return w
old.wave_audit=waveform_audit

def stimulus_check(st):
 assert len(st['bits'])==4736 and st['symbols_N']==st['bits']
 assert st['ranges_bits']['training_scoring']==[64,512]
 assert st['ranges_bits']['training']==[64,576] and st['ranges_bits']['validation']==[576,4672]
 state=st['seed'];bits=[]
 for _ in range(4736):bits.append((state>>14)&1);state=((state<<1)&32767)|(((state>>14)^(state>>13))&1)
 assert bits==st['bits'];return bits

def receiver_contract(q,rate,vc=False):
 assert q['validation_bits']==4096
 uikey='one_sided_margin_UI' if vc else 'one_sided_margin_bit_UI';delaykey='delay_UI' if vc else 'delay_bit_UI';passkey='screen_pass' if vc else 'research_margin_pass'
 good=q['errors']==q['train_errors']==0 and q['worst_signed_margin_uAeq']>=7.5 and q[uikey]>=.37
 assert q[passkey]==good
 close(q['one_sided_margin_ps'],q[uikey]*ETA/rate*1000,atol=1e-8)
 close(q['delay_ps'],q[delaykey]*ETA/rate*1000,atol=1e-8)
 close(q[delaykey]*64,round(q[delaykey]*64));assert 0<=q[delaykey]<=8
 return good

def normalized_deck(text,holdout=False,steps=False):
 text='\n'.join(lines(text.split('\n',1)[1]))
 if holdout:text=re.sub(r'(?m)^VD(?:0|1|B)? \S+ 0 .*$', '<data stimulus>',text)
 if steps:text=re.sub(r'(?m)^tran .*$', '<time step>',text)
 return text

def controls_protocol():
 micro=read(EV/'micro-protocol.json');vc=read(EV/'vcsel-holdout-protocol.json')
 assert micro['holdout_seed']==vc['holdout_seed']==0x4c2d
 state=0x5ace
 for _ in range(27081):state=((state<<1)&32767)|(((state>>14)^(state>>13))&1)
 assert state==0x4c2d
 windows=[[0,4736],[16749,21485],[27081,31817]]
 for lo,hi in windows:assert hi-lo==4736 and 0<=lo<hi<=32767
 for a,b in itertools.combinations(windows,2):assert a[1]<=b[0] or b[1]<=a[0]
 assert micro['holdout_window_in_reference_cycle']==windows[-1] and vc['new_holdout_window']==windows[-1]
 return dict(seed=state,seed_hex=hex(state),windows=windows,nonoverlap=True,scope='Non-overlapping windows from one deterministic PRBS15 cycle; not independent random BER.')

def micro_case(p,cache,mc):
 result=old.case_audit(p,cache,mc)
 r=read(p);work=p.parents[2];c=r['case'];m=read(work/'manifest.json')
 result['result_sha256']=sha(p);result['log_sha256']=sha(p.parent/'ngspice.log')
 result['audit_version']=AUDIT_VERSION
 if c.get('kind')!='dc':
  source=work
  if '-holdout4c2d' in work.name:source=work.with_name(work.name.replace('-holdout4c2d',''))
  for level in (0,1):
   dc=read(source/'cases'/f'DC-L{level}/result.json');assert dc['DC_screen_pass']
   # Current target uses same route, rails, corners, component parameters and C.
   keys=set(c)|set(dc['case']);ignore={'name','kind','level','net_rate_Gbps','steps_per_symbol','timeout_s'}
   for k in keys-ignore:assert c.get(k)==dc['case'].get(k),(work.name,k)
   assert dc['manifest_sha256']==sha(source/'manifest.json')
  result['matched_DC_levels']=[str((source/'cases'/f'DC-L{i}/result.json').relative_to(ROOT)) for i in (0,1)]
  if '-holdout4c2d' in work.name:
   assert read(work/'stimulus.json')['seed']==0x4c2d
   mm=read(source/'manifest.json');assert m['inputs']==mm['inputs'] and m['parameters']==mm['parameters']
   pp=source/'cases'/c['name']/'testbench.spice'
   assert normalized_deck(pp.read_text(),holdout=True)==normalized_deck((p.parent/'testbench.spice').read_text(),holdout=True)
   result['holdout_matches_frozen_circuit']=True
   base=read(pp.parent/'result.json')['analysis'];q=r['analysis'];result['control_comparison']=dict(type='holdout',base_pass=base['combined_screen_pass'],control_pass=q['combined_screen_pass'],delta_time_ps=q['full_receiver']['one_sided_margin_ps']-base['full_receiver']['one_sided_margin_ps'],delta_amplitude_uAeq=q['full_receiver']['worst_signed_margin_uAeq']-base['full_receiver']['worst_signed_margin_uAeq'],delta_positive_energy_percent=100*(q['energy_pJ_per_attempted_payload_bit']['positive']/base['energy_pJ_per_attempted_payload_bit']['positive']-1))
  elif c['steps_per_symbol']==80:
   pp=source/'cases'/c['name'].replace('-S80','-S40')/'testbench.spice'
   assert normalized_deck(pp.read_text(),steps=True)==normalized_deck((p.parent/'testbench.spice').read_text(),steps=True)
   result['S80_only_step_change']=True
   base=read(pp.parent/'result.json')['analysis'];q=r['analysis'];result['control_comparison']=dict(type='S80',base_pass=base['combined_screen_pass'],control_pass=q['combined_screen_pass'],delta_time_ps=q['full_receiver']['one_sided_margin_ps']-base['full_receiver']['one_sided_margin_ps'],delta_amplitude_uAeq=q['full_receiver']['worst_signed_margin_uAeq']-base['full_receiver']['worst_signed_margin_uAeq'],delta_positive_energy_percent=100*(q['energy_pJ_per_attempted_payload_bit']['positive']/base['energy_pJ_per_attempted_payload_bit']['positive']-1))
 return result

def native_vcsel(folder,m,r,oldcache):
 """Recompute every exported MOS terminal/body and 7-port energy in chunks."""
 gz=folder/'waveform.dat.gz';h=sha(gz);assert h==r['waveform']['sha256']
 cachekey=hashlib.sha256((h+sha(folder/'manifest.json')+sha(folder/'result.json')+AUDIT_VERSION).encode()).hexdigest()
 if oldcache.get('native_audit_key')==cachekey:return oldcache['native_audit'],cachekey,True
 ix={x:i+1 for i,x in enumerate(m['expressions'])};assert len(ix)==len(m['expressions'])
 assert m['expressions'][0]=='v(jmon)'
 pairs={'VDS':(0,2),'VGS':(1,2),'VGD':(1,0),'VGB':(1,3),'VDB':(0,3),'VSB':(2,3)}
 peaks=[{k:0. for k in pairs} for d in m['devices']];body=np.zeros(len(peaks))
 energy={p:dict(positive_J=0.,returned_J=0.,net_J=0.) for p in m['ports']}
 dc=m['method_config']['level'] is not None;digest=hashlib.sha256();count=0;prev=None;first=None;last=None;maxstep=0.;lo=np.inf;hi=-np.inf
 with gzip.open(gz,'rb') as f:
  header=next(f);digest.update(header)
  while True:
   raw=list(itertools.islice(f,4096))
   if not raw:break
   data=b''.join(raw);digest.update(data);a=np.loadtxt(io.BytesIO(data),ndmin=2);finite(a);assert a.shape[1]==len(ix)+1
   count+=len(a);first=a[0].copy() if first is None else first;last=a[-1].copy();lo=min(lo,a[:,1].min());hi=max(hi,a[:,1].max())
   for i,d in enumerate(m['devices']):
    v=[np.zeros(len(a)) if n=='0' else a[:,ix[f'v({n})']] for n in d['nodes']]
    for k,(j,l) in pairs.items():peaks[i][k]=max(peaks[i][k],float(np.max(abs(v[j]-v[l]))))
    body[i]=max(body[i],max(float(np.max((v[3]-v[j])*(1 if d['model'].startswith('nmos') else -1))) for j in (0,2)))
   if not dc:
    z=np.vstack([prev,a]) if prev is not None else a;dt=np.diff(z[:,0]);assert (dt>0).all();maxstep=max(maxstep,float(dt.max()))
    for port,node in m['ports'].items():
     power=-z[:,ix[f'v({node})']]*z[:,ix[f'i({port})']];u=power[:-1];v=power[1:]
     opposite=u*v<0;correction=np.zeros(len(dt));correction[opposite]=.5*dt[opposite]*abs(u[opposite]*v[opposite])/(abs(u[opposite])+abs(v[opposite]))
     energy[port]['positive_J']+=float(np.sum(.5*dt*(np.maximum(u,0)+np.maximum(v,0))-correction))
     energy[port]['returned_J']+=float(np.sum(.5*dt*(np.maximum(-u,0)+np.maximum(-v,0))-correction))
     energy[port]['net_J']+=float(np.sum(.5*dt*(u+v)))
   prev=a[-1:]
 assert digest.hexdigest()==r['waveform']['raw_sha256']
 assert len(r['stress'])==len(m['devices'])
 for i,(d,s) in enumerate(zip(m['devices'],r['stress'])):
  assert s['instance']==d['instance'] and s['model']==d['model'] and s['nodes']==d['nodes'] and s['parameters']==d['parameters']
  assert set(s['max_abs_terminal_V'])==set(pairs)
  for k in pairs:close(peaks[i][k],s['max_abs_terminal_V'][k],atol=5e-12)
  close(body[i],s['max_body_forward_V'],atol=5e-12)
  assert s['screen_pass']==(max(peaks[i].values())<=3.63 and body[i]<=.3)
 assert r['terminal_screen_pass']==all(s['screen_pass'] for s in r['stress']);close(r['max_body_forward_V'],max(body),atol=5e-12)
 if dc:
  assert count==1;cur=first[1]*1e3;close(cur,r['current_mA']);target=3+4*m['method_config']['level'];close(r['target_mA'],target)
  err=100*(cur/target-1);close(err,r['error_percent'],atol=1e-9)
  assert r['DC_screen_pass']==(abs(err)<=1 and r['terminal_screen_pass'] and max(body)<=.3)
  for port,node in m['ports'].items():close(r['source_power_W'][port],-first[ix[f'v({node})']]*first[ix[f'i({port})']],atol=1e-16)
 else:
  assert count==r['sample_count'];close(last[0],m['end_s'],rtol=2e-13);close(maxstep*1e12,r['max_native_step_ps'],atol=1e-10)
  assert maxstep<=ETA/(m['net_Gbps']*1e9*m['steps_per_UI'])*(1+1e-6)
  close(lo*1e3,r['current_min_mA']);close(hi*1e3,r['current_max_mA'])
  for port in energy:
   for k,v in energy[port].items():close(v,r['energy_by_port'][port][k],rtol=2e-8,atol=2e-21)
 return dict(raw_sha256=digest.hexdigest(),gzip_sha256=h,native_rows=count,current_range_mA=[float(lo*1e3),float(hi*1e3)],end_s=float(last[0]),max_step_ps=maxstep*1e12,all_MOS_stress_recomputed=len(peaks),seven_port_energy_recomputed=not dc,energy=energy if not dc else None),cachekey,False

def vcsel_case(p,oldcache):
 folder=p.parent;m=read(folder/'manifest.json');r=read(p);deck=(folder/'testbench.spice').read_text();defs={x.split()[0].upper():x for x in lines(deck)}
 assert sha(folder/'testbench.spice')==m['deck_sha256'];assert sha(folder/'ngspice.log')==r['log_sha256']
 assert sha(folder/'execution-source.py')==m['execution_source_sha256']
 for x in m['execution_helpers'].values():assert sha(folder/'execution-sources'/x['copy'])==x['sha256']
 for f in ('design.ngspice','sm141064.ngspice','vcsel.spice','driver.spice'):assert sha(folder/f)==m['source_sha256'][f]
 assert sha(folder/'stimulus.json')==m['stimulus_sha256'];st=read(folder/'stimulus.json');bits=stimulus_check(st)
 assert len(m['ports'])==7 and set(m['ports'])=={'VLASER','VDD','VREF','VD','VDB','VSET','VREGSET'}
 # Actual top-level independent sources: internal 0-V current sensors are allowed.
 assert {x.split()[0] for x in lines(deck.split('\n',1)[1]) if x[0].upper()=='V'}==set(m['ports'])
 assert defs['.TEMP'].split()[1]=='25';assert defs['.LIB'].split()[-1]=='typical'
 assert defs['XVCSEL'].split()[1:5]==['vl','vc_k','jmon','vcsel_research'];close(num(defs['XVCSEL'].split()[5].split('=')[1]),150e-15)
 assert defs['RPKG'].split()[1:3]==['vc_k','vc_a'];close(num(defs['RPKG'].split()[3]),.5)
 assert defs['LPKG'].split()[1:3]==['vc_a','out'];close(num(defs['LPKG'].split()[3]),.2e-9)
 for port,value in [('VLASER',3.3),('VDD',3.3),('VREF',3.3),('VSET',.15),('VREGSET',.3263157894736842)]:close(num(defs[port].split()[3]),value)
 for port,node in m['ports'].items():assert defs[port].split()[1:3]==[node,'0']
 close(m['line_GBd'],m['net_Gbps']/ETA);close(m['end_s'],4096/m['net_Gbps']/1e9)
 spec=m['candidate_spec'];cfg=m['method_config'];dc=cfg['level'] is not None
 assert cfg['net_Gbps']==m['net_Gbps'] and cfg['steps_per_UI']==m['steps_per_UI']
 assert spec==cfg['spec'] and len(bits)==m['frame_bits']==4736 and m['attempted_payload_bits']==4096
 xx=defs['XDRV'];atten=float(re.search(r'\bATTEN=([^ ]+)',xx)[1]);close(atten,spec.get('atten_ohm',50.))
 driver=lines((folder/'driver.spice').read_text());definition=next(s.lower().split() for s in driver if s.lower().startswith('.subckt '));top=xx.lower().split();pins=definition[2:definition.index('params:')];mapping=dict(zip(pins,top[1:1+len(pins)]))
 actual={ts[0]:ts for s in driver if (ts:=s.split()) and ts[0].startswith('X')}
 assert len(actual)==len(m['devices']);assert len(actual)==(69 if spec.get('single_stage') else 73)
 if r['simulation_ok']:assert len(actual)==len(r['stress'])
 passives={z[0]:z for line in driver if (z:=line.split()) and z[0].startswith(('R','C'))}
 close(num(passives['RDTOP'][3]),spec['RDTOP_ohm'])
 close(num(passives['RAD'][3]) if not passives['RAD'][3].startswith('{') else atten,atten)
 for name,pins in [('CFFP',['DI','GP']),('CFFN',['DBI','GN'])]:
  if spec['CFF_fF']:
   assert passives[name][1:3]==pins;close(num(passives[name][3]),spec['CFF_fF']*1e-15)
  else:assert name not in passives
 for d in m['devices']:
  ts=actual[d['instance']];assert ts[5] in {'nmos_3p3','pmos_3p3'}
  nodes=['0' if n=='0' else mapping.get(n.lower(),'xdrv.'+n.lower()) for n in ts[1:5]]
  assert nodes==d['nodes'] and ts[5]==d['model'] and ts[6:]==d['parameters']
  for n in nodes:
   if n!='0':assert f'v({n})' in m['expressions']
 expressions=next(s for s in lines(deck) if s.startswith('wrdata waveform.dat ')).split()[2:];assert expressions==m['expressions']
 if dc:
  assert 'OP' in defs
  close(num(defs['VD'].split()[3]),3.3*cfg['level']);close(num(defs['VDB'].split()[3]),3.3*(1-cfg['level']))
 else:
  ui=ETA/m['net_Gbps']/1e9;end=4736*ui;assert 20e-12<ui
  np.testing.assert_allclose(list(map(num,defs['TRAN'].split()[1:])),[ui/m['steps_per_UI'],end,0,ui/m['steps_per_UI']],rtol=2e-13,atol=1e-23)
  for port,seq in [('VD',bits),('VDB',[1-b for b in bits])]:
   expected=[0,seq[0]*3.3]
   for k in range(1,len(seq)):
    if seq[k]!=seq[k-1]:expected.extend([k*ui,seq[k-1]*3.3,k*ui+20e-12,seq[k]*3.3])
   expected.extend([end,seq[-1]*3.3]);got=list(map(float,re.search(r'PWL\((.*)\)',defs[port],re.I)[1].split()));np.testing.assert_allclose(got,expected,rtol=2e-13,atol=1e-23)
 out=dict(source_case=str(folder.relative_to(ROOT)),candidate=cfg['candidate'],kind='dc' if dc else 'transient',MOS_count=len(actual),result_sha256=sha(p),manifest_sha256=sha(folder/'manifest.json'),deck_sha256=sha(folder/'testbench.spice'),execution_sha256=m['execution_source_sha256'])
 if not r['simulation_ok']:return {**out,'retained_solver_failure':True,'reason':r['exit_code']}
 na,key,cached=native_vcsel(folder,m,r,oldcache);out.update(native_audit=na,native_audit_key=key,native_hash_cache_reused=cached)
 if dc:out.update(DC_screen_pass=r['DC_screen_pass'],current_mA=r['current_mA'],DC_error_percent=r['error_percent'])
 else:
  a=read(folder/'analysis.json');assert a['result_sha256']==sha(p) and a['manifest_sha256']==sha(folder/'manifest.json')
  assert a['deck_sha256']==m['deck_sha256'] and a['waveform']==r['waveform']
  for path in a['pathways'].values():receiver_contract(path,m['net_Gbps'],True)
  for k in ('positive','returned','net'):
   total=sum(v[k+'_J'] for v in r['energy_by_port'].values());close(total,r['total_energy'][k+'_J']);close(a['source_energy_pJ_per_attempted_net_bit'][k],total*1e12/4096)
  for port,v in a['energy_by_source_pJ_per_attempted_net_bit'].items():
   for k in ('positive','returned','net'):close(v[k],r['energy_by_port'][port][k+'_J']*1e12/4096)
  domain=na['current_range_mA'][0]>=2 and na['current_range_mA'][1]<=7.5;assert a['observed']['within_calibrated_electrical_and_optical_current_range']==domain
  combined=a['pathways']['actual_graph_5GHzRX']['screen_pass'] and r['terminal_screen_pass'] and r['max_body_forward_V']<=.3 and domain
  assert a['combined_screen_pass']==combined
  for level in (0,1):
   dp=folder.parent/f'DC-L{level}';dm=read(dp/'manifest.json');dr=read(dp/'result.json');assert dr['DC_screen_pass']
   assert dm['source_sha256']==m['source_sha256'] and dm['candidate_spec']==spec
  if cfg['holdout']:
   assert st['seed']==0x4c2d
   ref=folder.parent/f'net{m["net_Gbps"]:g}-s{m["steps_per_UI"]}'
   assert normalized_deck((ref/'testbench.spice').read_text(),holdout=True)==normalized_deck(deck,holdout=True)
   out['holdout_matches_frozen_circuit']=True
   b=read(ref/'analysis.json');q=a['pathways']['actual_graph_5GHzRX'];qb=b['pathways']['actual_graph_5GHzRX'];out['control_comparison']=dict(type='holdout',base_pass=b['combined_screen_pass'],control_pass=combined,delta_time_ps=q['one_sided_margin_ps']-qb['one_sided_margin_ps'],delta_amplitude_uAeq=q['worst_signed_margin_uAeq']-qb['worst_signed_margin_uAeq'],delta_positive_energy_percent=100*(a['source_energy_pJ_per_attempted_net_bit']['positive']/b['source_energy_pJ_per_attempted_net_bit']['positive']-1))
  if m['steps_per_UI']==80:
   ref=folder.parent/f'net{m["net_Gbps"]:g}-s40'
   assert normalized_deck((ref/'testbench.spice').read_text(),steps=True)==normalized_deck(deck,steps=True)
   out['S80_only_step_change']=True
   b=read(ref/'analysis.json');q=a['pathways']['actual_graph_5GHzRX'];qb=b['pathways']['actual_graph_5GHzRX'];out['control_comparison']=dict(type='S80',base_pass=b['combined_screen_pass'],control_pass=combined,delta_time_ps=q['one_sided_margin_ps']-qb['one_sided_margin_ps'],delta_amplitude_uAeq=q['worst_signed_margin_uAeq']-qb['worst_signed_margin_uAeq'],delta_positive_energy_percent=100*(a['source_energy_pJ_per_attempted_net_bit']['positive']/b['source_energy_pJ_per_attempted_net_bit']['positive']-1))
  out.update(rate_Gbps=m['net_Gbps'],line_Gbps=m['line_GBd'],steps=m['steps_per_UI'],holdout=cfg['holdout'],combined_screen_pass=combined,domain_pass=domain,receiver_pass=a['pathways']['actual_graph_5GHzRX']['screen_pass'],source_positive_pJ=a['source_energy_pJ_per_attempted_net_bit']['positive'],mean_source_positive_mW=a['source_energy_pJ_per_attempted_net_bit']['positive']*m['net_Gbps'],analysis_sha256=sha(folder/'analysis.json'))
 out['integrity_pass']=True;return out


def link_audit(path,recompute=False):
 x=read(path);assert len(x['rows'])==32
 for source,h in x.get('source_code_sha256',{}).items():assert sha(ROOT/source)==h,(source,h)
 protocols=list((BUILD/'link-sensitivity').glob('protocol.json'))+list(BUILD.glob('link-sensitivity*/protocol.json'))
 assert any(sha(p)==x['protocol_sha256'] for p in protocols),'link sensitivity protocol identity'
 grid=x['grid'];assert grid['net_Gbps']==3.2;assert grid['optical_tau_ps']==[0,50,100,200] and grid['receiver_GHz']==[1,2,4,8]
 keys={(r['route'],r['optical_tau_ps'],r['receiver_GHz']) for r in x['rows']};assert keys==set(itertools.product('AB',grid['optical_tau_ps'],grid['receiver_GHz']))
 dyn=module(ROOT/'scripts/microled_dynamic_v1/analyze.py','independent_link_dynamics');recv=module(ROOT/'scripts/blue_emitter_speed_20261110/analyze.py','independent_link_rx')
 out=[]
 for src in x['sources']:
  folder=ROOT/src['case'];r=read(folder/'result.json');assert sha(folder/'result.json')==src['result_sha256'];assert sha(folder/'waveform.dat.gz')==src['waveform_gzip_sha256'];assert r['raw_sha256']==src['waveform_raw_sha256']
  for k in ('positive','returned','net'):close(src['driver_energy_pJ_per_attempted_payload_bit'][k],r['analysis']['energy_pJ_per_attempted_payload_bit'][k])
  assert src['receiver_and_optical_hardware_power']=='not_modelled'
  work=folder.parents[1];rx=module(work/'execution-sources/receiver_equal_latency_v2.py','link_rx_'+src['route']);st=read(work/'stimulus.json');stimulus_check(st)
  if recompute:t,current=np.loadtxt(folder/'waveform.dat.gz',skiprows=1,usecols=(0,1)).T
  for row in [z for z in x['rows'] if z['route']==src['route']]:
   assert row['candidate']==src['candidate'] and row['net_Gbps']==3.2 and row['source_result_sha256']==src['result_sha256']
   receiver_contract(row['full_receiver'],3.2)
   if row['optical_tau_ps']==200 and row['receiver_GHz']==1:
    assert row['full_receiver']==r['analysis']['full_receiver']
   if recompute:
    _,y=dyn.cascade_pwl(t,current,row['optical_tau_ps']*1e-12,1/(2*np.pi*row['receiver_GHz']*1e9));fresh=recv.receive(t,y*1e6,st,src['route'],3.2,rx)
    assert fresh==row['full_receiver'],(src['route'],row['optical_tau_ps'],row['receiver_GHz'])
   out.append(dict(route=src['route'],tau_ps=row['optical_tau_ps'],RX_GHz=row['receiver_GHz'],errors=row['full_receiver']['errors'],receiver_screen_pass=row['full_receiver']['research_margin_pass']))
 return dict(path=str(path.relative_to(ROOT)),sha256=sha(path),grid_points=len(out),original_point_exact_reproduction=True,all_points_recomputed=recompute,scope='Fixed-native-current conditional model sensitivity; no new electrical hardware or end-to-end energy.',rows=out)


def vcsel_training_control():
 sys.path.insert(0,str(ROOT/'scripts/highspeed_workbench_20261110'))
 a=module(ROOT/'scripts/highspeed_workbench_20261110/vcsel_x10_analyze.py','audit_vc_training')
 rx=module(a.RX_PATH,'audit_vc_training_rx')
 st=read(ROOT/'build/ab-improvement-20261111/VCSEL/vc-atten50-steer20/net6.4-edge20-s40/stimulus.json')
 bits=np.asarray(st['bits']);ui=ETA/6.4e9;t=np.arange(4736*32+1)*ui/32
 k=np.minimum((t/ui).astype(int),4735);y=25+75*bits[k].astype(float)
 base=a.receive(rx,t,y,bits,ui,t[-1]);damaged=y.copy();mask=t>=576*ui;damaged[mask]=62.5+100*np.sin(8*t[mask]/ui)
 other=a.receive(rx,t,damaged,bits,ui,t[-1]);assert base['screen_pass'] and other['errors']>0
 assert base['delay_UI']==other['delay_UI'] and base['train_errors']==other['train_errors']
 return dict(passed=True,baseline_errors=base['errors'],counterfactual_errors=other['errors'],phase_UI=base['delay_UI'],validation_only_change_keeps_training=True)


def selection_audit(out):
 p=EV/'micro-selection.json'
 if not p.exists():out['pending'].append('micro-selection not published');return None
 x=read(p)
 if x['summary_sha256']!=sha(EV/'micro-summary.json'):out['pending'].append('micro-selection refers to earlier summary')
 rows=[]
 for entry in x['candidates']:
  name=entry['candidate'];cases=[r for r in out['microled_cases'] if r['candidate']==name and r.get('kind')=='transient' and r.get('steps')==40]
  passing=[r for r in cases if r.get('combined_screen_pass')];high=max(passing,key=lambda r:r['rate_Gbps']) if passing else None
  pub=entry['highest_development_grid_pass'];assert high and pub['rate_Gbps']==high['rate_Gbps'] and pub['result_sha256']==high['result_sha256']
  nextfail=min([r for r in cases if r['rate_Gbps']>high['rate_Gbps'] and not r['combined_screen_pass']],key=lambda r:r['rate_Gbps'])
  assert entry['next_development_grid_failure']['result_sha256']==nextfail['result_sha256']
  for rec in [pub,entry['next_development_grid_failure'],*entry['S80'],*entry['holdouts']]:
   rp=ROOT/rec['result'];assert sha(rp)==rec['result_sha256'];rr=read(rp)['analysis'];assert rec['joint_pass']==rr['combined_screen_pass']
   close(rec['timing_ps'],rr['full_receiver']['one_sided_margin_ps']);close(rec['amplitude_uAeq'],rr['full_receiver']['worst_signed_margin_uAeq'])
   for k in ('positive','returned','net'):close(rec['energy_pJ'][k],rr['energy_pJ_per_attempted_payload_bit'][k])
  target=entry.get('target_3p2')
  if target is None:out['pending'].append(name+': target3.2 point not yet selected')
  else:assert target['rate_Gbps']==3.2 and sha(ROOT/target['result'])==target['result_sha256']
  q=read(ROOT/pub['result'])['analysis']['full_receiver'];rows.append(dict(candidate=name,highest_passing_Gbps=high['rate_Gbps'],next_failing_Gbps=nextfail['rate_Gbps'],time_margin_above_screen_ps=q['one_sided_margin_ps']-.37*ETA/high['rate_Gbps']*1000,scope='Discrete nominal envelope; no continuous/PVT/BER claim.'))
 return dict(source_sha256=sha(p),rows=rows)

def freeze_audit():
 checked=[]
 for p in sorted(EV.glob('*-freeze.json')):
  x=read(p);n=0
  for group in ('files','results','manifests','orchestration_logs'):
   for path,h in x.get(group,{}).items():assert sha(ROOT/path)==h,(p.name,path);n+=1
  checked.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p),entries_checked=n))
 p=EV/'vcsel-final-summary.json'
 if p.exists():
  x=read(p);assert x['status']=='Frozen';n=0
  for name,h in x['source_hashes'].items():assert sha(ROOT/'scripts/driver_methods_20261111/vcsel'/name)==h;n+=1
  for name,h in x['compact_evidence'].items():assert sha(EV/name)==h;n+=1
  checked.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p),entries_checked=n))
 return checked

def snapshot():
 patterns=['[AB]_*/cases/*/result.json','[AB]_*/cases/*/case.json','VCSEL/*/*/manifest.json','VCSEL/*/*/result.json','VCSEL/*/*/analysis.json']
 files=set()
 for pattern in patterns:files.update(BUILD.glob(pattern))
 for pattern in ['micro-summary.json','micro-selection.json','vcsel-methods.json','vcsel-selection.json','vcsel-final-summary.json','link-sensitivity*.json','*-freeze.json']:files.update(EV.glob(pattern))
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(files)}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--final',action='store_true');ap.add_argument('--recompute-links',action='store_true');a=ap.parse_args()
 before=snapshot();previous=read(OUT) if OUT.exists() else {};prevrows={x['source_case']:x for x in previous.get('vcsel_cases',[])}
 out=dict(schema=AUDIT_VERSION,generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),final_requested=a.final,complete=False,integrity_pass=False,passed=False,errors=[],pending=[],microled_cases=[],vcsel_cases=[],link_sensitivity=[],script_sha256=sha(Path(__file__)),reused_micro_audit_sha256=sha(ROOT/'scripts/ab_improvement_20261111/validate_stage.py'),limits=['Integrity of nominal simulated evidence, not functional pass at every tested condition.','No new SPICE, silicon, layout/PEX, PVT, BER or manufacturing qualification.','Full-native VCSEL terminal/body/energy checks; MicroLED native SPICE scalar measurements independently checked against actual inventory.'])
 def save():OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 def check(label,fn):
  try:return fn()
  except Exception as e:
   out['errors'].append(dict(check=label,error=repr(e),traceback=traceback.format_exc(limit=4)));print('ERROR',label,repr(e),flush=True);return None
 out['holdout_protocol']=check('holdout_protocol',controls_protocol)
 out['training_counterfactual']=check('training_counterfactual',old.training_control)
 out['vcsel_training_counterfactual']=check('vcsel_training_counterfactual',vcsel_training_control)
 cache={};mc={}
 for p in sorted(BUILD.glob('[AB]_*/cases/*/result.json')):
  row=check(str(p.relative_to(ROOT)),lambda p=p:micro_case(p,cache,mc))
  if row:out['microled_cases'].append(row)
  save();print('MICRO',p.parent.name,'audited',flush=True)
 for p in sorted((BUILD/'VCSEL').glob('*/*/result.json')):
  if not (p.parent/'analysis.json').exists() and read(p.parent/'manifest.json')['method_config']['level'] is None:
   out['pending'].append(str(p.parent.relative_to(ROOT))+': missing analysis');continue
  key=str(p.parent.relative_to(ROOT));row=check(key,lambda p=p,key=key:vcsel_case(p,prevrows.get(key,{})))
  if row:out['vcsel_cases'].append(row)
  save();print('VCSEL',p.parent.parent.name,p.parent.name,'audited',flush=True)
 for p in sorted(EV.glob('link-sensitivity*.json')):
  x=read(p)
  if not ('rows' in x and 'grid' in x):continue
  row=check(str(p.relative_to(ROOT)),lambda p=p:link_audit(p,a.recompute_links))
  if row:out['link_sensitivity'].append(row)
 # Summary identity/coverage must not conceal an omitted new run or a failure.
 def summaries():
  micro=read(EV/'micro-summary.json');vc=read(EV/'vcsel-methods.json')
  expected={str(p.relative_to(ROOT)) for p in BUILD.glob('[AB]_*/cases/*/result.json')}
  got={r['result'] for r in micro['records'] if not r['baseline']}
  for row in micro['records']:assert sha(ROOT/row['result'])==row['result_sha256']
  if got!=expected:out['pending'].append('micro-summary result coverage not current')
  vc_expected={str(p.parent.relative_to(ROOT)) for p in (BUILD/'VCSEL').glob('*/*/analysis.json')}
  vc_got={r['source_case'] for r in vc['rows']}
  for row in vc['rows']:assert sha(ROOT/row['source_case']/'analysis.json')==row['analysis_sha256']
  if vc_expected!=vc_got:out['pending'].append('vcsel-methods analysis coverage not current')
  return dict(micro_summary_sha256=sha(EV/'micro-summary.json'),vcsel_summary_sha256=sha(EV/'vcsel-methods.json'),micro_actual=len(expected),micro_summary=len(got),vcsel_actual=len(vc_expected),vcsel_summary=len(vc_got))
 out['summary_coverage']=check('summary coverage',summaries)
 out['micro_selection']=check('micro selection',lambda:selection_audit(out))
 out['frozen_lanes']=check('lane freeze identities',freeze_audit)
 for p in BUILD.glob('[AB]_*/cases/*/case.json'):
  if not (p.parent/'result.json').exists():out['pending'].append(str(p.parent.relative_to(ROOT))+': missing result')
 for p in (BUILD/'VCSEL').glob('*/*/manifest.json'):
  if not (p.parent/'result.json').exists():out['pending'].append(str(p.parent.relative_to(ROOT))+': missing result')
 for route in 'AB':
  rr=[r for r in out['microled_cases'] if r.get('route')==route]
  if not any(r.get('holdout_matches_frozen_circuit') for r in rr):out['pending'].append(route+': new 0x4c2d holdout not audited')
  if not any(r.get('S80_only_step_change') for r in rr):out['pending'].append(route+': S80 control not audited')
 if not any(r.get('holdout_matches_frozen_circuit') for r in out['vcsel_cases']):out['pending'].append('VCSEL: new 0x4c2d holdout not audited')
 if not any(r.get('S80_only_step_change') for r in out['vcsel_cases']):out['pending'].append('VCSEL: S80 control not audited')
 after=snapshot();out['case_set_stable_during_audit']=before==after
 if before!=after:out['pending'].append('Case set/content changed during audit; rerun after experiments freeze.')
 out['case_set_sha256']=hashlib.sha256(json.dumps(after,sort_keys=True).encode()).hexdigest();out['integrity_pass']=not out['errors'];out['complete']=bool(a.final and not out['pending']);out['passed']=out['integrity_pass'] and out['complete'];save()
 print(json.dumps({k:out[k] for k in ['integrity_pass','complete','passed','pending','errors']},ensure_ascii=False),flush=True)
 return 0 if out['integrity_pass'] else 1
if __name__=='__main__':raise SystemExit(main())
