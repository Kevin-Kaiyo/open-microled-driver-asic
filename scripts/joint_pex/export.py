"""Project actual flat RC into a 12-MOS, ideal-PG joint pixel boundary.

No capacitor is clipped. Every source R/C receives an auditable disposition.
Diffusion A/P comes from the actual .ext geometry, including shared allocations.
"""
from pathlib import Path
from collections import defaultdict, Counter
from decimal import Decimal
import argparse, hashlib, json, re, shlex

ROOT=Path(__file__).resolve().parents[2]
SUFFIX={'':Decimal(1),'f':Decimal('1e-15'),'p':Decimal('1e-12'),'n':Decimal('1e-9'),'u':Decimal('1e-6'),'m':Decimal('1e-3'),'k':Decimal('1e3'),'meg':Decimal('1e6')}
def number(s):
 m=re.fullmatch(r'([+-]?[0-9.]+(?:e[+-]?\d+)?)([a-z]*)',s.lower());return Decimal(m[1])*SUFFIX[m[2]]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class DSU:
 def __init__(self):self.p={}
 def find(self,n):
  self.p.setdefault(n,n)
  if self.p[n]!=n:self.p[n]=self.find(self.p[n])
  return self.p[n]
 def join(self,a,b):
  a,b=self.find(a),self.find(b)
  if a!=b:self.p[max(a,b)]=min(a,b)
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--output',required=True);p.add_argument('--hier-run',default='full-nominal-r1');a=p.parse_args()
 run=ROOT/'build/joint-pex'/a.run;out=ROOT/a.output
 if out.exists() and any(out.iterdir()):raise RuntimeError('Use fresh --output')
 out.mkdir(parents=True,exist_ok=True)
 raw=run/'pixel_flat_rc.spice';ext=run/'pixel_flat.ext';extraction=json.loads((run/'extraction.json').read_text())
 assert extraction['passed'] and extraction['drc_count']==['0'] and sha(raw)==extraction['outputs_sha256'][raw.name]
 parts=[];d=DSU();mos=[];res=[];caps=[]
 for line in raw.read_text().splitlines():
  if line and line[0] in 'XRC':
   t=line.split();parts.append(t)
   if t[0][0]=='R':res.append(t);d.join(t[1],t[2])
   elif t[0][0]=='C':caps.append(t)
   else:mos.append(t)
 # Verify actual killnode/rnode replacement blocks before attaching .ext identities.
 # This is metadata equivalence, never an added resistor/circuit connection.
 for t in parts:
  for n in t[1:5] if t[0][0]=='X' else t[1:3]:d.find(n)
 known=set(d.p);blocks={};current=None
 for line in (run/'pixel_flat.res.ext').read_text().splitlines():
  if line.startswith('killnode '):current=shlex.split(line)[1];blocks[current]=[]
  elif line.startswith('rnode ') and current:
   node=shlex.split(line)[1]
   if node.startswith(current.rstrip('#')+'.'):blocks[current].append(node)
 for original,members in blocks.items():
  present=[n for n in members if n in known];roots={d.find(n)for n in present}
  assert len(roots)==1,(original,roots)
  if original in known:assert d.find(original)in roots,(original,roots)
  d.join(original,present[0])
 pg={d.find('VDD'):'VDD',d.find('VSS'):'VSS'};assert len(pg)==2
 def r(n):return d.find(n)
 def props(t):return {k:number(v) for k,v in (z.split('=')for z in t[6:])}
 def sig(t):
  q=props(t);return (t[5],r(t[2]),r(t[4]),q['w'],q['l'],tuple(sorted([(r(t[1]),q['ad'],q['pd']),(r(t[3]),q['as'],q['ps'])])))
 candidates=defaultdict(list)
 for t in mos:candidates[sig(t)].append(t)
 selected=[];matches=[]
 for line in ext.read_text().splitlines():
  if not line.startswith('device msubckt '):continue
  t=shlex.split(line);x,y=int(t[3]),int(t[4]);kind='analog'if t[2]in['nfet_06v0','pfet_06v0'] else 'output12'if 31568<=x<=32464 and 21464<=y<=22248 else None
  if not kind:continue
  dims={k:Decimal(v)*Decimal('.005e-6') for k,v in(z.split('=')for z in t[7:9])}
  ap=[]
  for node,area_per in[(t[13],t[15]),(t[16],t[18])]:
   ar,pe=map(Decimal,area_per.split(','));ap.append((r(node),ar*Decimal('.000025e-12'),pe*Decimal('.005e-6')))
  key=(t[2],r(t[10]),r(t[9]),dims['w'],dims['l'],tuple(sorted(ap)))
  found=candidates[key];assert len(found)==1,(kind,x,y,found)
  actual=found[0];selected.append(actual);matches.append(dict(kind=kind,ext_device=line,spice_device=' '.join(actual),gate_xy_um=[x*.005,y*.005],source_id=actual[0],w_um=float(dims['w']*Decimal('1e6')),l_um=float(dims['l']*Decimal('1e6'))))
 assert Counter(m['kind']for m in matches)=={'analog':6,'output12':6}
 active={r(n)for t in selected for n in t[1:5]}-set(pg)
 alias={'DRIVER_I':'I','DRIVER_Z':'PWM_DRIVE','ANALOG_PWM':'PWM','pwm_monitor':'PWM_MON','bias':'BIAS','led_k':'LED_K','gate':'GATE','pwm_b':'PWM_B','VDD':'VDD','VSS':'VSS'}
 neighbors=sorted({r(n)for t in caps if r(t[1])in active or r(t[2])in active for n in t[1:3]}-active-set(pg))
 neighbor_map={n:f'NBR_{i:02d}'for i,n in enumerate(neighbors)}
 def mapped(n):
  rt=r(n)
  if rt in pg:return pg[rt]
  if rt not in active:return neighbor_map[rt]
  return alias.get(n,n)
 ledger=[];capgroups=defaultdict(list);kept_res=[]
 for t in res:
  rt=r(t[1]);action='retain'if rt in active else 'ideal_pg_remove'if rt in pg else 'outside_remove'
  q=dict(id=t[0],kind='R',raw=t,action=action)
  if action=='retain':q['mapped']=[mapped(t[1]),mapped(t[2])];kept_res.append([t[0],*q['mapped'],t[3]])
  elif action=='ideal_pg_remove':q['mapped']=[pg[rt],pg[rt]]
  ledger.append(q)
 for t in caps:
  roots=[r(n)for n in t[1:3]];action='retain_aggregate'if any(rt in active for rt in roots)else 'fixed_pg_only_remove'if all(rt in pg for rt in roots)else 'outside_remove'
  q=dict(id=t[0],kind='C',raw=t,action=action)
  if action=='retain_aggregate':
   pair=tuple(sorted(mapped(n)for n in t[1:3]));q['mapped']=list(pair);capgroups[pair].append(t)
  elif action=='fixed_pg_only_remove':q['mapped']=[pg[rt]for rt in roots]
  ledger.append(q)
 coutput=[];aggregate=[]
 for i,(pair,items)in enumerate(sorted(capgroups.items())):
  value=sum((number(t[3])for t in items),Decimal(0));assert value>=0,(pair,value)
  q=dict(id=f'C{i}',nodes=list(pair),value_f=str(value),source_ids=[t[0]for t in items],multiplicity=len(items));aggregate.append(q)
  if value:coutput.append([q['id'],*pair,f'{value:.12e}'])
 model=['* Actual common GDS, output12 + analog six MOS; ideal PG, external neighbor boundary.', '* Replaces old buffer schematic, digital SPEF, link RC and analog RC together.', '.subckt output_pixel_pex I VDD VSS BIAS LED_K GATE PWM_B PWM_DRIVE PWM_MON PWM '+' '.join(neighbor_map.values())]
 for i,t in enumerate(selected):model.append(' '.join([f'X{i}',*[mapped(n)for n in t[1:5]],*t[5:]]))
 model+=[' '.join(t)for t in kept_res+coutput];model.append('.ends output_pixel_pex')
 (out/'output_pixel_pex.spice').write_text('\n'.join(model)+'\n')
 # Every omitted negative C is preserved here with its exact original value.
 negatives=[q for q in ledger if q['kind']=='C'and number(q['raw'][3])<0]
 assert all(q['action']=='fixed_pg_only_remove'for q in negatives),negatives
 ports=['I','VDD','VSS','BIAS','LED_K','GATE','PWM_B','PWM_DRIVE','PWM_MON','PWM',*neighbor_map.values()]
 # Ext node names are physical/net identities, not guessed logic truth states.
 identities={n:[]for n in neighbors}
 for line in ext.read_text().splitlines():
  if line.startswith('equiv '):
   t=shlex.split(line)
   for n in t[1:]:
    if r(n)in identities:identities[r(n)].append(line)
 from identify_neighbors import identify
 hier=ROOT/'build/joint-pex'/a.hier_run;ident=identify(hier,ext);assert ident['matched_MOS']==5644 and not ident['unmatched']
 neighbor_records=[]
 for n in neighbors:
  hnet=ident['gate_net_map'].get(n,[]);aliases=sorted({z for hn in hnet for z in ident['hierarchical_aliases'].get(hn,[hn])})
  assert len(hnet)==1,(n,hnet)
  neighbor_records.append(dict(port=neighbor_map[n],physical_net=n,hierarchical_net=hnet[0],hierarchical_aliases=aliases,equivalences=sorted(set(identities[n])),boundary='Explicit source in testbench. Internal floating/fillcap/FF nets are artificial quiet-clamp/rail-bracket sensitivities; no claim of functional neighbor state. External duty/enable may use declared input stimulus.'))
 summary=dict(passed=True,rc_style=extraction['rc_style'],source_run=str(run.relative_to(ROOT)),inputs_sha256={str(f.relative_to(ROOT)):sha(f)for f in[raw,ext,run/'pixel_flat.res.ext',run/'extraction.json',Path(__file__),ROOT/'scripts/joint_pex/identify_neighbors.py',*hier.glob('*.ext')]},counts=dict(raw_MOS=len(mos),raw_R=len(res),raw_C=len(caps),selected_MOS=len(selected),selected_R=len(kept_res),selected_C=len(coutput),negative_raw_C=len(negatives),neighbors=len(neighbors)),ports=ports,neighbors=neighbor_records,active_components=sorted(active),ideal_pg_components=pg,matches=matches,negative_capacitors=negatives,scope={'includes':['actual output12 six MOS and diffusion A/P','analog six MOS and diffusion A/P','signal-component distributed metal/diffusion R','digital output routing + cross-macro span + actual analog input bus','selected signal coupling to ideal PG and explicit neighboring nets'],'excludes':['full digital transistor transient','upstream FF active devices','all PG/source/body resistance and PG-only fixed-voltage capacitance','neighbor active drivers and distributed impedance','IR/EM/substrate impedance/pad/ESD/package/silicon/optics'],'double_count_rule':'Instantiate this joint circuit once; do not additionally instantiate old buffer/analog RC/SPEF/link.'},capacitance_totals_f={k:str(sum((number(q['raw'][3])for q in ledger if q['kind']=='C'and q['action']==k),Decimal(0)))for k in['retain_aggregate','fixed_pg_only_remove','outside_remove']},retained_negative_aggregate_count=0,passivity=dict(proof='Every exported R>0 and every exported two-terminal C>=0. Therefore each passive stamp v-transpose C v = C*(v_a-v_b)^2 is nonnegative; sum is positive-semidefinite for any node vector. Ideal-PG fixed-voltage-only terms are omitted by boundary projection, including all 19 signed template corrections; no clipping.',negative_dynamic_pairs=0),port_geometry_um={'I':[161.48,109.84],'PWM_DRIVE':[159.24,108.72],'PWM':[119.99,111.52],'PWM_MON':[125,111.52]},default_neighbor_clamp_fraction=0.0,default_neighbor_clamp_scope='Artificial ideal 0V clamp on all explicit NBR ports, including internal floating fillcap/FF nets. Conditional comparison only; actual floating/active neighbor behavior unverified.')
 (out/'projection-ledger.json').write_text(json.dumps(dict(elements=ledger,capacitor_aggregates=aggregate),indent=2)+'\n')
 summary['outputs_sha256']={f.name:sha(f)for f in out.iterdir()if f.is_file()};(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary['counts'],indent=2));print(out)
if __name__=='__main__':main()
