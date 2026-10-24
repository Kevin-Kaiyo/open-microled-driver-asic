"""Single-variable real-GDS comparison: identical MOS, added supply copper only."""
from pathlib import Path
import argparse
import hashlib
import json
import klayout.db as k

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--thin",required=True)
    p.add_argument("--pg",required=True)
    p.add_argument("--thin-network",required=True)
    p.add_argument("--pg-network",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    folders=[ROOT/a.thin,ROOT/a.pg]
    contracts=[json.loads((f/"physical-contract.json").read_text()) for f in folders]
    networks=[json.loads((ROOT/f).read_text())["networks"] for f in [a.thin_network,a.pg_network]]
    assert contracts[0]["devices"]==contracts[1]["devices"]
    assert contracts[0]["ports"]==contracts[1]["ports"]
    assert (folders[0]/"source/schematic.spice").read_bytes()==(folders[1]/"source/schematic.spice").read_bytes()
    layouts=[]
    for f,c in zip(folders,contracts):
        layout=k.Layout();layout.read(str(f/"generate"/(c["top"]+".gds")))
        layouts.append(layout)
    assert layouts[0].dbu==layouts[1].dbu
    cells=[l.cell(c["top"]) for l,c in zip(layouts,contracts)]
    layer_ids={(l.get_info(i).layer,l.get_info(i).datatype) for l in layouts for i in l.layer_indexes()}
    geometry=[];metadata=[]
    for layer,datatype in sorted(layer_ids):
        regions=[k.Region(cell.begin_shapes_rec(l.layer(layer,datatype))) for l,cell in zip(layouts,cells)]
        lost=(regions[0]-regions[1]).area()*layouts[0].dbu**2
        added=(regions[1]-regions[0]).area()*layouts[0].dbu**2
        if datatype==10:
            # GF180 port/text purpose, not conducting fabrication geometry.
            if lost or added:metadata.append(dict(layer=layer,datatype=datatype,lost_um2=lost,added_um2=added))
            continue
        assert lost==0,(layer,datatype,lost)
        if added:
            assert datatype==0 and layer in [34,35,36,38,40,41,42,46,81]
        if lost or added:geometry.append(dict(layer=layer,datatype=datatype,lost_um2=lost,added_um2=added))
    comparisons={}
    for net in ["VIN","VSS","IOUT"]:
        values=[]
        for n in networks:
            terminals=n[net]["terminal_to_anchor"]
            values.append(dict(max_DS_ohm=max(v["effective_ohm"] for v in terminals if v["pin"] in ["D","S"]),
                max_body_ohm=max((v["effective_ohm"] for v in terminals if v["pin"]=="B"),default=None)))
        comparisons[net]=dict(thin=values[0],pg=values[1],
            DS_reduction_percent=100*(1-values[1]["max_DS_ohm"]/values[0]["max_DS_ohm"]))
    metrics=[]
    for f,c in zip(folders,contracts):
        correction=json.loads((f/"capacitance-correction.json").read_text())
        audit=json.loads((f/"pex-audit.json").read_text())
        metrics.append(dict(module=str(f.relative_to(ROOT)),gds_sha256=c["gds_sha256"],
            rc_sha256=audit["full_rc_sha256"],counts=audit["counts"],area_um2=c["area_um2"],
            width_um=c["width_um"],height_um=c["height_um"],
            capacitance_fF=correction["authoritative_total_sum_fF"]))
    result=dict(schema_version=1,passed=True,identical_MOS_and_placement=True,identical_independent_schematic=True,
        all_original_manufacturing_polygons_retained=True,only_additional_routing_layers_changed=True,
        layer_changes=geometry,port_text_metadata_changes=metadata,terminal_path_comparison=comparisons,runs=metrics,
        area_change_percent=100*(metrics[1]["area_um2"]/metrics[0]["area_um2"]-1),
        capacitance_change_percent=100*(metrics[1]["capacitance_fF"]/metrics[0]["capacitance_fF"]-1),
        limits=["Body return includes unchanged well/substrate graph; metal improvement is not body-field validation.",
                "Only these two 10MOS runs establish the single-variable layout comparison.",
                "Earlier 19MOS module has different circuitry and is not an area optimization baseline."])
    (ROOT/a.out).write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({key:result[key] for key in ["passed","area_change_percent","capacitance_change_percent"]}))


if __name__=="__main__":main()
