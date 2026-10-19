"""Independent evidence audit; preserves experiment failure independently of audit."""
from pathlib import Path
import csv,hashlib,json,math,re
import numpy as np
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'evidence/analog-v3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 checks=[];paths=[]
 def ck(n,p):checks.append(dict(name=n,passed=bool(p)))
 for tag in ['pvt-pex-r5','pvt-pex-r5-bleed10M']:
  s=json.loads((E/tag/'summary.json').read_text());rows=list(csv.DictReader((E/tag/'pvt.csv').open()));ck(tag+'270',len(rows)==270 and s['count']==270);ck(tag+'unique270',len(set((r['corner'],r['temp_c'],r['logic_v'],r['led_v'],r['on']) for r in rows))==270)
  for r in rows:
   cur=float(r['current_a']);p=abs(cur/1e-4-1)<=.05 if r['on']=='1' else abs(cur)<1e-9;ck(tag+'case'+r['index'],p==(r['passed']=='True'))
  ck(tag+'reportedpass',s['passed']==all(r['passed']=='True' for r in rows))
 for tag in ['ac-pex-r4','ac-pex-r5','ac-pex-r5-bleed10M']:
  s=json.loads((E/tag/'summary.json').read_text());ck(tag+'12cases',len(s['results'])==12)
  for r in s['results']:
   p=E/tag/f'{r["envelope"]}_cc{r["cc_pf"]}_cs{r["csense_pf"]}.csv';a=np.loadtxt(p,delimiter=',',skiprows=1);ix=np.flatnonzero((a[:-1,1]>=0)&(a[1:,1]<0));ck(str(p.name)+'onecross',len(ix)==len(r['crossings']))
   for k,c in zip(ix,r['crossings']):
    z=-a[k,1]/(a[k+1,1]-a[k,1]);freq=10**((1-z)*math.log10(a[k,0])+z*math.log10(a[k+1,0]));pm=180+(1-z)*a[k,2]+z*a[k+1,2];ck(str(p.name)+'unity',abs(freq/c['frequency_hz']-1)<1e-9 and abs(pm-c['phase_margin_deg'])<1e-9)
   ck(str(p.name)+'opbias',r['dc_closed_vs_injected_max_delta']<1e-9)
 for tag in ['pex-r4-cc3','pex-r4-cc30','pex-r5-cc30','pex-r5-cc30-csense30','pex-r5-final-bleed10M','pex-r5-bleed10M-startup-grid']:
  q=E/tag/'summary.json'
  if not q.exists():continue
  s=json.loads(q.read_text());raw=ROOT/s['raw_directory'];ck(tag+'dut',sha(raw/'inputs/dut.spice')==s['dut_sha256'])
  for r in s['results']:
   p=raw/r['name'];log=(p/'ngspice.log').read_text();paths.append(dict(tag=tag,case=r['name'],transient_op_fallback='Transient op started' in log,log=str((p/'ngspice.log').relative_to(ROOT))))
   if not r['simulation_completed']:continue
   ck(tag+r['name']+'checkaggregate',r['passed']==all(c['passed'] for c in r['checks']))
   a=np.loadtxt(p/'waveform.dat',skiprows=1);ck(tag+r['name']+'time',np.isfinite(a).all() and np.all(np.diff(a[:,0])>0))
   if r['kind']=='startup':
    measured=float(np.abs(a[a[:,0]<20e-6,1]).max());ck(tag+r['name']+'startup_peak',abs(measured-r['startup']['branch_max_abs_a'])<1e-15)
    if s.get('startup_grid',{}).get('enabled'):
     text=(p/'testbench.spice').read_text();m=re.search(r'VREFRAIL refrail 0 PWL\((.*?)\)',text,re.S);tokens=m[1].replace('+',' ').split();pairs=np.asarray(list(map(float,tokens))).reshape(-1,2);rail={'tt':3.3,'ss':2.97,'ff':3.63}[r['envelope']];wanted=rail*np.minimum(pairs[:,0]/(r['ramp_ns']*1e-9),1);ck(tag+r['name']+'same_pwl_function',np.max(abs(pairs[:,1]-wanted))<1e-14)
  ck(tag+'aggregate',s['passed']==(all(r['passed'] for r in s['dc_results']) and all(r.get('passed',False) for r in s['results'])))
 fp=E/'final/summary.json'
 if fp.exists():
  fs=json.loads(fp.read_text());ck('final17',len(fs['results'])==17);ck('final10startup',sum(r['kind']=='startup' for r in fs['results'])==10)
  for r in fs['results']:
   sp=ROOT/r['source_summary_path'];source=json.loads(sp.read_text());ck('finalsource-summary-'+r['name'],sha(sp)==r['source_summary_sha256']);src=next(x for x in source['results'] if x['name']==r['name']);ck('finalsource-result-'+r['name'],all(r[k]==v for k,v in src.items()))
   for name,entry in r['source_artifacts'].items():ck('finalartifact-'+r['name']+'-'+name,sha(ROOT/entry['path'])==entry['sha256'])
  ck('finalaggregate',fs['passed']==(all(r['passed'] for r in fs['results']) and all(r['passed'] for r in fs['dc_results'])))
 body=json.loads((E/'body-audit.json').read_text());raw=ROOT/body['raw_directory']
 for r in body['results']:
  log=(raw/r['name']/'ngspice.log').read_text();paths.append(dict(tag='body-audit',case=r['name'],transient_op_fallback='Transient op started' in log,log=str((raw/r['name']/'ngspice.log').relative_to(ROOT))))
 ck('loop-control',json.loads((E/'loop-control.json').read_text())['passed'])
 result=dict(schema_version=1,date='2026-10-15',audit_passed=all(c['passed'] for c in checks),check_count=len(checks),checks=checks,solver_paths=paths,scope='Data/source/calculation consistency only; expected physical/numerical failures remain failures. Solver exit0 is not evidence that direct Newton DC succeeded; fallback paths retained.')
 (E/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['audit_passed','check_count']}))
 if not result['audit_passed']:raise SystemExit(2)
if __name__=='__main__':main()
