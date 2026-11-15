#!/usr/bin/env python3
"""Independent read-only audit of 20261115 finite-interface/continuous evidence.

No simulator is run. Only scientific-validation.json is written. Native traces,
source/deck/stimulus hashes, current/energy and MOS terminal checks are reread.
Ordinary runs are partial; --final is allowed only after the parent freezes cases.
This is evidence-integrity validation, not a circuit or product qualification.
"""
import argparse,copy,datetime,gzip,hashlib,importlib.util,inspect,io,itertools,json,re,sys,traceback
from pathlib import Path
import numpy as np
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/driver-interface-20261115';EV=ROOT/'evidence/driver-interface-20261115'
OUT=EV/'scientific-validation.json';ETA=32/37
VERSION='driver-interface-independent-v1'
EXECUTION_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def module(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def close(a,b,rtol=3e-9,atol=1e-20):assert np.isclose(a,b,rtol=rtol,atol=atol),(a,b)
prior=module(ROOT/'scripts/driver_methods_20261111/validate_stage.py','frozen_native_auditor')
prior.AUDIT_VERSION=VERSION+sha(ROOT/'scripts/driver_methods_20261111/validate_stage.py')
lines=prior.lines;num=prior.num

def pwl_contract(line,bits,ui,edge,voltage):
 expected=[0,bits[0]*voltage]
 for k in range(1,len(bits)):
  if bits[k]!=bits[k-1]:expected += [k*ui,bits[k-1]*voltage,k*ui+edge,bits[k]*voltage]
 expected += [len(bits)*ui,bits[-1]*voltage]
 got=list(map(float,re.search(r'PWL\((.*)\)',line,re.I)[1].split()))
 np.testing.assert_allclose(got,expected,rtol=2e-13,atol=1e-23)
 return len(got)//2

def ledger_consistency(r,a,payload):
 for k in ('positive','returned','net'):
  total=sum(v[k+'_J'] for v in r['energy_by_port'].values())
  close(total,r['total_energy'][k+'_J'])
  close(total*1e12/payload,a['source_energy_pJ_per_attempted_net_bit'][k])
 for p,v in a['energy_by_source_pJ_per_attempted_net_bit'].items():
  for k in ('positive','returned','net'):close(v[k],r['energy_by_port'][p][k+'_J']*1e12/payload)

def vcsel_rx_recompute(folder,m,a):
 """Reconstruct electrical and optical proxy once from native current and score.

 Receiver phase logic is frozen source, not a second PHY implementation. Direct
 label/sample-error checks and a post-prefix destructive control are independent.
 """
 sys.path.insert(0,str(ROOT/'scripts/highspeed_workbench_20261110'))
 ana=module(ROOT/'scripts/highspeed_workbench_20261110/vcsel_x10_analyze.py','audit_vcsel_analyze')
 rx=module(ana.RX_PATH,'audit_vcsel_rx');opto=module(ana.OPTO_PATH,'audit_vcsel_opto')
 st=read(folder/'stimulus.json');bits=np.asarray(st['bits']);ui=ETA/m['net_Gbps']/1e9
 raw=np.loadtxt(folder/'waveform.dat.gz',skiprows=1,usecols=(0,1))
 t=np.linspace(0,m['end_s'],4736*128+1);cur=np.interp(t,raw[:,0],raw[:,1])
 p0,p1=opto.static_power([.003,.007])
 photo=25+75*(opto.optical_power(t,cur)-p0)/(p1-p0)
 signal=ana.one_pole(t,photo,5e9)
 checks={}
 for key,y in [('actual_electrical',25+75*(cur-.003)/.004),('actual_graph_5GHzRX',signal)]:
  got=ana.receive(rx,t,y,bits,ui,m['end_s']);reported=a['pathways'][key]
  for k in ('errors','train_errors','validation_bits','screen_pass'):assert got[k]==reported[k],(key,k)
  for k in ('delay_UI','worst_signed_margin_uAeq','one_sided_margin_UI'):close(got[k],reported[k],rtol=3e-8,atol=1e-8)
  idx=np.arange(576,4672);sample=np.interp((idx+reported['delay_UI'])*ui,t,y)
  assert int(np.count_nonzero((sample>=62.5)!=bits[idx]))==reported['errors']
  close(float(np.min((2*bits[idx]-1)*(sample-62.5))),reported['worst_signed_margin_uAeq'],atol=1e-8)
  corrupt=y.copy();corrupt[t>=576*ui]=-1000
  ctl=ana.receive(rx,t,corrupt,bits,ui,m['end_s'])
  assert ctl['delay_UI']==got['delay_UI'] and ctl['train_errors']==got['train_errors']
  assert ctl['errors']>0
  checks[key]=dict(recomputed=True,direct_labels_verified=4096,post_prefix_corruption_does_not_change_training=True)
 return checks

def vcsel_case(p,cache):
 folder=p.parent;m=read(folder/'manifest.json');r=read(p);cfg=m['interface_config'];spec=m['candidate_spec']
 deck=(folder/'testbench.spice').read_text();defs={z.split()[0].upper():z for z in lines(deck)}
 assert m['schema']=='vcsel-finite-interface-v1' and cfg['spec']==spec
 assert cfg['steps_per_UI']==m['steps_per_UI'] and cfg['net_Gbps']==m['net_Gbps']
 for fn in ('manifest.json','testbench.spice','ngspice.log'):
  key={'manifest.json':'manifest_sha256','testbench.spice':'deck_sha256','ngspice.log':'log_sha256'}[fn]
  if key in r:assert sha(folder/fn)==r[key],(fn,key)
  else:assert cfg['level'] is None and key in ('manifest_sha256','deck_sha256')
 assert sha(folder/'testbench.spice')==m['deck_sha256'];assert sha(folder/'execution-source.py')==m['execution_source_sha256']
 for src,x in m['execution_helpers'].items():
  assert sha(folder/'execution-sources'/x['copy'])==x['sha256']
  assert sha(ROOT/src)==x['sha256']
 for f in ('design.ngspice','sm141064.ngspice','vcsel.spice','driver.spice'):assert sha(folder/f)==m['source_sha256'][f]
 baseline=ROOT/m['baseline_case'];bm=read(baseline/'manifest.json')
 assert sha(baseline/'manifest.json')==m['baseline_manifest_sha256'] and m['baseline_driver_sha256']==sha(baseline/'driver.spice')
 expected_driver=(baseline/'driver.spice').read_text()
 if 'shunt_R_ohm' in spec:
  expected_driver,n=re.subn(r'(?m)^(RAD(?:B)?I \w+ VSS) 2500$',lambda q:q.group(1)+' '+str(spec['shunt_R_ohm']),expected_driver);assert n==2
 assert (folder/'driver.spice').read_text()==expected_driver
 assert m['expressions'][:len(bm['expressions'])]==bm['expressions']
 assert m['devices'][:spec['core']]==bm['devices'] and len(m['devices'])==spec['core']+4
 assert spec['core'] in (69,73)
 assert sha(folder/'stimulus.json')==m['stimulus_sha256'];bits=prior.stimulus_check(read(folder/'stimulus.json'))
 assert set(m['ports'])=={'VLASER','VDD','VREF','VD','VDB','VSET','VREGSET','VPHY'}
 assert {z.split()[0] for z in lines(deck.split('\n',1)[1]) if z[0].upper()=='V'}==set(m['ports'])
 assert defs['.TEMP'].split()[1]=='25' and defs['.LIB'].split()[-1]=='typical'
 assert defs['XVCSEL'].split()[1:5]==['vl','vc_k','jmon','vcsel_research'];close(num(defs['XVCSEL'].split()[5].split('=')[1]),150e-15)
 for part,pins,val in [('RPKG',['vc_k','vc_a'],.5),('LPKG',['vc_a','out'],.2e-9),('RD',['d_src','d'],50),('RDB',['db_src','db'],50),('RPHY',['phy_src','phy_r'],.25),('LPHY',['phy_r','vphy'],.2e-9),('RCPHY',['vphy','phy_c'],.1),('CPHY',['phy_c','0'],1e-9)]:
  assert defs[part].split()[1:3]==pins;close(num(defs[part].split()[3]),val)
 for port,val in [('VLASER',3.3),('VDD',3.3),('VREF',3.3),('VSET',.15),('VREGSET',.3263157894736842),('VPHY',3.3)]:close(num(defs[port].split()[3]),val)
 for port,node in m['ports'].items():assert defs[port].split()[1:3]==[node,'0']
 for d in m['devices'][spec['core']:]:
  ts=defs[d['instance'].upper()].split();assert ts[1:5]==d['nodes'] and ts[5]==d['model'] and ts[6:]==d['parameters']
  nw=spec['nW_um'] if d['model']=='nmos_3p3' else spec['pW_um'];close(num(ts[6].split('=')[1]),nw*1e-6)
  close(num(ts[7].split('=')[1]),.28e-6)
  for n in d['nodes']:
   if n!='0':assert f'v({n})' in m['expressions']
 assert defs['WRDATA'].split()[2:]==m['expressions'];assert defs['SAVE'].split()[1:]==m['expressions']
 atten=float(re.search(r'\bATTEN=([^ ]+)',defs['XDRV'])[1]);close(atten,spec['internal_R_ohm'])
 bdefs={z.split()[0].upper():z for z in lines((baseline/'testbench.spice').read_text())}
 expected_xdrv=re.sub(r'\bATTEN=[^ ]+',lambda q:'ATTEN='+str(spec['internal_R_ohm']),bdefs['XDRV'])
 assert defs['XDRV']==expected_xdrv
 base_passives={k:v for k,v in bdefs.items() if k[0] in ('R','L','C') and not k.startswith(('LET','RESET'))}
 actual_passives={k:v for k,v in defs.items() if k[0] in ('R','L','C') and not k.startswith(('LET','RESET'))}
 assert set(actual_passives)-set(base_passives)=={'RPHY','LPHY','RCPHY','CPHY'}
 for k,v in base_passives.items():assert actual_passives[k]==v
 close(m['line_GBd'],m['net_Gbps']/ETA);close(m['end_s'],4096/m['net_Gbps']/1e9)
 dc=cfg['level'] is not None
 if dc:
  assert 'OP' in defs;close(num(defs['VD'].split()[3]),3.3*cfg['level']);close(num(defs['VDB'].split()[3]),3.3*(1-cfg['level']))
 else:
  ui=ETA/m['net_Gbps']/1e9
  np.testing.assert_allclose(list(map(num,defs['TRAN'].split()[1:])),[ui/m['steps_per_UI'],m['end_s'],0,ui/m['steps_per_UI']],rtol=2e-13,atol=1e-23)
  pwl_contract(defs['VD'],bits,ui,20e-12,3.3);pwl_contract(defs['VDB'],[1-b for b in bits],ui,20e-12,3.3)
  if m['steps_per_UI']==80:
   normal=folder.parent/f'net{m["net_Gbps"]:g}-s40';nm=read(normal/'manifest.json')
   assert m['ports']==nm['ports'] and m['source_sha256']==nm['source_sha256'] and m['stimulus_sha256']==nm['stimulus_sha256']
   assert prior.normalized_deck(deck,steps=True)==prior.normalized_deck((normal/'testbench.spice').read_text(),steps=True)
  if cfg['holdout']:
   protocol=read(EV/'vcsel-interface-protocol.json');assert read(folder/'stimulus.json')['seed']==protocol['holdout_seed']
   sel=read(EV/'vcsel-interface-selection.json');assert sel['parameters_frozen'] and sel['candidate']==cfg['candidate'] and sel['spec']==spec
   normal=folder.parent/f'net{m["net_Gbps"]:g}-s{m["steps_per_UI"]}'
   assert prior.normalized_deck(deck,holdout=True)==prior.normalized_deck((normal/'testbench.spice').read_text(),holdout=True)
 out=dict(source_case=str(folder.relative_to(ROOT)),MOS_count=len(m['devices']),new_MOS_count=4,source_port_count=8,kind='dc' if dc else 'transient',candidate=cfg['candidate'],result_sha256=sha(p),manifest_sha256=sha(folder/'manifest.json'))
 if not r['simulation_ok']:return {**out,'retained_solver_failure':True,'exit_code':r['exit_code']}
 # The prior independent native checker supports arbitrary manifest ports/devices;
 # supply the renamed configuration in memory, never edit historical evidence.
 adapted=copy.deepcopy(m);adapted['method_config']=cfg
 native,key,cached=prior.native_vcsel(folder,adapted,r,cache)
 native['source_port_count']=8;native['eight_port_energy_recomputed']=native.pop('seven_port_energy_recomputed',native.get('eight_port_energy_recomputed',False))
 out.update(native_audit=native,native_audit_key=key,native_hash_cache_reused=cached)
 if dc:out['functional_screen_pass']=r['DC_screen_pass'];return out
 a=read(folder/'analysis.json');assert a['result_sha256']==sha(p) and a['manifest_sha256']==sha(folder/'manifest.json')
 assert a['deck_sha256']==m['deck_sha256'] and a['waveform']==r['waveform']
 for q in a['pathways'].values():prior.receiver_contract(q,m['net_Gbps'],True)
 ledger_consistency(r,a,4096)
 dom=native['current_range_mA'][0]>=2 and native['current_range_mA'][1]<=7.5
 assert a['observed']['within_calibrated_electrical_and_optical_current_range']==dom
 assert a['combined_screen_pass']==bool(a['pathways']['actual_graph_5GHzRX']['screen_pass'] and r['terminal_screen_pass'] and r['max_body_forward_V']<=.3 and dom)
 for level in (0,1):
  df=folder.parent/f'DC-L{level}';dm=read(df/'manifest.json');dr=read(df/'result.json')
  assert dr['DC_screen_pass'] and dm['candidate_spec']==spec and dm['source_sha256']==m['source_sha256']
 for k in ('positive','returned','net'):
  val=sum(r['energy_by_port'][p][k+'_J'] for p in ('VD','VDB','VPHY'))*1e12/4096
  close(val,a['interface_observed']['interface_source_energy_pJ_per_payload_bit'][k+'_J'])
 rxkey=hashlib.sha256((key+inspect.getsource(vcsel_rx_recompute)+'native-receiver-v1').encode()).hexdigest()
 if cache.get('receiver_audit_key')==rxkey:out['receiver_recompute']=cache['receiver_recompute'];out['receiver_hash_cache_reused']=True
 else:out['receiver_recompute']=vcsel_rx_recompute(folder,m,a);out['receiver_hash_cache_reused']=False
 out['receiver_audit_key']=rxkey;out['functional_screen_pass']=a['combined_screen_pass'];out['net_Gbps']=m['net_Gbps']
 return out

def vcsel_default_case(p):
 """Audit a physical-open-cable DC diagnostic, never classify as shutdown."""
 folder=p.parent;r=read(p);m=read(folder/'manifest.json');parent=ROOT/m['case_source'];pm=read(parent/'manifest.json')
 assert m['schema']=='vcsel-open-input-diagnostic-v1' and m['diagnostic_kind']=='physical_open_cable_DC_not_shutdown'
 assert sha(parent/'manifest.json')==m['parent_manifest_sha256'];assert sha(folder/'manifest.json')==r['manifest_sha256']
 assert sha(folder/'testbench.spice')==m['deck_sha256']==r['deck_sha256'];assert sha(folder/'execution-source.py')==m['execution_source_sha256']
 for f in ('driver.spice','design.ngspice','sm141064.ngspice','vcsel.spice'):assert sha(folder/f)==m['source_sha256'][f]==sha(parent/f)
 for src,h in m['execution_helpers'].items():assert sha(folder/'execution-sources'/h['copy'])==h['sha256']==sha(ROOT/src)
 expected,n=re.subn(r'(?m)^XPHY[^\n]*\n','',(parent/'testbench.spice').read_text());assert n==4 and (folder/'testbench.spice').read_text()==expected
 assert m['devices']==[d for d in pm['devices'] if not d['instance'].startswith('XPHY')] and len(m['devices'])==69
 assert m['expressions']==pm['expressions'] and m['ports']==pm['ports'] and len(m['ports'])==8
 gz=folder/'waveform.dat.gz';assert sha(gz)==r['waveform']['sha256']
 with gzip.open(gz,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['waveform']['raw_sha256']
 a=np.atleast_2d(np.loadtxt(gz,skiprows=1));assert a.shape==(1,len(m['expressions'])+1) and np.isfinite(a).all()
 ix={e:i+1 for i,e in enumerate(m['expressions'])};close(r['current_mA'],a[0,1]*1e3)
 pairs={'VDS':(0,2),'VGS':(1,2),'VGD':(1,0),'VGB':(1,3),'VDB':(0,3),'VSB':(2,3)};bodymax=0
 assert len(r['stress'])==69
 for d,s in zip(m['devices'],r['stress']):
  assert all(d[k]==s[k] for k in ('instance','nodes','model','parameters'))
  v=[0 if n=='0' else a[0,ix['v('+n+')']] for n in d['nodes']]
  peaks={k:abs(v[i]-v[j]) for k,(i,j) in pairs.items()};body=max(0,max((v[3]-v[i])*(1 if d['model'].startswith('nmos') else -1) for i in (0,2)))
  for k,val in peaks.items():close(s['max_abs_terminal_V'][k],val,atol=5e-12)
  close(s['max_body_forward_V'],body,atol=5e-12);bodymax=max(bodymax,body)
  assert s['screen_pass']==bool(max(peaks.values())<=3.63 and body<=.3)
 assert r['terminal_screen_pass']==all(s['screen_pass'] for s in r['stress']);close(r['max_body_forward_V'],bodymax)
 for n,val in r['nodes_final_V'].items():close(val,a[0,ix['v('+n+')']],atol=1e-12)
 assert r['pins_default_low']==(max(abs(r['nodes_final_V'][k]) for k in ['xdrv.di','xdrv.dbi'])<.01)
 assert r['laser_is_not_shut_down']==(r['current_mA']>1)
 return dict(source_case=str(folder.relative_to(ROOT)),candidate=folder.name,kind='physical_open_input_dc_diagnostic',diagnostic_only=True,MOS_count=69,source_port_count=8,removed_upstream_MOS_count=4,result_sha256=sha(p),manifest_sha256=sha(folder/'manifest.json'),log_sha256=sha(folder/'ngspice.log'),native_audit=dict(raw_sha256=r['waveform']['raw_sha256'],gzip_sha256=sha(gz),native_rows=1,all_MOS_stress_recomputed=69),current_mA=r['current_mA'],pins_default_low=r['pins_default_low'],laser_is_not_shut_down=r['laser_is_not_shut_down'],source_power_mW={p:float(-a[0,ix['v('+n+')']]*a[0,ix['i('+p+')']]*1e3) for p,n in m['ports'].items()},scope='Physical removal of upstream output devices only. Open input is not power-down/backpower, safe shutdown, transient recovery or laser safety validation.')

def signed_integral(t,p):
 dt=np.diff(t);u=p[:-1];v=p[1:];opp=u*v<0;c=np.zeros(len(dt))
 c[opp]=.5*dt[opp]*abs(u[opp]*v[opp])/(abs(u[opp])+abs(v[opp]))
 return dict(positive_J=float(np.sum(.5*dt*(np.maximum(u,0)+np.maximum(v,0))-c)),returned_J=float(np.sum(.5*dt*(np.maximum(-u,0)+np.maximum(-v,0))-c)),net_J=float(np.sum(.5*dt*(u+v))))

def slice_native(t,a,start,end):
 mask=(t>start)&(t<end);ends=np.array([[np.interp(q,t,a[:,i]) for i in range(a.shape[1])] for q in (start,end)])
 z=np.vstack([ends[0],a[mask],ends[1]]);z[:,0]=np.r_[start,t[mask],end];return z[:,0],z

def micro_native(folder,m,r,cache):
 gz=folder/'waveform.dat.gz';gzsha=sha(gz);assert gzsha==r['gzip_sha256']
 key=hashlib.sha256((gzsha+sha(folder/'manifest.json')+sha(folder/'result.json')+r.get('_correction_sha256','')+VERSION+inspect.getsource(micro_native)+'micro-v1').encode()).hexdigest()
 if cache.get('native_audit_key')==key:return cache['native_audit'],key,True
 with gzip.open(gz,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['raw_sha256']
 a=np.loadtxt(gz,skiprows=1,ndmin=2);assert np.isfinite(a).all();ix=m['vectors'];t=a[:,0];cur=a[:,1]
 assert a.shape[1]==len(ix)+1
 dc=m['case'].get('kind')=='dc';missing=sorted({n for d in m['devices'] for n in d['nodes'] if n!='0' and n not in ix})
 scalars={k:float(v) for k,v in re.findall(r'^([a-z][a-z0-9]*)\s*=\s*([-+0-9.eE]+)\s*$',(folder/'ngspice.log').read_text(),re.M)}
 assert len(r['stress'])==len(m['devices'])==r['MOS']
 maxbody=0.;allterm=True;allbody=True
 for k,(d,s) in enumerate(zip(m['devices'],r['stress'])):
  assert all(s[n]==d[n] for n in ('instance','nodes','model'))
  have=all(n=='0' or n in ix for n in d['nodes'])
  if have:
   v=[np.zeros(len(a)) if n=='0' else a[:,ix[n]] for n in d['nodes']]
   peak=max(float(np.max(abs(v[i]-v[j]))) for i in range(4) for j in range(i+1,4));sgn=1 if d['model'].startswith('nfet') else -1
   body=max(0.,max(float(np.max(sgn*(v[3]-v[i]))) for i in (0,2)))
  else:
   assert not dc;peak=max(scalars[f'fs{k}x{j}'] for j in range(6));body=max(0.,max(scalars[f'fb{k}x{j}'] for j in (0,2)))
  close(peak,s['peak_pair_V'],rtol=5e-9,atol=5e-10);close(body,s['body_forward_V'],rtol=5e-9,atol=5e-10)
  limit=3.63 if '03v3' in d['model'] else 6.;close(s['limit_V'],limit)
  assert s['terminal_pass']==(peak<=limit) and s['body_pass']==(body<=.3)
  maxbody=max(maxbody,body);allterm&=s['terminal_pass'];allbody&=s['body_pass']
 assert r['terminal_pass']==allterm and r['body_pass']==allbody;close(r['body_forward_V'],maxbody)
 np.testing.assert_allclose(r['current_range_uA'],[cur.min()*1e6,cur.max()*1e6],rtol=3e-9,atol=1e-12)
 out=dict(raw_sha256=r['raw_sha256'],gzip_sha256=gzsha,native_rows=len(a),all_MOS_count=len(m['devices']),stress_recomputed_from_native_all_terminals=not missing,stress_missing_export_nodes=missing)
 if dc:
  assert len(a)==1;target=25+75*m['case']['level'];close(target,r['target_uA']);close(cur[-1]*1e6,r['current_uA'])
  close(100*(cur[-1]*1e6/target-1),r['DC_error_percent'],atol=1e-9)
  assert r['DC_pass']==(abs(cur[-1]*1e6/target-1)<=.01 and allterm and allbody)
  for p in m['sources']:close(r['power_mW'][p],-a[-1,ix[p+'_voltage']]*a[-1,ix[p+'_current']]*1e3,atol=1e-16)
  return out,key,False
 assert np.all(np.diff(t)>0);close(t[-1],m['end_s'],atol=1e-18);assert len(a)==r['native_samples']
 ui=ETA/m['case']['net_rate_Gbps']/1e9;assert np.diff(t).max()<=ui/m['case']['steps_per_symbol']*(1+1e-6)
 dyn=module(ROOT/'scripts/microled_dynamic_v1/analyze.py','audit_micro_dynamics')
 rx=module(ROOT/'scripts/fair_driver_v1/receiver_equal_latency_v2.py','audit_micro_rx')
 sys.path.insert(0,str(ROOT/'scripts/blue_emitter_speed_20261110'))
 ana=module(ROOT/'scripts/blue_emitter_speed_20261110/analyze.py','audit_micro_analysis')
 _,filtered=dyn.cascade_pwl(t,cur,200e-12,1/(2*np.pi*1e9))
 st=read(folder/'stimulus.json');rate=m['case']['net_rate_Gbps'];T=m['frame_duration_s'];firstdelay=None;frames=[]
 assert len(r['frames'])==m['frames'];bits=np.array(st['symbols_N'])
 for k,row in enumerate(r['frames']):
  start=k*T;stop=(k+1)*T;tt,b=slice_native(t,a,start,stop);local=tt-start;y=np.interp(tt,t,filtered)*1e6
  assert row['frame']==k+1;close(row['start_s'],start);close(row['end_s'],stop)
  ledger={p:signed_integral(tt,-b[:,ix[p+'_voltage']]*b[:,ix[p+'_current']]) for p in m['sources']}
  for p in ledger:
   for term,val in ledger[p].items():close(val,row['source_energy_J'][p][term],rtol=2e-8,atol=2e-20)
  for term in ('positive','returned','net'):close(sum(v[term+'_J'] for v in ledger.values())*1e12/4096,row['energy_pJ_per_attempted_payload_bit'][term],rtol=2e-8,atol=1e-9)
  q=ana.receive(local,y,st,m['case']['route'],rate,rx);reported=row['full_receiver'];prior.receiver_contract(reported,rate)
  for name in ('errors','train_errors','research_margin_pass'):assert q[name]==reported[name],(k,name,q[name],reported[name])
  for name in ('delay_ps','worst_signed_margin_uAeq','one_sided_margin_bit_UI'):close(q[name],reported[name],rtol=1e-7,atol=1e-8)
  if firstdelay is None:firstdelay=q['delay_ps']*1e-12
  idx=np.arange(576,4672);sample=np.interp(idx*ui+firstdelay,local,y);signed=(2*bits[idx]-1)*(sample-62.5)
  fixed=row['first_frame_phase_receiver'];assert fixed['errors']==int(np.count_nonzero((sample>=62.5)!=bits[idx]));close(fixed['amplitude_uAeq'],signed.min(),atol=1e-8);close(fixed['delay_ps'],firstdelay*1e12,atol=1e-8)
  horizontal=rx._horizontal(local,y,idx*ui+firstdelay,sample,bits[idx],np.array([62.5]),0,4736*ui,ui,ui)
  close(fixed['timing_UI'],horizontal['min_bit_UI'],atol=1e-8)
  assert fixed['research_margin_pass']==bool(fixed['errors']==0 and signed.min()>=7.5 and horizontal['min_bit_UI']>=.37)
  close(row['mean_current_uA'],np.trapezoid(b[:,1],tt)/T*1e6,atol=1e-9)
  for name,pair in row['rail_endpoints_V'].items():np.testing.assert_allclose(pair,b[[0,-1],ix[name]],atol=1e-12,rtol=3e-9)
  caps={'VIN':(100e-9,'vin_c','0'),'VDD':(100e-9,'vdd_c','0'),'LED':(200e-15,'led_a','led_k')}
  caps.update({'VH':(10e-9,'xdrv.hc','0'),'VL':(10e-9,'xdrv.lc','0'),'CFF':(31.275e-15,'xdrv.ff','out')} if m['case']['route']=='A' else {'COMP':(150e-12,'xdrv.cc','0'),'CFF':(31.275e-15,'xdrv.gb','out')})
  for name,C,p,n in m.get('extra_caps',[]):caps[name]=(C,p,n)
  assert set(row['explicit_storage_caps'])==set(caps)
  for name,cap in row['explicit_storage_caps'].items():
   C,p,n=caps[name];v=b[[0,-1],ix[p]]-(b[[0,-1],ix[n]] if n!='0' else 0)
   close(cap['C_F'],C);close(cap['initial_V'],v[0]);close(cap['final_V'],v[1])
   close(cap['delta_pJ'],.5*C*(v[1]**2-v[0]**2)*1e12,atol=1e-7)
  inductors={'VIN':(.5e-9,'VIN_current'),'VDD':(2e-9,'VDD_current')}
  if 'ipkg' in ix:inductors['LPKG']=(.5e-9,'ipkg')
  assert set(row['explicit_storage_inductors'])==set(inductors)
  for name,ind in row['explicit_storage_inductors'].items():
   L,node=inductors[name];i=b[[0,-1],ix[node]];close(ind['L_H'],L);close(ind['delta_pJ'],.5*L*(i[1]**2-i[0]**2)*1e12,atol=1e-9)
  if k in (0,m['frames']-1):
   ctl=y.copy();ctl[local>=576*ui]=-1000;z=ana.receive(local,ctl,st,m['case']['route'],rate,rx)
   assert z['delay_ps']==q['delay_ps'] and z['train_errors']==q['train_errors'] and z['errors']>0
  frames.append(dict(frame=k+1,source_energy_recomputed=True,once_filtered_continuous_receive_recomputed=True,first_frame_phase_errors=fixed['errors'],training_prefix_isolation_checked=k in (0,m['frames']-1)))
 normal_domain=bool(cur.min()>=.1e-6 and cur.max()<=.032) if m['case']['mode']!='fault' else None
 if 'normal_current_IV_domain_pass' in r:assert r['normal_current_IV_domain_pass']==normal_domain
 out['normal_current_IV_domain_pass']=normal_domain
 out.update(frames=frames,source_port_count=len(m['sources']),duration_s=float(t[-1]),max_step_ps=float(np.diff(t).max()*1e12),explicit_storage_scope='Exported capacitors/inductors only. Intrinsic MOS nonlinear charge, optical carrier energy and thermal storage are not an all-element conservation proof.')
 assert r['steady_state_qualified'] is False
 if len(r['frames'])>1:
  last=r['frames'][-1];prev=r['frames'][-2];change=100*(last['energy_pJ_per_attempted_payload_bit']['positive']/prev['energy_pJ_per_attempted_payload_bit']['positive']-1)
  close(change,r['steady_screen']['energy_change_percent'],atol=1e-9)
  drift=max(abs(v[1]-v[0]) for v in last['rail_endpoints_V'].values());fraction=sum(abs(v['delta_pJ']) for v in last['explicit_storage_caps'].values())/(last['energy_pJ_per_attempted_payload_bit']['net']*4096)
  close(drift*1e3,r['steady_screen']['max_monitored_rail_endpoint_delta_mV'],atol=1e-9);close(fraction,r['steady_screen']['absolute_explicit_cap_delta_fraction_of_source_net'],atol=1e-12)
  assert r['steady_screen']['finite_window_pass']==bool(abs(change)<=.1 and drift<=1e-4 and fraction<=.001)
 if m['case']['mode']=='fault':
  f=m['fault'];mask=(t>=f['assert_s']+f['settle_allowance_ns']*1e-9)&(t<=f['release_s']);s=r['shutdown'];window=cur[mask]
  np.testing.assert_allclose(s['post_guard_current_range_uA'],[window.min()*1e6,window.max()*1e6],atol=1e-10)
  close(s['max_abs_current_uA'],abs(window).max()*1e6,atol=1e-10);assert s['off_current_screen_pass']==bool(abs(window).max()<=.1e-6)
  vdiff=a[:,ix['led_a']]-a[:,ix['led_k']]
  if 'capacitive_charge_off_fC' in s:
   close(s['capacitive_charge_off_fC'],200e-15*(vdiff[mask][-1]-vdiff[mask][0])*1e15,atol=1e-9)
   cap=200e-15*np.gradient(vdiff,t)
   np.testing.assert_allclose(s['capacitive_current_off_range_uA'],[cap[mask].min()*1e6,cap[mask].max()*1e6],atol=1e-9)
   np.testing.assert_allclose(s['package_current_off_range_uA'],[a[mask,ix['ipkg']].min()*1e6,a[mask,ix['ipkg']].max()*1e6],atol=1e-9)
  if 'recovery_screen' in s:
   z=s['recovery_screen'];idx=np.arange(m['frames']*4736);sample_t=idx*ui+firstdelay;valid=(sample_t>=f['release_s']+f['edge_s'])&(sample_t<=t[-1]-8*ui);idx=idx[valid];sample_t=sample_t[valid]
   expected=np.tile(bits,m['frames'])[idx];sample=np.interp(sample_t,t,filtered)*1e6;sgn=(2*expected-1)*(sample-62.5)
   # Independent threshold-crossing nearest-neighbor timing distance.
   crossings=rx._crossings(t,filtered*1e6,62.5);pos=np.searchsorted(crossings,sample_t,side='right')
   prev=np.where(pos>0,crossings[np.maximum(pos-1,0)],0);nxt=np.where(pos<len(crossings),crossings[np.minimum(pos,len(crossings)-1)],t[-1])
   margin=np.maximum(0,np.minimum(sample_t-prev,nxt-sample_t));margin[sgn<=0]=0
   bad=(sgn<7.5)|(margin<.37*ui);lastbad=sample_t[bad][-1] if bad.any() else f['release_s']+f['edge_s'];bound=lastbad+ui-f['release_s'];observed=sample_t[-1]-lastbad
   assert z['postrelease_scored_bits']==len(idx) and z['postrelease_failed_margin_bits']==int(bad.sum())
   close(z['upper_bound_ns'],bound*1e9,atol=1e-7);close(z['all_subsequent_observation_ns'],observed*1e9,atol=1e-7)
   assert z['recovery_within_1us_verified']==bool(bound<=1e-6 and observed>=1e-6)
  duration=t[mask][-1]-t[mask][0];offpower={}
  for port in m['sources']:
   e=signed_integral(t[mask],-a[mask,ix[port+'_voltage']]*a[mask,ix[port+'_current']]);offpower[port]={k.replace('_J','_mW'):v/duration*1e3 for k,v in e.items()}
  out['settled_off_all_source_power_mW']={'ports':offpower,'total':{k:sum(z[k] for z in offpower.values()) for k in ('positive_mW','returned_mW','net_mW')},'window_s':[float(t[mask][0]),float(t[mask][-1])],'scope':'Data continues toggling during external DISABLE. No useful delivered-bit energy is claimed for this off window.'}
  out['shutdown_conduction_current_recomputed']=True;out['shutdown_displacement_separate']= 'capacitive_charge_off_fC' in s
 return out,key,False

def failure_native_identity(folder,m,r,cache):
 """Hash/check retained partial native evidence without scoring a failed solve."""
 gz=folder/'waveform.dat.gz'
 if not gz.exists():
  assert not r.get('gzip_sha256') and not r.get('raw_sha256')
  return dict(trace_exists=False,scope='Solver failed before native waveform export; log/deck identities retained.')
 h=sha(gz);assert h==r['gzip_sha256'];key=hashlib.sha256((h+sha(folder/'result.json')+'failure-native-v1').encode()).hexdigest()
 if cache.get('failure_native_key')==key:return {**cache['failure_native_audit'],'cache_reused':True}
 digest=hashlib.sha256();count=0;last=None
 with gzip.open(gz,'rb') as f:
  digest.update(next(f))
  while True:
   raw=list(itertools.islice(f,8192))
   if not raw:break
   b=b''.join(raw);digest.update(b);a=np.loadtxt(io.BytesIO(b),usecols=(0,1),ndmin=2);assert np.isfinite(a).all()
   if m['case'].get('kind')!='dc':
    assert np.all(np.diff(a[:,0])>0)
    if last is not None:assert a[0,0]>last
   count+=len(a);last=float(a[-1,0])
 assert digest.hexdigest()==r['raw_sha256']
 if r.get('native_end_s') is not None:close(last,r['native_end_s'])
 return dict(trace_exists=True,raw_sha256=r['raw_sha256'],gzip_sha256=h,native_rows=count,last_native_time_s=last,required_end_s=m['end_s'],failure_native_key=key,scope='Failed/incomplete solve: identities and exported time/current only; no full receiver, steady-state, energy or stress qualification.')

def incomplete_micro_case(folder,m,r):
 """A process may exit zero after aborting tran; retain but never score it."""
 d=read(folder/'diagnostic.json');assert d['schema_version']=='micro-solver-completeness-diagnostic-v1'
 for fn,key in [('manifest.json','manifest_sha256'),('testbench.spice','deck_sha256'),('waveform.dat.gz','gzip_sha256'),('ngspice.log','log_sha256')]:assert sha(folder/fn)==d[key]
 assert sha(folder/'result.json')==d['original_result_sha256'];assert d['raw_sha256']==r['raw_sha256']
 assert not d['simulation_complete'] and d['failure_classification']=='solver_incomplete'
 log=(folder/'ngspice.log').read_text();assert 'Timestep too small' in log and 'simulation(s) aborted' in log
 digest=hashlib.sha256();count=0;first=None;last=None
 with gzip.open(folder/'waveform.dat.gz','rb') as f:
  digest.update(next(f))
  while True:
   raw=list(itertools.islice(f,8192))
   if not raw:break
   b=b''.join(raw);digest.update(b);a=np.loadtxt(io.BytesIO(b),usecols=(0,1),ndmin=2)
   assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
   if last is not None:assert a[0,0]>last
   count+=len(a);first=a[0,0] if first is None else first;last=a[-1,0]
 assert digest.hexdigest()==r['raw_sha256'];close(last,d['last_native_time_s']);close(m['end_s'],d['required_end_s']);assert last<m['end_s']
 return dict(retained_solver_incomplete=True,original_process_success_flag_superseded=True,functional_screen_pass=False,diagnostic_sha256=sha(folder/'diagnostic.json'),last_native_time_s=float(last),required_end_s=m['end_s'],native_rows=count,raw_sha256=r['raw_sha256'],gzip_sha256=d['gzip_sha256'],scope='Aborted transient retained. No complete-frame receiver, energy, steady-state or protection qualification is extracted from the truncated waveform.')

def micro_case(p,cache):
 folder=p.parent;work=folder.parent;r=read(p);m=read(folder/'manifest.json');parent=read(work/'manifest.json');c=m['case'];deck=(folder/'testbench.spice').read_text();defs={x.split()[0].upper():x for x in lines(deck)}
 assert r['case']==c
 for f,key in [('testbench.spice','deck_sha256'),('manifest.json','manifest_sha256'),('ngspice.log','log_sha256')]:assert sha(folder/f)==r[key]
 assert sha(folder/'testbench.spice')==m['deck_sha256'];assert sha(folder/'execution-source.py')==m['execution_sha256'];assert sha(work/'manifest.json')==m['parent_manifest_sha256']
 assert sha(folder/'stimulus.json')==m['stimulus_sha256'];st=read(folder/'stimulus.json');bits=prior.stimulus_check(st)
 helper_gaps=[];helper_recovery=None
 for src,h in m['execution_helpers'].items():
  assert sha(ROOT/src)==h['sha256']
  if sha(folder/h['path'])!=h['sha256']:
   assert not r['simulation_ok'] and (ROOT/src).exists() and sha(ROOT/src)==h['sha256'];helper_gaps.append(src)
   cp=folder/'provenance-correction.json';recovery=read(cp)
   assert recovery['schema_version']=='micro-helper-provenance-correction-v1' and recovery['original_manifest_sha256']==sha(folder/'manifest.json')
   restored=recovery['restored_helper'];assert restored['original_source']==src and restored['original_declared_path']==h['path'] and restored['sha256']==h['sha256']
   assert sha(folder/restored['actual_restored_path'])==h['sha256'];helper_recovery=dict(path=str(cp.relative_to(ROOT)),sha256=sha(cp),restored_path=str((folder/restored['actual_restored_path']).relative_to(ROOT)),restored_sha256=h['sha256'])
 for path,h in parent['inputs'].items():assert sha(work/'inputs'/path)==h
 baseline=ROOT/parent['parent'];bm=read(baseline/'manifest.json');assert sha(baseline/'manifest.json')==parent['parent_manifest_sha256']
 for pth in ('led.spice','pdk/design.ngspice','pdk/sm141064.ngspice','common.spice'):assert parent['inputs'][pth]==bm['inputs'][pth]
 route='route_'+c['route'].lower()+'.spice';expected=(baseline/'inputs'/route).read_text()
 if parent['variant'] in ('fast_rail','protected_fast_rail'):expected=expected.replace('RHFEED VIN VH 100k','RHFEED VIN VH 20k').replace('RLFEED VIN VL 100k','RLFEED VIN VL 20k')
 assert (work/'inputs'/route).read_text()==expected
 devices,passives=prior.old.inventory(work,deck);core_count=len(devices)
 assert core_count=={'A':20,'B':21}[c['route']]
 added_geometry=[dict(instance=z[0].lower(),nodes=z[1:5],model=z[5],parameters={v.split('=')[0]:num(v.split('=')[1]) for v in z[6:]}) for line in lines(deck) if (z:=line.split()) and z[0].startswith('X') and len(z)>5 and z[5] in prior.old.MOS]
 devices.extend(dict(instance=z[0].lower(),nodes=[v.lower() for v in z[1:5]],model=z[5]) for line in lines(deck) if (z:=line.split()) and z[0].startswith('X') and len(z)>5 and z[5] in prior.old.MOS)
 correction=None
 if devices!=m['devices']:
  cp=folder/'reanalysis.json';assert cp.exists(),'Device metadata mismatch: append-only reanalysis pending'
  correction=read(cp);assert correction['schema_version']=='micro-device-node-reanalysis-v1'
  assert work.name=='B-protected_v2'
  orig=correction['original']
  for fn,key in [('manifest.json','manifest_sha256'),('result.json','result_sha256'),('testbench.spice','deck_sha256'),('waveform.dat.gz','gzip_sha256')]:assert sha(folder/fn)==orig[key]
  assert orig['raw_sha256']==r['raw_sha256'];assert correction['source_sha256']==sha(folder/'reanalysis-execution-source.py')
  changed=[]
  for actual,declared in zip(devices,m['devices']):
   if actual!=declared:
    assert actual['instance']==declared['instance'] and actual['instance'] in ('xdrv.xvi.xdis','xdrv.xvi.xkeep')
    assert actual['model']==declared['model'] and actual['nodes']==[('0' if n=='disable' else n) for n in declared['nodes']]
    changed.append(dict(instance=actual['instance'],old_nodes=declared['nodes'],new_nodes=actual['nodes']))
  assert len(changed)==2 and correction['changed_connections']==changed and correction['corrected_devices']==devices
  m=copy.deepcopy(m);m['devices']=devices;r=copy.deepcopy(r);r['stress']=correction['corrected_stress']
  for key in ('terminal_pass','body_pass','body_forward_V'):r[key]=correction[key]
  r['_correction_sha256']=sha(cp)
 else:assert not(folder/'reanalysis.json').exists(),'Unexpected correction on already matching metadata'
 assert set(m['sources'])==set(prior.old.PORTS)
 for port,node in m['sources'].items():assert defs[port].split()[1:3]==[node,'0']
 assert {z.split()[0] for z in lines(deck) if z[0].upper()=='V'}==set(m['sources'])|{'VSENSE'}
 assert defs['.TEMP'].split()[1]=='27';close(num(defs['CLED'].split()[3]),200e-15)
 assert defs['CLED'].split()[1:3]==['led_a','led_k'];assert defs['RPKG'].split()[1:3]==['led_k','pk'];close(num(defs['RPKG'].split()[3]),1)
 assert defs['LPKG'].split()[1:3]==['pk','out'];close(num(defs['LPKG'].split()[3]),.5e-9)
 assert defs['XLED'].split()[1:]==['led_a','led_dc_k','lin2026_yellow20_dc']
 for port,val in [('VIN',c['vin_V']),('VDD',3.3),('VLED',5),('VREF',2.5)]:close(num(defs[port].split()[3]),val)
 extra=m.get('extra_caps',[])
 for name,C,pnode,nnode in extra:
  line=defs['C'+name.upper()].split();assert line[1:3]==[pnode,nnode];close(num(line[3]),C)
 if 'disable_source_resistance_ohm' in m:
  assert m['sources']['VDISABLE']=='disable_src' and defs['RDISABLE'].split()[1:3]==['disable_src','disable'];close(num(defs['RDISABLE'].split()[3]),m['disable_source_resistance_ohm']);close(m['disable_source_resistance_ohm'],100)
 close(m['frame_duration_s'],4096/c['net_rate_Gbps']/1e9);close(m['end_s'],m['frames']*m['frame_duration_s'])
 dc=c.get('kind')=='dc'
 if dc:assert 'OP' in defs;close(num(defs['VD0'].split()[3]),3.3*c['level'])
 else:
  ui=ETA/c['net_rate_Gbps']/1e9;step=ui/c['steps_per_symbol'];np.testing.assert_allclose(list(map(num,defs['TRAN'].split()[1:])),[step,m['end_s'],0,step],rtol=2e-13,atol=1e-23)
  pwl_contract(defs['VD0'],bits*m['frames'],ui,20e-12,3.3)
  if c['mode']=='fault':
   f=m['fault'];T=m['frame_duration_s'];close(f['assert_s'],.25*T);close(f['release_s'],.5*T);close(f['edge_s'],1e-9)
   assert 576*ui<f['assert_s'] and f['assert_s']+f['edge_s']<f['release_s']<m['end_s']
   want=[0,0,f['assert_s'],0,f['assert_s']+f['edge_s'],3.3,f['release_s'],3.3,f['release_s']+f['edge_s'],0,m['end_s'],0]
   got=list(map(float,re.search(r'PWL\((.*)\)',defs['VDISABLE'],re.I)[1].split()))
   np.testing.assert_allclose(got,want,rtol=2e-13,atol=1e-23)
   close(f['off_current_screen_uA'],.1);close(f['settle_allowance_ns'],20);close(f['recovery_allowance_us'],1)
  else:close(num(defs['VDISABLE'].split()[3]),0)
  if c['holdout']:
   prot=read(EV/'micro-protocol.json');assert st['seed']==prot['seed']==22446
   fr=m['candidate_freeze'];fp=EV/f'micro-selection-{c["route"]}.json';assert fr['path']==str(fp.relative_to(ROOT)) and fr['sha256']==sha(fp)
   freeze=read(fp);assert freeze['variant']==parent['variant'] and freeze['route']==c['route'] and freeze['work_manifest_sha256']==sha(work/'manifest.json')
   assert freeze['inputs']==parent['inputs'] and freeze['parameters']==parent['parameters'] and freeze['no_retuning_after_reveal']
   assert freeze['holdout_protocol_sha256']==sha(EV/'micro-protocol.json') and freeze['holdout_window']==[8192,12928]
   for control in freeze['controls']:
    cf=ROOT/control['source_case']
    for filename,key in [('manifest.json','manifest_sha256'),('result.json','result_sha256'),('testbench.spice','deck_sha256')]:assert sha(cf/filename)==control[key]
   base=folder.parent/c['name'].replace('-holdout8192','')
   assert prior.normalized_deck(deck,holdout=True)==prior.normalized_deck((base/'testbench.spice').read_text(),holdout=True)
  if c['steps_per_symbol']==80:
   base=folder.parent/c['name'].replace('-s80','-s40')
   assert prior.normalized_deck(deck,steps=True)==prior.normalized_deck((base/'testbench.spice').read_text(),steps=True)
 close(num(defs['VD1'].split()[3]),0)
 out=dict(source_case=str(folder.relative_to(ROOT)),MOS_count=len(devices),source_port_count=7,kind='dc' if dc else c['mode'],candidate=work.name,result_sha256=sha(p),manifest_sha256=sha(folder/'manifest.json'),helper_copy_gaps_on_retained_solver_failure=helper_gaps)
 out.update(core_MOS_count=core_count,added_MOS_count=len(added_geometry),added_MOS_geometry_from_actual_deck=added_geometry)
 if helper_recovery is not None:out['helper_snapshot_recovery']=helper_recovery
 if correction is not None:out.update(metadata_correction=dict(path=str((folder/'reanalysis.json').relative_to(ROOT)),sha256=sha(folder/'reanalysis.json'),original_device_metadata_and_stress_superseded=True,changed_connections=correction['changed_connections'],same_electrical_deck=True))
 if (folder/'diagnostic.json').exists():return {**out,**incomplete_micro_case(folder,m,r)}
 if not r['simulation_ok']:
  failure=failure_native_identity(folder,m,r,cache)
  return {**out,'retained_solver_failure':True,'exit_code':r['exit_code'],'failure_native_audit':failure,'failure_native_key':failure.get('failure_native_key',cache.get('failure_native_key'))}
 if not dc and m['frames']==1 and c['mode']=='fault':out.update(diagnostic_only=True,qualification_scope='One-frame mechanism/stress diagnostic contains the off interval; no complete post-release 4096-payload-bit frame qualification.')
 assert 'analysis_error' not in r,r.get('analysis_error')
 if not dc and c['mode']=='fault' and 'complete_recovered_frames' in r['shutdown']:
  f=m['fault'];complete=[z for z in r['frames'] if z['start_s']>=f['release_s']+f['recovery_allowance_us']*1e-6 and z['full_receiver']['research_margin_pass'] and z['first_frame_phase_receiver']['research_margin_pass']]
  assert r['shutdown']['complete_recovered_frames']==[z['frame'] for z in complete]
  if complete:close(r['shutdown']['first_complete_recovered_frame_start_after_release_us'],(complete[0]['start_s']-f['release_s'])*1e6,atol=1e-9)
  else:assert r['shutdown']['first_complete_recovered_frame_start_after_release_us'] is None
 native,key,cached=micro_native(folder,m,r,cache);out.update(native_audit=native,native_audit_key=key,native_hash_cache_reused=cached)
 if dc:out['functional_screen_pass']=r['DC_pass']
 elif c['mode']=='fault':
  out['functional_screen_pass']=bool(r['terminal_pass'] and r['body_pass'] and r['shutdown']['off_current_screen_pass'] and r['shutdown'].get('recovery_within_1us_verified',False) and r['frames'][-1]['first_frame_phase_receiver']['research_margin_pass'])
  out['functional_definition']='Off-current screen plus frozen-phase recovery and final normal frame; intentional off-frame receive errors are expected, not protection failure.'
 else:out['functional_screen_pass']=bool(r['terminal_pass'] and r['body_pass'] and all(q['full_receiver']['research_margin_pass'] and q['first_frame_phase_receiver']['research_margin_pass'] for q in r['frames']))
 return out

def protocol_check():
 p=EV/'vcsel-interface-protocol.json'
 if not p.exists():return dict(pending='VCSEL protocol missing')
 q=read(p);s=q['development_seed']
 for _ in range(q['phase_offset_bits']):s=((s<<1)&32767)|(((s>>14)^(s>>13))&1)
 assert s==q['holdout_seed'];assert q['window']==[q['phase_offset_bits'],q['phase_offset_bits']+4736]
 windows=q['previous_windows']+[q['window']]
 for lo,hi in windows:assert 0<=lo<hi<=32767 and hi-lo==4736
 for a,b in itertools.combinations(windows,2):assert a[1]<=b[0] or b[1]<=a[0]
 return dict(PRBS15_seed_and_nonoverlap_verified=True,window=q['window'])

def summaries_audit():
 result={}
 p=EV/'vcsel-interface-summary.json'
 if p.exists():
  s=read(p);seen=[]
  for row in s['dc']:
   f=ROOT/row['source_case'];r=read(f/'result.json');assert row['result_sha256']==sha(f/'result.json')
   for k in ('current_mA','target_mA','DC_screen_pass','error_percent','terminal_screen_pass','max_body_forward_V'):assert row[k]==r[k]
   seen.append(row['source_case'])
  for row in s['rows']:
   f=ROOT/row['source_case'];a=read(f/'analysis.json');m=read(f/'manifest.json')
   assert row['analysis_sha256']==sha(f/'analysis.json') and row['manifest_sha256']==sha(f/'manifest.json')
   for k,expected in {'candidate':a['candidate'],'config':a['config'],'MOS':len(m['devices']),'full_receiver':a['pathways']['actual_graph_5GHzRX'],'electrical_receiver':a['pathways']['actual_electrical'],'stages':a['stages'],'observed':a['observed'],'interface_observed':a['interface_observed'],'energy_pJ':a['source_energy_pJ_per_attempted_net_bit'],'energy_by_source_pJ':a['energy_by_source_pJ_per_attempted_net_bit'],'combined_screen_pass':a['combined_screen_pass'],'waveform':a['waveform']}.items():assert row[k]==expected,k
   seen.append(row['source_case'])
  assert len(seen)==len(set(seen));result['vcsel_summary_rows']=len(seen);result['vcsel_status']=s.get('status','in_progress')
 for p in sorted(EV.glob('vcsel-default-input-*.json')):
  d=read(p);r=read(ROOT/d['case']/'result.json');assert d['result_sha256']==sha(ROOT/d['case']/'result.json')
  for key in ('nodes_final_V','current_mA','terminal_screen_pass','max_body_forward_V','pins_default_low','laser_is_not_shut_down','waveform','scope'):assert d[key]==r[key]
 p=EV/'vcsel-interface-comparison.json'
 if p.exists():
  for row in read(p)['rows']:
   f=ROOT/row['case'];a=read(f/'analysis.json');m=read(f/'manifest.json');q=a['pathways']['actual_graph_5GHzRX']
   assert row['analysis_sha256']==sha(f/'analysis.json') and row['manifest_sha256']==sha(f/'manifest.json')
   vals={'net_Gbps':a['net_Gbps'],'steps_per_UI':m['steps_per_UI'],'MOS':len(m['devices']),'receiver_errors':q['errors'],'amplitude_uAeq':q['worst_signed_margin_uAeq'],'timing_UI':q['one_sided_margin_UI'],'timing_ps':q['one_sided_margin_ps'],'receiver_delay_UI':q['delay_UI'],'receiver_delay_ps':q['delay_ps'],'screen_pass':a['combined_screen_pass'],'I_range_mA':a['observed']['electrical_current_range_mA'],'terminal_peak':a['observed']['terminal_peak'],'max_body_forward_V':a['observed']['max_body_forward_V'],'energy_pJ':a['source_energy_pJ_per_attempted_net_bit'],'energy_by_source':a['energy_by_source_pJ_per_attempted_net_bit'],'stages':a['stages'],'waveform':a['waveform'],'within_current_domain':a['observed']['within_calibrated_electrical_and_optical_current_range']}
   for key,value in vals.items():assert row[key]==value,(row['case'],key)
  result['vcsel_comparison_rows_verified']=len(read(p)['rows'])
 p=EV/'vcsel-interface-confirmation.json'
 if p.exists():
  conf=read(p);sel=read(EV/'vcsel-interface-selection.json');assert conf['selection_sha256']==sha(EV/'vcsel-interface-selection.json')
  assert sel['parameters_frozen'] and sel['selected_analysis_sha256']==sha(ROOT/sel['selected_design_case']/'analysis.json')
  assert sel['driver_sha256']==sha(ROOT/sel['selected_design_case']/'driver.spice')
  specs=[]
  for row in conf['cases']:
   f=ROOT/row['case'];m=read(f/'manifest.json');a=read(f/'analysis.json');q=a['pathways']['actual_graph_5GHzRX']
   assert row['analysis_sha256']==sha(f/'analysis.json') and row['manifest_sha256']==sha(f/'manifest.json')
   expected={'steps_per_UI':m['steps_per_UI'],'holdout':m['interface_config']['holdout'],'screen_pass':a['combined_screen_pass'],'errors':q['errors'],'amplitude_uAeq':q['worst_signed_margin_uAeq'],'timing_UI':q['one_sided_margin_UI'],'timing_ps':q['one_sided_margin_ps'],'delay_ps':q['delay_ps'],'energy_pJ':a['source_energy_pJ_per_attempted_net_bit'],'current_mA':a['observed']['electrical_current_range_mA'],'body_forward_V':a['observed']['max_body_forward_V'],'waveform':a['waveform']}
   for k,v in expected.items():assert row[k]==v,k
   assert m['candidate_spec']==sel['spec'];specs.append((m['steps_per_UI'],m['interface_config']['holdout']))
  assert sorted(specs)==[(40,False),(40,True),(80,False)]
  assert (conf['status']=='PASS')==all(x['screen_pass'] for x in conf['cases'])
  d0=next(x for x in conf['cases'] if x['steps_per_UI']==40 and not x['holdout']);d1=next(x for x in conf['cases'] if x['steps_per_UI']==80)
  for key,field in [('timing_UI','timing_UI'),('timing_ps','timing_ps'),('amplitude_uAeq','amplitude_uAeq')]:close(conf['half_step_delta'][key],d1[field]-d0[field],atol=1e-10)
  close(conf['half_step_delta']['energy_positive_pJ'],d1['energy_pJ']['positive']-d0['energy_pJ']['positive'],atol=1e-10)
  old=conf['old_ideal69_comparison'];a=read(ROOT/old['old_case']/'analysis.json');assert sha(ROOT/old['old_case']/'analysis.json')==old['old_analysis_sha256']
  close(old['old_Epositive_pJ'],a['source_energy_pJ_per_attempted_net_bit']['positive']);close(old['finite_interface_Epositive_pJ'],d0['energy_pJ']['positive']);close(old['Epositive_change_percent'],100*(old['finite_interface_Epositive_pJ']/old['old_Epositive_pJ']-1),atol=1e-9)
  result['vcsel_confirmation_verified']=True
 p=EV/'micro-summary.json'
 if p.exists():
  s=read(p);assert s['protocol']['sha256']==sha(ROOT/s['protocol']['path']);seen=[]
  for row in s['rows']:
   f=ROOT/row['source_case'];r=read(f/'result.json');assert row['result_sha256']==sha(f/'result.json') and row['manifest_sha256']==sha(f/'manifest.json') and row['result']==r
   assert row['waveform_gzip_sha256']==r.get('gzip_sha256');effective=copy.deepcopy(r)
   if 'correction' in row:
    q=row['correction'];cp=ROOT/q['path'];assert q['sha256']==sha(cp) and q['record']==read(cp);c=q['record']
    effective.update(stress=c['corrected_stress'],terminal_pass=c['terminal_pass'],body_pass=c['body_pass'],body_forward_V=c['body_forward_V'],stress_provenance='append-only actual-deck native-waveform reanalysis')
   if 'completion_diagnostic' in row:
    q=row['completion_diagnostic'];dp=ROOT/q['path'];assert q['sha256']==sha(dp) and q['record']==read(dp)
    effective.update(simulation_ok=False,simulation_complete=False,failure_classification=q['record']['failure_classification'])
   if 'corrected_effective_result' in row:assert row['corrected_effective_result']==effective
   if 'combined_research_screen_pass' in row:
    if effective.get('case',{}).get('kind')=='dc':good=effective.get('DC_pass',False)
    elif effective.get('case',{}).get('mode')=='fault':good=effective.get('shutdown',{}).get('off_current_screen_pass',False) and effective.get('shutdown',{}).get('recovery_within_1us_verified',False) and effective.get('shutdown',{}).get('last_frame_full_rx_pass',False)
    else:good=bool(effective.get('frames')) and all(x['full_receiver']['research_margin_pass'] and x['first_frame_phase_receiver']['research_margin_pass'] for x in effective.get('frames',[]))
    assert row['combined_research_screen_pass']==bool(good and effective.get('simulation_ok',False) and not effective.get('analysis_error') and effective.get('terminal_pass',False) and effective.get('body_pass',False))
   seen.append(row['source_case'])
  assert len(seen)==len(set(seen));result['micro_summary_rows']=len(seen);result['micro_case_paths']=seen;result['micro_status']=s['status']
 freezes={}
 for filename in ('vcsel-interface-freeze.json','micro-freeze.json'):
  p=EV/filename
  if p.exists():
   f=read(p);assert f['status']=='frozen'
   for row in f['files']:
    assert sha(ROOT/row['path'])==row['sha256'],row['path']
    if 'bytes' in row:assert (ROOT/row['path']).stat().st_size==row['bytes']
   freezes[filename]=dict(files=len(f['files']),required_cases=len(f['required_cases']),sha256=sha(p))
 result['lane_freezes']=freezes
 figures=[]
 for p in sorted((ROOT/'docs/research/driver-interface-20261115/assets').glob('*.source.json')):
  d=read(p)
  if 'source_case' in d:
   f=ROOT/d['source_case']
   for key,fn in [('deck_sha256','testbench.spice'),('manifest_sha256','manifest.json')]:
    if key in d:assert sha(f/fn)==d[key]
  for key,hkey in [('source_svg','source_svg_sha256'),('source_receipt','source_receipt_sha256'),('generator_path','generator_sha256'),('config_path','config_sha256')]:
   if key in d and hkey in d:assert sha(ROOT/d[key])==d[hkey]
  figures.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p)))
 result['circuit_figure_source_receipts']=figures
 return result

def off_tail_audit(cases,cache):
 """Independently read the native guard point, with full-trace identity upstream."""
 p=EV/'micro-off-tail-B.json'
 if not p.exists():return {'present':False}
 d=read(p);assert d['schema_version']=='micro-off-tail-node-diagnostic-v1'
 f=ROOT/d['source_case'];m=read(f/'manifest.json');r=read(f/'result.json')
 for name,key in [('manifest.json','manifest_sha256'),('result.json','result_sha256'),('waveform.dat.gz','waveform_gzip_sha256')]:assert sha(f/name)==d[key]
 assert d['raw_sha256']==r['raw_sha256'] and d['waveform_gzip_sha256']==r['gzip_sha256']
 full=next(x for x in cases if x['source_case']==d['source_case'])
 assert full['audit_pass'] and full['native_audit']['raw_sha256']==d['raw_sha256'] and full['native_audit']['shutdown_conduction_current_recomputed']
 receipt=ROOT/'docs/research/driver-interface-20261115/assets/micro-protection-B-offtail.source.json';v=read(receipt)
 assert v['case']==d['source_case'] and v['result_sha256']==d['result_sha256'] and v['preview_sha256']==sha(f/'preview.npz')
 assert v['native_point_record']==str(p.relative_to(ROOT)) and v['generator_sha256']==sha(ROOT/'scripts/driver_interface_20261115/micro/plot_off_tail.py')
 key=hashlib.sha256((sha(p)+sha(receipt)+inspect.getsource(off_tail_audit)).encode()).hexdigest()
 if cache.get('audit_key')==key:return {**cache,'native_hash_cache_reused':True}
 names=list(d['native_values']);n=d['native_row_index_zero_based'];a=np.loadtxt(f/'waveform.dat.gz',skiprows=1,usecols=[0]+[m['vectors'][name] for name in names],max_rows=n+1)
 assert len(a)==n+1 and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 fault=m['fault'];guard=fault['assert_s']+fault['settle_allowance_ns']*1e-9
 assert a[-2,0]<guard<=a[-1,0];close(a[-1,0],d['native_time_s']);close((a[-1,0]-fault['assert_s'])*1e9,d['relative_to_assert_ns'])
 nodes={name:float(a[-1,j]) for j,name in enumerate(names,1)}
 for name,value in nodes.items():close(value,d['native_values'][name],rtol=1e-12,atol=1e-18)
 clamp=next(x for x in m['devices'] if x['instance']=='xclamp');assert clamp['nodes']==['led_a','disable','led_k','0'] and clamp['model']=='nfet_06v0'
 cond=a[:,1+names.index('iled_cond')];bad=(a[:,0]>=fault['assert_s'])&(abs(cond)>fault['off_current_screen_uA']*1e-6);assert bad.any()
 last=(a[bad][-1,0]-fault['assert_s'])*1e9;close(last,r['shutdown']['last_above_threshold_ns'])
 derived={'V_AK_V':nodes['led_a']-nodes['led_k'],'XCLAMP_VGS_V':nodes['disable']-nodes['led_k'],'XCLAMP_VSB_V':nodes['led_k'],'I_cond_uA':nodes['iled_cond']*1e6,'current_margin_to_0p1uA_uA':fault['off_current_screen_uA']-abs(nodes['iled_cond'])*1e6,'shutdown_deadline_margin_ns':fault['settle_allowance_ns']-last}
 for name,value in derived.items():close(value,d['derived'][name],rtol=1e-12,atol=1e-12)
 close(abs(nodes['iled_cond'])*1e6,r['shutdown']['max_abs_current_uA']);assert r['shutdown']['off_current_screen_pass']
 return dict(present=True,audit_key=key,native_hash_cache_reused=False,path=str(p.relative_to(ROOT)),sha256=sha(p),source_case=d['source_case'],raw_identity_bound_to_full_native_case_audit=True,first_guard_native_row=n,first_guard_time_s=float(a[-1,0]),nodes_recomputed=nodes,derived_recomputed=derived,scope='First real sample at/after 20 ns; last pre-guard threshold crossing independently checked. Full-window off-current maximum is verified in the separate complete-waveform audit. No optical leakage or unique body-effect mechanism claim.')

def revision_contracts():
 """Bind the reported isolated circuit changes to actual simulator cards."""
 def cards(case):
  path=BUILD/'MicroLED'/case/'testbench.spice'
  return {x.split()[0]:x for x in lines(path.read_text().split('.control')[0].split('\n',1)[1])},sha(path)
 rows=[]
 for route,old,new in [('A','protected_v3','protected_v3r'),('B','protected_v6','protected_v6r')]:
  a,ha=cards(f'{route}-{old}/fault-f2-net1.6-s40');b,hb=cards(f'{route}-{new}/fault-f2-net1.6-s40')
  assert set(b)-set(a)=={'RDISABLE'} and not set(a)-set(b)
  assert b['RDISABLE']=='RDISABLE disable_src disable 100'
  assert b['VDISABLE']==a['VDISABLE'].replace('VDISABLE disable ','VDISABLE disable_src ',1)
  assert all(a[k]==b[k] for k in a if k!='VDISABLE')
  rows.append(dict(route=route,old_variant=old,new_variant=new,old_deck_sha256=ha,new_deck_sha256=hb,change='Only finite 100 ohm DISABLE source impedance and its source node; all other pre-control simulator cards identical.'))
 a,ha=cards('B-protected_v4/fault-f2-net1.6-s40');b,hb=cards('B-protected_v5/fault-f1-net1.6-s40')
 assert set(b)-set(a)=={'XDATAIN'} and not set(a)-set(b)
 assert b['XDATAIN']=='XDATAIN d0 data_gate 0 ppolyf_u_1k_6p0 r_width=4u r_length=8u'
 for name in ('XNAND_NDATA','XNAND_PDATA'):assert b[name]==a[name].replace(' d0 ',' data_gate ',1)
 assert all(a[k]==b[k] for k in a if k not in ('VD0','VDISABLE','XNAND_NDATA','XNAND_PDATA'))
 rows.append(dict(route='B',old_variant='protected_v4',new_variant='protected_v5',old_deck_sha256=ha,new_deck_sha256=hb,change='Only two-square PDK poly resistor before both DATA NAND gate pins; shorter one-frame diagnostic stimulus is independently validated and not treated as equal-duration receiver confirmation.'))
 a,ha=cards('B-protected_v5/fault-f1-net1.6-s40');b,hb=cards('B-protected_v6/fault-f2-net1.6-s40')
 assert set(a)==set(b) and all(a[k]==b[k] for k in a if k not in ('VD0','VDISABLE','XFASTOFF'))
 assert b['XFASTOFF']==a['XFASTOFF'].replace('w=20u','w=4u').replace('ad=8.8p as=8.8p pd=40.88u ps=40.88u','ad=1.76p as=1.76p pd=8.88u ps=8.88u')
 rows.append(dict(route='B',old_variant='protected_v5',new_variant='protected_v6',old_deck_sha256=ha,new_deck_sha256=hb,change='Only fast-off PFET width 20 to 4 um and associated diffusion geometry; stimulus duration changes from one to two frames, with the latter aborted and unqualified.'))
 return {'isolated_circuit_changes_verified':rows}

def source_impedance_audit(cache):
 """Check finite-control-source comparison only over the observed old prefix.

 The old run remains truncated. Sample RMS is diagnostic, not time-weighted
 energy. New native signals are interpolated on old time points without padding.
 """
 checked=[]
 for route in 'AB':
  p=EV/f'micro-source-impedance-{route}.json'
  if not p.exists():continue
  d=read(p);assert d['schema_version']=='micro-control-source-prefix-comparison-v1' and d['route']==route
  assert d['source_sha256']==sha(ROOT/'scripts/driver_interface_20261115/micro/compare_prefix.py')
  paths=[];names=['iled_cond','out','disable','iso_p','led_a'];manifests=[]
  for source in d['sources']:
   f=ROOT/source['case'];m=read(f/'manifest.json');r=read(f/'result.json')
   assert source['manifest_sha256']==sha(f/'manifest.json') and source['result_sha256']==sha(f/'result.json')
   assert source['waveform_gzip_sha256']==r['gzip_sha256']==sha(f/'waveform.dat.gz') and source['raw_sha256']==r['raw_sha256']
   paths.append(f);manifests.append(m)
  assert len(paths)==2
  key=hashlib.sha256((sha(p)+inspect.getsource(source_impedance_audit)).encode()).hexdigest()
  previous=next((x for x in cache if x.get('audit_key')==key),None)
  if previous:checked.append({**previous,'native_hash_cache_reused':True});continue
  signals=[]
  for f,m in zip(paths,manifests):
   with gzip.open(f/'waveform.dat.gz','rb') as g:assert hashlib.file_digest(g,'sha256').hexdigest()==read(f/'result.json')['raw_sha256']
   a=np.loadtxt(f/'waveform.dat.gz',skiprows=1,usecols=[0]+[m['vectors'][n] for n in names])
   assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
   signals.append(a)
  before,after=signals;assert before[-1,0]<after[-1,0]
  close(before[-1,0],d['common_end_s']);close(after[-1,0],d['replacement_complete_end_s']);close(after[-1,0],d['original_required_end_s']);assert len(before)==d['original_prefix_points']
  t=before[:,0];assert t[0]>=after[0,0] and t[-1]<=after[-1,0]
  regions={'entire_common_prefix':np.ones(len(t),dtype=bool),'outside_control_edge_windows':(np.abs(t-.64e-6)>25e-9)&(np.abs(t-1.28e-6)>25e-9)}
  recomputed={}
  for region,mask in regions.items():
   metrics={}
   for j,name in enumerate(names,1):
    delta=np.interp(t[mask],after[:,0],after[:,j])-before[mask,j];peak=int(np.argmax(np.abs(delta)))
    got={'max_abs_difference':float(abs(delta[peak])),'rms_sample_difference':float(np.sqrt(np.dot(delta,delta)/len(delta))),'max_time_s':float(t[mask][peak])}
    for field,value in got.items():close(value,d['metrics'][region][name][field],rtol=2e-10,atol=1e-18)
    assert d['metrics'][region][name]['unit']==('A' if name=='iled_cond' else 'V');metrics[name]=got
   recomputed[region]=metrics
  checked.append(dict(route=route,path=str(p.relative_to(ROOT)),sha256=sha(p),audit_key=key,native_hash_cache_reused=False,common_prefix_end_s=float(before[-1,0]),original_prefix_points=len(before),metrics_recomputed=recomputed,scope='Observed old prefix only; old aborted waveform is neither completed nor qualified.'))
 return {'comparisons':checked,'count':len(checked)}

def snapshot():
 paths=[Path(__file__)]+list((ROOT/'docs/research/driver-interface-20261115/assets').glob('*.source.json'))+list(BUILD.glob('**/manifest.json'))+list(BUILD.glob('**/result.json'))+list(BUILD.glob('**/analysis.json'))+list(BUILD.glob('**/reanalysis.json'))+list(BUILD.glob('**/diagnostic.json'))+list(BUILD.glob('**/provenance-correction.json'))
 paths+=list(EV.glob('validation-matrix.json'))+list(EV.glob('*protocol.json'))+list(EV.glob('*summary.json'))+list(EV.glob('*selection.json'))+list(EV.glob('micro-selection-*.json'))+list(EV.glob('*confirmation.json'))+list(EV.glob('*freeze.json'))+list(EV.glob('*comparison.json'))+list(EV.glob('vcsel-default-input-*.json'))+list(EV.glob('micro-source-impedance-*.json'))+list(EV.glob('micro-off-tail-*.json'))
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--final',action='store_true');args=ap.parse_args()
 before=snapshot();old=read(OUT) if OUT.exists() else {};oldcases={c['source_case']:c for c in old.get('cases',[]) if c.get('audit_pass')}
 rows=[];fail=[];pending=[]
 def check(label,fn):
  try:return {'audit_pass':True,**fn()}
  except Exception as e:
   row=dict(source_case=label,audit_pass=False,error=f'{type(e).__name__}: {e}',traceback=traceback.format_exc());fail.append(row);return row
 prot=check('VCSEL protocol',protocol_check)
 for p in sorted(BUILD.glob('VCSEL/*/*/manifest.json')):
  f=p.parent;rel=str(f.relative_to(ROOT));m=read(p)
  if not(f/'result.json').exists():pending.append(rel+': result pending');continue
  r=read(f/'result.json')
  if m.get('schema')=='vcsel-open-input-diagnostic-v1':
   rows.append(check(rel,lambda p=f/'result.json':vcsel_default_case(p)));continue
  if r.get('simulation_ok') and m['interface_config']['level'] is None and not(f/'analysis.json').exists():pending.append(rel+': receiver analysis pending');continue
  rows.append(check(rel,lambda p=f/'result.json',rel=rel:vcsel_case(p,oldcases.get(rel,{}))))
 micro_manifests=list(BUILD.glob('MicroLED/*/*/manifest.json'))
 for p in sorted(micro_manifests):
  f=p.parent;rel=str(f.relative_to(ROOT))
  if not(f/'result.json').exists():pending.append(rel+': result pending');continue
  rows.append(check(rel,lambda p=f/'result.json',rel=rel:micro_case(p,oldcases.get(rel,{}))))
 if not micro_manifests:pending.append('MicroLED continuous/protection evidence pending')
 summaries=check('summary and freeze provenance',summaries_audit)
 revisions=check('actual isolated protection circuit changes',revision_contracts)
 prefix=check('finite-control-source native prefix comparisons',lambda:source_impedance_audit(old.get('source_impedance',{}).get('comparisons',[])))
 off_tail=check('native B shutdown guard-point voltages',lambda:off_tail_audit(rows,old.get('off_tail',{})))
 if args.final and (summaries.get('vcsel_status')!='frozen' or summaries.get('micro_status')!='frozen'):pending.append('both lane summaries must be frozen for final')
 matrix_path=EV/'validation-matrix.json';coverage={'matrix_present':matrix_path.exists(),'verified':False}
 if matrix_path.exists():
  matrix=read(matrix_path);seen={z['source_case'] for z in rows};required=matrix['required_cases'];assert len(required)==len(set(required))
  missing=sorted(set(required)-seen);extra=sorted(seen-set(required));coverage.update(status=matrix['status'],required_cases=len(required),missing=missing,unlisted_audited_cases=extra,matrix_sha256=sha(matrix_path),deferred=matrix.get('excluded_or_deferred',[]))
  if matrix['status']!='frozen':pending.append('validation matrix not frozen')
  if missing:pending.extend('required case missing: '+x for x in missing)
  if extra:pending.extend('audited case absent from frozen matrix: '+x for x in extra)
  corrections={z['source_case']:z['metadata_correction']['path'] for z in rows if z.get('metadata_correction')}
  declared={z['source_case']:z['correction_file'] for z in matrix.get('expected_retained_metadata_defects',[])}
  if corrections!=declared:pending.append('append-only correction set does not match frozen matrix')
  coverage['append_only_metadata_corrections']=corrections
  micro_seen={x for x in seen if '/MicroLED/' in x}
  if summaries.get('micro_status')=='frozen' and set(summaries.get('micro_case_paths',[]))!=micro_seen:pending.append('frozen MicroLED summary omits or adds audited cases')
  coverage['verified']=matrix['status']=='frozen' and not missing and not extra and corrections==declared
 else:pending.append('final validation-matrix.json not frozen yet')
 after=snapshot()
 if before!=after:pending.append('case/evidence hashes changed during audit; rerun after freeze')
 if not rows:pending.append('No completed VCSEL cases')
 if args.final and pending:fail.append(dict(source_case='final completeness',audit_pass=False,error='Pending evidence remains'))
 out=dict(schema='driver-interface-independent-audit-v1',audit_version=VERSION,generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),requested_final=args.final,status='complete' if args.final and not pending and not fail else 'partial',complete=bool(args.final and not pending and not fail),evidence_integrity_pass=not fail,audited_cases=len(rows),functional_pass_cases=sum(x.get('functional_screen_pass',False) for x in rows),protocol=prot,summaries=summaries,coverage=coverage,cases=rows,pending=pending,failures=fail,snapshot_before=before,snapshot_after=after,validator_sha256=EXECUTION_SHA,evidence_scope=['Deterministic nominal transistor-level simulations with synthetic/unfitted emitter and optical proxy parameters.','Generic finite CMOS interface is not a measured FPGA/SerDes, LVDS/CML compliance, IBIS or PAD/ESD validation.','Integrity pass does not convert failed receiver/stress cases into circuit passes.','No inherited PVT, mismatch, layout, DRC/LVS/PEX, silicon, optical BER or lifetime qualification.'])
 out['source_impedance']=prefix
 out['revision_contracts']=revisions
 out['off_tail']=off_tail
 EV.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print(json.dumps({k:out[k] for k in ('status','complete','evidence_integrity_pass','audited_cases','functional_pass_cases','pending')},ensure_ascii=False));print('failures',len(fail))
 for x in fail:print(x['source_case'],x['error'])
 return 1 if fail else 0
if __name__=='__main__':raise SystemExit(main())
