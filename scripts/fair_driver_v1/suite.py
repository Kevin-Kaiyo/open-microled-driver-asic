#!/usr/bin/env python3
"""Frozen45-point paired schematic experiment; resume only completed case names."""
from pathlib import Path
import argparse,concurrent.futures,json,time
import run as e
CORNERS=[('TT','typical',27,3.3),('SS','ss',125,2.95),('FF','ff',-40,3.65)]
RATES=[.1,.25,.5,1.,2.]
def cases():
 out=[]
 for label,corner,temp,vdd in CORNERS:
  for route in 'ABC':
   for level in range(4 if route=='C' else 2):out.append({'name':f'DC-{label}-{route}-L{level}','kind':'dc','route':route,'corner':corner,'temp_C':temp,'vdd_V':vdd,'level':level})
 for rate in [.5,.1,.25,1.,2.]:
  for label,corner,temp,vdd in CORNERS:
   for route in 'ABC':out.append({'name':f'RX-{label}-{route}-{rate:g}G','route':route,'corner':corner,'temp_C':temp,'vdd_V':vdd,'net_rate_Gbps':rate})
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,default=e.BUILD/'matched-r2');ap.add_argument('--jobs',type=int,default=2);ap.add_argument('--timeout-s',type=int,default=900);ap.add_argument('--only',default='');a=ap.parse_args();w=a.work.resolve()
 parameters=json.loads((e.BUILD/'dc-calibration-r1/calibration.json').read_text())['parameters'];e.init(w,parameters)
 plan=cases();planpath=w/'plan.json'
 if planpath.exists():assert json.loads(planpath.read_text())==plan
 else:e.emit(planpath,plan)
 selected=[c for c in plan if not a.only or a.only in c['name']]
 def go(case):
  old=w/'cases'/case['name']/'result.json'
  if old.exists():return json.loads(old.read_text())
  return e.run(w,dict(case,timeout_s=a.timeout_s))
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
  futures={pool.submit(go,c):c for c in selected}
  for future in concurrent.futures.as_completed(futures):
   c=futures[future]
   try:
    r=future.result();m=r.get('metrics',{});rx=m.get('receiver',{});print(json.dumps({'case':c['name'],'ok':r['simulation_ok'],'sec':round(r['elapsed_s'],2),'MB':round(r.get('gzip_bytes',0)/1e6,1),'I_uA':m.get('i_led_A',0)*1e6,'E_pJ':m.get('total_energy',{}).get('positive_pJ_per_payload_bit'),'errors':rx.get('validation',{}).get('bit_errors'),'margin_uA':rx.get('validation',{}).get('decision_distance_min_uA'),'time_ps':rx.get('horizontal_margin',{}).get('min_ps'),'passed':m.get('passed')},allow_nan=False),flush=True)
   except Exception as err:print(json.dumps({'case':c['name'],'error':repr(err)}),flush=True);raise
if __name__=='__main__':main()
