#!/usr/bin/env python3
"""Two TT calibration freedoms per route; immutable probe iterations."""
import json
from pathlib import Path
import numpy as np
import run as engine

def main():
 w=engine.BUILD/'dc-calibration-r1';engine.init(w)
 count=0
 def pair(p,tag):
  nonlocal count
  z=[]
  for level in [0,1]:
   case={'name':f'B-{tag}-{count:03d}-L{level}','kind':'dc','route':'B','level':level,'parameters':{'RSET':float(p[0]),'WTAIL':float(p[1]),'RINL':8e-6}}
   count+=1;r=engine.run(w,case);assert r['simulation_ok'];z.append(r['metrics']['i_led_A'])
  print(tag,p,z,flush=True);return np.array(z)
 p=np.array([20000.,5.76e-6]);target=np.array([25e-6,100e-6])
 for iteration in range(4):
  y=pair(p,f'iter{iteration}')
  if np.max(abs(y/target-1))<.00005:break
  h=p*np.array([.002,.002]);cols=[]
  for i in range(2):
   q=p.copy();q[i]+=h[i];cols.append((pair(q,f'jac{iteration}-{i}')-y)/h[i])
  dp=np.linalg.solve(np.array(cols).T,target-y);p+=dp
 p[1]=round(p[1]/5e-9)*5e-9
 final=pair(p,'grid-final')
 params=dict(engine.DEFAULT_PARAMS);params['B']={'RSET':float(p[0]),'WTAIL':float(p[1]),'RINL':8e-6}
 checks=[]
 for route,levels in [('A',[0,1]),('C',[0,1,2,3])]:
  for level in levels:
   r=engine.run(w,{'name':f'{route}-common-L{level}','kind':'dc','route':route,'level':level});checks.append({'route':route,'level':level,'current_uA':r['metrics']['i_led_A']*1e6,'error_percent':r['metrics']['current_error_percent']})
 out={'parameters':params,'B_final_uA':(final*1e6).tolist(),'common_port_A_C_checks':checks,'calibration_scope':'TT27C only; common finite port supplies; no PVT/RX tuning; WTAIL 5nm grid','runner_sha256':engine.sha(Path(engine.__file__))}
 engine.emit(w/'calibration.json',out);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
