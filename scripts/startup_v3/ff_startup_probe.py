"""Retain an observed new-PEX FF startup failure and test the initial corner.
20ns screening is explicitly incomplete; it cannot establish whole startup pass.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import argparse,importlib.util,json,re,subprocess,itertools
import numpy as np
R=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('refine',R/'scripts/startup_v3/refine.py');F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)
VECTORS=['i(VLEDLOAD)','v(led_k)','v(bias)','v(refout)','v(sense)','v(n2)','v(ctrl)','v(refrail)','v(safe_out)','v(pwm_drive)','v(gate)','@d.xled.dled[id]','@d.xled.dled[capcur]']
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--base-deck',type=Path,default=R/'build/analog-v3/pex-r5-bleed10M-fftrial-x718575b/startup_ff_100/testbench.spice');ap.add_argument('--tag',default='pex-r5-bleed10M-ff-probe');ap.add_argument('--reuse',action='store_true');a=ap.parse_args();src=a.base_deck.resolve();base=src.read_text();w=R/'build/startup-v3/numerical'/a.tag;d=R/'evidence/startup-v3/numerical'/a.tag;w.mkdir(exist_ok=True,parents=True);d.mkdir(exist_ok=True,parents=True)
 original=next(l for l in base.splitlines() if l.startswith('VREFRAIL '));vfinal=Decimal(original.split()[-1].rstrip(')'))
 cases=[(1,2,'1e-12','standard'),(1,1,'1e-12','standard'),(2,2,'1e-12','standard'),(2,1,'1e-12','standard'),(2,1,'1e-14','standard'),(2,1,'1e-10','standard'),(2,1,'1e-12','tight'),(2,1,'1e-12','wide'),(1,.5,'1e-12','standard'),(2,.5,'1e-12','standard')]
 def run(c):
  order,mesh,gmin,profile=c;name=f'gear{order}_mesh{mesh}tick_gmin{gmin}_{profile}';target=w/name;target.mkdir(exist_ok=True)
  ticks=sorted(set([0,2000000]+list(range(0,20001,int(mesh*2)))));points=[]
  for tick in ticks:
   ns=Decimal(tick)/20000;v=min(ns/100,Decimal(1))*vfinal;points.extend([str(ns)+'n',str(v)])
  source='VREFRAIL refrail 0 PWL('+' '.join(points)+')';deck=base.replace(original,source);deck=re.sub(r'(?m)^tran .*$', 'tran .001n 20n 0 .01n',deck)
  opts={'standard':('1e-7','1e-14','1e-9'),'tight':('1e-9','1e-16','1e-11'),'wide':('1e-8','1e-12','1e-7')}[profile]
  options=f'.options reltol={opts[0]} abstol={opts[1]} vntol={opts[2]} method=gear maxord={order} gmin={gmin} itl1=500'
  deck=re.sub(r'(?m)^.options .*$',options,deck);deck=re.sub(r'(?m)^save all.*$','save '+' '.join(VECTORS),deck);deck=re.sub(r'(?m)^wrdata waveform.dat.*$','wrdata waveform.dat '+' '.join(VECTORS),deck)
  reused=a.reuse and (target/'testbench.spice').exists() and (target/'testbench.spice').read_text()==deck and (target/'ngspice.log').exists() and (target/'result.json').exists()
  (target/'testbench.spice').write_text(deck)
  try:
   if reused:
    log=(target/'ngspice.log').read_text();code=json.loads((target/'result.json').read_text())['exit_code']
   else:
    p=subprocess.run(['ngspice','-b','testbench.spice'],cwd=target,text=True,capture_output=True,timeout=150);log=p.stdout+p.stderr;code=p.returncode
  except subprocess.TimeoutExpired as e:
   def txt(v):return v.decode(errors='replace') if isinstance(v,bytes) else (v or '')
   log=txt(e.stdout)+txt(e.stderr)+'\nRUN_TIMEOUT_150S\n';code=-1
  (target/'ngspice.log').write_text(log);failed=re.search(r'(?im)^Error:.*|.*Timestep too small.*|RUN_TIMEOUT_150S',log)
  row=dict(name=name,order=order,mesh_ps=mesh*.1,gmin_s=float(gmin),profile=profile,options=options,solver_completed=code==0 and not bool(failed),exit_code=code,deck_sha256=F.M.sha(target/'testbench.spice'),log_sha256=F.M.sha(target/'ngspice.log'),raw_directory=str(target.relative_to(R)),transient_op_fallback='Transient op started' in log,operating_point_path='transient_op_fallback' if 'Transient op started' in log else 'ordinary_dc_op')
  if not row['solver_completed']:row['failure']=failed.group() if failed else 'nonzero exit'
  else:
   p=target/'waveform.dat';data=np.loadtxt(p,skiprows=1);t=data[:,0];i=data[:,1];k=int(np.abs(i).argmax());cond=data[:,12]-data[:,13]
   row.update(points=len(t),peak_a=float(abs(i[k])),peak_signed_a=float(i[k]),peak_time_s=float(t[k]),charge=F.M.split_linear(t,i,0,20e-9),first_10ps_charge=F.M.split_linear(t,i,0,10e-12),passed_1nA=bool(abs(i[k])<1e-9),conduction_peak_a=float(np.abs(cond).max()),initial={name:float(data[0,j+1]) for j,name in enumerate(VECTORS)},raw_sha256=F.M.sha(p))
   sel=np.unique(np.r_[np.flatnonzero(t<20e-12),np.arange(0,len(t),max(1,len(t)//2000)),len(t)-1]);cp=d/(name+'.csv');np.savetxt(cp,data[sel],delimiter=',',header='time_s,'+','.join(VECTORS),comments='',fmt='%.16e');row['compact_csv_sha256']=F.M.sha(cp)
  (target/'result.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row),flush=True);return row
 with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(run,cases))
 comparisons=[]
 valid=[r for r in rows if r['solver_completed']]
 arrays={r['name']:np.loadtxt(R/r['raw_directory']/'waveform.dat',skiprows=1,usecols=[0,1]) for r in valid}
 for x,y in itertools.combinations(valid,2):
  xa,ya=arrays[x['name']],arrays[y['name']];ts=np.unique(np.r_[xa[:,0],ya[:,0]]);delta=np.interp(ts,xa[:,0],xa[:,1])-np.interp(ts,ya[:,0],ya[:,1]);k=int(np.abs(delta).argmax());di=float(abs(delta[k]));dq=max(abs(x['charge'][q]-y['charge'][q]) for q in ['signed_c','positive_c','negative_c'])
  sameop=x['gmin_s']==y['gmin_s'] and not x['transient_op_fallback'] and not y['transient_op_fallback']
  comparisons.append(dict(a=x['name'],b=y['name'],current_max_difference_a=di,current_max_difference_time_s=float(ts[k]),charge_max_difference_c=dq,absolute_current_limit_a=2e-12,absolute_charge_limit_c=4e-20,same_op_numerical_control=sameop,revised_short_window_passed=di<=2e-12 and dq<=4e-20))
 selected={r['name'] for r in valid if r['mesh_ps']<=.1 and r['gmin_s']==1e-12 and r['profile'] in ['standard','wide'] and not r['transient_op_fallback']}
 selected_comparisons=[c for c in comparisons if c['a'] in selected and c['b'] in selected]
 summary=dict(date='2026-10-15',tag=a.tag,source_deck=str(src.relative_to(R)),source_deck_sha256=F.M.sha(src),dut_sha256=F.M.sha(src.parent.parent/'inputs/dut.spice'),script_sha256=F.M.sha(Path(__file__)),window_s=[0,20e-9],results=rows,all_comparisons=comparisons,selected_comparisons=selected_comparisons,selected_controls=sorted(selected),selected_numerical_acceptance_passed=len(selected)==5 and all(c['revised_short_window_passed'] for c in selected_comparisons),scope='Initial FF corner screening only; no full20us startup/recovery pass. All physical circuit/device/source-ramp data preserved.',all_completed=all(r['solver_completed'] for r in rows),all_1nA_passed=all(r.get('passed_1nA',False) for r in rows))
 (d/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return 0 if summary['all_completed'] and summary['all_1nA_passed'] else 2
if __name__=='__main__':raise SystemExit(main())
