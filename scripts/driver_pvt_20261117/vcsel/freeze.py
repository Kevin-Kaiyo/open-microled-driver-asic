#!/usr/bin/env python3
"""Package compact validated records and freeze this lane without Git/Release actions."""
from pathlib import Path
from collections import Counter
import shutil,sys
sys.dont_write_bytecode=True
import run,report_assets

def main():
 v=run.read(run.EV/'validation.json');assert v['status']=='passed' and v['case_count']==89
 required=[];counts=Counter()
 for row in v['cases']:
  source=run.ROOT/row['case'];m=run.read(source/'manifest.json');cfg=m['pvt_config'];counts[(cfg['variant'],m['kind'])]+=1
  target=run.EV/'cases'/source.relative_to(run.BUILD);target.mkdir(parents=True,exist_ok=True)
  for name in ['manifest.json','result.json','analysis.json']:
   if (source/name).exists():shutil.copy2(source/name,target/name);assert run.sha(source/name)==run.sha(target/name)
  required.append(dict(case=row['case'],manifest_sha256=run.sha(source/'manifest.json'),result_sha256=run.sha(source/'result.json'),analysis_sha256=run.sha(source/'analysis.json') if (source/'analysis.json').exists() else None,waveform=row['waveform']))
 expected={('frozen','dc'):18,('frozen','short'):9,('frozen','full'):3,('cmd-r100','dc'):10,('cmd-r100','short'):5,('cmd-r330','dc'):18,('cmd-r330','short'):9,('cmd-r330','full'):7,('cmd-r330-atten75','dc'):6,('cmd-r330-atten75','short'):3,('cmd-r330-atten75','full'):1};assert counts==expected
 run.summarize();s=run.read(run.EV/'summary.json');s.update(status='frozen',case_count=89,validation_sha256=run.sha(run.EV/'validation.json'),selection_sha256=run.sha(run.EV/'selection.json'),counts={f'{a}/{b}':n for (a,b),n in counts.items()});run.emit(run.EV/'summary.json',s)
 report_assets.main()
 scriptdir=Path(__file__).parent;assets=report_assets.OUT
 files=list(scriptdir.glob('*.py'))+list(scriptdir.glob('*.md'))+[p for p in run.EV.rglob('*') if p.is_file() and p.name!='freeze.json']+[p for p in assets.glob('vcsel-*') if p.is_file()]
 q=dict(schema='vcsel-pvt-freeze-v1',status='frozen',script_sha256=run.sha(Path(__file__)),scope='89newcases:52DC+26short+11full including2halfstep and1holdout; plus1explicit reused nominal full frame. No new silicon/optical measurement,physicallayout,PHYcompliance or all-corner fullRXqualification.',required_cases=required,counts={f'{a}/{b}':n for (a,b),n in counts.items()},files={str(p.relative_to(run.ROOT)):run.sha(p) for p in sorted(files)},shared_input_note='Archive build/driver-pvt-20261117/vcsel/_inputs plus relative case symlinks,or explicitly dereference;case-only archives would lose sharedmodels.',shared_inputs={str(p.relative_to(run.ROOT)):run.sha(p) for p in (run.BUILD/'_inputs').glob('*')},exclusions=['NoGit/Release action by thislane','Large original nativegzip remainsbuild; compactsource/records stay evidence','Current/optical load fixed;MOS PVT only','Frozen6.4SS and8.8TT confirmations do not establish everycornerfullframepass'])
 run.emit(run.EV/'freeze.json',q);print('FROZEN',len(required),'cases',len(q['files']),'compact/source/assets files')
if __name__=='__main__':main()
