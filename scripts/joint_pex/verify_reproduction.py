"""Compare a fresh extraction to frozen PEX by actual rnode geometry, not IDs."""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,json,re,shlex
from export import ROOT,sha,number

def nodes(path):
 out={}
 for l in path.read_text().splitlines():
  if not l.startswith('rnode '):continue
  t=shlex.split(l);base=re.sub(r'\.[tn]\d+$','',t[1]);out[t[1]]=(base,int(t[4]),int(t[5]))
 return out
def graph(path,node_map):
 rows=[];ports=[];used=set()
 for l in path.read_text().splitlines():
  if l.startswith('.subckt '):ports=l.split()[2:]
  if not l or l[0]not in 'XRC':continue
  t=l.split();used.update(t[1:5]if l[0]=='X'else t[1:3]);n=lambda x:node_map.get(x,('port_or_unresisted',x))
  if l[0]in'RC':row=(l[0],tuple(sorted((n(t[1]),n(t[2])),key=str)),str(number(t[3])))
  else:row=('X',*[n(x)for x in t[1:5]],t[5],tuple(sorted((k,str(number(v)))for k,v in(z.split('=')for z in t[6:]))))
  rows.append(row)
 identities=[node_map[n]for n in used if n in node_map];assert len(identities)==len(set(identities)),'Physical-node mapping must be injective'
 return ports,Counter(rows)
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--model',required=True);p.add_argument('--baseline-run',default='flat-nominal-r3');a=p.parse_args();run=ROOT/'build/joint-pex'/a.run;baseline=ROOT/'build/joint-pex'/a.baseline_run;old=ROOT/'evidence/joint-pex/nominal/output_pixel_pex.spice';new=ROOT/a.model
 oldmap=nodes(baseline/'pixel_flat.res.ext');newmap=nodes(run/'pixel_flat.res.ext');op,og=graph(old,oldmap);np,ng=graph(new,newmap)
 raw=run/'pixel_flat_rc.spice';oldraw=baseline/'pixel_flat_rc.spice';negative={}
 text=new.read_text();controls={'port_swap':text.replace('.subckt output_pixel_pex I VDD VSS','.subckt output_pixel_pex VDD I VSS'), 'remove_cap':'\n'.join(l for l in text.splitlines()if not l.startswith('C0 '))+'\n','change_resistor':text.replace('22.126','22.127',1)}
 private=run/'reproduction-controls';private.mkdir(exist_ok=True)
 for name,t in controls.items():
  f=private/(name+'.spice');f.write_text(t);cp,cg=graph(f,newmap);negative[name]=dict(rejected=cp!=op or cg!=og,model_sha256=sha(f))
 result=dict(passed=op==np and og==ng and all(v['rejected']for v in negative.values()),raw_bytes_identical=raw.read_bytes()==oldraw.read_bytes(),model_bytes_identical=old.read_bytes()==new.read_bytes(),ordered_ports_identical=op==np,exact_geometric_multiset_identical=og==ng,method='Replace .res.ext rnode identifiers by exact (physical net base,x,y); compare ordered MOS terminals/properties and symmetric R/C endpoints/values/multiplicity, keeping all formal port names/order. No numeric tolerance and no clipping.',counts=dict(Counter(row[0]for row in og.elements())),negative_controls=negative,run=str(run.relative_to(ROOT)),model=str(new.relative_to(ROOT)),inputs_sha256={str(f.relative_to(ROOT)):sha(f)for f in[raw,oldraw,old,new,baseline/'pixel_flat.res.ext',run/'pixel_flat.res.ext',Path(__file__)]},scope='Fresh actual native Magic extraction + source export + private package. Internal rnode numbering may change despite fixed seed; original and reproduced byte hashes both preserved, equivalent electrical graph required.')
 (ROOT/'evidence/joint-pex/reproduction.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
 if not result['passed']:raise RuntimeError('Fresh extraction graph differs')
if __name__=='__main__':main()
