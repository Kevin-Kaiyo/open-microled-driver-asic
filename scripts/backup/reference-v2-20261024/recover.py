#!/usr/bin/env python3
"""Restore small Release groups, or resume after the documented disk guard."""
from pathlib import Path
import argparse, datetime, json, os, re, subprocess, sys
import backup_common as c
REC=c.ROOT/'build/github-recovery-reference-v2-20261024'
CHECKOUT=REC/'repository'
DOWNLOAD=REC/'downloads'
LOGS=REC/'check-evidence'
GROUPS=['nrz-inputs','nrz-metadata','pwm-inputs','pwm-metadata','physical-evidence','report-support']

def metadata():
 index=c.read(c.STAGE/'upload-index.json');manifest=c.read(c.path('.json'))
 assert index['source_commit']==c.read(c.path('-scope.json'))['source_commit']
 assert index['tag']==c.TAG and index['repository']==c.REPO
 selected=[x for x in manifest['assets'] if x['group'] in GROUPS]
 return index,manifest,selected

def verify_restored():
 index,manifest,selected=metadata();checks=c.read(REC/'command-progress.json')['commands']
 byname={x['name']:x for x in checks}
 for name in ('download','restore','restore-links'):
  record=byname[name];assert record['exit_code']==0
  assert c.digest(LOGS/(name+'.log'))==record['log_sha256']
 source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=CHECKOUT,text=True).strip();assert source==index['source_commit']
 tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=CHECKOUT,text=True).strip()
 expected_tree=subprocess.check_output(['git','rev-parse',source+'^{tree}'],cwd=c.ROOT,text=True).strip();assert tree==expected_tree
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=CHECKOUT,text=True).strip()
 names=[c.TAG+'.json',c.TAG+'-scope.json','restore_symlinks.py','backup_common.py']+[x['name'] for x in selected]
 expected={x['name']:x for x in index['files']};downloads=[]
 for name in names:
  p=DOWNLOAD/name;assert not p.is_symlink() and p.is_file()
  assert p.stat().st_size==expected[name]['size'] and c.digest(p)==expected[name]['sha256']
  downloads.append({'name':name,'size':p.stat().st_size,'sha256':c.digest(p),'passed':True})
 assert c.digest(DOWNLOAD/(c.TAG+'.json'))==c.digest(c.path('.json'))
 count=0
 for asset in selected:
  for item in asset['files']:
   relative=c.safe_relative(item['path']);p=CHECKOUT/relative
   assert all(not x.is_symlink() for x in [p]+list(p.parents) if x.is_relative_to(CHECKOUT))
   assert p.is_file() and p.stat().st_size==item['size'] and c.digest(p)==item['sha256'],item['path']
   count+=1
 linkcount=0
 for item in c.read(c.path('-scope.json'))['exclusions']:
  if item.get('target_contents_selected'):
   p=CHECKOUT/c.safe_relative(item['path']);target=CHECKOUT/c.safe_relative(item['target_repository_relative'])
   assert p.is_symlink() and not os.path.isabs(os.readlink(p)) and p.resolve()==target.resolve() and target.exists()
   linkcount+=1
 match=re.search(r'RESTORED (\d+) files; SKIPPED (\d+) identical files',(LOGS/'restore.log').read_text());assert match
 restored,skipped=map(int,match.groups());assert restored+skipped==count
 receipt={'passed':True,'scope':'File restore only; DC reproduction pending, including preserved storage-guard failure.','source_commit':source,'tree':tree,'manifest_sha256':c.digest(c.path('.json')),'upload_index_sha256':c.digest(c.STAGE/'upload-index.json'),'selected_archives':len(selected),'planned_regular_files':count,'restored_regular_files':restored,'skipped_identical_files':skipped,'current_restored_file_hashes_verified':count,'internal_relative_links_verified':linkcount,'download_hash_checks':downloads,'commands_verified':[byname[x] for x in ('download','restore','restore-links')]}
 c.write(REC/'files-restored.json',receipt)
 return receipt

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--resume',action='store_true');ap.add_argument('--verify-restored',action='store_true');a=ap.parse_args()
 if a.verify_restored:
  r=verify_restored();print(json.dumps({k:r[k] for k in ('passed','current_restored_file_hashes_verified','internal_relative_links_verified')}));return
 index,manifest,selected=metadata();LOGS.mkdir(parents=True,exist_ok=True);DOWNLOAD.mkdir(exist_ok=True)
 checks=c.read(REC/'command-progress.json')['commands'] if a.resume else []
 def run(label,command,cwd=CHECKOUT):
  log=LOGS/(label+'.log');assert not log.exists(),'Preserve previous command logs: '+str(log)
  p=subprocess.run([str(x) for x in command],cwd=cwd,text=True,capture_output=True)
  log.write_text(p.stdout+p.stderr)
  checks.append({'name':label,'command':[str(x) for x in command],'cwd':str(cwd.relative_to(c.ROOT)),'exit_code':p.returncode,'log_sha256':c.digest(log)})
  c.write(REC/'command-progress.json',{'commands':checks});print(label+': '+str(p.returncode),flush=True)
  if p.returncode:raise RuntimeError(label+' failed; inspect '+str(log))
  return p.stdout
 if not a.resume:
  c.expected_uploads()
  names=[c.TAG+'.json',c.TAG+'-scope.json','restore_symlinks.py','backup_common.py']+[x['name'] for x in selected]
  command=['gh','release','download',c.TAG,'--repo',c.REPO,'--dir',str(DOWNLOAD)]
  for name in names:command+=['--pattern',name]
  run('download',command,c.ROOT)
  expected={x['name']:x for x in index['files']}
  for name in names:
   p=DOWNLOAD/name;assert p.stat().st_size==expected[name]['size'] and c.digest(p)==expected[name]['sha256']
  command=[sys.executable,'-B','scripts/backup/release_bundle.py','restore','--manifest',DOWNLOAD/(c.TAG+'.json'),'--asset-dir',DOWNLOAD,'--root',CHECKOUT]
  for group in GROUPS:command+=['--group',group]
  run('restore',command)
  run('restore-links',[sys.executable,'-B',DOWNLOAD/'restore_symlinks.py','--root',CHECKOUT,'--scope',DOWNLOAD/(c.TAG+'-scope.json'),'--execute'])
 files=verify_restored()
 suffix='-retry1' if a.resume else ''
 nrzout='build/nrz-reference-v2/github-recovery-smoke-dc'+suffix
 run('nrz-dc'+suffix,[sys.executable,'-B','scripts/nrz_reference_v2/reproduce.py','--source-work','build/nrz-reference-v2/selected-final-r2','--out',nrzout,'--smoke-dc'])
 run('pwm-dc',[sys.executable,'-B','scripts/pwm_reference_v2/reproduce.py','--source','build/pwm-reference-v2/20261024','--case','c15_dc','--destination','build/pwm-reference-v2/github-recovery-c15-dc'])
 for label,folder in [('physical-joint','nrz-switched-keeper-joint-r1'),('physical-module','vi-switched-keeper-pg-r1b')]:
  run(label,[sys.executable,'-B','scripts/reference_v2_layout/validate.py','--run','build/reference-v2-layout/'+folder,'--out',LOGS/(label+'.json')])
 nrz=c.read(CHECKOUT/nrzout/'reproduction-check.json');pwm=c.read(CHECKOUT/'build/pwm-reference-v2/github-recovery-c15-dc/reproduction.json')
 assert nrz['reproduction_passed'] and abs(nrz['current_difference_A'])<1e-12
 assert abs(pwm['current_delta_from_original_a'])<1e-12 and pwm['rtl_recompiled']
 receipt={**files,'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'restored_groups':GROUPS,'commands':checks,'nrz_reproduction':nrz,'pwm_reproduction':pwm,'scope':'GitHub fresh shallow checkout on same macOS host using existing Python/ngspice/Icarus. Downloaded six small groups; no full waveform restore, no new EDA run, no other-OS qualification. Physical validators read existing reports and geometry.','prior_failure':'Initial NRZ run stopped before simulation by minimum 5 GiB free-space guard; failed run and logs preserved. Verified staging archives removed after full remote readback and file restoration; original data retained; no solver guard bypass.' if a.resume else None}
 c.write(REC/'recovery.json',receipt)
 print(json.dumps({'passed':True,'files':receipt['restored_regular_files'],'nrz_delta_A':nrz['current_difference_A'],'pwm_delta_A':pwm['current_delta_from_original_a']},indent=2))
if __name__=='__main__':main()
