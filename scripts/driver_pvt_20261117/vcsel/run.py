#!/usr/bin/env python3
"""Frozen finite-input VCSEL MOS PVT screening; fixed emitter/RX assumptions."""
from pathlib import Path
import argparse,copy,gzip,hashlib,importlib.util,json,os,re,shutil,subprocess,sys,time
import numpy as np
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts/highspeed_workbench_20261110'))
import vcsel_x10_run as engine
import vcsel_x10_analyze as analysis
BUILD=ROOT/'build/driver-pvt-20261117/vcsel'
EV=ROOT/'evidence/driver-pvt-20261117/vcsel'
BASE=ROOT/'build/driver-interface-20261115/VCSEL/single-phy12/net8.8-s40'
SOURCE=Path(__file__).read_bytes()
GRID={
 'tt25':dict(section='typical',temp_C=25,rail_scale=1),
 'ttcold':dict(section='typical',temp_C=-40,rail_scale=1),
 'tthot':dict(section='typical',temp_C=85,rail_scale=1),
 'ttlow':dict(section='typical',temp_C=25,rail_scale=.95),
 'tthigh':dict(section='typical',temp_C=25,rail_scale=1.05),
 'sshotlow':dict(section='ss',temp_C=85,rail_scale=.95),
 'ffcoldhigh':dict(section='ff',temp_C=-40,rail_scale=1.05),
 'sfhotlow':dict(section='sf',temp_C=85,rail_scale=.95),
 'fscoldhigh':dict(section='fs',temp_C=-40,rail_scale=1.05),
}
VARIANTS={'frozen':dict(nW_um=12.,pW_um=24.,internal_R_ohm=150.,hypothesis='Frozen Nov15 finite CMOS input candidate.')}
VARIANTS['cmd-r100']={**VARIANTS['frozen'],'command_R_ohm':100.,'hypothesis':'Only add 100ohm to each upstream CMOS gate command. Reduce falling-gate Cgd feedthrough at d_src/db_src; preserve ideal command20ps and count its source energy. May worsen delay/short-circuit energy.'}
VARIANTS['cmd-r330']={**VARIANTS['frozen'],'command_R_ohm':330.,'hypothesis':'Increase only the declared gate-command resistor100to330ohm after100ohm reduced but did not clear SS body and TT/FS high-rail VDS screens. Same speed/energy penalties require full-frame testing.'}
VARIANTS['cmd-r330-atten75']={**VARIANTS['cmd-r330'],'internal_R_ohm':75.,'hypothesis':'After330ohm clears SS electrical stress but causes178RXerrors at8.8, reduce only internal input150to75ohm. Retain command330ohm and all MOS sizes. Test whether lower input RC recovers GP/current edges without unsafe overshoot.'}
FILES=['design.ngspice','sm141064.ngspice','vcsel.spice','driver.spice']
HELPERS=[Path(engine.__file__),Path(analysis.__file__),engine.LEGACY,engine.ENERGY,analysis.OPTO_PATH,analysis.RX_PATH,analysis.PARAMETERS]
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def emit(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+f'.tmp-{os.getpid()}');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(p)
def protocol():
 return dict(schema='vcsel-pvt-protocol-v1',grid=GRID,baseline=str(BASE.relative_to(ROOT)),baseline_manifest_sha256=sha(BASE/'manifest.json'),baseline_driver_sha256=sha(BASE/'driver.spice'),swept_sources=['VLASER','VDD','VREF','VPHY'],fixed_sources={'VSET':.15,'VREGSET':.3263157894736842,'VD_VDB_high':3.3,'command_edge_ps':20},short_line_bits=1024,full_line_bits=4736,payload_bits=4096,net_rates_Gbps=[8.8,6.4],dc_error_percent=1,body_forward_limit_V=.3,terminal_limit_V=3.63,current_domain_mA=[2,7.5],RX_GHz=5,amplitude_margin_uAeq=7.5,timing_margin_UI=.37,scope='MOS process/.temp and 3.3V source sweep with fixed25C emitter graph I-V/optical model,150fF,0.5ohm/0.2nH. Ideal passive values and VSET/VREGSET precision boundaries do not vary. Not full emitter temperature, resistor tolerance, PHY conformity or statistical BER. Short1024-bit probes never claim payload RX performance.')
def ensure_protocol():
 p=EV/'protocol.json';q=protocol()
 if p.exists():assert read(p)==q
 else:emit(p,q)
def prepare(variant,corner,rate=8.8,steps=40,kind='short',level=None,holdout=False):
 ensure_protocol();spec=VARIANTS[variant];c=GRID[corner]
 assert kind in ['dc','short','full'] and (kind=='dc')==(level is not None)
 count=1024 if kind=='short' else 4736
 cfg=dict(variant=variant,corner=corner,pvt=c,net_Gbps=rate,steps_per_UI=steps,kind=kind,level=level,spec=spec,line_bits=count)
 if holdout:
  selection=read(EV/'selection.json');assert kind=='full' and variant==selection['variant'] and spec==selection['spec']
  cfg['holdout_protocol']=selection['holdout_protocol']
 case=f'DC-L{level}' if kind=='dc' else f'{kind}-net{rate:g}-s{steps}'
 if holdout:case='holdout-'+case
 folder=BUILD/variant/corner/case
 if (folder/'manifest.json').exists():
  m=read(folder/'manifest.json');assert m['pvt_config']==cfg
  assert sha(folder/'testbench.spice')==m['deck_sha256'] and sha(folder/'stimulus.json')==m['stimulus_sha256']
  assert sha(folder/'execution-source.py')==m['execution_source_sha256']
  for n,h in m['source_sha256'].items():assert sha(folder/n)==h
  return folder,m
 folder.mkdir(parents=True,exist_ok=False)
 old=read(BASE/'manifest.json');assert sha(BASE/'testbench.spice')==old['deck_sha256']
 for name in FILES:
  assert sha(BASE/name)==old['source_sha256'][name]
  target=BUILD/'_inputs'/name;target.parent.mkdir(parents=True,exist_ok=True)
  if target.exists():assert sha(target)==sha(BASE/name)
  else:shutil.copy2(BASE/name,target)
  (folder/name).symlink_to('../../../_inputs/'+name)
 m=copy.deepcopy(old);st=read(BASE/'stimulus.json')
 if holdout:
  legacy=engine.module(engine.LEGACY,'pvt_holdout_stimulus');rx=engine.module(ROOT/'scripts/fair_driver_v1/receiver_equal_latency_v2.py','pvt_holdout_rx')
  st=legacy.seeded_stimulus(selection['holdout_protocol']['seed'],rx)
 fullbits=st['bits'];bits=fullbits[:count]
 # Keep full original labels in short-probe metadata but explicitly forbid full RX use.
 st['bits']=bits;emit(folder/'stimulus.json',st)
 deck=(BASE/'testbench.spice').read_text();deck=f'VCSEL MOS PVT {variant} {corner} {kind}\n'+deck.split('\n',1)[1]
 deck,n=re.subn(r'(?m)^\.lib "sm141064.ngspice" \w+$',f'.lib "sm141064.ngspice" {c["section"]}',deck);assert n==1
 deck,n=re.subn(r'(?m)^\.temp .+$',f'.temp {c["temp_C"]}',deck);assert n==1
 for port in ['VLASER','VDD','VREF','VPHY']:
  deck,n=re.subn(rf'(?m)^({port} \w+ 0) 3\.3$',lambda z:z.group(1)+f' {3.3*c["rail_scale"]:.12g}',deck);assert n==1
 ui=4096/4736/(rate*1e9);end=count*ui;legacy=engine.module(engine.LEGACY,'pvt_stimulus')
 for port,node,bb in [('VD','d_cmd',bits),('VDB','db_cmd',[1-b for b in bits])]:
  val=str(3.3*(level if port=='VD' else 1-level)) if level is not None else legacy.pwl(bb,ui,3.3,20e-12)
  deck,n=re.subn(rf'(?m)^{port} {node} 0 PWL\([^)]*\)',f'{port} {node} 0 {val}',deck);assert n==1
 deck,n=re.subn(r'(?m)^tran .+$','op' if kind=='dc' else f'tran {ui/steps:.16g} {end:.16g} 0 {ui/steps:.16g}',deck);assert n==1
 deck,n=re.subn(r'(?m)^(XDRV[^\n]*\bATTEN=)[^ ]+',lambda z:z.group(1)+str(spec['internal_R_ohm']),deck);assert n==1
 # Only declared physical mechanisms may differ from the frozen source.
 gate_map={'d_cmd':'phy_d_gate','db_cmd':'phy_db_gate'} if spec.get('command_R_ohm') else {}
 if gate_map:
  for source,node in gate_map.items():
   deck=deck.replace('XPHYDN ',f'RCMD_{source} {source} {node} {spec["command_R_ohm"]:g}\nXPHYDN ',1)
   expr=f'v({node})';m['expressions'].append(expr)
   deck=re.sub(r'(?m)^(save .+)$',lambda z:z.group(1)+' '+expr,deck)
   deck=re.sub(r'(?m)^(wrdata waveform.dat .+)$',lambda z:z.group(1)+' '+expr,deck)
 for device in m['devices']:
  if not device['instance'].startswith('XPHY'):continue
  device['nodes'][1]=gate_map.get(device['nodes'][1],device['nodes'][1])
  width=spec['nW_um'] if device['model']=='nmos_3p3' else spec['pW_um']
  params=[f'w={width:g}u','l=.28u',f'ad={width*.44:g}p',f'as={width*.44:g}p',f'pd={2*width+.88:g}u',f'ps={2*width+.88:g}u']
  device['parameters']=params
  newline=' '.join([device['instance'],*device['nodes'],device['model'],*params])
  deck,n=re.subn(rf'(?m)^{device["instance"]} .+$',newline,deck);assert n==1
 (folder/'testbench.spice').write_text(deck);(folder/'execution-source.py').write_bytes(SOURCE)
 if holdout:
  assert m['devices']==selection['devices'] and m['ports']==selection['ports']
  assert {n:sha(folder/n) for n in FILES}==selection['source_sha256']
  def canonical(text):return re.sub(r'(?m)^(VD|VDB) \w+ 0 PWL\([^)]*\)',r'\1 STIMULUS_REMOVED',text)
  assert hashlib.sha256(canonical(deck).encode()).hexdigest()==selection['canonical_deck_sha256']
 helper={};hp=folder/'execution-sources';hp.mkdir()
 for i,p in enumerate(HELPERS):
  data=p.read_bytes();fn=f'{i}-{p.name}';(hp/fn).write_bytes(data);helper[str(p.relative_to(ROOT))]=dict(copy=fn,sha256=hashlib.sha256(data).hexdigest())
 m.update(schema='vcsel-mos-pvt-v1',pvt_config=cfg,scope=protocol()['scope'],baseline_case=str(BASE.relative_to(ROOT)),baseline_manifest_sha256=sha(BASE/'manifest.json'),source_sha256={n:sha(folder/n) for n in FILES},deck_sha256=sha(folder/'testbench.spice'),stimulus_sha256=sha(folder/'stimulus.json'),execution_source_sha256=hashlib.sha256(SOURCE).hexdigest(),execution_helpers=helper,net_Gbps=rate,line_GBd=1e-9/ui,UI_ps=ui*1e12,steps_per_UI=steps,end_s=end,frame_bits=count,attempted_payload_bits=4096 if kind=='full' else None,kind=kind)
 emit(folder/'manifest.json',m);return folder,m
def solve(folder,m):
 p=folder/'result.json'
 if p.exists():
  r=read(p);assert r['manifest_sha256']==sha(folder/'manifest.json') and r['deck_sha256']==sha(folder/'testbench.spice')
  return r
 start=time.monotonic();code=None
 recovery=(folder/'waveform.dat.gz').exists() and not(folder/'waveform.dat').exists()
 if recovery:
  # First short probe reached compress() after successful ngspice, then numpy.bool
  # serialization failed. Preserve native bytes/log/execution snapshot and reanalyze.
  code=0
 else:
  with (folder/'ngspice.log').open('w') as log:
   try:code=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=log,stderr=subprocess.STDOUT,timeout=600).returncode
   except subprocess.TimeoutExpired:pass
 log=(folder/'ngspice.log').read_text();raw=folder/'waveform.dat'
 r=dict(simulation_ok=False,exit_code=code,solve_s=time.monotonic()-start,log_sha256=sha(folder/'ngspice.log'),manifest_sha256=sha(folder/'manifest.json'),deck_sha256=sha(folder/'testbench.spice'))
 if recovery:
  r.update(solve_s=None,postprocess_recovery='Original ngspice returned0 and completed native compression; result JSON failed on numpy.bool. This reanalysis preserves source/deck/log/native bytes; no new SPICE.',postprocess_source_sha256=hashlib.sha256(SOURCE).hexdigest())
  (folder/'postprocess-recovery-source.py').write_bytes(SOURCE)
 if raw.exists() or recovery:
  a=np.atleast_2d(np.loadtxt(folder/'waveform.dat.gz' if recovery else raw,skiprows=1));t=a[:,0];ix={e:k+1 for k,e in enumerate(m['expressions'])}
  complete=bool(m['kind']=='dc' or abs(t[-1]-m['end_s'])<1e-16)
  r.update(native_end_s=float(t[-1]),simulation_complete=complete)
  if code==0 and complete and 'Timestep too small' not in log and 'simulation(s) aborted' not in log and np.isfinite(a).all():
   assert a.shape[1]==len(ix)+1
   legacy=engine.module(engine.LEGACY,'pvt_stress');stress=legacy.stress(a,ix,m['devices']);maxpair=max((abs(v),q['instance'],key) for q in stress for key,v in q['max_abs_terminal_V'].items())
   r.update(simulation_ok=True,stress=stress,terminal_peak=dict(value_V=maxpair[0],instance=maxpair[1],pair=maxpair[2]),terminal_screen_pass=all(q['screen_pass'] for q in stress),max_body_forward_V=max(q['max_body_forward_V'] for q in stress),native_samples=len(t),current_min_mA=float(a[:,1].min()*1e3),current_max_mA=float(a[:,1].max()*1e3))
   nodes=['v(d_src)','v(db_src)','v(xdrv.di)','v(xdrv.dbi)','v(xdrv.gp)','v(xdrv.gn)','v(xdrv.dr)','v(vl)','v(xdrv.bctrl)','v(xdrv.tctrl)','v(xdrv.sbase)','v(xdrv.stail)','v(out)','v(vphy)','v(d_cmd)','v(db_cmd)']
   nodes += [n for n in ['v(phy_d_gate)','v(phy_db_gate)'] if n in ix]
   r['node_ranges_V']={n:[float(a[:,ix[n]].min()),float(a[:,ix[n]].max())] for n in nodes}
   if m['kind']=='dc':
    current=float(a[-1,1]*1e3);target=3+4*m['pvt_config']['level']
    r.update(current_mA=current,target_mA=target,error_percent=100*(current/target-1),source_power_W={p:float(-a[-1,ix[f'v({n})']]*a[-1,ix[f'i({p})']]) for p,n in m['ports'].items()})
    r['DC_screen_pass']=abs(r['error_percent'])<=1 and r['terminal_screen_pass'] and r['max_body_forward_V']<=.3
   else:
    energy=engine.module(engine.ENERGY,'pvt_energy');ledger={p:energy.signed_integrals(t,-a[:,ix[f'v({n})']]*a[:,ix[f'i({p})']]) for p,n in m['ports'].items()}
    r['energy_by_port']=ledger;r['total_energy']={k:sum(q[k] for q in ledger.values()) for k in ['positive_J','returned_J','net_J']}
    r['energy_per_attempted_payload_bit_pJ']={k.replace('_J',''):v*1e12/4096 for k,v in r['total_energy'].items()} if m['kind']=='full' else None
    r['dynamic_screen_pass']=r['terminal_screen_pass'] and r['max_body_forward_V']<=.3 and r['current_min_mA']>=2 and r['current_max_mA']<=7.5
    selected=np.unique(np.r_[np.linspace(0,len(t)-1,min(5000,len(t)),dtype=int),np.flatnonzero((t/m['UI_ps']/1e-12>576)&(t/m['UI_ps']/1e-12<608))])
    np.savez_compressed(folder/'diagnostic.npz',time_s=t[selected],current_mA=a[selected,1]*1e3,**{n:a[selected,ix[n]] for n in nodes})
   if not recovery:r['waveform']=legacy.compress(raw)
  else:
   r['failure_classification']='solver_incomplete_or_error'
   legacy=engine.module(engine.LEGACY,'pvt_failure_compress');r['waveform']=legacy.compress(raw)
 if recovery:
  path=folder/'waveform.dat.gz'
  with gzip.open(path,'rb') as f:raw_hash=hashlib.file_digest(f,'sha256').hexdigest()
  r['waveform']=dict(path=str(path.relative_to(ROOT)),sha256=sha(path),raw_sha256=raw_hash,bytes=path.stat().st_size,roundtrip_verified=True)
 emit(p,r)
 print(m['pvt_config']['variant'],m['pvt_config']['corner'],folder.name,'OK',r['simulation_ok'],'I',r.get('current_mA',[r.get('current_min_mA'),r.get('current_max_mA')]),'body',r.get('max_body_forward_V'),'DC',r.get('DC_screen_pass'),'dynamic',r.get('dynamic_screen_pass'),flush=True)
 return r
def run(variant,corner,rate=8.8,steps=40,kind='short',level=None,holdout=False):
 folder,m=prepare(variant,corner,rate,steps,kind,level,holdout);r=solve(folder,m)
 if kind=='full' and r['simulation_ok'] and not(folder/'analysis.json').exists():
  rx=engine.module(analysis.RX_PATH,'pvt_rx');opto=engine.module(analysis.OPTO_PATH,'pvt_opto')
  met,traces=analysis.analyze(folder,rx,opto,False,128)
  dcs=[run(variant,corner,8.8,40,'dc',l) for l in [0,1]]
  q=met['pathways']['actual_graph_5GHzRX'];o=met['observed']
  met.update(pvt_config=m['pvt_config'],DC_screen_pass=all(q.get('DC_screen_pass',False) for q in dcs),result_sha256=sha(folder/'result.json'),manifest_sha256=sha(folder/'manifest.json'))
  met['combined_screen_pass']=met['DC_screen_pass'] and q['screen_pass'] and o['terminal_screen_pass'] and o['max_body_forward_V']<=.3 and o['within_calibrated_electrical_and_optical_current_range']
  emit(folder/'analysis.json',met);emit(folder/'excerpt.json',{k:v.tolist() for k,v in traces.items()})
  print('RX',corner,rate,'combined',met['combined_screen_pass'],'errors',q['errors'],'amp',q['worst_signed_margin_uAeq'],'UI',q['one_sided_margin_UI'],'E+',met['source_energy_pJ_per_attempted_net_bit']['positive'],flush=True)
 return r
def summarize():
 rows=[]
 for p in sorted(BUILD.glob('*/*/*/result.json')):
  m=read(p.parent/'manifest.json');r=read(p);a=p.parent/'analysis.json'
  row=dict(case=str(p.parent.relative_to(ROOT)),config=m['pvt_config'],manifest_sha256=sha(p.parent/'manifest.json'),result_sha256=sha(p),result={k:v for k,v in r.items() if k!='stress'})
  if a.exists():row['analysis']=read(a);row['analysis_sha256']=sha(a)
  rows.append(row)
 emit(EV/'summary.json',dict(schema='vcsel-pvt-summary-v1',status='in_progress',rows=rows,protocol_sha256=sha(EV/'protocol.json')))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--variant',default='frozen',choices=VARIANTS);p.add_argument('--corners',nargs='+',default=list(GRID),choices=GRID);p.add_argument('--kind',choices=['dc','short','full'],default='dc');p.add_argument('--rates',nargs='+',type=float,default=[8.8]);p.add_argument('--steps',type=int,default=40);p.add_argument('--holdout',action='store_true');args=p.parse_args()
 for c in args.corners:
  if args.kind=='dc':
   for l in [0,1]:run(args.variant,c,8.8,args.steps,'dc',l)
  else:
   for rate in args.rates:run(args.variant,c,rate,args.steps,args.kind,holdout=args.holdout)
  summarize()
