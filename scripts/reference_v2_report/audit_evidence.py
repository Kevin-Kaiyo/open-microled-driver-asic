#!/usr/bin/env python3
"""Independent read-back of new simulation files, without importing their evaluators."""
from pathlib import Path
import argparse,datetime,gzip,hashlib,json
ROOT=Path(__file__).resolve().parents[2]
def sha(p,unzip=False):
 h=hashlib.sha256()
 with (gzip.open(p,'rb') if unzip else p.open('rb')) as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def audit(result,unzip):
 j=json.loads(result.read_text());d=result.parent;checks=[]
 def check(label,p,wanted,compressed=False):
  good=p.is_file() and sha(p,compressed)==wanted;checks.append({'check':label,'path':str(p.relative_to(ROOT)),'passed':good})
 if 'deck_sha256' not in j:return None
 deck=d/'testbench.spice'
 if not deck.exists():deck=d/'bench.spice'
 check('deck',deck,j['deck_sha256'])
 if 'log_sha256' in j:
  log=d/'ngspice.log'
  if not log.exists() and j.get('log'):log=ROOT/j['log']
  check('solver log',log,j['log_sha256'])
 if j.get('waveform_sha256'):
  candidates=[ROOT/j['waveform']] if j.get('waveform') else [p for p in d.iterdir() if p.is_file() and p.suffix in ['.gz','.dat'] and sha(p)==j['waveform_sha256']]
  if len(candidates)!=1:
   checks.append({'check':'waveform hash resolves uniquely','passed':False});candidates=[d/'MISSING_WAVEFORM']
  p=candidates[0];check('compressed waveform',p,j['waveform_sha256'])
  if unzip:check('waveform payload',p,j['uncompressed_sha256'],p.suffix=='.gz')
 if j.get('gzip_sha256'):
  candidates=[p for p in d.glob('*.gz') if sha(p)==j['gzip_sha256']]
  if len(candidates)!=1:checks.append({'check':'unique gzip waveform','passed':False})
  elif unzip:check('waveform payload',candidates[0],j['raw_sha256'],True)
 if j.get('runner_source_sha256'):check('executed runner',ROOT/j['runner_source'],j['runner_source_sha256'])
 return {'result':str(result.relative_to(ROOT)),'completed':j.get('completed',j.get('simulation_ok')),'exit_code':j.get('exit_code'),'electrical_passed':j.get('passed'),'checks':checks,'identity_passed':all(x['passed'] for x in checks)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--unzip',action='store_true');ap.add_argument('--out',required=True);a=ap.parse_args()
 rows=[]
 for folder in ['build/pwm-reference-v2','build/nrz-reference-v2']:
  for p in sorted((ROOT/folder).rglob('result.json')):
   if any(x in p.parts for x in ['inputs','execution-sources','executed_sources']):continue
   row=audit(p,a.unzip)
   if row:rows.append(row)
 data={'created':datetime.datetime.now().isoformat(),'scope':'Byte identity only. Electrical results including failures retained; no pass inferred from simulator exit code. Read after runners stop for a frozen final audit.','decompressed_all_recorded_waveforms':a.unzip,'result_count':len(rows),'identity_passed':all(r['identity_passed'] for r in rows),'rows':rows,'source_sha256':sha(Path(__file__))}
 p=ROOT/a.out;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in data.items() if k!='rows'},ensure_ascii=False))
 for r in rows:
  if not r['identity_passed']:print(json.dumps(r,ensure_ascii=False))
 raise SystemExit(0 if data['identity_passed'] else 1)
if __name__=='__main__':main()
