#!/usr/bin/env python3
"""Continuous actual PRBS and independent high-side isolation experiments.

Frozen 20um/200fF/200ps/1GHz load, source energy and receiver contract.
New current extension/low leakage is not measured device qualification.
"""
from pathlib import Path
import argparse,copy,gzip,hashlib,importlib.util,json,re,shutil,subprocess,sys,time
import numpy as np
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'build/driver-interface-20261115/MicroLED';EV=ROOT/'evidence/driver-interface-20261115'
OLD=ROOT/'build/driver-methods-20261111'
SOURCE=Path(__file__).read_bytes();SOURCE_SHA=hashlib.sha256(SOURCE).hexdigest()
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def emit(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
legacy=module(OLD/'A_rcff31p275/execution-sources/legacy_engine.py','micro_continuous_legacy')
rx=module(ROOT/'scripts/fair_driver_v1/receiver_equal_latency_v2.py','micro_continuous_rx')
dyn=module(ROOT/'scripts/microled_dynamic_v1/analyze.py','micro_continuous_dyn')
sys.path.insert(0,str(ROOT/'scripts/blue_emitter_speed_20261110'))
from analyze import receive
BASE={'A':'A_rcff31p275','B':'B_vin3p3_dummy27p6k'}
ETA=32/37
CAPS={'A':[('VH',10e-9,'xdrv.hc','0'),('VL',10e-9,'xdrv.lc','0'),('CFF',31.275e-15,'xdrv.ff','out')], 'B':[('COMP',150e-12,'xdrv.cc','0'),('CFF',31.275e-15,'xdrv.gb','out')]}
CAPCOMMON=[('VIN',100e-9,'vin_c','0'),('VDD',100e-9,'vdd_c','0'),('LED',200e-15,'led_a','led_k')]

def prbs(seed,n=4736):
 state=seed;bits=[]
 for _ in range(n):
  bits.append((state>>14)&1);state=((state<<1)&0x7fff)|(((state>>14)^(state>>13))&1)
 return bits

def holdout_stim(base):
 state=0x5ace
 for _ in range(8192):state=((state<<1)&0x7fff)|(((state>>14)^(state>>13))&1)
 # Match original seeded_stimulus exactly, not an assumed LFSR output tap.
 helper=module(ROOT/'scripts/three_gbps_experiment/vcsel_driver_run.py','micro_holdout_replay')
 st=helper.seeded_stimulus(state,rx)
 return st,dict(seed=state,seed_hex=hex(state),phase_offset=8192,window=[8192,12928],scope='Predeclared nonoverlapping PRBS15 window; no circuit retuning after reveal.')

def mos(inst,d,g,s,b,model,w,l):
 return f'{inst} {d} {g} {s} {b} {model} w={w:g}u l={l:g}u ad={w*.44:g}p as={w*.44:g}p pd={2*(w+.44):g}u ps={2*(w+.44):g}u'

def protection(variant):
 # Six low-current control MOS + power isolation and A/K equalization MOS.
 defs=[('XEN_N','en','disable','0','0','nfet_03v3',2.5,.28),('XEN_P','en','disable','vdd','vdd','pfet_03v3',3.93,.28),
 ('XLS_N1','iso_g','en','0','0','nfet_06v0',10,.7),('XLS_N2','iso_gb','disable','0','0','nfet_06v0',10,.7),
 ('XLS_P1','iso_g','iso_gb','led_feed','led_feed','pfet_06v0',4,.7),('XLS_P2','iso_gb','iso_g','led_feed','led_feed','pfet_06v0',4,.7),
 *[('XISO'+str(k),'led_a','iso_g','led_feed','led_feed','pfet_06v0',100,.7) for k in range(3)],
 ('XCLAMP','led_a','disable','led_k','0','nfet_06v0',10,.7)]
 extra=''
 if variant in ['protected_v3','protected_v3r','protected_v4','protected_v5','protected_v6','protected_v6r']:
  defs=[tuple([x[0],x[1],'iso_p',*x[3:]]) if x[0].startswith('XISO') else x for x in defs]
  defs.append(('XFASTOFF','iso_p','iso_gb','led_feed','led_feed','pfet_06v0',4 if variant in ['protected_v6','protected_v6r'] else 20,.7))
  extra='\nRGATE iso_g iso_p 100k'
 if variant in ['protected_v4','protected_v5','protected_v6','protected_v6r']:
  defs += [('XREADYRESET','ready_rc','disable','0','0','nfet_03v3',10,.28),('XNAND_PDATA','nand_o','d0','vdd','vdd','pfet_03v3',3.93,.28),('XNAND_PREADY','nand_o','ready_rc','vdd','vdd','pfet_03v3',3.93,.28),('XNAND_NDATA','nand_o','d0','nand_s','0','nfet_03v3',5,.28),('XNAND_NREADY','nand_s','ready_rc','0','0','nfet_03v3',5,.28),('XSAFE_N','data_safe','nand_o','0','0','nfet_03v3',2.5,.28),('XSAFE_P','data_safe','nand_o','vdd','vdd','pfet_03v3',3.93,.28)]
  extra += '\nRREADY en ready_rc 100k\nCREADY ready_rc 0 1p'
 if variant in ['protected_v5','protected_v6','protected_v6r']:
  defs=[tuple([x[0],x[1],'data_gate',*x[3:]]) if x[0] in ['XNAND_PDATA','XNAND_NDATA'] else x for x in defs]
  extra += '\nXDATAIN d0 data_gate 0 ppolyf_u_1k_6p0 r_width=4u r_length=8u'
 return '\n'.join(mos(*x) for x in defs)+extra,[dict(instance=x[0].lower(),nodes=list(x[1:5]),model=x[5]) for x in defs]

def stress_commands(devices):
 lines=[];vn=lambda n:'0' if n=='0' else f'v({n})'
 for k,d in enumerate(devices):
  for j,(i,l) in enumerate(( (i,l) for i in range(4) for l in range(i+1,4) )):
   lines +=[f'let fs{k}x{j}=vecmax(abs({vn(d["nodes"][i])}-{vn(d["nodes"][l])}))',f'print fs{k}x{j}',f'unlet fs{k}x{j}']
  sign=1 if d['model'].startswith('nfet') else -1
  for j in [0,2]:lines +=[f'let fb{k}x{j}=vecmax({sign}*({vn(d["nodes"][3])}-{vn(d["nodes"][j])}))',f'print fb{k}x{j}',f'unlet fb{k}x{j}']
 return '\n'.join(lines)

def init(route,variant):
 name=route+'-'+variant;work=WORK/name;base=OLD/BASE[route]
 if not work.exists():
  work.mkdir(parents=True);shutil.copytree(base/'inputs',work/'inputs');shutil.copy2(base/'stimulus.json',work/'stimulus.json')
  m=read(base/'manifest.json');m['name']=name;m['parent_manifest_sha256']=sha(base/'manifest.json');m['parent']=str(base.relative_to(ROOT));m['variant']=variant
  text=(work/'inputs'/f'route_{route.lower()}.spice').read_text()
  if variant in ['fast_rail','protected_fast_rail']:
   assert route=='A';text=text.replace('RHFEED VIN VH 100k','RHFEED VIN VH 20k').replace('RLFEED VIN VL 100k','RLFEED VIN VL 20k')
  (work/'inputs'/f'route_{route.lower()}.spice').write_text(text)
  m['inputs']={str(p.relative_to(work/'inputs')):sha(p) for p in (work/'inputs').rglob('*') if p.is_file()}
  m['protection']=variant.startswith('protected');m['assumptions']['scope']='New schematic and control only; no PVT/layout/PEX/optical measurement.'
  emit(work/'manifest.json',m)
 return work,legacy.verify(work)

def prepare(route,variant,frames,rate,kind='continuous',steps=40,level=None,holdout=False):
 work,m=init(route,variant)
 freeze_record=None
 if holdout:
  fp=EV/f'micro-selection-{route}.json';fr=read(fp);assert fr['variant']==variant and fr['work_manifest_sha256']==sha(work/'manifest.json');assert fr['holdout_protocol_sha256']==sha(EV/'micro-protocol.json');freeze_record=dict(path=str(fp.relative_to(ROOT)),sha256=sha(fp))
  for control in fr['controls']:assert control['result_sha256']==sha(ROOT/control['source_case']/'result.json')
 case=dict(name='',route=route,corner='typical',temp_C=27,vdd_V=3.3,vin_V=3.3 if route=='B' else 5.,led_cap_F=200e-15,net_rate_Gbps=rate,steps_per_symbol=steps)
 name=f'DC-L{level}' if level is not None else f'{kind}-f{frames}-net{rate:g}-s{steps}'+('-holdout8192' if holdout else '')
 case.update(name=name,frames=frames,mode=kind,holdout=holdout)
 if level is not None:case.update(kind='dc',level=level)
 folder=work/name
 if (folder/'manifest.json').exists():
  met=read(folder/'manifest.json');assert met['case']==case
  assert sha(folder/'testbench.spice')==met['deck_sha256'];assert sha(folder/'execution-source.py')==met['execution_sha256'];return folder,met
 folder.mkdir()
 text,meta=legacy.deck(work,case);meta['case']=case;meta['parent_manifest_sha256']=sha(work/'manifest.json')
 st=read(work/'stimulus.json');protocol=None
 if holdout:st,protocol=holdout_stim(st)
 T=4096/(rate*1e9);end=T*frames
 if level is None:
  bits=st['bits']*frames
  text,n=re.subn(r'(?m)^VD0 data0_src 0 PWL\([^)]*\)',f'VD0 data0_src 0 '+legacy.pwl(bits,ETA/(rate*1e9),3.3,20e-12),text);assert n==1
  text,n=re.subn(r'(?m)^VD1 data1_src 0 PWL\([^)]*\)',f'VD1 data1_src 0 0',text);assert n==1
  step=ETA/(rate*1e9)/steps
  text,n=re.subn(r'(?m)^tran .+$',f'tran {step:.16g} {end:.16g} 0 {step:.16g}',text);assert n==1
  if kind=='fault':
   off=0.25*T;on=0.5*T
   command=f'VDISABLE disable 0 PWL(0 0 {off:.16g} 0 {off+1e-9:.16g} 3.3 {on:.16g} 3.3 {on+1e-9:.16g} 0 {end:.16g} 0)'
   text=text.replace('VDISABLE disable 0 0',command);meta['fault']={'assert_s':off,'release_s':on,'edge_s':1e-9,'off_current_screen_uA':.1,'settle_allowance_ns':20,'recovery_allowance_us':1}
 if m['protection']:
  prot,ds=protection(variant);text=text.replace('RLEDSRC led_src led_a .25','RLEDSRC led_src led_feed .25\n'+prot)
  if route=='B':
   # Reference remains running; dedicated cutoff blocks all emission paths.
   text,n=re.subn(r'(?m)^(XDRV .+ vref 0) disable (fair_b)',r'\1 0 \2',text);assert n==1
   meta['reference_during_off']='kept running; extra static power reported'
   # Inventory was generated before XDRV DISABLE port was physically grounded.
   # Correct nested reference-device gates before native stress commands are emitted.
   for dev in meta['devices']:dev['nodes']=['0' if node=='disable' else node for node in dev['nodes']]
  if variant in ['protected_v4','protected_v5','protected_v6','protected_v6r']:
   assert route=='B'
   text,n=re.subn(r'(?m)^XDRV d0 d1 ', 'XDRV data_safe d1 ',text);assert n==1
   # Correct all original core D0 connections after insertion of actual NAND+INV.
   for dev in meta['devices']:dev['nodes']=['data_safe' if node=='d0' else node for node in dev['nodes']]
   meta['extra_caps']=[['READY',1e-12,'ready_rc','0']]
  meta['protection_revision']=variant
  meta['devices']+=ds
  if level is None:
   # Replace all original stress blocks (source-energy scalar block retained).
   start=text.index('let fs0x0=');endp=text.index('wrdata waveform.dat',start)
   text=text[:start]+stress_commands(meta['devices'])+'\n'+text[endp:]
 if variant in ['protected_v3r','protected_v6r']:
  text,n=re.subn(r'(?m)^VDISABLE disable 0 (.+)$',r'VDISABLE disable_src 0 \1\nRDISABLE disable_src disable 100',text);assert n==1
  text=text.replace('let fp=-v(disable)*i(VDISABLE)','let fp=-v(disable_src)*i(VDISABLE)');meta['sources']['VDISABLE']='disable_src';meta['disable_source_resistance_ohm']=100
 wanted=['out','led_a','led_k','pk','vin','vdd','vref','vin_c','vdd_c','disable','d0']
 wanted += ['xdrv.'+n for n in (['di','n1','ctrl','vh','vl','hc','lc','hset','lset','hg','lg','ff'] if route=='A' else ['di','gb','gp','vx','dummy','bias','sense','cc','in2','ictrl'])]
 if m['protection']:wanted+=['en','iso_g','iso_gb','led_feed']
 if variant in ['protected_v3','protected_v3r','protected_v4','protected_v5','protected_v6','protected_v6r']:wanted+=['iso_p']
 vectors=[('iled_cond','i(VSENSE)'),('ipkg','i(LPKG)')]+[(n,'v('+n+')') for n in wanted]
 for n,node in meta['sources'].items():vectors +=[(n+'_voltage','v('+node+')'),(n+'_current','i('+n+')')]
 if True:
  # Export all terminal voltages to permit independent native-time stress audit.
  for d in meta['devices']:
   for n in d['nodes']:
    if n!='0' and n not in [x[0] for x in vectors]:vectors.append((n,'v('+n+')'))
 text,n=re.subn(r'(?m)^wrdata waveform.dat .+$','wrdata waveform.dat '+' '.join(e for _,e in vectors),text);assert n==1
 # Relative input references independent of current machine mount.
 text=text.replace(str(work/'inputs'),'../inputs');assert str(ROOT) not in text
 if holdout:
  norm=lambda x:re.sub(r'(?m)^VD[01] data[01]_src 0 .*$', '<DATA SOURCE>',x.split('\n',1)[1])
  assert norm(text)==norm((work/f'{kind}-f{frames}-net{rate:g}-s{steps}'/'testbench.spice').read_text()),'Holdout changed more than stimulus'
 (folder/'testbench.spice').write_text(text);(folder/'execution-source.py').write_bytes(SOURCE);emit(folder/'stimulus.json',st)
 helpers={}
 helper_paths=[Path(legacy.__file__),Path(rx.__file__),Path(dyn.__file__),ROOT/'scripts/blue_emitter_speed_20261110/analyze.py']+([ROOT/'scripts/three_gbps_experiment/vcsel_driver_run.py'] if holdout else [])
 for k,p in enumerate(helper_paths):
  dest=folder/'execution-sources'/(str(k)+'-'+p.name);dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest);helpers[str(p.relative_to(ROOT))]=dict(path=str(dest.relative_to(folder)),sha256=sha(dest))
 meta.update(vectors={k:i+1 for i,(k,e) in enumerate(vectors)},frames=frames,frame_duration_s=T,end_s=end,execution_sha256=SOURCE_SHA,execution_helpers=helpers,deck_sha256=sha(folder/'testbench.spice'),stimulus_sha256=sha(folder/'stimulus.json'),holdout_protocol=protocol,candidate_freeze=freeze_record,scope='Nominal repeated actual PRBS; continuously filtered once; no thermal/noise/PVT or optical leakage validation.')
 emit(folder/'manifest.json',meta);return folder,meta

def stress(a,m,folder,dc=False):
 values=lambda n:np.zeros(len(a)) if n=='0' else a[:,m['vectors'][n]]
 sc={k:float(v) for k,v in re.findall(r'^([a-z][a-z0-9]*)\s*=\s*([-+0-9.eE]+)\s*$',(folder/'ngspice.log').read_text(),re.M)}
 rows=[]
 for k,d in enumerate(m['devices']):
  if dc:
   ds=[values(n) for n in d['nodes']];mx=max(float(np.abs(ds[i]-ds[j]).max()) for i in range(4) for j in range(i+1,4));body=max(0.,max(float((ds[3]-ds[i] if d['model'].startswith('nfet') else ds[i]-ds[3]).max()) for i in [0,2]))
  else:mx=max(sc[f'fs{k}x{j}'] for j in range(6));body=max(0.,max(sc[f'fb{k}x{j}'] for j in [0,2]))
  limit=3.63 if '03v3' in d['model'] else 6.
  rows.append(dict(**d,peak_pair_V=mx,limit_V=limit,body_forward_V=body,terminal_pass=mx<=limit,body_pass=body<=.3))
 return rows

def sliced(t,a,start,stop):
 mask=(t>start)&(t<stop);tt=np.r_[start,t[mask],stop];b=np.vstack([np.array([np.interp(start,t,a[:,i]) for i in range(a.shape[1])]),a[mask],np.array([np.interp(stop,t,a[:,i]) for i in range(a.shape[1])])]);b[:,0]=tt
 return tt,b

def fixed_receive(t,signal,st,rate,delay):
 ui=ETA/rate/1e9;idx=np.arange(576,4672);sample_t=idx*ui+delay;expected=np.array(st['symbols_N'])[idx];threshold=np.array([62.5]);samples=np.interp(sample_t,t,signal);decoded=rx._decode(samples,threshold);err=int(np.count_nonzero(decoded!=expected));amp=float(rx._signed_margin(samples,expected,threshold).min());timing=rx._horizontal(t,signal,sample_t,samples,expected,threshold,0,4736*ui,ui,ui)
 return dict(errors=err,amplitude_uAeq=amp,timing_ps=timing['min_ps'],timing_UI=timing['min_bit_UI'],delay_ps=delay*1e12,research_margin_pass=err==0 and amp>=7.5 and timing['min_bit_UI']>=.37)

def summarize_case(folder,m,a):
 route=m['case']['route'];level=m['case'].get('level');ix=m['vectors'];t=a[:,0];cur=a[:,1];device=stress(a,m,folder,level is not None)
 result=dict(case=m['case'],MOS=len(device),stress=device,terminal_pass=all(x['terminal_pass'] for x in device),body_pass=all(x['body_pass'] for x in device),body_forward_V=max(x['body_forward_V'] for x in device),current_range_uA=[float(cur.min()*1e6),float(cur.max()*1e6)])
 source_power={name:-a[:,ix[name+'_voltage']]*a[:,ix[name+'_current']] for name in m['sources']}
 if level is not None:
  current=float(cur[-1]*1e6);target=25+75*level
  result.update(current_uA=current,target_uA=target,DC_error_percent=100*(current/target-1),DC_pass=abs(current/target-1)<=.01 and result['terminal_pass'] and result['body_pass'],power_mW={k:float(v[-1]*1e3) for k,v in source_power.items()},nodes_V={k:float(a[-1,v]) for k,v in ix.items() if k not in ['iled_cond'] and '_current' not in k})
  return result
 st=read(folder/'stimulus.json');rate=m['case']['net_rate_Gbps'];T=m['frame_duration_s'];assert abs(t[-1]-m['end_s'])<1e-14
 _,filtered=dyn.cascade_pwl(t,cur,200e-12,1/(2*np.pi*1e9));frame_rows=[];first_delay=None
 # Derived display-only trace: exact native points near edges; sparse overview is not used for scoring.
 vdiff=a[:,ix['led_a']]-a[:,ix['led_k']];preview_idx=np.linspace(0,len(t)-1,8000,dtype=int)
 for edge in ([m['fault']['assert_s'],m['fault']['release_s']] if 'fault' in m else []):preview_idx=np.r_[preview_idx,np.flatnonzero(np.abs(t-edge)<=30e-9)]
 if 'ready_rc' in ix and 'fault' in m:
  edge=m['fault']['release_s'];preview_idx=np.r_[preview_idx,np.flatnonzero((t>=edge-30e-9)&(t<=edge+250e-9))]
 preview_idx=np.unique(preview_idx);preview={key:a[preview_idx,col] for key,col in ix.items() if key in ['iled_cond','ipkg','out','led_a','led_k','disable','iso_g','iso_gb','iso_p','ready_rc','data_safe','data_gate','nand_o','nand_s','xdrv.bias','xdrv.vh','xdrv.vl','d0']}
 preview.update(time_s=t[preview_idx],received_uAeq=filtered[preview_idx]*1e6,icled_derivative_A=(200e-15*np.gradient(vdiff,t))[preview_idx]);np.savez_compressed(folder/'preview.npz',**preview)
 caps=CAPCOMMON+CAPS[route]+m.get('extra_caps',[])
 for k in range(m['frames']):
  start=k*T;stop=(k+1)*T;tt,b=sliced(t,a,start,stop);local=tt-start;signal=np.interp(tt,t,filtered)*1e6
  full=receive(local,signal,st,route,rate,rx)
  if first_delay is None:first_delay=full['delay_ps']*1e-12
  fixed=fixed_receive(local,signal,st,rate,first_delay)
  energy={name:legacy.signed_integrals(tt,-b[:,ix[name+'_voltage']]*b[:,ix[name+'_current']]) for name in m['sources']}
  storage={}
  for name,c,p,n in caps:
   v=b[[0,-1],ix[p]]-(b[[0,-1],ix[n]] if n!='0' else 0)
   storage[name]=dict(C_F=c,initial_V=float(v[0]),final_V=float(v[1]),delta_pJ=float(.5*c*(v[1]**2-v[0]**2)*1e12))
  # Include external package inductors, not intrinsic MOS charge models.
  inductors={}
  for name,L,port in [('VIN',.5e-9,'VIN'),('VDD',2e-9,'VDD'),('LPKG',.5e-9,'package')]:
   i=b[[0,-1],ix['ipkg' if port=='package' else port+'_current']];inductors[name]=dict(L_H=L,delta_pJ=float(.5*L*(i[1]**2-i[0]**2)*1e12))
  total={s:sum(v[s+'_J'] for v in energy.values())/4096*1e12 for s in ['positive','returned','net']}
  frame_rows.append(dict(frame=k+1,start_s=start,end_s=stop,full_receiver=full,first_frame_phase_receiver=fixed,energy_pJ_per_attempted_payload_bit=total,source_energy_J=energy,explicit_storage_caps=storage,explicit_storage_inductors=inductors,mean_current_uA=float(np.trapezoid(b[:,1],tt)/(stop-start)*1e6),current_range_uA=[float(b[:,1].min()*1e6),float(b[:,1].max()*1e6)],rail_endpoints_V={n:[float(b[0,ix[n]]),float(b[-1,ix[n]])] for n in (['xdrv.vh','xdrv.vl','vin','vdd'] if route=='A' else ['xdrv.bias','xdrv.sense','vin','vdd'])}))
 result.update(normal_current_IV_domain_pass=bool(cur.min()>=.1e-6 and cur.max()<=.032) if m['case']['mode']!='fault' else None,frames=frame_rows,native_samples=len(t),frame_duration_s=T,mode=m['case']['mode'],steady_state_qualified=False,steady_screen=dict(criterion='last2frames E+ relative change<=0.1%, all monitored rail endpoint changes<=0.1mV, explicit capacitor energy change<=0.1% of source net energy per frame; deterministic finite window only',energy_change_percent=100*(frame_rows[-1]['energy_pJ_per_attempted_payload_bit']['positive']/frame_rows[-2]['energy_pJ_per_attempted_payload_bit']['positive']-1) if len(frame_rows)>1 else None))
 if len(frame_rows)>1:
  last=frame_rows[-1];drift=max(abs(v[1]-v[0]) for v in last['rail_endpoints_V'].values());storage_abs=sum(abs(v['delta_pJ']) for v in last['explicit_storage_caps'].values());net=last['energy_pJ_per_attempted_payload_bit']['net']*4096
  result['steady_screen'].update(max_monitored_rail_endpoint_delta_mV=drift*1e3,absolute_explicit_cap_delta_fraction_of_source_net=storage_abs/net,finite_window_pass=abs(result['steady_screen']['energy_change_percent'])<=.1 and drift<=1e-4 and storage_abs/net<=.001)
 if m['case']['mode']=='fault':
  fault=m['fault'];off=fault['assert_s'];on=fault['release_s'];guard=20e-9;mask=(t>=off+guard)&(t<=on);window=cur[mask];above=np.flatnonzero((t>=off)&(t<on)&(np.abs(cur)>.1e-6));last_above=float(t[above[-1]]-off) if len(above) else 0
  off_tt,off_b=sliced(t,a,off+guard,on);off_energy={name:legacy.signed_integrals(off_tt,-off_b[:,ix[name+'_voltage']]*off_b[:,ix[name+'_current']]) for name in m['sources']}
  q=legacy.signed_integrals(t[mask],cur[mask]);vdiff=a[:,ix['led_a']]-a[:,ix['led_k']]
  result['shutdown']=dict(**fault,post_guard_current_range_uA=[float(window.min()*1e6),float(window.max()*1e6)],max_abs_current_uA=float(np.abs(window).max()*1e6),off_current_screen_pass=bool(np.abs(window).max()<=.1e-6),last_above_threshold_ns=last_above*1e9,post_guard_charge_fC={k.replace('_J','_fC'):v*1e15 for k,v in q.items()},LED_voltage_range_off_V=[float(vdiff[mask].min()),float(vdiff[mask].max())],low_current_model_boundary='Below0.1uA and reverse behavior are unmeasured linear extension. Shutdown result is numerical electrical diagnostic, not leakage/optical-darkness qualification.')
  result['shutdown']['source_energy_during_settled_off_J']=off_energy
  result['shutdown']['average_source_power_during_settled_off_mW']={name:1000*e['net_J']/(on-off-guard) for name,e in off_energy.items()}
  result['shutdown']['total_source_positive_power_during_settled_off_mW']=1000*sum(e['positive_J'] for e in off_energy.values())/(on-off-guard)
  # Frame 2 is fully after release+1us at 1.6Gb/s; first frame training precedes fault.
  result['shutdown']['last_frame_full_rx_pass']=frame_rows[-1]['full_receiver']['research_margin_pass']
  complete=[f for f in frame_rows if f['start_s']>=on+1e-6 and f['full_receiver']['research_margin_pass'] and f['first_frame_phase_receiver']['research_margin_pass']]
  result['shutdown']['first_complete_recovered_frame_start_after_release_us']=(complete[0]['start_s']-on)*1e6 if complete else None
  result['shutdown']['complete_recovered_frames']=[f['frame'] for f in complete]
  result['shutdown']['recovery_within_1us_verified']=False
  # Native-grid dV/dt estimates explicit LED capacitance current; package current also includes the protection clamp path.
  cap_current=200e-15*np.gradient(vdiff,t)
  result['shutdown']['displacement_definition']='200fF * native-grid nonuniform central derivative of LED A-K voltage; peak is numerical approximation, charge uses exact endpoint C*deltaV.'
  result['shutdown']['capacitive_charge_off_fC']=float(200e-15*(vdiff[mask][-1]-vdiff[mask][0])*1e15)
  result['shutdown']['package_current_off_range_uA']=[float(a[mask,ix['ipkg']].min()*1e6),float(a[mask,ix['ipkg']].max()*1e6)]
  result['shutdown']['capacitive_current_off_range_uA']=[float(cap_current[mask].min()*1e6),float(cap_current[mask].max()*1e6)]
  result['shutdown']['protection_nodes_off_V']={n:[float(a[mask,ix[n]].min()),float(a[mask,ix[n]].max())] for n in ['out','led_a','led_k','disable']+(['iso_g','iso_gb','en','led_feed'] if 'iso_g' in ix else [])+(['iso_p'] if 'iso_p' in ix else [])+(['ready_rc','data_safe'] if 'ready_rc' in ix else [])}
  result['shutdown']['settled_off_stress']=[]
  for dev in m['devices']:
   vv=[np.zeros(mask.sum()) if n=='0' else a[mask,ix[n]] for n in dev['nodes']];peak=max(float(np.abs(vv[i]-vv[j]).max()) for i in range(4) for j in range(i+1,4));body=max(0.,max(float((vv[3]-vv[j] if dev['model'].startswith('nfet') else vv[j]-vv[3]).max()) for j in [0,2]));result['shutdown']['settled_off_stress'].append(dict(instance=dev['instance'],peak_pair_V=peak,body_forward_V=body))
  result['shutdown']['transitions']={}
  for label,edge in [('assert',off),('release',on)]:
   edge_mask=(t>=edge-10e-9)&(t<=edge+30e-9)
   row=dict(window_relative_ns=[-10,30],conduction_range_uA=[float(cur[edge_mask].min()*1e6),float(cur[edge_mask].max()*1e6)],LED_AK_voltage_range_V=[float(vdiff[edge_mask].min()),float(vdiff[edge_mask].max())],VLED_delivered_current_range_mA=[float((-a[edge_mask,ix['VLED_current']]).min()*1e3),float((-a[edge_mask,ix['VLED_current']]).max()*1e3)],package_current_range_mA=[float(a[edge_mask,ix['ipkg']].min()*1e3),float(a[edge_mask,ix['ipkg']].max()*1e3)])
   row['protection_MOS_stress']=[]
   for dev in m['devices']:
    if not dev['instance'].startswith('xdrv.'):
     vv=[np.zeros(edge_mask.sum()) if node=='0' else a[edge_mask,ix[node]] for node in dev['nodes']];peak=max(float(np.abs(vv[i]-vv[j]).max()) for i in range(4) for j in range(i+1,4));row['protection_MOS_stress'].append(dict(instance=dev['instance'],peak_pair_V=peak,limit_V=3.63 if '03v3' in dev['model'] else 6.))
   result['shutdown']['transitions'][label]=row
  # Resume at the original frame-1 training phase; no post-fault phase fitting.
  ui=ETA/rate/1e9;nbits=m['frames']*4736;idx=np.arange(nbits);sample_t=idx*ui+first_delay
  valid=(sample_t>=on+fault['edge_s'])&(sample_t<=t[-1]-8*ui);idx=idx[valid];sample_t=sample_t[valid]
  expected=np.tile(st['bits'],m['frames'])[idx];sample=np.interp(sample_t,t,filtered)*1e6;sgn=rx._signed_margin(sample,expected,np.array([62.5]));margins=np.zeros(len(idx));events=rx._crossing_events(t,filtered*1e6,np.array([62.5]))
  for lev,ev in enumerate(events):
   ixlev=np.flatnonzero((expected==lev)&(sgn>0));ts=sample_t[ixlev]
   pos=np.searchsorted(ev,ts,side='right');previous=np.where(pos>0,ev[np.maximum(pos-1,0)],0);following=np.where(pos<len(ev),ev[np.minimum(pos,len(ev)-1)],t[-1]);margins[ixlev]=np.maximum(0,np.minimum(ts-previous,following-ts))
  failed=(sgn<7.5)|(margins<.37*ui);last_bad=float(sample_t[failed][-1]) if failed.any() else on+fault['edge_s'];recovery=(last_bad+ui-on)
  result['shutdown'].update(recovery_screen=dict(definition='Last post-release amplitude/timing failure plus one line UI at the frozen first-frame training phase; all later sampled bits through end-minus8UI satisfy the normal margins. Finite-trace settling diagnostic, not synchronization protocol.',postrelease_scored_bits=int(len(idx)),postrelease_failed_margin_bits=int(failed.sum()),upper_bound_ns=recovery*1e9,all_subsequent_observation_ns=(sample_t[-1]-last_bad)*1e9,recovery_within_1us_verified=bool(recovery<=1e-6 and sample_t[-1]-last_bad>=1e-6)))
  result['shutdown']['recovery_within_1us_verified']=result['shutdown']['recovery_screen']['recovery_within_1us_verified']

 return result

def run(route,variant,frames=4,rate=1.6,kind='continuous',steps=40,level=None,holdout=False):
 folder,m=prepare(route,variant,frames,rate,kind,steps,level,holdout)
 if (folder/'result.json').exists():
  r=read(folder/'result.json');assert r['deck_sha256']==sha(folder/'testbench.spice');assert r['manifest_sha256']==sha(folder/'manifest.json');assert not r.get('gzip_sha256') or sha(folder/'waveform.dat.gz')==r['gzip_sha256'];return r
 print('START',folder.name,route,variant,flush=True);start=time.monotonic()
 with (folder/'ngspice.log').open('w') as log:
  try:code=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=log,stderr=subprocess.STDOUT,timeout=3600).returncode
  except subprocess.TimeoutExpired:code=None
 raw=folder/'waveform.dat';logtext=(folder/'ngspice.log').read_text();aborted='simulation(s) aborted' in logtext or 'Timestep too small' in logtext
 native_end=None
 if raw.exists():
  with raw.open('rb') as f:
   f.seek(max(0,raw.stat().st_size-16384));tail=f.read().splitlines()
  native_end=float(tail[-1].split()[0])
 complete=raw.exists() and (level is not None or abs(native_end-m['end_s'])<1e-14)
 r=dict(simulation_ok=code==0 and raw.exists() and complete and not aborted,simulation_complete=bool(complete and not aborted),native_end_s=native_end,abort_reported=aborted,exit_code=code,solve_s=time.monotonic()-start,case=m['case'],deck_sha256=sha(folder/'testbench.spice'),manifest_sha256=sha(folder/'manifest.json'))
 if not r['simulation_ok']:r['failure_classification']='solver_incomplete' if aborted or not complete else 'solver_process_failure'
 if r['simulation_ok']:
  try:
   a=np.loadtxt(raw,skiprows=1,ndmin=2);assert np.isfinite(a).all();assert a.shape[1]==len(m['vectors'])+1
   if level is None:assert np.all(np.diff(a[:,0])>0)
   r.update(summarize_case(folder,m,a))
  except Exception as err:r['analysis_error']=repr(err)
 if raw.exists():
  r['raw_sha256']=sha(raw);gz=folder/'waveform.dat.gz'
  with raw.open('rb') as src,gzip.open(gz,'wb',compresslevel=5) as dst:shutil.copyfileobj(src,dst)
  with gzip.open(gz,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['raw_sha256']
  r.update(gzip_sha256=sha(gz),gzip_bytes=gz.stat().st_size);raw.unlink()
 if (folder/'preview.npz').exists():r['preview_sha256']=sha(folder/'preview.npz')
 r['log_sha256']=sha(folder/'ngspice.log');r['elapsed_s']=time.monotonic()-start;emit(folder/'result.json',r)
 print('DONE',route,variant,folder.name,r['simulation_ok'],r.get('analysis_error'),r.get('DC_pass'),r.get('shutdown',{}).get('max_abs_current_uA'),flush=True)
 return r

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('route',choices=['A','B']);p.add_argument('variant',choices=['baseline','protected_v2','protected_v3','protected_v3r','protected_v4','protected_v5','protected_v6','protected_v6r','fast_rail','protected_fast_rail']);p.add_argument('--frames',type=int,default=4);p.add_argument('--rate',type=float,default=1.6);p.add_argument('--kind',choices=['continuous','fault'],default='continuous');p.add_argument('--steps',type=int,default=40);p.add_argument('--dc',action='store_true');p.add_argument('--holdout',action='store_true');args=p.parse_args()
 if args.dc:
  for level in [0,1]:run(args.route,args.variant,level=level)
 else:run(args.route,args.variant,args.frames,args.rate,args.kind,args.steps,holdout=args.holdout)
