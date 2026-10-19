"""Isolate the reference output while fault is asserted; preserve old failures.

The fault storage is actual RTL replay; valid logic/LED rails are an explicit
boundary. New reference/isolation/safety cells are schematic, not extracted.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse,csv,hashlib,importlib.util,json,math,os,re,shutil,subprocess,tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
PDK=ROOT/'build/layout/pdk/gf180mcuD'
sp=importlib.util.spec_from_file_location('safety_math',ROOT/'scripts/safety/run.py')
M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)
ENV=M.ENVS
VECTORS=M.VECTORS+['v(refrail)','v(refout)','v(isolator_in)','v(xiso.fault_b)',
 'v(vset)','v(sense)','v(xref.pb)','v(xref.tail)','v(xref.n1)','v(xref.n2)','v(xref.ctrl)']
IDX={n:i+1 for i,n in enumerate(VECTORS)}
REFDEVS=[('XPBIAS','pb','pb','refrail','refrail'),('XPTAIL','tail','pb','refrail','refrail'),
 ('XPD1','n1','vset','tail','refrail'),('XPD2','n2','sense','tail','refrail'),
 ('XND1','n1','n1','0','0'),('XND2','n2','n1','0','0'),('XNSTAGE','ctrl','n2','0','0'),
 ('XPLOAD','ctrl','ctrl','refrail','refrail'),('XPREG','sense','ctrl','refrail','refrail'),
 ('XPOUT','refout','ctrl','refrail','refrail')]
ISODEVS=[('XFN','fault_b','fault','0','0'),('XFP','fault_b','fault','vdd','vdd'),
 ('XISO','isolator_in','fault_b','bias','0'),('XPISO','bias','fault','isolator_in','vdd'),('XDIS','bias','fault','0','0')]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command(args,folder,log):
 p=subprocess.run([str(a) for a in args],cwd=folder,text=True,capture_output=True)
 (folder/log).write_text(p.stdout+p.stderr)
 if p.returncode or re.search(r'(?im)^Error:|timestep too small|simulation interrupted',p.stdout+p.stderr):raise RuntimeError(str(folder/log))
 return p.stdout+p.stderr

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--publish-evidence',action='store_true');ap.add_argument('--only');args=ap.parse_args()
 if args.only and args.publish_evidence:raise RuntimeError('Partial debug cannot publish')
 stage=json.loads((ROOT/'evidence/robustness/stage-contract.json').read_text())
 if sha(ROOT/stage['model_path'])!=stage['model_sha256']:raise RuntimeError('Old selected PEX changed')
 for lock in ['layout/pdk-lock.json','scripts/physical/pdk-lock.json']:
  for p,h in json.loads((ROOT/lock).read_text())['files'].items():
   if sha(PDK/p)!=h:raise RuntimeError('Pinned PDK changed '+p)
 sources=['scripts/startup_v2/run.py','analog/startup_v2/reference_isolator_tg.spice',
  'analog/reference/vset_servo.spice','analog/reference/vset_servo_with_junctions.spice',
  'analog/safety/fault_gate.spice','analog/safety/fault_led_clamp.spice','scripts/safety/run.py',
  'rtl/pixel_pwm.v','rtl/safety/pixel_safety.v','sim/safety/tb_safety.v','analog/models/microled.spice',
  'evidence/safety/contract.json','evidence/safety/clamp-contract.json','evidence/robustness/stage-contract.json',
  stage['model_path'],'layout/pdk-lock.json','scripts/physical/pdk-lock.json']+list(stage['required_inputs_sha256'])
 (ROOT/'build/startup-v2').mkdir(parents=True,exist_ok=True)
 work=Path(tempfile.mkdtemp(prefix='isolated-reference-',dir=ROOT/'build/startup-v2'))
 hashes={};frozen=work/'inputs'
 for name in dict.fromkeys(sources):
  src=ROOT/name;dst=frozen/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst);hashes[name]=sha(src)
  if sha(dst)!=hashes[name]:raise RuntimeError('Frozen byte mismatch')
 (work/'input-manifest.json').write_text(json.dumps(hashes,indent=2)+'\n')
 tools={k:command([k,'--version' if k=='ngspice' else '-V'],work,k+'-version.log') for k in ['ngspice','iverilog']}
 binary=work/'safety.vvp'
 command(['iverilog','-g2012','-s','tb_safety','-o',binary,frozen/'rtl/pixel_pwm.v',frozen/'rtl/safety/pixel_safety.v',frozen/'sim/safety/tb_safety.v'],work,'rtl-compile.log')
 cases=[]
 # Genuine failure control, same old zero-junction servo and Trap integration.
 for step in [10,2]:
  cases.append(dict(name=f'baseline_startup_{step}ns',kind='startup',envelope='tt',ramp_ns=100,maxstep_ns=step,isolated=False,junctions=False,method='trap',stop_ns=40000,duty=256,initial_fault_clear_ns=20000))
 cases.append(dict(name='baseline_matched_finite_gear',kind='startup',envelope='tt',ramp_ns=100,maxstep_ns=10,isolated=False,junctions=True,method='gear',stop_ns=40000,duty=256,initial_fault_clear_ns=20000))
 for env in ['tt','ss','ff']:
  for ramp in [100,1000,10000]:
   cases.append(dict(name=f'startup_{env}_ramp{ramp}ns',kind='startup',envelope=env,ramp_ns=ramp,maxstep_ns=10,isolated=True,junctions=True,method='gear',stop_ns=40000,duty=256,initial_fault_clear_ns=20000))
  cases.append(dict(name=f'fault_{env}',kind='fault',envelope=env,maxstep_ns=10,isolated=True,junctions=True,method='gear',stop_ns=66125,duty=256,fault_ns=50125,clock_stop_ns=47700))
 cases.append(dict(name='startup_tt_ramp100ns_fine',kind='startup',envelope='tt',ramp_ns=100,maxstep_ns=2,isolated=True,junctions=True,method='gear',stop_ns=40000,duty=256,initial_fault_clear_ns=20000))
 cases.append(dict(name='startup_tt_zero_junction',kind='startup',envelope='tt',ramp_ns=100,maxstep_ns=10,isolated=True,junctions=False,method='gear',stop_ns=40000,duty=256,initial_fault_clear_ns=20000))
 cases.append(dict(name='startup_tt_vset_late',kind='startup',envelope='tt',ramp_ns=100,vset_start_ns=5000,maxstep_ns=10,isolated=True,junctions=True,method='gear',stop_ns=40000,duty=256,initial_fault_clear_ns=20000))
 cases.append(dict(name='fault_tt_fine',kind='fault',envelope='tt',maxstep_ns=2,isolated=True,junctions=True,method='gear',stop_ns=66125,duty=256,fault_ns=50125,clock_stop_ns=47700))
 for step in [10,2]:cases.append(dict(name=f'normal_d1_{step}ns',kind='normal',envelope='tt',maxstep_ns=step,isolated=True,junctions=True,method='gear',stop_ns=1070000,duty=1))
 if args.only:cases=[c for c in cases if c['name']==args.only]
 if not cases:raise RuntimeError('Unknown case')
 for c in cases:
  target=work/c['name'];target.mkdir();c['target']=target
  log=command(['vvp',binary,f'+DUTY={c["duty"]}',f'+FAULT_NS={c.get("fault_ns",-1)}',f'+STOP_NS={c.get("clock_stop_ns",-1)}',f'+STOP_TIME_NS={c["stop_ns"]}',f'+INITIAL_FAULT_CLEAR_NS={c.get("initial_fault_clear_ns",100)}',f'+OUT={target/"rtl-events.csv"}'],target,'rtl.log')
  c['rtl_passed']='SAFETY_CASE_PASS' in log;c['rows']=M.read_events(target/'rtl-events.csv')
  for p in ['design.ngspice','sm141064.ngspice']:(target/p).symlink_to(os.path.relpath(PDK/'libs.tech/ngspice'/p,target))
 led_is=100e-6/math.expm1((2.8-100e-6*50)/(3*8.617333262145e-5*300.15))
 def deck(c,dc=None):
  mos,temp,logic,led=ENV[c['envelope']];stop=c['stop_ns'];rows=c.get('rows',[])
  raw=M.pwl_signal(rows,'raw_pwm',logic,stop) if dc is None else str(dc*logic)
  fault=M.pwl_signal(rows,'fault',logic,stop) if dc is None else '0'
  permit=M.pwl_signal(rows,'permit',logic,stop) if dc is None else str(logic)
  refrail=f'PWL(0 0 {c["ramp_ns"]}n {logic})' if c['kind']=='startup' and dc is None else str(logic)
  vset=f'PWL(0 0 {c["vset_start_ns"]}n 0 {c["vset_start_ns"]+100}n .5)' if c.get('vset_start_ns') and dc is None else '.5'
  reference='vset_servo_with_junctions.spice' if c['junctions'] else 'vset_servo.spice'
  subckt='vset_reference_junctions' if c['junctions'] else 'vset_reference'
  isolation=f'.include "{frozen}/analog/startup_v2/reference_isolator_tg.spice"\nXISO isolator_in bias fault_pin safety_vdd 0 reference_isolator_tg' if c['isolated'] else 'VBASE isolator_in bias 0\n* Unconnected identical isolate cell for compatible voltage/stress vectors\nXISO 0 unused_iso fault_pin safety_vdd 0 reference_isolator_tg\n.include "'+str(frozen)+'/analog/startup_v2/reference_isolator_tg.spice"'
  neighbors='\n'.join(f'VN{n} {r["node"]} 0 0' for n,r in enumerate(stage['neighbor_sources']))
  pins=' '.join(stage['pin_bindings'][p] for p in stage['ports_order'])
  ctl='op' if dc is not None else f'tran 10n {stop}n 0 {c["maxstep_ns"]}n'
  return f'''Reference startup isolation v2, declared powered-safety/LED boundary
.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0 LED_IS={led_is:.17g}
.lib sm141064.ngspice {mos}
.temp {temp}
VSUPSAFE safety_vdd 0 {logic}
VLOGIC vbuffer 0 {logic}
VREFRAIL refrail 0 {refrail}
VSET vset 0 {vset}
RSET sense 0 5k
.include "{frozen}/analog/reference/{reference}"
XREF refrail 0 vset sense refout {subckt}
VREFLOAD refout isolator_in 0
{isolation}
VLED rail 0 {led}
VLEDLOAD rail led_anode 0
VCLAMPSUP rail clamp_anode 0
VRAW raw_pwm 0 {raw}
VPERMIT permit 0 {permit}
VFAULT fault_pin 0 {fault}
RFAULTPULLUP safety_vdd fault_pin 1Meg
.include "{frozen}/analog/safety/fault_gate.spice"
XSAFE raw_pwm fault_pin permit input safety_vdd 0 fault_gate
BUNUSED unused_safe 0 V=v(input)
.include "{frozen}/analog/safety/fault_led_clamp.spice"
XCLAMP fault_pin clamp_anode led_k 0 fault_led_clamp
.include "{frozen}/analog/models/microled.spice"
XLED led_anode led_k microled
{neighbors}
.include "{frozen/stage['model_path']}"
XJOINT {pins} {stage['subckt']}
.options reltol=1e-7 abstol=1e-14 vntol=1e-9 method=gear maxord=2
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
save all @d.xled.dled[id] @d.xled.dled[capcur] @m.xjoint.x10.m0[id]
{'* Strict DC options' if dc is not None else 'option reltol=1e-6 abstol=1e-12 vntol=1e-7 method='+c['method']+' maxord=2'}
{ctl}
wrdata waveform.dat {' '.join(VECTORS)}
quit
.endc
.end
'''
 dc={};dc_results=[]
 for env,junc,iso in sorted(set((c['envelope'],c['junctions'],c['isolated']) for c in cases)):
  for level in [0,1]:
   c=dict(name=f'dc_{env}_{junc}_{iso}_{level}',kind='dc',envelope=env,junctions=junc,isolated=iso,stop_ns=0)
   target=work/c['name'];target.mkdir()
   for p in ['design.ngspice','sm141064.ngspice']:(target/p).symlink_to(os.path.relpath(PDK/'libs.tech/ngspice'/p,target))
   (target/'testbench.spice').write_text(deck(c,level));command(['ngspice','-b','testbench.spice'],target,'ngspice.log')
   a=np.atleast_2d(np.loadtxt(target/'waveform.dat',skiprows=1));full=float(a[0,IDX['i(VLEDLOAD)']]);dc[env,junc,iso,level]=full
   dc_results.append(dict(name=c['name'],current_a=full,passed=abs(full/100e-6-1)<=.05 if level else abs(full)<1e-9,deck_sha256=sha(target/'testbench.spice'),reference_output_a=float(a[0,IDX['i(VREFLOAD)']]),BIAS_v=float(a[0,IDX['v(bias)']]),refout_v=float(a[0,IDX['v(refout)']])))
 def run(c):
  target=c['target'];(target/'testbench.spice').write_text(deck(c));command(['ngspice','-b','testbench.spice'],target,'ngspice.log')
  a=np.loadtxt(target/'waveform.dat',skiprows=1);t=a[:,0];i=a[:,IDX['i(VLEDLOAD)']];total=a[:,IDX['@d.xled.dled[id]']];cap=a[:,IDX['@d.xled.dled[capcur]']];cond=total-cap
  full=dc[c['envelope'],c['junctions'],c['isolated'],1]
  checks=[dict(name='Actual RTL hold/recovery assertions',passed=c['rtl_passed'])]
  def ck(n,yes,**more):checks.append(dict(name=n,passed=bool(yes),**more))
  def window(l,r):
   _,v=M.clip(t,i,l,r);_,co=M.clip(t,cond,l,r);_,ca=M.clip(t,cap,l,r)
   return dict(left_s=l,right_s=r,branch_max_abs_a=float(np.abs(v).max()),branch_min_a=float(v.min()),branch_max_a=float(v.max()),branch_charge=M.split_charge(t,i,l,r),conduction_max_abs_a=float(np.abs(co).max()),conduction_charge=M.split_charge(t,cond,l,r),capacitance_max_abs_a=float(np.abs(ca).max()),capacitance_charge=M.split_charge(t,cap,l,r))
  out=dict(name=c['name'],conditions={k:v for k,v in c.items() if k not in ['target','rows']},dc_full_a=full,checks=checks)
  if c['kind']=='startup':
   out['startup']=window(0,20e-6);out['startup_slices']=[window(0,1e-6),window(1e-6,5e-6),window(5e-6,20e-6)]
   guard=out['startup']['branch_max_abs_a']<1e-9
   if c['isolated']:ck('Unchanged all-startup 1nA branch peak guard',guard)
   else:ck('Original all-startup failure is reproduced',not guard);out['expected_failure']=not guard
   out['fault_release_before_permit']=window(20e-6,21.5e-6)
   _,v=M.clip(t,a[:,IDX['v(input)']],20e-6,21.5e-6);ck('Fault release alone cannot pass PWM before permit',float(np.abs(v).max())<.01)
   ck('Model conduction remains below 1nA before permit',out['fault_release_before_permit']['conduction_max_abs_a']<1e-9)
   out['permit_before_raw']=window(21.5e-6,22.5e-6)
   late=window(30e-6,40e-6);out['recovered_dc_window']=late;avg=M.integral(t,i,30e-6,40e-6)/10e-6
   ck('Explicitly recovered full current within 5%',abs(avg/100e-6-1)<.05,average_a=avg)
   out['bias_recovery_peak_v']=float(a[(t>=20e-6)&(t<=22.5e-6),IDX['v(bias)']].max())
   out['bias_recovery_settle_s']=M.stable_below_time(t,a[:,IDX['v(bias)']]-float(a[-1,IDX['v(bias)']]),20e-6,22.5e-6,.01*float(a[-1,IDX['v(bias)']]))
  elif c['kind']=='normal':
   l,r=514.5e-6,1026.5e-6;q=M.integral(t,i,l,r);err=(q/((r-l)*full/256)-1)*100
   out.update(charge_c=q,area_error_pct=err,average_current_a=q/(r-l));ck('Unchanged d1 2% charge guard',abs(err)<=2)
  else:
   f=c['fault_ns']*1e-9;out['fault']=window(f,f+1e-6)
   stable=M.stable_below_time(t,i,f,f+3e-6,1e-9);out['fault_to_safe_s']=None if stable is None else stable-f
   out['held_fault']=window(f+1e-6,f+2e-6);out['fault_removal_stopped_clock']=window(f+3e-6,f+5e-6)
   ck('Unchanged fault 1us deadline',stable is not None and stable-f<=1e-6)
   ck('Unchanged held-fault 1nA guard',out['held_fault']['branch_max_abs_a']<1e-9)
   ck('Unchanged fault positive 10pC budget',out['fault']['branch_charge']['positive_c']<=10e-12)
   ck('Fault negative 20pC teaching budget',abs(out['fault']['branch_charge']['negative_c'])<=20e-12)
   ck('Fault negative 10mA teaching peak',out['fault']['branch_min_a']>=-.01)
   reverse=float(max(0,np.max(a[(t>=f)&(t<=f+1e-6),IDX['v(led_k)']]-ENV[c['envelope']][3])))
   out['fault_reverse_peak_v']=reverse;ck('Fault model reverse 0.5V teaching budget',reverse<=.5)
   _,v=M.clip(t,a[:,IDX['v(input)']],f+3e-6,f+5e-6);ck('Fault removal/clock stop cannot recover PWM',np.abs(v).max()<.01)
   ck('No model conduction before stopped-clock recovery',out['fault_removal_stopped_clock']['conduction_max_abs_a']<1e-9)
   avg=M.integral(t,i,t[-1]-3e-6,t[-1])/3e-6;out['recovered_current_a']=avg;ck('After reset/recovery current within 5%',abs(avg/100e-6-1)<.05)
  # Every declared new MOS terminal pair. No SOA assertion or latchup claim.
  zero=np.zeros(len(t));logic=np.full(len(t),ENV[c['envelope']][2])
  node={'0':zero,'vdd':logic,'fault':a[:,IDX['v(fault_pin)']],'bias':a[:,IDX['v(bias)']],'isolator_in':a[:,IDX['v(isolator_in)']],'fault_b':a[:,IDX['v(xiso.fault_b)']]}
  stress={}
  def add(prefix,devs,nodes):
   for name,d,g,s,b in devs:
    stress[prefix+name]={label:dict(min_v=float(y.min()),max_v=float(y.max()),max_abs_v=float(np.abs(y).max())) for label,y in [('VGS',nodes[g]-nodes[s]),('VGD',nodes[g]-nodes[d]),('VDS',nodes[d]-nodes[s]),('VSB',nodes[s]-nodes[b]),('VDB',nodes[d]-nodes[b])]}
  add('iso/',ISODEVS,node)
  ref={'0':zero,'refrail':a[:,IDX['v(refrail)']],'vset':a[:,IDX['v(vset)']],'sense':a[:,IDX['v(sense)']],'refout':a[:,IDX['v(refout)']]}
  for n in ['pb','tail','n1','n2','ctrl']:ref[n]=a[:,IDX[f'v(xref.{n})']]
  add('ref/',REFDEVS,ref)
  saf={'0':zero,'vdd':logic,'raw':a[:,IDX['v(raw_pwm)']],'fault':node['fault'],'permit':a[:,IDX['v(permit)']],'out':a[:,IDX['v(input)']]}
  for n in ['fault_b','nand_n','stack1','stack2']:saf[n]=a[:,IDX[f'v(xsafe.{n})']]
  add('safe/',M.NEW_DEVICES,saf)
  clamp={'0':zero,'fault':node['fault'],'anode':a[:,IDX['v(clamp_anode)']],'cathode':a[:,IDX['v(led_k)']],'hb':a[:,IDX['v(xclamp.fault_hb)']]}
  add('clamp/',[('XLN0','hb','fault','0','0'),('XCP','cathode','hb','anode','anode')],clamp)
  out['terminal_stress']=stress;out['max_new_terminal_difference_v']=max(p['max_abs_v'] for d in stress.values() for p in d.values())
  out['terminal_stress_scope']='Capture only, not SOA/HCI/TDDB/latchup qualification; finite junctions assumed 0.44um landing.'
  out['passed']=all(x['passed'] for x in checks);out['raw_sha256']=sha(target/'waveform.dat');out['deck_sha256']=sha(target/'testbench.spice');out['rtl_sha256']=sha(target/'rtl-events.csv')
  # Retain all startup/fault/recovery samples; normal compact waveform keeps all PWM edges.
  if c['kind']=='normal':
   sel=np.unique(np.r_[np.arange(0,len(t),max(1,len(t)//5000)),np.flatnonzero((t>514.3e-6)&(t<516e-6)),np.flatnonzero((t>770.3e-6)&(t<772e-6))])
  else:sel=np.arange(len(t))
  with (target/'waveform.csv').open('w') as stream:
   wr=csv.writer(stream);wr.writerow(['time_s']+VECTORS);wr.writerows(a[sel].tolist())
  out['csv_sha256']=sha(target/'waveform.csv');(target/'result.json').write_text(json.dumps(out,indent=2)+'\n')
  print(c['name'],out['passed'],out.get('area_error_pct',out.get('fault_to_safe_s',out.get('startup',{}).get('branch_max_abs_a'))),flush=True)
  return out
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,cases))
 checks=[dict(name='DC '+d['name'],passed=d['passed']) for d in dc_results]
 for r in results:checks.extend(dict(name=r['name']+' / '+c['name'],**{k:v for k,v in c.items() if k!='name'}) for c in r['checks'])
 lookup={r['name']:r for r in results};convergence=[]
 for a,b,key in [('normal_d1_10ns','normal_d1_2ns','normal'),('fault_tt','fault_tt_fine','fault'),('startup_tt_ramp100ns','startup_tt_ramp100ns_fine','startup')]:
  if a not in lookup or b not in lookup:continue
  aa,bb=lookup[a],lookup[b]
  qa=aa['charge_c'] if key=='normal' else aa[key]['branch_charge']['positive_c'];qb=bb['charge_c'] if key=='normal' else bb[key]['branch_charge']['positive_c']
  diff=abs(qb/qa-1)*100 if qa else None
  row=dict(name=key,coarse=a,fine=b,coarse_charge_c=qa,fine_charge_c=qb,change_pct=diff,original_relative_limit_pct=.2,passed=diff is not None and diff<=.2)
  convergence.append(row)
  if key!='startup':checks.append(dict(name=key+' charge convergence <=0.2%',passed=row['passed'],change_pct=diff))
  else:
   checks.append(dict(name='Legacy startup Q+ relative convergence <=0.2%',passed=row['passed'],change_pct=diff))
   row['numerical_resolution']=dict(absolute_difference_c=abs(qb-qa),difference_fraction_of_fault_10pC_budget=abs(qb-qa)/10e-12,coarse_equivalent_electrons=qa/1.602176634e-19,fine_equivalent_electrons=qb/1.602176634e-19,assessment='Keep original relative result; SPICE charge is continuous; equivalent electron count is scale context only, not a numerical floor. Absolute budget comparison is extra diagnostic, not a substitute for the original relative contract; instrument resolution is unknown.')
 functionality=[c for c in checks if not c['name'].startswith('Legacy startup')]
 summary=dict(schema_version=1,date='2026-10-14',stage='startup-v2 / 5 schematic MOS CMOS transmission-gate reference isolation + finite-junction servo + old selected signal PEX',source_sha256=hashes,tools=tools,raw_directory=str(work.relative_to(ROOT)),transient_runs=len(results),dc_runs=len(dc_results),results=results,dc_results=dc_results,convergence=convergence,checks=checks,functional_contract_passed=all(c['passed'] for c in functionality),legacy_startup_relative_convergence_passed=all(c['passed'] for c in checks if c['name'].startswith('Legacy startup')),passed=all(c['passed'] for c in checks),limitations=['External fault initially asserted; valid powered logic and LED rail, not POR','Only reference supply/VSET sequencing tested, not arbitrary whole-chip power order','Recovery storage remains RTL replay','New isolation/reference/gate/clamp lack layout/DRC/LVS/PEX','Finite junction geometry is declared hypothesis, not extraction','External VSET/RSET tolerances and synthetic LED model remain','No silicon, optical extinction, package/IO/ESD or reliability evidence'])
 (work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 if args.publish_evidence:
  dest=ROOT/'evidence/startup-v2';dest.mkdir(exist_ok=True)
  for r in results:
   target=dest/'waveforms'/r['name'];target.mkdir(parents=True,exist_ok=True)
   for fn in ['waveform.csv','rtl-events.csv','result.json','testbench.spice']:shutil.copyfile(work/r['name']/fn,target/fn)
   r['csvpath']=str((target/'waveform.csv').relative_to(ROOT));r['rtlpath']=str((target/'rtl-events.csv').relative_to(ROOT))
  (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps({'raw':str(work),'functional_passed':summary['functional_contract_passed'],'legacy_convergence_passed':summary['legacy_startup_relative_convergence_passed'],'overall':summary['passed']}),flush=True)
 return 0 if summary['passed'] else 2
if __name__=='__main__':raise SystemExit(main())
