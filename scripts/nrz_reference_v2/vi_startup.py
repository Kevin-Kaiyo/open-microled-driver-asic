"""VI startup/hold/ready metrics, separate from the unchanged NRZ receiver."""
from pathlib import Path
import hashlib,json
import numpy as np
import run as r
SOURCE=Path(__file__).read_bytes();SHA=hashlib.sha256(SOURCE).hexdigest()
def analyze(work,c,result,out_name='startup-analysis.json'):
 folder=work/'cases'/c['name'];snapshot=work/'execution-sources'/('vi-startup-'+SHA+'.py');snapshot.parent.mkdir(exist_ok=True)
 if not snapshot.exists():snapshot.write_bytes(SOURCE)
 out=folder/out_name;identity={'result_sha256':r.sha(folder/'result.json'),'source_sha256':SHA}
 if out.exists():
  previous=json.loads(out.read_text());assert previous['analysis_identity']==identity,'Existing analysis identity changed';return previous['row']
 if not result['simulation_ok']:
  row={'name':c['name'],'simulation_ok':False,'analysis_ok':False};r.emit(out,{'row':row,'analysis_source_sha256':SHA,'analysis_identity':identity});return row
 r.module(work/'inputs/legacy/metrics.py','metrics');a=r.module(work/'inputs/legacy/analyze.py','vi_start');a.ROOT=r.ROOT
 trace,sources=a.load_trace(result,folder/'result.json');stress=a.stress_metrics(trace,result);t=trace[:,0];vec=result['vectors'];i=trace[:,vec['iled_cond']];s=c['startup'];release=s.get('disable_release_s',20e-6);last=t>s.get('stop_s',100e-6)-10e-6
 device=[{'instance':d['instance'],'model':d['model'],'maximum_V':d['max_abs_terminal_V'],'margin_V':(6 if '06v0' in d['model'] else 3.63)-d['max_abs_terminal_V']} for d in stress['all_devices']]
 hold=np.zeros(len(t),dtype=bool)
 for lo,hi in s.get('hold_windows_s',[[0,release]]):hold|=(t>=lo)&(t<hi)
 errors=(abs(i-100e-6)>5e-6)&(t>=release);ix=np.flatnonzero(errors);settled=float(t[ix[-1]]) if len(ix) else release
 row={'name':c['name'],'simulation_ok':True,'analysis_ok':True,'current_peak_A':float(i.max()),'current_final_A':float(i[-1]),'last10us_pp_A':float(np.ptp(i[last])),'hold_peak_A':float(i[hold].max()) if hold.any() else None,'hold_mean_A':float(np.trapezoid(i[hold],t[hold])/(t[hold][-1]-t[hold][0])) if hold.sum()>1 else None,'last_outside_5pct_s':settled,'release_to_settled_s':max(0,settled-release),'minimum_device_margin_V':min(d['margin_V'] for d in device)}
 row['hold_budget_passed']=bool(not hold.any() or row['hold_peak_A']<=2e-6)
 row['ready_deadline_passed']=bool(settled<=release+2e-6 and abs(i[-1]-100e-6)<=5e-6)
 row['device_screen_passed']=bool(row['minimum_device_margin_V']>=0)
 row['startup_passed']=bool(row['current_peak_A']<=125e-6 and row['last10us_pp_A']<1e-6 and row['hold_budget_passed'] and row['ready_deadline_passed'] and row['device_screen_passed'])
 powers={}
 for name in result['rails']:
  p=-trace[:,vec[name.lower()+'_voltage']]*trace[:,vec[name.lower()+'_current']]
  powers[name]={'last10us_mean_W':float(np.trapezoid(p[last],t[last])/(t[last][-1]-t[last][0])),'full_energy_J':float(np.trapezoid(p,t))}
 gate=max((z['max_abs_V'],d['instance'],p) for d in stress['all_devices'] for p,z in d['terminal_differences'].items() if p in ['VGS','VGD','VGB'])
 r.emit(out,{'row':row,'stress':stress,'device_specific_screen':device,'max_gate_pair':{'V':gate[0],'instance':gate[1],'pair':gate[2]},'source_power':powers,'sources':sources,'analysis_source_sha256':SHA,'analysis_source':r.rel(snapshot),'analysis_identity':identity,'acceptance':'Hold conductiveLED <=2uA; after release reach100uA±5% within2us and stay; peak<=125uA; last10us pp<1uA; model-specific conservative terminal screen. Not zero-current shutdown, POR, BER, or silicon signoff.'})
 return row
def analyze_slow(work,c,result):
 folder=work/'cases'/c['name'];out=folder/'slow-analysis.json';identity={'result_sha256':r.sha(folder/'result.json'),'source_sha256':SHA}
 snapshot=work/'execution-sources'/('vi-startup-'+SHA+'.py');snapshot.parent.mkdir(exist_ok=True)
 if not snapshot.exists():snapshot.write_bytes(SOURCE)
 if out.exists():
  previous=json.loads(out.read_text());assert previous['analysis_identity']==identity;return previous['row']
 if not result['simulation_ok']:
  row={'name':c['name'],'simulation_ok':False,'analysis_ok':False};r.emit(out,{'row':row,'analysis_identity':identity});return row
 r.module(work/'inputs/legacy/metrics.py','metrics');a=r.module(work/'inputs/legacy/analyze.py','vi_slow');a.ROOT=r.ROOT
 tr,sources=a.load_trace(result,folder/'result.json');stress=a.stress_metrics(tr,result);t=tr[:,0];vec=result['vectors'];current=tr[:,vec['iled_cond']];iset=tr[:,vec['iset_current']]
 target=np.where(tr[:,vec['data']]>c['vdd_V']/2,100e-6,25e-6)
 mask=t>2e-6
 edges=[20e-6,40e-6,60e-6,80e-6,100e-6] if c['startup']['kind']=='loadstep' else [20e-6,40e-6]
 for edge in edges:mask&=~((t>=edge-1e-12)&(t<edge+2e-6))
 err=np.abs(current-target)/target;last=t>90e-6
 limits=[(6 if '06v0' in d['model'] else 3.63)-d['max_abs_terminal_V'] for d in stress['all_devices']]
 row={'name':c['name'],'simulation_ok':True,'analysis_ok':True,'LED_min_A':float(current.min()),'LED_max_A':float(current.max()),'max_current_error_fraction_after_2us':float(err[mask].max()),'iset_min_A':float(iset.min()),'iset_max_A':float(iset.max()),'iset_last10us_pp_A':float(np.ptp(iset[last])),'minimum_device_margin_V':min(limits)}
 row['device_screen_passed']=bool(min(limits)>=0);row['slow_passed']=bool(row['device_screen_passed'] and current.max()<=125e-6 and err[mask].max()<=.05 and np.ptp(iset[last])<=1e-6)
 r.emit(out,{'row':row,'stress':stress,'sources':sources,'analysis_identity':identity,'acceptance':'After2us transition blanking:25/100uA target±5%,peak125uA,last10usISETpp<=1uA,model-specificterminalscreen. SeparatefromNRZsampling.'});return row
