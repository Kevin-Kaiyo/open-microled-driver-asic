#!/usr/bin/env python3
"""Effective resistance of the extracted wire-only network between named pins."""
from pathlib import Path
import json, hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'evidence/highspeed-nrz-pex/wire-paths.json'
def resistance(edges,a,b):
    seen={a}
    while True:
        grown=seen|{n for e in edges if any(x in seen for x in e['nodes']) for n in e['nodes']}
        if grown==seen:break
        seen=grown
    assert b in seen
    nodes=sorted(seen-{b});ix={x:i for i,x in enumerate(nodes)};g=np.zeros((len(nodes),len(nodes)));i=np.zeros(len(nodes));i[ix[a]]=1
    for e in edges:
        n,m=e['nodes'];r=e['ohm']
        if n not in seen:continue
        assert r>0
        if n!=b:g[ix[n],ix[n]]+=1/r
        if m!=b:g[ix[m],ix[m]]+=1/r
        if n!=b and m!=b:g[ix[n],ix[m]]-=1/r;g[ix[m],ix[n]]-=1/r
    v=np.linalg.solve(g,i);assert np.max(np.abs(g@v-i))<1e-9
    return float(v[ix[a]])
assert abs(resistance([{'nodes':['a','b'],'ohm':10},{'nodes':['b','c'],'ohm':20}],'a','c')-30)<1e-9
assert abs(resistance([{'nodes':['a','b'],'ohm':10},{'nodes':['a','b'],'ohm':20}],'a','b')-20/3)<1e-9
result={'method':'1 A injected between selected endpoints of wire-only extracted R graph; all other endpoints open. MOS conductance excluded. This is not total driver output resistance.','analytic_checks':['10+20 series = 30 ohm','10 || 20 = 6.666666667 ohm'],'routes':{}}
for route in 'AB':
    folder=ROOT/'build/highspeed-nrz-layout/r4'/route
    p=folder/'pex-audit.json';audit=json.loads(p.read_text());c=json.loads((folder/'physical-contract.json').read_text());mp={d['original_instance'][1:]:d['rc_nodes'] for d in c['extracted_device_mapping']}

    if route=='B':mp['N1']=mp['INV1N'];mp['N2']=mp['INV2N']
    paths=[('DATA→N1.G','DATA',mp['N1']['G']),('N1.D→N2.G',mp['N1']['D'],mp['N2']['G'])]
    if route=='A':paths += [('N2.D→NOUT.G',mp['N2']['D'],mp['NOUT']['G']),('OUT→NOUT.D','OUT',mp['NOUT']['D']),('VSS→N1.S','VSS',mp['N1']['S']),('VSS→N1.B','VSS',mp['N1']['B'])]
    else:paths += [('N2.D→LED.G',mp['N2']['D'],mp['LED']['G']),('N1.D→DUMMY.G',mp['N1']['D'],mp['DUMMY']['G']),('OUT→LED.D','OUT',mp['LED']['D']),('VSS→TAIL.S','VSS',mp['TAIL']['S']),('VSS→TAIL.B','VSS',mp['TAIL']['B'])]
    if route=='B':paths=[(label.replace('N1','INV1N').replace('N2','INV2N'),a,b)for label,a,b in paths]
    result['routes'][route]={'audit_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'paths':[{'label':label,'from':a,'to':b,'effective_R_ohm':resistance(audit['resistors'],a,b)}for label,a,b in paths]}
OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(result['routes'],indent=2,ensure_ascii=False))
