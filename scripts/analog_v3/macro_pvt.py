"""270 deterministic DC points on a frozen actual new macro deck."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse,csv,hashlib,itertools,json,re,shutil,subprocess,tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--tag',required=True);a=ap.parse_args();a.base=a.base.resolve();w=Path(tempfile.mkdtemp(prefix='pvt-'+a.tag+'-',dir=ROOT/'build/analog-v3'));base=a.base.read_text();cases=list(itertools.product(['typical','ss','ff','sf','fs'],[0,27,85],[2.97,3.3,3.63],[4.5,5,5.5],[0,1]));deps={str(a.base.relative_to(ROOT)):sha(a.base)}
 for src in re.findall(r'(?im)^\.include "([^"]+)"',base):deps[str(Path(src).relative_to(ROOT))]=sha(Path(src))
 def run(item):
  k,(co,t,v,l,on)=item;p=w/f'{k:03d}';p.mkdir();s=re.sub(r'(?m)^(\.lib .* )typical$',r'\g<1>'+co,base);s=re.sub(r'(?m)^\.temp .*',f'.temp {t}',s)
  for name,node,val in [('VREFRAIL','refrail',v),('VSAFE','saferail',v),('VBUF','bufrail',v),('VLED','rail',l),('VRAW','raw_pwm',v*on),('VPERMIT','permit',v)]:s=re.sub(r'(?m)^'+name+r' .*$',f'{name} {node} 0 {val}',s)
  (p/'testbench.spice').write_text(s);r=subprocess.run(['ngspice','-b','testbench.spice'],cwd=p,text=True,capture_output=True);(p/'ngspice.log').write_text(r.stdout+r.stderr)
  if r.returncode or re.search(r'(?im)^Error:|Timestep too small',r.stdout+r.stderr):return dict(index=k,corner=co,temp_c=t,logic_v=v,led_v=l,on=on,completed=False,current_a=None,passed=False)
  d=np.loadtxt(p/'op.dat',skiprows=1);cur=float(d[1]);return dict(index=k,corner=co,temp_c=t,logic_v=v,led_v=l,on=on,completed=True,current_a=cur,passed=abs(cur/100e-6-1)<=.05 if on else abs(cur)<1e-9)
 with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(run,enumerate(cases)))
 with (w/'pvt.csv').open('w') as f:d=csv.DictWriter(f,fieldnames=list(rows[0]));d.writeheader();d.writerows(rows)
 s=dict(schema_version=1,date='2026-10-15',tag=a.tag,raw_directory=str(w.relative_to(ROOT)),base_deck=str(a.base.relative_to(ROOT)),input_sha256=deps,count=len(rows),failed_count=sum(not x['passed'] for x in rows),on_min_a=min(x['current_a'] for x in rows if x['on'] and x['completed']),on_max_a=max(x['current_a'] for x in rows if x['on'] and x['completed']),off_max_abs_a=max(abs(x['current_a']) for x in rows if not x['on'] and x['completed']),passed=all(x['passed'] for x in rows),scope='Actual selected new macro topology and extracted nominal RC; deterministic MOS process corners, temperature and rail voltage. No statistical mismatch/yield or RC extraction-corner sweep.')
 (w/'summary.json').write_text(json.dumps(s,indent=2)+'\n');e=ROOT/'evidence/analog-v3'/('pvt-'+a.tag);e.mkdir(parents=True,exist_ok=True)
 for n in ['pvt.csv','summary.json']:shutil.copyfile(w/n,e/n)
 print(json.dumps(s,indent=2))
if __name__=='__main__':main()
