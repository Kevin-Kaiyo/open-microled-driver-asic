#!/usr/bin/env python3
"""Freeze-gated explicit raw backup; no upload, Git mutation or source cleanup.

The existing release_bundle API performs packing, member verification and safe
restoration. This helper selects only this milestone's approved raw scope.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
TAG = 'microled-dynamic-validation-20261108'
STAGE = Path('build/microled-dynamic-v1')
ELECTRICAL = STAGE / 'electrical/run-r1'
EVIDENCE = Path('evidence/microled-dynamic-v1')
TARGET_BYTES = 512 * 1024 ** 2
ENV_NAMES = {'venv', '.venv', 'env', '.env'}
REBUILDABLE = {'cache', 'states', 'state-cache', '__pycache__'}


class ArchiveError(ValueError):
    pass


@lru_cache(maxsize=1)
def bundle():
    spec = importlib.util.spec_from_file_location('dynamic_release_bundle', ROOT / 'scripts/backup/release_bundle.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 ** 2), b''):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ArchiveError(f'Cannot read required metadata {path}: {error}') from error


def emit(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def regular(root, relative):
    # Resolve the trusted root first: this workspace's visible Mac path is a
    # symlink, while release_bundle deliberately rejects a symlink root.
    value = relative.as_posix() if isinstance(relative, Path) else relative
    return bundle()._safe_path(root, value, must_exist=True)


def signature(path):
    info = path.stat()
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            stat.S_IMODE(info.st_mode)]


def discover(root):
    selected, excluded = [], []
    for section in ['electrical', 'receiver', 'calibration', 'report']:
        base = root / STAGE / section
        if not base.is_dir():
            raise ArchiveError(f'Missing required raw section: {base.relative_to(root)}')
        for folder, directories, names in os.walk(base, followlinks=False):
            folder = Path(folder)
            for name in list(directories):
                child = folder / name
                reason = None
                if name in ENV_NAMES or (child / 'pyvenv.cfg').is_file():
                    reason = 'Entire Python environment excluded; reinstall pinned dependencies'
                elif section != 'electrical' and name in REBUILDABLE:
                    reason = 'Regenerable filter states/bytecode excluded; original files remain local'
                if reason:
                    directories.remove(name)
                    excluded.append({'path': child.relative_to(root).as_posix(), 'recursive': True, 'reason': reason})
                elif child.is_symlink():
                    raise ArchiveError(f'Symlink inside approved raw scope: {child.relative_to(root)}')
            for name in names:
                path = folder / name
                rel = path.relative_to(root).as_posix()
                if path.is_symlink() or not path.is_file():
                    raise ArchiveError(f'Only regular raw files are allowed: {rel}')
                if section != 'electrical' and (path.suffix == '.pyc' or name.endswith(('-states.npz', 'states.npy'))):
                    excluded.append({'path': rel, 'reason': 'Regenerable bytecode/filter-state file; retained locally'})
                elif section == 'report' and path.suffix.lower() not in {'.log', '.json', '.txt', '.stdout', '.stderr'}:
                    excluded.append({'path': rel, 'reason': 'Report renders are in Git or regenerable; only rendering logs/metadata selected'})
                else:
                    selected.append(rel)
    if not selected:
        raise ArchiveError('Empty raw selection')
    return sorted(selected), sorted(excluded, key=lambda row: row['path'])


def readiness(root):
    ep = root / EVIDENCE / 'electrical-registry.json'
    rp = root / EVIDENCE / 'rx-summary.json'
    plan_path = root / ELECTRICAL / 'plan.json'
    manifest_path = root / ELECTRICAL / 'manifest.json'
    electrical, rx, plan, manifest = load(ep), load(rp), load(plan_path), load(manifest_path)
    names = {case['name'] for case in plan}
    transient = {case['name'] for case in plan if case.get('kind', 'transient') == 'transient'}
    records = electrical.get('records', [])
    if len(plan) != 49 or len(names) != 49 or len(transient) != 33 or len(records) != 49:
        raise ArchiveError('Freeze requires exactly 49 planned/attempted electrical cases and 33 transient cases')
    if {r['case']['name'] for r in records} != names or electrical.get('missing'):
        raise ArchiveError('Missing/duplicate electrical cases; backup refused')
    successful = {r['case']['name'] for r in records if r['case'].get('kind', 'transient') == 'transient'
                  and r.get('simulation_ok') and not r.get('analysis_error')}
    if successful != transient:
        raise ArchiveError('All 33 successful transient source records are required before freezing')
    for record in records:
        if sha(regular(root, record['result_path'])) != record['result_sha256']:
            raise ArchiveError(f'Electrical result identity changed: {record["case"]["name"]}')
        if record.get('simulation_ok') and not record.get('waveform_path'):
            raise ArchiveError(f'Successful case has no native waveform identity: {record["case"]["name"]}')
        if record.get('waveform_path') and sha(regular(root, record['waveform_path'])) != record['gzip_sha256']:
            raise ArchiveError(f'Native waveform identity changed: {record["case"]["name"]}')
        if record.get('deck_sha256'):
            deck = Path(record['result_path']).with_name('testbench.spice')
            if sha(regular(root, deck)) != record['deck_sha256']:
                raise ArchiveError(f'Electrical deck identity changed: {record["case"]["name"]}')
    if rx.get('analysis_failures') or rx.get('missing_electrical') or rx.get('electrical_failures'):
        raise ArchiveError('RX metadata reports missing/failed cases; backup refused')
    if rx.get('stage_status') != 'complete' or rx.get('selection_filter'):
        raise ArchiveError('Only a complete, unfiltered RX summary may be frozen')
    full = [r for r in rx.get('records', []) if r.get('stage') == 'full']
    if {r['case_name'] for r in full} != transient or len(full) != 33 * 4:
        raise ArchiveError('RX must cover all 33 successful cases, each with four optical tau hypotheses')
    for name in transient:
        if {r['optical_tau_ps'] for r in full if r['case_name'] == name} != {0, 25, 75, 200}:
            raise ArchiveError(f'Incomplete/duplicate RX tau set: {name}')
    for record in rx.get('records', []):
        if sha(regular(root, record['analysis_path'])) != record['analysis_sha256']:
            raise ArchiveError(f'RX analysis identity changed: {record["case_name"]}')
        if record.get('eye_path') and sha(regular(root, record['eye_path'])) != record['eye_sha256']:
            raise ArchiveError(f'RX eye identity changed: {record["case_name"]}')
    baselines = rx.get('baseline_200ps_reproduction', [])
    if len(baselines) != 33 or {r['case_name'] for r in baselines} != transient or not all(r.get('passed') for r in baselines):
        raise ArchiveError('The 33 unchanged 200ps receiver reproduction checks are required')
    if rx.get('electrical_registry_sha256') != sha(ep):
        raise ArchiveError('RX summary is not bound to the final electrical registry')
    if electrical.get('manifest_sha256') != sha(manifest_path):
        raise ArchiveError('Electrical registry is not bound to the frozen manifest')
    for directory, entries in [('inputs', manifest['inputs']), ('execution-sources', manifest['source_snapshots'])]:
        for relative, expected in entries.items():
            if sha(regular(root, ELECTRICAL / directory / relative)) != expected:
                raise ArchiveError(f'Frozen input/source changed: {directory}/{relative}')
    for relative, key in [('plan.json', 'plan_sha256'), ('stimulus.json', 'stimulus_sha256')]:
        if sha(regular(root, ELECTRICAL / relative)) != manifest[key]:
            raise ArchiveError(f'Frozen {relative} changed')
    return {'attempted_electrical_cases': 49, 'successful_RX_source_cases': 33, 'DC_case_records': 16,
            'full_RX_hypotheses': len(full), 'baseline_200ps_reproductions': len(baselines),
            'electrical_registry_sha256': sha(ep), 'rx_summary_sha256': sha(rp),
            'electrical_manifest_sha256': sha(manifest_path)}


def active_writers(root, selected):
    command = shutil.which('lsof')
    if not command:
        raise ArchiveError('lsof is required for the default active-writer guard; install it before prepare/pack')
    proc = subprocess.run([command, '-nP', '-F', 'pan', '+D', str(root / STAGE)],
                          capture_output=True, text=True, timeout=45)
    if proc.returncode not in (0, 1):
        raise ArchiveError('lsof writer guard failed: ' + proc.stderr.strip())
    wanted = {str(root / name) for name in selected}
    pid, access, writers = None, None, []
    for line in proc.stdout.splitlines():
        if line.startswith('p'):
            pid = line[1:]
        elif line.startswith('a'):
            access = line[1:]
        elif line.startswith('n') and line[1:] in wanted and access in {'w', 'u'}:
            writers.append({'pid': pid, 'path': Path(line[1:]).relative_to(root).as_posix(), 'access': access})
    if writers:
        raise ArchiveError('Selected raw files have active write handles: ' + json.dumps(writers, ensure_ascii=False))


def frozen_inventory(root, quiet_seconds):
    paths, excluded = discover(root)
    active_writers(root, paths)
    before = {name: signature(regular(root, name)) for name in paths}
    time.sleep(quiet_seconds)
    again, exclusions_again = discover(root)
    if paths != again or excluded != exclusions_again or any(signature(root / name) != before[name] for name in paths):
        raise ArchiveError('Raw inventory/logs changed during the quiet interval; stop writers and retry')
    files = []
    for name in paths:
        path = regular(root, name)
        digest = sha(path)
        if signature(path) != before[name]:
            raise ArchiveError(f'Raw file changed while hashing: {name}')
        files.append({'path': name, 'size': path.stat().st_size, 'sha256': digest,
                      'mode': stat.S_IMODE(path.stat().st_mode) & 0o777})
    active_writers(root, paths)
    if discover(root)[0] != paths or any(signature(root / name) != before[name] for name in paths):
        raise ArchiveError('Raw sources changed during inventory hashing')
    return files, excluded


def provenance(root, source_commit):
    if not re.fullmatch(r'[0-9a-f]{40}', source_commit):
        raise ArchiveError('--source-commit must be the exact 40-character reviewed source commit for this tag')
    paths = [Path('scripts/backup/release_bundle.py')]
    paths += [p.relative_to(root) for p in (root / 'scripts/microled_dynamic_v1').glob('*.py')] if root == ROOT else []
    paths += [p.relative_to(root) for p in (root / EVIDENCE).glob('*') if p.is_file()]
    paths += [Path('analog/models/measured-led/lin2026-yellow20-diamond-iv.csv'),
              Path('evidence/microled-dynamic-20261029/yellow20-s21-selected.csv'),
              Path('evidence/microled-dynamic-20261029/yellow20-optical-power.csv')]
    return {'tag': TAG, 'source_commit': source_commit,
            'source_commit_status': 'supplied by caller; helper performs no Git operations or tag publication',
            'root_policy': 'Trusted repository root resolved with Path.resolve before release_bundle API calls; archived members are repository relative',
            'Git_source_and_compact_evidence': [{'path': p.as_posix(), 'sha256': sha(regular(root, p))} for p in sorted(set(paths))],
            'scientific_scope': 'Raw schematic experiments, conditional magnitude fits and synthetic RX sensitivity only; no physical dynamic/optical qualification'}


def prepare(root, output, source_commit, quiet_seconds=3.):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(root / STAGE):
        raise ArchiveError('Use a fresh output directory outside the selected raw stage')
    ready_before = readiness(root)
    prov_before = provenance(root, source_commit)
    files, excluded = frozen_inventory(root, quiet_seconds)
    if ready_before != readiness(root) or prov_before != provenance(root, source_commit):
        raise ArchiveError('Readiness/source evidence changed while preparing')
    paths = [row['path'] for row in files]
    waveforms = [p for p in paths if '/electrical/' in p and p.endswith(('.dat', '.dat.gz'))]
    metadata = sorted(set(paths) - set(waveforms))
    selection = {'groups': [{'name': group, 'paths': values} for group, values in [('metadata', metadata), ('waveforms', waveforms)] if values]}
    scope = {'tag': TAG, 'selected_regular_files': len(files), 'original_bytes': sum(x['size'] for x in files),
             'selected_trees': ['electrical: all regular raw files including original manifest-locked r1 bytecode',
                                'receiver: analysis/eyes/fixtures/logs; filter-state caches excluded',
                                'calibration: all trials/failures/logs except Python environment/bytecode',
                                'report: rendering logs and metadata only'],
             'exclusions': excluded,
             'outside_scope': ['all historical build trees', 'full Python environments', 'private paper PDFs/HTML/images',
                               'full PDK/VMs', 'regenerable receiver/cache filter states', 'Git source/compact report data already carried by the source tag'],
             'receiver_cache_restore': 'Recompute filtered states from restored native conduction traces with the exact tagged analyze.py. Eye NPZ files remain archived.',
             'originals_removed': False, 'upload_performed': False, 'target_uncompressed_part_bytes': TARGET_BYTES}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.' + output.name + '.preparing-', dir=output.parent))
    try:
        for name, value in [('selection.json', selection), ('files-sha256.json', files), ('scope.json', scope),
                            ('provenance.json', prov_before), ('readiness.json', ready_before)]:
            emit(temporary / name, value)
        if output.exists():
            raise ArchiveError('Prepared output appeared concurrently')
        temporary.rename(output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)  # Only this helper's incomplete, newly created preparation directory.
    return scope


def pack_prepared(root, prepared, freeze_confirmed=False, quiet_seconds=3., target_bytes=TARGET_BYTES):
    if not freeze_confirmed:
        raise ArchiveError('Packing requires --freeze-confirmed after the parent has frozen all writers and reviewed readiness/scope')
    root, prepared = Path(root).resolve(), Path(prepared).resolve()
    if load(prepared / 'readiness.json') != readiness(root):
        raise ArchiveError('Final electrical/RX identity changed since prepare')
    saved_provenance = load(prepared / 'provenance.json')
    if saved_provenance != provenance(root, saved_provenance['source_commit']):
        raise ArchiveError('Source/compact evidence changed since prepare')
    current, excluded = frozen_inventory(root, quiet_seconds)
    if current != load(prepared / 'files-sha256.json') or excluded != load(prepared / 'scope.json')['exclusions']:
        raise ArchiveError('Raw file set or SHA changed since prepare; make a fresh preparation')
    selection = load(prepared / 'selection.json')
    selected = [p for group in selection['groups'] for p in group['paths']]
    if sorted(selected) != sorted(row['path'] for row in current):
        raise ArchiveError('Explicit selection differs from the approved per-file manifest')
    manifest = prepared / (TAG + '.json')
    lib = bundle()
    data = lib.pack(selection, TAG, prepared / 'assets', manifest, root=root, target_bytes=target_bytes)
    lib.verify(manifest, prepared / 'assets')
    # Final post-pack identity check supplements release_bundle's per-file stream checks.
    if discover(root)[0] != [row['path'] for row in current]:
        raise ArchiveError('Raw file set changed during packing; retain output as unaccepted local archives')
    active_writers(root, [row['path'] for row in current])
    if readiness(root) != load(prepared / 'readiness.json') or provenance(root, saved_provenance['source_commit']) != saved_provenance:
        raise ArchiveError('Readiness/source evidence changed during packing; retain archives as unaccepted local output')
    for item in current:
        if sha(root / item['path']) != item['sha256']:
            raise ArchiveError('Source changed during packing: ' + item['path'])
    receipt = {'tag': TAG, 'source_commit': saved_provenance['source_commit'], 'manifest_sha256': sha(manifest),
               'files': len(current), 'original_bytes': sum(row['size'] for row in current),
               'assets': [{k: a[k] for k in ['name', 'size', 'sha256']} for a in data['assets']],
               'local_archive_and_members_verified': True, 'remote_readback_verified': False,
               'freeze_confirmed_by_caller': True, 'originals_removed': False, 'upload_performed': False}
    emit(prepared / 'archive-local.json', receipt)
    return receipt


def fixture(root):
    def put(relative, text='tiny fixture\n'):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path
    def js(relative, obj):
        return put(relative, json.dumps(obj))
    for section in ['electrical', 'receiver', 'calibration', 'report']:
        put(STAGE / section / 'fixture.log')
    put(ELECTRICAL / 'inputs/fixture.spice')
    put(ELECTRICAL / 'inputs/__pycache__/receiver.cpython-312.pyc', 'locked original identity')
    put(ELECTRICAL / 'execution-sources/legacy_engine.py', 'pass\n')
    stimulus = put(ELECTRICAL / 'stimulus.json', '{}')
    plan = [{'name': f'TR-{i}'} for i in range(33)] + [{'name': f'DC-{i}', 'kind': 'dc'} for i in range(16)]
    plan_path = js(ELECTRICAL / 'plan.json', plan)
    manifest = {'inputs': {'fixture.spice': sha(root / ELECTRICAL / 'inputs/fixture.spice'), '__pycache__/receiver.cpython-312.pyc': sha(root / ELECTRICAL / 'inputs/__pycache__/receiver.cpython-312.pyc')},
                'source_snapshots': {'legacy_engine.py': sha(root / ELECTRICAL / 'execution-sources/legacy_engine.py')},
                'stimulus_sha256': sha(stimulus), 'plan_sha256': sha(plan_path)}
    manifest_path = js(ELECTRICAL / 'manifest.json', manifest)
    records = []
    for case in plan:
        relative = ELECTRICAL / 'cases' / case['name'] / 'result.json'
        path = js(relative, {'case': case, 'simulation_ok': True})
        wave = put(relative.with_name('waveform.dat.gz'), 'tiny raw waveform')
        deck = put(relative.with_name('testbench.spice'))
        records.append({'case': case, 'simulation_ok': True, 'analysis_error': None,
                        'result_path': relative.as_posix(), 'result_sha256': sha(path),
                        'waveform_path': wave.relative_to(root).as_posix(), 'gzip_sha256': sha(wave), 'deck_sha256': sha(deck)})
    ep = js(EVIDENCE / 'electrical-registry.json', {'records': records, 'missing': [], 'manifest_sha256': sha(manifest_path)})
    full = [{'case_name': f'TR-{i}', 'stage': 'full', 'optical_tau_ps': tau} for i in range(33) for tau in [0, 25, 75, 200]]
    for row in full:
        path = js(STAGE / 'receiver/cases' / row['case_name'] / f"tau{row['optical_tau_ps']}.json", {'fixture': True})
        row.update(analysis_path=path.relative_to(root).as_posix(), analysis_sha256=sha(path))
    js(EVIDENCE / 'rx-summary.json', {'records': full, 'stage_status': 'complete', 'analysis_failures': [], 'missing_electrical': [], 'electrical_failures': [],
        'electrical_registry_sha256': sha(ep), 'baseline_200ps_reproduction': [{'case_name': f'TR-{i}', 'passed': True} for i in range(33)]})
    for relative in ['scripts/backup/release_bundle.py', 'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv',
                     'evidence/microled-dynamic-20261029/yellow20-s21-selected.csv', 'evidence/microled-dynamic-20261029/yellow20-optical-power.csv']:
        put(relative)
    put(STAGE / 'receiver/cache/excluded.npz')
    put(STAGE / 'receiver/eyes/retained.npz')
    put(STAGE / 'calibration/venv/private-environment')
    put(Path('build/historical/private-paper.pdf'))


def self_test():
    with tempfile.TemporaryDirectory(prefix='microled-archive-selftest-') as temporary:
        base = Path(temporary).resolve()
        root, output = base / 'fixture-repo', base / 'prepared'
        root.mkdir()
        fixture(root)
        paths, _ = discover(root)
        assert any(p.endswith('receiver.cpython-312.pyc') for p in paths)
        assert any('/eyes/' in p for p in paths)
        assert not any('/cache/' in p or '/venv/' in p or 'private-paper' in p for p in paths)
        registry_path = root / EVIDENCE / 'electrical-registry.json'
        registry_bytes = registry_path.read_bytes()
        incomplete = load(registry_path)
        incomplete['missing'] = ['TR-0']
        registry_path.write_text(json.dumps(incomplete))
        try:
            readiness(root)
            raise AssertionError('Missing electrical case was not rejected')
        except ArchiveError:
            pass
        registry_path.write_bytes(registry_bytes)
        with (root / STAGE / 'receiver/fixture.log').open('a'):
            try:
                active_writers(root, paths)
                raise AssertionError('Active writer was not rejected')
            except ArchiveError:
                pass
        prepare(root, output, '0' * 40, quiet_seconds=.01)
        try:
            pack_prepared(root, output)
            raise AssertionError('Unconfirmed freeze was not rejected')
        except ArchiveError:
            pass
        changed = root / STAGE / 'calibration/fixture.log'
        saved = changed.read_bytes()
        changed.write_bytes(saved + b'changed')
        try:
            pack_prepared(root, output, True, quiet_seconds=.01)
            raise AssertionError('Changed source was not rejected')
        except ArchiveError:
            pass
        changed.write_bytes(saved)
        receipt = pack_prepared(root, output, True, quiet_seconds=.01, target_bytes=4096)
        lib, manifest, assets = bundle(), output / (TAG + '.json'), output / 'assets'
        lib.verify(manifest, assets)
        restored = base / 'restored'
        result = lib.restore(manifest, assets, restored)
        assert len(result['restored']) == receipt['files']
        assert not lib.restore(manifest, assets, restored)['restored']
        conflict = restored / paths[0]
        conflict.write_text('conflicting pre-existing file')
        try:
            lib.restore(manifest, assets, restored)
            raise AssertionError('Restore conflict was not rejected')
        except lib.BundleError:
            pass
        asset = assets / receipt['assets'][0]['name']
        data = asset.read_bytes()
        asset.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
        try:
            lib.verify(manifest, assets)
            raise AssertionError('Corrupted archive was not rejected')
        except lib.BundleError:
            pass
        print(json.dumps({'self_test': 'PASS', 'temporary_fixture_only': True, 'files': receipt['files'],
                          'checks': ['scope exclusions and locked bytecode', 'missing-case rejection', 'active writer rejection', 'freeze gate',
                                     'changed raw SHA rejection', 'pack/member verification', 'restore/idempotence/conflict', 'archive corruption rejection']}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--source-commit', required=True)
    p.add_argument('--quiet-seconds', type=float, default=3.)
    p = sub.add_parser('pack')
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--prepared', type=Path, required=True)
    p.add_argument('--freeze-confirmed', action='store_true')
    p.add_argument('--quiet-seconds', type=float, default=3.)
    for action in ['verify', 'restore']:
        p = sub.add_parser(action)
        p.add_argument('--manifest', type=Path, required=True)
        p.add_argument('--asset-dir', type=Path, required=True)
        p.add_argument('--group', action='append')
        if action == 'restore':
            p.add_argument('--destination', type=Path, required=True)
    sub.add_parser('self-test')
    args = parser.parse_args()
    try:
        if args.action == 'prepare':
            if not 0 < args.quiet_seconds <= 60:
                raise ArchiveError('Quiet interval must be >0 and <=60 seconds')
            result = prepare(args.root, args.output, args.source_commit, args.quiet_seconds)
        elif args.action == 'pack':
            if not 0 < args.quiet_seconds <= 60:
                raise ArchiveError('Quiet interval must be >0 and <=60 seconds')
            result = pack_prepared(args.root, args.prepared, args.freeze_confirmed, args.quiet_seconds)
        elif args.action == 'verify':
            result = bundle().verify(args.manifest.resolve(), args.asset_dir.resolve(), args.group)
            result = {'verified_assets': len(result['assets']), 'verified_files': sum(len(a['files']) for a in result['assets'])}
        elif args.action == 'restore':
            result = bundle().restore(args.manifest.resolve(), args.asset_dir.resolve(), args.destination.resolve(), args.group)
        else:
            self_test()
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ArchiveError, bundle().BundleError, OSError, subprocess.SubprocessError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
