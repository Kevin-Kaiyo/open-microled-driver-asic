"""Independent stdlib audit: hashes, peak guards, directional charge, failure flags."""
from pathlib import Path
import bisect,csv,hashlib,json,math
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clip(t,y,l,r):
 def point(x):
  tol=8*math.ulp(max(abs(x),abs(t[-1])))
  if abs(x-t[0])<=tol:return y[0]
  if abs(x-t[-1])<=tol:return y[-1]
  j=bisect.bisect_right(t,x)-1
  if t[j]==x:return y[j]
  if j<0 or j+1==len(t):raise ValueError('Missing window')
  return y[j]+(y[j+1]-y[j])*(x-t[j])/(t[j+1]-t[j])
 a=bisect.bisect_right(t,l);b=bisect.bisect_left(t,r)
 return [l]+t[a:b]+[r],[point(l)]+y[a:b]+[point(r)]
def charge(t,y,l,r):
 t,y=clip(t,y,l,r);pos=[];neg=[];signed=[]
 for a,b,u,v in zip(t,t[1:],y,y[1:]):
  signed.append((b-a)*(u+v)/2)
  if u*v<0:
   z=a-u*(b-a)/(v-u);parts=[(z-a)*u/2,(b-z)*v/2]
  else:parts=[(b-a)*(u+v)/2]
  for q in parts:(pos if q>0 else neg).append(q)
 return dict(signed_c=math.fsum(signed),positive_c=math.fsum(pos),negative_c=math.fsum(neg))
def main():
 s=json.loads((ROOT/'evidence/startup-v2/summary.json').read_text());raw=ROOT/s['raw_directory'];checks=[]
 def ck(name,passed,**more):checks.append(dict(name=name,passed=bool(passed),**more))
 def close(a,b):return abs(a-b)<=max(1e-26,abs(b)*1e-10)
 for p,h in s['source_sha256'].items():
  ck('As-run frozen source '+p,sha(raw/'inputs'/p)==h)
  ck('Live source '+p,sha(ROOT/p)==h)
 for row in s['results']:
  case=raw/row['name'];ck(row['name']+' CSV hash',sha(ROOT/row['csvpath'])==row['csv_sha256'])
  ck(row['name']+' raw hash',sha(case/'waveform.dat')==row['raw_sha256']);ck(row['name']+' deck hash',sha(case/'testbench.spice')==row['deck_sha256'])
  with (case/'waveform.dat').open() as f:
   names=next(f).split();cols={n:[] for n in names}
   for ln in f:
    for n,v in zip(names,map(float,ln.split())):cols[n].append(v)
  t=cols[names[0]];i=cols['i(VLEDLOAD)'];cond=[a-b for a,b in zip(cols['@d.xled.dled[id]'],cols['@d.xled.dled[capcur]'])]
  ck(row['name']+' time monotonic',all(a<b for a,b in zip(t,t[1:])))
  for key in ['startup','fault','held_fault','fault_release_before_permit','fault_removal_stopped_clock','permit_before_raw','recovered_dc_window']:
   if key not in row:continue
   w=row[key];l,r=w['left_s'],w['right_s'];_,y=clip(t,i,l,r);_,co=clip(t,cond,l,r)
   ck(row['name']+' '+key+' branch peak',close(max(map(abs,y)),w['branch_max_abs_a']))
   ck(row['name']+' '+key+' conduction peak',close(max(map(abs,co)),w['conduction_max_abs_a']))
   q=charge(t,i,l,r)
   for k in q:ck(row['name']+' '+key+' '+k,close(q[k],w['branch_charge'][k]))
  if 'area_error_pct' in row:
   q=charge(t,i,514.5e-6,1026.5e-6)['signed_c'];err=(q/(512e-6*row['dc_full_a']/256)-1)*100
   ck(row['name']+' full raw d1 charge',close(q,row['charge_c']));ck(row['name']+' d1 relative error',abs(err-row['area_error_pct'])<1e-8)
  if row['name'].startswith('baseline'):
   ck(row['name']+' actual old 1nA failure preserved',row['expected_failure'] and row['startup']['branch_max_abs_a']>1e-9)
 for c in s['convergence']:
  change=abs(c['fine_charge_c']/c['coarse_charge_c']-1)*100
  ck(c['name']+' convergence math',abs(change-c['change_pct'])<1e-10)
  ck(c['name']+' original 0.2% status preserved',c['passed']==(change<=.2))
 ck('Functional pass is only declared subset',s['functional_contract_passed'] is True)
 ck('Original startup relative failure remains',s['legacy_startup_relative_convergence_passed'] is False and s['passed'] is False)
 output=dict(date='2026-10-14',checks=checks,check_count=len(checks),passed=all(c['passed'] for c in checks),experiment_passed=s['passed'],functional_contract_passed=s['functional_contract_passed'],legacy_relative_charge_passed=s['legacy_startup_relative_convergence_passed'],summary_sha256=sha(ROOT/'evidence/startup-v2/summary.json'))
 (ROOT/'evidence/startup-v2/validation.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps({k:v for k,v in output.items() if k!='checks'}))
 return 0 if output['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
