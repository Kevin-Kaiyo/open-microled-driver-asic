#!/usr/bin/env python3
"""Resume an explicit plan after administrative lock migration, without rewriting failures."""
import argparse,datetime,json
import run as r
import validate as v
p=argparse.ArgumentParser();p.add_argument('--work',required=True);p.add_argument('--plans',required=True);p.add_argument('--label',default='lock-migration');a=p.parse_args();w=r.ROOT/a.work;v.verify(w)
cs=[];mapping=[]
for pattern in a.plans.split(','):
 for plan in sorted(w.glob(pattern)):
  for original in json.loads(plan.read_text())['cases']:
   path=w/'cases'/original['name']/'result.json';c=dict(original)
   if path.exists():
    x=json.loads(path.read_text())
    if x.get('simulation_ok') and path.with_name('analysis.json').exists():continue
    if x.get('exit_code') is None and not x.get('error'):
     c['name']=original['name']+'-admin-retry';c['administrative_retry_of']=r.rel(path);mapping.append({'original':original['name'],'replacement':c['name'],'reason':'No ngspice launched; interrupted while waiting old global lock.'})
    elif not x.get('simulation_ok'):continue
   cs.append(c)
seen=set();cs=[c for c in cs if not (c['name'] in seen or seen.add(c['name']))]
r.emit(w/f'plan-resume-{a.label}.json',{'created_before_execution':datetime.datetime.now().isoformat(),'cases':cs,'administrative_replacements':mapping})
for c in cs:print(json.dumps(v.analyze(w,r.run_case(w,c))),flush=True)
v.summarize(w)
