"""Nominal routed-SDF events replayed through the complete 39MOS extracted RC.
Digital cell delay is measured from SDF; 10ns analog input slew remains assumed.
"""
from pathlib import Path
import argparse,csv,hashlib,importlib.util,json,math,shutil,subprocess,tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('m',ROOT/'scripts/safety/run.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--netlist',type=Path,required=True);ap.add_argument('--tag',required=True);ap.add_argument('--bleed-meg',type=float,default=0);a=ap.parse_args();a.netlist=a.netlist.resolve()
 B=Path(tempfile.mkdtemp(prefix='sdf-'+a.tag+'-',dir=ROOT/'build/control-v3'));E=ROOT/'evidence/control-v3'/('coupled-'+a.tag);E.mkdir(exist_ok=True)
 src=ROOT/'build/control-v3/sdf/nom_tt_025C_3v30/events.csv';rows=m.read_events(src)
 inputs=B/'inputs';inputs.mkdir();pd=ROOT/'build/layout/pdk/gf180mcuD/libs.tech/ngspice'
 files={'dut.spice':a.netlist,'events.csv':src,'microled.spice':ROOT/'analog/models/microled.spice','design.ngspice':pd/'design.ngspice','sm141064.ngspice':pd/'sm141064.ngspice'}
 for n,p in files.items():shutil.copyfile(p,inputs/n)
 fault=min(float(r['time_ns']) for r in rows if r['fault']=='1' and float(r['time_ns'])>1e5)
 rise=min(float(r['time_ns']) for r in rows if r['raw_pwm']=='1')
 cases=[dict(name='d1',begin=rise-5000,stop=rise+513000),dict(name='fault_stopped_recovery',begin=fault-10000,stop=float(rows[-1]['time_ns'])+5000)]
 def wave(key,begin,stop):
  initial=next(r[key] for r in reversed(rows) if float(r['time_ns'])<=begin and r[key] in ['0','1']);state=int(initial);pts=[(0,state*3.3)]
  for r in rows:
   t=float(r['time_ns']);v=r[key]
   if not begin<t<stop or v not in ['0','1'] or int(v)==state:continue
   pts.extend([((t-begin)*1e-9,state*3.3),((t-begin+10)*1e-9,int(v)*3.3)]);state=int(v)
  pts.append(((stop-begin)*1e-9,state*3.3));assert all(pts[i+1][0]>pts[i][0] for i in range(len(pts)-1))
  return 'PWL(\n'+'\n'.join(f'+ {t:.17g} {v}' for t,v in pts)+'\n+)'
 led_is=100e-6/math.expm1((2.8-100e-6*50)/(3*8.617333262145e-5*300.15))
 def deck(c,dc=False):
  return f'''Routed SDF to complete RC, explicit external passives
.include "{inputs}/design.ngspice"
.param sw_stat_global=0 sw_stat_mismatch=0 LED_IS={led_is}
.lib "{inputs}/sm141064.ngspice" typical
.temp 27
VREF refrail 0 3.3
VSAFE saferail 0 3.3
VBUF bufrail 0 3.3
VLED rail 0 5
VLOAD rail led_anode 0
VSET vset 0 .5
VRAW raw_pwm 0 {'3.3' if dc else wave('raw_pwm',c['begin'],c['stop'])}
VFAULT fault 0 {'0' if dc else wave('fault',c['begin'],c['stop'])}
VPERMIT permit 0 {'3.3' if dc else wave('permit',c['begin'],c['stop'])}
RSET sense 0 5k
RBIAS pb 0 100k
CCOMP n2 ctrl 30p
RRELEASE rail fault_hb 100k
CSENSE sense 0 30p
{f'RBLEED refout 0 {a.bleed_meg}Meg' if a.bleed_meg else '* no bleed'}
.include "{inputs}/dut.spice"
XDUT 0 refrail saferail bufrail rail raw_pwm fault permit vset sense pb n2 ctrl fault_hb led_k refout bias gate pwm_b safe_out pwm_drive startup_test_macro
.include "{inputs}/microled.spice"
XLED led_anode led_k microled
.options reltol=1e-7 abstol=1e-14 vntol=1e-9 method=gear maxord=2
.control
set numdgt=15
set wr_vecnames
set wr_singlescale
save all @d.xled.dled[id] @d.xled.dled[capcur]
{'op' if dc else f'tran 2n {(c["stop"]-c["begin"])*1e-9} 0 2n'}
wrdata waveform.dat i(VLOAD) v(raw_pwm) v(permit) v(fault) v(led_k) v(sense) @d.xled.dled[id] @d.xled.dled[capcur]
quit
.endc
.end
'''
 def simulate(c,dc=False):
  p=B/('dc' if dc else c['name']);p.mkdir();(p/'testbench.spice').write_text(deck(c,dc));r=subprocess.run(['ngspice','-b','testbench.spice'],cwd=p,capture_output=True,text=True);(p/'ngspice.log').write_text(r.stdout+r.stderr);assert r.returncode==0 and 'timestep too small' not in r.stdout+r.stderr,p
  return p,np.loadtxt(p/'waveform.dat',skiprows=1)
 _,dc=simulate(cases[0],True);full=float(dc[1]);results=[]
 for c in cases:
  p,d=simulate(c);t=d[:,0];i=d[:,1]
  if c['name']=='d1':
   lo=(rise-c['begin']-500)*1e-9;hi=lo+512e-6;q=m.integral(t,i,lo,hi);err=100*(q/(full*2e-6)-1);r=dict(name=c['name'],charge_c=q,error_pct=err,passed=abs(err)<2)
  else:
   f=(fault-c['begin'])*1e-9;safe=m.stable_below_time(t,i,f,f+3e-6,1e-9);q=m.split_charge(t,i,f,f+1e-6);recovered=m.integral(t,i,t[-1]-2e-6,t[-1])/2e-6
   r=dict(name=c['name'],fault_to_safe_ns=(safe-f)*1e9 if safe else None,charge=q,recovered_a=recovered,passed=safe is not None and safe-f<1e-6 and q['positive_c']<10e-12 and abs(q['negative_c'])<20e-12 and abs(recovered/100e-6-1)<.05)
  mask=np.ones(len(t),bool) if c['name']!='d1' else ((t>3e-6)&(t<9e-6))|(np.arange(len(t))%100==0)
  np.savetxt(E/(c['name']+'.csv'),d[mask],delimiter=',',header='time_s,current_a,raw_v,permit_v,fault_v,led_k_v,sense_v,led_id_a,led_capcur_a',comments='');results.append(r)
 summary=dict(passed=all(r['passed'] for r in results),full_on_a=full,results=results,raw_directory=str(B.relative_to(ROOT)),inputs={str(p.relative_to(ROOT)):sha(p) for p in files.values()},cc_pf=30,csense_pf=30,bleed_meg=a.bleed_meg,script_sha256=sha(Path(__file__)),scope='Nominal SDF timestamp replay into actual macro full R/C with assumed 10ns pin slew, not full-chip transistor co-simulation')
 (E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
