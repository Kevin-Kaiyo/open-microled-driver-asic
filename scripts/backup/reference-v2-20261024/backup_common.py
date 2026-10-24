"""Shared milestone helpers. No action runs on import; all state stays in STAGE."""
from __future__ import annotations
import hashlib, importlib.util, json, os, re, stat, subprocess, urllib.request
from pathlib import Path

STAGE = Path(__file__).resolve().parent
ROOT = STAGE.parents[1]
TAG = 'reference-v2-20261024'
REPO = 'Kevin-Kaiyo/open-microled-driver-asic'
ROOTS = {'nrz': 'build/nrz-reference-v2', 'pwm': 'build/pwm-reference-v2', 'physical': 'build/reference-v2-layout', 'audit': 'build/reference-v2-audit'}
SUPPORT = ['build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf', 'build/blender-pwm-animation/fonts/LICENSE.txt']
ARCHIVE_LIMIT = 512 * 1024**2
PACK_TARGET = 480 * 1024**2
RESERVE_BYTES = 2 * 1024**3
CHUNK = 4 * 1024**2

def path(suffix): return STAGE / (TAG + suffix)
def read(p): return json.loads(Path(p).read_text())
def digest(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(CHUNK), b''): h.update(block)
    return h.hexdigest()
def write(p, value, exclusive=False):
    p = Path(p)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if exclusive:
        with p.open('x') as f: f.write(payload)
    else:
        temp = p.with_suffix(p.suffix + '.tmp')
        temp.write_text(payload); temp.replace(p)
def gh(*args):
    r = subprocess.run(['gh', *args], text=True, capture_output=True)
    if r.returncode: raise RuntimeError('gh command failed: ' + r.stderr.strip())
    return r.stdout
def bundle():
    spec = importlib.util.spec_from_file_location('milestone_bundle', ROOT / 'scripts/backup/release_bundle.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod
def safe_relative(value):
    p = Path(value)
    if p.is_absolute() or not value or any(x in ('', '.', '..') for x in value.split('/')):
        raise ValueError('Unsafe repository-relative path: ' + value)
    return p
def regular(relative):
    p = ROOT
    parts = safe_relative(relative).parts
    for i, part in enumerate(parts):
        p = p / part; mode = p.lstat().st_mode
        if stat.S_ISLNK(mode): raise ValueError('Symlink source: ' + relative)
        if i < len(parts)-1 and not stat.S_ISDIR(mode): raise ValueError('Non-directory ancestor: ' + relative)
    if not stat.S_ISREG(mode): raise ValueError('Not a regular file: ' + relative)
    return p
def group_for(prefix, relative):
    if prefix == 'physical': return 'physical-evidence'
    p = Path(relative)
    if p.name.endswith(('.dat', '.dat.gz', '.raw', '.raw.gz', '.vcd', '.vcd.gz', '.fst')):
        return prefix + '-waveforms'
    if 'inputs' in p.parts or 'execution-sources' in p.parts: return prefix + '-inputs'
    return prefix + '-metadata'
def inventory_tree():
    """Only the four declared roots and two explicit font files; never follow links."""
    files, exclusions = {}, []
    def exclude_link(p):
        rel = p.relative_to(ROOT).as_posix(); literal = os.readlink(p)
        target = Path(os.path.abspath(os.path.join(p.parent, literal)))
        try: internal = target.relative_to(ROOT).as_posix()
        except ValueError: internal = None
        exclusions.append({'path': rel, 'reason': 'symlink excluded; never dereferenced',
                           'target_repository_relative': internal,
                           'target_outside_repository': internal is None,
                           'original_link_was_absolute': os.path.isabs(literal)})
    for prefix, name in ROOTS.items():
        top = ROOT / name
        if top.is_symlink() or not top.is_dir(): raise ValueError('Missing or symlink scope root: ' + name)
        for directory, directories, names in os.walk(top, followlinks=False):
            directories.sort(); names.sort()
            for child in directories[:]:
                p = Path(directory) / child
                if p.is_symlink(): exclude_link(p); directories.remove(child)
                elif child == '__pycache__':
                    exclusions.append({'path': p.relative_to(ROOT).as_posix(), 'reason': 'rebuildable Python bytecode directory; not traversed'})
                    directories.remove(child)
            for name in names:
                p = Path(directory) / name; rel = p.relative_to(ROOT).as_posix()
                if p.is_symlink(): exclude_link(p); continue
                if p.suffix in ('.pyc', '.pyo'):
                    exclusions.append({'path': rel, 'reason': 'rebuildable Python bytecode'}); continue
                s = p.lstat()
                if not stat.S_ISREG(s.st_mode): raise ValueError('Unexpected special file; review before backup: ' + rel)
                files[rel] = {'size': s.st_size, 'mtime_ns': s.st_mtime_ns, 'mode': stat.S_IMODE(s.st_mode), 'group': group_for(prefix, rel)}
    for rel in SUPPORT:
        s = regular(rel).stat()
        files[rel] = {'size': s.st_size, 'mtime_ns': s.st_mtime_ns, 'mode': stat.S_IMODE(s.st_mode), 'group': 'report-support'}
    for x in exclusions:
        if 'target_repository_relative' in x:
            target = x['target_repository_relative']
            x['target_contents_selected'] = bool(target and (target in files or any(p.startswith(target + '/') for p in files)))
    return dict(sorted(files.items())), sorted(exclusions, key=lambda x: x['path'])
def check_inventory(expected, hashes=True):
    found, exclusions = inventory_tree()
    if set(found) != set(expected): raise ValueError('Selected file set changed after freeze')
    for rel, item in expected.items():
        if any(found[rel][k] != item[k] for k in ('size', 'mtime_ns', 'mode', 'group')):
            raise ValueError('Selected source metadata changed: ' + rel)
        if hashes and digest(regular(rel)) != item['sha256']: raise ValueError('Selected source bytes changed: ' + rel)
    return exclusions
def remote_release(source_commit):
    info = read_json_output(gh('repo', 'view', REPO, '--json', 'nameWithOwner,isPrivate'))
    if info['nameWithOwner'] != REPO or info['isPrivate']: raise ValueError('Expected existing public repository identity')
    ref = read_json_output(gh('api', f'repos/{REPO}/git/ref/tags/{TAG}'))['object']
    while ref['type'] == 'tag': ref = read_json_output(gh('api', f'repos/{REPO}/git/tags/{ref["sha"]}'))['object']
    if ref['type'] != 'commit' or ref['sha'] != source_commit: raise ValueError('Remote release tag/source commit mismatch')
    release = read_json_output(gh('api', f'repos/{REPO}/releases/tags/{TAG}'))
    if release['tag_name'] != TAG: raise ValueError('Release tag mismatch')
    return release
def read_json_output(value): return json.loads(value)
def expected_uploads():
    index = read(STAGE / 'upload-index.json')
    scope = read(path('-scope.json'))
    if index['source_commit'] != scope['source_commit'] or index['tag'] != TAG or index['repository'] != REPO:
        raise ValueError('Upload metadata identity mismatch')
    for item in index['files']:
        p = STAGE / safe_relative(item['local_path'])
        if p.is_symlink() or not p.is_file() or p.stat().st_size != item['size'] or digest(p) != item['sha256']:
            raise ValueError('Local upload file changed: ' + item['name'])
    return index
def stream_asset(asset, expected):
    if asset['state'] != 'uploaded' or asset['size'] != expected['size']: raise ValueError('Remote asset size/state mismatch: ' + expected['name'])
    if asset.get('digest') and asset['digest'] != 'sha256:' + expected['sha256']: raise ValueError('Remote API digest mismatch: ' + expected['name'])
    url = asset['browser_download_url']
    prefix = f'https://github.com/{REPO}/releases/download/{TAG}/'
    if not url.startswith(prefix): raise ValueError('Unexpected public Release download URL')
    h = hashlib.sha256(); count = 0
    request = urllib.request.Request(url, headers={'User-Agent': 'DriverRobustnessEvidenceReadback/1.0'})
    with urllib.request.urlopen(request, timeout=60) as f:
        for block in iter(lambda: f.read(CHUNK), b''): h.update(block); count += len(block)
    if count != expected['size'] or h.hexdigest() != expected['sha256']: raise ValueError('Downloaded SHA-256/size mismatch: ' + expected['name'])
    return {'remote_asset_id': asset['id'], 'name': expected['name'], 'size': count, 'sha256': h.hexdigest(), 'download_readback_verified': True, 'method': 'streamed SHA-256; no local download copy'}
