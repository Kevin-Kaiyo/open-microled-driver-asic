"""Retain compact views in evidence; preserve complete files under build."""
from pathlib import Path
import datetime,hashlib,json,shutil
import numpy as np
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'evidence/analog-v3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 target=ROOT/'build/analog-v3/evidence-dense-backup';rows=[]
 for p in E.rglob('*.csv'):
  if p.name in ['dc.csv','pvt.csv'] or p.parent.name.startswith('ac-') or p.stat().st_size<1024*1024:continue
  a=np.loadtxt(p,delimiter=',',skiprows=1)
  if len(a)<=600:continue
  keep=set(np.linspace(0,len(a)-1,400,dtype=int))
  for col in range(1,a.shape[1]):keep.add(int(np.argmin(a[:,col])));keep.add(int(np.argmax(a[:,col])))
  for low,high in [(0,1e-9),(0,1e-6),(19.9e-6,22.6e-6),(50e-6,55e-6),(514.4e-6,518e-6)]:
   ii=np.flatnonzero((a[:,0]>=low)&(a[:,0]<=high))
   if len(ii):
    for col in range(1,min(a.shape[1],15)):
     keep.add(int(ii[np.argmin(a[ii,col])]))
     keep.add(int(ii[np.argmax(a[ii,col])]))
  dst=target/p.relative_to(E);dst.parent.mkdir(parents=True,exist_ok=True)
  if dst.exists():
   if sha(dst)!=sha(p):raise RuntimeError('Dense archive already exists with different bytes: '+str(p))
  else:shutil.copyfile(p,dst)
  header=p.open().readline().strip();np.savetxt(p,a[sorted(keep)],delimiter=',',header=header,comments='');rows.append(dict(path=str(p.relative_to(ROOT)),rows_before=len(a),rows_after=len(keep),dense_backup=str(dst.relative_to(ROOT)),dense_sha256=sha(dst),compact_sha256=sha(p)))
 manifest=E/'compact-views.json';old=json.loads(manifest.read_text()) if manifest.exists() else {'schema_version':1,'note':'Visualization-only decimation, retain extrema plus400 even-index samples. All qualification metrics independently use full raw build waveform.dat. Dense previous evidence bytes preserved in build/analog-v3/evidence-dense-backup.','files':[]};old['files'].extend(rows);manifest.write_text(json.dumps(old,indent=2)+'\n');print(json.dumps({'compacted_files':len(rows)}))
if __name__=='__main__':main()
