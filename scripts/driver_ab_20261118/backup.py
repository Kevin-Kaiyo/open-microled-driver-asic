"""Package original experiments and reconstruct their boundary to the frozen PDK and prior inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
TAG = 'driver-ab-20261118'
BUILD = ROOT/'build'/TAG
EV = ROOT/'evidence'/TAG
RELEASE = BUILD/'release'
MANIFEST = EV/'raw-backup-manifest.json'
sys.path.insert(0, str(ROOT/'scripts/backup'))
import release_bundle as bundle


def emit(path, data):
    path.write_text(json.dumps(data,indent=2)+'\n')


def selection():
    groups, links, models = [], {}, {}
    for lane in ['a','b','b_final','b_review','b-grid','b-final-grid']:
        paths = []
        for path in sorted((BUILD/lane).rglob('*')):
            if '__pycache__' in path.parts or path.name.startswith('.'):
                continue
            rel = str(path.relative_to(ROOT))
            if path.is_symlink():
                target = path.resolve(strict=True)
                target.relative_to(ROOT/'build')
                links[rel] = str(target.relative_to(ROOT))
            elif path.is_file():
                if 'pdk' in path.parts or path.suffix=='.ngspice':
                    models[rel]=bundle.digest_file(path)
                else:
                    paths.append(rel)
        if not paths:
            raise FileNotFoundError(lane)
        if lane=='b_final':
            fine=[p for p in paths if '/ss_hot_low-full-s80/' in p]
            groups.append(dict(name='b_final',paths=[p for p in paths if '/ss_hot_low-full-s80/' not in p]))
            if fine:groups.append(dict(name='b_final_fine',paths=fine))
        else:
            groups.append(dict(name=lane,paths=paths))
    return groups, dict(models=models, links=links, dependencies=['driver-interface-20261115','driver-pvt-20261117'])


def pack_lane(group):
    manifest=RELEASE/'parts'/f"{group['name']}.json"
    if manifest.exists():
        stored=bundle.read_manifest(manifest)
        items={f['path']:f for a in stored['assets'] for f in a['files']}
        assert set(items)==set(group['paths']), group['name']
        for path,f in items.items():
            assert (ROOT/path).stat().st_size==f['size'] and bundle.digest_file(ROOT/path)==f['sha256'],path
    else:
        bundle.pack({'groups':[group]},TAG,RELEASE/'assets',manifest,ROOT)
    return bundle.read_manifest(manifest)['assets']


def pack(lane=None):
    groups, deps = selection()
    RELEASE.mkdir(parents=True,exist_ok=True)
    if lane:
        group=next(g for g in groups if g['name']==lane)
        pack_lane(group)
        return
    assets=[asset for group in groups for asset in pack_lane(group)]
    emit(EV/'restore.json',deps)
    with MANIFEST.open('x') as stream:
        json.dump(dict(schema_version=1,tag=TAG,assets=assets),stream,indent=2)
        stream.write('\n')
    manifest=bundle.verify(MANIFEST, RELEASE/'assets')
    emit(RELEASE/'pack-verification.json',dict(
        manifest_sha256=bundle.digest_file(MANIFEST),
        archives=len(manifest['assets']),
        members=sum(len(a['files']) for a in manifest['assets']),
        archive_bytes=sum(a['size'] for a in manifest['assets']),
        local_archive_and_member_sha_verified=True))


def restore(model_dir, check):
    deps=json.loads((EV/'restore.json').read_text())
    models = {bundle.digest_file(p):p for p in model_dir.glob('*.ngspice') if p.is_file()}
    for rel, digest in deps['models'].items():
        path=ROOT/rel
        path.parent.resolve().relative_to(BUILD)
        if path.exists():
            assert not path.is_symlink() and bundle.digest_file(path)==digest, rel
        elif digest not in models:
            raise FileNotFoundError(f'Missing matching GF180 {digest}')
        elif not check:
            path.parent.mkdir(parents=True,exist_ok=True)
            with models[digest].open('rb') as src, path.open('xb') as dst:
                shutil.copyfileobj(src,dst)
    for rel,destination in deps['links'].items():
        path=ROOT/rel
        path.parent.resolve().relative_to(BUILD)
        target=(ROOT/destination).resolve(strict=True)
        target.relative_to(ROOT/'build')
        if path.is_symlink():
            assert path.resolve(strict=True)==target, rel
        elif path.exists():
            raise FileExistsError(path)
        elif not check:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.symlink_to(os.path.relpath(target,path.parent),target_is_directory=target.is_dir())
    print(f"Checked {len(deps['models'])} PDK identities and {len(deps['links'])} input links.")


def deliver():
    """Use same transfer/readback logic as the prior release, including each tar member."""
    import importlib.util
    sys.path.insert(0,str(ROOT/'scripts/driver_pvt_20261117'))
    src=ROOT/'scripts/driver_pvt_20261117/deliver_backup.py'
    spec=importlib.util.spec_from_file_location('pvt_delivery',src)
    transfer=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(transfer)
    transfer.TAG, transfer.RELEASE, transfer.MANIFEST = TAG, RELEASE, MANIFEST
    commit=(RELEASE/'source-commit.txt').read_text().strip()
    if transfer.api('git/ref/heads/main')['object']['sha'] != commit:
        raise ValueError('Remote main must match the reviewed source commit')
    if not transfer.release():
        transfer.command('gh','release','create',TAG,'--repo',transfer.REPO,'--draft','--target',commit,
                         '--title','MicroLED A/B · 重接、镜像精度与电流校准 · 2026-11-18',
                         '--notes-file',str(RELEASE/'release-notes.md'))
    transfer.wait_for_release()
    transfer.main()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    commands=p.add_subparsers(dest='action',required=True)
    commands.add_parser('pack').add_argument('--lane',choices=['a','b','b-grid','b_final','b_review','b-final-grid'])
    commands.add_parser('deliver')
    sub=commands.add_parser('restore-inputs')
    sub.add_argument('--model-dir',type=Path,required=True)
    sub.add_argument('--check-only',action='store_true')
    args=p.parse_args()
    if args.action=='pack':
        pack(args.lane)
    elif args.action=='deliver':
        deliver()
    else:
        restore(args.model_dir,args.check_only)
