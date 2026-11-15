#!/usr/bin/env python3
"""Freeze delivered MicroLED sources, compact evidence and figures after the held-out run."""
from pathlib import Path
import datetime,hashlib,json
ROOT=Path(__file__).resolve().parents[3];E=ROOT/'evidence/driver-interface-20261115'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def rel(p):return str(p.relative_to(ROOT))
s=json.loads((E/'micro-summary.json').read_text());assert s['status']=='frozen'
for row in s['rows']:
 p=ROOT/row['source_case'];assert sha(p/'result.json')==row['result_sha256'];assert sha(p/'manifest.json')==row['manifest_sha256']
for route,c in s['selections'].items():
 keys=['continuous_case','fault_case','half_step_case','holdout_case']
 for p in c['dc_cases']+[c[k] for k in keys]:
  assert next(x for x in s['rows'] if x['source_case']==p)['combined_research_screen_pass'],p
out=E/'micro-freeze.json'
files=sorted((ROOT/'scripts/driver_interface_20261115/micro').glob('*.py'))
files+=sorted(p for p in E.glob('micro-*') if p.is_file() and p!=out)
files+=sorted(p for p in (ROOT/'docs/research/driver-interface-20261115/assets').glob('micro-*') if p.is_file())
record={'schema_version':'micro-delivery-freeze-v1','status':'frozen','frozen_at_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'case_count':len(s['rows']),'required_cases':[x['source_case'] for x in s['rows']],'selections':s['selections'],'files':[{'path':rel(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in files],'cases':[{'source_case':x['source_case'],'result_sha256':x['result_sha256'],'manifest_sha256':x['manifest_sha256'],'waveform_gzip_sha256':x.get('waveform_gzip_sha256'),'combined_research_screen_pass':x['combined_research_screen_pass']} for x in s['rows']],'scope':'Source/compact evidence/figures frozen after DC, normal4, fault2, half-step, and predeclared 8192 holdout. Historical failed cases are intentionally retained. Raw waveform hashes are copied from the completed native-byte compression/readback receipts; independent audit verifies original traces. This is schematic research evidence, not physical/optical qualification.'}
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(rel(out),sha(out),'files',len(files),'cases',len(s['rows']))
