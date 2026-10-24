#!/usr/bin/env python3
"""Recover early manifest byte strings by exact SHA, never change case files.
Early runner versions kept only a mutable manifest index. All frozen source
bytes and executed runners survived. This enumerates only possible frozen
file inventories and source IDs, retaining a candidate iff its SHA is exact.
"""
from pathlib import Path
import hashlib,itertools,json
ROOT=Path(__file__).resolve().parents[2];W=ROOT/'build/pwm-reference-v2/20261024';I=W/'inputs';E=ROOT/'evidence/pwm-reference-v2/20261024'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base={n:{'source':f'build/pwm-robustness/20261024/inputs/{n}','sha256':sha(I/n)} for n in ['design.ngspice','sm141064.ngspice','dut.spice','microled.spice','pixel_pwm.v','pixel_safety.v','tb_safety.v','math.py']}
base['legacy_runner_original.py']={'source':'scripts/pwm_robustness/run.py','sha256':sha(I/'legacy_runner_original.py')}
base['old_loop_runner.py']={'source':'scripts/analog_v3/ac_macro.py','sha256':sha(I/'old_loop_runner.py')}
base['scope.json']={'source':'analog/pwm_reference_v2/scope.json','sha256':sha(I/'scope.json')}
extra=[p.name for p in sorted((ROOT/'analog/pwm_reference_v2').glob('*')) if p.suffix in ['.json','.spice'] and p.name!='scope.json' and (I/p.name).exists()]
targets={}
for p in W.glob('*/result.json'):
 d=json.loads(p.read_text())
 if 'case' in d:targets.setdefault(d['source_manifest_sha256'],[]).append(d['case']['name'])
out=I/'manifests';out.mkdir(exist_ok=True);known={p.stem for p in out.glob('*.json')};missing=set(targets)-known;found=[]
for sid in sorted(p.name for p in (I/'executed_sources').iterdir() if (p/'run.py').exists()):
 for bits in itertools.product([False,True],repeat=len(extra)):
  files=dict(base)
  for n,include in zip(extra,bits):
   if include:files[n]={'source':'analog/pwm_reference_v2/'+n,'sha256':sha(I/n)}
  files['legacy_runner_relocated.py']={'source':'path-relocated frozen legacy source; no circuit/stimulus function change','sha256':sha(I/'legacy_runner_relocated.py')}
  manifest={'baseline_commit':'112ba95969ac6a2141c305324ea694e7b96c0765','files':files,'executed_runner_source':f'build/pwm-reference-v2/20261024/inputs/executed_sources/{sid}/run.py','executed_runner_sha256':sid,'old_directories_read_only':True}
  blob=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode();h=hashlib.sha256(blob).hexdigest()
  if h in missing:
   (out/(h+'.json')).write_bytes(blob);missing.remove(h);found.append({'sha256':h,'cases':targets[h],'reconstruction':'Exact byte SHA matched recorded pre-existing case manifest SHA; source inventory recovered from retained frozen bytes.'})
result={'recovered':found,'still_missing':sorted(missing),'limitation':'Original mutable index file history was not preserved; these are explicitly reconstructed bytes with exact recorded SHA matches. No old deck, raw, result or executed source was modified.'}
(E/'manifest-recovery-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'recovered':len(found),'missing':sorted(missing)},indent=2))
