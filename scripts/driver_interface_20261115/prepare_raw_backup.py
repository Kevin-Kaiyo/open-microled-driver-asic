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
WORK=ROOT/'build/driver-interface-20261115'
RELEASE=WORK/'release'
OUT=ROOT/'evidence/driver-interface-20261115'
TARGET=512*1024**2
PDK={'design.ngspice','sm141064.ngspice'}

spec=importlib.util.spec_from_file_location('release_bundle',ROOT/'scripts/backup/release_bundle.py')
bundle=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundle)

def write_new(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')

def keep(path):
    return path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts and 'pdk' not in path.parts and path.name not in PDK and path.suffix in {'.json','.gz','.spice','.py','.log','.csv','.md','.npz','.txt'}

def tree(path):return [p for p in sorted(path.rglob('*')) if keep(p)]
def rel(path):return str(path.relative_to(ROOT))

def build_selection():
    scientific=json.loads((OUT/'scientific-validation.json').read_text())
    assert scientific.get('evidence_integrity_pass') and scientific.get('complete'), 'Freeze and independently audit all experiments first'
    cases=[]; groups=[]; paths=[]
    for lane in ['MicroLED','VCSEL']:
        base=WORK/lane
        manifests=sorted(base.rglob('manifest.json'))
        for p in manifests:
            if not (p.parent/'testbench.spice').exists():continue
            result=p.parent/'result.json'
            # Some preserved failed first attempts have a failure marker instead.
            cases.append(dict(path=rel(p.parent),result_present=result.exists(),scope='Includes preserved solver/model and functional failures; see scientific audit.'))
        files=tree(base)
        assert files, lane
        batch=[]; size=0; index=1
        for p in files:
            n=p.stat().st_size
            assert n <= bundle.MAX_FILE_BYTES, f'Single file too large for Release: {p}'
            if batch and size+n>TARGET:
                groups.append(dict(name=f'{lane}{index:02d}',paths=[rel(x) for x in batch]));batch=[];size=0;index+=1
            batch.append(p);size+=n
        if batch:groups.append(dict(name=f'{lane}{index:02d}',paths=[rel(x) for x in batch]))
    protocols=sorted(OUT.glob('*protocol*.json'))
    assert protocols
    groups.append(dict(name='protocols',paths=[rel(p) for p in protocols]))
    paths=[p for g in groups for p in g['paths']];assert len(paths)==len(set(paths))
    excluded_pdk=[p for lane in ['MicroLED','VCSEL'] for p in sorted((WORK/lane).rglob('*')) if p.is_file() and ('pdk' in p.parts or p.name in PDK)]
    dependencies=dict(previous_raw_releases=['driver-methods-20261111','driver-improvement-20261111','blue-emitter-speed-review-20261110'],
        public_scripts_reports_compact_evidence='Restore matching public Git milestone; report and validation artifacts are in Git, not this native-data bundle.',
        excluded_PDK=[dict(path=rel(p),bytes=p.stat().st_size,sha256=bundle.digest_file(p)) for p in excluded_pdk])
    counts={lane:sum('/'+lane+'/' in x['path'] for x in cases) for lane in ['MicroLED','VCSEL']}
    selection=dict(schema='driver-interface-native-selection-v1',scope='Frozen complete experiment lanes, including failures, execution snapshots, inputs, logs and compressed native waveforms. Bundles may divide a case at file boundaries; restore all volumes.',target_bytes=TARGET,case_counts=counts,cases=cases,groups=groups,dependencies=dependencies,
        exclusions=['PDK bytes','virtual environments','earlier-stage waveforms already archived','uncompressed duplicate waveform.dat','PDF/render temporaries','mutable report/audit/Release output','unrelated workspace status','Python bytecode'],no_external_action='Local preparation only; no upload, commit or source deletion.')
    snapshot={p:dict(bytes=(ROOT/p).stat().st_size,sha256=bundle.digest_file(ROOT/p)) for p in paths}
    measurement=dict(files=len(paths),bytes=sum(x['bytes'] for x in snapshot.values()),cases=len(cases),case_counts=counts,groups=[dict(name=g['name'],files=len(g['paths']),bytes=sum(snapshot[p]['bytes'] for p in g['paths'])) for g in groups],largest_file=max((dict(path=p,**v) for p,v in snapshot.items()),key=lambda x:x['bytes']))
    return selection,snapshot,measurement

def pack_and_verify():
    if (RELEASE/'selection.json').exists():raise RuntimeError('Existing selection: refuse blind restart; inspect partial archive state first.')
    selection,snapshot,measurement=build_selection()
    write_new(RELEASE/'selection.json',selection);write_new(RELEASE/'source-snapshot.json',snapshot);write_new(RELEASE/'measurement.json',measurement)
    print('MEASURED '+json.dumps(measurement,ensure_ascii=False),flush=True)
    manifest=OUT/'raw-backup-manifest.json';assets=RELEASE/'assets'
    data=bundle.pack(RELEASE/'selection.json','driver-interface-20261115',assets,manifest,root=ROOT,target_bytes=TARGET)
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
    receipt=dict(schema='driver-interface-local-raw-backup-verification-v1',verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
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
