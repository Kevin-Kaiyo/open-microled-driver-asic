#!/usr/bin/env python3
"""External receipt driver: download Release assets and validate a fresh checkout."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, importlib.util, json, os, subprocess, sys, time

OUT = Path(__file__).resolve().parent
ROOT = OUT / 'repository'
DOWNLOAD = OUT / 'downloads'
CHECK = ROOT / 'build/recovery-checks'
TAG = 'driver-robustness-20261024'
REPO = 'Kevin-Kaiyo/open-microled-driver-asic'
COMMIT = '9d84753bae099e497a813f9097b1ce6eeb2f2df7'
EXPECTED_MANIFEST_SHA = 'df54d23d95ea79cff403dc8a2ee1547c7ac872ef267784b7f7ce247d3e9065fe'
PYTHON = str(OUT.parent.parent / 'build/layout/venv/bin/python')
GROUPS = ['nrz-inputs', 'nrz-metadata', 'pwm-inputs', 'pwm-metadata', 'physical-evidence', 'report-support']
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
receipt = {'started_at': datetime.now(timezone.utc).isoformat(), 'repository': REPO,
           'release_tag': TAG, 'expected_source_commit': COMMIT, 'commands': []}

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def save():
    (OUT / 'recovery.json').write_text(json.dumps(receipt, indent=2) + '\n')

def command(label, args, cwd=ROOT):
    log = OUT / (label + '.log')
    start = time.monotonic()
    with log.open('x') as f:
        result = subprocess.run([str(a) for a in args], cwd=cwd, env=ENV,
                                stdout=f, stderr=subprocess.STDOUT)
    receipt['commands'].append({'label': label, 'command': [str(a) for a in args],
        'cwd': str(cwd), 'exit_code': result.returncode, 'elapsed_s': time.monotonic()-start,
        'log': str(log.relative_to(OUT)), 'log_sha256': sha(log)})
    save()
    if result.returncode: raise RuntimeError(f'{label} failed: {log}')
    print(label + ': passed', flush=True)
    return log.read_text()

def main():
    assert not (OUT/'recovery.json').exists(), 'Use a new receipt directory; do not overwrite recovery'
    assert not CHECK.exists(), 'Recovery output directory must be new'
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    assert actual == COMMIT
    receipt['source_commit'] = actual
    receipt['actual_script_sha256'] = {p:sha(ROOT/p) for p in [
        'scripts/backup/release_bundle.py','scripts/highspeed_nrz_robustness/reproduce.py',
        'scripts/highspeed_nrz_robustness/run.py','scripts/highspeed_nrz_robustness/validate.py',
        'scripts/pwm_robustness/reproduce.py','scripts/pwm_robustness/run.py',
        'scripts/highspeed_nrz_robustness_layout/validate.py']}
    receipt['receipt_driver_sha256'] = sha(__file__)
    receipt['checkout_log_sha256'] = sha(OUT/'checkout-log.json')
    before = subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True)
    assert not before
    receipt['tracked_status_before'] = before
    receipt['historical_builds_absent_before_restore'] = {
        x: not (ROOT/x).exists() for x in ['build/analog-v3', 'build/layout-v3', 'build/highspeed-nrz-pvt', 'build/highspeed-nrz-pvt-layout']}
    assert all(receipt['historical_builds_absent_before_restore'].values())
    DOWNLOAD.mkdir(exist_ok=True)
    metadata = json.loads(command('release-metadata', ['gh','api',f'repos/{REPO}/releases/tags/{TAG}']))
    (OUT/'release-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    receipt['release_url'] = metadata['html_url']
    receipt['release_metadata_sha256'] = sha(OUT/'release-metadata.json')
    receipt['release_id'] = metadata['id']
    assets = {a['name']:a for a in metadata['assets']}
    manifest_name = TAG+'.json'
    assert manifest_name in assets, 'Release manifest not uploaded yet'
    command('download-manifest', ['gh','release','download',TAG,'--repo',REPO,'--pattern',manifest_name,'--dir',DOWNLOAD])
    manifest = DOWNLOAD/manifest_name
    assert sha(manifest)==EXPECTED_MANIFEST_SHA, 'Manifest differs from publishing agent verified SHA'
    receipt['manifest'] = {'name':manifest_name,'sha256':sha(manifest),'bytes':manifest.stat().st_size,
                           'url':assets[manifest_name]['browser_download_url'], 'asset_id':assets[manifest_name]['id'],
                           'github_digest':assets[manifest_name].get('digest')}
    digest = assets[manifest_name].get('digest')
    if digest: assert digest == 'sha256:'+sha(manifest)
    data = json.loads(manifest.read_text())
    selected = [a for a in data['assets'] if a['group'] in GROUPS]
    assert set(a['group'] for a in selected) == set(GROUPS)
    assert not any('waveform' in a['group'] for a in selected)
    receipt['downloads'] = []
    for item in selected:
        name=item['name']; assert name in assets, 'Required asset not uploaded: '+name
        command('download-'+item['group'],['gh','release','download',TAG,'--repo',REPO,'--pattern',name,'--dir',DOWNLOAD])
        path=DOWNLOAD/name; actual_sha=sha(path)
        assert actual_sha==item['sha256'] and path.stat().st_size==item['size']
        digest=assets[name].get('digest')
        if digest: assert digest=='sha256:'+actual_sha
        receipt['downloads'].append({'name':name,'group':item['group'],'bytes':path.stat().st_size,
            'expected_sha256':item['sha256'],'downloaded_sha256':actual_sha,'asset_id':assets[name]['id'],
            'github_digest':digest,'url':assets[name]['browser_download_url'],'members':len(item['files'])})
        save()
    group_args=[v for group in GROUPS for v in ['--group',group]]
    command('verify-archives',[PYTHON,'scripts/backup/release_bundle.py','verify','--manifest',manifest,'--asset-dir',DOWNLOAD,*group_args])
    spec=importlib.util.spec_from_file_location('release_bundle',ROOT/'scripts/backup/release_bundle.py')
    bundle=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundle)
    restored=bundle.restore(manifest,DOWNLOAD,ROOT,GROUPS)
    (OUT/'restore-files.json').write_text(json.dumps(restored,indent=2)+'\n')
    receipt['restore']={'method':'repository scripts/backup/release_bundle.py restore(manifest, downloads, fresh_checkout, groups)',
        'exit_code':0,
        'restored_count':len(restored['restored']),'skipped_identical_count':len(restored['skipped_identical']),
        'total_member_count':sum(len(a['files']) for a in selected),'files_receipt_sha256':sha(OUT/'restore-files.json'),
        'all_members_hash_verified':True,'different_existing_file_overwrite_allowed':False}
    assert len(restored['restored'])+len(restored['skipped_identical'])==sum(len(a['files']) for a in selected)
    CHECK.mkdir(parents=True)
    receipt['historical_waveforms_downloaded']=False
    assert not list(ROOT.rglob('waveform.dat.gz')), 'Unexpected restored NRZ waveform'
    save()
    wrapper="import sys,runpy;from pathlib import Path;sys.path.insert(0,'scripts/highspeed_nrz_robustness');import run;run.EVIDENCE=Path('build/recovery-checks/nrz-generated-evidence').resolve();runpy.run_path('scripts/highspeed_nrz_robustness/reproduce.py',run_name='__main__')"
    command('nrz-smoke-dc',[PYTHON,'-c',wrapper,'--source-work','build/highspeed-nrz-robustness/selected-a8-b58-r4','--work','build/recovery-checks/nrz-github-smoke','--smoke-dc'])
    command('pwm-dc-board100n',[PYTHON,'scripts/pwm_robustness/reproduce.py','--work','build/recovery-checks/pwm-github-smoke'])
    for name in ['hv-A8-r3','hv-r2']:
        command('physical-'+name,[PYTHON,'scripts/highspeed_nrz_robustness_layout/validate.py','--run','build/highspeed-nrz-robustness-layout/'+name,'--out','build/recovery-checks/physical-'+name+'.json'])
    nrz=json.loads((CHECK/'nrz-github-smoke/reproduction-check.json').read_text())
    old=json.loads((ROOT/'evidence/highspeed-nrz-robustness/selected-a8-b58-r4-summary.json').read_text())
    ref=next(x for x in old['rows'] if x['route']=='A' and x.get('dc_bit')==1 and x['vdd_V']==3.65 and x['kind']=='FFplus50_DC')
    new=nrz['smoke_row']; delta=new['LED_current_A']-ref['LED_current_A']
    assert abs(delta)<=1e-12 and new['analysis_ok'] and new['device_specific_screen_passed']
    pwm=json.loads((CHECK/'pwm-github-smoke/reproduction-summary.json').read_text())
    assert pwm['reproduction_passed']
    phys={name:json.loads((CHECK/('physical-'+name+'.json')).read_text()) for name in ['hv-A8-r3','hv-r2']}
    assert all(v['passed'] for v in phys.values())
    after=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True)
    assert after==before
    receipt.update({'completed_at':datetime.now(timezone.utc).isoformat(),'passed':True,'tracked_status_after':after,
        'comparisons':{'nrz':{'reference_case':ref['name'],'reference_current_A':ref['LED_current_A'],
            'fresh_current_A':new['LED_current_A'],'current_difference_A':delta,'acceptance_abs_A':1e-12,
            'reference_max_terminal_V':ref['max_abs_terminal_V'],'fresh_max_terminal_V':new['max_abs_terminal_V'],
            'source_manifest_sha256':json.loads((CHECK/'nrz-github-smoke/manifest.json').read_text())['reproduction_identity']['source_manifest_sha256'], 'passed':True},
            'pwm':{'reference_current_A':pwm['result']['current_a']-pwm['current_difference_a'],
                'fresh_current_A':pwm['result']['current_a'],'current_difference_A':pwm['current_difference_a'],'passed':pwm['reproduction_passed']},
            'physical':{name:{'manifest_files':v['manifest_files'],'routes':list(v['routes']),'passed':v['passed']} for name,v in phys.items()}},
        'runtime':{'python':PYTHON,'python_version':subprocess.check_output([PYTHON,'--version'],text=True).strip(),
            'ngspice':subprocess.check_output(['ngspice','--version'],text=True),
            'shared_runtime_only':True,'same_host_new_directory':True},
        'boundaries':['Downloaded exact Release assets over GitHub; archives and every tar member verified with frozen manifest SHA256.',
            'Restored only six named small groups; no archived waveform download, full matrix rerun, physical EDA rerun, upload, or deletion.',
            'NRZ and PWM each regenerated one DC testbench in a new recovery directory; NRZ generated summary redirected in-process to recovery-checks without source edits.',
            'Physical validator rehashed artifacts, parsed stored DRC/LVS reports and inspected actual GDS Dualgate/negative-control polygons. It did not rerun Magic/KLayout DRC/Netgen extraction.',
            'Uses original workspace Python virtualenv and host ngspice/iverilog binaries; this is same-host fresh-directory recovery, not a clean second-machine dependency installation.',
            'Original author inputs, evidence and source were not written; all receipt and generated outputs are under this external recovery tree.']})
    receipt['generated_check_files']=[{'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size}
        for p in sorted(CHECK.rglob('*')) if p.is_file() and not p.is_symlink()]
    save()
    print(json.dumps({'passed':True,'restore':receipt['restore'],'comparisons':receipt['comparisons']},indent=2),flush=True)

if __name__=='__main__':
    try: main()
    except Exception as exc:
        receipt['passed']=False;receipt['error']=type(exc).__name__+': '+str(exc);save();raise
