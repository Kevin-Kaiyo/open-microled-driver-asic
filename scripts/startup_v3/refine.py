"""Local numerical mesh refinement of exactly the same reference ramp.

Collinear PWL knots force solver breakpoints around 0ns and100ns. No passive,
MOS parameter, model, power slope or circuit connection is changed. All mesh
and method/tolerance controls are retained; comparisons use full raw data.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from decimal import Decimal
import argparse,csv,hashlib,importlib.util,json,re,subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('numeric',ROOT/'scripts/startup_v3/numerical.py');M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
WORK=ROOT/'build/startup-v3/numerical/localmesh-final';DEST=ROOT/'evidence/startup-v3/numerical'
CONTRACT_PATH=ROOT/'scripts/startup_v3/numerical_contract.json';CONTRACT=json.loads(CONTRACT_PATH.read_text())
SRC=M.FROZEN/'startup_tt_ramp100ns';BASE=(SRC/'testbench.spice').read_text()
VECTORS=['i(VLEDLOAD)','v(bias)','v(led_k)','v(refrail)','@d.xled.dled[id]','@d.xled.dled[capcur]']
def ramp(mesh_ticks):
 # Time unit is 0.0001ns; integer ticks avoid near-duplicate breakpoint times.
 ticks=sorted(set([0,1000000,200000000]+list(range(0,10001,mesh_ticks))+list(range(990000,1020001,mesh_ticks))))
 pairs=[]
 for k in ticks:
  t=Decimal(k)/Decimal(10000);v=min(t/Decimal(100),Decimal(1))*Decimal('3.3');pairs.append((str(t)+'n',str(v)))
 return 'PWL('+' '.join(' '.join(p) for p in pairs)+')',ticks

def run(c,reuse=False):
 order,mesh,step,rel=c;name=f'gear{order}_mesh{mesh}tick_s{step}_r{rel}';d=WORK/name;d.mkdir(parents=True,exist_ok=True)
 for fn in ['design.ngspice','sm141064.ngspice']:
  if not (d/fn).exists():(d/fn).symlink_to((SRC/fn).resolve())
 source,ticks=ramp(mesh);deck=BASE.replace('PWL(0 0 100n 3.3)',source).replace('tran 10n 40000n 0 10n',f'tran 0.001n 20000n 0 {step}n')
 deck=deck.replace('option '+M.BASE,f'option reltol={rel} abstol=1e-12 vntol=1e-7 method=gear maxord={order}')
 deck=re.sub(r'(?m)^save all.*$', 'save '+' '.join(VECTORS),deck);deck=re.sub(r'(?m)^wrdata waveform.dat.*$', 'wrdata waveform.dat '+' '.join(VECTORS),deck)
 reused=reuse and (d/'testbench.spice').exists() and (d/'testbench.spice').read_text()==deck and (d/'ngspice.log').exists()
 (d/'testbench.spice').write_text(deck)
 if not reused:
  try:p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=d,text=True,capture_output=True,timeout=240);log=p.stdout+p.stderr
  except subprocess.TimeoutExpired as e:log='NUMERICAL_RUN_TIMEOUT\n'+str(e)
  (d/'ngspice.log').write_text(log)
 log=(d/'ngspice.log').read_text();failure=re.search(r'(?im)^Error:.*|.*Timestep too small.*|NUMERICAL_RUN_TIMEOUT',log)
 result=dict(name=name,order=order,local_mesh_ps=mesh*.1,maxstep_ns=step,reltol=float(rel),tstep_ns=.001,solver_completed=not bool(failure),breakpoint_count=len(ticks),deck_sha256=M.sha(d/'testbench.spice'),log_sha256=M.sha(d/'ngspice.log'),raw_directory=str(d.relative_to(ROOT)),reference_ramp_unchanged=True)
 if failure:result['failure']=failure.group()
 else:
  path=d/'waveform.dat';a=np.loadtxt(path,skiprows=1);result.update(M.measures(a[:,0],a[:,1]));result['raw_sha256']=M.sha(path)
  actual_ref=a[:,4];expected=np.minimum(a[:,0]/100e-9,1)*3.3;result['max_reference_source_function_error_v']=float(np.abs(actual_ref-expected).max())
  # Preserve dense corner windows; full raw remains under build for every metric.
  t=a[:,0];sel=np.unique(np.r_[np.flatnonzero(t<=.02e-9),np.flatnonzero((t>=99.98e-9)&(t<=100.03e-9)),np.arange(0,len(t),max(1,len(t)//1500)),len(t)-1])
  target=DEST/'refined-waveforms';target.mkdir(exist_ok=True,parents=True);csvpath=target/(name+'.csv')
  np.savetxt(csvpath,a[sel],delimiter=',',header='time_s,'+','.join(VECTORS),comments='',fmt='%.16e');result['compact_csv_path']=str(csvpath.relative_to(ROOT));result['compact_csv_sha256']=M.sha(csvpath)
 (d/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(name,result.get('branch_peak_a',result.get('failure')),flush=True);return result

def compare(a,b,arrays):
 x,y=arrays[a['name']],arrays[b['name']];t=np.unique(np.r_[x[:,0],y[:,0]]);diff=np.interp(t,x[:,0],x[:,1])-np.interp(t,y[:,0],y[:,1]);idx=int(np.abs(diff).argmax());di=float(abs(diff[idx]));charges={}
 for key in ['signed_c','positive_c','negative_c']:
  qa,qb=a['charge'][key],b['charge'][key];delta=abs(qb-qa);relative=abs(qb/qa-1) if qa else None;near=max(abs(qa),abs(qb))<=CONTRACT['charge_switch_scale_c']
  passed=delta<=CONTRACT['absolute_charge_difference_limit_c'] and di<=CONTRACT['absolute_current_difference_limit_a'] if near else relative is not None and relative<=CONTRACT['legacy_relative_limit_fraction']
  charges[key]=dict(a_c=qa,b_c=qb,absolute_difference_c=delta,relative_difference_fraction=relative,branch='near_zero_absolute' if near else 'resolved_relative',passed=bool(passed))
 return dict(a=a['name'],b=b['name'],maximum_current_difference_a=di,maximum_difference_time_s=float(t[idx]),charge_comparisons=charges,passed=all(q['passed'] for q in charges.values()))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--reuse',action='store_true');args=ap.parse_args();DEST.mkdir(exist_ok=True,parents=True)
 cases=[(o,m,s,'1e-8') for o in [1,2] for m in [10,2,1] for s in [10,2]]+[(o,1,2,'1e-7') for o in [1,2]]
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda c:run(c,args.reuse),cases))
 arrays={r['name']:np.loadtxt(WORK/r['name']/'waveform.dat',skiprows=1,usecols=[0,1]) for r in results if r['solver_completed']}
 allpairs=[compare(a,b,arrays) for a,b in combinations([r for r in results if r['solver_completed']],2)]
 selected=[r for r in results if r['local_mesh_ps']<=.2];selnames={r['name'] for r in selected};pairs=[p for p in allpairs if p['a'] in selnames and p['b'] in selnames]
 passed=len(selected)==10 and all(r['solver_completed'] and r['branch_1nA_peak_passed'] and r['max_reference_source_function_error_v']<1e-12 for r in selected) and all(p['passed'] for p in pairs)
 summary=dict(schema_version=1,date='2026-10-15',criterion_revision=CONTRACT['criterion_revision'],contract=CONTRACT,contract_sha256=M.sha(CONTRACT_PATH),script_sha256=M.sha(Path(__file__)),frozen_source_summary_sha256=M.sha(M.OLD),physical_changes='none; collinear PWL breakpoints only',runs=len(results),selected_comparison_runs=len(selected),selected_pairwise_comparisons=len(pairs),legacy_4p909pct_result_passed=False,revised_numerical_acceptance_passed=bool(passed),selected_maximum_current_difference_a=max(p['maximum_current_difference_a'] for p in pairs),selected_maximum_charge_difference_c=max(q['absolute_difference_c'] for p in pairs for q in p['charge_comparisons'].values()),results=results,selected_comparisons=pairs,all_comparisons=allpairs,selection_rule='Two finest local meshes 0.2ps/0.1ps, both Gear1/Gear2 and TMAX10ns/2ns; 1e-7 tolerance controls included. 1ps retained as coarse refinement controls, not deleted.',scope='Only frozen startup-v2 circuit and valid logic/LED/external-fault startup envelope; not new physical layout or arbitrary rail sequencing.')
 (DEST/'refined-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:summary[k] for k in ['runs','selected_pairwise_comparisons','revised_numerical_acceptance_passed','selected_maximum_current_difference_a','selected_maximum_charge_difference_c']}))
 return 0 if passed else 2
if __name__=='__main__':raise SystemExit(main())
