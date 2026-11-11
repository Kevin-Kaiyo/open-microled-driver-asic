#!/usr/bin/env python3
"""Prepare and verify local-only frozen native-data bundles; never upload/delete."""
from pathlib import Path
import argparse
import datetime
import importlib.util
import json
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'build/driver-methods-20261111'
RELEASE=WORK/'release'
OUT=ROOT/'evidence/driver-methods-20261111'
TARGET=512*1024**2
PDK={'design.ngspice','sm141064.ngspice'}

spec=importlib.util.spec_from_file_location('release_bundle',ROOT/'scripts/backup/release_bundle.py')
bundle=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundle)

def write_new(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')

def keep(path):
    return path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts and 'pdk' not in path.parts and path.name not in PDK and path.suffix in {'.json','.gz','.spice','.py','.log','.csv','.md'}

def tree(path):return [p for p in sorted(path.rglob('*')) if keep(p)]
def rel(path):return str(path.relative_to(ROOT))

def build_selection():
    units={'A':[],'B':[],'VCSEL':[]};workspaces=set();case_rows=[]
    for result in sorted(WORK.rglob('result.json')):
        if 'release' in result.relative_to(WORK).parts:continue
        r=json.loads(result.read_text());folder=result.parent
        if not r.get('simulation_ok') or r.get('analysis_error'):
            raise RuntimeError(f'Unexpected unfinished/failed-solver case; inspect explicitly: {result}')
        if folder.parent.name=='cases':
            group=r['case']['route'];assert group in 'AB';workspaces.add(folder.parent.parent)
        elif 'VCSEL' in result.parts:group='VCSEL'
        else:raise RuntimeError(f'Unclassified result: {result}')
        files=tree(folder);size=sum(p.stat().st_size for p in files)
        assert size<TARGET, 'This stage measured case units must fit 512 MiB; inspect a new oversized case before changing policy'
        units[group].append(files)
        case_rows.append(dict(group=group,path=rel(folder),files=len(files),bytes=size,simulation_ok=r['simulation_ok'],receiver_failures_included=True))
    assert sum(x['group'] in 'AB' for x in case_rows)==20
    assert sum(x['group']=='VCSEL' for x in case_rows)==22
    # Explicit bounded-volume groups preserve each case as an atomic unit.
    groups=[]
    for name,case_units in units.items():
        batch=[];size=0;index=1
        for files in case_units:
            added=sum(p.stat().st_size for p in files)
            if batch and size+added>TARGET:
                groups.append(dict(name=f'{name}{index:02d}',paths=[rel(p) for p in batch]));batch=[];size=0;index+=1
            batch.extend(files);size+=added
        if batch:groups.append(dict(name=f'{name}{index:02d}',paths=[rel(p) for p in batch]))
    frozen=[]
    for work in sorted(workspaces):
        for part in ['inputs','execution-sources']:frozen.extend(tree(work/part))
        for name in ['manifest.json','stimulus.json']:frozen.append(work/name)
    frozen.extend(tree(WORK/'link-sensitivity'))
    frozen.extend(tree(WORK/'micro-orchestration'))
    for name in ['link-sensitivity.log','link-sensitivity-cache-check.log']:
        p=WORK/name
        if p.exists():frozen.append(p)
    for name in ['micro-protocol.json','vcsel-holdout-protocol.json']:
        p=OUT/name;assert p.exists();frozen.append(p)
    frozen=sorted(set(frozen));assert all(keep(p) for p in frozen)
    groups.append(dict(name='frozen-inputs-diagnostics',paths=[rel(p) for p in frozen]))
    paths=[p for g in groups for p in g['paths']];assert len(paths)==len(set(paths))
    # PDK identity retained for restore, but the PDK bytes are deliberately excluded.
    excluded_pdk=[p for p in sorted(WORK.rglob('*')) if p.is_file() and ('pdk' in p.parts or p.name in PDK)]
    dependencies=dict(previous_raw_releases=['driver-improvement-20261111','blue-emitter-speed-review-20261110'],
        public_scripts_reports_compact_evidence='Restore matching public Git milestone; current report/validator output is not captured in this raw bundle.',
        excluded_PDK=[dict(path=rel(p),bytes=p.stat().st_size,sha256=bundle.digest_file(p)) for p in excluded_pdk])
    selection=dict(schema='driver-methods-native-selection-v1',scope='All 20 MicroLED and 22 VCSEL completed new cases, including successful solves failing receiver/stress screens; atomic case units plus frozen input/execution/diagnostic/protocol/orchestration data.',
        target_bytes=TARGET,case_counts=dict(MicroLED=20,VCSEL=22),cases=case_rows,groups=groups,dependencies=dependencies,
        exclusions=['PDK bytes','virtual environments','old-stage waveforms restorable from earlier releases','PDF/render temporaries','mutable scientific-validator/report/release output','unrelated workspace-before status','Python bytecode'],
        no_external_action='Local preparation only; no upload, Git commit or source deletion.')
    source_snapshot={p:dict(bytes=(ROOT/p).stat().st_size,sha256=bundle.digest_file(ROOT/p)) for p in paths}
    measurement=dict(files=len(paths),bytes=sum(x['bytes'] for x in source_snapshot.values()),cases=42,
        groups=[dict(name=g['name'],files=len(g['paths']),bytes=sum(source_snapshot[p]['bytes'] for p in g['paths'])) for g in groups],
        largest_case=max(case_rows,key=lambda x:x['bytes']),largest_file=max((dict(path=p,**v) for p,v in source_snapshot.items()),key=lambda x:x['bytes']))
    return selection,source_snapshot,measurement

def pack_and_verify():
    if (RELEASE/'selection.json').exists():raise RuntimeError('Existing selection: refuse blind restart; inspect partial archive state first.')
    selection,snapshot,measurement=build_selection()
    write_new(RELEASE/'selection.json',selection);write_new(RELEASE/'source-snapshot.json',snapshot);write_new(RELEASE/'measurement.json',measurement)
    print('MEASURED '+json.dumps(measurement,ensure_ascii=False),flush=True)
    manifest=OUT/'raw-backup-manifest.json';assets=RELEASE/'assets'
    data=bundle.pack(RELEASE/'selection.json','driver-methods-20261111',assets,manifest,root=ROOT,target_bytes=TARGET)
    # pack verifies source bytes while streaming; independently compare that
    # result with the pre-pack snapshot and then re-read the current sources.
    seen={}
    for asset in data['assets']:
        assert asset['size']<2*1024**3
        for item in asset['files']:
            assert snapshot[item['path']]['bytes']==item['size']
            assert snapshot[item['path']]['sha256']==item['sha256'], f'Pre-pack source hash changed: {item["path"]}'
            seen[item['path']]=item
    assert set(seen)==set(snapshot)
    for path,value in snapshot.items():
        if (ROOT/path).stat().st_size!=value['bytes'] or bundle.digest_file(ROOT/path)!=value['sha256']:
            raise RuntimeError(f'Source changed during archive preparation: {path}')
    verified=bundle.verify(manifest,assets)
    receipt=dict(schema='driver-methods-local-raw-backup-verification-v1',verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        local_only=True,uploaded=False,source_removed=False,member_SHA256_verified=True,prepack_and_postpack_source_SHA256_identical=True,
        source_files=len(snapshot),source_bytes=measurement['bytes'],case_counts=selection['case_counts'],assets=len(verified['assets']),archive_bytes=sum(a['size'] for a in verified['assets']),
        manifest=rel(manifest),manifest_sha256=bundle.digest_file(manifest),selection=rel(RELEASE/'selection.json'),selection_sha256=bundle.digest_file(RELEASE/'selection.json'),
        source_snapshot=rel(RELEASE/'source-snapshot.json'),source_snapshot_sha256=bundle.digest_file(RELEASE/'source-snapshot.json'),preparation_script_sha256=bundle.digest_file(Path(__file__)),bundle_tool_sha256=bundle.digest_file(ROOT/'scripts/backup/release_bundle.py'),
        scope='Archive SHA and every logical tar member checked locally; this is not remote backup or permission to remove source data.')
    write_new(OUT/'raw-backup-verification.json',receipt)
    print('VERIFIED '+json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--measure-only',action='store_true');a=p.parse_args()
    if a.measure_only:
        _,_,measurement=build_selection();print(json.dumps(measurement,ensure_ascii=False,indent=2))
    else:pack_and_verify()
