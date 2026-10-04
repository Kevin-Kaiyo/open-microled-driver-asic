"""Match full-hierarchy MOS gate geometry to flat extracted gate-net identities."""
from pathlib import Path
from collections import defaultdict
import argparse,json,shlex,re
from export import DSU,ROOT,sha

def identify(hier,flat):
 d=DSU();devices=[];paths={}
 def point(t,x,y):a,b,c,e,f,g=t;return a*x+b*y+c,e*x+f*y+g
 def compose(t,u):
  a,b,c,e,f,g=t;A,B,C,E,F,G=u
  return(a*A+b*E,a*B+b*F,a*C+b*G+c,e*A+f*E,e*B+f*F,e*C+f*G+g)
 def visit(cell,path,transform):
  paths[path]=cell
  for line in(hier/(cell+'.ext')).read_text().splitlines():
   if not line.startswith(('use ','merge ','equiv ','device msubckt ')):continue
   t=shlex.split(line)
   if t[0]=='use':visit(t[1],path+t[2]+'/',compose(transform,tuple(map(int,t[3:9]))))
   elif t[0]in['merge','equiv']:d.join(path+t[1],path+t[2])
   else:
    dims={k:int(v)for k,v in(z.split('=')for z in t[7:9])};x,y=int(t[3]),int(t[4]);corners=[point(transform,X,Y)for X in[x,x+dims['l']]for Y in[y,y+dims['w']]]
    gatexy=(min(z[0]for z in corners),min(z[1]for z in corners));devices.append(dict(key=(t[2],*gatexy),gate=path+t[10],body=path+t[9],terminals=[(path+t[13],t[15]),(path+t[16],t[18])],instance=path.rstrip('/'),cell=cell))
 visit('pixel_integrated','',(1,0,0,0,1,0))
 geom=defaultdict(list)
 for z in devices:geom[z['key']].append(z)
 mapping=defaultdict(set);matched=0;unmatched=[]
 for line in flat.read_text().splitlines():
  if not line.startswith('device msubckt '):continue
  t=shlex.split(line);key=(t[2],int(t[3]),int(t[4]));found=geom[key]
  if len(found)!=1:unmatched.append(dict(key=key,candidates=len(found)));continue
  z=found[0];matched+=1;mapping[t[10]].add(d.find(z['gate']));mapping[t[9]].add(d.find(z['body']))
  for n,ap in[(t[13],t[15]),(t[16],t[18])]:
   roots={d.find(hn)for hn,hap in z['terminals']if hap==ap}
   if len(roots)==1:mapping[n].update(roots)
 aliases=defaultdict(list)
 for n in d.p:aliases[d.find(n)].append(n)
 return dict(matched_MOS=matched,unmatched=unmatched,gate_net_map={n:sorted(v)for n,v in mapping.items()},hierarchical_aliases={n:sorted(v)for n,v in aliases.items()},instance_cells=paths)

def main():
 p=argparse.ArgumentParser();p.add_argument('--flat-run',required=True);p.add_argument('--hier-run',default='full-nominal-r1');p.add_argument('--output',required=True);a=p.parse_args()
 hier=ROOT/'build/joint-pex'/a.hier_run;flat=ROOT/'build/joint-pex'/a.flat_run/'pixel_flat.ext';q=identify(hier,flat)
 q['inputs_sha256']={str(f.relative_to(ROOT)):sha(f)for f in [flat,Path(__file__),*hier.glob('*.ext')]};out=ROOT/a.output;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(q,indent=2)+'\n');print({k:q[k]for k in['matched_MOS','unmatched']})
if __name__=='__main__':main()
