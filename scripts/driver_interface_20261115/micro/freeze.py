#!/usr/bin/env python3
"""Bind a candidate to completed DC/continuous/fault/step controls before holdout."""
from pathlib import Path
import argparse,datetime,hashlib,json
ROOT=Path(__file__).resolve().parents[3];EV=ROOT/'evidence/driver-interface-20261115'
def read(p):return json.loads(p.read_text())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(route,variant):
 work=ROOT/f'build/driver-interface-20261115/MicroLED/{route}-{variant}';out=EV/f'micro-selection-{route}.json'
 if out.exists():
  old=read(out);assert old['variant']==variant and old['work_manifest_sha256']==sha(work/'manifest.json');return
 paths=['DC-L0','DC-L1','continuous-f4-net1.6-s40','fault-f2-net1.6-s40','fault-f2-net1.6-s80'];controls=[]
 for name in paths:
  p=work/name;r=read(p/'result.json');assert r['simulation_ok'] and not r.get('analysis_error') and r['terminal_pass'] and r['body_pass'],name
  if name.startswith('DC'):assert r['DC_pass']
  elif name.startswith('continuous'):assert r['steady_screen']['finite_window_pass'] and all(x['full_receiver']['research_margin_pass'] and x['first_frame_phase_receiver']['research_margin_pass'] for x in r['frames'])
  else:assert r['shutdown']['off_current_screen_pass'] and r['shutdown']['recovery_within_1us_verified'] and r['shutdown']['complete_recovered_frames'],name
  controls.append(dict(source_case=str(p.relative_to(ROOT)),result_sha256=sha(p/'result.json'),manifest_sha256=sha(p/'manifest.json'),deck_sha256=sha(p/'testbench.spice')))
 m=read(work/'manifest.json');record=dict(schema_version='micro-candidate-freeze-v1',frozen_at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),route=route,variant=variant,work_manifest_sha256=sha(work/'manifest.json'),inputs=m['inputs'],parameters=m['parameters'],controls=controls,holdout_protocol_sha256=sha(EV/'micro-protocol.json'),holdout_window=[8192,12928],no_retuning_after_reveal=True,allowed_deck_delta='Only external DATA0/DATA1 stimulus sources and case title; same fault timing, supplies, load, circuitry, solver settings, energy and receiver method.')
 out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(out)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('route');p.add_argument('variant');a=p.parse_args();run(a.route,a.variant)
