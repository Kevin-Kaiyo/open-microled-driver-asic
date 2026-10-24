#!/usr/bin/env python3
"""Pack an already frozen selection, verify every tar member, then prepare upload index."""
import argparse, datetime, shutil
import backup_common as c

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true', help='Explicitly run local packing; no upload')
    a = p.parse_args()
    if not a.execute: p.error('--execute is required')
    inv = c.read(c.path('-inventory.json')); scope = c.read(c.path('-scope.json'))
    if c.path('.json').exists() or (c.STAGE/'upload-index.json').exists(): raise ValueError('Existing bundle/index will not be overwritten')
    exclusions = c.check_inventory(inv['files'])
    if exclusions != scope['exclusions']: raise ValueError('Exclusions changed after preparation')
    required = int(inv['total_bytes'] * 1.01) + c.ARCHIVE_LIMIT + c.RESERVE_BYTES
    free = shutil.disk_usage(c.ROOT).free
    if free < required: raise RuntimeError(f'Insufficient staging space: free={free}, conservative required={required}; no source deletion attempted')
    b = c.bundle(); assets = c.STAGE/'assets'
    m = b.pack(c.path('-selection.json'), c.TAG, assets, c.path('.json'), c.ROOT, target_bytes=c.PACK_TARGET)
    if any(x['size'] > c.ARCHIVE_LIMIT for x in m['assets']): raise ValueError('Archive exceeds 512 MiB; do not upload')
    b.verify(c.path('.json'), assets)
    if c.check_inventory(inv['files'], hashes=False) != scope['exclusions']:
        raise ValueError('Exclusion inventory changed while packing')
    local = {'tag': c.TAG, 'source_commit': scope['source_commit'], 'verified_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'manifest_sha256': c.digest(c.path('.json')), 'inventory_sha256': c.digest(c.path('-inventory.json')),
             'all_archive_and_member_hashes_verified': True, 'all_archives_at_most_512MiB': True,
             'archives': len(m['assets']), 'files': sum(len(x['files']) for x in m['assets']),
             'bytes': sum(x['size'] for x in m['assets']), 'free_bytes_before_pack': free,
             'source_inventory_unchanged': True, 'original_sources_removed': False}
    c.write(c.path('-local.json'), local, exclusive=True)
    paths = [c.path(x) for x in ['.json', '-scope.json', '-selection.json', '-inventory.json', '-local.json']]
    paths += [c.STAGE/name for name in ['restore_symlinks.py', 'backup_common.py']]
    paths += [assets/x['name'] for x in m['assets']]
    index = {'tag': c.TAG, 'repository': c.REPO, 'source_commit': scope['source_commit'],
             'files': [{'name': p.name, 'local_path': p.relative_to(c.STAGE).as_posix(), 'size': p.stat().st_size, 'sha256': c.digest(p)} for p in paths]}
    c.write(c.STAGE/'upload-index.json', index, exclusive=True)
    print(f'LOCAL VERIFIED: {local["archives"]} archives, {local["files"]} files, {local["bytes"]} archive bytes; nothing uploaded')
if __name__ == '__main__': main()
