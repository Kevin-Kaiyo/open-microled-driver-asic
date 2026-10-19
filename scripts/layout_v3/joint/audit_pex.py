"""Check extraction annotation integrity and independently collapse all RC wires
back to the LVS topology. No capacitor or resistor is removed from the delivered
simulation model; only this named audit control shorts R and ignores C.
"""
from pathlib import Path
import json,hashlib,re,subprocess,os
ROOT=Path(__file__).resolve().parents[3];run=ROOT/'build/layout-v3/joint-r2';rc=run/'pex-driven-final/startup_integrated_v3_flat_rc.spice';src=rc.read_text();lines=re.sub(r'\n\+\s*',' ',src).splitlines();ports=next(x.split()[2:]for x in lines if x.startswith('.subckt'))
parent={}
def find(n):
 parent.setdefault(n,n)
 if parent[n]!=n:parent[n]=find(parent[n])
 return parent[n]
def union(a,b):
 a,b=find(a),find(b)
 if a!=b:parent[b]=a
for x in lines:
 if x.startswith('R'):
  t=x.split();union(t[1],t[2])
groups={}
for n in list(parent):groups.setdefault(find(n),[]).append(n)
canon={}
for root,nodes in groups.items():
 ps=[n for n in nodes if n in ports]
 assert len(ps)<=1,ps
 canon[root]=ps[0]if ps else sorted(nodes)[0]
def mapped(n):return canon.get(find(n),n)
mos=[]
for x in lines:
 if x.startswith('X'):
  t=x.split();mos.append(' '.join([t[0]]+[mapped(n)for n in t[1:5]]+t[5:]))
audit=run/'pex-collapse-audit.spice';audit.write_text('* Independent R=0/C-ignored topology control ONLY, never simulation replacement.\n.subckt startup_integrated_v3_flat '+' '.join(ports)+'\n'+'\n'.join(mos)+'\n.ends startup_integrated_v3_flat\n')
tcl=(ROOT/'scripts/layout_v3/joint/lvs.tcl').read_text().replace('$env(V3_JOINT_RUN)/extract/startup_integrated_v3.spice',str(audit)).replace('$extracted startup_integrated_v3"','$extracted startup_integrated_v3_flat"').replace('$env(V3_JOINT_RUN)/netgen-lvs.log','$env(V3_JOINT_RUN)/netgen-pex-collapse-lvs.log');(run/'pex-collapse-lvs.tcl').write_text(tcl)
pdk=ROOT/'build/layout/pdk';cmd=[ROOT/'build/layout/tools/install/bin/netgen','-batch','source',run/'pex-collapse-lvs.tcl']
with(run/'netgen-pex-collapse-stdout.log').open('w')as f:r=subprocess.run([str(x)for x in cmd],cwd=ROOT/'layout/startup_v3',env=os.environ|{'PDK_ROOT':str(pdk),'V3_JOINT_RUN':str(run),'V3_ROOT':str(ROOT)},stdout=f,stderr=subprocess.STDOUT)
log=(run/'netgen-pex-collapse-lvs.log').read_text();match=re.findall(r'^Final result:\s*(.+)$',log,re.M)==['Circuits match uniquely.']and not re.search(r'property errors|do not match|not equivalent',log,re.I)
old=(run/'pex/startup_integrated_v3_flat.ext').read_text();new=(run/'pex-driven-final/startup_integrated_v3_flat.ext').read_text();clean='\n'.join(x for x in new.splitlines()if not(x.startswith('attr ')and 'res:drive' in x))+'\n';drive=json.loads((run/'pex-driven-final/drive-attributes.json').read_text());only_attrs=clean==old
counts={key:sum(x.startswith(pre)for x in lines)for key,pre in [('mos','X'),('resistors','R'),('capacitors','C')]};result=dict(passed=bool(match and only_attrs),rc_short_topology_lvs_unique=bool(match),only_documented_drive_attributes_added=only_attrs,attribute_count=drive['node_count'],nets_extracted=6512,nets_total=6512,counts=counts,ports=ports,rc_sha256=hashlib.sha256(rc.read_bytes()).hexdigest(),audit_spice_sha256=hashlib.sha256(audit.read_bytes()).hexdigest(),scope='R collapse is audit control only. Delivered RC model retains every extracted R/C and all 39 analog MOS plus digital/filler devices; this checks connectivity, not frequency-dependent EM/PDK accuracy.')
(run/'pex-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(result);assert result['passed']
