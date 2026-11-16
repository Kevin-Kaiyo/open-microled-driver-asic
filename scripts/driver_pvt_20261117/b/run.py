#!/usr/bin/env python3
"""B-v6r PVT and protection experiments. Immutable inputs and per-case execution snapshots."""
from pathlib import Path
import argparse,copy,gzip,hashlib,importlib.util,json,re,shutil,subprocess,sys,time
import numpy as np
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3];BUILD=ROOT/'build/driver-pvt-20261117/b';EV=ROOT/'evidence/driver-pvt-20261117/b';OLD=ROOT/'build/driver-interface-20261115/MicroLED/B-protected_v6r'
EXECUTION_SOURCE=Path(__file__).read_bytes()
SP=ROOT/'scripts/driver_interface_20261115/micro/run.py';spec=importlib.util.spec_from_file_location('prior_micro',SP);prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
GRID={'tt':('typical',27,1.),'tt_cold':('typical',-40,1.),'tt_hot':('typical',85,1.),'tt_low':('typical',27,.95),'tt_high':('typical',27,1.05),'ss_hot_low':('ss',85,.95),'ff_cold_high':('ff',-40,1.05),'sf_hot_low':('sf',85,.95),'fs_cold_high':('fs',-40,1.05)}
# Explicit internal model quantities, not extra ideal-current branches.
INTERNAL={'clamp_id':'@m.xclamp.m0[id]','clamp_vth':'@m.xclamp.m0[vth]','clamp_vdsat':'@m.xclamp.m0[vdsat]','iso0_id':'@m.xiso0.m0[id]','fastoff_id':'@m.xfastoff.m0[id]','base_id':'@m.xdrv.xbase.m0[id]','base_vdsat':'@m.xdrv.xbase.m0[vdsat]','tail_id':'@m.xdrv.xtail.m0[id]','tail_vdsat':'@m.xdrv.xtail.m0[vdsat]'}
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def emit(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def read(p):return json.loads(p.read_text())
def pwl_window(line,start,end,scale=1.):
 a=np.array([float(x) for x in re.search(r'PWL\((.*)\)',line).group(1).split()]).reshape(-1,2);mask=(a[:,0]>start)&(a[:,0]<start+end);t=np.r_[0,a[mask,0]-start,end];v=np.r_[np.interp(start,a[:,0],a[:,1]),a[mask,1],np.interp(start+end,a[:,0],a[:,1])]*scale
 return 'PWL('+' '.join(f'{x:.16g} {y:.16g}' for x,y in zip(t,v))+')'
def prepare(variant,grid,mode,level=None,steps=40):
 corner,temp,scale=GRID[grid];kind='DC-L'+str(level) if mode=='dc' else mode+'-s'+str(steps);work=BUILD/variant;folder=work/(grid+'-'+kind)
 if (folder/'manifest.json').exists():
  m=read(folder/'manifest.json');assert sha(folder/'testbench.spice')==m['deck_sha256'];return folder,m
 work.mkdir(parents=True,exist_ok=True)
 if not (work/'inputs').exists():
  shutil.copytree(OLD/'inputs',work/'inputs')
  if variant in ['unit_tail','unit_long','unit_long_trim']:
   w,l=(2,1) if variant=='unit_tail' else (4,2)
   p=work/'inputs/route_b.spice';s=p.read_text();s=re.sub(r'(?m)^XTAIL .+$','\n'.join(prior.mos(n,'VX','BIAS','VSS','VSS','nfet_03v3',w,l) for n in ['XTAIL','XTAIL1','XTAIL2']),s)
   if variant in ['unit_long','unit_long_trim']:
    s=re.sub(r'(?m)^XREF .+$',prior.mos('XREF','BIAS','BIAS','VSS','VSS','nfet_03v3',w,l),s);s=re.sub(r'(?m)^XBASE .+$',prior.mos('XBASE','OUT','BIAS','VSS','VSS','nfet_03v3',w,l),s)
   p.write_text(s)
 source_name='DC-L'+str(level) if mode=='dc' else ('continuous-f4-net1.6-s40' if mode in ['continuous','normal1'] else 'fault-f2-net1.6-s40')
 source=OLD/source_name;text=(source/'testbench.spice').read_text();m=copy.deepcopy(read(source/'manifest.json'));m['case'].update(name=folder.name,variant=variant,pvt_key=grid,corner=corner,temp_C=temp,rail_scale=scale,vdd_V=3.3*scale,vin_V=3.3*scale,steps_per_symbol=steps)
 if mode!='dc':m['case']['mode']='fault' if mode=='full' else mode
 text=re.sub(r'(?m)^\.lib (.+) typical$',r'.lib \1 '+corner,text);text=re.sub(r'(?m)^\.temp .+$',f'.temp {temp}',text)
 for name,node,value in [('VIN','vin_src',3.3*scale),('VDD','vdd_src',3.3*scale),('VLED','led_src',5*scale)]:text=re.sub(r'(?m)^'+name+r' '+node+r' 0 .+$',f'{name} {node} 0 {value:.16g}',text)
 # VREF deliberately independent and fixed 2.5V; no rail-tracking current target.
 if mode=='dc':text=re.sub(r'(?m)^VD0 data0_src 0 .+$',f'VD0 data0_src 0 {3.3*scale*level:.16g}',text)
 else:
  line=re.search(r'(?m)^VD0 data0_src 0 .+$',text).group(0)
  if mode in ['assert','release']:
   start=.608e-6 if mode=='assert' else 1.248e-6;end=96e-9 if mode=='assert' else 160e-9
   text=text.replace(line,'VD0 data0_src 0 '+pwl_window(line,start,end,scale));cmd=f'PWL(0 0 32n 0 33n {3.3*scale:.16g} {end:.16g} {3.3*scale:.16g})' if mode=='assert' else f'PWL(0 {3.3*scale:.16g} 32n {3.3*scale:.16g} 33n 0 {end:.16g} 0)'
   text=re.sub(r'(?m)^VDISABLE disable_src 0 .+$','VDISABLE disable_src 0 '+cmd,text);m['diagnostic']={'edge_s':32e-9,'old_absolute_input_start_s':start,'end_s':end,'scope':'Short local DC-initialized diagnostic using exact old PRBS segment. Not original history, full receiver, continuous-energy or protocol qualification.'}
  else:
   end=10.24e-6 if mode=='continuous' else (2.56e-6 if mode=='normal1' else 5.12e-6);text=text.replace(line,'VD0 data0_src 0 '+pwl_window(line,0,end,scale))
   if mode=='normal1':m['frames']=1;m['case']['frames']=1
   if mode=='full':text=re.sub(r'(?m)^VDISABLE disable_src 0 .+$',f'VDISABLE disable_src 0 PWL(0 0 6.4e-7 0 6.41e-7 {3.3*scale:.16g} 1.28e-6 {3.3*scale:.16g} 1.281e-6 0 5.12e-6 0)',text)
  step=prior.ETA/1.6e9/steps;text=re.sub(r'(?m)^tran .+$',f'tran {step:.16g} {end:.16g} 0 {step:.16g}',text);m['end_s']=end
 if variant.startswith('clamp5v'):
  text=text.replace('XCLAMP led_a disable led_k 0','XCLAMP led_a iso_g led_k 0')
  for d in m['devices']:
   if d['instance']=='xclamp':d['nodes'][1]='iso_g'
 elif variant in ['unit_tail','unit_long','unit_long_trim']:
  d=next(d for d in m['devices'] if d['instance']=='xdrv.xtail')
  m['devices'] += [dict(d,instance='xdrv.xtail1'),dict(d,instance='xdrv.xtail2')]
 elif variant!='baseline':raise ValueError(variant)
 if variant=='unit_long_trim':
  m['parameters']['RSET']*=.9925
  text=re.sub(r'(?m)^(XDRV .+ RSET=)\S+',lambda q:q.group(1)+f'{m["parameters"]["RSET"]:.16g}',text)
 if variant.startswith('unit_'):m['unit_mirror']={'reference_and_base_W_um':2 if variant=='unit_tail' else 4,'reference_and_base_L_um':1 if variant=='unit_tail' else 2,'tail_parallel_count':3,'tail_same_geometry_as_reference':True,'legacy_WTAIL_parameter_unused':True,'scope':'DC structure probe only unless separately tested dynamically.'}
 if variant=='clamp5v_r1k':text=text.replace('XDATAIN d0 data_gate 0 ppolyf_u_1k_6p0 r_width=4u r_length=8u','XDATAIN d0 data_gate 0 ppolyf_u_1k_6p0 r_width=4u r_length=4u')
 if variant in ['clamp5v_delayed','clamp5v_delay200'] or variant.startswith('clamp5v_buffer'):
  text=text.replace('XCLAMP led_a iso_g led_k 0','XCLAMP led_a clamp_g led_k 0')
  reset_w=.5 if variant in ['clamp5v_buffer_soft','clamp5v_buffer_damped'] else 4
  text=text.replace('RGATE iso_g iso_p 100k','RGATE iso_g iso_p 100k\nRCLAMP iso_g clamp_g 100k\n'+prior.mos('XCLAMPRST','clamp_g','en','0','0','nfet_06v0',reset_w,.7))
  for d in m['devices']:
   if d['instance']=='xclamp':d['nodes'][1]='clamp_g'
  m['devices'].append(dict(instance='xclamprst',nodes=['clamp_g','en','0','0'],model='nfet_06v0'))
  if variant=='clamp5v_delay200' or variant.startswith('clamp5v_buffer'):text=text.replace('RCLAMP iso_g clamp_g 100k','RCLAMP iso_g clamp_g 200k')
 if variant.startswith('clamp5v_buffer'):
  defs=[('XIB1N','ib1','data_gate','0','0','nfet_03v3',2.5,.28),('XIB1P','ib1','data_gate','vdd','vdd','pfet_03v3',3.93,.28),('XIB2N','data_buffered','ib1','0','0','nfet_03v3',2.5,.28),('XIB2P','data_buffered','ib1','vdd','vdd','pfet_03v3',3.93,.28)]
  for name in ['XNAND_PDATA','XNAND_NDATA']:text=text.replace(name+' nand_o data_gate ',name+' nand_o data_buffered ')
  text=text.replace('RGATE iso_g iso_p 100k','\n'.join(prior.mos(*d) for d in defs)+'\nRGATE iso_g iso_p 100k')
  for d in m['devices']:
   if d['instance'] in ['xnand_pdata','xnand_ndata']:d['nodes'][1]='data_buffered'
  m['devices'] += [dict(instance=d[0].lower(),nodes=list(d[1:5]),model=d[5]) for d in defs]
  if variant=='clamp5v_buffer_damped':
   text=text.replace('XIB2N data_buffered ib1 ','XIB2N data_buffered ib2_gate ').replace('XIB2P data_buffered ib1 ','XIB2P data_buffered ib2_gate ')
   text=text.replace('RGATE iso_g iso_p 100k','XIBDAMP ib1 ib2_gate 0 ppolyf_u_1k_6p0 r_width=4u r_length=4u\nRGATE iso_g iso_p 100k')
   for d in m['devices']:
    if d['instance'] in ['xib2n','xib2p']:d['nodes'][1]='ib2_gate'
 new_nodes=[]
 for d in m['devices']:
  for n in d['nodes']:
   if n!='0' and n not in m['vectors']:
    m['vectors'][n]=len(m['vectors'])+1;new_nodes.append('v('+n+')')
 internal=dict(INTERNAL)
 if variant in ['unit_tail','unit_long','unit_long_trim']:internal.update(tail1_id='@m.xdrv.xtail1.m0[id]',tail2_id='@m.xdrv.xtail2.m0[id]')
 # Internal model quantities add no ideal voltage source or changed circuit connectivity.
 text=text.replace('.control','.save all '+' '.join(internal.values())+'\n.control')
 for key,value in internal.items():m['vectors'][key]=len(m['vectors'])+1
 text=re.sub(r'(?m)^wrdata waveform.dat (.+)$',lambda x:'wrdata waveform.dat '+x.group(1)+' '+' '.join(new_nodes+list(internal.values())),text)
 m['internal_model_quantities']=internal
 if mode!='dc':
  start=text.index('let fs0x0=');stop=text.index('wrdata waveform.dat',start);text=text[:start]+prior.stress_commands(m['devices'])+'\n'+text[stop:]
 text='B PVT research '+folder.name+'\n'+text.split('\n',1)[1]
 folder.mkdir();(folder/'testbench.spice').write_text(text);shutil.copy2(source/'stimulus.json',folder/'stimulus.json');(folder/'execution-source.py').write_bytes(EXECUTION_SOURCE)
 helpers=[SP,Path(prior.legacy.__file__),Path(prior.rx.__file__),Path(prior.dyn.__file__),ROOT/'scripts/blue_emitter_speed_20261110/analyze.py'];m['execution_helpers']={}
 for i,p in enumerate(helpers):
  q=folder/'execution-sources'/f'{i}-{p.name}';q.parent.mkdir(exist_ok=True);shutil.copy2(p,q);m['execution_helpers'][str(p.relative_to(ROOT))]={'path':str(q.relative_to(folder)),'sha256':sha(q)}
 m.update(source_case=str(source.relative_to(ROOT)),source_manifest_sha256=sha(source/'manifest.json'),source_deck_sha256=sha(source/'testbench.spice'),execution_sha256=sha(folder/'execution-source.py'),deck_sha256=sha(folder/'testbench.spice'),stimulus_sha256=sha(folder/'stimulus.json'),inputs={str(p.relative_to(work/'inputs')):sha(p) for p in (work/'inputs').rglob('*') if p.is_file()},pvt={'model_section':corner,'temperature_C':temp,'VIN_V':3.3*scale,'VDD_V':3.3*scale,'VLED_V':5*scale,'VREF_V':2.5,'DATA_and_DISABLE_high_V':3.3*scale,'resistor_corner':'res_typical','LED_temperature':'Static measured-IV PWL has no T coefficient; electrical IV/C and optical/RX held fixed. Only PDK devices get .temp; no LED/optical thermal qualification.'},scope='PVT at net1.6Gb/s; no measured optical/thermal or layout qualification.')
 emit(folder/'manifest.json',m);return folder,m

def diagnostic(a,m,folder):
 ix=m['vectors'];t=a[:,0];edge=m['diagnostic']['edge_s'];stress=prior.stress(a,m,folder);cur=a[:,1];v=lambda n:a[:,ix[n]];mask=t>=edge+20e-9;last=np.flatnonzero((t>=edge)&(abs(cur)>.1e-6))
 r={'case':m['case'],'MOS':len(stress),'stress':stress,'terminal_pass':all(x['terminal_pass'] for x in stress),'body_pass':all(x['body_pass'] for x in stress),'body_forward_V':max(x['body_forward_V'] for x in stress),'current_range_uA':[float(cur.min()*1e6),float(cur.max()*1e6)],'diagnostic_only':True}
 if m['case']['mode']=='assert':
  p=np.flatnonzero(mask)[0];g=v('clamp_g') if 'clamp_g' in ix else (v('iso_g') if m['case']['variant'].startswith('clamp5v') else v('disable'));first={n:float(v(n)[p]) for n in ['led_a','led_k','out','iso_p','iso_g','disable','clamp_id','clamp_vth','clamp_vdsat','base_id','base_vdsat','tail_id','tail_vdsat']};first.update(time_s=float(t[p]),current_uA=float(cur[p]*1e6),VAK_V=float(v('led_a')[p]-v('led_k')[p]),clamp_VGS_V=float(g[p]-v('led_k')[p]),clamp_VSB_V=float(v('led_k')[p]),clamp_gate_overdrive_V=float(g[p]-v('led_k')[p]-v('clamp_vth')[p]))
  r['shutdown']={'max_abs_current_uA':float(abs(cur[mask]).max()*1e6),'last_above_threshold_ns':float((t[last[-1]]-edge)*1e9) if len(last) else 0.,'off_current_screen_pass':bool(abs(cur[mask]).max()<=.1e-6),'first_post_guard':first}
 energy={n:prior.legacy.signed_integrals(t,-v(n+'_voltage')*v(n+'_current')) for n in m['sources']};r['diagnostic_source_energy_J']=energy
 np.savez_compressed(folder/'preview.npz',time_s=t,**{n:v(n) for n in ['iled_cond','ipkg','led_a','led_k','out','iso_g','iso_p','disable','data_safe','d0',*INTERNAL]+[n for n in ['clamp_g','ib1','data_gate','data_buffered','nand_o','nand_s'] if n in ix]})
 return r

def run(variant,grid,mode,level=None,steps=40):
 folder,m=prepare(variant,grid,mode,level,steps)
 if (folder/'result.json').exists():return read(folder/'result.json')
 print('START',folder.name,variant,flush=True);clock=time.monotonic()
 with (folder/'ngspice.log').open('w') as f:
  try:code=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,stdout=f,stderr=subprocess.STDOUT,timeout=3600).returncode
  except subprocess.TimeoutExpired:code=None
 raw=folder/'waveform.dat';log=(folder/'ngspice.log').read_text();aborted='Timestep too small' in log or 'simulation(s) aborted' in log;end=None
 if raw.exists():
  with raw.open('rb') as f:f.seek(max(0,raw.stat().st_size-16384));end=float(f.read().splitlines()[-1].split()[0])
 complete=raw.exists() and not aborted and (mode=='dc' or abs(end-m['end_s'])<1e-14)
 r={'case':m['case'],'simulation_ok':code==0 and complete,'simulation_complete':complete,'exit_code':code,'abort_reported':aborted,'native_end_s':end,'solve_s':time.monotonic()-clock,'deck_sha256':sha(folder/'testbench.spice'),'manifest_sha256':sha(folder/'manifest.json')}
 if r['simulation_ok']:
  try:
   a=np.loadtxt(raw,skiprows=1,ndmin=2);assert a.shape[1]==len(m['vectors'])+1 and np.isfinite(a).all();r.update(diagnostic(a,m,folder) if mode in ['assert','release'] else prior.summarize_case(folder,m,a))
   if mode=='dc':
    r['model_operating_quantities']={n:{'value':float(a[-1,m['vectors'][n]]),'unit':'A' if n.endswith('_id') else 'V'} for n in m['internal_model_quantities']}
    for n in m['internal_model_quantities']:r['nodes_V'].pop(n,None)
   elif mode not in ['assert','release']:
    p=folder/'preview.npz';z=dict(np.load(p));indices=np.searchsorted(a[:,0],z['time_s'])
    for n in ['clamp_g','data_buffered','ib1',*m['internal_model_quantities']]:
     if n in m['vectors']:z[n]=a[indices,m['vectors'][n]]
    np.savez_compressed(p,**z)
  except Exception as e:r['analysis_error']=repr(e)
 if raw.exists():
  r['raw_sha256']=sha(raw)
  with raw.open('rb') as src,gzip.open(folder/'waveform.dat.gz','wb',compresslevel=5) as dst:shutil.copyfileobj(src,dst)
  with gzip.open(folder/'waveform.dat.gz','rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['raw_sha256']
  r.update(gzip_sha256=sha(folder/'waveform.dat.gz'),gzip_bytes=(folder/'waveform.dat.gz').stat().st_size);raw.unlink()
 r.update(log_sha256=sha(folder/'ngspice.log'),elapsed_s=time.monotonic()-clock)
 if (folder/'preview.npz').exists():r['preview_sha256']=sha(folder/'preview.npz')
 emit(folder/'result.json',r)
 print('DONE',variant,folder.name,r['simulation_ok'],r.get('analysis_error'),r.get('current_uA'),r.get('body_forward_V'),r.get('shutdown',{}).get('max_abs_current_uA'),flush=True);return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('variant',choices=['baseline','clamp5v','clamp5v_r1k','clamp5v_delayed','clamp5v_delay200','clamp5v_buffer','clamp5v_buffer_soft','clamp5v_buffer_damped','unit_tail','unit_long','unit_long_trim']);p.add_argument('--grid',default='tt');p.add_argument('--mode',choices=['dc','assert','release','full','continuous','normal1'],default='assert');p.add_argument('--steps',type=int,default=40);a=p.parse_args()
 for grid in GRID if a.grid=='all' else a.grid.split(','):
  for lev in [0,1] if a.mode=='dc' else [None]:run(a.variant,grid,a.mode,lev,a.steps)
