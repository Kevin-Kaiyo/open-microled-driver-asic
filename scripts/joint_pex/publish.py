"""Package frozen exports; existing artifact bytes must match exactly."""
from pathlib import Path
import argparse,gzip,json,shutil
from collections import defaultdict
import numpy as np
from export import ROOT,sha,number,DSU

def write_frozen(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():assert path.read_bytes()==data,('Frozen artifact differs',path)
 else:path.write_bytes(data)

def metrics(model):
 rs=[];cs=[];d=DSU()
 for line in model.read_text().splitlines():
  if line.startswith('R'):
   t=line.split();rs.append(t);d.join(t[1],t[2])
  elif line.startswith('C'):cs.append(line.split())
 roots={d.find('PWM_DRIVE'),d.find('PWM')};assert len(roots)==1
 nodes=sorted({n for t in rs if d.find(t[1])in roots for n in t[1:3]});index={n:i for i,n in enumerate(nodes)};L=np.zeros((len(nodes),len(nodes)))
 for t in rs:
  if t[1]not in index:continue
  i,j=index[t[1]],index[t[2]];g=1/float(number(t[3]));L[i,i]+=g;L[j,j]+=g;L[i,j]-=g;L[j,i]-=g
 b=np.zeros(len(nodes));b[index['PWM_DRIVE']]=1;b[index['PWM']]=-1;ground=index['PWM'];keep=[i for i in range(len(nodes))if i!=ground];v=np.linalg.solve(L[np.ix_(keep,keep)],b[keep]);volts=dict(zip([nodes[i]for i in keep],v))
 return dict(output_drive_to_actual_analog_entry_effective_R_ohm=float(volts['PWM_DRIVE']),total_exported_explicit_C_f=float(sum(number(t[3])for t in cs)),output_component_incident_C_f=float(sum(number(t[3])for t in cs if t[1]in index or t[2]in index)),signal_R_min_ohm=float(min(number(t[3])for t in rs)),signal_R_max_ohm=float(max(number(t[3])for t in rs)))

def main():
 p=argparse.ArgumentParser();p.add_argument('--export',action='append',required=True,help='style=repo-relative export directory');p.add_argument('--output',default='evidence/joint-pex');a=p.parse_args();base=(ROOT/a.output).resolve();entries={}
 assert base==ROOT/'evidence/joint-pex' or base.is_relative_to(ROOT/'build/joint-pex'), 'Private reproductions must use build/joint-pex'
 for arg in a.export:
  style,path=arg.split('=',1);src=ROOT/path;s=json.loads((src/'summary.json').read_text());assert s['passed']and s['rc_style']==style
  for n,h in s['outputs_sha256'].items():assert sha(src/n)==h
  dest=base/style;dest.mkdir(parents=True,exist_ok=True)
  write_frozen(dest/'output_pixel_pex.spice',(src/'output_pixel_pex.spice').read_bytes())
  write_frozen(dest/'projection-ledger.json.gz',gzip.compress((src/'projection-ledger.json').read_bytes(),mtime=0))
  s['as_run_outputs_sha256']=s.pop('outputs_sha256');s['as_run_output_directory']=path;s['as_run_summary_sha256']=sha(src/'summary.json');s['public_artifacts_sha256']={f.name:sha(f)for f in dest.iterdir()if f.name in ['output_pixel_pex.spice','projection-ledger.json.gz']};s['ledger_compression']='gzip; decompressed SHA must equal as_run_outputs_sha256[projection-ledger.json]';s['metrics']=metrics(dest/'output_pixel_pex.spice')
  write_frozen(dest/'summary.json',(json.dumps(s,indent=2)+'\n').encode());entries[style]=dict(summary=f'{style}/summary.json',summary_sha256=sha(dest/'summary.json'),model=f'{style}/output_pixel_pex.spice',model_sha256=sha(dest/'output_pixel_pex.spice'),counts=s['counts'],metrics=s['metrics'],passed=True)
 summary=base/'summary.json';old=json.loads(summary.read_text())if summary.exists()else dict(passed=True,scope='Post-extraction 12-MOS joint signal cutout; ideal PG and explicit neighbor boundary, no full-chip transient/IR/EM signoff.',styles={})
 old['styles'].update(entries);sources=[*sorted((ROOT/'scripts/joint_pex').glob('*.py')),ROOT/'docs/specifications/joint-pex-v0.4.md']
 for f in [ROOT/'docs/research/joint-pex.md',ROOT/'evidence/joint-pex/README.md']:
  if f.exists():sources.append(f)
 old['packaging_source_sha256']={str(f.relative_to(ROOT)):sha(f)for f in sources};summary.write_text(json.dumps(old,indent=2)+'\n');print(json.dumps(entries,indent=2))
if __name__=='__main__':main()
