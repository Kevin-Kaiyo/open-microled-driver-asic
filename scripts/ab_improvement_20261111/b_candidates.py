#!/usr/bin/env python3
"""Append-only B candidate definitions for matched-load transistor experiments.

The original load, current reference topology and terminal-energy boundary remain
unchanged. CFF is a physical capacitor driven by the counted CMOS gate supply;
it is not an ideal edge-current source. These are hypotheses, not qualified IP.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/blue-emitter-speed-review-20261110/microled/inputs/route_b.spice'
PARAMETERS = dict(RSET=20126.535444301146, WTAIL=5.76e-6, RINL=8e-6)
SPECS = {
    'B_baseline': dict(hypothesis='Unmodified frozen B baseline.'),
    'B_rin1': dict(rin=1e-6, hypothesis='Reduce input RC by RINL 8 to 1 um; preserve gate devices and output stage.'),
    'B_fast': dict(fast=True, hypothesis='Use 3.3 V, L=0.28 um CMOS predrivers on the 3.3 V domain; keep RINL=8 um and 6 V output switches.'),
    'B_fast_wide': dict(fast=True, rin=4e-6, wide=True, hypothesis='3.3 V predrivers plus 4 um x 4 um high-res poly input resistor: about 1 kohm while reducing current density versus a 1 um wide resistor.'),
    'B_fast_rin1': dict(fast=True, rin=1e-6, hypothesis='Combine verified input RC and faster predriver changes; keep output current steering unchanged.'),
}
for cap in [5,10,15,20,30,40]:
    SPECS[f'B_fast_ff{cap}'] = dict(fast=True,rin=1e-6,cff=cap,
        hypothesis=f'Add {cap} fF from complementary gate GB to OUT for edge-charge feed-forward; capacitor is open at DC. Cathode is pulled up for data 1->0 and down for 0->1. Check current overshoot, body and terminal stress, and extra gate energy.')

for cap in [10,20,31.275,40]:
    slug=str(cap).replace('.', 'p')
    SPECS[f'B_wide_ff{slug}'] = dict(fast=True,rin=4e-6,wide=True,cff=cap,
        hypothesis=f'Physical-aware 4 um x 4 um input resistor with 3.3 V predrivers and {cap} fF GB-to-OUT feed-forward. DC target unchanged; check dynamic peak current, body stress and charged-gate energy. 31.275 fF corresponds to the nominal minimum 5x5 um 1fF/um2 MIM model including edge capacitance, but here is still a lumped schematic capacitor.')

def candidate(name):
    spec=SPECS[name];text=BASE.read_text();parameters=dict(PARAMETERS)
    if 'rin' in spec: parameters['RINL']=spec['rin']
    if spec.get('wide'): text=text.replace('r_width=1u r_length={RINL}', 'r_width=4u r_length={RINL}')
    if spec.get('fast'):
        lines=[]
        for line in text.splitlines():
            if line.startswith(('XINV1N ','XINV2N ')):
                line=line.replace('nfet_06v0','nfet_03v3').replace('l=.7u','l=.28u')
            if line.startswith(('XINV1P ','XINV2P ')):
                line=line.replace('pfet_06v0','pfet_03v3').replace('l=.55u','l=.28u')
            lines.append(line)
        text='\n'.join(lines)+'\n'
    if spec.get('cff'):
        text=text.replace('.ends fair_b',f'* DC-neutral edge assist; counted GB gate-driver charges this capacitor.\nCFF GB OUT {spec["cff"]}f\n.ends fair_b')
    return dict(name=name,route='B',route_text=text,parameters=parameters,
                hypothesis=spec['hypothesis'],notes=dict(cff_fF=spec.get('cff',0),
                changes={k:v for k,v in spec.items() if k!='hypothesis'},
                retained='Same XREF/XBASE/XTAIL, 6 V XLED/XDUMMY, 50 kohm RDUMMY, common reference, 25/100 uA DC targets, static LED I-V and nominal dynamic load.'))

if __name__=='__main__':
    import json
    print(json.dumps({k:{a:b for a,b in candidate(k).items() if a!='route_text'} for k in SPECS},indent=2))
