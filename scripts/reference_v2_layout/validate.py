"""Read-only validation of generated evidence, including actual 03/06 GDS masks."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
import klayout.db as k

ROOT=Path(__file__).resolve().parents[2]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def validate(base):
    manifest=json.loads((base/'artifact-manifest.json').read_text())
    for item in manifest['artifacts']:
        path=base/item['path']
        assert path.is_file() and path.stat().st_size==item['size'] and sha(path)==item['sha256'],path
    status=json.loads((base/'status.json').read_text())
    routes={}
    for route,s in status.items():
        folder=base/route
        c=json.loads((folder/'physical-contract.json').read_text());top=c['top']
        gds=folder/'generate'/(top+'.gds')
        assert sha(gds)==c['gds_sha256']
        layout=k.Layout();layout.read(str(gds));cell=layout.cell(top)
        active=k.Region(cell.begin_shapes_rec(layout.layer(22,0)))
        poly=k.Region(cell.begin_shapes_rec(layout.layer(30,0)))
        dual=k.Region(cell.begin_shapes_rec(layout.layer(55,0)))
        maskchecks=[]
        for d in c['devices']:
            x,y,w,l=d['cx'],d['cy'],d['w_um'],d['l_um']
            window=k.Region(k.DBox(x-l/2-.1,y-w/2-.01,x+l/2+.1,y+w/2+.01).to_itype(layout.dbu))
            channel=(active & poly & window).merged()
            assert math.isclose(channel.area()*layout.dbu**2,w*l,rel_tol=1e-10)
            overlap=(channel&dual).area()*layout.dbu**2
            expected=w*l if d['model'].endswith('06v0') else 0
            assert math.isclose(overlap,expected,rel_tol=1e-10,abs_tol=1e-12),(d,overlap,expected)
            maskchecks.append(dict(instance=d['name'],model=d['model'],channel_um2=w*l,dualgate_overlap_um2=overlap,passed=True))
        for name in ('magic_drc','readback_drc','lvs','readback_lvs','klayout_drc','pex_audit','gds_geometry'):
            assert s[name]['passed'],(route,name)
        for log in ('lvs.log','readback-lvs.log','rc-collapse-lvs.log'):
            txt=(folder/log).read_text()
            assert re.findall(r'^Final result:\s*(.+)$',txt,re.M)==['Circuits match uniquely.']
            assert not re.search('property errors|do not match|not equivalent',txt,re.I)
        assert len(ET.parse(folder/'klayout'/(top+'_main.lyrdb')).findall('.//item'))==0
        pex=json.loads((folder/'pex-audit.json').read_text())
        rc=folder/'full-rc'/(top+'_rc.spice')
        assert sha(rc)==pex['full_rc_sha256']
        assert pex['all_nets_extracted'] and pex['expected_nets']==pex['extracted_nets']==len(c['buses_um'])
        corrections=json.loads((folder/'capacitance-correction.json').read_text())
        assert corrections['passed'] and corrections['matrix_max_abs_error_farad']<1e-27
        assert corrections['r_or_mos_changed']==False
        controls=[]
        for control in json.loads((folder/'negative-controls.json').read_text()):
            mutated=folder/'controls'/control['control']/(top+'.gds')
            assert sha(mutated)==control['gds_sha256']
            m=k.Layout();m.read(str(mutated));mc=m.cell(top)
            total=0
            for i in layout.layer_indexes():
                info=layout.get_info(i)
                original=k.Region(cell.begin_shapes_rec(i))
                altered=k.Region(mc.begin_shapes_rec(m.layer(info)))
                total+=(original^altered).area()*layout.dbu**2
            assert total>0 and math.isclose(total,control['changed_polygon_area_um2'],rel_tol=1e-9)
            assert control['passed'] and not control['lvs']['passed']
            controls.append(dict(control=control['control'],actual_changed_area_um2=total,lvs_rejected=True))
        routes[route]=dict(gds_sha256=sha(gds),rc_sha256=sha(rc),dualgate_checks=maskchecks,negative_controls=controls,
                           counts=pex['counts'],all_nets_extracted=True)
    return dict(schema_version=1,passed=True,raw_run=str(base.relative_to(ROOT)),manifest_files=len(manifest['artifacts']),
                method='Rehash every frozen artifact, parse full LVS and independent KLayout report, intersect actual channel polygons with Dualgate 55/0, and compare actual negative-control polygons.',routes=routes)

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    result=validate(ROOT/a.run)
    (ROOT/a.out).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'manifest_files':result['manifest_files'],'routes':list(result['routes'])}))
if __name__=='__main__':main()
