"""DC transfer resistance of the extracted VSS network, not a substrate field solve."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def solve(directory):
    c=json.loads((directory/'physical-contract.json').read_text())
    path=directory/'full-rc'/(c['top']+'_rc.spice')
    resistors=[]
    for line in path.read_text().splitlines():
        t=line.split()
        if t and t[0].startswith('R') and all(n.startswith('VSS') for n in t[1:3]):
            resistors.append((t[1],t[2],float(t[3])))
    names=sorted(set(n for a,b,_ in resistors for n in (a,b))-{'VSS'})
    index={n:i for i,n in enumerate(names)}
    g=np.zeros((len(names),len(names)))
    for a,b,r in resistors:
        for n in (a,b):
            if n!='VSS':g[index[n],index[n]]+=1/r
        if a!='VSS' and b!='VSS':
            g[index[a],index[b]]-=1/r
            g[index[b],index[a]]-=1/r
    source=c['extracted_resistor_mapping'][0]['rc_nodes']['B']
    rhs=np.zeros(len(names));rhs[index[source]]=1
    voltage=np.linalg.solve(g,rhs)
    transfers={m['original_instance']:float(voltage[index[m['rc_nodes']['B']]])
               for m in c['extracted_device_mapping'] if m['original_nodes']['B']=='VSS'}
    residual=float(np.max(np.abs(g@voltage-rhs)))
    assert residual<1e-8
    return dict(directory=str(directory.relative_to(ROOT)),source=source,
        self_ohm=float(voltage[index[source]]),logic_body_transfer_ohm=transfers,
        max_residual_A=residual,rc_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('routes',nargs='+',help='Repository relative physical route directories')
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    result=dict(method='1 A DC injection at compact resistor B, logical VSS port clamped to 0 V; '
        'solve only actual extracted interconnect VSS R network. Not a 3D substrate solution '
        'or full transient including nonlinear devices and capacitances.',
        results=[solve(ROOT/p) for p in args.routes])
    (ROOT/args.out).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
