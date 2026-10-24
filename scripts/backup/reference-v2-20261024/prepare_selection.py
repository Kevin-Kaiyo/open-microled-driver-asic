#!/usr/bin/env python3
"""Run only after the parent freezes simulation/report generation. Does not pack/upload."""
import argparse, collections, datetime, json, re, subprocess
import backup_common as c

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--freeze-ack', action='store_true', help='Acknowledge all writers in the declared scope have stopped')
    p.add_argument('--source-commit', required=True, help='Exact public source commit to be tagged for this release')
    a = p.parse_args()
    if not a.freeze_ack: p.error('--freeze-ack is required; do not snapshot live simulations')
    if not re.fullmatch('[0-9a-f]{40}', a.source_commit): p.error('source commit must be a full lowercase SHA-1')
    actual = subprocess.check_output(['git', 'rev-parse', a.source_commit + '^{commit}'], cwd=c.ROOT, text=True).strip()
    if actual != a.source_commit: raise ValueError('Invalid source commit')
    for suffix in ['-selection.json', '-inventory.json', '-scope.json']:
        if c.path(suffix).exists(): raise ValueError('Preparation already exists; review rather than overwrite: ' + str(c.path(suffix)))
    files, exclusions = c.inventory_tree()
    groups = collections.defaultdict(list)
    for rel, item in files.items():
        if item['size'] > c.PACK_TARGET: raise ValueError('Single file exceeds safe 480 MiB packing target; preserve and losslessly split/compress by a separately reviewed step: ' + rel)
        item['sha256'] = c.digest(c.regular(rel)); groups[item['group']].append(rel)
    later_exclusions = c.check_inventory(files, hashes=False)
    if later_exclusions != exclusions: raise ValueError('Exclusion inventory changed during hashing')
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    selection = {'groups': [{'name': name, 'paths': paths} for name, paths in sorted(groups.items())]}
    scope = {'schema_version': 1, 'tag': c.TAG, 'repository': c.REPO, 'source_commit': a.source_commit,
             'prepared_at_utc': now, 'freeze_acknowledged': True,
             'scope': 'Only all regular non-bytecode files from the four new NRZ/PWM/reference-physical/independent-audit build trees, plus the explicitly named public report font and its license. Includes unsuccessful candidates, numerical failures, administrative interruptions and their available raw evidence.',
             'roots': c.ROOTS, 'explicit_report_support': c.SUPPORT,
             'standalone_restore_helpers': ['restore_symlinks.py', 'backup_common.py'],
             'groups': [{'name': name, 'files': len(paths), 'bytes': sum(files[x]['size'] for x in paths)} for name, paths in sorted(groups.items())],
             'exclusions': exclusions,
             'environment_exclusions': ['Full PDK installations, VM/container/tool/runtime dependencies and Python environments', 'Unrelated build trees and all other historical raw data', 'Symlinks listed explicitly; their selected target bytes are included independently', 'Rebuildable Python bytecode'],
             'baseline_dependencies': [{'release': 'driver-robustness-20261024', 'reason': 'Original selected B and PWM robustness inputs, baseline raw comparisons and prior actual layout. Restore original relative paths if rerunning those comparisons.'}],
             'restore': {'regular_files': 'Use scripts/backup/release_bundle.py restore with the SHA-256 manifest at the checkout root; it verifies all members and refuses conflicting files.', 'symlinks': 'After selected target bytes and any named prior-release dependency are restored, recreate only listed internal links using relative paths. Do not recreate external-target links automatically. See restore_symlinks.py --help.', 'absolute_paths_in_decks': 'Original saved decks and metadata remain byte-identical and may contain their original absolute workspace path. Reproduction entrypoints must regenerate decks for the new root; do not rewrite archived evidence in place.', 'full_PDK': 'Install the matching public PDK/rule decks/tools from the committed lock files separately; saved ngspice model files are only frozen subsets.'},
             'retention': 'No active raw input, waveform, failure log, PDK or working tree is removed. Only separately authorized staging/download duplicates may be cleaned after remote readback and restoration proof.',
             'archive_policy': {'maximum_bytes': c.ARCHIVE_LIMIT, 'uncompressed_batch_target_bytes': c.PACK_TARGET, 'readback': 'Sequential streaming SHA-256; no full downloaded copy on disk.'}}
    inventory = {'created_at_utc': now, 'files': files, 'total_bytes': sum(x['size'] for x in files.values())}
    c.write(c.path('-selection.json'), selection, exclusive=True)
    c.write(c.path('-inventory.json'), inventory, exclusive=True)
    c.write(c.path('-scope.json'), scope, exclusive=True)
    print(json.dumps({'selected_files': len(files), 'bytes': inventory['total_bytes'], 'groups': scope['groups'], 'symlinks_excluded': sum('target_repository_relative' in x for x in exclusions)}, indent=2))
if __name__ == '__main__': main()
