#!/usr/bin/env python3
"""Explicit milestone backup: local pack or rolling draft upload/readback; never remove originals."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, subprocess, urllib.request

ROOT=Path(__file__).resolve().parents[2]
TAG='vcsel-reference-microled-dynamics-20261029'
REPO='Kevin-Kaiyo/open-microled-driver-asic'
STAGE=ROOT/'build'/('github-sync-'+TAG)
EV=ROOT/'evidence/vcsel-robustness-20261029'

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()

def emit(p,x):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    with Path(p).open('x') as f: f.write(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def emit_or_match(p,x):
    if Path(p).exists():assert json.loads(Path(p).read_text())==x,'Refusing changed receipt: '+str(p)
    else:emit(p,x)

def gh(*args):
    return json.loads(subprocess.check_output(['gh',*args],text=True))

def bundle():
    spec=importlib.util.spec_from_file_location('bundle',ROOT/'scripts/backup/release_bundle.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def selected_files():
    files=[];excluded=[]
    for folder in ['build/vcsel-robustness-20261029','build/microled-dynamic-20261029']:
      for p in sorted((ROOT/folder).rglob('*')):
        if p.is_symlink(): raise ValueError('Review symlink: '+str(p))
        if not p.is_file():continue
        rel=str(p.relative_to(ROOT))
        if p.suffix=='.pyc' or '__pycache__' in p.parts:
            excluded.append(dict(path=rel,reason='Rebuildable Python bytecode'));continue
        if folder.endswith('microled-dynamic-20261029'):
            # Only the exact public dataset workbooks/metadata are distributable here. Original papers,
            # screenshots and private evidence excerpts stay local, even inside build/.
            allowed=ROOT/'evidence/microled-dynamic-20261029/release-allowlist.json'
            allow=json.loads(allowed.read_text())['files']
            if rel not in allow:
                excluded.append(dict(path=rel,sha256=sha(p),reason='Not in the explicit licensed MicroLED data allowlist; retained locally'));continue
        files.append(rel)
    assert files
    return files,excluded

def pack():
    assert not STAGE.exists(),'Immutable stage already exists'
    files,excluded=selected_files()
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
                 boundary='New VCSEL build cases plus explicitly licensed MicroLED dataset files only. Prior milestone dependencies, full PDK, installed runtimes, private paper excerpts and full papers are excluded. See per-file exclusions; originals remain local.')
    emit(EV/'archive-local.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

def api_readback(asset,expected):
    """Read authenticated remote bytes, including draft assets, without saving a second copy."""
    assert asset['state']=='uploaded' and asset['size']==expected['size']
    if asset.get('digest'):assert asset['digest']=='sha256:'+expected['sha256']
    command=['gh','api',f'repos/{REPO}/releases/assets/{asset["id"]}','-H','Accept: application/octet-stream']
    p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    h=hashlib.sha256();size=0
    for block in iter(lambda:p.stdout.read(1048576),b''):h.update(block);size+=len(block)
    error=p.stderr.read();code=p.wait()
    assert code==0, error.decode(errors='replace')[:500]
    assert size==expected['size'] and h.hexdigest()==expected['sha256'],asset['name']
    return dict(name=asset['name'],size=size,sha256=h.hexdigest(),asset_id=asset['id'],updated_at=asset['updated_at'],download_readback_verified=True,readback_method='Authenticated GitHub asset API byte stream')

def rolling():
    """Pack, verify, upload and read back one batch at a time; remove only verified staging copies.

    Requires an explicitly created draft Release. Original build files are never removed.
    Per-part manifests and receipts allow resuming a network interruption without overwriting evidence.
    """
    files,excluded=selected_files();STAGE.mkdir(exist_ok=True)
    release=gh('api',f'repos/{REPO}/releases/tags/{TAG}')
    assert release['draft'],'Use a draft until every member and archive has been verified'
    assert gh('repo','view',REPO,'--json','nameWithOwner,isPrivate')=={'isPrivate':False,'nameWithOwner':REPO}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    plans=[]
    for group in ['metadata','waveforms']:
        batch=[];size=0
        for rel in files:
            if rel.endswith(('.dat','.dat.gz','.npz')) != (group=='waveforms'):continue
            n=(ROOT/rel).stat().st_size
            if batch and size+n>128*1024**2:plans.append((group,batch));batch=[];size=0
            batch.append(rel);size+=n
        if batch:plans.append((group,batch))
    snapshot={p:dict(size=(ROOT/p).stat().st_size,sha256=sha(ROOT/p)) for p in files}
    plan=dict(source_commit=commit,release_id=release['id'],parts=[dict(group=g,paths=p) for g,p in plans],files=snapshot,exclusions=excluded)
    pp=STAGE/'rolling-plan.json'
    if pp.exists():assert json.loads(pp.read_text())==plan,'Inputs changed since first batch'
    else:emit(pp,plan)
    m=bundle();assets=[];checked=[]
    for i,(group,paths) in enumerate(plans,1):
        for rel in paths:assert (ROOT/rel).stat().st_size==snapshot[rel]['size'] and sha(ROOT/rel)==snapshot[rel]['sha256'],'Frozen input changed: '+rel
        part=f'{TAG}-s{i:03}';mf=STAGE/(part+'.json');receipt=STAGE/(part+'-readback.json')
        if not mf.exists():m.pack({'groups':[dict(name=group,paths=paths)]},part,STAGE/'assets',mf,root=ROOT,target_bytes=128*1024**2)
        index=json.loads(mf.read_text());assets.extend(index['assets'])
        if receipt.exists():
            prior=json.loads(receipt.read_text());now={a['name']:a for a in gh('api',f'repos/{REPO}/releases/{release["id"]}')['assets']}
            for x in prior:
                a=now[x['name']];assert (a['id'],a['updated_at'],a['size'])==(x['asset_id'],x['updated_at'],x['size'])
                if a.get('digest'):assert a['digest']=='sha256:'+x['sha256']
                staged=STAGE/'assets'/x['name']
                if staged.exists():assert sha(staged)==x['sha256'];staged.unlink()
            checked.extend(prior);continue
        m.verify(mf,STAGE/'assets');part_checked=[]
        for a in index['assets']:
            current={x['name']:x for x in gh('api',f'repos/{REPO}/releases/{release["id"]}')['assets']}
            if a['name'] not in current:subprocess.run(['gh','release','upload',TAG,str(STAGE/'assets'/a['name']),'--repo',REPO],check=True)
            current={x['name']:x for x in gh('api',f'repos/{REPO}/releases/{release["id"]}')['assets']}
            part_checked.append(api_readback(current[a['name']],a))
        emit(receipt,part_checked);checked.extend(part_checked)
        for a in index['assets']:
            p=STAGE/'assets'/a['name'];assert sha(p)==a['sha256'];p.unlink()  # Verified temporary archive only; never an original.
        print(f'REMOTE VERIFIED {i}/{len(plans)}; original inputs retained',flush=True)
    for rel,item in snapshot.items():assert (ROOT/rel).stat().st_size==item['size'] and sha(ROOT/rel)==item['sha256'],'Input changed during archive: '+rel
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==commit
    manifest=STAGE/(TAG+'.json');full=dict(schema_version=1,tag=TAG,assets=assets)
    if manifest.exists():assert json.loads(manifest.read_text())==full
    else:emit(manifest,full)
    m.read_manifest(manifest)
    current={x['name']:x for x in gh('api',f'repos/{REPO}/releases/{release["id"]}')['assets']}
    if manifest.name not in current:subprocess.run(['gh','release','upload',TAG,str(manifest),'--repo',REPO],check=True)
    current={x['name']:x for x in gh('api',f'repos/{REPO}/releases/{release["id"]}')['assets']}
    checked.append(api_readback(current[manifest.name],dict(size=manifest.stat().st_size,sha256=sha(manifest))))
    local=dict(tag=TAG,repository=REPO,source_commit=commit,manifest_sha256=sha(manifest),files=len(files),original_bytes=sum((ROOT/p).stat().st_size for p in files),archives=[{k:a[k] for k in ['name','sha256','size']} for a in assets],exclusions=excluded,local_archive_members_verified=True,originals_removed=False,verified_temporary_archives_removed=True,boundary='Every selected VCSEL build file plus explicitly licensed MicroLED workbooks/metadata. Original inputs and failures retained. Full PDK, runtimes and private paper originals excluded. Batches locally member-verified, remotely byte-verified, then temporary archive copies removed to limit disk use.')
    emit_or_match(EV/'archive-local.json',local);emit_or_match(STAGE/'rolling-readback.json',dict(release_id=release['id'],source_commit=commit,files=checked))
    print('All draft assets verified; publish the same Release, then run finalize-rolling',flush=True)

def finalize_rolling():
    local=json.loads((EV/'archive-local.json').read_text());saved=json.loads((STAGE/'rolling-readback.json').read_text())
    release=identity(local['source_commit']);assert release['id']==saved['release_id']
    now={a['name']:a for a in release['assets']}
    for x in saved['files']:
        a=now[x['name']];assert (a['id'],a['updated_at'],a['size'])==(x['asset_id'],x['updated_at'],x['size'])
        if a.get('digest'):assert a['digest']=='sha256:'+x['sha256']
    manifest=STAGE/(TAG+'.json');assert sha(manifest)==local['manifest_sha256']
    with urllib.request.urlopen(f'https://github.com/{REPO}/releases/download/{TAG}/{manifest.name}',timeout=60) as f:assert hashlib.sha256(f.read()).hexdigest()==local['manifest_sha256']
    emit(EV/'archive-remote.json',dict(tag=TAG,source_commit=local['source_commit'],manifest_sha256=local['manifest_sha256'],release_url=release['html_url'],all_expected_assets_verified=True,files=saved['files'],originals_removed=False,publication_identity_verified=True,boundary='All archive bytes were downloaded through the authenticated asset API; unchanged asset ids/timestamps/sizes/digests and source tag checked after publishing. Public manifest read back. No original input deletion or independent-machine simulation claim.'))

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
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['pack','readback','rolling','finalize-rolling']);args=ap.parse_args()
    {'pack':pack,'readback':readback,'rolling':rolling,'finalize-rolling':finalize_rolling}[args.action]()
