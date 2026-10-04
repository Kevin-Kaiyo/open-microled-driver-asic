"""Preserve the as-run link and prove final serialization has identical R/C.

Instance names and statement order do not change a linear R/C network. Node
names, subcircuit ports, types, values and repeated components remain exact.
This does not compare layouts or expand the simulated PEX scope.
"""
from decimal import Decimal
from pathlib import Path
import hashlib
import json
import re
import shutil

ROOT=Path(__file__).resolve().parents[2]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def graph(text):
    ports=None;parts=[]
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith('*'):continue
        tokens=line.split()
        if tokens[0].lower()=='.subckt':ports=tokens[1:];continue
        if tokens[0].lower()=='.ends':continue
        if len(tokens)!=4 or tokens[0][0].upper() not in ['R','C']:
            raise RuntimeError('Unsupported element in linear-RC identity proof: '+line)
        match=re.fullmatch(r'([0-9.eE+-]+)([fpnum]?)',tokens[3])
        if not match:raise RuntimeError('Unexpected R/C numeric value')
        scale={'':Decimal(1),'m':Decimal('1e-3'),'u':Decimal('1e-6'),'n':Decimal('1e-9'),
               'p':Decimal('1e-12'),'f':Decimal('1e-15')}[match[2]]
        value=str((Decimal(match[1])*scale).normalize())
        parts.append([tokens[0][0].upper(),sorted(tokens[1:3]),value])
    if ports!=['pwm_link_rc','A','Y','VDD','VSS']:raise RuntimeError('Subckt identity changed')
    return dict(subckt_and_ports=ports,elements=sorted(parts,key=lambda p:json.dumps(p)))


def main():
    summary=json.loads((ROOT/'evidence/interface/summary.json').read_text())
    work=ROOT/summary['run_directory']
    dest=ROOT/'evidence/interface/input-snapshots';dest.mkdir(exist_ok=True)
    names=['evidence/integration/pwm_link_rc.spice','evidence/integration/link-rc.json']
    paths={}
    for name in names:
        old=work/'inputs'/name;new=ROOT/name;snapshot=dest/Path(name).name
        if sha(old)!=summary['source_hashes'][name]:raise RuntimeError('Frozen source is not as-run')
        shutil.copyfile(old,snapshot)
        paths[name]=dict(as_run_sha256=sha(old),current_sha256=sha(new),
                         snapshot_path=str(snapshot.relative_to(ROOT)),snapshot_sha256=sha(snapshot))
    before=graph((dest/'pwm_link_rc.spice').read_text());after=graph((ROOT/names[0]).read_text())
    equal=before==after
    if not equal:raise RuntimeError('Electrical R/C topology changed; new simulations required')
    modified=graph((dest/'pwm_link_rc.spice').read_text().replace('4.81871','4.9'))
    removed=graph('\n'.join(line for line in (dest/'pwm_link_rc.spice').read_text().splitlines() if not line.startswith('C1 ')))
    negative_controls=dict(changed_R_rejected=modified!=after,removed_C_rejected=removed!=after)
    oldmeta=json.loads((dest/'link-rc.json').read_text());newmeta=json.loads((ROOT/names[1]).read_text())
    current_GDS_hash=newmeta['inputs_sha256']['build/integration/r3/pixel_integrated.gds']
    previous_GDS_hash=oldmeta['inputs_sha256']['build/integration/r3/pixel_integrated.gds']
    result=dict(passed=equal and all(negative_controls.values()) and current_GDS_hash==previous_GDS_hash,
                purpose='as-run link and final serialization differ only instance names and order; preserve the actual recorded byte hashes',
                paths=paths,electrical_graph=after,electrical_graph_sha256=hashlib.sha256(json.dumps(after,sort_keys=True).encode()).hexdigest(),
                electrical_graph_equal=equal,negative_controls=negative_controls,full_top_GDS_identity_equal=current_GDS_hash==previous_GDS_hash,
                full_top_GDS_sha256=current_GDS_hash,metadata_changed=True,
                metadata_interpretation='current metadata adds substrate binding/full-top extraction provenance and regenerated helper artifact locators; it does not retroactively change frozen stimulus/model',
                simulated_joint_PEX_scope='new M3 metal-only span; ideal PG boundary; no full joint digital/analog PEX',
                mapper_sha256=sha(Path(__file__)))
    (ROOT/'evidence/interface/input-mapping.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if not result['passed']:raise RuntimeError('Input identity mapping failed')


if __name__=='__main__':main()
