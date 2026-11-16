#!/usr/bin/env python3
"""A protected_v3r PVT: immutable copied inputs, actual transistor corner decks.

All results are simulation diagnostics with frozen, temperature-independent LED
I-V and optical/RX models. No inherited layout/PEX or production qualification.
"""
from pathlib import Path
import argparse,copy,gzip,hashlib,importlib.util,json,re,shutil,subprocess,sys,time
import numpy as np
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
BUILD=ROOT/'build/driver-pvt-20261117/a'
EV=ROOT/'evidence/driver-pvt-20261117/a'
FROZEN=ROOT/'build/driver-interface-20261115/MicroLED/A-protected_v3r'
SOURCE=Path(__file__).read_bytes()
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def emit(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def module(p,name):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
old=module(ROOT/'scripts/driver_interface_20261115/micro/run.py','a_pvt_analysis')
GRID=[('TT', 'typical',27,1.),('TTcold','typical',-40,1.),('TThot','typical',85,1.),('TTlow','typical',27,.95),('TThigh','typical',27,1.05),('SShotlow','ss',85,.95),('FFcoldhigh','ff',-40,1.05),('SFhotlow','sf',85,.95),('FScoldhigh','fs',-40,1.05)]
RH=185509.10418855824;RL=93447.8341496855
def init(variant='baseline'):
 work=BUILD/variant;work.mkdir(parents=True,exist_ok=True)
 if not (work/'inputs').exists():shutil.copytree(FROZEN/'inputs',work/'inputs')
 route=(FROZEN/'inputs/route_a.spice').read_text()
 if variant.startswith('track'):
  route=route.replace('VSS DISABLE params:', 'VSS DISABLE LEDREF params:')
  route=route.replace('RH_TOP VREF HSET 100k\nRH_BOTTOM HSET VSS {RH}\nRL_TOP VREF LSET 100k\nRL_BOTTOM LSET VSS {RL}',
   '* Physical passive difference sensing. Conductance ratios sum to 1uS.\n'
   '* A fixed calibrated pair of resistors implements b and 0.75-b.\n'
   'RH_TOP LEDREF HSET 3meg\nRH_BOTTOM HSET VSS 1meg\n'
   'RL_TOP LEDREF LSET 3meg\nRL_BOTTOM LSET VSS 1meg\n'
   'RH_SENSE VH HSENSE 4meg\nRH_REF VREF HSENSE {RH}\nRH_GND HSENSE VSS {1/(0.75u-1/RH)}\n'
   'RL_SENSE VL LSENSE 4meg\nRL_REF VREF LSENSE {RL}\nRL_GND LSENSE VSS {1/(0.75u-1/RL)}')
  route=route.replace('XHP1 HN1 VH HTAIL','XHP1 HN1 HSENSE HTAIL').replace('XLP1 LN1 VL LTAIL','XLP1 LN1 LSENSE LTAIL')
 if variant.startswith('tracklong'):
  # 2.5x L and W keeps W/L; longer devices reduce channel-length modulation.
  route=re.sub(r'w=20u l=4u ad=8.8p as=8.8p pd=40.88u ps=40.88u', 'w=50u l=10u ad=22p as=22p pd=100.88u ps=100.88u',route)
  route=re.sub(r'w=10u l=4u ad=4.4p as=4.4p pd=20.88u ps=20.88u', 'w=25u l=10u ad=11p as=11p pd=50.88u ps=50.88u',route)
 if variant.startswith('trackwide4'):
  for name,width in [('XNOUT',40),('XPOUT',62.88)]:
   route=re.sub(r'(?m)^('+name+r' .+? (?:nfet|pfet)_03v3) .+$',lambda z:z[1]+f' w={width:g}u l=0.28u ad={width*.44:g}p as={width*.44:g}p pd={2*(width+.44):g}u ps={2*(width+.44):g}u',route)
 if variant.startswith('trackwide4gm5'):
  for name in ['XHP1','XHP2','XLP1','XLP2']:
   route=re.sub(r'(?m)^('+name+r' .+? pfet_06v0) .+$',lambda z:z[1]+' w=100u l=4u ad=44p as=44p pd=200.88u ps=200.88u',route)
 if variant.startswith('trackwide4gm5a37'):
  route=route.replace('HSET 3meg','HSET 1.702702702702703meg').replace('LSET 3meg','LSET 1.702702702702703meg').replace('HSENSE 4meg','HSENSE 2.702702702702703meg').replace('LSENSE 4meg','LSENSE 2.702702702702703meg').replace('0.75u-1/','0.63u-1/')
 if variant.startswith('trackwide4gm5pre2') or variant.startswith('trackwide4gm5buf2'):
  for name,width in [('XN2',20),('XP2',31.44)]:
   route=re.sub(r'(?m)^('+name+r' .+? (?:nfet|pfet)_03v3) .+$',lambda z:z[1]+f' w={width:g}u l=0.28u ad={width*.44:g}p as={width*.44:g}p pd={2*(width+.44):g}u ps={2*(width+.44):g}u',route)
 if variant.startswith('trackwide4gm5buf2'):
  for name,width in [('XN1',5),('XP1',7.86)]:
   route=re.sub(r'(?m)^('+name+r' .+? (?:nfet|pfet)_03v3) .+$',lambda z:z[1]+f' w={width:g}u l=0.28u ad={width*.44:g}p as={width*.44:g}p pd={2*(width+.44):g}u ps={2*(width+.44):g}u',route)
 dest=work/'inputs/route_a.spice'
 if not any(work.glob('*/manifest.json')):dest.write_text(route)
 else:assert dest.read_text()==route
 return work
def prepare(point,variant='baseline',level=None,mode='fault',steps=40,rh=RH,rl=RL,supply_override=None,frames=None):
 label,corner,temp,scale=point;work=init(variant)
 source_name=f'DC-L{level}' if level is not None else f'{mode}-f{2 if mode=="fault" else 4}-net1.6-s{steps}'
 source=FROZEN/source_name
 if not source.exists() and level is None:source=FROZEN/f'{mode}-f{2 if mode=="fault" else 4}-net1.6-s40'
 name=label+'-'+(f'DC-L{level}' if level is not None else f'{mode}-s{steps}')
 if frames is not None:
  assert level is None and mode=='continuous' and frames in [1,2,4]
  name=label+f'-continuous-f{frames}-s{steps}'
 folder=work/name
 if (folder/'manifest.json').exists():
  m=read(folder/'manifest.json');assert m['pvt']==dict(label=label,corner=corner,temp_C=temp,supply_scale=scale)
  assert m['trim_ohm']==dict(RH=rh,RL=rl);assert sha(folder/'testbench.spice')==m['deck_sha256'];return folder,m
 folder.mkdir(exist_ok=True);m=read(source/'manifest.json');text=(source/'testbench.spice').read_text()
 text=re.sub(r'(?m)^(\.lib "../inputs/pdk/sm141064.ngspice") typical$',rf'\1 {corner}',text)
 assert re.search(r'^\.LIB '+corner+r'$',(work/'inputs/pdk/sm141064.ngspice').read_text(),re.M|re.I)
 text=re.sub(r'(?m)^\.temp .+$',f'.temp {temp}',text)
 rails={'VIN':5*scale,'VDD':3.3*scale,'VLED':5*scale};rails.update(supply_override or {})
 for name_,value in rails.items():text,n=re.subn(r'(?m)^'+name_+r' (\w+) 0 [^\n]+$',lambda z:f'{name_} {z[1]} 0 {value:.16g}',text);assert n==1
 for n in ['VD0','VD1','VDISABLE']:
  pattern=r'(?m)^'+n+r' (\w+) 0 ([^\n]+)$'
  def change(z):
   val=z[2]
   if val.startswith('PWL('):
    items=val[4:-1].split();assert len(items)%2==0
    val='PWL('+' '.join(v if i%2==0 else f'{float(v)*scale:.16g}' for i,v in enumerate(items))+')'
   else:val=f'{float(val)*scale:.16g}'
   return f'{n} {z[1]} 0 {val}'
  text,nc=re.subn(pattern,change,text);assert nc==1
 text,n=re.subn(r'(?m)^(XDRV .+ fair_a) RH=[^ ]+ RL=[^\n]+$',rf'\1 RH={rh:.16g} RL={rl:.16g}',text);assert n==1
 if variant.startswith('track'):
  text=text.replace('0 disable fair_a','0 disable led_feed fair_a')
  for d in m['devices']:
   if d['instance']=='xdrv.xhp1':d['nodes'][1]='xdrv.hsense'
   if d['instance']=='xdrv.xlp1':d['nodes'][1]='xdrv.lsense'
  for node in ['xdrv.hsense','xdrv.lsense']:m['vectors'][node]=len(m['vectors'])+1
  text=re.sub(r'(?m)^(wrdata waveform.dat .+)$',r'\1 v(xdrv.hsense) v(xdrv.lsense)',text)
  if level is None:
   start=text.index('let fs0x0=');end=text.index('wrdata waveform.dat',start)
   text=text[:start]+old.stress_commands(m['devices'])+'\n'+text[end:]
 if level is None:
  if frames is not None:m.update(frames=frames,end_s=m['frame_duration_s']*frames);m['case']['frames']=frames
  step=(32/37)/(1.6e9)/steps
  text=re.sub(r'(?m)^tran .+$',f'tran {step:.16g} {m["end_s"]:.16g} 0 {step:.16g}',text)
 m['case'].update(name=folder.name,corner=corner,temp_C=temp,vdd_V=rails['VDD'],vin_V=rails['VIN'],steps_per_symbol=steps)
 m.update(pvt=dict(label=label,corner=corner,temp_C=temp,supply_scale=scale),variant=variant,trim_ohm=dict(RH=rh,RL=rl),rails_V=rails,source_case=str(source.relative_to(ROOT)),source_case_manifest_sha256=sha(source/'manifest.json'),source_case_deck_sha256=sha(source/'testbench.spice'),load_temperature_scope='MOS and PDK resistors use .temp; measured LED I-V table, explicit 200fF capacitance, 200ps optical proxy and 1GHz RX remain fixed. No LED thermal characterization.',scope='New PVT schematic simulation. VREF fixed2.5V; VIN/VDD/VLED scaled; DATA/DISABLE logic high tracks VDD. Resistor process res_typical, external ideal resistors have no tolerance or TC.',execution_sha256=hashlib.sha256(SOURCE).hexdigest())
 (folder/'testbench.spice').write_text(text);(folder/'execution-source.py').write_bytes(SOURCE);shutil.copy2(source/'stimulus.json',folder/'stimulus.json')
 helpers={}
 for p in [Path(old.__file__),Path(old.legacy.__file__),Path(old.rx.__file__),Path(old.dyn.__file__),ROOT/'scripts/blue_emitter_speed_20261110/analyze.py']:
  dest=folder/'execution-sources'/f'{len(helpers)}-{p.name}';dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest);helpers[str(p.relative_to(ROOT))]=dict(path=str(dest.relative_to(folder)),sha256=sha(dest))
 m['execution_helpers']=helpers;m['deck_sha256']=sha(folder/'testbench.spice');m['inputs']={str(p.relative_to(work/'inputs')):sha(p) for p in (work/'inputs').rglob('*') if p.is_file()};m['stimulus_sha256']=sha(folder/'stimulus.json');emit(folder/'manifest.json',m)
 return folder,m
def solve(point,variant='baseline',**kw):
 folder,m=prepare(point,variant,**kw)
 if (folder/'result.json').exists():
  r=read(folder/'result.json');assert r['manifest_sha256']==sha(folder/'manifest.json');return r
 print('START',variant,folder.name,flush=True);start=time.monotonic()
 with (folder/'ngspice.log').open('w') as f:
  try:code=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=f,stderr=subprocess.STDOUT,timeout=1800).returncode
  except subprocess.TimeoutExpired:code=None
 raw=folder/'waveform.dat';log=(folder/'ngspice.log').read_text();ok=code==0 and raw.exists() and not any(s in log for s in ['simulation(s) aborted','Timestep too small'])
 r=dict(simulation_ok=ok,exit_code=code,case=m['case'],variant=variant,pvt=m['pvt'],trim_ohm=m['trim_ohm'],deck_sha256=sha(folder/'testbench.spice'),manifest_sha256=sha(folder/'manifest.json'))
 if ok:
  try:
   a=np.loadtxt(raw,skiprows=1,ndmin=2);assert np.isfinite(a).all();assert a.shape[1]==len(m['vectors'])+1
   if m['case'].get('level') is None:assert np.all(np.diff(a[:,0])>0) and abs(a[-1,0]-m['end_s'])<1e-14
   r.update(old.summarize_case(folder,m,a));r['simulation_complete']=True
  except Exception as e:r['analysis_error']=repr(e)
 if raw.exists():
  r['raw_sha256']=sha(raw);gz=folder/'waveform.dat.gz'
  with raw.open('rb') as src,gzip.open(gz,'wb',compresslevel=5) as dst:shutil.copyfileobj(src,dst)
  with gzip.open(gz,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['raw_sha256']
  r.update(gzip_sha256=sha(gz),gzip_bytes=gz.stat().st_size);raw.unlink()
 r.update(log_sha256=sha(folder/'ngspice.log'),elapsed_s=time.monotonic()-start,folder=str(folder.relative_to(ROOT)));emit(folder/'result.json',r)
 print('DONE',folder.name,r.get('current_uA'),r.get('DC_error_percent'),r.get('analysis_error'),r.get('terminal_pass'),r.get('body_pass'),flush=True);return r
def collect():
 rows=[read(p) for p in BUILD.glob('*/*/result.json')];emit(BUILD/'complete-results-summary.json',dict(grid=GRID,rows=rows,scope='All completed cases, including failed DC/stress/receiver cases.'))
 compact=[{k:r.get(k) for k in ['folder','variant','pvt','case','simulation_ok','analysis_error','current_uA','DC_error_percent','DC_pass','terminal_pass','body_pass','raw_sha256','gzip_sha256','deck_sha256','manifest_sha256']} for r in rows]
 emit(EV/'summary.json',dict(grid=GRID,rows=compact,complete_results_path=str((BUILD/'complete-results-summary.json').relative_to(ROOT)),scope='Compact case ledger. See matrix.json for effective append-only reanalysis and frame metrics; full MOS arrays kept under build.'))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['dc-grid','wave','collect']);p.add_argument('--point',default='TT');p.add_argument('--variant',default='baseline');p.add_argument('--mode',default='fault',choices=['fault','continuous']);p.add_argument('--frames',type=int);p.add_argument('--steps',type=int,default=40);p.add_argument('--rh',type=float,default=RH);p.add_argument('--rl',type=float,default=RL);args=p.parse_args()
 if args.action=='dc-grid':
  for g in GRID:
   for level in [0,1]:solve(g,args.variant,level=level,rh=args.rh,rl=args.rl)
 elif args.action=='wave':solve(next(g for g in GRID if g[0]==args.point),args.variant,mode=args.mode,steps=args.steps,rh=args.rh,rl=args.rl,frames=args.frames)
 collect()
