"""Compose actual verified GDS macros with extracted intermodule metal wiring.

Independent electrical sources are renamed/flattened separately from the
physical contracts. Original core polygons remain intact up to translation;
shared logical nets receive ONE label only, so a missing bridge cannot be
hidden by duplicate disconnected labels. Every signal bridge has a GDS-open
negative control.
"""
from pathlib import Path
import argparse
import copy
import importlib.util
import json
import re
import shutil
import sys

module_spec = importlib.util.spec_from_file_location("reference_module_runner", Path(__file__).with_name("run.py"))
physical = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = physical
module_spec.loader.exec_module(physical)

ROOT = physical.ROOT
helpers, flow = physical.helpers, physical.flow


def create_inputs(specification, target):
    source = target/"source"
    source.mkdir()
    top = specification["top"]
    ports = specification["ports"]
    devices, resistors, routes, modules = [], [], [], []
    buses, spans, anchors, original_anchors = {}, {}, {}, {}
    labels = {}
    gold = ["* Independently composed frozen electrical sources; no physical netlist parsing.",
            ".subckt "+top+" "+" ".join(ports)]
    tcl = ["proc rect {layer x1 y1 x2 y2} {",
           "box values ${x1}um ${y1}um ${x2}um ${y2}um", "paint $layer", "}",
           "proc via3at {x y} {",
           "rect metal3 [expr {$x-.19}] [expr {$y-.19}] [expr {$x+.19}] [expr {$y+.19}]",
           "rect metal4 [expr {$x-.19}] [expr {$y-.19}] [expr {$x+.19}] [expr {$y+.19}]",
           "rect via3 [expr {$x-.14}] [expr {$y-.14}] [expr {$x+.14}] [expr {$y+.14}]", "}",
           "proc via4at {x y} {",
           "rect metal4 [expr {$x-.19}] [expr {$y-.19}] [expr {$x+.19}] [expr {$y+.19}]",
           "rect metal5 [expr {$x-.5}] [expr {$y-.5}] [expr {$x+.5}] [expr {$y+.5}]",
           "rect via4 [expr {$x-.14}] [expr {$y-.14}] [expr {$x+.14}] [expr {$y+.14}]", "}"]
    for m in specification["modules"]:
        folder = ROOT/m["folder"]
        c = json.loads((folder/"physical-contract.json").read_text())
        srcgds = folder/"generate"/(c["top"]+".gds")
        assert flow.sha(srcgds) == c["gds_sha256"]
        x,y = m["offset_um"]
        mapping = m["node_map"]
        remap = lambda n: mapping.get(n,n)
        tag = m["tag"]
        gds = source/(tag+".gds")
        shutil.copyfile(srcgds,gds)
        shutil.copyfile(folder/"physical-contract.json",source/(tag+"-physical-contract.json"))
        electrical = ROOT/m["electrical_source"]
        shutil.copyfile(electrical,source/(tag+"-electrical.spice"))
        for line in re.sub(r"\n\+\s*"," ",electrical.read_text()).splitlines():
            t = line.split()
            if not t or t[0].startswith("*") or t[0].startswith("."):
                continue
            assert t[0].upper().startswith("X"), line
            device_index = 4 if t[4] == "ppolyf_u_1k_6p0" else 5
            assert t[device_index] in ["ppolyf_u_1k_6p0","nfet_03v3","pfet_03v3","nfet_06v0","pfet_06v0"]
            keys = ["r_width","r_length"] if device_index == 4 else ["w","l"]
            params = dict(re.findall(r"(\w+)=([^\s]+)",line))
            gold.append(" ".join(["X"+tag+"_"+t[0][1:]] +
                [remap(n.upper()) for n in t[1:device_index]] + [t[device_index]] +
                [key+"="+params[key] for key in keys]))
        for d in c["devices"]:
            d = copy.deepcopy(d)
            d["name"] = tag+"_"+d["name"]
            d["nodes"] = [remap(n) for n in d["nodes"]]
            d["cx"] += x; d["cy"] += y
            d["pins_um"] = {p:[v[0]+x,v[1]+y] for p,v in d["pins_um"].items()}
            devices.append(d)
        for r in c.get("resistors",[]):
            r = copy.deepcopy(r)
            r["name"] = tag+"_"+r["name"]
            r["nodes"] = [remap(n) for n in r["nodes"]]
            r["cx"] += x; r["cy"] += y
            r["pins_um"] = {p:[v[0]+x,v[1]+y] for p,v in r["pins_um"].items()}
            resistors.append(r)
        for net, by in c["buses_um"].items():
            named = remap(net)
            span = [v+x for v in c["bus_spans_um"][net]]
            point = [span[0]+.2,by+y]
            if net in c["port_anchor_um"]:
                point = [c["port_anchor_um"][net][0]+x,c["port_anchor_um"][net][1]+y]
            original_anchors[tag+":"+net] = point
            # Last component has priority; one label for each merged net.
            buses[named],spans[named],labels[named] = by+y,span,point
            if named in ports:
                anchors[named] = point
        for r in c["routes"]:
            r = copy.deepcopy(r)
            r["net"] = remap(r["net"])
            r["rect_um"] = [v+(x if i%2==0 else y) for i,v in enumerate(r["rect_um"])]
            routes.append(r)
        modules.append(dict(tag=tag,top=c["top"],input_folder=m["folder"],
            offset_um=[x,y],gds_sha256=flow.sha(gds),electrical_source=m["electrical_source"],
            electrical_source_sha256=flow.sha(electrical),node_map=mapping))
        tcl.append("gds read "+str(gds))
    tcl.append("load reference_joint_assembly")
    for m in modules:
        x,y=m["offset_um"]
        tcl.append(f"getcell {m['top']} child 0 0 parent {x}um {y}um")
    tcl += ["select top cell","flatten -nolabels "+top,"load "+top]
    bridges = []
    for bridge in specification["bridges"]:
        a,b = [[p[0]+delta[0],p[1]+delta[1]] for p,delta in zip(
            [original_anchors[q] for q in bridge["anchors"]],
            bridge.get("endpoint_offsets_um", [[0,0],[0,0]]))]
        corridor = bridge["corridor_y_um"]
        net = bridge["net"]
        m4w = bridge.get("vertical_width_um", .38)
        m5w = bridge.get("horizontal_width_um", 1.)
        offsets = [-.6,0,.6] if m4w >= 1.6 else [0]
        for x,y in [a,b]:
            tcl += [f"rect metal3 {x-m4w/2} {y-.19} {x+m4w/2} {y+.19}",
                    f"rect metal4 {x-m4w/2} {min(y,corridor)-.19} {x+m4w/2} {max(y,corridor)+.19}"]
            for dx in offsets:
                tcl += [f"via3at {x+dx} {y}", f"via4at {x+dx} {corridor}"]
            routes.append(dict(net=net,layer="metal4",rect_um=[x-m4w/2,min(y,corridor)-.19,x+m4w/2,max(y,corridor)+.19]))
        rectangle = [min(a[0],b[0])-m5w/2,corridor-m5w/2,max(a[0],b[0])+m5w/2,corridor+m5w/2]
        tcl.append("rect metal5 "+" ".join(map(str,rectangle)))
        routes.append(dict(net=net,layer="metal5",rect_um=rectangle))
        bridges.append(bridge|dict(anchor_points_um=[a,b],horizontal_metal5_rect_um=rectangle,
                                   vertical_width_um=m4w,horizontal_width_um=m5w,via_array_cuts=len(offsets),
                                   source_to_destination_real_GDS_wiring=True))
    for net, (x,y) in labels.items():
        tcl += [f"box values {x-.1}um {y-.1}um {x+.1}um {y+.1}um",f"label {net} center metal3"]
        if net in ports:
            tcl.append("port make "+str(ports.index(net)+1))
    tcl += ["select top cell","drc style drc(full)","drc check","drc catchup",
            'puts "NRZ_DRC_COUNT [drc list count total]"','puts "NRZ_DRC_ERRORS [drc listall why]"',
            "save "+top,"extract all","ext2spice lvs","ext2spice","gds write "+top+".gds","quit -noprompt"]
    gold.append(".ends "+top)
    (source/"schematic.spice").write_text("\n".join(gold)+"\n")
    (source/"generate.tcl").write_text("\n".join(tcl)+"\n")
    contract=dict(schema_version=1,route="J",top=top,ports=ports,grid_um=.005,
        devices=devices,resistors=resistors,buses_um=buses,bus_spans_um=spans,
        port_anchor_um=anchors,routes=routes,external_components=specification["external_components"],
        dimension_change=[],design_changes=["Verified module/core GDS composed with real Metal4/Metal5 intermodule routing"],
        modules=modules,intermodule_bridges=bridges,negative_control_gate="VSET",supply_port="VIN",
        source_sha256={str((source/"schematic.spice").relative_to(ROOT)):flow.sha(source/"schematic.spice")},
        electrical_physical_independence="Independent frozen electrical source flattening versus actual verified GDS/physical contracts; shared nodes named once.")
    assert set(ports) <= set(anchors)
    flow.write(source/"contract.json",contract)
    return contract


def bridge_negative_controls(out,c):
    k = helpers.audit.k
    result=[]
    for bridge in c["intermodule_bridges"]:
        # VSS is also connected by the shared physical substrate. Cutting a
        # metal return alone need not cause topological LVS failure.
        if bridge["net"] == "VSS":
            continue
        name="bridge-"+bridge["net"]+"-open"
        folder=out/"controls"/name
        folder.mkdir(parents=True)
        lay=k.Layout();lay.read(str(out/"generate"/(c["top"]+".gds")))
        cell=lay.cell(c["top"])
        x0,y0,x1,y1=bridge["horizontal_metal5_rect_um"]
        x=round((x0+x1)/2/.005)*.005
        cut=[x-.5,y0-.2,x+.5,y1+.2]
        li=lay.layer(81,0)
        before=k.Region(cell.shapes(li))
        after=before-k.Region(k.DBox(*cut).to_itype(lay.dbu))
        delta=(before^after).area()*lay.dbu**2
        assert delta>0
        cell.shapes(li).clear();cell.shapes(li).insert(after)
        gds=folder/(c["top"]+".gds");lay.write(str(gds))
        drc=flow.extract(gds,c,folder/"extract",False)
        lvs=flow.lvs(folder/"extract"/(c["top"]+".spice"),out/"source/schematic.spice",c["top"],folder)
        assert not lvs["passed"],"Physical bridge opening must be visible to independent LVS"
        result.append(dict(control=name,passed=True,expected_lvs_match=False,gds_sha256=flow.sha(gds),
            edit_rect_um=cut,changed_polygon_area_um2=delta,drc=drc,lvs=lvs))
    return result


def macro_geometry_preservation(out,c):
    """Every source polygon survives the stated translation into final GDS."""
    k=helpers.audit.k
    final=k.Layout();final.read(str(out/"generate"/(c["top"]+".gds")))
    top=final.cell(c["top"])
    results=[]
    for m in c["modules"]:
        original=k.Layout();original.read(str(out/"source"/(m["tag"]+".gds")))
        assert original.dbu==final.dbu
        cell=original.cell(m["top"])
        x,y=m["offset_um"]
        trans=k.Trans(round(x/final.dbu),round(y/final.dbu))
        area=lost=0.
        for idx in original.layer_indexes():
            info=original.get_info(idx)
            if info.datatype==10:
                continue  # Port/text purpose is re-authored at top level.
            source=k.Region(cell.begin_shapes_rec(idx)).transformed(trans)
            result=k.Region(top.begin_shapes_rec(final.layer(info)))
            area+=source.area()*final.dbu**2
            lost+=(source-result).area()*final.dbu**2
        assert area>0 and lost==0
        results.append(dict(tag=m["tag"],input_gds_sha256=m["gds_sha256"],
                            original_polygon_area_sum_um2=area,lost_polygon_area_um2=lost))
    value=dict(passed=True,method="Independent KLayout region difference on every manufacturing source layer after translation; "
               "routing can add polygons, but no original fabrication geometry may disappear. "
               "Datatype10 port/text metadata is re-authored at top level and excluded.",modules=results)
    flow.write(out/"macro-geometry-preservation.json",value)
    return value


def preserve_source_polygons(out,c):
    """Keep exact source fabrication polygons through Magic's GDS roundtrip.

    Pinned Magic clips 10nm N+ corner slivers during import/export. Reinsert
    only actual source polygons using KLayout, retain the roundtrip file, and
    then run all authoritative extraction/DRC from the preserved final GDS.
    No transistor or netlist parameters are adjusted to compensate.
    """
    k=helpers.audit.k
    gds=out/"generate"/(c["top"]+".gds")
    preliminary=gds.with_name(c["top"]+".magic-roundtrip.gds")
    shutil.copyfile(gds,preliminary)
    lay=k.Layout();lay.read(str(gds));cell=lay.cell(c["top"])
    additions=[]
    for m in c["modules"]:
        src=k.Layout();src.read(str(out/"source"/(m["tag"]+".gds")))
        tr=k.Trans(*[round(v/lay.dbu) for v in m["offset_um"]])
        for idx in src.layer_indexes():
            info=src.get_info(idx)
            if info.datatype==10:continue
            original=k.Region(src.cell(m["top"]).begin_shapes_rec(idx)).transformed(tr)
            dest=lay.layer(info)
            before=k.Region(cell.begin_shapes_rec(dest))
            missing=original-before
            if not missing.area():continue
            assert (info.layer,info.datatype)==(31,0), "Unexpected source geometry loss"
            cell.shapes(dest).insert(missing)
            additions.append(dict(module=m["tag"],layer=info.layer,datatype=info.datatype,
                                  restored_source_area_um2=missing.area()*lay.dbu**2))
    lay.write(str(gds))
    result=dict(method="Exact original source GDS polygon union, only documented N+ import/export corner losses; final file is re-extracted and independently checked.",
                preliminary_sha256=flow.sha(preliminary),final_sha256=flow.sha(gds),restorations=additions)
    flow.write(out/"gds-source-preservation.json",result)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--spec",required=True)
    parser.add_argument("--run",required=True)
    parser.add_argument("--prepare-only",action="store_true")
    args=parser.parse_args()
    target=ROOT/"build/reference-v2-layout"/args.run
    target.mkdir(parents=True,exist_ok=False)
    spec=json.loads((ROOT/args.spec).read_text())
    if "pending" in spec.get("status", ""):
        assert args.prepare_only, "Electrical topology is not frozen; only input preparation is allowed"
    lock=json.loads((ROOT/"layout/pdk-lock.json").read_text())
    for name,digest in lock["files"].items():
        assert flow.sha(flow.PDK/"gf180mcuD"/name)==digest
    flow.write(target/"selected-spec.json",spec)
    out=target/"J";out.mkdir()
    c=create_inputs(spec,out)
    if args.prepare_only:
        print("Prepared only; no physical verification claim:",target)
        return
    gen=out/"generate";gen.mkdir()
    text=flow.magic(out/"source/generate.tcl",gen)
    counts=re.findall(r"NRZ_DRC_COUNT (\d+)",text)
    s=dict(preliminary_magic_drc=dict(passed=counts==["0"],counts=counts))
    flow.write(target/"status.json",{"J":s})
    assert s["preliminary_magic_drc"]["passed"]
    top=c["top"];gds=gen/(top+".gds")
    s["gds_source_preservation"]=preserve_source_polygons(out,c)
    s["macro_geometry_preservation"]=macro_geometry_preservation(out,c)
    s["magic_drc"]=flow.extract(gds,c,out/"native",False)
    s["lvs"]=flow.lvs(out/"native"/(top+".spice"),out/"source/schematic.spice",top,out)
    assert s["magic_drc"]["passed"] and s["lvs"]["passed"]
    s["readback_drc"]=flow.extract(gds,c,out/"readback",True)
    s["readback_lvs"]=flow.lvs(out/"readback"/(top+".spice"),out/"source/schematic.spice",top,out,"readback-lvs")
    assert s["readback_drc"]["passed"] and s["readback_lvs"]["passed"]
    s["pex_coverage"]=helpers.force_pex(out/"readback",out/"full-rc",c)
    s["klayout_drc"]=flow.klayout_drc(gds,c,out)
    flow.write(target/"status.json",{"J":s})
    assert s["klayout_drc"]["passed"]
    helpers.correction.correct(out)
    s["pex_audit"]={k:v for k,v in helpers.audit.audit(out).items() if k in ("passed","counts","all_nets_extracted","full_rc_sha256")}
    actual=json.loads((out/"physical-contract.json").read_text())
    actual["routed_metal_layers"]=["Metal1","Metal2","Metal3","Metal4","Metal5"]
    for layer in actual["drawn_layers"]:
        if layer["gds_layer"]==81: layer["name"]="Metal5"
        if layer["gds_layer"]==41: layer["name"]="Via4"
    flow.write(out/"physical-contract.json",actual)
    s["gds_geometry"]=helpers.geometry_audit(out)
    controls=physical.negative_controls(out)+bridge_negative_controls(out,c)
    flow.write(out/"negative-controls.json",controls)
    s["negative_controls"]=controls
    flow.write(target/"status.json",{"J":s})
    scripts=[Path(__file__),Path(__file__).with_name("run.py"),
             Path(__file__).with_name("correct_capacitance.py"),
             Path(__file__).with_name("power_routes.py"),Path(__file__).with_name("generate.py"),
             physical.OLD/"run.py",physical.OLD/"audit.py",physical.OLD/"correct_capacitance.py",
             ROOT/"scripts/highspeed_nrz_layout/run.py"]
    (target/"source_scripts").mkdir()
    for i,p in enumerate(scripts):shutil.copyfile(p,target/"source_scripts"/f"{i}-{p.name}")
    flow.write(target/"correction-provenance.json",dict(
        method="Actual GDS macro composition; real intermodule metal; full extraction and C accounting after composition",
        old_core_sources_and_artifacts_unchanged=True,source_hashes={str(p.relative_to(ROOT)):flow.sha(p) for p in scripts}))
    files=sorted(p for p in target.rglob("*") if p.is_file())
    assert sum(p.stat().st_size for p in (ROOT/"build/reference-v2-layout").rglob("*") if p.is_file())<.5*1024**3
    flow.write(target/"artifact-manifest.json",dict(schema_version=1,
        physical_pdk_lock=json.loads((ROOT/"layout/pdk-lock.json").read_text()),
        artifacts=[dict(path=str(p.relative_to(target)),size=p.stat().st_size,sha256=flow.sha(p)) for p in files]))
    print(s["pex_audit"],target,flush=True)


if __name__=="__main__":main()
