#!/usr/bin/env python3
"""Select only successful raw cases and their public frozen inputs for backup."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/blue-emitter-speed-review-20261110'
WORK=ROOT/'build/blue-emitter-speed-review-20261110'
PDK={'design.ngspice','sm141064.ngspice'}

def selected(path):
    if not path.is_file() or path.is_symlink():return False
    if '__pycache__' in path.parts or 'pdk' in path.parts:return False
    if path.name in PDK or path.suffix in ['.pyc','.dat']:return False
    # No literature originals, environments or intermediate graphical caches.
    return path.suffix in ['.json','.gz','.spice','.py','.log','.csv','.txt']

def tree(path):
    return [str(p.relative_to(ROOT)) for p in sorted(path.rglob('*')) if selected(p)]

def main():
    data=json.loads((EV/'speed-sweep-all.json').read_text())
    new=[];old=[]
    for row in data['rows']:
        base=ROOT/row['source_case']
        target=new if base.is_relative_to(WORK) else old
        target.extend(tree(base))
    sources=[]
    for base in [ROOT/'build/microled-dynamic-v1/electrical/run-r1',WORK/'microled']:
        for folder in ['inputs','execution-sources']:sources.extend(tree(base/folder))
        for name in ['manifest.json','stimulus.json','plan.json']:
            p=base/name
            if p.is_file():sources.append(str(p.relative_to(ROOT)))
    # Frozen VCSEL baseline contains required deck, manifest and driver snapshots
    # under each selected original case; model files are restored via PDK lock.
    groups=[{'name':name,'paths':sorted(set(paths))} for name,paths in [('new-cases',new),('historic-anchors',old),('frozen-inputs',sources)]]
    flat=[p for g in groups for p in g['paths']]
    assert len(flat)==len(set(flat)),'Cross-group overlap'
    assert all(selected(ROOT/p) for p in flat)
    assert not any('/literature/' in p or '/report-venv/' in p for p in flat)
    out=WORK/'release';out.mkdir(exist_ok=True)
    selection={'scope':'All source cases in final speed-sweep-all.json, their native gzip traces and public frozen metadata. Excludes PDK copies, Python environments/bytecode, paper/vendor originals and cancelled/unselected experiments. No local deletion.', 'groups':groups}
    (out/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    print(json.dumps({'files':len(flat),'bytes':sum((ROOT/p).stat().st_size for p in flat),'groups':[(g['name'],len(g['paths'])) for g in groups]}))

if __name__=='__main__':main()
