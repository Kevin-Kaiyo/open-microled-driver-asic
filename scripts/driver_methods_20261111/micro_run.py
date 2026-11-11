#!/usr/bin/env python3
"""Run exactly the named bounded MicroLED experiment; one SPICE at a time."""
import argparse
import json
from micro_engine import init_candidate, run_case
from micro_candidates import candidate

def run(name, rates, dc=True, steps=40):
    c=candidate(name)
    work=init_candidate(c['name'], c['route'], c['route_text'], c['parameters'], notes=c['notes'])
    if dc:
        for level in [0,1]:
            r=run_case(work, level=level, **c['case_overrides'])
            print(json.dumps({'DC':level,'passed':r.get('DC_screen_pass'),'metrics':r.get('metrics')},ensure_ascii=False),flush=True)
            if not r.get('DC_screen_pass'): return
    for rate in rates:
        r=run_case(work,rate=rate,steps=steps,timeout_s=1800,**c['case_overrides'])
        print(json.dumps({'name':name,'rate':rate,'analysis':r.get('analysis'),'error':r.get('analysis_error')},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--rates',nargs='*',type=float,default=[1.6]);p.add_argument('--steps',type=int,default=40);p.add_argument('--skip-dc',action='store_true');a=p.parse_args()
    run(a.name,a.rates,not a.skip_dc,a.steps)
