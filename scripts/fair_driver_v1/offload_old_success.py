#!/usr/bin/env python3
"""Offload only already-backed historical successful waveforms, never live/failure inputs."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,urllib.request
import run as e
TAG='driver-robustness-20261024';REPO='Kevin-Kaiyo/open-microled-driver-asic'

def main():
 root=e.ROOT;plan=json.loads((e.BUILD/'old-success-waveform-offload-plan.json').read_text());manifest=json.loads((root/f'evidence/backups/{TAG}.json').read_text());prior=json.loads((root/f'evidence/backups/{TAG}-remote.json').read_text())
 assert prior['all_expected_assets_verified'] and prior['manifest_sha256']==e.sha(root/f'evidence/backups/{TAG}.json')
 gh=lambda *a:json.loads(subprocess.check_output(['gh',*a],cwd=root,text=True))
 repo=gh('repo','view',REPO,'--json','nameWithOwner,isPrivate');assert repo=={'isPrivate':False,'nameWithOwner':REPO} or repo=={'nameWithOwner':REPO,'isPrivate':False}
 ref=gh('api',f'repos/{REPO}/git/ref/tags/{TAG}')['object'];assert ref['type']=='commit' and ref['sha']==prior['source_commit']
 remote=gh('api',f'repos/{REPO}/releases/tags/{TAG}');assets={a['name']:a for a in remote['assets']};previous={a['name']:a for a in prior['files']};bound={a['name']:a for a in manifest['assets']};selected={x['asset']['name'] for x in plan['files']}
 for name in selected:
  a,b,p=assets[name],bound[name],previous[name]
  assert a['state']=='uploaded' and a['id']==p['remote_asset_id'] and a['size']==b['size']==p['size'] and a['digest']=='sha256:'+b['sha256'] and p['sha256']==b['sha256'] and p['download_readback_verified']
 for x in plan['files']:
  f=x['file'];p=root/f['path'];assert str(p.relative_to(root)).startswith('build/highspeed-nrz-robustness/') and p.name=='waveform.dat.gz' and not p.is_symlink() and p.is_file()
  assert p.stat().st_size==f['size'] and e.sha(p)==f['sha256'];analysis=json.loads(p.with_name('analysis.json').read_text());assert analysis['row']['combined_screen_passed'] is True
 # One additional fresh full stream verifies availability; all selected assets are
 # bound to the prior complete readback by unchanged current id/size/server digest.
 name=sorted(selected)[0];a=assets[name];h=hashlib.sha256();count=0
 with urllib.request.urlopen(urllib.request.Request(a['browser_download_url'],headers={'User-Agent':'MicroLEDArchiveReadback/1.0'}),timeout=60) as stream:
  for block in iter(lambda:stream.read(4*2**20),b''):h.update(block);count+=len(block)
 assert h.hexdigest()==bound[name]['sha256'] and count==bound[name]['size']
 out=root/'evidence/backups/fair-driver-20261025-old-waveforms-offload.json';assert not out.exists()
 receipt={'created':datetime.datetime.now().astimezone().isoformat(),'scope':plan['scope'],'repository':REPO,'release':TAG,'remote_source_commit':ref['sha'],'historical_complete_readback_receipt_sha256':e.sha(root/f'evidence/backups/{TAG}-remote.json'),'current_selected_asset_checks':[{k:assets[n][k] for k in ['id','name','size','digest','state']} for n in sorted(selected)],'additional_fresh_full_stream':{'name':name,'size':count,'sha256':h.hexdigest()},'expected_bytes':plan['total_bytes'],'files':[],'completed':False}
 e.emit(out,receipt)
 for x in plan['files']:
  f=x['file'];p=root/f['path'];assert e.sha(p)==f['sha256']
  pointer={'state':'raw waveform offloaded; metadata and all failure evidence retained locally','release_url':remote['html_url'],'archive':x['asset'],'file':f,'restore':'Download this named archive from the release, verify its SHA256, then restore this exact repository-relative member. scripts/backup/release_bundle.py can restore the corresponding manifest group without overwriting other files.'}
  marker=p.with_name('REMOTE-WAVEFORM.json');assert not marker.exists();e.emit(marker,pointer);p.unlink();receipt['files'].append(pointer);e.emit(out,receipt)
 receipt.update(completed=True,released_bytes=sum(x['file']['size'] for x in receipt['files']));e.emit(out,receipt);print(json.dumps({'files':len(receipt['files']),'released_GiB':receipt['released_bytes']/2**30,'receipt':str(out)},indent=2))
if __name__=='__main__':main()
