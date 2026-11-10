#!/usr/bin/env python3
"""Select completed new native experiments, including screening failures."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'build/ab-improvement-20261111'
PDK={'design.ngspice','sm141064.ngspice'}
def keep(p):
    return (p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts
            and 'pdk' not in p.parts and p.name not in PDK
            and p.suffix in ['.json','.gz','.spice','.py','.log','.csv','.md'])
def tree(p):return [str(f.relative_to(ROOT)) for f in sorted(p.rglob('*')) if keep(f)]
def main():
    groups={k:[] for k in ['A-cases','B-cases','VCSEL-cases','frozen-inputs','diagnostics']}
    workspaces=set();cases=[]
    for result in sorted(WORK.rglob('result.json')):
        if 'release' in result.parts:continue
        r=json.loads(result.read_text())
        if not r.get('simulation_ok') or r.get('analysis_error'):continue
        folder=result.parent
        if folder.parent.name=='cases':
            route=r['case']['route'];assert route in 'AB'
            groups[route+'-cases'].extend(tree(folder));workspaces.add(folder.parents[1]);cases.append(str(folder.relative_to(ROOT)))
        elif 'VCSEL' in folder.parts or 'VCSEL-holdout' in folder.parts:
            groups['VCSEL-cases'].extend(tree(folder));cases.append(str(folder.relative_to(ROOT)))
    for work in sorted(workspaces):
        for name in ['inputs','execution-sources']:groups['frozen-inputs'].extend(tree(work/name))
        for name in ['manifest.json','stimulus.json']:
            p=work/name
            if p.exists():groups['frozen-inputs'].append(str(p.relative_to(ROOT)))
    for folder in ['A','B','audit']:
        for p in (WORK/folder).glob('*'):
            if keep(p) and p.suffix in ['.json','.csv','.py','.md']:
                groups['diagnostics'].append(str(p.relative_to(ROOT)))
    output=[{'name':name,'paths':sorted(set(paths))} for name,paths in groups.items() if paths]
    paths=[p for g in output for p in g['paths']]
    assert len(paths)==len(set(paths))
    assert all(keep(ROOT/p) for p in paths)
    release=WORK/'release';release.mkdir(exist_ok=True)
    selection=dict(scope='All completed new native A/B and VCSEL cases, including DC calibration and valid solves failing receiver/stress screens; per-case frozen inputs and teaching diagnostics.',
        dependencies='Historical reference curves and baseline raw data are restored from blue-emitter-speed-review-20261110. Matching PDK files restored separately with pinned SHA256. Public scripts/reports/compact evidence are in Git.',
        exclusions=['PDK copies','environments','incomplete or failed solver runs retained locally','original third-party papers','uncompressed intermediate data','unrelated workspace changes'],
        cases=cases,groups=output)
    (release/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    print(json.dumps({'cases':len(cases),'files':len(paths),'bytes':sum((ROOT/p).stat().st_size for p in paths),'groups':[(x['name'],len(x['paths'])) for x in output]}))
if __name__=='__main__':main()
