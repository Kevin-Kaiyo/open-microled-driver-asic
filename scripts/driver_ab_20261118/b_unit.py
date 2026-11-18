#!/usr/bin/env python3
"""Size every mirror unit identically. Rank with the nominal, slow-hot and fast-cold DC points."""
from concurrent.futures import ThreadPoolExecutor
from itertools import product
import json
import os
from pathlib import Path
import re

from b_grid import BUILD, EV, ROOT, case, sha

SOURCE = ROOT / 'build/driver-ab-20261118/b/merged220c10'
GEOMETRIES = [(4,2), (6,2), (8,2), (5,2.5), (6,3), (8,4), (4.5,1.5), (6,1.5)]


def fixture(width, length):
    name = f'unit-W{width:g}-L{length:g}'
    folder = BUILD / 'geometry-inputs' / name
    folder.mkdir(parents=True,exist_ok=True)
    source_route = SOURCE / 'inputs/route_b.spice'
    route, count = re.subn(r'^(X(?:REF|BASE|TAIL[12]?) .+? nfet_03v3) w=4u l=2u .+$',
                           lambda m: f'{m[1]} w={width:g}u l={length:g}u ad={width*.44:g}p as={width*.44:g}p pd={2*(width+.44):g}u ps={2*(width+.44):g}u',
                           source_route.read_text(), flags=re.MULTILINE)
    assert count == 5
    model = folder/'route_b.spice'
    model.write_text(route)
    for level in [0,1]:
        src = SOURCE / f'tt-DC-L{level}' / 'testbench.spice'
        dst = folder / src.parent.name / src.name
        dst.parent.mkdir(exist_ok=True)
        def include(match):
            original = (src.parent/match[2]).resolve(strict=True)
            dep = model if original==source_route else original
            return f'{match[1]}"{os.path.relpath(dep,dst.parent)}"'
        dst.write_text(re.sub(r'^(\.(?:include|lib) )"([^"]+)"',include,src.read_text(),flags=re.MULTILINE))
    return name,folder


def main():
    summary=[]
    for w,l in GEOMETRIES:
        name,folder=fixture(w,l)
        training=[(s,t,v,r,level) for (s,t,v),(r,level) in product(
            [('typical',27,100),('ss',85,95),('ff',-40,105)],product([-10,0,10],[0,1]))]
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows=list(pool.map(lambda p:case('screen-'+name,folder,p), training))
        summary.append(dict(width_um=w,length_um=l, worst_percent=max(abs(r['error_percent']) for r in rows),
                            route_sha256=sha(folder/'route_b.spice'), points=rows))
    print([(r['width_um'],r['length_um'],r['worst_percent']) for r in summary])
    (EV/'b-unit-screen.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    main()
