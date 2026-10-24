#!/usr/bin/env python3
"""Delete only this run's verified tar duplicates, after readback and recovery."""
import argparse, datetime, shutil
import backup_common as c

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--after-files-restored',action='store_true',help='Explicitly allow removal after verified file restoration while DC remains pending due to storage guard');a=ap.parse_args()
 index=c.expected_uploads();remote=c.read(c.path('-remote.json'))
 if a.after_files_restored:
  import recover
  recovery=recover.verify_restored()
 else:recovery=c.read(c.ROOT/'build/github-recovery-reference-v2-20261024/recovery.json')
 assert remote['all_expected_assets_verified'] and recovery['passed']
 assert remote['source_commit']==recovery['source_commit']==index['source_commit']
 assert remote['manifest_sha256']==recovery['manifest_sha256']==c.digest(c.path('.json'))
 inv=c.read(c.path('-inventory.json'));scope=c.read(c.path('-scope.json'))
 assert c.check_inventory(inv['files'])==scope['exclusions']
 release=c.remote_release(index['source_commit']);current={x['name']:x for x in release['assets']};proof={x['name']:x for x in remote['files']}
 assert set(proof)=={x['name'] for x in index['files']}
 for expected in index['files']:
  r=current[expected['name']];v=proof[expected['name']]
  assert v['download_readback_verified'] and r['id']==v['remote_asset_id'] and r['state']=='uploaded'
  assert r['size']==v['size']==expected['size'] and v['sha256']==expected['sha256']
  assert not r.get('digest') or r['digest']=='sha256:'+expected['sha256']
 manifest=c.read(c.path('.json'));folder=c.STAGE/'assets';plans=[]
 assert not folder.is_symlink() and folder.is_dir()
 assert {p.name for p in folder.iterdir()}=={x['name'] for x in manifest['assets']}
 for item in manifest['assets']:
  p=folder/item['name'];r=current[item['name']];v=proof[item['name']]
  assert not p.is_symlink() and p.is_file() and p.resolve().parent==folder.resolve()
  assert r['id']==v['remote_asset_id'] and r['state']=='uploaded'
  assert r['size']==v['size']==item['size']==p.stat().st_size
  assert v['sha256']==item['sha256']==c.digest(p)
  assert not r.get('digest') or r['digest']=='sha256:'+item['sha256']
  plans.append({'path':str(p.relative_to(c.ROOT)),'bytes':item['size'],'sha256':item['sha256'],'remote_asset_id':r['id']})
 receipt={'source_commit':index['source_commit'],'source_inventory_rechecked':True,'remote_readback_passed':True,'file_restoration_passed':True,'dc_recovery_passed_at_cleanup':not a.after_files_restored,'recovery_stage':'files_restored_DC_pending' if a.after_files_restored else 'DC_completed','recovery_receipt_sha256':c.digest(c.ROOT/('build/github-recovery-reference-v2-20261024/files-restored.json' if a.after_files_restored else 'build/github-recovery-reference-v2-20261024/recovery.json')),'scope':'Only 22 staging tar.gz copies; original active inputs, waveforms, failures, PDK and recovery checkout retained.','files':plans,'logical_bytes':sum(x['bytes'] for x in plans),'free_bytes_before':shutil.disk_usage(c.ROOT).free,'executed':False}
 c.write(c.STAGE/'cleanup-preview.json',receipt)
 if a.execute:
  for item in plans:(c.ROOT/item['path']).unlink()
  folder.rmdir()
  receipt.update(executed=True,completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),free_bytes_after=shutil.disk_usage(c.ROOT).free,original_sources_removed=False)
  c.write(c.path('-cleanup.json'),receipt)
 print(('REMOVED' if a.execute else 'PREVIEW')+f": {len(plans)} staging archives, {receipt['logical_bytes']} logical bytes")
if __name__=='__main__':main()
