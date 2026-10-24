#!/usr/bin/env python3
"""Resume verified Release readback with at most four independent streaming workers.

Workers call the original frozen stream_asset and never write progress. The main
thread alone saves receipts in upload-index order. No original/archive is changed.
"""
import argparse, concurrent.futures, datetime, hashlib, json, time
from pathlib import Path
import backup_common as c

SOURCE_SHA256 = c.digest(Path(__file__))

def load_context():
    index = c.expected_uploads()
    release = c.remote_release(index['source_commit'])
    remote = {x['name']: x for x in release['assets']}
    progress = c.read(c.STAGE/'readback-progress.json')
    if progress['source_commit'] != index['source_commit']: raise ValueError('Previous readback source commit differs')
    previous = {x['name']: x for x in progress['files']}
    expected_names = {x['name'] for x in index['files']}
    if set(previous) - expected_names: raise ValueError('Unexpected prior receipt name')
    for item in index['files']:
        asset = remote.get(item['name'])
        if not asset or asset['state'] != 'uploaded' or asset['size'] != item['size']:
            raise ValueError('Remote asset missing or size/state changed: ' + item['name'])
        if asset.get('digest') and asset['digest'] != 'sha256:' + item['sha256']:
            raise ValueError('Remote digest changed: ' + item['name'])
        old = previous.get(item['name'])
        if old and not (old.get('download_readback_verified') and old['remote_asset_id'] == asset['id'] and old['size'] == item['size'] and old['sha256'] == item['sha256']):
            raise ValueError('Prior receipt cannot be reused: ' + item['name'])
    return index, release, remote, previous

def ordered(index, results):
    return [results[x['name']] for x in index['files'] if x['name'] in results]

def metadata_control(index, remote, previous):
    item = next(x for x in index['files'] if x['name'] == c.TAG+'.json')
    old = previous[item['name']]
    actual = c.stream_asset(remote[item['name']], item)
    for key in ['remote_asset_id', 'name', 'size', 'sha256', 'download_readback_verified']:
        if actual[key] != old[key]: raise ValueError('Metadata control differs from serial receipt: ' + key)
    output = {'passed': True, 'source_commit': index['source_commit'], 'name': item['name'],
              'compared_fields': ['remote_asset_id','name','size','sha256','download_readback_verified'],
              'serial_receipt': old, 'fresh_control_receipt': actual,
              'upload_index_sha256': c.digest(c.STAGE/'upload-index.json'),
              'parallel_source_sha256': SOURCE_SHA256,
              'verified_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    c.write(c.STAGE/'readback-parallel-control.json', output)
    print('METADATA CONTROL MATCHES SERIAL RECEIPT', item['name'], flush=True)

def worker(item, asset):
    for attempt in range(1, 4):
        try:
            result = c.stream_asset(asset, item)
            result.update({'verified_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                           'attempts': attempt, 'readback_phase': 'bounded_parallel_resume'})
            return result
        except Exception:
            if attempt == 3: raise
            time.sleep(2*attempt)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--control-only', action='store_true')
    p.add_argument('--workers', type=int, choices=range(1,5), default=4)
    a = p.parse_args()
    if not a.execute: p.error('--execute is required')
    index, release, remote, results = load_context()
    if a.control_only:
        metadata_control(index, remote, results); return
    control = c.read(c.STAGE/'readback-parallel-control.json')
    if not control['passed'] or control['source_commit'] != index['source_commit'] or control['upload_index_sha256'] != c.digest(c.STAGE/'upload-index.json') or control['parallel_source_sha256'] != SOURCE_SHA256:
        raise ValueError('Run matching --control-only before the parallel resume')
    transition_path = c.STAGE/'readback-transition.json'; transition = c.read(transition_path)
    snapshot = c.STAGE/transition['serial_progress_snapshot']
    if c.digest(snapshot) != transition['serial_progress_sha256']: raise ValueError('Serial progress snapshot changed')
    prior_count = len(results); todo = [x for x in index['files'] if x['name'] not in results]; failures = []
    print(f'RESUME {prior_count} prior verified assets; {len(todo)} remaining; max {a.workers} workers', flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures = {pool.submit(worker, item, remote[item['name']]): item for item in todo}
        for future in concurrent.futures.as_completed(futures):
            item = futures[future]
            try: result = future.result()
            except Exception as exc:
                failures.append({'name': item['name'], 'error': str(exc)}); print('READBACK FAILED', item['name'], str(exc), flush=True); continue
            results[item['name']] = result
            c.write(c.STAGE/'readback-progress.json', {'source_commit': index['source_commit'], 'files': ordered(index, results)})
            print(f'READBACK VERIFIED {len(results)}/{len(index["files"])} {item["name"]}', flush=True)
    if failures:
        c.write(c.STAGE/'readback-parallel-errors.json', {'failures': failures, 'successful_count': len(results)})
        raise RuntimeError('Some assets failed after bounded retries; successful receipts retained')
    if len(results) != len(index['files']): raise ValueError('Incomplete expected receipt set')
    receipt = {'tag': c.TAG, 'repository': c.REPO, 'source_commit': index['source_commit'], 'release_url': release['html_url'],
               'manifest_sha256': c.digest(c.path('.json')), 'all_expected_assets_verified': True,
               'archive_member_validation': 'Local tar-member SHA-256 verified before upload; identical remote archive SHA-256 preserves those exact bytes.',
               'method': f'Original sequential streaming receipts retained; remaining assets use at most {a.workers} concurrent independent stream_asset calls, each reading4MiB blocks. Only main thread writes progress; final receipts follow original upload-index order. No download replicas on disk.',
               'maximum_concurrent_streams': a.workers, 'serial_verified_asset_count': transition['stopped_after_completed_count'],
               'already_verified_before_this_resume': prior_count, 'newly_verified_this_resume': len(todo),
               'readback_transition': transition, 'readback_transition_sha256': c.digest(transition_path),
               'metadata_control_sha256': c.digest(c.STAGE/'readback-parallel-control.json'),
               'parallel_source_sha256': SOURCE_SHA256,
               'original_sources_removed': False, 'files': ordered(index, results)}
    c.write(c.path('-remote.json'), receipt)
    print(f'ALL REMOTE READBACK VERIFIED: {len(results)} files; source data retained', flush=True)
if __name__ == '__main__': main()
