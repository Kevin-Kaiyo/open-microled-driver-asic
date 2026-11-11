#!/usr/bin/env python3
"""Finite VCSEL methods experiment, append-only with frozen helper snapshots."""
from pathlib import Path
import argparse, copy, gzip, hashlib, json, re, shutil, subprocess, sys, time
import numpy as np
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts/highspeed_workbench_20261110'))
import vcsel_x10_run as engine
import vcsel_x10_analyze as analysis
SOURCE=Path(__file__).read_bytes(); SOURCE_HASH=hashlib.sha256(SOURCE).hexdigest()
BUILD=ROOT/'build/driver-methods-20261111/VCSEL'
EV=ROOT/'evidence/driver-methods-20261111'
BASE=ROOT/'build/ab-improvement-20261111/VCSEL/vc-atten50-steer20/net6.4-edge20-s40'
SPECS={
 'vc-single-r150':{'CFF_fF':0.,'RDTOP_ohm':85000.,'single_stage':True,'atten_ohm':150.,'hypothesis':'One computed damping confirmation: measured50to100ohm peak slope predicts~7.447mA at150ohm. FreezeRafterthispoint; preserve3/7mAtargets,69MOSandall7sources.'},
 'vc-single-r100':{'CFF_fF':0.,'RDTOP_ohm':85000.,'single_stage':True,'atten_ohm':100.,'hypothesis':'Same69MOSsingle-stage topology; increase existing RAD/RADB50to100ohm to damp fast input Miller feedthrough after7.584mA overshoot seen in undampedcontrol. No changing light-source calibration range.'},
 'vc-single':{'CFF_fF':0.,'RDTOP_ohm':85000.,'single_stage':True,'hypothesis':'Remove first two CMOS inverters (4MOS); feed remaining GP inverter from DBI and GN inverter from DI, retaining output W12/24 and actual DR. Test less cascaded pulse compression versus greater input port capacitance.'},
 'vc-ff20':{'CFF_fF':20.,'RDTOP_ohm':85000.,'hypothesis':'Two DI-to-GP/DBI-to-GN passive feedforward capacitors supply early gate charge from already metered input ports; test gate delay versus rebound/stress.'},
 'vc-ff40':{'CFF_fF':40.,'RDTOP_ohm':85000.,'hypothesis':'One bounded feedforward dose control; double20fF only if20fF node behavior justifies it.'},
 'vc-dr65':{'CFF_fF':0.,'RDTOP_ohm':65000.,'hypothesis':'Reduce actual predriver regulator feedback target from~3.1V to~2.45V without changing raw3.3V sources or laser rail. Test smaller swing energy versus lower gate overdrive.'}}
HELPERS=[Path(engine.__file__),Path(analysis.__file__),engine.LEGACY,engine.ENERGY,analysis.OPTO_PATH,analysis.RX_PATH,analysis.PARAMETERS]
HELPER_BYTES={str(p.relative_to(ROOT)):p.read_bytes() for p in HELPERS}
CAPS=[('Lout',10e-9,'xdrv.lcap',None),('Dout',1e-9,'xdrv.dcap',None),('rawLaser',1e-9,'laser_c',None),('rawDriver',1e-9,'vdd_c',None),('Bcomp',5e-12,'xdrv.bn2','xdrv.bctrl'),('Tcomp',5e-12,'xdrv.tn2','xdrv.tctrl'),('Lcomp',30e-12,'xdrv.lzc','xdrv.lctrl'),('Dcomp',30e-12,'xdrv.dzc','xdrv.dctrl')]
def emit(p,o):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(p):return engine.sha(p)
def protocol():
 state=0x5ace
 for _ in range(27081):state=((state<<1)&0x7fff)|(((state>>14)^(state>>13))&1)
 return dict(baseline_seed=0x5ace,holdout_seed=state,holdout_phase_offset_bits=27081,frame_bits=4736,prior_holdout_window=[16749,21485],new_holdout_window=[27081,31817],scope='Predeclared nonoverlapping PRBS15 window; no post-holdout circuit retuning, training delay allowed. Not independent random BER.')
def prepare(name,rate,steps=40,level=None,holdout=False):
 spec=SPECS[name];assert steps>=40 and rate>0 and level in (None,0,1)
 assert not holdout or level is None
 config=dict(candidate=name,spec=spec,net_Gbps=rate,steps_per_UI=steps,level=level,holdout=holdout)
 suffix=f'DC-L{level}' if level is not None else f'{"holdout-" if holdout else ""}net{rate:g}-s{steps}'
 folder=BUILD/name/suffix
 if folder.exists():
  m=engine.read_json(folder/'manifest.json');assert m['method_config']==config
  assert sha(folder/'testbench.spice')==m['deck_sha256'] and sha(folder/'stimulus.json')==m['stimulus_sha256']
  for f in ['design.ngspice','sm141064.ngspice','vcsel.spice','driver.spice']:assert sha(folder/f)==m['source_sha256'][f]
  assert sha(folder/'execution-source.py')==m['execution_source_sha256']
  return folder,m
 frozen=engine.read_json(BASE/'manifest.json');assert sha(BASE/'driver.spice')==frozen['source_sha256']['driver.spice']
 folder.mkdir(parents=True,exist_ok=False);m=engine.make_deck(folder,rate,20,steps)
 driver=(BASE/'driver.spice').read_text()
 driver,n=re.subn(r'(?m)^RDTOP DR Dfb 85k$',f'RDTOP DR Dfb {spec["RDTOP_ohm"]:.12g}',driver);assert n==1
 if spec['CFF_fF']:
  driver=driver.replace('.ends vcsel_servo',f'CFFP DI GP {spec["CFF_fF"]:.12g}f\nCFFN DBI GN {spec["CFF_fF"]:.12g}f\n.ends vcsel_servo')
 m['devices']=copy.deepcopy(frozen['devices'])
 if spec.get('single_stage'):
  removed={'XBP1N_0','XBP1P_0','XBN1N_0','XBN1P_0'}
  lines=[]
  for line in driver.splitlines():
   words=line.split()
   if words and words[0] in removed:continue
   if words and words[0] in {'XBP2N_0','XBP2P_0'}:words[2]='DBI';line=' '.join(words)
   if words and words[0] in {'XBN2N_0','XBN2P_0'}:words[2]='DI';line=' '.join(words)
   lines.append(line)
  driver='\n'.join(lines)+'\n'
  m['devices']=[d for d in m['devices'] if d['instance'] not in removed]
  for d in m['devices']:
   if d['instance'] in {'XBP2N_0','XBP2P_0'}:d['nodes'][1]='xdrv.dbi'
   if d['instance'] in {'XBN2N_0','XBN2P_0'}:d['nodes'][1]='xdrv.di'
  m['expressions']=[e for e in m['expressions'] if e not in {'v(xdrv.np)','v(xdrv.nn)'}]
 (folder/'driver.spice').write_text(driver)
 if holdout:
  selection=engine.read_json(EV/'vcsel-selection.json')
  assert selection['parameters_frozen'] and selection['candidate']==name
  assert selection['candidate_spec_frozen']==spec
  assert sha(folder/'driver.spice')==selection['driver_sha256']
  assert protocol()['holdout_seed']==0x4c2d
 expected_mos=69 if spec.get('single_stage') else 73
 assert len(m['devices'])==expected_mos and sum(line.startswith('X') for line in driver.splitlines())==expected_mos
 deck=(folder/'testbench.spice').read_text();deck,n=re.subn(r'(?m)^(XDRV[^\n]*\bATTEN=)[^ ]+',lambda q:q.group(1)+str(spec.get('atten_ohm',50.)),deck);assert n==1
 if holdout:
  assert next(x for x in deck.splitlines() if x.startswith('XDRV '))==selection['xdrv_instance_line_frozen']
 if spec.get('single_stage'):
  for removed_node in ['v(xdrv.np)','v(xdrv.nn)']:deck=deck.replace(' '+removed_node,'')
 if holdout:
  legacy=engine.module(engine.LEGACY,'vcsel_methods_stimulus');rx0=engine.module(ROOT/'scripts/fair_driver_v1/receiver_equal_latency_v2.py','vcsel_methods_rxstim')
  stim=legacy.seeded_stimulus(protocol()['holdout_seed'],rx0);assert len(stim['bits'])==4736;emit(folder/'stimulus.json',stim)
  for port,node,bits in [('VD','d_src',stim['bits']),('VDB','db_src',[1-b for b in stim['bits']])]:
   deck,n=re.subn(rf'(?m)^{port} {node} 0 PWL\([^)]*\)',f'{port} {node} 0 '+legacy.pwl(bits,m['end_s']/4736,3.3,20e-12),deck);assert n==1
 if level is not None:
  for port,node,value in [('VD','d_src',3.3*level),('VDB','db_src',3.3*(1-level))]:
   deck,n=re.subn(rf'(?m)^{port} {node} 0 PWL\([^)]*\)',f'{port} {node} 0 {value}',deck);assert n==1
  deck,n=re.subn(r'(?m)^tran .+$','op',deck);assert n==1
 (folder/'testbench.spice').write_text(deck);(folder/'execution-source.py').write_bytes(SOURCE)
 helper_records={};hp=folder/'execution-sources';hp.mkdir()
 for i,(rel,data) in enumerate(HELPER_BYTES.items()):
  fn=f'{i}-{Path(rel).name}';(hp/fn).write_bytes(data);helper_records[rel]={'copy':fn,'sha256':hashlib.sha256(data).hexdigest()}
 m.update(method_config=config,candidate_spec=spec,execution_source_sha256=SOURCE_HASH,execution_helpers=helper_records,baseline_manifest_sha256=sha(BASE/'manifest.json'),baseline_driver_sha256=sha(BASE/'driver.spice'),source_sha256={**m['source_sha256'],'driver.spice':sha(folder/'driver.spice')},deck_sha256=sha(folder/'testbench.spice'),stimulus_sha256=sha(folder/'stimulus.json'),scope=f'{expected_mos}MOS actual rail/reference schematic,3/7mA,850nm graph proxy,150fF,.5ohm/.2nH,5GHzRX,TT25C,20ps input. Only listed candidate topology, passive feedforward, input damping, or regulator-divider changes. No PVT/layout/PEX/physicalBER claim.',holdout_protocol=protocol() if holdout else None)
 emit(folder/'manifest.json',m);return folder,m

def dc(name,level):
 folder,m=prepare(name,3.2,40,level)
 if (folder/'result.json').exists():return engine.read_json(folder/'result.json')
 start=time.monotonic()
 with (folder/'ngspice.log').open('w') as f:code=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=f,stderr=subprocess.STDOUT,timeout=120).returncode
 raw=folder/'waveform.dat';r=dict(simulation_ok=code==0 and raw.exists(),exit_code=code,solve_s=time.monotonic()-start)
 if r['simulation_ok']:
  a=np.atleast_2d(np.loadtxt(raw,skiprows=1));ix={e:i+1 for i,e in enumerate(m['expressions'])};assert np.isfinite(a).all() and a.shape[1]==len(ix)+1
  legacy=engine.module(engine.LEGACY,'vcsel_methods_dcstress');stress=legacy.stress(a,ix,m['devices']);cur=float(a[-1,1]*1e3);target=3+4*level
  r.update(current_mA=cur,target_mA=target,error_percent=100*(cur/target-1),stress=stress,terminal_screen_pass=all(s['screen_pass'] for s in stress),max_body_forward_V=max(s['max_body_forward_V'] for s in stress),source_power_W={p:float(-a[-1,ix[f'v({n})']]*a[-1,ix[f'i({p})']]) for p,n in m['ports'].items()},nodes_final_V={e:float(a[-1,i]) for e,i in ix.items() if e.startswith('v(')},waveform=legacy.compress(raw))
  r['DC_screen_pass']=bool(abs(r['error_percent'])<=1 and r['terminal_screen_pass'] and r['max_body_forward_V']<=.3)
 r.update(manifest_sha256=sha(folder/'manifest.json'),deck_sha256=sha(folder/'testbench.spice'),log_sha256=sha(folder/'ngspice.log'));emit(folder/'result.json',r)
 print('DC',name,level,r.get('current_mA'),r.get('DC_screen_pass'),flush=True);return r

def storage(folder,m,r):
 with gzip.open(folder/'waveform.dat.gz','rb') as f:
  digest=hashlib.sha256();header=next(f);digest.update(header);first=next(f);digest.update(first);last=first
  for line in f:digest.update(line);last=line
 assert digest.hexdigest()==r['waveform']['raw_sha256']
 a=np.array([np.fromstring(first,sep=' '),np.fromstring(last,sep=' ')]);ix={e:k+1 for k,e in enumerate(m['expressions'])}
 caps=list(CAPS);c=m['candidate_spec']['CFF_fF']*1e-15
 if c:caps += [('FFP',c,'xdrv.di','xdrv.gp'),('FFN',c,'xdrv.dbi','xdrv.gn')]
 rows={}
 for name,c,p,n in caps:
  v=a[:,ix['v('+p+')']]-(a[:,ix['v('+n+')']] if n else 0);u=.5*c*v*v
  rows[name]=dict(C_F=c,initial_voltage_V=float(v[0]),final_voltage_V=float(v[1]),delta_J=float(u[1]-u[0]))
 return dict(capacitors=rows,explicit_cap_delta_J=sum(x['delta_J'] for x in rows.values()),source_net_J=r['total_energy']['net_J'],scope='Actual native first/last supply, compensation and added CFF energies. Excludes intrinsic MOS, VCSEL C and inductors; not full energy balance or periodic steady-state efficiency.')

def frame(name,rate,steps=40,holdout=False):
 for l in [0,1]:assert dc(name,l).get('DC_screen_pass'),f'DC failed {name}'
 folder,m=prepare(name,rate,steps,holdout=holdout)
 if not (folder/'result.json').exists():engine.solve(folder,m)
 r=engine.read_json(folder/'result.json');assert r['simulation_ok']
 if (folder/'analysis.json').exists():
  met=engine.read_json(folder/'analysis.json');assert met['result_sha256']==sha(folder/'result.json');return met
 rx=engine.module(analysis.RX_PATH,'vcsel_methods_rx');opto=engine.module(analysis.OPTO_PATH,'vcsel_methods_opto')
 met,traces=analysis.analyze(folder,rx,opto,False,128);obs=met['observed'];full=met['pathways']['actual_graph_5GHzRX']
 met.update(candidate=name,candidate_spec=SPECS[name],DC_calibration_pass=True,holdout=holdout,combined_screen_pass=bool(full['screen_pass'] and obs['terminal_screen_pass'] and obs['max_body_forward_V']<=.3 and obs['within_calibrated_electrical_and_optical_current_range']),result_sha256=sha(folder/'result.json'),manifest_sha256=sha(folder/'manifest.json'),execution_source_sha256=m['execution_source_sha256'])
 emit(folder/'analysis.json',met);emit(folder/'excerpt.json',{k:v.tolist() for k,v in traces.items()});emit(folder/'storage.json',storage(folder,m,r))
 print('FRAME',name,rate,steps,'holdout',holdout,'PASS',met['combined_screen_pass'],'err',full['errors'],'amp',full['worst_signed_margin_uAeq'],'UI',full['one_sided_margin_UI'],'pJ',met['source_energy_pJ_per_attempted_net_bit']['positive'],'range',obs['electrical_current_range_mA'],'body',obs['max_body_forward_V'],flush=True);return met

def summarize():
 rows=[];dcs=[]
 for p in sorted(BUILD.glob('*/DC-L*/result.json')):
  r=engine.read_json(p);m=engine.read_json(p.parent/'manifest.json');dcs.append(dict(candidate=m['method_config']['candidate'],level=m['method_config']['level'],source_case=str(p.parent.relative_to(ROOT)),result_sha256=sha(p),**{k:r.get(k) for k in ['current_mA','error_percent','DC_screen_pass','terminal_screen_pass','max_body_forward_V']}))
 for p in sorted(BUILD.glob('*/*/analysis.json')):
  r=engine.read_json(p);rows.append(dict(candidate=r['candidate'],net_Gbps=r['net_Gbps'],steps_per_UI=r['steps_per_UI'],holdout=r['holdout'],combined_screen_pass=r['combined_screen_pass'],full_receiver=r['pathways']['actual_graph_5GHzRX'],electrical_receiver=r['pathways']['actual_electrical'],stages=r['stages'],source_energy_pJ_per_attempted_net_bit=r['source_energy_pJ_per_attempted_net_bit'],energy_by_source_pJ_per_attempted_net_bit=r['energy_by_source_pJ_per_attempted_net_bit'],observed=r['observed'],storage=engine.read_json(p.parent/'storage.json'),source_case=r['run'],analysis_sha256=sha(p),deck_sha256=r['deck_sha256'],waveform=r['waveform']))
 out=dict(schema='vcsel-methods-v1',candidates=SPECS,dc=dcs,rows=rows,holdout_protocol=protocol(),scope='Nominal deterministic schematic only; all7 source ports counted. External supply IC/clock/RX overhead excluded. OP initial state, no long-pattern periodic closure, no PVT/layout/PEX/silicon/optical measurement.');emit(EV/'vcsel-methods.json',out);return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--candidate',choices=SPECS);p.add_argument('--rates',nargs='+',type=float);p.add_argument('--steps',type=int,default=40);p.add_argument('--holdout',action='store_true');args=p.parse_args()
 emit(EV/'vcsel-holdout-protocol.json',protocol())
 if args.candidate:
  for level in [0,1]:dc(args.candidate,level)
  for rate in args.rates or []:frame(args.candidate,rate,args.steps,args.holdout)
 summarize()
