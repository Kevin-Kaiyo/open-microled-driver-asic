#!/usr/bin/env python3
"""Bounded VCSEL reference/rail experiments; immutable per-case inputs and results."""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json,shutil,subprocess,time
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/vcsel-robustness-20261029'
CIR=ROOT/'analog/circuits/vcsel_robustness_20261029'
EV=ROOT/'evidence/vcsel-robustness-20261029'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def emit(p,x):
 Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def mod(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
OLD=mod(ROOT/'scripts/three_gbps_experiment/vcsel_driver_run.py','legacy_runner')
RX0=mod(ROOT/'scripts/fair_driver_v1/receiver_equal_latency_v2.py','stimulus_rx')
ENERGY=mod(ROOT/'scripts/fair_driver_v1/run.py','energy_helper')
def mos(name,d,g,s,b,p,w,l):
 n=int(np.ceil(w/100));wf=w/n
 return ''.join(f'X{name}_{k} {d} {g} {s} {b} {p}mos_3p3 w={wf}u l={l}u ad={wf*.44}p as={wf*.44}p pd={2*(wf+.44)}u ps={2*(wf+.44)}u\n' for k in range(n))
def ota(prefix,vp,vm,out,power,bias):
 # PMOS pair: vp>vm gives positive output. External bias common per rail.
 q=prefix
 return ''.join([mos(q+'T',q+'tail',bias,power,power,'p',10,2),mos(q+'P1',q+'n1',vp,q+'tail',power,'p',128,8),mos(q+'P2',out,vm,q+'tail',power,'p',128,8),mos(q+'N1',q+'n1',q+'n1','VSS','VSS','n',32,8),mos(q+'N2',out,q+'n1','VSS','VSS','n',32,8)])
def amp(prefix,vp,vm,out,power,bias,cap):
 q=prefix
 return ota(q,vp,vm,q+'n2',power,bias)+mos(q+'NS',out,q+'n2','VSS','VSS','n',20,1)+mos(q+'PL',out,bias,power,power,'p',20,2)+f'C{q}MILLER {q}n2 {out} {{{cap}}}\n'
def ldo(prefix,raw,out):
 q=prefix
 # reversed OTA sense for PMOS pass negative feedback
 rz='RZERO' if q=='L' else 'RZEROD'
 stages=amp(q,'VREGSET',q+'fb',q+'ctrl',raw,q+'pb','CLDO').replace(f'C{q}MILLER {q}n2 {q}ctrl {{CLDO}}',f'R{q}ZERO {q}n2 {q}zc {{{rz}}}\nC{q}MILLER {q}zc {q}ctrl {{CLDO}}')
 cout='10n' if q=='L' else '1n'
 return mos(q+'B',q+'pb',q+'pb',raw,raw,'p',10,2)+f'R{q}BIAS {q}pb VSS 100k\n'+stages+mos(q+'PASS',out,q+'ctrl',raw,raw,'p',1000,.28)+f'R{q}TOP {out} {q}fb 85k\nR{q}BOT {q}fb VSS 10k\nR{q}ESR {out} {q}cap .1\nC{q}OUT {q}cap VSS {cout}\nR{q}BLEED {out} VSS {{RBLEED}}\n'
def circuit(variant):
 if variant=='baseline':return (ROOT/'analog/circuits/vcsel_research_20261027/vcsel_bias_mod.spice').read_text()
 text='''* Independent dual source-sense current servo; finite-gain PMOS-input OTAs.
* VSET and VREGSET are externally supplied precision-voltage boundaries, NOT implemented bandgaps.
* RBASE/RTAIL, compensation, divider and output capacitors are explicit external ideal passive assumptions.
* All MOS use pinned GF180 silicon 3.3V BSIM; no layout/PEX qualification.
.subckt vcsel_servo D DB OUT VLASER VDD VREF VSET VREGSET VL VSS params: RBASE=50 RTAIL=37.5 CC=5p CLDO=30p WBASE=60u WTAIL=84u RDUMMY=500 ATTEN=200 RZERO=100000 RZEROD=100000 RBLEED=5000
'''
 if variant=='regulated':text+=ldo('L','VLASER','VL')+ldo('D','VDD','DR')
 else:text+='VVL VLASER VL 0\nVDR VDD DR 0\n'
 text+=mos('AB','ABIAS','ABIAS','VREF','VREF','p',10,2)+'RABIAS ABIAS VSS 100k\n'
 text+=amp('B','SBASE','VSET','BCTRL','VREF','ABIAS','CC')+amp('T','STAIL','VSET','TCTRL','VREF','ABIAS','CC')
 text+='VIBASE OUT BS 0\nVITAIL VX TS 0\n'
 text+='XBASE0 BS BCTRL SBASE VSS nmos_3p3 w={WBASE} l=1u ad={WBASE*.44u} as={WBASE*.44u} pd={2*(WBASE+.44u)} ps={2*(WBASE+.44u)}\nXTAIL0 TS TCTRL STAIL VSS nmos_3p3 w={WTAIL} l=.28u ad={WTAIL*.44u} as={WTAIL*.44u} pd={2*(WTAIL+.44u)} ps={2*(WTAIL+.44u)}\nRBASE SBASE VSS {RBASE}\nRTAIL STAIL VSS {RTAIL}\n'
 text+='XBASE1 BS BCTRL SBASE VSS nmos_3p3 w={WBASE} l=1u ad={WBASE*.44u} as={WBASE*.44u} pd={2*(WBASE+.44u)} ps={2*(WBASE+.44u)}\nXTAIL1 TS TCTRL STAIL VSS nmos_3p3 w={WTAIL} l=.28u ad={WTAIL*.44u} as={WTAIL*.44u} pd={2*(WTAIL+.44u)} ps={2*(WTAIL+.44u)}\n'
 text+=mos('STEER','OUT','GP','VX','VSS','n',40,.28)+mos('DUMP','DUMMY','GN','VX','VSS','n',40,.28)+'RDUMMY1 VL DUMMY {RDUMMY}\n'
 if variant=='regulated':text+='RAD D DI {ATTEN}\nRADI DI VSS 2500\nRADB DB DBI {ATTEN}\nRADBI DBI VSS 2500\n';d,db='DI','DBI'
 else:d,db='D','DB'
 for label,di,nd,gate in [('P',d,'NP','GP'),('N',db,'NN','GN')]:
  text+=mos('B'+label+'1N',nd,di,'VSS','VSS','n',4,.28)+mos('B'+label+'1P',nd,di,'DR','DR','p',8,.28)+mos('B'+label+'2N',gate,nd,'VSS','VSS','n',12,.28)+mos('B'+label+'2P',gate,nd,'DR','DR','p',24,.28)
 return text+'.ends vcsel_servo\n'
def cfg(**kw):
 d=dict(variant='baseline',mode='dc',level=0,corner='typical',temp=25,voltage=3.3,seed=0x5ACE,rate=3.2,steps=40,nbits=4736,cj=150e-15,vset=.15,vregset=.3,rscale=1.,cc=5e-12,cldo=100e-12,wbase=60e-6,wtail=84e-6,atten=200.,ramp_ns=100.,duration_ns=2000.,disturb=0.,rref=6900.)
 d.update(revision='r10',rzero=100000.,rzerod=100000.,cldo=30e-12,rbleed=5000.,vregset=3.1/9.5)
 d.update(frame_start_ns=60000.,frame_steps=40)
 d.update(kw);return d
def run(name,**kw):
 c=cfg(**kw);work=BUILD/name
 if work.exists():
  old=json.loads((work/'manifest.json').read_text());assert old['config']==c, 'Immutable case config mismatch'
  assert (work/'inputs/driver.spice').read_text()==circuit(c['variant']), 'Immutable case circuit revision mismatch'
  return json.loads((work/'result.json').read_text())
 assert shutil.disk_usage(ROOT).free>1.5*1024**3
 work.mkdir(parents=True);inp=work/'inputs';inp.mkdir()
 shared=BUILD/'shared';shared.mkdir(exist_ok=True)
 for n,src in [('design.ngspice',ROOT/'.cache/pdk/gf180mcu/design.ngspice'),('sm141064.ngspice',ROOT/'.cache/pdk/gf180mcu/sm141064.ngspice'),('vcsel.spice',ROOT/'analog/models/vcsel_research_20261027/vcsel_research.spice')]:
  if not (shared/n).exists():shutil.copy2(src,shared/n)
  assert sha(shared/n)==sha(src)
 text=circuit(c['variant']);(inp/'driver.spice').write_text(text);shutil.copy2(Path(__file__),inp/'runner.py')
 pins=dict(D='d',DB='db',OUT='out',VLASER='vlaser',VDD='vdd',VREF='vref',VSS='0',VSET='vset',VREGSET='vregset',VL='vl')
 devs=[]
 for line in text.splitlines():
  w=line.split()
  if len(w)>=6 and w[5] in ['nmos_3p3','pmos_3p3']:devs.append(dict(instance=w[0],model=w[5],nodes=[pins.get(n,'xdrv.'+n.lower()) for n in w[1:5]],parameters=w[6:]))
 nodes=sorted({n for d in devs for n in d['nodes']}-{'0'})
 ports=dict(VLASER='laser_src',VDD='vdd_src',VREF='ref_src',VD='d_src',VDB='db_src')
 if c['variant']!='baseline':ports['VSET']='set_src'
 if c['variant']=='regulated':ports['VREGSET']='regset_src'
 extra=['laser_src','vdd_src','ref_src','d_src','db_src','vc_a','vc_k','vlaser','vdd','vref']+list(ports.values())
 extra+=['xdrv.lcap','xdrv.dcap','xdrv.lzc','xdrv.dzc','laser_c','vdd_c']
 expr=['v(jmon)']+['v('+n+')' for n in sorted(set(nodes+extra))]+['i('+p+')' for p in ports]+['i(v.xdrv.vibase)','i(v.xdrv.vitail)']
 stim=OLD.seeded_stimulus(c['seed'],RX0);emit(work/'stimulus.json',stim)
 ui=32/37/(c['rate']*1e9);end=c['frame_start_ns']*1e-9+c['nbits']*ui
 v=c['voltage'];raw=str(v);vset=str(c['vset']);vregset=str(c['vregset'])
 if c['mode']=='startup_frame':
  ramp=c['ramp_ns']*1e-9;raw=f'PWL(0 0 {ramp} {v})';vset=f'PWL(0 0 {ramp} {c["vset"]})';vregset=f'PWL(0 0 {ramp} {c["vregset"]})'
  dat=f'PWL(0 0 {ramp} {v*c["level"]})';datb=f'PWL(0 0 {ramp} {v*(1-c["level"])})'
  start=c['frame_start_ns']*1e-9
  def delayed(bits):
   assert bits[0]==c['level'], 'Startup held level must match first frame bit'
   entries=[(0,0),(ramp,v*c['level']),(start,v*bits[0])]
   for k in range(1,len(bits)):
    if bits[k]!=bits[k-1]:entries += [(start+k*ui,bits[k-1]*v),(start+k*ui+20e-12,bits[k]*v)]
   entries.append((end,bits[-1]*v))
   return 'PWL(\n+'+'\n+'.join(' '.join(f'{t:.15g} {a:.15g}' for t,a in entries[j:j+4]) for j in range(0,len(entries),4))+')'
  dat=delayed(stim['bits']);saved_level=c['level'];c['level']=1-saved_level;datb=delayed([1-b for b in stim['bits']]);c['level']=saved_level
 elif c['mode']=='dc':dat=str(c['level']*v);datb=str((1-c['level'])*v)
 else:
  dat=OLD.pwl(stim['bits'][:c['nbits']],ui,v);datb=OLD.pwl([1-b for b in stim['bits'][:c['nbits']]],ui,v)
 if c['disturb']:
  t1=end*.42;t2=end*.46;t3=end*.70;t4=end*.74
  raw=f'PWL(0 {v} {t1} {v} {t2} {v*(1+c["disturb"])} {t3} {v*(1+c["disturb"])} {t4} {v} {end} {v})'
 manifest=dict(case=name,config=c,devices=devs,expressions=expr,ports=ports,end_s=end,source_hashes={str(p.relative_to(ROOT)):sha(p) for p in [inp/'driver.spice',inp/'runner.py',shared/'design.ngspice',shared/'sm141064.ngspice',shared/'vcsel.spice']},stimulus_sha256=sha(work/'stimulus.json'),target='3.2Gnet,3.7Gbaud,4736frame/4096payload; unchanged optical/RX/threshold contract',scope='Schematic-level finite MOS servo/LDO; ideal external precision-voltage sources and passives remain explicit boundaries. VCSEL fixed25C graph proxy, not physical PVT. Source pin power excludes external reference/regulator-chip internal power.')
 emit(work/'manifest.json',manifest)
 if c['variant']=='baseline':instance=f'XDRV d db out vlaser vdd vref 0 vcsel_bias_mod RREF={c["rref"]} WBASE=60u WTAIL=84u';vcrail='vlaser';extras=''
 else:
  instance=f'XDRV d db out vlaser vdd vref vset vregset vl 0 vcsel_servo RBASE={50*c["rscale"]} RTAIL={37.5*c["rscale"]} CC={c["cc"]} CLDO={c["cldo"]} WBASE={c["wbase"]} WTAIL={c["wtail"]} ATTEN={c["atten"]} RZERO={c["rzero"]} RZEROD={c["rzerod"]} RBLEED={c["rbleed"]}'
  vcrail='vl';extras=f'VSET set_src 0 {vset}\nRSETSRC set_src vset 100\n'
  if c['variant']=='regulated':extras+=f'VREGSET regset_src 0 {vregset}\nRREGSETSRC regset_src vregset 100\n'
  else:extras+='VREGSET_UNUSED vregset 0 0\n'
 assert c['mode']=='startup_frame'
 action=f'tran {ui/c["steps"]} {end} 0 {ui/c["steps"]}'
 grid=[(0,0)]+[(c['frame_start_ns']*1e-9+k*ui/c['frame_steps'],(k%2)*1e-12) for k in range(c['nbits']*c['frame_steps']+1)]
 grid_source='* Disconnected numerical breakpoint source; no hardware or energy. Forces fine steps only in frame.\nVNUMGRID numerical_grid 0 PWL(\n+'+'\n+'.join(' '.join(f'{t:.15g} {a:.15g}' for t,a in grid[j:j+4]) for j in range(0,len(grid),4))+')\n'
 deck=f'''VCSEL reference and rail experiment {name}
.include "{shared/'design.ngspice'}"
.param sw_stat_global=0 sw_stat_mismatch=0
.lib "{shared/'sm141064.ngspice'}" {c['corner']}
.include "{inp/'driver.spice'}"
.include "{shared/'vcsel.spice'}"
.temp {c['temp']}
VLASER laser_src 0 {raw}
RLASER laser_src laser_r .25
LLASER laser_r vlaser .2n
RCLASER vlaser laser_c .1
CLASER laser_c 0 1n
VDD vdd_src 0 {raw}
RVDD vdd_src vdd_r .25
LVDD vdd_r vdd .2n
RCVDD vdd vdd_c .1
CVDD vdd_c 0 1n
VREF ref_src 0 {raw}
RREFSRC ref_src vref .2
VD d_src 0 {dat}
VDB db_src 0 {datb}
RD d_src d 50
RDB db_src db 50
{extras}{grid_source}{instance}
XVCSEL {vcrail} vc_k jmon vcsel_research CJ={c['cj']}
RPKG vc_k vc_a .5
LPKG vc_a out .2n
.options reltol=1e-5 abstol=1e-12 vntol=1e-7 chgtol=1e-16
.control
set numdgt=12
set wr_singlescale
set wr_vecnames
save {' '.join(expr)}
{action}
wrdata waveform.dat {' '.join(expr)}
quit
.endc
.end
'''
 (work/'testbench.spice').write_text(deck);start=time.time()
 try:
  with (work/'ngspice.log').open('w') as f:code=subprocess.run(['ngspice','-b','testbench.spice'],cwd=work,stdout=f,stderr=subprocess.STDOUT,timeout=360).returncode
 except subprocess.TimeoutExpired:code='timeout'
 result=dict(case=name,config=c,exit_code=code,elapsed_s=time.time()-start,manifest_sha256=sha(work/'manifest.json'),deck_sha256=sha(work/'testbench.spice'),log_sha256=sha(work/'ngspice.log'),simulation_ok=False)
 if code==0 and (work/'waveform.dat').exists():
  a=np.atleast_2d(np.loadtxt(work/'waveform.dat',skiprows=1));t=a[:,0];ix={e:i+1 for i,e in enumerate(expr)}
  result.update(simulation_ok=bool(c['mode']=='dc' or (t[-1]>=end-1e-15 and np.all(np.diff(t)>0))),sample_count=len(t),current_range_mA=[float(a[:,1].min()*1e3),float(a[:,1].max()*1e3)],stress=OLD.stress(a,ix,devs))
  result['device_screen_passed']=all(x['screen_pass'] for x in result['stress']);result['max_terminal_V']=max(max(x['max_abs_terminal_V'].values()) for x in result['stress']);result['max_body_forward_V']=max(x['max_body_forward_V'] for x in result['stress'])
  result['nodes_final_V']={n:float(a[-1,ix['v('+n+')']]) for n in nodes}
  cap_specs=[('Lout',10e-9,'xdrv.lcap',None),('Dout',1e-9,'xdrv.dcap',None),('rawLaser',1e-9,'laser_c',None),('rawDriver',1e-9,'vdd_c',None),('Bcomp',c['cc'],'xdrv.bn2','xdrv.bctrl'),('Tcomp',c['cc'],'xdrv.tn2','xdrv.tctrl'),('Lcomp',c['cldo'],'xdrv.lzc','xdrv.lctrl'),('Dcomp',c['cldo'],'xdrv.dzc','xdrv.dctrl')]
  caps={}
  for label,cap,p,n in cap_specs:
   vv=a[:,ix['v('+p+')']]-(a[:,ix['v('+n+')']] if n else 0);ee=.5*cap*vv[[0,-1]]**2
   caps[label]=dict(capacitance_F=cap,start_J=float(ee[0]),end_J=float(ee[1]),change_J=float(ee[1]-ee[0]))
  result['explicit_capacitor_energy']=dict(capacitors=caps,change_J=sum(x['change_J'] for x in caps.values()),scope='Explicit supply and compensation capacitors only; MOS intrinsic stored charge and load/package storage not included; do not present as complete energy balance')
  if c['mode']=='dc':result.update(current_mA=float(a[-1,1]*1e3),base_current_mA=float(a[-1,ix['i(v.xdrv.vibase)']]*1e3),tail_current_mA=float(a[-1,ix['i(v.xdrv.vitail)']]*1e3),source_power_W={p:float(-a[-1,ix['v('+n+')']]*a[-1,ix['i('+p+')']]) for p,n in ports.items()})
  else:
   ledger={p:ENERGY.signed_integrals(t,-a[:,ix['v('+n+')']]*a[:,ix['i('+p+')']]) for p,n in ports.items()};sums={k:sum(x[k] for x in ledger.values()) for k in ['positive_J','returned_J','net_J']}
   if c['mode']=='frame' and c['nbits']==4736:sums.update(positive_pJ_per_offered_payload_bit=sums['positive_J']/4096*1e12,net_pJ_per_offered_payload_bit=sums['net_J']/4096*1e12)
   result.update(energy_by_port=ledger,total_energy=sums,energy_method='Exact native piecewise-linear power integral split at zero crossings',max_timestep_ps=float(np.diff(t).max()*1e12))
   if c['mode']=='startup':
    final=float(a[-1,1]);band=.05*abs(final);good=np.abs(a[:,1]-final)<=band;bad=np.flatnonzero(~good)
    result['startup']=dict(final_mA=final*1e3,time_entering_final_5percent_ns=float(t[min(bad[-1]+1,len(t)-1)]*1e9) if len(bad) else 0.,last_20percent_peak_to_peak_mA=float(np.ptp(a[t>.8*end,1])*1e3),no_error_log='Error:' not in (work/'ngspice.log').read_text())
  rawsha=sha(work/'waveform.dat');gz=work/'waveform.dat.gz'
  with (work/'waveform.dat').open('rb') as fi,gzip.open(gz,'wb',compresslevel=5) as fo:shutil.copyfileobj(fi,fo)
  h=hashlib.sha256()
  with gzip.open(gz,'rb') as f:
   for b in iter(lambda:f.read(1048576),b''):h.update(b)
  assert h.hexdigest()==rawsha;(work/'waveform.dat').unlink()
  result['waveform']=dict(path=str(gz.relative_to(ROOT)),sha256=sha(gz),raw_sha256=rawsha,bytes=gz.stat().st_size,roundtrip_verified=True)
 emit(work/'result.json',result)
 print(json.dumps({k:result[k] for k in ['case','simulation_ok','current_mA','current_range_mA','max_terminal_V','max_body_forward_V','startup'] if k in result}),flush=True)
 return result
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('name');ap.add_argument('--config',default='{}');a=ap.parse_args();run(a.name,**json.loads(a.config))
