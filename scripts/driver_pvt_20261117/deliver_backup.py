#!/usr/bin/env python3
"""Publish the authorized milestone backup after a verified draft readback."""
from concurrent.futures import as_completed, ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import time
from urllib.request import urlopen

from prepare_backup import MANIFEST, RELEASE, ROOT, TAG, release_bundle


REPO = 'Kevin-Kaiyo/open-microled-driver-asic'


def command(*args):
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()


def api(path):
    return json.loads(command('gh', 'api', f'repos/{REPO}/{path}'))


def release():
    for obj in api('releases?per_page=100'):
        if obj['tag_name'] == TAG:
            return obj
    return None


def upload(item):
    source, digest = item
    for attempt in range(5):
        remote = next((a for a in release()['assets'] if a['name'] == source.name), None)
        if remote and remote['state'] == 'uploaded':
            assert remote.get('digest') == f'sha256:{digest}', source.name
            assert remote['size'] == source.stat().st_size
            print(f'UPLOAD VERIFIED {source.name}', flush=True)
            return item
        if remote is None and attempt < 4:
            transfer = subprocess.run(['gh', 'release', 'upload', TAG, str(source), '--repo', REPO],
                                      cwd=ROOT, text=True, capture_output=True)
            if transfer.returncode:
                print(f'{source.name}: upload attempt {attempt+1} returned {transfer.returncode}', flush=True)
        time.sleep(2)
    raise RuntimeError(f'Upload verification failed: {source.name}')


def download(item):
    source, digest = item
    target = RELEASE / 'readback' / source.name
    if not target.exists():
        with TemporaryDirectory(dir=target.parent) as scratch:
            command('gh', 'release', 'download', TAG, '--pattern', source.name,
                    '--dir', scratch, '--repo', REPO)
            incoming = Path(scratch) / source.name
            assert release_bundle.digest_file(incoming) == digest, source.name
            incoming.replace(target)
    assert target.stat().st_size == source.stat().st_size
    assert release_bundle.digest_file(target) == digest, source.name
    print(f'READBACK VERIFIED {source.name}', flush=True)
    return {'name': source.name, 'bytes': target.stat().st_size, 'sha256': digest}


def read_git_file(commit, relative):
    with urlopen(f'https://raw.githubusercontent.com/{REPO}/{commit}/{relative}', timeout=60) as stream:
        remote_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert remote_hash == release_bundle.digest_file(ROOT / relative), relative
    return {'path': relative, 'sha256': remote_hash}


def main():
    commit = (RELEASE / 'source-commit.txt').read_text().strip()
    assert api('git/ref/heads/main')['object']['sha'] == commit
    pack_receipt = json.loads((RELEASE / 'pack-verification.json').read_text())
    manifest_hash = release_bundle.digest_file(MANIFEST)
    assert pack_receipt['local_archive_and_member_sha_verified']
    assert manifest_hash == pack_receipt['manifest_sha256']
    report = ROOT / 'docs/research' / TAG
    verified = ['index.html', 'technical-stage-report.pdf', 'reproduce.html']
    git_files = [read_git_file(commit, (report / name).relative_to(ROOT).as_posix()) for name in verified]
    git_files.append(read_git_file(commit, MANIFEST.relative_to(ROOT).as_posix()))

    if not release():
        command('gh', 'release', 'create', TAG, '--repo', REPO, '--draft', '--target', commit,
                '--title', 'MicroLED and VCSEL PVT experiments · 2026-11-17',
                '--notes-file', str(RELEASE / 'release-notes.md'))
    remote = release()
    assert remote['draft'] or api(f'git/ref/tags/{TAG}')['object']['sha'] == commit
    if remote['draft']:
        assert remote['target_commitish'] == commit
    print(f'Draft pinned to {commit}', flush=True)

    manifest = json.loads(MANIFEST.read_text())
    upload_manifest = RELEASE / f'{TAG}-archive-manifest.json'
    shutil.copyfile(MANIFEST, upload_manifest)
    (RELEASE / 'readback').mkdir(exist_ok=True)
    items = [(RELEASE / 'assets' / a['name'], a['sha256']) for a in manifest['assets']]
    items.append((upload_manifest, manifest_hash))
    ordered = sorted(items, key=lambda item: item[0].stat().st_size, reverse=True)
    with ThreadPoolExecutor(max_workers=2) as send, ThreadPoolExecutor(max_workers=2) as receive:
        transfers = [send.submit(upload, item) for item in ordered]
        readbacks = [receive.submit(download, ready.result()) for ready in as_completed(transfers)]
        assets = sorted((job.result() for job in as_completed(readbacks)), key=lambda item: item['name'])
    downloaded = RELEASE / 'readback' / upload_manifest.name
    back = release_bundle.verify(downloaded, downloaded.parent)
    members = sum(len(asset['files']) for asset in back['assets'])
    assert members == pack_receipt['members']
    print(f'MEMBER SHA VERIFIED {members}', flush=True)
    if release()['draft']:
        command('gh', 'release', 'edit', TAG, '--repo', REPO, '--draft=false', '--target', commit)
    remote = release()
    assert not remote['draft'] and len(remote['assets']) == len(items)
    assert api(f'git/ref/tags/{TAG}')['object']['sha'] == commit
    manifest_asset = next(a for a in remote['assets'] if a['name'] == upload_manifest.name)
    with urlopen(manifest_asset['browser_download_url'], timeout=60) as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == manifest_hash
    receipt = {
        'verified_at_utc': datetime.now(timezone.utc).isoformat(), 'source_commit': commit,
        'release_url': remote['html_url'], 'release_published': True, 'assets': assets,
        'archives': len(back['assets']), 'members': members, 'manifest_sha256': manifest_hash,
        'all_downloaded_members_verified': True, 'public_manifest_readback_verified': True,
        'public_source_readback': git_files, 'local_originals_removed': False,
    }
    (MANIFEST.parent / 'delivery.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(remote['html_url'], flush=True)


if __name__ == '__main__':
    main()
