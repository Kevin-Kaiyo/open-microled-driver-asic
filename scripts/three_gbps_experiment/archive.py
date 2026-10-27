#!/usr/bin/env python3
"""Explicit milestone pack/readback. No upload, overwrite or original cleanup."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, subprocess, urllib.request

ROOT=Path(__file__).resolve().parents[2]
TAG='three-gbps-experiment-20261027'
REPO='Kevin-Kaiyo/open-microled-driver-asic'
STAGE=ROOT/'build'/('github-sync-'+TAG)
EV=ROOT/'evidence/three-gbps-experiment-20261027'

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()

def emit(p,x):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    with Path(p).open('x') as f: f.write(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def gh(*args):
    return json.loads(subprocess.check_output(['gh',*args],text=True))

def bundle():
    spec=importlib.util.spec_from_file_location('bundle',ROOT/'scripts/backup/release_bundle.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def pack():
    assert not STAGE.exists(),'Immutable stage already exists'
    files=[];excluded=[]
    for p in sorted((ROOT/'build'/TAG).rglob('*')):
        if p.is_symlink(): raise ValueError('Review symlink: '+str(p))
        if not p.is_file():continue
        rel=str(p.relative_to(ROOT))
        if p.suffix=='.pyc' or '__pycache__' in p.parts:
            excluded.append(dict(path=rel,reason='Rebuildable Python bytecode'));continue
        if p.name in ['frontiers-full.html','frontiers-text.txt']:
            excluded.append(dict(path=rel,sha256=sha(p),reason='Original web-page snapshot retained locally; primary DOI and licensed selected figures available in report'));continue
        files.append(rel)
    assert files
    groups=[dict(name=g,paths=[p for p in files if (p.endswith(('.dat','.dat.gz','.npz')))==(g=='waveforms')]) for g in ['metadata','waveforms']]
    groups=[g for g in groups if g['paths']]
    STAGE.mkdir();selection={'groups':groups}
    emit(STAGE/'selection.json',selection)
    manifest=STAGE/(TAG+'.json')
    m=bundle();m.pack(selection,TAG,STAGE/'assets',manifest,root=ROOT,target_bytes=128*1024**2)
    m.verify(manifest,STAGE/'assets')
    index=json.loads(manifest.read_text())
    receipt=dict(tag=TAG,repository=REPO,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                 manifest_sha256=sha(manifest),files=len(files),original_bytes=sum((ROOT/p).stat().st_size for p in files),
                 archives=[dict(name=a['name'],sha256=a['sha256'],size=a['size']) for a in index['assets']],
                 exclusions=excluded,local_archive_members_verified=True,originals_removed=False,
                 boundary='New experiment build tree only. Prior milestones, full PDK, installed runtimes and downloaded full HTML are not included.')
    emit(EV/'archive-local.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

def identity(expected):
    repo=gh('repo','view',REPO,'--json','nameWithOwner,isPrivate')
    assert repo=={'isPrivate':False,'nameWithOwner':REPO}
    ref=gh('api',f'repos/{REPO}/git/ref/tags/{TAG}')['object']
    while ref['type']=='tag':ref=gh('api',f'repos/{REPO}/git/tags/{ref["sha"]}')['object']
    assert ref['type']=='commit' and ref['sha']==expected
    release=gh('api',f'repos/{REPO}/releases/tags/{TAG}')
    assert not release['draft'] and release['tag_name']==TAG
    return release

def readback():
    local=json.loads((EV/'archive-local.json').read_text());manifest=STAGE/(TAG+'.json')
    assert sha(manifest)==local['manifest_sha256']
    release=identity(local['source_commit'])
    expected=local['archives']+[dict(name=manifest.name,sha256=sha(manifest),size=manifest.stat().st_size)]
    remote={x['name']:x for x in release['assets']};checked=[]
    for x in expected:
        a=remote[x['name']];assert a['state']=='uploaded' and a['size']==x['size']
        if a.get('digest'):assert a['digest']=='sha256:'+x['sha256']
        url=f'https://github.com/{REPO}/releases/download/{TAG}/{x["name"]}'
        assert a['browser_download_url']==url
        h=hashlib.sha256();size=0
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ResearchEvidenceReadback/1.0'}),timeout=60) as stream:
            for block in iter(lambda:stream.read(1048576),b''):h.update(block);size+=len(block)
        assert size==x['size'] and h.hexdigest()==x['sha256']
        checked.append(dict(x,asset_id=a['id'],updated_at=a['updated_at'],download_readback_verified=True))
        print('Verified '+x['name'],flush=True)
    after=identity(local['source_commit']);assert after['id']==release['id']
    newer={a['name']:a for a in after['assets']}
    for x in checked:
        a=newer[x['name']];assert a['id']==x['asset_id'] and a['updated_at']==x['updated_at'] and a['size']==x['size']
    emit(EV/'archive-remote.json',dict(tag=TAG,source_commit=local['source_commit'],manifest_sha256=sha(manifest),
        release_url=release['html_url'],all_expected_assets_verified=True,files=checked,originals_removed=False,
        boundary='Remote bytes match locally member-verified archives. This does not claim an independent machine rerun.'))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['pack','readback']);args=ap.parse_args()
    {'pack':pack,'readback':readback}[args.action]()
