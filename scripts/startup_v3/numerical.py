"""Reproduce startup numerical diagnostics without changing a physical device.

Legacy 0.2% relative-Q+ status is retained. A two-point pass is not promoted to
convergence if method/tolerance/refinement controls disagree. Raw failures stay
under build; evidence contains hashes, compact current samples, and all results.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse, hashlib, importlib.util, json, re, subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'evidence/startup-v2/summary.json'
FROZEN=ROOT/json.loads(OLD.read_text())['raw_directory']
WORK=ROOT/'build/startup-v3/numerical'
DEST=ROOT/'evidence/startup-v3/numerical'
SPEC=importlib.util.spec_from_file_location('safety',ROOT/'scripts/safety/run.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
BASE='reltol=1e-6 abstol=1e-12 vntol=1e-7 method=gear maxord=2'
PROFILES={
 'base':BASE,
 'tight':'reltol=1e-8 abstol=1e-17 vntol=1e-12 method=gear maxord=2 chgtol=1e-22',
 'tighttrap':'reltol=1e-8 abstol=1e-17 vntol=1e-12 method=trap maxord=2 chgtol=1e-22',
 'medium':'reltol=1e-7 abstol=1e-15 vntol=1e-10 method=gear maxord=2 chgtol=1e-20',
 'gear1':'reltol=1e-8 abstol=1e-17 vntol=1e-12 method=gear maxord=1 chgtol=1e-22',
 'fine':BASE,
 'chg':BASE+' chgtol=1e-20',
 'volt':BASE.replace('vntol=1e-7','vntol=1e-9'),
 'amp':BASE.replace('abstol=1e-12','abstol=1e-15'),
 'rel':BASE.replace('reltol=1e-6','reltol=1e-8'),
 'moderate':'reltol=1e-7 abstol=1e-13 vntol=1e-8 method=gear maxord=2',
 'klu':'reltol=1e-7 abstol=1e-13 vntol=1e-8 method=gear maxord=2 klu',
 'trap':BASE.replace('method=gear','method=trap'),
 'be':BASE.replace('maxord=2','maxord=1'),
 'be_more':BASE.replace('maxord=2','maxord=1'),
 'klutight':'reltol=1e-8 abstol=1e-17 vntol=1e-12 method=gear maxord=2 chgtol=1e-22 klu',
 'klurel':BASE.replace('reltol=1e-6','reltol=1e-8')+' klu',
 'chglight':BASE.replace('reltol=1e-6','reltol=1e-8')+' chgtol=1e-22',
 'trtol1':BASE+' trtol=1',
 'tinychg':BASE+' chgtol=1e-24',
 'be_tight':'reltol=1e-8 abstol=1e-13 vntol=1e-8 method=gear maxord=1',
 'startsmall':BASE,
 'startstrict':'reltol=1e-8 abstol=1e-17 vntol=1e-12 method=gear maxord=2 chgtol=1e-22',
 'startmedium':'reltol=1e-7 abstol=1e-15 vntol=1e-10 method=gear maxord=2 chgtol=1e-20',
 'startklurel':BASE.replace('reltol=1e-6','reltol=1e-8')+' klu',
 'startbe':'reltol=1e-8 abstol=1e-13 vntol=1e-8 method=gear maxord=1',
 'negative_control':BASE,
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def split_linear(t,y,left,right):
 """Independent analytic triangle/trapezoid integration; no thresholding."""
 x,v=M.clip(t,y,left,right);a,b=v[:-1],v[1:];dt=np.diff(x)
 p=np.zeros(len(dt));n=p.copy();pos=(a>=0)&(b>=0);neg=(a<=0)&(b<=0)
 p[pos]=dt[pos]*(a[pos]+b[pos])/2;n[neg]=dt[neg]*(a[neg]+b[neg])/2
 cross=a*b<0;up=cross&(b>0);dn=cross&(a>0)
 p[up]=dt[up]*b[up]**2/(2*(b[up]-a[up]));n[up]=-dt[up]*a[up]**2/(2*(b[up]-a[up]))
 p[dn]=dt[dn]*a[dn]**2/(2*(a[dn]-b[dn]));n[dn]=-dt[dn]*b[dn]**2/(2*(a[dn]-b[dn]))
 return dict(signed_c=float(np.sum(dt*(a+b)/2)),positive_c=float(p.sum()),negative_c=float(n.sum()))
def measures(t,i):
 return dict(points=len(t),branch_peak_a=float(np.abs(i).max()),branch_max_a=float(i.max()),branch_min_a=float(i.min()),charge=split_linear(t,i,0,20e-6),
  early_charge=split_linear(t,i,0,100e-9),late_charge=split_linear(t,i,1e-6,20e-6),
  legacy_algorithm_charge=M.split_charge(t,i,0,20e-6),branch_1nA_peak_passed=bool(np.abs(i).max()<1e-9))
def load(name):
 p=WORK/name/'waveform.dat';a=np.loadtxt(p,skiprows=1);header=p.open().readline().split();return a[:,0],a[:,header.index('i(VLEDLOAD)')]
def run_case(case,reuse):
 profile,step=case;name=f'{profile}_{step}ns';folder=WORK/name;folder.mkdir(parents=True,exist_ok=True)
 source='baseline_matched_finite_gear' if profile=='negative_control' else 'startup_tt_ramp100ns'
 src=FROZEN/source;deck=(src/'testbench.spice').read_text()
 deck=deck.replace('tran 10n 40000n 0 10n',f'tran {"0.01" if profile.startswith("start") else "10"}n 20000n 0 {step}n')
 deck=deck.replace('option '+BASE,'option '+PROFILES[profile])
 for fn in ['design.ngspice','sm141064.ngspice']:
  if not (folder/fn).exists():(folder/fn).symlink_to((src/fn).resolve())
 reuse_ok=reuse and (folder/'testbench.spice').exists() and (folder/'testbench.spice').read_text()==deck and (folder/'ngspice.log').exists()
 (folder/'testbench.spice').write_text(deck)
 if not reuse_ok:
  try:
   p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,text=True,capture_output=True,timeout=180)
   (folder/'ngspice.log').write_text(p.stdout+p.stderr)
  except subprocess.TimeoutExpired as e:
   text=(e.stdout or b'')+(e.stderr or b'')
   if isinstance(text,bytes):text=text.decode(errors='replace')
   (folder/'ngspice.log').write_text(text+'\nNUMERICAL_RUN_TIMEOUT\n')
 log=(folder/'ngspice.log').read_text();failure=re.search(r'(?im)^Error:.*|.*Timestep too small.*|.*simulation.*aborted.*|NUMERICAL_RUN_TIMEOUT',log)
 out=dict(name=name,profile=profile,maxstep_ns=step,tstep_ns=.01 if profile.startswith('start') else 10,options=PROFILES[profile],negative_control=profile=='negative_control',raw_directory=str(folder.relative_to(ROOT)),deck_sha256=sha(folder/'testbench.spice'),log_sha256=sha(folder/'ngspice.log'),solver_completed=not bool(failure))
 if failure:out['failure']=failure.group().strip()
 else:
  t,i=load(name);out.update(measures(t,i));out['waveform_sha256']=sha(folder/'waveform.dat')
  target=DEST/'waveforms';target.mkdir(exist_ok=True,parents=True)
  sel=np.unique(np.r_[np.flatnonzero(t<=1e-6),np.arange(0,len(t),max(1,len(t)//1200)),len(t)-1])
  compact=target/(name+'.csv');np.savetxt(compact,np.c_[t[sel],i[sel]],delimiter=',',header='time_s,led_branch_current_a',comments='',fmt='%.16e');out['compact_csv_sha256']=sha(compact);out['compact_csv_scope']='All first-us samples; decimated late samples. Metrics use full raw waveform.'
 print(name,'complete' if out['solver_completed'] else 'FAILED',flush=True)
 return out

def compare(a,b):
 ta,ia=load(a['name']);tb,ib=load(b['name']);t=np.unique(np.r_[ta,tb]);d=np.interp(t,ta,ia)-np.interp(t,tb,ib)
 q1=a['charge']['positive_c'];q2=b['charge']['positive_c'];change=abs(q2/q1-1)*100 if q1 else None
 return dict(coarse=a['name'],fine=b['name'],q_positive_change_pct=change,legacy_limit_pct=.2,legacy_relative_passed=change is not None and change<=.2,absolute_positive_difference_c=abs(q2-q1),waveform_max_difference_a=float(np.abs(d).max()),waveform_l1_difference_c=split_linear(t,d,0,20e-6)['positive_c']-split_linear(t,d,0,20e-6)['negative_c'])

def dc_run(name):
 src=FROZEN/name;folder=WORK/name;folder.mkdir(exist_ok=True)
 for fn in ['design.ngspice','sm141064.ngspice']:
  if not (folder/fn).exists():(folder/fn).symlink_to((src/fn).resolve())
 (folder/'testbench.spice').write_text((src/'testbench.spice').read_text())
 p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=folder,text=True,capture_output=True);(folder/'ngspice.log').write_text(p.stdout+p.stderr)
 if p.returncode or 'Error:' in p.stderr:raise RuntimeError(str(folder))
 path=folder/'waveform.dat';a=np.atleast_2d(np.loadtxt(path,skiprows=1));head=path.open().readline().split();current=float(a[0,head.index('i(VLEDLOAD)')]);on=name.endswith('_1')
 return dict(name=name,branch_current_a=current,within_5pct_on_or_1nA_off=abs(current/100e-6-1)<.05 if on else abs(current)<1e-9,deck_sha256=sha(folder/'testbench.spice'),waveform_sha256=sha(path),log_sha256=sha(folder/'ngspice.log'))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--reuse',action='store_true');args=ap.parse_args();WORK.mkdir(parents=True,exist_ok=True);DEST.mkdir(parents=True,exist_ok=True)
 old=json.loads(OLD.read_text());old_hash=sha(OLD)
 for path,h in old['source_sha256'].items():
  p=FROZEN/'inputs'/path
  if sha(p)!=h:raise RuntimeError('Frozen input changed '+path)
 analytic=split_linear(np.array([0.,2.]),np.array([3.,-1.]),0,2)
 if analytic!={'signed_c':2.,'positive_c':2.25,'negative_c':-.25}:raise RuntimeError('Analytic triangle integration failed')
 cases=[(p,s) for p in PROFILES for s in ([.5,.1] if p in ['fine','be_more'] else [10,2])]
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda c:run_case(c,args.reuse),cases))
 look={r['name']:r for r in results};pairs=[]
 for p in PROFILES:
  ss=[.5,.1] if p in ['fine','be_more'] else [10,2];a,b=[look[f'{p}_{s}ns'] for s in ss]
  if a['solver_completed'] and b['solver_completed']:pairs.append(compare(a,b))
 for p,q in [('base_2ns','fine_0.5ns'),('be_2ns','be_more_0.5ns'),('base_10ns','be_10ns'),('base_10ns','moderate_10ns'),('base_10ns','startsmall_10ns')]:pairs.append(compare(look[p],look[q]))
 dcs=[dc_run(f'dc_{e}_True_True_{l}') for e in ['tt','ss','ff'] for l in [0,1]]
 checks=[dict(name='Independent analytic integration oracle',passed=True),dict(name='Old summary bytes unchanged',passed=sha(OLD)==old_hash),dict(name='DC calibration',passed=all(d['within_5pct_on_or_1nA_off'] for d in dcs)),dict(name='All successful isolated trials below 1nA',passed=all(r['branch_1nA_peak_passed'] for r in results if r['solver_completed'] and not r['negative_control'])),dict(name='Matched non-isolated negative controls fail 1nA',passed=all(not r['branch_1nA_peak_passed'] for r in results if r['solver_completed'] and r['negative_control'])),dict(name='Zero crossing integration independently agrees',passed=all(max(abs(r['charge'][k]-r['legacy_algorithm_charge'][k]) for k in r['charge'])<1e-28 for r in results if r['solver_completed']))]
 summary=dict(schema_version=1,date='2026-10-15',stage='numerical diagnostics of unchanged startup-v2 physical netlist',source_summary_sha256=old_hash,source_manifest=old['source_sha256'],script_sha256=sha(Path(__file__)),ngspice_version=subprocess.run(['ngspice','--version'],text=True,capture_output=True).stdout,window_s=[0,20e-6],branch_source='i(VLEDLOAD)',physical_changes='none',legacy_relative_limit_pct=.2,legacy_relative_passed=False,strict_numerical_convergence_resolved=False,diagnostic_checks_passed=all(c['passed'] for c in checks),simulation_runs=len(results),solver_completed_runs=sum(r['solver_completed'] for r in results),solver_failed_runs=sum(not r['solver_completed'] for r in results),dc_results=dcs,checks=checks,results=results,comparisons=pairs,findings=['Legacy splitter already inserts zero crossings; independent analytic triangles agree.','Near-zero Q+ is unstable under integration order, tolerance, initial time step, and fine step controls. Do not select a passing two-point pair.','TRAP shows numerical sign-alternating ringing; Gear2 controls reduce it but do not establish strict relative Q+ convergence.','Tight tolerances cause actual timestep failures; all failure logs preserved.','Peak guard is robust for successful isolated trials; negative-control circuit fails guard. This does not upgrade strict convergence.'],proposed_measurement_contract={'status':'proposal_only_not_original_gate','absolute_current_error_budget_a':2e-12,'derivation':'0.2% of existing 1nA off-current peak limit','absolute_charge_error_budget_c':4e-17,'derivation_charge':'2pA times unchanged 20us observation window','condition':'Require both max waveform difference and charge difference across refinement/method controls; keep legacy status alongside. No clipping, zero replacement, or sensor-resolution claim.'})
 (DEST/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(DEST/'failure-ledger.json').write_text(json.dumps([r for r in results if not r['solver_completed']],indent=2)+'\n');print(json.dumps({k:summary[k] for k in ['simulation_runs','solver_completed_runs','solver_failed_runs','diagnostic_checks_passed','strict_numerical_convergence_resolved']}))
 return 2 if not summary['strict_numerical_convergence_resolved'] else 0
if __name__=='__main__':raise SystemExit(main())
