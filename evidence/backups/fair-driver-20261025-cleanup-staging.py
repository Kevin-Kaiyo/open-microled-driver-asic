#!/usr/bin/env python3
"""Remove only reproducible staging tar copies after remote readback AND DC restore."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path.cwd().resolve();STAGE=ROOT/'build/github-sync-fair-driver-20261025'
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(4*2**20),b''):h.update(b)
 return h.hexdigest()
def write(p,d):
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
def main():
 remote=json.loads((STAGE/'fair-driver-20261025-remote.json').read_text());recovery=json.loads((STAGE/'recovery/check.json').read_text());manifest=json.loads((STAGE/'fair-driver-20261025.json').read_text());inventory=json.loads((STAGE/'fair-driver-20261025-inventory.json').read_text());assert remote['all_expected_assets_verified'] and recovery['reproduction_passed'] and recovery['source_commit']==remote['source_commit'];assert remote['manifest_sha256']==recovery['trusted_manifest_sha256']==sha(STAGE/'fair-driver-20261025.json')
 assert all(x['exit_code']==0 for x in recovery['commands']) and abs(recovery['DC_smoke']['current_difference_A'])<=1e-12 and all(abs(x)<=1e-10 for x in recovery['DC_smoke']['port_power_differences_W'].values())
 current=json.loads(subprocess.check_output(['gh','api','repos/Kevin-Kaiyo/open-microled-driver-asic/releases/tags/fair-driver-20261025'],text=True));assets={x['name']:x for x in current['assets']};verified={x['name']:x for x in remote['files']}
 planned=[]
 for a in manifest['assets']:
  p=STAGE/'assets'/a['name'];v=verified[a['name']];c=assets[a['name']];assert p.parent.resolve()==(STAGE/'assets').resolve() and not p.is_symlink() and p.is_file() and p.name.endswith('.tar.gz')
  assert p.stat().st_size==a['size']==v['size']==c['size'] and sha(p)==a['sha256']==v['sha256'];assert v['download_readback_verified'] and c['id']==v['remote_asset_id'] and c['updated_at']==v['remote_updated_at'] and c['digest']=='sha256:'+a['sha256'];planned.append({'path':str(p.relative_to(ROOT)),'size':a['size'],'sha256':a['sha256'],'remote_asset_id':c['id']})
 # This full fresh content check concerns the original scope; none is deleted.
 for relative,item in inventory['files'].items():
  p=ROOT/relative;assert p.is_file() and not p.is_symlink() and p.stat().st_size==item['size'] and sha(p)==item['sha256'],'Original drift: '+relative
 out=STAGE/'fair-driver-20261025-staging-cleanup.json';assert not out.exists();receipt={'created':datetime.datetime.now().astimezone().isoformat(),'scope':'Seven local staging tar copies only. All1413 original files and current failure/input/raw evidence retained and freshly SHA-checked. Fresh-checkout recovery retained.','source_commit':remote['source_commit'],'remote_receipt_sha256':sha(STAGE/'fair-driver-20261025-remote.json'),'recovery_receipt_sha256':sha(STAGE/'recovery/check.json'),'original_scope_files_freshly_content_verified':len(inventory['files']),'original_scope_bytes_verified':inventory['total_bytes'],'planned':planned,'removed':[],'completed':False,'restore_staging':'Archives remain in the named GitHub release with these exact digests. Re-download and verify them before reusing a helper that requires local assets.'};write(out,receipt)
 for item in planned:
  p=ROOT/item['path'];assert sha(p)==item['sha256'];p.unlink();receipt['removed'].append(item);write(out,receipt)
 receipt['completed']=True;receipt['released_bytes']=sum(x['size'] for x in receipt['removed']);write(out,receipt);print(json.dumps({'completed':True,'staging_archives_removed':len(planned),'released_bytes':receipt['released_bytes'],'original_scope_content_hashes_verified':len(inventory['files'])},indent=2))
if __name__=='__main__':main()
