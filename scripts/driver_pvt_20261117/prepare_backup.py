#!/usr/bin/env python3
"""Pack reproducibility evidence by lane and verify every archive member locally."""
import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/backup'))
import release_bundle

TAG = 'driver-pvt-20261117'
BUILD = ROOT / 'build' / TAG
RELEASE = BUILD / 'release'
MANIFEST = ROOT / 'evidence' / TAG / 'raw-backup-manifest.json'
SUFFIXES = {'.spice', '.py', '.json', '.txt', '.log', '.dat', '.raw', '.gz', '.csv', '.npz', '.bin'}


def select():
    groups = []
    model_hashes = {}
    input_links = {}
    for lane in ['a', 'b', 'vcsel', 'clamp-probe']:
        inputs = BUILD / lane
        archive_paths = []
        for path in sorted(inputs.rglob('*')):
            if '__pycache__' in path.parts:
                continue
            relative = path.relative_to(ROOT).as_posix()
            if path.is_symlink():
                target = path.resolve(strict=True)
                target.relative_to(BUILD)
                input_links[relative] = target.relative_to(ROOT).as_posix()
                continue
            if not path.is_file():
                continue
            if path.suffix == '.ngspice' or 'pdk' in path.parts:
                model_hashes[relative] = release_bundle.digest_file(path)
            elif path.suffix in SUFFIXES:
                archive_paths.append(relative)
        if not archive_paths:
            raise ValueError(f'Missing runs in {inputs}')
        groups.append({'name': lane, 'paths': archive_paths})
    return {
        'groups': groups,
        'excluded_PDK_hashes': model_hashes,
        'input_links': input_links,
        'dependencies': ['driver-interface-20261115'],
        'scope': 'New lane inputs, decks, native waveforms and failure evidence. Matching GF180 model bytes and prior release restored separately.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--measure', action='store_true')
    args = parser.parse_args()
    selection = select()
    for group in selection['groups']:
        size = sum((ROOT / path).stat().st_size for path in group['paths'])
        print(group['name'], len(group['paths']), size, flush=True)
    if args.measure:
        return
    RELEASE.mkdir(exist_ok=True)
    if MANIFEST.exists():
        raise FileExistsError(f'Review existing archive {MANIFEST} before rebuilding')
    (RELEASE / 'selection.json').write_text(json.dumps(selection, indent=2) + '\n')
    models = {}
    for path, sha256 in selection['excluded_PDK_hashes'].items():
        if sha256 not in models:
            models[sha256] = {'example_path': path, 'count_excluded': 0, 'sha256': sha256}
        models[sha256]['count_excluded'] += 1
    (MANIFEST.parent / 'model-dependencies.json').write_text(json.dumps({
        'previous_release': 'driver-interface-20261115',
        'pdk_files_excluded': list(models.values()),
        'pdk_destinations': selection['excluded_PDK_hashes'],
        'input_links': selection['input_links'],
        'scope': 'Model bytes excluded from the raw release. Use matching model files at the locations in each case manifest.',
    }, indent=2) + '\n')
    assets = RELEASE / 'assets'
    release_bundle.pack(selection, TAG, assets, MANIFEST, ROOT)
    verified = release_bundle.verify(MANIFEST, assets)
    receipt = {'manifest_sha256': release_bundle.digest_file(MANIFEST),
               'archives': len(verified['assets']),
               'members': sum(len(asset['files']) for asset in verified['assets']),
               'archive_bytes': sum(asset['size'] for asset in verified['assets']),
               'local_archive_and_member_sha_verified': True}
    (RELEASE / 'pack-verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
