"""Read-only independent audit of numerical evidence; writes audit receipt only."""
from pathlib import Path
import json,hashlib,re,itertools
import numpy as np
R=Path(__file__).resolve().parents[2];D=R/'evidence/startup-v3/numerical';W=R/'build/startup-v3/numerical/localmesh-final'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
s=json.loads((D/'refined-summary.json').read_text());scan=json.loads((D/'summary.json').read_text());old=json.loads((R/'evidence/startup-v2/summary.json').read_text());checks=[]
def ck(name,value):checks.append(dict(name=name,passed=bool(value)))
ck('Old failure remains recorded',not old['legacy_startup_relative_convergence_passed'] and not s['legacy_4p909pct_result_passed'])
ck('Old summary hash matches',sha(R/'evidence/startup-v2/summary.json')==s['frozen_source_summary_sha256']==scan['source_summary_sha256'])
ck('Criterion SHA matches',sha(R/'scripts/startup_v3/numerical_contract.json')==s['contract_sha256'])
ck('Refinement script SHA matches',sha(R/'scripts/startup_v3/refine.py')==s['script_sha256'])
ck('Scan script SHA matches',sha(R/'scripts/startup_v3/numerical.py')==scan['script_sha256'])
ck('Claimed full scan counts',scan['simulation_runs']==54 and scan['solver_completed_runs']==40 and scan['solver_failed_runs']==14)
for row in scan['results']:
 p=R/row['raw_directory'];ck(row['name']+' deck bytes',sha(p/'testbench.spice')==row['deck_sha256']);ck(row['name']+' log bytes',sha(p/'ngspice.log')==row['log_sha256'])
 if row['solver_completed']:ck(row['name']+' full raw bytes',sha(p/'waveform.dat')==row['waveform_sha256'])
 else:ck(row['name']+' solver failure explicit',bool(re.search(r'timestep too small', (p/'ngspice.log').read_text(),re.I)))

def independently_integrate(t,y):
 roots=[]
 for j in np.flatnonzero(y[:-1]*y[1:]<0):roots.append(t[j]+(t[j+1]-t[j])*(-y[j])/(y[j+1]-y[j]))
 xx=np.unique(np.r_[t,roots]);yy=np.interp(xx,t,y);areas=np.diff(xx)*(yy[:-1]+yy[1:])/2
 return {'signed_c':float(areas.sum()),'positive_c':float(areas[areas>0].sum()),'negative_c':float(areas[areas<0].sum())}
arrays={};rows={}
for row in s['results']:
 name=row['name'];p=W/name;rows[name]=row
 ck(name+' solver completed',row['solver_completed']);ck(name+' deck bytes',sha(p/'testbench.spice')==row['deck_sha256']);ck(name+' raw bytes',sha(p/'waveform.dat')==row['raw_sha256']);ck(name+' compact bytes',sha(R/row['compact_csv_path'])==row['compact_csv_sha256'])
 deck=(p/'testbench.spice').read_text();ref=next(l for l in deck.splitlines() if l.startswith('VREFRAIL '));tok=ref.split('PWL(')[1].rstrip(')').split();time=np.array([float(v.rstrip('n')) for v in tok[::2]])*1e-9;volts=np.array([float(v) for v in tok[1::2]])
 ck(name+' source knots monotonic',np.all(np.diff(time)>0));ck(name+' same physical source function',np.max(np.abs(volts-np.minimum(time/100e-9,1)*3.3))<1e-12)
 a=np.loadtxt(p/'waveform.dat',skiprows=1,usecols=[0,1,4]);arrays[name]=a;ck(name+' complete window',a[0,0]==0 and abs(a[-1,0]-20e-6)<1e-18)
 ck(name+' unchanged 1nA guard',np.abs(a[:,1]).max()<1e-9)
 q=independently_integrate(a[:,0],a[:,1]);ck(name+' independent Q integrals',all(abs(q[k]-row['charge'][k])<1e-29 for k in q))
selected=[r for r in s['results'] if r['local_mesh_ps']<=.2];keys={r['name'] for r in selected};pairs=s['selected_comparisons'];expected={tuple(sorted([a['name'],b['name']])) for a,b in itertools.combinations(selected,2)}
ck('Exactly 10 final controls',len(selected)==10);ck('All 45 unique comparisons',len(pairs)==45 and {tuple(sorted([p['a'],p['b']])) for p in pairs}==expected)
for row in pairs:
 a,b=arrays[row['a']],arrays[row['b']];t=np.unique(np.r_[a[:,0],b[:,0]]);d=np.interp(t,a[:,0],a[:,1])-np.interp(t,b[:,0],b[:,1]);di=float(np.abs(d).max())
 ck(row['a']+' vs '+row['b']+' current norm recompute',abs(di-row['maximum_current_difference_a'])<1e-25)
 ck(row['a']+' vs '+row['b']+' current budget',di<=2e-12)
 for key,q in row['charge_comparisons'].items():
  expected=abs(rows[row['a']]['charge'][key]-rows[row['b']]['charge'][key]);ck(row['a']+' vs '+row['b']+' '+key+' budget',abs(expected-q['absolute_difference_c'])<1e-30 and expected<=4e-17 and q['branch']=='near_zero_absolute')
ck('Revised pass explicitly separate from old fail',s['revised_numerical_acceptance_passed'] and not s['legacy_4p909pct_result_passed'])
report=dict(date='2026-10-15',checks_count=len(checks),data_integrity_passed=all(c['passed'] for c in checks),legacy_relative_gate_passed=False,revised_numerical_acceptance_passed=s['revised_numerical_acceptance_passed'],summary_sha256=sha(D/'refined-summary.json'),scan_summary_sha256=sha(D/'summary.json'),audit_script_sha256=sha(Path(__file__)),checks=checks,scope='No new physical-circuit or layout claim; frozen startup-v2 numerical evidence only.')
(D/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['checks_count','data_integrity_passed','legacy_relative_gate_passed','revised_numerical_acceptance_passed']}))
raise SystemExit(0 if report['data_integrity_passed'] else 2)
