#!/usr/bin/env python3
"""Explicit off-die VDD source and VSS return RL, external ground-referenced DATA."""
import argparse,datetime,json
import run as r
import validate as v
p=argparse.ArgumentParser();p.add_argument('--work',required=True);p.add_argument('--final',action='store_true');p.add_argument('--matched-baseline',action='store_true');p.add_argument('--routes',default='AB');a=p.parse_args();w=r.ROOT/a.work;v.verify(w)
cs=[]
external_vdd=3.65 if a.final and not a.matched_baseline else 3.6
for q in a.routes:
 c=v.case(w,q,'VDDVSSpkg_R1_L2'+('_matched' if a.matched_baseline else ''),vdd=external_vdd,supply_package={'r_vdd_ohm':1.,'l_vdd_H':2e-9,'r_vss_ohm':1.,'l_vss_H':2e-9},data_mode='fixed',data_high_V=external_vdd)
 if a.final and not a.matched_baseline and q=='A':c['rate_Gbps']=.4;c['name']=c['name'].replace('-1G-','-0.4G-')
 cs.append(c)
r.emit(w/('plan-supply-package'+('-matched' if a.matched_baseline else '')+'-AB.json'),{'created_before_execution':datetime.datetime.now().isoformat(),'scope':'Assumed lumped1ohm/2nH each VDD lead and VSS return. VDD source sampled before RL, dieVDD/dieVSS individually saved. DATA fixed to board0V/high nominalVDD, not die-ground tracking. VLED/aux remain board referenced. No PCB/EM signoff.','cases':cs})
for c in cs: print(json.dumps(v.analyze(w,r.run_case(w,c))),flush=True)
v.summarize(w)
