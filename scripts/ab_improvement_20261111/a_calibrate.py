#!/usr/bin/env python3
"""Freeze route A output candidates at the same25/100uA DC targets.

Uses monotonic bisection once at TT27C; all fit points are preserved.
This calibrates nominal shunt-rail resistor values, not PVT corners or RX labels.
"""
from pathlib import Path
import argparse,sys,json
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/ab_improvement_20261111'))
from a_candidates import candidate
from engine_checked import init_candidate,run_case,emit,sha
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('variant',choices=['a-rin1wide-buf03-out2','a-rin1wide-core03'])
parser.add_argument('--rates',nargs='*',type=float,default=[])
args=parser.parse_args()
c=candidate(args.variant)
w=init_candidate(c['name']+'-calibration',c['route'],c['route_text'],c['parameters'],c['hypothesis'])
p=c['parameters'].copy();records=[]
for level,key,target in [(0,'RH',25),(1,'RL',100)]:
 lo=c['parameters'][key]*.8;hi=c['parameters'][key]*1.5
 for iteration in range(18):
  value=(lo+hi)/2;p[key]=value
  r=run_case(w,level=level,label=f'DC-fit-{key}-{iteration:02}',parameters=p.copy())
  assert r['simulation_ok'] and not r.get('analysis_error')
  got=r['metrics']['i_led_A']*1e6
  rec={'parameter':key,'iteration':iteration,'value_ohm':value,'current_uA':got,'target_uA':target,'error_percent':(got/target-1)*100,'source_result':str((w/'cases'/r['case']['name']/'result.json').relative_to(ROOT)),'result_sha256':sha(w/'cases'/r['case']['name']/'result.json')};records.append(rec)
  print('FIT',json.dumps(rec),flush=True)
  if abs(got/target-1)<.0002:break
  if got>target:lo=value
  else:hi=value
 else:raise RuntimeError('DC fit did not meet0.02%')
final=init_candidate(c['name']+'-matched',c['route'],c['route_text'],p,c['hypothesis']+' FinalnominalDCcalibration only; noPVTpercornerretuning.')
checks=[]
for level in [0,1]:
 r=run_case(final,level=level);assert r['DC_screen_pass'];checks.append({'level':level,'current_uA':r['metrics']['i_led_A']*1e6,'error_percent':r['metrics']['current_error_percent'],'pass':r['DC_screen_pass'],'source_result':str((final/'cases'/f'DC-L{level}'/'result.json').relative_to(ROOT)),'result_sha256':sha(final/'cases'/f'DC-L{level}'/'result.json')})
filename='a-output-calibration.json' if args.variant.endswith('out2') else 'a-core03-calibration.json'
emit(ROOT/'evidence/ab-improvement-20261111'/filename,{'method':'Sequential monotonic bisection RH for25uA thenRL for100uA; freezeonceatTT27C3.3V. Stops0.02%perlevel, finalbothlevelscheckedwithsameparameterpair.','candidate':final.name,'parameters':p,'records':records,'final_checks':checks,'reproduction_script':str(Path(__file__).relative_to(ROOT)),'reproduction_script_sha256':sha(Path(__file__))})

for rate in args.rates:
 r=run_case(final,rate=rate);print('TRANSIENT_RESULT',json.dumps(r.get('analysis',{})),flush=True)
