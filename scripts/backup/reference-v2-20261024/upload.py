#!/usr/bin/env python3
"""Upload to the already created, exact-commit public Release. Never clobber assets."""
import argparse, datetime
import backup_common as c

def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--execute', action='store_true'); a = p.parse_args()
    if not a.execute: p.error('--execute is required; parent creates/tags the final Release first')
    index = c.expected_uploads(); release = c.remote_release(index['source_commit'])
    remote = {x['name']: x for x in release['assets']}; done = []
    for item in index['files']:
        if item['name'] in remote:
            # Existing name is never overwritten; verify existing remote bytes before treating it as a resume.
            c.stream_asset(remote[item['name']], item); status = 'existing_remote_bytes_verified'
        else:
            c.gh('release', 'upload', c.TAG, str(c.STAGE/item['local_path']), '--repo', c.REPO)
            status = 'uploaded_pending_independent_readback'
        done.append({'name': item['name'], 'sha256': item['sha256'], 'status': status, 'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        c.write(c.STAGE/'upload-progress.json', {'source_commit': index['source_commit'], 'files': done})
        print(f'{status}: {len(done)}/{len(index["files"])} {item["name"]}', flush=True)
    print('UPLOAD FINISHED; run readback.py before calling the backup verified')
if __name__ == '__main__': main()
