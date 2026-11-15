#!/usr/bin/env python3
"""Finite transistor upstream CMOS interface; same frozen VCSEL load and receiver."""
from pathlib import Path
import argparse,copy,gzip,hashlib,importlib.util,json,re,shutil,subprocess,sys,time
import numpy as np
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts/highspeed_workbench_20261110'))
import vcsel_x10_run as engine
import vcsel_x10_analyze as analysis
BUILD=ROOT/'build/driver-interface-20261115/VCSEL'
EV=ROOT/'evidence/driver-interface-20261115'
BASE69=ROOT/'build/driver-methods-20261111/VCSEL/vc-single-r150/net6.4-s40'
BASE73=ROOT/'build/ab-improvement-20261111/VCSEL/vc-atten50-steer20/net6.4-edge20-s40'
SOURCE=Path(__file__).read_bytes();SOURCE_HASH=hashlib.sha256(SOURCE).hexdigest()
HELPERS=[Path(engine.__file__),Path(analysis.__file__),engine.LEGACY,engine.ENERGY,analysis.OPTO_PATH,analysis.RX_PATH,analysis.PARAMETERS]
HELPER_BYTES={str(p.relative_to(ROOT)):p.read_bytes() for p in HELPERS}
SPECS={
 'single-phy4':dict(core=69,nW_um=4.,pW_um=8.,internal_R_ohm=150.,hypothesis='Replace ideal command-driven pin source by finite GF180 CMOS inverter pair; preserve fixed50ohm series R and 150ohm internal input damping.'),
 'double-phy4':dict(core=73,nW_um=4.,pW_um=8.,internal_R_ohm=50.,hypothesis='Same finite upstream output cell attached to original two-stage73MOS core; load-isolation control.'),
 'single-phy12':dict(core=69,nW_um=12.,pW_um=24.,internal_R_ohm=150.,hypothesis='Only widen finite upstream CMOS from4/8to12/24um to reduce output resistance; command gate energy and all added supply current remain counted.'),
 'single-phy4-r25k':dict(core=69,nW_um=4.,pW_um=8.,internal_R_ohm=150.,shunt_R_ohm=25000.,hypothesis='Only reduce historical input attenuation/static load: RADI/RADBI2500to25000ohm; preserve upstream4/8um and all series resistors. No vendor50ohm termination was specified for these shunts. Check input default/stress separately.'),
}
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def emit(p,o):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def protocol():
 s=0x5ace
 for _ in range(8192):s=((s<<1)&0x7fff)|(((s>>14)^(s>>13))&1)
 return dict(development_seed=0x5ace,holdout_seed=s,holdout_seed_hex=hex(s),phase_offset_bits=8192,window=[8192,12928],previous_windows=[[0,4736],[16749,21485],[27081,31817]],scope='Predeclared disjoint PRBS15 period window; not independent random BER. No circuit changes after holdout.')
def prepare(name,rate,steps=40,level=None,holdout=False):
 assert rate>0 and steps>=40 and level in [None,0,1] and not(holdout and level is not None)
 spec=SPECS[name];base=BASE69 if spec['core']==69 else BASE73
 cfg=dict(candidate=name,spec=spec,net_Gbps=rate,steps_per_UI=steps,level=level,holdout=holdout)
 case=f'DC-L{level}' if level is not None else f'{"holdout-" if holdout else ""}net{rate:g}-s{steps}'
 folder=BUILD/name/case
 if (folder/'manifest.json').exists():
  m=read(folder/'manifest.json');assert m['interface_config']==cfg
  assert sha(folder/'testbench.spice')==m['deck_sha256'] and sha(folder/'stimulus.json')==m['stimulus_sha256']
  for n,v in m['source_sha256'].items():
   if n!='runner.py':assert sha(folder/n)==v
  assert sha(folder/'execution-source.py')==m['execution_source_sha256'];return folder,m
 folder.mkdir(parents=True,exist_ok=False)
 m=copy.deepcopy(read(base/'manifest.json'));assert sha(base/'driver.spice')==m['source_sha256']['driver.spice'];assert sha(base/'testbench.spice')==m['deck_sha256']
 for n in ['design.ngspice','sm141064.ngspice','vcsel.spice','driver.spice']:shutil.copy2(base/n,folder/n)
 if 'shunt_R_ohm' in spec:
  driver=(folder/'driver.spice').read_text()
  driver,n=re.subn(r'(?m)^(RAD(?:B)?I \w+ VSS) 2500$',lambda q:q.group(1)+' '+str(spec['shunt_R_ohm']),driver);assert n==2
  (folder/'driver.spice').write_text(driver)
  m['source_sha256']['driver.spice']=sha(folder/'driver.spice')
 st=read(base/'stimulus.json');legacy=engine.module(engine.LEGACY,'interface_stimulus')
 if holdout:
  sel=read(EV/'vcsel-interface-selection.json');assert sel['parameters_frozen'] and sel['candidate']==name and sel['spec']==spec
  rx=engine.module(ROOT/'scripts/fair_driver_v1/receiver_equal_latency_v2.py','interface_stimulus_rx');st=legacy.seeded_stimulus(protocol()['holdout_seed'],rx)
 emit(folder/'stimulus.json',st);assert len(st['bits'])==4736
 ui=4096/4736/(rate*1e9);end=4736*ui
 deck=(base/'testbench.spice').read_text();deck='VCSEL finite upstream CMOS '+name+'\n'+deck.split('\n',1)[1]
 for port,node,bits in [('VD','d_cmd',st['bits']),('VDB','db_cmd',[1-b for b in st['bits']])]:
  value=str(3.3*(level if port=='VD' else 1-level)) if level is not None else legacy.pwl(bits,ui,3.3,20e-12)
  deck,n=re.subn(rf'(?m)^{port} \w+ 0 PWL\([^)]*\)',f'{port} {node} 0 '+value,deck);assert n==1
 deck,n=re.subn(r'(?m)^tran .+$','op' if level is not None else f'tran {ui/steps:.16g} {end:.16g} 0 {ui/steps:.16g}',deck);assert n==1
 deck,n=re.subn(r'(?m)^(XDRV[^\n]*\bATTEN=)[^ ]+',lambda q:q.group(1)+str(spec['internal_R_ohm']),deck);assert n==1
 phy=['* Finite generic CMOS output model, NOT vendor PHY/PAD/ESD conformity.',
      'VPHY phy_src 0 3.3','RPHY phy_src phy_r .25','LPHY phy_r vphy .2n','RCPHY vphy phy_c .1','CPHY phy_c 0 1n']
 newdev=[]
 for branch,out,gate in [('D','d_src','db_cmd'),('DB','db_src','d_cmd')]:
  for typ,w in [('N',spec['nW_um']),('P',spec['pW_um'])]:
   rail='0' if typ=='N' else 'vphy';model='nmos_3p3' if typ=='N' else 'pmos_3p3';inst='XPHY'+branch+typ
   params=[f'w={w:g}u','l=.28u',f'ad={w*.44:g}p',f'as={w*.44:g}p',f'pd={2*w+.88:g}u',f'ps={2*w+.88:g}u']
   phy.append(' '.join([inst,out,gate,rail,rail,model,*params]));newdev.append(dict(instance=inst,model=model,nodes=[out,gate,rail,rail],parameters=params))
 deck=deck.replace('RD d_src d 50','\n'.join(phy)+'\nRD d_src d 50')
 expr=m['expressions']+['v(d_cmd)','v(db_cmd)','v(phy_src)','v(phy_r)','v(vphy)','v(phy_c)','v(d)','v(db)','i(VPHY)']
 assert len(expr)==len(set(expr));m['expressions']=expr;m['ports']={**m['ports'],'VD':'d_cmd','VDB':'db_cmd','VPHY':'phy_src'}
 m['devices']+=newdev
 deck,n=re.subn(r'(?m)^save .+$','save '+' '.join(expr),deck);assert n==1
 deck,n=re.subn(r'(?m)^wrdata waveform.dat .+$','wrdata waveform.dat '+' '.join(expr),deck);assert n==1
 if holdout:
  assert sha(folder/'driver.spice')==sel['driver_sha256']
  frozen_lines=[x for x in deck.splitlines() if x.startswith(('VPHY ','RPHY ','LPHY ','RCPHY ','CPHY ','XPHY','RD ','RDB ','XDRV '))]
  assert frozen_lines==sel['interface_and_core_instance_lines']
 (folder/'testbench.spice').write_text(deck);(folder/'execution-source.py').write_bytes(SOURCE)
 helper={};hp=folder/'execution-sources';hp.mkdir()
 for i,(rel,data) in enumerate(HELPER_BYTES.items()):
  fn=f'{i}-{Path(rel).name}';(hp/fn).write_bytes(data);helper[rel]=dict(copy=fn,sha256=hashlib.sha256(data).hexdigest())
 m.update(schema='vcsel-finite-interface-v1',interface_config=cfg,candidate_spec=spec,execution_source_sha256=SOURCE_HASH,execution_helpers=helper,baseline_case=str(base.relative_to(ROOT)),baseline_manifest_sha256=sha(base/'manifest.json'),baseline_driver_sha256=sha(base/'driver.spice'),net_Gbps=rate,line_GBd=1e-9/ui,UI_ps=ui*1e12,source_edge_ps_0_to_100=20,steps_per_UI=steps,end_s=end,deck_sha256=sha(folder/'testbench.spice'),stimulus_sha256=sha(folder/'stimulus.json'),scope='Generic transistor-level finite CMOS interface; same emitter/current/RX. Eight source ports counted including both ideal command gates and VPHY. Fixed50ohm series R remains; no calibrated vendor PHY/PAD/ESD/Sparameters/noise/BER qualification.',holdout_protocol=protocol() if holdout else None)
 emit(folder/'manifest.json',m);return folder,m
def dc(name,level):
 folder,m=prepare(name,6.4,40,level)
 if (folder/'result.json').exists():return read(folder/'result.json')
 t=time.monotonic()
 with (folder/'ngspice.log').open('w') as out:code=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=out,stderr=subprocess.STDOUT,timeout=120).returncode
 raw=folder/'waveform.dat';r=dict(simulation_ok=code==0 and raw.exists(),exit_code=code,solve_s=time.monotonic()-t)
 if r['simulation_ok']:
  a=np.atleast_2d(np.loadtxt(raw,skiprows=1));ix={e:i+1 for i,e in enumerate(m['expressions'])};assert np.isfinite(a).all() and a.shape[1]==len(ix)+1
  legacy=engine.module(engine.LEGACY,'interface_dc');s=legacy.stress(a,ix,m['devices']);cur=float(a[-1,1]*1e3);target=3+4*level
  r.update(current_mA=cur,target_mA=target,error_percent=100*(cur/target-1),stress=s,terminal_screen_pass=all(x['screen_pass'] for x in s),max_body_forward_V=max(x['max_body_forward_V'] for x in s),source_power_W={p:float(-a[-1,ix[f'v({n})']]*a[-1,ix[f'i({p})']]) for p,n in m['ports'].items()},nodes_final_V={e:float(a[-1,i]) for e,i in ix.items() if e.startswith('v(')},waveform=legacy.compress(raw))
  r['DC_screen_pass']=abs(r['error_percent'])<=1 and r['terminal_screen_pass'] and r['max_body_forward_V']<=.3
 r.update(manifest_sha256=sha(folder/'manifest.json'),deck_sha256=sha(folder/'testbench.spice'),log_sha256=sha(folder/'ngspice.log'));emit(folder/'result.json',r);print('DC',name,level,r.get('DC_screen_pass'),r.get('current_mA'),flush=True);return r
def diagnostics(folder,m,r):
 a=np.loadtxt(folder/'waveform.dat.gz',skiprows=1);t=a[:,0];ix={e:i+1 for i,e in enumerate(m['expressions'])};dt=t[-1]-t[0]
 def v(e):return a[:,ix[e]]
 obs={}
 for port,n in m['ports'].items():
  i=-v('i('+port+')');obs[port]=dict(source_peak_mA=float(max(i)*1e3),sink_peak_mA=float(max(-i)*1e3),mean_source_mA=float(np.trapezoid(i,t)/dt*1e3))
 pins={}
 for src,pin in [('d_src','d'),('db_src','db')]:
  i=(v('v('+src+')')-v('v('+pin+')'))/50
  pins[pin]=dict(max_positive_mA=float(max(i)*1e3),max_negative_mA=float(min(i)*1e3),rms_mA=float(np.sqrt(np.trapezoid(i*i,t)/dt)*1e3))
 energy_phy=r['energy_by_port']['VPHY'];commands={k:sum(r['energy_by_port'][s][k] for s in ['VD','VDB']) for k in ['positive_J','returned_J','net_J']}
 return dict(source_currents=obs,pin_series_currents=pins,interface_source_energy_pJ_per_payload_bit={k:(energy_phy[k]+commands[k])*1e12/4096 for k in commands},source_boundary='All8 ports; VPHY plus command gates counted; optical/RX/host clock and still-upstream logic excluded.',native_samples=len(t))
def frame(name,rate,steps=40,holdout=False):
 for l in [0,1]:assert dc(name,l).get('DC_screen_pass'),f'DC failure {name}'
 folder,m=prepare(name,rate,steps,holdout=holdout)
 if not(folder/'result.json').exists():engine.solve(folder,m)
 r=read(folder/'result.json');assert r['simulation_ok']
 if (folder/'analysis.json').exists():
  out=read(folder/'analysis.json');assert out['result_sha256']==sha(folder/'result.json');return out
 rx=engine.module(analysis.RX_PATH,'interface_rx');opto=engine.module(analysis.OPTO_PATH,'interface_opto')
 met,traces=analysis.analyze(folder,rx,opto,False,128);obs=met['observed'];full=met['pathways']['actual_graph_5GHzRX']
 met.update(candidate=name,config=m['interface_config'],DC_calibration_pass=True,combined_screen_pass=bool(full['screen_pass'] and obs['terminal_screen_pass'] and obs['max_body_forward_V']<=.3 and obs['within_calibrated_electrical_and_optical_current_range']),result_sha256=sha(folder/'result.json'),manifest_sha256=sha(folder/'manifest.json'),interface_observed=diagnostics(folder,m,r))
 emit(folder/'analysis.json',met);emit(folder/'excerpt.json',{k:v.tolist() for k,v in traces.items()})
 print('FRAME',name,rate,steps,holdout,'PASS',met['combined_screen_pass'],'err',full['errors'],'amp',full['worst_signed_margin_uAeq'],'UI',full['one_sided_margin_UI'],'E+',met['source_energy_pJ_per_attempted_net_bit']['positive'],'I',obs['electrical_current_range_mA'],'body',obs['max_body_forward_V'],flush=True);return met
def summarize():
 rows=[];dcs=[]
 for p in sorted(BUILD.glob('*/DC-L*/result.json')):
  r=read(p);m=read(p.parent/'manifest.json');dcs.append(dict(candidate=m['interface_config']['candidate'],source_case=str(p.parent.relative_to(ROOT)),result_sha256=sha(p),**{k:r.get(k) for k in ['current_mA','target_mA','DC_screen_pass','error_percent','terminal_screen_pass','max_body_forward_V']}))
 for p in sorted(BUILD.glob('*/*/analysis.json')):
  r=read(p);m=read(p.parent/'manifest.json');rows.append(dict(candidate=r['candidate'],config=r['config'],source_case=r['run'],MOS=len(m['devices']),full_receiver=r['pathways']['actual_graph_5GHzRX'],electrical_receiver=r['pathways']['actual_electrical'],stages=r['stages'],observed=r['observed'],interface_observed=r['interface_observed'],energy_pJ=r['source_energy_pJ_per_attempted_net_bit'],energy_by_source_pJ=r['energy_by_source_pJ_per_attempted_net_bit'],combined_screen_pass=r['combined_screen_pass'],analysis_sha256=sha(p),manifest_sha256=sha(p.parent/'manifest.json'),waveform=r['waveform']))
 emit(EV/'vcsel-interface-summary.json',dict(schema='vcsel-finite-interface-summary-v1',candidates=SPECS,dc=dcs,rows=rows,holdout_protocol=protocol(),scope='Generic finite CMOS interface, not vendor PHY compliance; fixed load/RX and eight-source energy boundary. Nominal deterministic frames, no PVT/long-term/physicalBER or layout qualification.'))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--candidate',choices=SPECS);p.add_argument('--rates',nargs='+',type=float);p.add_argument('--steps',type=int,default=40);p.add_argument('--holdout',action='store_true');a=p.parse_args()
 prot=EV/'vcsel-interface-protocol.json'
 if prot.exists():assert read(prot)==protocol()
 else:emit(prot,protocol())
 if a.candidate:
  for r in a.rates or []:frame(a.candidate,r,a.steps,a.holdout)
 summarize()
