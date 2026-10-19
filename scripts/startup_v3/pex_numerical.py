"""Numerical/gmin sensitivity for a frozen physical macro deck; never alters DUT.

Default uses existing r5 TT CC30 deck for 200ns screening. Parameterized base
allows later final decks. Includes source hashes, direct logs and failed solves.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse,importlib.util,json,re,subprocess,itertools
import numpy as np
R=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('refine',R/'scripts/startup_v3/refine.py');F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)
VECTORS=['i(VLEDLOAD)','v(bias)','v(led_k)','v(refrail)','v(refout)','@d.xled.dled[id]','@d.xled.dled[capcur]']
def main():
 p=argparse.ArgumentParser();p.add_argument('--base-deck',type=Path,default=R/'build/analog-v3/pex-r5-cc30-vns1xvvi/startup_tt_100/testbench.spice');p.add_argument('--tag',default='pex-r5-gmin-screen');p.add_argument('--stop-ns',type=int,default=200);p.add_argument('--wide',action='store_true');p.add_argument('--gear1',action='store_true');p.add_argument('--reuse',action='store_true');a=p.parse_args()
 src=a.base_deck.resolve();base=src.read_text();w=R/'build/startup-v3/numerical'/a.tag;d=R/'evidence/startup-v3/numerical'/a.tag;w.mkdir(exist_ok=True,parents=True);d.mkdir(exist_ok=True,parents=True)
 cases=[(order,gmin) for order in ([1,2] if a.gear1 else [2]) for gmin in ['1e-14','1e-12','1e-10']]
 def run(c):
  order,gmin=c;name=f'gear{order}_gmin{gmin}';target=w/name;target.mkdir(exist_ok=True);source,ticks=F.ramp(2)
  deck=base.replace('PWL(0 0 100n 3.3)',source);deck=re.sub(r'(?m)^tran .*$',f'tran .001n {a.stop_ns}n 0 2n',deck)
  options=f'.options reltol={"1e-8" if a.wide else "1e-7"} abstol={"1e-12" if a.wide else "1e-14"} vntol={"1e-7" if a.wide else "1e-9"} method=gear maxord={order} gmin={gmin}'
  deck=re.sub(r'(?m)^.options .*$',options,deck);deck=re.sub(r'(?m)^save all.*$','save '+' '.join(VECTORS),deck);deck=re.sub(r'(?m)^wrdata waveform.dat.*$','wrdata waveform.dat '+' '.join(VECTORS),deck)
  reused=a.reuse and (target/'testbench.spice').exists() and (target/'testbench.spice').read_text()==deck and (target/'ngspice.log').exists();(target/'testbench.spice').write_text(deck)
  code=None
  if not reused:
   try:
    result=subprocess.run(['ngspice','-b','testbench.spice'],cwd=target,text=True,capture_output=True,timeout=180);log=result.stdout+result.stderr;code=result.returncode
   except subprocess.TimeoutExpired as e:
    def txt(v):return v.decode(errors='replace') if isinstance(v,bytes) else (v or '')
    log=txt(e.stdout)+txt(e.stderr)+'\nNUMERICAL_RUN_TIMEOUT_180S\n';code=-1
   (target/'ngspice.log').write_text(log)
  log=(target/'ngspice.log').read_text();failed=re.search(r'(?im)^Error:.*|.*Timestep too small.*|NUMERICAL_RUN_TIMEOUT_180S',log)
  row=dict(name=name,order=order,gmin_s=float(gmin),options=options,stop_ns=a.stop_ns,local_mesh_ps=.2,solver_completed=not bool(failed) and code in [0,None],exit_code=code,raw_directory=str(target.relative_to(R)),deck_sha256=F.M.sha(target/'testbench.spice'),log_sha256=F.M.sha(target/'ngspice.log'),transient_op_fallback='Transient op started' in log,operating_point_path='transient_op_fallback' if 'Transient op started' in log else 'ordinary_dc_op')
  if not row['solver_completed']:row['failure']=failed.group() if failed else 'nonzero process exit'
  else:
   path=target/'waveform.dat';data=np.loadtxt(path,skiprows=1);t=data[:,0];i=data[:,1];right=a.stop_ns*1e-9
   row.update(points=len(t),branch_peak_a=float(np.abs(i).max()),branch_positive_peak_a=float(i.max()),branch_negative_peak_a=float(i.min()),branch_charge=F.M.split_linear(t,i,0,right),branch_1nA_peak_passed=bool(np.abs(i).max()<1e-9),refout_initial_v=float(data[0,5]),refout_final_v=float(data[-1,5]),raw_sha256=F.M.sha(path))
   mask=np.unique(np.r_[np.flatnonzero(t<=.02e-9),np.flatnonzero((t>=99.98e-9)&(t<=100.03e-9)),np.arange(0,len(t),max(1,len(t)//1500)),len(t)-1]);out=d/(name+'.csv');np.savetxt(out,data[mask],delimiter=',',header='time_s,'+','.join(VECTORS),comments='',fmt='%.16e');row['compact_csv_sha256']=F.M.sha(out)
  (target/'result.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row),flush=True);return row
 with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(run,cases))
 summary=dict(date='2026-10-15',tag=a.tag,base_deck=str(src.relative_to(R)),base_deck_sha256=F.M.sha(src),dut_sha256=F.M.sha(src.parent.parent/'inputs/dut.spice'),script_sha256=F.M.sha(Path(__file__)),stop_ns=a.stop_ns,wide_solver=a.wide,results=rows,all_solvers_completed=all(r['solver_completed'] for r in rows),peak_guard_passed=all(r.get('branch_1nA_peak_passed',False) for r in rows),scope='200ns screens only initial corner, not full 20us startup or recovery; gmin is numerical conductance, not a physical bleed transistor.' if a.stop_ns==200 else 'Numerical gmin sensitivity; circuit/model unchanged; recovery depends on window and explicit source signals.')
 (d/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 return 0 if summary['all_solvers_completed'] and summary['peak_guard_passed'] else 2
if __name__=='__main__':raise SystemExit(main())
