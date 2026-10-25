#!/usr/bin/env python3
"""Explicit fair-driver scope scan, freeze, or local pack. Never uploads/cleans."""
from __future__ import annotations
import argparse
from collections import defaultdict
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
TAG = 'fair-driver-20261025'
REPO = 'Kevin-Kaiyo/open-microled-driver-asic'
ROOTS = ('build/fair-driver-v1', 'build/fair-driver-v1-a-probe', 'build/fair-driver-v1-c-probe')
STAGE_REL = 'build/github-sync-fair-driver-20261025'
TARGET_BYTES = 480 * 1024**2
ARCHIVE_LIMIT = 512 * 1024**2
EXPECTED_TOTAL = 2 * 1024**3
RESERVE_BYTES = 5 * 1024**3
CHUNK = 4 * 1024**2
PUBLIC_PATHS = ('analog/fair_driver_v1', 'scripts/fair_driver_v1', 'evidence/fair-driver-v1',
                'docs/research/fair-driver-comparison-20261025',
                'scripts/backup/fair-driver-20261025', 'scripts/backup/release_bundle.py')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(CHUNK), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Symlink JSON input rejected: ' + str(path))
    return json.loads(path.read_text())


def write(path, value, exclusive=True):
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('Symlink receipt destination rejected: ' + str(path))
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if exclusive:
        with path.open('x') as output:
            output.write(payload)
    else:
        fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.partial', dir=path.parent)
        temporary = Path(temporary)
        try:
            with os.fdopen(fd, 'w') as output:
                output.write(payload); output.flush(); os.fsync(output.fileno())
            if path.is_symlink():
                raise ValueError('Receipt became a symlink: ' + str(path))
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()  # Only this invocation's incomplete JSON write, never original evidence.


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def regular(root, relative):
    parts = relative.split('/')
    if not relative or any(x in ('', '.', '..') for x in parts) or '\\' in relative:
        raise ValueError('Unsafe relative path: ' + relative)
    path = root
    for i, part in enumerate(parts):
        path = path / part
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError('Symlink source rejected: ' + relative)
        if i < len(parts)-1 and not stat.S_ISDIR(mode):
            raise ValueError('Non-directory ancestor: ' + relative)
    if not stat.S_ISREG(mode):
        raise ValueError('Not a regular file: ' + relative)
    return path


def group_for(relative):
    path = Path(relative)
    if path.name.endswith(('.dat', '.dat.gz', '.raw', '.raw.gz', '.vcd', '.vcd.gz', '.fst')):
        return 'waveforms'
    if 'inputs' in path.parts or 'execution-sources' in path.parts or path.name in ('manifest.json', 'stimulus.json'):
        return 'inputs'
    return 'results'


def inventory(root=ROOT):
    """Every regular non-bytecode file, including failures; never follow links."""
    selected, excluded = {}, []
    def fail_scan(error):
        raise error
    for name in ROOTS:
        top = root / name
        if top.is_symlink() or not top.is_dir() or (root / 'build').is_symlink():
            raise ValueError('Missing/symlink scope root: ' + name)
        for directory, dirs, names in os.walk(top, followlinks=False, onerror=fail_scan):
            dirs.sort(); names.sort()
            for child in dirs[:]:
                path = Path(directory) / child
                if path.is_symlink():
                    excluded.append({'path': path.relative_to(root).as_posix(), 'reason': 'symlink directory; not followed', 'literal_target': os.readlink(path)})
                    dirs.remove(child)
            for name in names:
                path = Path(directory) / name
                relative = path.relative_to(root).as_posix()
                if path.is_symlink():
                    excluded.append({'path': relative, 'reason': 'symlink file; not followed', 'literal_target': os.readlink(path)})
                    continue
                if path.suffix in ('.pyc', '.pyo'):
                    excluded.append({'path': relative, 'reason': 'rebuildable Python bytecode'})
                    continue
                info = regular(root, relative).stat()
                selected[relative] = {'size': info.st_size, 'mtime_ns': info.st_mtime_ns,
                                      'mode': stat.S_IMODE(info.st_mode), 'group': group_for(relative)}
    return dict(sorted(selected.items())), sorted(excluded, key=lambda x: x['path'])


def partitions(files):
    groups = defaultdict(list)
    for path, item in files.items():
        if item['size'] > TARGET_BYTES:
            raise ValueError('Single file exceeds 480 MiB; preserve it and review a separate lossless splitting plan: ' + path)
        groups[item['group']].append(path)
    parts = []
    for group, paths in sorted(groups.items()):
        batch, size, number = [], 0, 1
        for path in sorted(paths):
            if batch and size + files[path]['size'] > TARGET_BYTES:
                parts.append({'group': group, 'part': number, 'paths': batch, 'bytes': size})
                batch, size, number = [], 0, number + 1
            batch.append(path); size += files[path]['size']
        if batch:
            parts.append({'group': group, 'part': number, 'paths': batch, 'bytes': size})
    return parts


def summary(files, exclusions):
    parts = partitions(files)
    return {'files': len(files), 'bytes': sum(x['size'] for x in files.values()),
            'groups': [{'name': name, 'files': sum(x['group'] == name for x in files.values()),
                        'bytes': sum(x['size'] for x in files.values() if x['group'] == name)} for name in sorted({x['group'] for x in files.values()})],
            'planned_archives': len(parts), 'largest_payload_bytes': max(x['bytes'] for x in parts),
            'largest_file': max(files, key=lambda p: files[p]['size']), 'exclusions': exclusions,
            'scope_roots': ROOTS, 'maximum_uncompressed_payload_per_part': TARGET_BYTES,
            'live_scan_only': True, 'frozen': False}


def check_inventory(root, expected, exclusions, hashes=True):
    actual, skipped = inventory(root)
    if actual.keys() != expected.keys() or skipped != exclusions:
        raise ValueError('Source/exclusion file set changed after freeze')
    for path, item in expected.items():
        if any(actual[path][key] != item[key] for key in ('size', 'mtime_ns', 'mode', 'group')):
            raise ValueError('Source metadata changed after freeze: ' + path)
        if hashes and sha(regular(root, path)) != item['sha256']:
            raise ValueError('Source content changed after freeze: ' + path)


def bundle(root=ROOT):
    spec = importlib.util.spec_from_file_location('fair_release_bundle', root / 'scripts/backup/release_bundle.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def stage_dir(root=ROOT):
    path = root / STAGE_REL
    if path.is_symlink() or (root / 'build').is_symlink():
        raise ValueError('Symlink staging path rejected')
    return path


def verify_source_commit(commit, root=ROOT):
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Full lowercase source commit SHA required')
    current = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if current != commit:
        raise ValueError('Supplied source commit must equal current checkout HEAD')
    changed = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all', '--', *PUBLIC_PATHS], cwd=root, text=True)
    if changed:
        raise ValueError('Public milestone source/report paths are not committed; stop before freeze:\n' + changed)
    tools = ['scripts/backup/release_bundle.py', 'scripts/backup/fair-driver-20261025/prepare.py',
             'scripts/backup/fair-driver-20261025/readback.py', 'scripts/backup/fair-driver-20261025/README.md']
    for relative in tools:
        saved = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=root)
        if hashlib.sha256(saved).hexdigest() != sha(root / relative):
            raise ValueError('Helper differs from delivery source commit: ' + relative)
    return {relative: sha(root / relative) for relative in tools}


def freeze(commit, acknowledged, root=ROOT):
    if not acknowledged:
        raise ValueError('--freeze-ack is required after ALL simulation/report writers have stopped')
    helper_hashes = verify_source_commit(commit, root)
    stage = stage_dir(root)
    if stage.exists() and any(stage.iterdir()):
        raise ValueError('Refusing to overwrite nonempty staging directory')
    files, exclusions = inventory(root)
    info = summary(files, exclusions)
    if info['bytes'] >= EXPECTED_TOTAL:
        raise ValueError('Actual scope exceeds the expected <2 GiB budget; review before freezing')
    for relative, item in files.items():
        item['sha256'] = sha(regular(root, relative))
    check_inventory(root, files, exclusions)
    groups = defaultdict(list)
    for relative, item in files.items():
        groups[item['group']].append(relative)
    scope = {'schema_version': 1, 'tag': TAG, 'repository': REPO, 'source_commit': commit,
             'prepared_at_utc': utc(), 'writers_stopped_acknowledged': True, 'roots': ROOTS,
             'coverage': 'All regular non-bytecode files under the three declared roots, including failed candidates, partial outputs, logs and storage prototypes. No outcome-based exclusion.',
             'exclusions': exclusions, 'helper_sha256': helper_hashes,
             'archive_policy': {'payload_target_bytes': TARGET_BYTES, 'compressed_limit_bytes': ARCHIVE_LIMIT},
             'restore_small_groups': ['inputs', 'results'],
             'source_identity_boundary': 'Delivery source_commit identifies this public checkout. Historical experiment manifests and execution-source hashes retain their original identities without rewriting.',
             'excluded_environment': ['Full PDK/VM/tool/Python installations', 'All other build trees', 'Symlink targets are never dereferenced; all links are listed and excluded', 'Python .pyc/.pyo'],
             'restore_boundary': 'Restore relative paths into a matching source checkout. Regenerate a new DC deck from frozen inputs; saved decks contain original absolute paths. No physical EDA, silicon or optical validation is implied.',
             'retention': 'Original files are retained. No cleanup or upload operation is implemented by this helper.'}
    stage.mkdir(parents=True, exist_ok=True)
    write(stage / (TAG + '-selection.json'), {'groups': [{'name': k, 'paths': v} for k, v in sorted(groups.items())]})
    write(stage / (TAG + '-inventory.json'), {'created_at_utc': utc(), 'files': files, 'total_bytes': info['bytes']})
    write(stage / (TAG + '-scope.json'), scope)
    return {**info, 'live_scan_only': False, 'frozen': True, 'source_commit': commit, 'stage': str(stage)}


def pack(acknowledged, root=ROOT):
    if not acknowledged:
        raise ValueError('--execute is required for local packing')
    stage = stage_dir(root)
    scope = read(stage / (TAG + '-scope.json')); inv = read(stage / (TAG + '-inventory.json'))
    helpers = verify_source_commit(scope['source_commit'], root)
    if helpers != scope['helper_sha256']:
        raise ValueError('Helper source changed after freeze')
    for path in [stage / (TAG + '.json'), stage / (TAG + '-local.json'), stage / 'upload-index.json']:
        if path.exists():
            raise ValueError('Refuse existing output: ' + str(path))
    check_inventory(root, inv['files'], scope['exclusions'])
    selected_groups = defaultdict(list)
    for relative, item in inv['files'].items():
        selected_groups[item['group']].append(relative)
    wanted_selection = {'groups': [{'name': k, 'paths': sorted(v)} for k, v in sorted(selected_groups.items())]}
    if read(stage / (TAG + '-selection.json')) != wanted_selection:
        raise ValueError('Selection/group membership differs from frozen inventory')
    free = shutil.disk_usage(root).free
    required = int(inv['total_bytes'] * 1.02) + ARCHIVE_LIMIT + RESERVE_BYTES
    if free < required:
        raise RuntimeError(f'Insufficient staging space: free={free}, required={required}; no deletion attempted')
    helper = bundle(root)
    manifest = stage / (TAG + '.json'); assets = stage / 'assets'
    data = helper.pack(stage / (TAG + '-selection.json'), TAG, assets, manifest, root, target_bytes=TARGET_BYTES)
    if any(a['size'] > ARCHIVE_LIMIT or sum(f['size'] for f in a['files']) > TARGET_BYTES for a in data['assets']):
        raise ValueError('Archive limit violated; do not upload')
    helper.verify(manifest, assets)
    archived = {f['path']: f for a in data['assets'] for f in a['files']}
    if archived.keys() != inv['files'].keys() or any(any(archived[p][k] != item[k] for k in ('size', 'sha256', 'mode')) for p, item in inv['files'].items()):
        raise ValueError('Archive members differ from frozen scope')
    if any(inv['files'][f['path']]['group'] != asset['group'] for asset in data['assets'] for f in asset['files']):
        raise ValueError('Archive group differs from frozen scope')
    check_inventory(root, inv['files'], scope['exclusions'])
    receipt = {'tag': TAG, 'source_commit': scope['source_commit'], 'verified_at_utc': utc(),
               'manifest_sha256': sha(manifest), 'all_archive_and_member_hashes_verified': True,
               'source_inventory_unchanged': True, 'archives': len(data['assets']), 'files': len(archived),
               'archive_bytes': sum(a['size'] for a in data['assets']), 'free_bytes_before_pack': free,
               'original_files_removed': False, 'uploaded': False}
    write(stage / (TAG + '-local.json'), receipt)
    small = [stage / (TAG + suffix) for suffix in ('.json', '-scope.json', '-selection.json', '-inventory.json', '-local.json')]
    paths = small + [assets / a['name'] for a in sorted(data['assets'], key=lambda a: (a['group'] == 'waveforms', a['name']))]
    write(stage / 'upload-index.json', {'tag': TAG, 'repository': REPO, 'source_commit': scope['source_commit'],
          'files': [{'name': p.name, 'local_path': p.relative_to(stage).as_posix(), 'size': p.stat().st_size, 'sha256': sha(p)} for p in paths]})
    return receipt


def expected_uploads(root=ROOT):
    stage = stage_dir(root); index = read(stage / 'upload-index.json'); scope = read(stage / (TAG + '-scope.json'))
    if index['tag'] != TAG or index['repository'] != REPO or index['source_commit'] != scope['source_commit']:
        raise ValueError('Upload index identity mismatch')
    if len({f['name'] for f in index['files']}) != len(index['files']):
        raise ValueError('Duplicate upload asset name')
    metadata_names = {TAG + suffix for suffix in ('.json', '-scope.json', '-selection.json', '-inventory.json', '-local.json')}
    for item in index['files']:
        canonical = item['name'] if item['name'] in metadata_names else 'assets/' + item['name']
        if item['local_path'] != canonical:
            raise ValueError('Noncanonical upload path: ' + item['name'])
        path = regular(stage, item['local_path'])
        if path.name != item['name'] or path.stat().st_size != item['size'] or sha(path) != item['sha256']:
            raise ValueError('Local upload bytes changed: ' + item['name'])
    manifest = bundle(root).read_manifest(stage / (TAG + '.json'))
    if manifest['tag'] != TAG:
        raise ValueError('Manifest tag mismatch')
    expected = metadata_names | {a['name'] for a in manifest['assets']}
    if {f['name'] for f in index['files']} != expected:
        raise ValueError('Upload index is not complete for this manifest/metadata')
    by_name = {f['name']: f for f in index['files']}
    for asset in manifest['assets']:
        if any(by_name[asset['name']][k] != asset[k] for k in ('size', 'sha256')):
            raise ValueError('Manifest/archive upload binding mismatch: ' + asset['name'])
    local = read(stage / (TAG + '-local.json'))
    if local['manifest_sha256'] != sha(stage / (TAG + '.json')) or local['source_commit'] != scope['source_commit'] or not local['all_archive_and_member_hashes_verified'] or not local['source_inventory_unchanged']:
        raise ValueError('Local tar verification receipt does not match this manifest')
    return index


def self_test():
    # Only disposable synthetic bytes; no archive creation, simulation or network.
    with tempfile.TemporaryDirectory(prefix='fair-backup-unit-') as tmp:
        root = Path(tmp)
        for relative in ROOTS:
            (root / relative).mkdir(parents=True)
        base = root / ROOTS[0]
        (base / 'inputs').mkdir(); (base / 'inputs/model.spice').write_text('model')
        (base / 'failure.log').write_text('failed candidate retained')
        (base / 'waveform.dat.gz').write_bytes(b'raw fixture')
        (base / 'cached.pyc').write_bytes(b'cache')
        (base / 'external').symlink_to('/tmp')
        files, exclusions = inventory(root)
        if len(files) != 3 or len(exclusions) != 2 or {v['group'] for v in files.values()} != {'inputs', 'results', 'waveforms'}:
            raise AssertionError('scope/group/bytecode/symlink self-test')
        for p, item in files.items():
            item['sha256'] = sha(regular(root, p))
        check_inventory(root, files, exclusions)
        (base / 'failure.log').write_text('changed')
        try:
            check_inventory(root, files, exclusions)
        except ValueError:
            pass
        else:
            raise AssertionError('drift must be rejected')
        f = {'a': {'group': 'waveforms', 'size': TARGET_BYTES}, 'b': {'group': 'waveforms', 'size': 1}}
        if len(partitions(f)) != 2:
            raise AssertionError('480 MiB split boundary')
        try:
            partitions({'large': {'group': 'waveforms', 'size': TARGET_BYTES + 1}})
        except ValueError:
            pass
        else:
            raise AssertionError('oversized individual file must be rejected')
        target = root / 'protected.txt'; target.write_text('untouched')
        receipt = root / 'progress.json'; receipt.symlink_to(target)
        try:
            write(receipt, {}, exclusive=False)
        except ValueError:
            pass
        else:
            raise AssertionError('symlink receipt must be rejected')
        if target.read_text() != 'untouched':
            raise AssertionError('symlink target changed')
        write(root / 'regular-progress.json', {'state': 1}, exclusive=False)
        write(root / 'regular-progress.json', {'state': 2}, exclusive=False)
        if read(root / 'regular-progress.json') != {'state': 2}:
            raise AssertionError('atomic progress replacement')
        from unittest.mock import patch
        with patch('os.scandir', side_effect=PermissionError('synthetic unreadable directory')):
            try:
                inventory(root)
            except PermissionError:
                pass
            else:
                raise AssertionError('directory scan errors must be fatal')
    return {'passed': True, 'checks': ['scope coverage and failure retention', 'no symlink traversal', 'bytecode exclusion', 'three restore groups', 'source drift rejection', '480 MiB split', 'oversized file rejection', 'symlink receipt rejection', 'atomic progress replacement', 'directory scan errors rejected'], 'archives_created': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('scan', help='Read-only live scope/partition preview; not a freeze')
    sub.add_parser('self-test', help='Synthetic scope tests; no packing or network')
    p = sub.add_parser('freeze'); p.add_argument('--freeze-ack', action='store_true'); p.add_argument('--source-commit', required=True)
    p = sub.add_parser('pack'); p.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.command == 'scan':
        files, exclusions = inventory(); result = summary(files, exclusions)
    elif args.command == 'self-test':
        result = self_test()
    elif args.command == 'freeze':
        result = freeze(args.source_commit, args.freeze_ack)
    else:
        result = pack(args.execute)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
