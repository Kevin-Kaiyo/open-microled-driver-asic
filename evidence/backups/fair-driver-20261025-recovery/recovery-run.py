#!/usr/bin/env python3
"""Independent public Release small-input restoration and one same-host DC smoke.

Writes only beside this file under recovery/. Never removes original evidence,
downloads waveform archives, uploads, commits, or changes frozen circuitry.
"""
from pathlib import Path
import datetime
import gzip
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve()
STAGE = SCRIPT.parent
ORIGINAL_ROOT = STAGE.parent.parent
RECOVERY = STAGE / 'recovery'
CHECKOUT = RECOVERY / 'checkout'
DOWNLOADS = RECOVERY / 'downloads'
RUNTIME = ORIGINAL_ROOT / 'build/layout/venv/bin/python'
REPO = 'Kevin-Kaiyo/open-microled-driver-asic'
ORIGIN = 'https://github.com/' + REPO + '.git'
TAG = 'fair-driver-20261025'
COMMIT = 'd203aa748de36c96a4d51605bc5acaae94b0b759'
MANIFEST_SHA = '3a9af00442308fe7c01034d64c834e65456803968e47ecc4b4b44e725393f7b2'
SCOPE_SHA = '88eb9b83dc2c868389cd99723203a93be42aad64bcb10e88342618a6192bd24b'
RUNNER_SHA = '0316afadb96dabc2c7554214bad408779d8f07ea3b430074140899c685a92873'
GROUPS = ['inputs', 'results']
FLOOR = 5 * 1024**3
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', GIT_TERMINAL_PROMPT='0')
RECEIPT = {}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def record_file(path, base=RECOVERY):
    path = Path(path)
    return {'path': str(path.relative_to(base)), 'bytes': path.stat().st_size,
            'sha256': sha(path)}


def save():
    temp = RECOVERY / 'check.json.tmp'
    temp.write_text(json.dumps(RECEIPT, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    temp.replace(RECOVERY / 'check.json')


def guard(extra=0):
    free = shutil.disk_usage(STAGE).free
    assert free >= FLOOR + extra, f'5 GiB free-space guard: free={free}, reserved writes={extra}'
    return free


def command(label, argv, cwd=RECOVERY, timeout=600):
    guard()
    output_path = RECOVERY / 'logs' / (label + '.log')
    assert not output_path.exists(), 'Refuse command-log overwrite'
    start = time.monotonic()
    entry = {'label': label, 'argv': [str(x) for x in argv], 'cwd': str(cwd),
             'started_utc': now(), 'timeout_s': timeout}
    try:
        process = subprocess.run(entry['argv'], cwd=cwd, env=ENV, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        output, code = process.stdout, process.returncode
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ''
        if isinstance(output, bytes): output = output.decode(errors='replace')
        output += '\nRECOVERY COMMAND TIMEOUT\n'
        code = None
    output_path.write_text(output)
    entry.update(exit_code=code, elapsed_s=time.monotonic()-start,
                 log=record_file(output_path))
    RECEIPT['commands'].append(entry)
    save()
    assert code == 0, f'{label} failed (exit={code}); retain {output_path}'
    return output


def original_tree_metadata():
    """Read-only metadata identity; not a second independent full content hash."""
    h = hashlib.sha256()
    count = total = 0
    for dirname in ['fair-driver-v1', 'fair-driver-v1-a-probe', 'fair-driver-v1-c-probe']:
        root = ORIGINAL_ROOT / 'build' / dirname
        for current, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not (Path(current)/d).is_symlink())
            for name in sorted(files):
                path = Path(current)/name
                st = path.lstat()
                row = [str(path.relative_to(ORIGINAL_ROOT)), st.st_size, st.st_mtime_ns, st.st_mode]
                h.update((json.dumps(row, separators=(',', ':'))+'\n').encode())
                count += 1
                total += st.st_size
    return {'files': count, 'bytes': total, 'path_size_mtime_mode_sha256': h.hexdigest()}


def validate_restored(assets):
    rows = []
    for asset in assets:
        for item in asset['files']:
            path = CHECKOUT / item['path']
            assert path.resolve().is_relative_to(CHECKOUT.resolve()) and not path.is_symlink()
            assert path.is_file() and path.stat().st_size == item['size']
            assert sha(path) == item['sha256'], 'Restored file mismatch: '+item['path']
            rows.append({'path': item['path'], 'bytes': item['size'], 'sha256': item['sha256'],
                         'group': asset['group']})
    assert len(rows) == len({x['path'] for x in rows})
    return rows


def smoke():
    """Child process, using only downloaded frozen source and relocated paths."""
    assert Path.cwd().resolve() == CHECKOUT.resolve()
    assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip() == COMMIT
    source = CHECKOUT/'build/fair-driver-v1/matched-r2'
    original_path = source/'cases/DC-TT-B-L0/result.json'
    original = json.loads(original_path.read_text())
    runner_path = source/'execution-sources'/('run-'+RUNNER_SHA+'.py')
    assert original['runner_sha256'] == sha(runner_path) == RUNNER_SHA
    work = CHECKOUT/'build/fair-driver-v1/recovery-dc-r1'
    assert not work.exists(), 'Refuse reuse of a previous recovery case'
    shutil.copytree(source/'inputs',work/'inputs')
    for name in ['manifest.json','stimulus.json']:
        shutil.copy2(source/name,work/name)
    spec = importlib.util.spec_from_file_location('frozen_fair_runner',runner_path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    original_paths = {key:str(getattr(runner,key)) for key in ['ROOT','BUILD','MODELS']}
    runner.ROOT = CHECKOUT
    runner.BUILD = CHECKOUT/'build/fair-driver-v1'
    runner.MODELS = source/'inputs'
    runner.verify(work)
    case = dict(original['case'],name='DC-TT-B-L0-recovery')
    fresh = runner.run(work,case)
    assert fresh['simulation_ok'] and 'metrics' in fresh, 'DC simulation/analysis failed; retain logs'
    actual, expected = fresh['metrics'], original['metrics']
    delta = actual['i_led_A']-expected['i_led_A']
    assert set(actual['energy']) == set(expected['energy']) and len(actual['energy']) == 7
    powers = {key:actual['energy'][key]['DC_power_W']-value['DC_power_W']
              for key,value in expected['energy'].items()}
    passed = abs(delta) <= 1e-12 and all(abs(value) <= 1e-10 for value in powers.values())
    casefolder = work/'cases'/case['name']
    includes = re.findall(r'^\.(?:include|lib)\s+"([^"]+)"', (casefolder/'testbench.spice').read_text(),re.M)
    assert includes and all(Path(value).resolve().is_relative_to(work/'inputs') for value in includes)
    assert fresh['runner_sha256'] == RUNNER_SHA
    with gzip.open(casefolder/'waveform.dat.gz','rb') as stream:
        raw_sha = hashlib.sha256(stream.read()).hexdigest()
    assert raw_sha == fresh['raw_sha256']
    receipt = {'source_commit':COMMIT,'runner_sha256':RUNNER_SHA,
               'original_result':record_file(original_path,CHECKOUT),
               'fresh_result':record_file(casefolder/'result.json',CHECKOUT),
               'parent_manifest_sha256':sha(source/'manifest.json'),
               'new_manifest_is_byte_identical':sha(source/'manifest.json') == sha(work/'manifest.json'),
               'path_relocation_only':['ROOT','BUILD','MODELS'], 'path_constants_before':original_paths,
               'path_constants_after':{key:str(getattr(runner,key)) for key in original_paths},
               'all_deck_includes_use_new_inputs':True,
               'case':case,'simulation_exit_code':fresh['exit_code'],
               'simulation_ok':fresh['simulation_ok'],'sample_count':actual['sample_count'],
               'original_current_A':expected['i_led_A'],'fresh_current_A':actual['i_led_A'],
               'current_difference_A':delta,'current_tolerance_A':1e-12,
               'port_power_tolerance_W':1e-10,'port_power_differences_W':powers,
               'original_port_power_W':{key:value['DC_power_W'] for key,value in expected['energy'].items()},
               'fresh_port_power_W':{key:value['DC_power_W'] for key,value in actual['energy'].items()},
               'fresh_device_voltage_passed':actual['device_voltage_passed'],
               'fresh_current_error_percent':actual['current_error_percent'],
               'raw_sha256':raw_sha,'reproduction_passed':passed,
               'boundary':'Same host/OS/runtime; one B TT L0 DC only. No NRZ rerun, new optical/physical evidence, or full-matrix qualification.'}
    (RECOVERY/'smoke-check.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
    assert passed, 'DC numerical reproduction exceeded predeclared tolerance'


def main():
    assert not RECOVERY.exists(), 'Refuse an existing recovery directory; no automatic cleanup/retry'
    free_before = guard()
    RECOVERY.mkdir()
    (RECOVERY/'logs').mkdir()
    DOWNLOADS.mkdir()
    RECEIPT.update(schema_version=1,started_utc=now(),status='running',repository=REPO,
                   tag=TAG,expected_source_commit=COMMIT,trusted_manifest_sha256=MANIFEST_SHA,
                   trusted_scope_sha256=SCOPE_SHA,recovery_script_sha256=sha(SCRIPT),
                   commands=[],downloads=[],free_bytes_before=free_before,
                   free_floor_bytes=FLOOR,original_tree_metadata_before=original_tree_metadata(),
                   boundary={'same_host':True,'same_OS':True,'existing_runtime':str(RUNTIME),
                             'runtime_resolved':str(RUNTIME.resolve()),'platform':platform.platform(),
                             'download_groups':GROUPS,'waveform_archives_downloaded':False,
                             'new_case':'B typical 27 C 3.3 V logic, level 0, DC only',
                             'no_original_evidence_cleanup':True,'no_commit_or_upload':True})
    save()
    try:
        command('origin',['git','remote','get-url','origin'],ORIGINAL_ROOT)
        before_tag = command('tag-before',['git','ls-remote',ORIGIN,'refs/tags/'+TAG,'refs/tags/'+TAG+'^{}'])
        command('clone',['git','clone','--depth','1','--branch',TAG,ORIGIN,str(CHECKOUT)],timeout=900)
        head = command('checkout-HEAD',['git','rev-parse','HEAD'],CHECKOUT).strip()
        tag = command('checkout-tag',['git','rev-parse',TAG+'^{commit}'],CHECKOUT).strip()
        assert head == tag == COMMIT
        remote_rows = dict(row.split('\t')[::-1] for row in before_tag.strip().splitlines())
        assert remote_rows.get('refs/tags/'+TAG+'^{}',remote_rows.get('refs/tags/'+TAG)) == COMMIT
        RECEIPT['source_commit'] = head
        release = json.loads(command('release-before',['gh','api','repos/'+REPO+'/releases/tags/'+TAG]))
        assert release['tag_name'] == TAG and not release['draft']
        assets_by_name = {a['name']:a for a in release['assets']}
        assert len(assets_by_name) == len(release['assets'])
        names = [TAG+'.json',TAG+'-scope.json']
        for name in names:
            assert name in assets_by_name
            command('download-'+name,['gh','release','download',TAG,'--repo',REPO,'--dir',str(DOWNLOADS),'--pattern',name])
        manifest_path = DOWNLOADS/(TAG+'.json')
        scope_path = DOWNLOADS/(TAG+'-scope.json')
        assert sha(manifest_path) == MANIFEST_SHA
        assert sha(scope_path) == SCOPE_SHA
        manifest = json.loads(manifest_path.read_text())
        scope = json.loads(scope_path.read_text())
        assert scope['source_commit'] == COMMIT and manifest['tag'] == TAG
        assert scope['repository'] == REPO and scope['restore_small_groups'] == GROUPS
        for relative,wanted in scope['helper_sha256'].items():
            assert sha(CHECKOUT/relative) == wanted, 'Source helper mismatch: '+relative
        chosen = [asset for asset in manifest['assets'] if asset['group'] in GROUPS]
        assert {a['group'] for a in chosen} == set(GROUPS)
        guard(sum(a['size']+sum(f['size'] for f in a['files']) for a in chosen))
        for asset in chosen:
            name = asset['name']
            assert Path(name).name == name and name in assets_by_name
            command('download-'+name,['gh','release','download',TAG,'--repo',REPO,'--dir',str(DOWNLOADS),'--pattern',name])
            assert (DOWNLOADS/name).stat().st_size == asset['size']
            assert sha(DOWNLOADS/name) == asset['sha256']
            names.append(name)
        assert set(p.name for p in DOWNLOADS.iterdir()) == set(names)
        for name in names:
            entry = record_file(DOWNLOADS/name)
            metadata = assets_by_name[name]
            assert entry['bytes'] == metadata['size']
            if metadata.get('digest'):
                assert metadata['digest'] == 'sha256:'+entry['sha256']
            entry['release_asset'] = {key:metadata.get(key) for key in ['id','name','size','digest','updated_at','browser_download_url']}
            RECEIPT['downloads'].append(entry)
        save()
        output = command('restore',[str(RUNTIME),'-B',str(CHECKOUT/'scripts/backup/release_bundle.py'),'restore',
                        '--manifest',str(manifest_path),'--asset-dir',str(DOWNLOADS),'--root',str(CHECKOUT),
                        '--group','inputs','--group','results'],CHECKOUT)
        counts = re.search(r'RESTORED (\d+) files; SKIPPED (\d+) identical files',output)
        assert counts and int(counts[2]) == 0
        restored = validate_restored(chosen)
        assert len(restored) == int(counts[1])
        (RECOVERY/'restored-files.json').write_text(json.dumps(restored,indent=2)+'\n')
        RECEIPT['restore'] = {'restored':len(restored),'skipped_identical':int(counts[2]),
                              'per_file_sha256_all_verified':True,
                              'groups':{group:sum(x['group']==group for x in restored) for group in GROUPS},
                              'manifest':record_file(RECOVERY/'restored-files.json')}
        command('runtime',[str(RUNTIME),'-B','-c','import sys,numpy; print(sys.version); print("numpy="+numpy.__version__)'])
        command('ngspice-version',['ngspice','--version'])
        command('DC-smoke',[str(RUNTIME),'-B',str(SCRIPT),'--smoke'],CHECKOUT)
        RECEIPT['DC_smoke'] = json.loads((RECOVERY/'smoke-check.json').read_text())
        assert RECEIPT['DC_smoke']['reproduction_passed']
        assert validate_restored(chosen) == restored, 'Restored evidence changed during smoke'
        assert command('checkout-clean',['git','status','--porcelain','--untracked-files=no'],CHECKOUT) == ''
        after_tag = command('tag-after',['git','ls-remote',ORIGIN,'refs/tags/'+TAG,'refs/tags/'+TAG+'^{}'])
        assert before_tag == after_tag, 'Remote tag changed during restoration'
        release_after = json.loads(command('release-after',['gh','api','repos/'+REPO+'/releases/tags/'+TAG]))
        assert release_after['id'] == release['id'] and release_after['tag_name'] == TAG and not release_after['draft']
        after_assets = {a['name']:a for a in release_after['assets']}
        for name in names:
            for key in ['id','size','digest','updated_at']:
                assert assets_by_name[name].get(key) == after_assets[name].get(key), 'Release asset drift'
        RECEIPT['original_tree_metadata_after'] = original_tree_metadata()
        assert RECEIPT['original_tree_metadata_after'] == RECEIPT['original_tree_metadata_before']
        RECEIPT['original_tree_metadata_unchanged'] = True
        compact = RECOVERY/'compact-evidence'
        compact.mkdir()
        casefolder = CHECKOUT/'build/fair-driver-v1/recovery-dc-r1/cases/DC-TT-B-L0-recovery'
        for file in casefolder.iterdir():
            assert file.is_file() and file.stat().st_size < 1024**2
            shutil.copy2(file,compact/file.name)
        shutil.copy2(RECOVERY/'smoke-check.json',compact/'smoke-check.json')
        RECEIPT['compact_evidence'] = [record_file(p) for p in sorted(compact.iterdir())]
        RECEIPT.update(status='passed',reproduction_passed=True,completed_utc=now(),free_bytes_after=guard(),
                       originals_content_hash_recomputed=False,
                       original_preservation_check='No original writes by helper; original file path/size/mtime/mode unchanged. This is not a second content hash of all original waveforms.',
                       final_boundary='Public GitHub fresh checkout plus inputs/results download and SHA-verified restore; same-machine one TT B L0 DC reproduction only. No full-waveform download, NRZ/full-matrix/EDA rerun, new-machine or new-OS claim.')
        save()
        print(json.dumps({'status':RECEIPT['status'],'restored':len(restored),
                          'current_difference_A':RECEIPT['DC_smoke']['current_difference_A'],
                          'check':str(RECOVERY/'check.json'),'sha256':sha(RECOVERY/'check.json')},indent=2))
        return 0
    except Exception:
        RECEIPT.update(status='failed',reproduction_passed=False,failed_utc=now(),error=traceback.format_exc())
        save()
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    if sys.argv[1:] == ['--smoke']:
        smoke()
    elif sys.argv[1:]:
        raise SystemExit('Use no arguments for a fresh run; --smoke is the recorded child invocation only')
    else:
        raise SystemExit(main())
