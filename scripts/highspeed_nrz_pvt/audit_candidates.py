#!/usr/bin/env python3
"""Retrospective exploratory audit; does not rewrite historical result metadata."""
import json,re,hashlib
from pathlib import Path
import explore as e
r=e.r;w=e.ROOT/'build/highspeed-nrz-pvt/explore';m=json.loads((w/'manifest.json').read_text());rows=[];errors=[]
for rp in sorted((w/'cases').glob('*/result.json')):
 result=json.loads(rp.read_text());case=result['case'];definition=m['variants'][case['route']][case['variant']];core=w/'inputs'/definition['path'];deck=rp.with_name('testbench.spice');a=rp.with_name('analysis.json')
 checks={'deck_matches_original_result_hash':r.sha(deck)==result['deck_sha256'],'current_core_matches_candidate_definition':r.sha(core)==definition['sha256'],'core_explicitly_included':str(core) in deck.read_text()}
 if case['route']=='B':
  match=re.search(r'^RREF_EXT\s+(\w+)\s+bias\s+(\S+)',deck.read_text(),re.M)
  checks['RREF_source_matches_definition']=bool(match and match.group(1)==definition.get('rref_source','vdd'))
  checks['RREF_value_matches_definition']=bool(match and float(match.group(2))==definition.get('rref_ohm',88386.1064910889))
 rec=json.loads(a.read_text()) if a.exists() else {};row=rec.get('row',{})
 rows.append({'case':case,'definition':definition,'result_json':r.rel(rp),'result_sha256':r.sha(rp),'analysis_json':r.rel(a) if a.exists() else None,'analysis_sha256':r.sha(a) if a.exists() else None,'checks':checks,'original_runner_source':result.get('runner_source'),'original_runner_sha256':result.get('runner_source_sha256'),'metrics':row})
 if not all(checks.values()):errors.append(case['name'])
out={'scope':'Retrospective inspection of preserved exploratory decks and current immutable candidate core files. Older cases did not capture complete candidate definition identity at execution time; this audit does not imply that they did. Formal regression has original input identities.','manifest_at_audit_sha256':r.sha(w/'manifest.json'),'cases':rows,'case_count':len(rows),'config_count':sum(len(v) for v in m['variants'].values()),'failures':errors,'all_checks_passed':not errors}
r.emit(r.EVIDENCE/'candidate-ledger.json',out);print(json.dumps({'case_count':len(rows),'config_count':out['config_count'],'audit_failures':errors}))
if errors:raise SystemExit(1)
