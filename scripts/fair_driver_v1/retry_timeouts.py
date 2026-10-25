#!/usr/bin/env python3
"""Only extend wall-clock allowance after preserved administrative timeouts."""
import argparse,concurrent.futures,json
import run as e

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--jobs',type=int,default=1);a=ap.parse_args()
 w=e.BUILD/'matched-r2';todo=[]
 for p in sorted((w/'cases').glob('RX-*/result.json')):
  r=json.loads(p.read_text());c=r['case']
  if r.get('timed_out') and not c.get('retry_of'):
   q=dict(c,name=c['name']+'-retry900',retry_of=c['name'],timeout_s=900)
   if not (w/'cases'/q['name']).exists():todo.append(q)
 print('preserved timeout retries',len(todo),flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
  futures={pool.submit(e.run,w,c):c for c in todo}
  for f in concurrent.futures.as_completed(futures):
   r=f.result();m=r.get('metrics',{});rx=m.get('receiver',{});print(json.dumps({'case':r['case']['name'],'simulation_ok':r['simulation_ok'],'elapsed_s':r['elapsed_s'],'analysis_error':r.get('analysis_error'),'energy':m.get('total_energy'),'rx':rx.get('checks')}),flush=True)
if __name__=='__main__':main()
