"""Verify frozen PEX numerical probes independently from their runners."""
from pathlib import Path
import hashlib,json,re,itertools
import numpy as np
R=Path(__file__).resolve().parents[2];D=R/'evidence/startup-v3/numerical';checks=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ck(name,x):checks.append(dict(name=name,passed=bool(x)))
def charges(t,i):
 k=np.flatnonzero(i[:-1]*i[1:]<0);z=t[k]-i[k]*(t[k+1]-t[k])/(i[k+1]-i[k]);x=np.unique(np.r_[t,z]);v=np.interp(x,t,i);q=np.diff(x)*(v[:-1]+v[1:])/2
 return dict(signed_c=float(q.sum()),positive_c=float(q[q>0].sum()),negative_c=float(q[q<0].sum()))
inputs={};summaries={}
for tag,runner in [('pex-r5-gmin-screen','pex_numerical.py'),('pex-r5-bleed10M-ff-probe','ff_startup_probe.py')]:
 p=D/tag/'summary.json';s=json.loads(p.read_text());summaries[tag]=s;inputs[str(p.relative_to(R))]=sha(p)
 ck(tag+' current runner bytes',sha(R/'scripts/startup_v3'/runner)==s['script_sha256'])
 base=R/s.get('base_deck',s.get('source_deck'));ck(tag+' frozen source deck bytes',sha(base)==s.get('base_deck_sha256',s.get('source_deck_sha256')));ck(tag+' frozen DUT bytes',sha(base.parent.parent/'inputs/dut.spice')==s['dut_sha256'])
 for row in s['results']:
  label=tag+'/'+row['name'];raw=R/row['raw_directory'];log=(raw/'ngspice.log').read_text();ck(label+' deck hash',sha(raw/'testbench.spice')==row['deck_sha256']);ck(label+' log hash',sha(raw/'ngspice.log')==row['log_sha256']);ck(label+' OP path explicit',row['transient_op_fallback']==('Transient op started' in log))
  if not row['solver_completed']:
   ck(label+' timeout remains explicit',row['exit_code']==-1 and 'RUN_TIMEOUT_150S' in log);continue
  data=np.loadtxt(raw/'waveform.dat',skiprows=1,usecols=[0,1]);inputs[label]=data;t=data[:,0];i=data[:,1];q=charges(t,i);reported=row.get('charge',row.get('branch_charge'));ck(label+' independently integrated charge',all(abs(q[k]-reported[k])<1e-28 for k in q));ck(label+' actual peak matches',abs(float(abs(i).max())-row.get('peak_a',row.get('branch_peak_a')))<1e-25);ck(label+' 1nA guard',abs(i).max()<1e-9);ck(label+' raw hash',sha(raw/'waveform.dat')==row['raw_sha256']);ck(label+' compact hash',sha(D/tag/(row['name']+'.csv'))==row['compact_csv_sha256'])
  ref=next(x for x in (raw/'testbench.spice').read_text().splitlines() if x.startswith('VREFRAIL '));tokens=ref.split('PWL(')[1].rstrip(')').split();times=np.array([float(x.rstrip('n')) for x in tokens[::2]])*1e-9;volt=np.array([float(x) for x in tokens[1::2]]);vf=3.63 if 'ff' in tag else 3.3;ck(label+' same original ramp function',np.diff(times).min()>0 and max(abs(volt-np.minimum(times/100e-9,1)*vf))<1e-12)
s=summaries['pex-r5-bleed10M-ff-probe'];tag='pex-r5-bleed10M-ff-probe';byname={r['name']:r for r in s['results']};selected=set(s['selected_controls']);expected={tuple(sorted(p)) for p in itertools.combinations(selected,2)}
ck('Five selected controls, all ten comparisons',len(selected)==5 and len(s['selected_comparisons'])==10 and {tuple(sorted([p['a'],p['b']])) for p in s['selected_comparisons']}==expected)
for p in s['all_comparisons']:
 x,y=inputs[tag+'/'+p['a']],inputs[tag+'/'+p['b']];ts=np.unique(np.r_[x[:,0],y[:,0]]);di=float(max(abs(np.interp(ts,x[:,0],x[:,1])-np.interp(ts,y[:,0],y[:,1]))));ck(p['a']+' vs '+p['b']+' independent norm',abs(di-p['current_max_difference_a'])<1e-25)
 if p['a'] in selected and p['b'] in selected:ck(p['a']+' vs '+p['b']+' selected numerical budget',di<=2e-12 and p['charge_max_difference_c']<=4e-20 and not byname[p['a']]['transient_op_fallback'] and not byname[p['b']]['transient_op_fallback'])
ck('Fallback excluded from selected controls',all(not byname[n]['transient_op_fallback'] for n in selected));ck('Strict timeout not erased',not s['all_completed'] and any(not r['solver_completed'] and r['profile']=='tight' for r in s['results']));ck('Selected result recomputed true',s['selected_numerical_acceptance_passed'])
receipt=dict(date='2026-10-15',checks_count=len(checks),data_integrity_passed=all(c['passed'] for c in checks),ff_selected_short_window_numerical_passed=s['selected_numerical_acceptance_passed'],full_startup_or_recovery_pass_claimed=False,audit_script_sha256=sha(Path(__file__)),source_summary_sha256={k:v for k,v in inputs.items() if isinstance(v,str)},checks=checks)
(D/'validation-pex.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:receipt[k] for k in ['checks_count','data_integrity_passed','ff_selected_short_window_numerical_passed','full_startup_or_recovery_pass_claimed']}));raise SystemExit(0 if receipt['data_integrity_passed'] else 2)
