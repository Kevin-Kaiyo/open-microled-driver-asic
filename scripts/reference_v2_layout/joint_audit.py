"""Independent exact fabrication-layer comparison of real composed GDS."""
from pathlib import Path
import argparse
import hashlib
import json
import klayout.db as k

ROOT=Path(__file__).resolve().parents[2]
ROUTING={34,35,36,38,40,41,42,46,81}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--module',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args();folder=ROOT/a.module
    c=json.loads((folder/'physical-contract.json').read_text())
    gds=folder/'generate'/(c['top']+'.gds')
    layout=k.Layout();layout.read(str(gds));cell=layout.cell(c['top'])
    source={};modules=[]
    for m in c['modules']:
        original=k.Layout();original.read(str(folder/'source'/(m['tag']+'.gds')))
        assert original.dbu==layout.dbu
        tr=k.Trans(*[round(v/layout.dbu) for v in m['offset_um']])
        layers=[]
        for i in original.layer_indexes():
            info=original.get_info(i)
            if info.datatype==10:continue
            old=k.Region(original.cell(m['top']).begin_shapes_rec(i)).transformed(tr)
            new=k.Region(cell.begin_shapes_rec(layout.layer(info)))
            lost=(old-new).area()*layout.dbu**2
            assert lost==0,(m['tag'],info,lost)
            key=(info.layer,info.datatype)
            source.setdefault(key,k.Region());source[key]+=old
            layers.append(dict(layer=info.layer,datatype=info.datatype,original_um2=old.area()*layout.dbu**2,lost_um2=lost))
        modules.append(dict(tag=m['tag'],input_gds_sha256=m['gds_sha256'],layers=layers))
    exact=[]
    for (layer,datatype),old in sorted(source.items()):
        if layer in ROUTING:continue
        new=k.Region(cell.begin_shapes_rec(layout.layer(layer,datatype)))
        xor=(old^new).area()*layout.dbu**2
        assert xor==0,(layer,datatype,xor)
        exact.append(dict(layer=layer,datatype=datatype,xor_um2=xor))
    # The independent schematic and extracted-device map must preserve the
    # distinct 5V reference and logic supply names throughout actual LVS.
    mapping=c['extracted_device_mapping']
    for d in mapping:
        for pin,logical in d['original_nodes'].items():
            rc=d['rc_nodes'][pin]
            if logical in ('VIN','VDD'):
                assert rc==logical or rc.startswith(logical+'.')
    value=dict(passed=True,gds=str(gds.relative_to(ROOT)),gds_sha256=hashlib.sha256(gds.read_bytes()).hexdigest(),
        method='Independent KLayout all-source fabrication polygon subset check; exact equality on every non-routing layer; datatype10 port metadata excluded.',
        modules=modules,exact_nonrouting_union=exact,separate_VIN_VDD_extracted_mapping=True,
        exclusions=['Port/text metadata is re-authored; no pad/ESD, package, substrate field or silicon signoff.'])
    (ROOT/a.out).write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(dict(passed=True,modules=len(modules),exact_nonrouting_layers=len(exact))))

if __name__=='__main__':main()
