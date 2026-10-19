#!/usr/bin/env python3
"""Deterministic, verified research release bundles (standard library only).

pack accepts explicit repository-relative regular files, never directories.
verify checks the manifest, archive bytes and every logical tar member.
restore verifies everything and preflights all destinations before writing;
it skips identical existing files and never overwrites a different file.
No command uploads files or removes repository source files.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tarfile
import tempfile

SCHEMA_VERSION = 1
TARGET_BYTES = 512 * 1024**2
MAX_FILE_BYTES = 18 * 1024**3 // 10  # 1.8 GiB, below a 2 GiB release-asset ceiling.
CHUNK = 1024 * 1024


class BundleError(ValueError):
    """Invalid, unsafe, inconsistent or conflicting bundle input."""


def digest_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b''):
            h.update(chunk)
    return h.hexdigest()


def _relative(value):
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise BundleError(f'Invalid relative file path: {value!r}')
    parts = value.split('/')
    if any(p in ('', '.', '..') for p in parts) or ':' in parts[0]:
        raise BundleError(f'Unsafe relative file path: {value!r}')
    if PurePosixPath(value).is_absolute():
        raise BundleError(f'Absolute file path rejected: {value!r}')
    return value


def _component(value, what):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', value):
        raise BundleError(f'Invalid {what}: {value!r}')
    return value


def _root(path, must_exist=True):
    path = Path(path).absolute()
    if path.is_symlink():
        raise BundleError(f'Symlink root rejected: {path}')
    path = path.resolve(strict=must_exist)
    if path.exists() and not path.is_dir():
        raise BundleError(f'Root is not a directory: {path}')
    return path


def _safe_path(root, relative, must_exist=False):
    """Inspect each component under a trusted root, without following links."""
    parts = _relative(relative).split('/')
    current = root
    for index, part in enumerate(parts):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if must_exist:
                raise BundleError(f'Missing selected file: {relative}')
            continue
        if stat.S_ISLNK(info.st_mode):
            raise BundleError(f'Symlink rejected: {current}')
        if index < len(parts)-1 and not stat.S_ISDIR(info.st_mode):
            raise BundleError(f'Non-directory ancestor: {current}')
        if index == len(parts)-1 and not stat.S_ISREG(info.st_mode):
            raise BundleError(f'Only regular files are allowed: {current}')
    return current


def _no_path_collisions(paths):
    seen = set()
    for path in sorted(paths):
        if path in seen:
            raise BundleError(f'Duplicate member path: {path}')
        if any('/'.join(path.split('/')[:i]) in seen for i in range(1, len(path.split('/')))):
            raise BundleError(f'File/ancestor collision: {path}')
        seen.add(path)


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise BundleError(f'Cannot read JSON {path}: {exc}') from exc


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise BundleError(f'Invalid {label}: {value!r}')


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise BundleError('Expected a lowercase SHA-256 hex digest')


def read_manifest(path):
    data = _json(path)
    if not isinstance(data, dict) or data.get('schema_version') != SCHEMA_VERSION:
        raise BundleError('Unsupported manifest schema')
    _component(data.get('tag'), 'tag')
    assets = data.get('assets')
    if not isinstance(assets, list) or not assets:
        raise BundleError('Manifest must contain assets')
    names, paths = set(), []
    for asset in assets:
        if not isinstance(asset, dict):
            raise BundleError('Asset entry must be an object')
        name = _component(asset.get('name'), 'asset name')
        _component(asset.get('group'), 'asset group')
        if not name.endswith('.tar.gz') or name in names:
            raise BundleError(f'Invalid or duplicate asset name: {name}')
        names.add(name)
        _integer(asset.get('size'), 'asset size', 1); _hash(asset.get('sha256'))
        if not isinstance(asset.get('files'), list) or not asset['files']:
            raise BundleError(f'Asset has no files: {name}')
        for item in asset['files']:
            if not isinstance(item, dict):
                raise BundleError('File entry must be an object')
            paths.append(_relative(item.get('path')))
            _integer(item.get('size'), 'file size'); _hash(item.get('sha256'))
            if 'mode' in item:
                _integer(item['mode'], 'file mode')
                if item['mode'] > 0o777:
                    raise BundleError('Special file permission bits rejected')
    _no_path_collisions(paths)
    return data


class _HashReader:
    def __init__(self, stream):
        self.stream, self.hash, self.size = stream, hashlib.sha256(), 0

    def read(self, count=-1):
        chunk = self.stream.read(count)
        self.hash.update(chunk); self.size += len(chunk)
        return chunk


def pack(selection, tag, output, manifest, root='.', target_bytes=TARGET_BYTES):
    root = _root(root); tag = _component(tag, 'tag')
    _integer(target_bytes, 'target bytes', 1)
    selection = _json(selection) if not isinstance(selection, dict) else selection
    groups = selection.get('groups') if isinstance(selection, dict) else None
    if not isinstance(groups, list) or not groups:
        raise BundleError('Selection must contain a nonempty groups list')
    plans, all_paths, group_names = [], [], set()
    # Validate sizes before hashing, including the single-file release limit.
    for group in groups:
        if not isinstance(group, dict):
            raise BundleError('Selection group must be an object')
        name = _component(group.get('name'), 'group name')
        if name in group_names:
            raise BundleError(f'Duplicate group: {name}')
        group_names.add(name)
        paths = group.get('paths')
        if not isinstance(paths, list) or not paths:
            raise BundleError(f'Group must contain explicit files: {name}')
        files = []
        for relative in paths:
            relative = _relative(relative)
            path = _safe_path(root, relative, must_exist=True); info = path.stat()
            if info.st_size > MAX_FILE_BYTES:
                raise BundleError(f'File exceeds 1.8 GiB: {relative} ({info.st_size} bytes)')
            files.append({'path': relative, 'size': info.st_size, 'mode': stat.S_IMODE(info.st_mode) & 0o777})
            all_paths.append(relative)
        plans.append((name, sorted(files, key=lambda item: item['path'])))
    _no_path_collisions(all_paths)
    batches = []
    for name, files in sorted(plans):
        part, size, index = [], 0, 1
        for item in files:
            if part and size + item['size'] > target_bytes:
                batches.append((f'{tag}-{name}-{index:03d}.tar.gz', part, name)); part, size = [], 0; index += 1
            part.append(item); size += item['size']
        if part:
            batches.append((f'{tag}-{name}-{index:03d}.tar.gz', part, name))
    output, manifest = Path(output).absolute(), Path(manifest).absolute()
    if output.is_symlink() or manifest.is_symlink():
        raise BundleError('Symlink output or manifest rejected')
    if manifest.exists():
        raise BundleError(f'Refusing to overwrite an existing manifest: {manifest}')
    if any((output/name).exists() or (output/name).is_symlink() for name, _, _ in batches):
        raise BundleError('Refusing to overwrite existing bundle assets; choose a fresh output directory/tag')
    source_paths = {root/path for path in all_paths}
    if manifest in source_paths or any(output/name in source_paths for name, _, _ in batches):
        raise BundleError('Bundle output collides with selected source file')
    for _, files, _ in batches:
        for item in files:
            item['sha256'] = digest_file(_safe_path(root, item['path'], must_exist=True))
    output.mkdir(parents=True, exist_ok=True)
    assets = []
    for name, files, group in batches:
        final = output/name
        fd, temporary = tempfile.mkstemp(prefix='.'+name+'.', suffix='.partial', dir=output)
        temp = Path(temporary)
        try:
            with os.fdopen(fd, 'wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=6) as gz:
                with tarfile.open(fileobj=gz, mode='w', format=tarfile.PAX_FORMAT) as archive:
                    for item in files:
                        source = _safe_path(root, item['path'], must_exist=True)
                        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                        with os.fdopen(os.open(source, flags), 'rb') as stream:
                            before = os.fstat(stream.fileno())
                            if before.st_size != item['size'] or not stat.S_ISREG(before.st_mode):
                                raise BundleError(f'Source changed while packing: {item["path"]}')
                            info = tarfile.TarInfo(item['path']); info.size = item['size']; info.mode = item['mode']
                            info.uid = info.gid = 0; info.uname = info.gname = ''; info.mtime = 0
                            reader = _HashReader(stream); archive.addfile(info, reader)
                            after = os.fstat(stream.fileno())
                            if reader.hash.hexdigest() != item['sha256'] or reader.size != item['size'] or after.st_size != before.st_size:
                                raise BundleError(f'Source changed while packing: {item["path"]}')
            if final.exists():
                raise BundleError(f'Output appeared during packing: {final}')
            temp.replace(final)
        finally:
            if temp.exists():temp.unlink()  # Only this command's incomplete temporary output.
        asset = {'name': name, 'group': group, 'size': final.stat().st_size, 'sha256': digest_file(final), 'files': files}
        assets.append(asset)
        print(f'PACKED {name}: {asset["size"]} bytes, {len(files)} files', flush=True)
    data = {'schema_version': SCHEMA_VERSION, 'tag': tag, 'assets': assets}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects another process or an existing milestone.
    with manifest.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    print(f'TOTAL {len(assets)} assets, {sum(a["size"] for a in assets)} compressed bytes, {sum(f["size"] for a in assets for f in a["files"])} original bytes', flush=True)
    return data


def _archive_path(asset_dir, name):
    return _safe_path(asset_dir, name, must_exist=True)


def _selected(data, group):
    if group is None:return data
    groups = [group] if isinstance(group, str) else list(group)
    requested = {_component(value, 'selected group') for value in groups}
    available = {asset['group'] for asset in data['assets']}
    if not requested or requested-available:
        raise BundleError(f'Unknown or empty group selection: {sorted(requested-available)}')
    return dict(data, assets=[asset for asset in data['assets'] if asset['group'] in requested])


def verify(manifest, asset_dir, group=None):
    data = read_manifest(manifest); asset_dir = _root(asset_dir)
    data = _selected(data, group)
    for asset in data['assets']:
        path = _archive_path(asset_dir, asset['name'])
        if path.stat().st_size != asset['size'] or digest_file(path) != asset['sha256']:
            raise BundleError(f'Archive byte checksum/size mismatch: {asset["name"]}')
        expected = {item['path']: item for item in asset['files']}; seen = set()
        try:
            with tarfile.open(path, 'r:gz') as archive:
                for member in archive:
                    name = _relative(member.name)
                    if not member.isreg() or member.issparse():
                        raise BundleError(f'Non-regular tar member rejected: {name}')
                    if name not in expected or name in seen:
                        raise BundleError(f'Unexpected or duplicate tar member: {name}')
                    item = expected[name]
                    if member.size != item['size'] or member.mode & ~0o777:
                        raise BundleError(f'Member size/permission mismatch: {name}')
                    if 'mode' in item and member.mode != item['mode']:
                        raise BundleError(f'Member executable/permission bits differ: {name}')
                    with archive.extractfile(member) as stream:
                        reader = _HashReader(stream)
                        for _ in iter(lambda: reader.read(CHUNK), b''):pass
                    if reader.size != item['size'] or reader.hash.hexdigest() != item['sha256']:
                        raise BundleError(f'Member byte checksum mismatch: {name}')
                    seen.add(name)
        except (tarfile.TarError, OSError, EOFError) as exc:
            raise BundleError(f'Cannot read archive {path}: {exc}') from exc
        if seen != set(expected):
            raise BundleError(f'Missing tar members in {asset["name"]}: {sorted(set(expected)-seen)}')
    return data


def restore(manifest, asset_dir, root, group=None):
    data = verify(manifest, asset_dir, group); asset_dir = _root(asset_dir); root = _root(root, must_exist=False)
    missing, skipped = set(), []
    # Entire destination preflight precedes even directory creation.
    for asset in data['assets']:
        for item in asset['files']:
            path = _safe_path(root, item['path'])
            if path.exists():
                if path.stat().st_size != item['size'] or digest_file(path) != item['sha256']:
                    raise BundleError(f'Existing file differs; nothing restored: {item["path"]}')
                skipped.append(item['path'])
            else:missing.add(item['path'])
    restored = []
    for asset in data['assets']:
        if not any(item['path'] in missing for item in asset['files']):continue
        expected = {item['path']: item for item in asset['files']}
        with tarfile.open(_archive_path(asset_dir, asset['name']), 'r:gz') as archive:
            for member in archive:
                if member.name not in missing:continue
                item = expected[member.name]; path = _safe_path(root, member.name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path = _safe_path(root, member.name)  # Recheck after making parents.
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
                with os.fdopen(os.open(path, flags, 0o600), 'wb') as output, archive.extractfile(member) as source:
                    reader = _HashReader(source)
                    shutil.copyfileobj(reader, output, CHUNK)
                if reader.size != item['size'] or reader.hash.hexdigest() != item['sha256']:
                    raise BundleError(f'Archive changed during restoration: {member.name}')
                path.chmod(item.get('mode', member.mode) & 0o777)
                restored.append(member.name)
    return {'restored': restored, 'skipped_identical': skipped}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('pack'); p.add_argument('--selection', required=True); p.add_argument('--tag', required=True)
    p.add_argument('--output', required=True); p.add_argument('--manifest', required=True); p.add_argument('--root', default='.')
    for command in ['verify', 'restore']:
        p = sub.add_parser(command); p.add_argument('--manifest', required=True); p.add_argument('--asset-dir', required=True)
        p.add_argument('--group', action='append', help='Only this group; repeat to select several groups')
        if command == 'restore':p.add_argument('--root', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'pack':pack(args.selection, args.tag, args.output, args.manifest, args.root)
        elif args.command == 'verify':
            data = verify(args.manifest, args.asset_dir, args.group)
            print(f'VERIFIED {len(data["assets"])} assets and {sum(len(a["files"]) for a in data["assets"])} files')
        else:
            result = restore(args.manifest, args.asset_dir, args.root, args.group)
            print(f'RESTORED {len(result["restored"])} files; SKIPPED {len(result["skipped_identical"])} identical files')
    except (BundleError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr); return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
