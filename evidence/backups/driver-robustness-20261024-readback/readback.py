#!/usr/bin/env python3
"""Sequential public-Release streaming readback; no temporary archive copies."""
import argparse, datetime, time
import backup_common as c

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true'); p.add_argument('--resume', action='store_true', help='Reuse receipts only for identical remote asset IDs, sizes and expected hashes')
    a = p.parse_args()
    if not a.execute: p.error('--execute is required')
    index = c.expected_uploads(); release = c.remote_release(index['source_commit'])
    remote = {x['name']: x for x in release['assets']}; progress = c.STAGE/'readback-progress.json'
    prior = c.read(progress) if a.resume and progress.exists() else {'files': []}
    old = {x['name']: x for x in prior['files']}; done = []
    for item in index['files']:
        asset = remote.get(item['name'])
        if asset is None: raise ValueError('Missing remote asset: ' + item['name'])
        previous = old.get(item['name'])
        if previous and previous.get('download_readback_verified') and previous['remote_asset_id'] == asset['id'] and previous['size'] == item['size'] == asset['size'] and previous['sha256'] == item['sha256'] and asset['state'] == 'uploaded' and (not asset.get('digest') or asset['digest'] == 'sha256:' + item['sha256']):
            result = previous
        else:
            for attempt in range(1, 4):
                try: result = c.stream_asset(asset, item); break
                except Exception:
                    if attempt == 3: raise
                    time.sleep(2 * attempt)
            result.update({'verified_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'attempts': attempt})
        done.append(result); c.write(progress, {'source_commit': index['source_commit'], 'files': done})
        print(f'READBACK VERIFIED {len(done)}/{len(index["files"])} {item["name"]}', flush=True)
    receipt = {'tag': c.TAG, 'repository': c.REPO, 'source_commit': index['source_commit'], 'release_url': release['html_url'],
               'manifest_sha256': c.digest(c.path('.json')), 'all_expected_assets_verified': True,
               'archive_member_validation': 'Local tar-member SHA-256 verified before upload; identical remote archive SHA-256 preserves those exact bytes.',
               'method': 'Sequential streaming, at most one 4 MiB download block plus HTTP buffers; no on-disk download replicas.',
               'original_sources_removed': False, 'files': done}
    c.write(c.path('-remote.json'), receipt)
    print(f'ALL REMOTE READBACK VERIFIED: {len(done)} files; source data retained')
if __name__ == '__main__': main()
