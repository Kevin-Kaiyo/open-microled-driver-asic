#!/usr/bin/env python3
"""Verify public Release bytes by sequential streaming SHA-256. No upload/cleanup."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import subprocess
import sys
import urllib.parse
import urllib.request

sys.dont_write_bytecode = True
import prepare as p


def gh(*arguments):
    result = subprocess.run(['gh', *arguments], text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def release_identity(source_commit):
    info = gh('repo', 'view', p.REPO, '--json', 'nameWithOwner,isPrivate')
    if info['nameWithOwner'] != p.REPO or info['isPrivate']:
        raise ValueError('Expected public repository identity')
    ref = gh('api', f'repos/{p.REPO}/git/ref/tags/{p.TAG}')['object']
    for _ in range(10):
        if ref['type'] != 'tag':
            break
        ref = gh('api', f'repos/{p.REPO}/git/tags/{ref["sha"]}')['object']
    if ref['type'] != 'commit' or ref['sha'] != source_commit:
        raise ValueError('Remote tag/source commit mismatch')
    release = gh('api', f'repos/{p.REPO}/releases/tags/{p.TAG}')
    if release['tag_name'] != p.TAG or release['draft']:
        raise ValueError('Expected published release tag')
    pages = gh('api', f'repos/{p.REPO}/releases/{release["id"]}/assets?per_page=100', '--paginate', '--slurp')
    assets = [a for page in pages for a in page]
    if len({a['name'] for a in assets}) != len(assets):
        raise ValueError('Duplicate remote asset names')
    return release, {a['name']: a for a in assets}


def stream_digest(stream):
    h = hashlib.sha256(); count = 0
    for block in iter(lambda: stream.read(p.CHUNK), b''):
        count += len(block); h.update(block)
    return count, h.hexdigest()


def read_asset(asset, expected):
    if asset['state'] != 'uploaded' or asset['size'] != expected['size']:
        raise ValueError('Remote state/size mismatch: ' + expected['name'])
    if asset.get('digest') and asset['digest'] != 'sha256:' + expected['sha256']:
        raise ValueError('API digest mismatch: ' + expected['name'])
    url = f'https://github.com/{p.REPO}/releases/download/{p.TAG}/{urllib.parse.quote(expected["name"], safe="")}'
    if asset['browser_download_url'] != url:
        raise ValueError('Unexpected Release asset URL')
    request = urllib.request.Request(url, headers={'User-Agent': 'FairDriverEvidenceReadback/1.0'})
    with urllib.request.urlopen(request, timeout=60) as stream:
        size, digest = stream_digest(stream)
    if size != expected['size'] or digest != expected['sha256']:
        raise ValueError('Streamed size/SHA mismatch: ' + expected['name'])
    return {'name': expected['name'], 'remote_asset_id': asset['id'], 'remote_updated_at': asset['updated_at'],
            'size': size, 'sha256': digest, 'download_readback_verified': True,
            'verified_at_utc': p.utc(), 'method': 'streamed in <=4 MiB blocks; no downloaded archive copy'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Actually read public remote assets')
    parser.add_argument('--resume', action='store_true', help='Reuse only identical asset IDs/timestamps/sizes/hashes')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        payload = b'\x00verified bytes\n' * 1000
        assert stream_digest(io.BytesIO(payload)) == (len(payload), hashlib.sha256(payload).hexdigest())
        print(json.dumps({'passed': True, 'network_requests': 0, 'checks': ['streamed size and SHA-256']})); return
    if not args.execute:
        parser.error('--execute is required; no network request made')
    index = p.expected_uploads(); release, remote = release_identity(index['source_commit'])
    stage = p.stage_dir(); progress = stage / 'readback-progress.json'
    prior = p.read(progress) if args.resume and progress.exists() else {'files': []}
    if prior['files'] and (prior.get('source_commit') != index['source_commit'] or prior.get('upload_index_sha256') != p.sha(stage / 'upload-index.json')):
        raise ValueError('Prior readback belongs to another frozen upload index')
    old = {x['name']: x for x in prior['files']}; done = []
    for expected in index['files']:
        asset = remote.get(expected['name'])
        if asset is None:
            raise ValueError('Missing remote asset: ' + expected['name'])
        previous = old.get(expected['name'])
        reusable = previous and previous.get('download_readback_verified') and asset['state'] == 'uploaded' and previous['remote_asset_id'] == asset['id'] and previous['remote_updated_at'] == asset['updated_at'] and previous['size'] == expected['size'] == asset['size'] and previous['sha256'] == expected['sha256'] and (not asset.get('digest') or asset['digest'] == 'sha256:' + expected['sha256'])
        result = previous if reusable else read_asset(asset, expected)
        done.append(result)
        p.write(progress, {'source_commit': index['source_commit'], 'upload_index_sha256': p.sha(stage / 'upload-index.json'), 'files': done}, exclusive=False)
        print(f'READBACK {len(done)}/{len(index["files"])} {expected["name"]}', flush=True)
    after_release, after_assets = release_identity(index['source_commit'])
    if after_release['id'] != release['id']:
        raise ValueError('Release identity changed during readback')
    for result in done:
        after = after_assets.get(result['name'])
        if not after or after['state'] != 'uploaded' or after['id'] != result['remote_asset_id'] or after['updated_at'] != result['remote_updated_at'] or after['size'] != result['size'] or (after.get('digest') and after['digest'] != 'sha256:' + result['sha256']):
            raise ValueError('Remote asset changed during readback: ' + result['name'])
    final = {'tag': p.TAG, 'repository': p.REPO, 'source_commit': index['source_commit'],
             'release_url': release['html_url'], 'manifest_sha256': p.sha(stage / (p.TAG + '.json')),
             'upload_index_sha256': p.sha(stage / 'upload-index.json'), 'all_expected_assets_verified': True,
             'archive_member_validation': 'Every tar member was locally verified before upload; identical remotely streamed archive SHA preserves those exact bytes.',
             'restore_validation': 'Not performed by this command; small-group fresh-checkout DC smoke is a separate required step.',
             'method': 'Sequential streaming; no full archive download replica and no original-data removal.', 'files': done}
    destination = stage / (p.TAG + '-remote.json')
    if destination.exists():
        old_final = p.read(destination)
        if old_final.get('upload_index_sha256') != final['upload_index_sha256']:
            raise ValueError('Existing remote receipt belongs to another upload index')
        destination = stage / (p.TAG + '-remote-' + str(len(list(stage.glob(p.TAG + '-remote-*.json'))) + 1) + '.json')
    p.write(destination, final)
    print('ALL REMOTE ARCHIVES VERIFIED; restoration/DC validation remains separate; originals retained')


if __name__ == '__main__':
    main()
