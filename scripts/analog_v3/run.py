"""New independent coupled validation for finite-junction reference + TG.
Keeps v2 frozen selected signal PEX; all new reference/safety MOS pre-layout.
Double AC injection at sense input retains DC bias and both terminal loads.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import csv,hashlib,itertools,json,math,os,re,shutil,subprocess,tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'build/startup-v2/isolated-reference-md_hikap'
PDK=ROOT/'build/layout/pdk/gf180mcuD/libs.tech/ngspice'
E=ROOT/'evidence/analog-v3'
DEVICES=['pbias','ptail','pd1','pd2','nd1','nd2','nstage','pload','preg','pout']
VEC=['v(refrail)','v(sense)','v(refout)','v(bias)','v(led_k)','v(input)','v(gate)','v(xref.n2)','v(xref.ctrl)','i(VLEDLOAD)','i(VREFLOAD)','i(VREFRAIL)','v(fault_pin)','v(raw_pwm)','v(permit)','v(xiso.fault_b)','v(vset)']
JVEC=[f'@m.xref.x{d}.m0[{q}]' for d in DEVICES for q in ['ibd','ibs']]
ENV={'tt':('typical',27,3.3,5),'ss':('ss',85,2.97,4.5),'ff':('ff',0,3.63,5.5)}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj):p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def writecsv(p,rows):
 with p.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def cmd(args,p):
 r=subprocess.run(args,cwd=p,text=True,capture_output=True);(p/'ngspice.log').write_text(r.stdout+r.stderr)
 if r.returncode or re.search(r'(?im)^Error:|timestep too small|simulation interrupted',r.stdout+r.stderr):raise RuntimeError(str(p/'ngspice.log'))
def source(s,name,value):return re.sub(r'(?m)^'+name+r' .*?(?:\n\+.*?)*$',f'{name} {value}',s)
def main():
 w=Path(tempfile.mkdtemp(prefix='reference-tg-',dir=ROOT/'build/analog-v3'));f=w/'inputs';f.mkdir()
 names=['scripts/analog_v3/run.py','analog/reference/vset_servo_with_junctions.spice','analog/startup_v2/reference_isolator_tg.spice','analog/safety/fault_gate.spice','analog/safety/fault_led_clamp.spice','analog/models/microled.spice','evidence/joint-pex/nominal/output_pixel_pex.spice','evidence/robustness/stage-contract.json','layout/pdk-lock.json','scripts/physical/pdk-lock.json']
 hashes={}
 for name in names:
  dst=f/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dst);hashes[name]=sha(dst)
 (f/'pdk').mkdir()
 for name in ['design.ngspice','sm141064.ngspice']:
  shutil.copyfile(PDK/name,f/'pdk'/name);hashes['PDK/'+name]=sha(f/'pdk'/name)
 base=(OLD/'dc_tt_True_True_1/testbench.spice').read_text().replace(str(OLD/'inputs'),str(f))
 base=base.split('.options')[0].replace('.include design.ngspice',f'.include "{f}/pdk/design.ngspice"').replace('.lib sm141064.ngspice',f'.lib "{f}/pdk/sm141064.ngspice"')
 ref=(f/'analog/reference/vset_servo_with_junctions.spice').read_text()
 testref=ref.replace('XPD2 n2 sense tail','XPD2 n2 fb tail').replace('.subckt vset_reference_junctions vdd vss vset sense iout','.subckt vset_reference_junctions vdd vss vset sense iout fb')
 (f/'reference_loop.spice').write_text(testref)
 def deck(c,ac=None):
  s=base.replace(' typical\n',f' {c.get("corner","typical")}\n');s=re.sub(r'(?m)^.temp .*$',f'.temp {c.get("temp",27)}',s)
  logic=c.get('logic',3.3);led=c.get('led',5)
  for name,node,val in [('VSUPSAFE','safety_vdd',logic),('VLOGIC','vbuffer',logic),('VREFRAIL','refrail',logic),('VLED','rail',led),('VRAW','raw_pwm',logic*c.get('on',1)),('VFAULT','fault_pin',logic*c.get('fault',0)),('VPERMIT','permit',logic)]:s=source(s,name,f'{node} 0 {val}')
  s=s.replace('vset_reference_junctions\n',f'vset_reference_junctions RBIAS={c.get("rbias",100000)} CC={c.get("cc",3e-12)}\n')
  s=s.replace('RSET sense 0 5k',f'RSET sense 0 {c.get("rset",5000)}')
  s+=f'CSENSE sense 0 {c.get("csense",0)}\nCBIAS bias 0 {c.get("cbias",0)}\n'
  if c.get('vset') is not None:s=source(s,'VSET',f'vset 0 {c["vset"]}')
  if c.get('kind')=='ref_step':s=source(s,'VREFRAIL',f'refrail 0 PWL(0 {logic} 10u {logic} 10.1u {logic*.9} 25u {logic*.9} 25.1u {logic} 50u {logic})')
  if c.get('kind')=='led_step':s=source(s,'VLED',f'rail 0 PWL(0 {led} 10u {led} 10.1u {led-.5} 25u {led-.5} 25.1u {led} 50u {led})')
  if c.get('kind')=='vset_step':s=source(s,'VSET','vset 0 PWL(0 .5 10u .5 10.1u .505 25u .505 25.1u .5 50u .5)')
  if c.get('kind')=='fault_cycle':
   s=source(s,'VFAULT',f'fault_pin 0 PWL(0 0 10u 0 10.01u {logic} 20u {logic} 20.01u 0 50u 0)')
   s=source(s,'VPERMIT',f'permit 0 PWL(0 {logic} 10u {logic} 10.01u 0 22u 0 22.01u {logic} 50u {logic})')
   s=source(s,'VRAW',f'raw_pwm 0 PWL(0 {logic} 10u {logic} 10.01u 0 23u 0 23.01u {logic} 50u {logic})')
  if c.get('kind')=='startup':
   s=source(s,'VREFRAIL',f'refrail 0 PWL(0 0 100n {logic})')
   s=source(s,'VSET','vset 0 PWL(0 0 5u 0 5.1u .5)')
   s=source(s,'VFAULT',f'fault_pin 0 PWL(0 {logic} 20u {logic} 20.01u 0 50u 0)')
   s=source(s,'VPERMIT',f'permit 0 PWL(0 0 21.5u 0 21.51u {logic} 50u {logic})')
   s=source(s,'VRAW',f'raw_pwm 0 PWL(0 0 22.5u 0 22.51u {logic} 50u {logic})')
  vectors=VEC+JVEC
  if ac:
   s=s.replace(str(f/'analog/reference/vset_servo_with_junctions.spice'),str(f/'reference_loop.spice')).replace('refout vset_reference_junctions','refout fb vset_reference_junctions')
   if ac=='voltage':s+='VINJECT fb sense DC 0 AC 1\n';out='v(sense) v(fb)'
   else:s+='VRETURN inject sense 0\nVFORWARD inject fb 0\nIINJECT 0 inject DC 0 AC 1\n';out='i(VRETURN) i(VFORWARD)'
   ctl='op\nwrdata op.dat '+' '.join(VEC)+'\nac dec 100 1 1G\nwrdata ac.dat '+out
  elif c.get('kind'):ctl='tran 1n 50u 0 2n\nwrdata waveform.dat '+' '.join(vectors)
  else:ctl='op\nwrdata op.dat '+' '.join(vectors)
  s+='''.options reltol=1e-7 abstol=1e-14 vntol=1e-9 method=gear maxord=2
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
save all '''+' '.join(JVEC)+'\n'+ctl+'\nquit\n.endc\n.end\n'
  return s
 def run(c,ac=None):
  target=w/c['name'];target.mkdir();(target/'testbench.spice').write_text(deck(c,ac));cmd(['ngspice','-b','testbench.spice'],target)
  path=target/('ac.dat' if ac else ('waveform.dat' if c.get('kind') else 'op.dat'))
  a=np.atleast_2d(np.loadtxt(path,skiprows=1));return a,target
 cases=[dict(name=f'dc_{k:03d}',corner=co,temp=t,logic=v,led=l,on=on) for k,(co,t,v,l,on) in enumerate(itertools.product(['typical','ss','ff','sf','fs'],[0,27,85],[2.97,3.3,3.63],[4.5,5,5.5],[0,1]))]
 def dc(c):
  a,p=run(c);r={k:v for k,v in c.items() if k!='name'};r.update(name=c['name'],led_current_a=float(a[0,10]),reference_current_a=float(a[0,11]),sense_v=float(a[0,2]),bias_v=float(a[0,4]),refout_v=float(a[0,3]));r['passed']=abs(r['led_current_a']/100e-6-1)<=.05 if c['on'] else abs(r['led_current_a'])<=1e-9;return r
 with ThreadPoolExecutor(max_workers=4) as pool:dcrows=list(pool.map(dc,cases))
 writecsv(w/'dc.csv',dcrows);save(w/'dc-summary.json',{'count':len(dcrows),'failed':[r for r in dcrows if not r['passed']]});print('DC',len(dcrows),'failed',sum(not r['passed'] for r in dcrows),flush=True)
 acrows=[];acwaves={}
 # CC is tested across envelopes; CSENSE and CBIAS intentionally vary separately.
 ac_cases=[]
 for env,(co,t,v,l) in ENV.items():
  for cc,cs,cb in [(cc,0,0) for cc in [1e-12,3e-12,10e-12]]+[(3e-12,cs,0) for cs in [2e-12,10e-12,30e-12]]+[(3e-12,0,cb) for cb in [2e-12,10e-12,30e-12]]+[(cc,cs,0) for cc in [10e-12,30e-12] for cs in [10e-12,30e-12]]:
   ac_cases.append(dict(name=f'ac_{len(ac_cases):03d}',envelope=env,corner=co,temp=t,logic=v,led=l,cc=cc,csense=cs,cbias=cb))
 def cross(f,g,ph):
  idx=np.flatnonzero((g[:-1]>=0)&(g[1:]<0));return [dict(frequency_hz=float(10**np.interp(0,[g[j+1],g[j]],[np.log10(f[j+1]),np.log10(f[j])])),phase_margin_deg=float(180+np.interp(0,[g[j+1],g[j]],[ph[j+1],ph[j]]))) for j in idx]
 for c in ac_cases:
  av,pv=run(dict(c,name=c['name']+'_v'),'voltage');ai,pi=run(dict(c,name=c['name']+'_i'),'current')
  assert np.array_equal(av[:,0],ai[:,0]);freq=av[:,0];vr=av[:,1]+1j*av[:,2];vf=av[:,3]+1j*av[:,4];ir=ai[:,1]+1j*ai[:,2];iff=ai[:,3]+1j*ai[:,4]
  tv=-vr/vf;ti=ir/iff;T=(tv*ti-1)/(tv+ti+2);gain=20*np.log10(np.abs(T));phase=np.unwrap(np.angle(T))*180/np.pi
  ov=np.loadtxt(pv/'op.dat',skiprows=1);oi=np.loadtxt(pi/'op.dat',skiprows=1);opdelta=float(np.max(np.abs(ov-oi)))
  crossings=cross(freq,gain,phase);r=dict(c,dc_loop_gain_db=float(gain[0]),crossings=crossings,dc_injection_agreement_max_abs=opdelta,phase_margin_guard_pass=bool(crossings) and all(x['phase_margin_deg']>=45 for x in crossings))
  acrows.append(r);np.savetxt(w/(c['name']+'.csv'),np.c_[freq,gain,phase,20*np.log10(np.abs(tv)),np.unwrap(np.angle(tv))*180/np.pi],delimiter=',',header='frequency_hz,double_injection_gain_db,double_injection_phase_deg,voltage_only_gain_db,voltage_only_phase_deg',comments='');acwaves[c['name']]=str((w/(c['name']+'.csv')).relative_to(ROOT))
 print('AC',len(acrows),'PMfailed',sum(not r['phase_margin_guard_pass'] for r in acrows),flush=True)
 trans=[]
 tcases=[]
 for env,(co,t,v,l) in ENV.items():
  for kind in ['startup','ref_step','led_step','vset_step','fault_cycle']:
   tcases.append(dict(name=f'{kind}_{env}',envelope=env,corner=co,temp=t,logic=v,led=l,kind=kind))
 for cc,cs,cb in [(1e-12,0,0),(10e-12,0,0),(3e-12,10e-12,0),(3e-12,30e-12,0),(3e-12,0,30e-12),(10e-12,30e-12,0),(30e-12,30e-12,0)]:
  tcases.append(dict(name=f'sensitivity_{len(tcases)}',envelope='tt',kind='vset_step',cc=cc,csense=cs,cbias=cb))
 def tran(c):
  try:a,p=run(c)
  except RuntimeError as exc:return dict(c,simulation_completed=False,failure_log=str(exc),limitation='Failed runs retained; do not count as a functional pass.')
  t=a[:,0];i=a[:,10];ibd=a[:,VEC.__len__()+1+18];ibs=a[:,VEC.__len__()+1+19];dv=a[:,3]-a[:,1]
  rows={k:v for k,v in c.items()};rows['simulation_completed']=True;rows.update(led_min_a=float(i.min()),led_max_a=float(i.max()),pout_drain_above_bulk_max_v=float(dv.max()),pout_ibd_max_abs_a=float(np.abs(ibd).max()),pout_ibs_max_abs_a=float(np.abs(ibs).max()),pout_ibd_integral_c=float(np.trapezoid(ibd,t)),final_current_a=float(np.mean(i[t>49e-6])))
  # Settling after return of selected disturbance to nominal, absolute .5% baseline.
  if c['kind'] in ['ref_step','led_step','vset_step']:
   final=np.mean(i[t>49e-6]);m=(t>=25.1e-6)&(t<=49e-6);bad=np.flatnonzero(m&(np.abs(i-final)>.005*abs(final)));rows['return_settle_s']=float(t[bad[-1]+1]-25.1e-6) if len(bad) and bad[-1]+1<len(t) else 0.;rows['last_5us_pp_a']=float(np.ptp(i[t>45e-6]));rows['settle_5us_guard_pass']=rows['return_settle_s']<=5e-6
  if c['kind']=='startup':rows['held_fault_peak_a']=float(np.abs(i[t<20e-6]).max());rows['held_fault_1na_pass']=rows['held_fault_peak_a']<=1e-9
  if c['kind']=='fault_cycle':
   mask=(t>11e-6)&(t<20e-6);rows['held_fault_peak_a']=float(np.abs(i[mask]).max());rows['held_fault_1na_pass']=rows['held_fault_peak_a']<=1e-9
   # Restore gate blocked until permit/raw sequence; branch can contain displacement.
   rows['premature_gate_peak_v']=float(np.abs(a[(t>20.1e-6)&(t<22e-6),6]).max())
  out=w/(c['name']+'.csv');np.savetxt(out,a[:,[0,1,2,3,4,5,6,7,8,9,10,11,13,14,15,len(VEC)+1+18,len(VEC)+1+19]],delimiter=',',header='time_s,refrail_v,sense_v,refout_v,bias_v,led_k_v,safe_out_v,gate_v,n2_v,ctrl_v,led_current_a,ref_current_a,fault_v,raw_v,permit_v,pout_ibd_a,pout_ibs_a',comments='');rows['waveform']=str(out.relative_to(ROOT));return rows
 with ThreadPoolExecutor(max_workers=3) as pool:trans=list(pool.map(tran,tcases))
 summary=dict(schema_version=1,date='2026-10-15',stage='Reference/TG v3 pre-layout validation with frozen old selected joint PEX',raw_directory=str(w.relative_to(ROOT)),source_sha256=hashes,dc_count=len(dcrows),dc_failed_count=sum(not r['passed'] for r in dcrows),dc_on_min_a=min(r['led_current_a'] for r in dcrows if r['on']),dc_on_max_a=max(r['led_current_a'] for r in dcrows if r['on']),ac_results=acrows,ac_waveforms=acwaves,transient_results=trans,method=dict(ac='Sense feedback input double injection; voltage source DC0 retains operating point; current source DC0 open. Tv=-V(sense)/V(fb), Ti=I(VRETURN)/I(VFORWARD), T=(Tv*Ti-1)/(Tv+Ti+2). All other sources AC0.',ac_limits='Local linear feedback-loop metric. No exhaustive global stability or mismatch/PEX/package guarantee. Requires review against closed-loop transient and pole/reverse-transmission concerns.',ac_primary_sources=['https://www.analog.com/jp/lp/003/jp-web-lab/tnj-055.html','https://iic-jku.github.io/analog-circuit-design/slides/middlebrook_method.html']),limitations=['External ideal VSET .5V and RSET5k remain accuracy boundary. RBIAS and CCOMP ideal schematic passives; sweep is sensitivity, not package extraction.','MOS sw_stat_global/mismatch=0; corners are deterministic, no yield estimate. Reference/TG/safety geometry uses declared finite junction hypothesis, not final layout.','Old joint PEX excludes full PG resistance/capacitance, pads, ESD, package, substrate impedance and optical measurement.','Startup assumes pre-powered logic/LED rails and asserted external fault. Fault cycle is explicit voltage-pin stimulus; actual RTL storage qualification remains startup-v2/root v3 tests.','Model ibd/ibs are BSIM junction current outputs, not measured substrate current or latch-up qualification.'])
 for name,h in hashes.items():
  if not name.startswith('PDK/') and sha(ROOT/name)!=h:raise RuntimeError('Source changed during run: '+name)
 save(w/'summary.json',summary);E.mkdir(exist_ok=True)
 for name in ['summary.json','dc.csv','dc-summary.json']:shutil.copyfile(w/name,E/name)
 (E/'waveforms').mkdir(exist_ok=True)
 for p in w.glob('*.csv'):
  if p.name!='dc.csv':shutil.copyfile(p,E/'waveforms'/p.name)
 save(E/'latest-run.json',{'raw_directory':str(w.relative_to(ROOT)),'summary_sha256':sha(E/'summary.json')})
 print(json.dumps({'workdir':str(w),'dc_failed':summary['dc_failed_count'],'ac':acrows,'transient':trans},indent=2))
if __name__=='__main__':main()
