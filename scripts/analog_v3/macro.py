"""Replay actual safety RTL against new 39-MOS geometry or full RC macro.
The 21 macro pins are fixed by layout/startup_v3/contract.json. External
VSET/RSET/RBIAS/CCOMP/RRELEASE remain explicit, absent pad/package parasitics.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse,csv,hashlib,importlib.util,json,math,re,shutil,subprocess,tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[2];PDK=ROOT/'build/layout/pdk/gf180mcuD/libs.tech/ngspice'
spec=importlib.util.spec_from_file_location('mathutil',ROOT/'scripts/safety/run.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
VEC=['i(VLEDLOAD)','v(led_k)','v(bias)','v(refout)','v(sense)','v(n2)','v(ctrl)','v(refrail)','v(raw_pwm)','v(fault)','v(permit)','v(safe_out)','v(pwm_drive)','v(gate)','v(pb)','v(fault_hb)','i(VREFRAIL)','i(VSAFE)','i(VBUF)','i(VLED)','@d.xled.dled[id]','@d.xled.dled[capcur]','@m.xdut.x28.m0[ibd]','@m.xdut.x28.m0[ibs]']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj):p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def command(args,p,log):
 r=subprocess.run([str(a) for a in args],cwd=p,text=True,capture_output=True);(p/log).write_text(r.stdout+r.stderr)
 if r.returncode or re.search(r'(?im)^Error:|timestep too small|simulation interrupted',r.stdout+r.stderr):raise RuntimeError(str(p/log))
 return r.stdout+r.stderr

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--netlist',type=Path,required=True);ap.add_argument('--tag',required=True);ap.add_argument('--cc-pf',type=float,default=3);ap.add_argument('--csense-pf',type=float,default=0);ap.add_argument('--workers',type=int,default=2);ap.add_argument('--bleed-ohm',type=float);ap.add_argument('--only');ap.add_argument('--only-kind',choices=['startup','normal','fault']);ap.add_argument('--startup-grid',action='store_true');ap.add_argument('--quick',action='store_true');a=ap.parse_args();a.netlist=a.netlist.resolve()
 name=a.tag;w=Path(tempfile.mkdtemp(prefix=name+'-',dir=ROOT/'build/analog-v3'));inp=w/'inputs';inp.mkdir();hashes={}
 files={'dut.spice':a.netlist,'microled.spice':ROOT/'analog/models/microled.spice','pixel_pwm.v':ROOT/'rtl/pixel_pwm.v','pixel_safety.v':ROOT/'rtl/safety/pixel_safety.v','tb_safety.v':ROOT/'sim/safety/tb_safety.v','math.py':ROOT/'scripts/safety/run.py','macro.py':Path(__file__),'contract.json':ROOT/'layout/startup_v3/contract.json','design.ngspice':PDK/'design.ngspice','sm141064.ngspice':PDK/'sm141064.ngspice'}
 for dest,src in files.items():shutil.copyfile(src,inp/dest);hashes[str(src.relative_to(ROOT))]=sha(src)
 text=(inp/'dut.spice').read_text();pout_line=next(x for x in text.splitlines() if x.startswith('X28 '));pout_tokens=pout_line.split();assert [n.split('.')[0].upper() for n in pout_tokens[1:5]]==['VREF','CTRL','REFOUT','VREF'] and 'pfet_06v0' in pout_line and 'w=100u l=10u' in pout_line
 isrc='X28' # named extracted output PMOS, verify same physical nodes before metrics.
 binary=w/'safety.vvp';command(['iverilog','-g2012','-s','tb_safety','-o',binary,inp/'pixel_pwm.v',inp/'pixel_safety.v',inp/'tb_safety.v'],w,'rtl-compile.log')
 cases=[]
 for env in M.ENVS:
  for ramp in ([100] if a.quick else [100,1000,10000]):cases.append(dict(name=f'startup_{env}_{ramp}',kind='startup',envelope=env,ramp_ns=ramp,stop_ns=40000,duty=256,initial_fault_clear_ns=20000,maxstep_ns=2))
  cases.append(dict(name=f'fault_{env}',kind='fault',envelope=env,fault_ns=50125,clock_stop_ns=47700,stop_ns=66125,duty=256,maxstep_ns=2))
 cases.append(dict(name='startup_tt_vset_late',kind='startup',envelope='tt',ramp_ns=100,vset_start_ns=5000,stop_ns=40000,duty=256,initial_fault_clear_ns=20000,maxstep_ns=2))
 if not a.quick:
  for env in M.ENVS:
   cases.append(dict(name=f'normal_{env}_d1',kind='normal',envelope=env,stop_ns=1070000,duty=1,maxstep_ns=5))
  cases.append(dict(name='normal_tt_d1_fine',kind='normal',envelope='tt',stop_ns=1070000,duty=1,maxstep_ns=2))
 if a.only:cases=[c for c in cases if c['name']==a.only]
 if a.only_kind:cases=[c for c in cases if c['kind']==a.only_kind]
 for c in cases:
  p=w/c['name'];p.mkdir();log=command(['vvp',binary,f'+DUTY={c["duty"]}',f'+FAULT_NS={c.get("fault_ns",-1)}',f'+STOP_NS={c.get("clock_stop_ns",-1)}',f'+STOP_TIME_NS={c["stop_ns"]}',f'+INITIAL_FAULT_CLEAR_NS={c.get("initial_fault_clear_ns",100)}',f'+OUT={p/"rtl-events.csv"}'],p,'rtl.log');c['rtl_pass']='SAFETY_CASE_PASS' in log;c['rows']=M.read_events(p/'rtl-events.csv')
 led_is=100e-6/math.expm1((2.8-100e-6*50)/(3*8.617333262145e-5*300.15))
 def deck(c,dc=None):
  co,t,v,l=M.ENVS[c['envelope']];stop=c['stop_ns'];rows=c.get('rows',[])
  raw=str(v*dc) if dc is not None else M.pwl_signal(rows,'raw_pwm',v,stop)
  fault='0' if dc is not None else M.pwl_signal(rows,'fault',v,stop)
  permit=str(v) if dc is not None else M.pwl_signal(rows,'permit',v,stop)
  refrail=f'PWL(0 0 {c["ramp_ns"]}n {v})' if c['kind']=='startup' and dc is None else str(v)
  if a.startup_grid and c['kind']=='startup' and dc is None:
   ramp=c['ramp_ns']/1e9;rt=int(round(c['ramp_ns']*10000));ticks=sorted(set(range(10001))|set(range(rt-10000,rt+20001))|{0,rt});times=[k/1e13 for k in ticks];refrail='PWL(\n'+'\n'.join(f'+ {t:.17g} {v*min(t/ramp,1):.17g}' for t in times)+'\n+)'
  vset=f'PWL(0 0 {c["vset_start_ns"]}n 0 {c["vset_start_ns"]+100}n .5)' if c.get('vset_start_ns') and dc is None else '.5'
  ctl='op\nwrdata op.dat '+' '.join(VEC) if dc is not None else f'tran {".001n" if a.startup_grid and c["kind"]=="startup" else "10n"} {stop}n 0 {c["maxstep_ns"]}n\nwrdata waveform.dat '+' '.join(VEC)
  return f'''Actual 39MOS macro: {name}, external passives explicit
.include "{inp}/design.ngspice"
.param sw_stat_global=0 sw_stat_mismatch=0 LED_IS={led_is:.17g}
.lib "{inp}/sm141064.ngspice" {co}
.temp {t}
VREFRAIL refrail 0 {refrail}
VSAFE saferail 0 {v}
VBUF bufrail 0 {v}
VLED rail 0 {l}
VLEDLOAD rail led_anode 0
VSET vset 0 {vset}
VRAW raw_pwm 0 {raw}
VFAULT fault 0 {fault}
VPERMIT permit 0 {permit}
RFAULTPULLUP saferail fault 1Meg
RSET sense 0 5k
RBIAS pb 0 100k
CCOMP n2 ctrl {a.cc_pf}p
RRELEASE rail fault_hb 100k
CSENSE sense 0 {a.csense_pf}p
{'RBLEED refout 0 '+str(a.bleed_ohm) if a.bleed_ohm else '* No external REFOUT bleed'}
.include "{inp}/dut.spice"
XDUT 0 refrail saferail bufrail rail raw_pwm fault permit vset sense pb n2 ctrl fault_hb led_k refout bias gate pwm_b safe_out pwm_drive startup_test_macro
.include "{inp}/microled.spice"
XLED led_anode led_k microled
.options reltol=1e-7 abstol=1e-14 vntol=1e-9 method=gear maxord=2
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
save all @d.xled.dled[id] @d.xled.dled[capcur] @m.xdut.x28.m0[ibd] @m.xdut.x28.m0[ibs]
{ctl}
quit
.endc
.end
'''
 dcrows=[];full={}
 for env in M.ENVS:
  for level in [0,1]:
   c=dict(envelope=env,kind='dc',stop_ns=0);p=w/f'dc_{env}_{level}';p.mkdir();(p/'testbench.spice').write_text(deck(c,level));command(['ngspice','-b','testbench.spice'],p,'ngspice.log');d=np.loadtxt(p/'op.dat',skiprows=1);current=float(d[1]);dcrows.append(dict(envelope=env,on=level,current_a=current,passed=abs(current/100e-6-1)<=.05 if level else abs(current)<1e-9));full[env,level]=current
 print('DC',name,dcrows,flush=True)
 def run(c):
  p=w/c['name'];(p/'testbench.spice').write_text(deck(c));row={k:v for k,v in c.items() if k!='rows'}
  try:command(['ngspice','-b','testbench.spice'],p,'ngspice.log')
  except RuntimeError as e:row.update(simulation_completed=False,failure_log=str(e));return row
  d=np.loadtxt(p/'waveform.dat',skiprows=1);t=d[:,0];i=d[:,1];cond=d[:,21]-d[:,22];checks=[]
  def ck(n,p):checks.append(dict(name=n,passed=bool(p)))
  def metric(l,r):
   x,y=M.clip(t,i,l,r);return dict(branch_max_abs_a=float(np.abs(y).max()),branch_charge=M.split_charge(t,i,l,r),conduction_max_abs_a=float(np.abs(M.clip(t,cond,l,r)[1]).max()))
  ck('Actual RTL assertions',c['rtl_pass'])
  if c['kind']=='startup':
   row['startup']=metric(0,20e-6);ck('Startup held-fault 1nA guard',row['startup']['branch_max_abs_a']<1e-9);row['release']=metric(20e-6,21.5e-6);ck('No conduction before permission',row['release']['conduction_max_abs_a']<1e-9);late=M.integral(t,i,30e-6,40e-6)/10e-6;row['recovered_a']=late;ck('Recovered current within5pct',abs(late/100e-6-1)<.05)
  elif c['kind']=='fault':
   f=c['fault_ns']*1e-9;row['fault']=metric(f,f+1e-6);safe=M.stable_below_time(t,i,f,f+3e-6,1e-9);row['fault_to_safe_s']=None if safe is None else safe-f;ck('Fault shutdown under1us',safe is not None and safe-f<1e-6);ck('Fault Q+ under10pC',row['fault']['branch_charge']['positive_c']<10e-12);ck('Fault Q- under20pC',abs(row['fault']['branch_charge']['negative_c'])<20e-12);row['held_fault']=metric(f+1e-6,f+2e-6);ck('Held fault under1nA',row['held_fault']['branch_max_abs_a']<1e-9);row['release_stopped']=metric(f+3e-6,f+5e-6);ck('No conduction on stopped-clock release',row['release_stopped']['conduction_max_abs_a']<1e-9);last=M.integral(t,i,t[-1]-3e-6,t[-1])/3e-6;row['recovered_a']=last;ck('Recovered within5pct',abs(last/100e-6-1)<.05)
  else:
   q=M.integral(t,i,514.5e-6,1026.5e-6);err=100*(q/(512e-6*full[c['envelope'],1]/256)-1);row.update(charge_c=q,d1_error_pct=err);ck('d1 charge error within2pct',abs(err)<2)
  row['pout_model_ibd_max_a']=float(np.abs(d[:,23]).max());row['pout_model_ibs_max_a']=float(np.abs(d[:,24]).max());row['pout_external_refout_above_vref_v']=float((d[:,4]-d[:,8]).max());row['checks']=checks;row['simulation_completed']=True;row['passed']=all(x['passed'] for x in checks)
  # Dense boundary windows retained; normal full raw remains in build.
  keep=set(np.linspace(0,len(t)-1,min(400,len(t)),dtype=int))
  for column in [1,2,3,4,5,6,7,12,13,14]:
   keep.add(int(np.argmin(d[:,column])));keep.add(int(np.argmax(d[:,column])))
  for low,high in [(0,1e-9),(0,1e-6),(19.9e-6,22.6e-6),(50e-6,55e-6),(514.4e-6,518e-6)]:
   ii=np.flatnonzero((t>=low)&(t<=high))
   if len(ii):
    for column in [1,3,4,5,14]:
     keep.add(int(ii[np.argmin(d[ii,column])]))
     keep.add(int(ii[np.argmax(d[ii,column])]))
  mask=np.asarray(sorted(keep),dtype=int)
  np.savetxt(p/'compact.csv',d[mask],delimiter=',',header='time_s,'+','.join(VEC),comments='');return row
 with ThreadPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(run,cases))
 summary=dict(schema_version=1,date='2026-10-15',tag=name,raw_directory=str(w.relative_to(ROOT)),dut_source=str(a.netlist.relative_to(ROOT)),dut_sha256=sha(a.netlist),pout_terminal_mapping=pout_tokens[:6],source_sha256=hashes,cc_pf=a.cc_pf,csense_pf=a.csense_pf,bleed_ohm=a.bleed_ohm,selected_case=a.only,selected_kind=a.only_kind,startup_grid=dict(enabled=a.startup_grid,grid_step_s=1e-13,tstep_s=1e-12,windows='0–1ns and ramp_end−1ns to ramp_end+2ns',same_source_function=True),dc_results=dcrows,results=results,passed=all(r['passed'] for r in dcrows) and all(r.get('passed',False) for r in results),compact_waveform_note='Decimated visualization only,400 evenly indexed samples plus extrema. Metrics use full raw waveform.dat, never compact.csv.',limitations=['39MOS macro only: no pad/ESD/package/other digital cells/POR or optical qualification.','All external passives and rail ideal-source contracts explicit. Pin-level fault/recovery from actual RTL simulation, not storage transistors in macro.','Extracted model geometry or distributed R/C scope follows selected DUT file and physical manifest.','All startup cases assume VSAFE/VBUF/LED prepowered and external fault high.'])
 save(w/'summary.json',summary);dest=ROOT/'evidence/analog-v3'/name;dest.mkdir(parents=True,exist_ok=True);shutil.copyfile(w/'summary.json',dest/'summary.json')
 for c in cases:
  p=w/c['name'];q=dest/c['name'];q.mkdir(exist_ok=True)
  for n in ['compact.csv','rtl-events.csv']:
   if (p/n).exists():shutil.copyfile(p/n,q/n)
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
