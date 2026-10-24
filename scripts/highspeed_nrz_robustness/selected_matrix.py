#!/usr/bin/env python3
"""Final frozen-device regression at declared discrete points, with retained negative controls."""
import datetime,json,subprocess
import final as f
w=f.r.ROOT/'build/highspeed-nrz-robustness/selected-a8-b58-r4';f.v.verify(w)
cs=[]
# Finish interrupted original targets; completed points are immutable references.
for c in json.loads((w/'plan-targets-AB.json').read_text())['cases']:
 rp=w/'cases'/c['name']/'result.json'
 if rp.exists() and rp.with_name('analysis.json').exists():continue
 if rp.exists():
  rr=json.loads(rp.read_text())
  if rr.get('exit_code') is None and not rr.get('error'):c=c|{'name':c['name']+'-admin-retry','administrative_retry_of':f.r.rel(rp)}
 cs.append(c)
cs.append(f.case(w,'A','SS_rate04','ss',125,3.,rate=.4))
for stage in ['dc','stress','rates','numerical']:cs+=f.plan(w,stage,'AB')
# DC corroboration for declared joint negative control; low rate cannot repair static threshold failure.
for q in 'AB':
 offsets={'VLED':-.05,'VH':.05,'VL':.05} if q=='A' else {'VLED':-.05,'VDUMMY':-.05}
 for bit in [0,1]:cs.append(f.case(w,q,'joint_SSmin_VLEDaux_DC','ss',125,2.95,rail_offsets_V=offsets,dc_bit=bit))
f.r.emit(w/'plan-selected-final-matrix.json',{'created_before_execution':datetime.datetime.now().isoformat(),'selected_discrete_points_Gbps':{'A':.4,'B':.5},'common_energy_comparison_Gbps':.4,'scope':'Discrete verification points; .25/.4/.5 behavior is not monotonic under frozen sampler, not a continuous maximum-rate proof.','cases':cs})
for c in cs:
 print(json.dumps(f.v.analyze(w,f.r.run_case(w,c))),flush=True)
 f.v.summarize(w)
for extra in [[],['--matched-baseline','--routes','A']]:
 subprocess.run(['build/layout/venv/bin/python','scripts/highspeed_nrz_robustness/supply_package.py','--work',str(w),'--final',*extra],check=True)
f.v.summarize(w)
