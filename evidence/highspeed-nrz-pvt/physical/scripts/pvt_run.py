"""Isolated physical implementation of selected NRZ PVT circuit candidates.

This wrapper reuses the pinned, reviewed public-PCell routing/extraction code,
without modifying either its sources or its October 20 artifacts.  Physical
connectivity is supplied independently of the electrical SPICE reference.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import math
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / "scripts/highspeed_nrz_layout"
sys.path.insert(0, str(LEGACY))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


# The imported audit/correction modules use `import run`.  In this isolated
# process it must resolve to the legacy EDA utility module, never this CLI.
flow = module("run", LEGACY / "run.py")
generator = module("pvt_legacy_generator", LEGACY / "generate.py")
audit = module("audit", Path(__file__).with_name("audit.py"))
correction = module("pvt_capacitance_correction", Path(__file__).with_name("correct_capacitance.py"))
_ext_matrix = correction.ext_matrix


def compact_body_nodes(path):
    """Magic records a resistor marker node in addition to its three terminals."""
    found = []
    for line in Path(path).read_text().splitlines():
        if line.startswith("device rsubckt ppolyf_u_1k_6p0 "):
            quoted = re.findall(r'"([^"]+)"', line)
            assert len(quoted) == 4, line
            found.append(quoted[1])
    return found


def electrical_ext_matrix(path):
    nodes, substrate, couplings, matrix = _ext_matrix(path)
    for name in compact_body_nodes(path):
        assert nodes[name] == 0
        assert not any(name in (a,b) for a,b,_ in couplings)
        del nodes[name]
        key=tuple(sorted((name,substrate)))
        assert matrix.pop(key) == 0
    return nodes,substrate,couplings,matrix


correction.ext_matrix = electrical_ext_matrix


def force_pex(base, out, c):
    """Expand every physical electrical net; compact resistor marker is not a net.

    The resistor body has its PDK compact X model. Magic's extra unconnected
    marker branch would otherwise produce a floating R in parallel with no
    terminal. Ignore only that documented, zero-C device marker at extraction,
    retaining every interconnect R and the complete compact resistor model.
    """
    if not c.get("resistors"):
        return flow.force_pex(base,out,c)
    out.mkdir()
    top=c["top"]
    original_path=base/(top+".ext")
    original=original_path.read_text()
    excluded=compact_body_nodes(original_path)
    assert len(excluded)==len(c["resistors"])
    nodes=[];lines=[]
    for line in original.splitlines():
        lines.append(line)
        m=re.match(r'^node "([^"]+)" \S+ (\S+) (\S+) (\S+) (\S+)',line)
        if m:
            n,cap,x,y,layer=m.groups()
            if n in excluded:
                assert float(cap)==0
                continue
            assert n in c["buses_um"],n
            nodes.append(dict(node=n,x=int(x),y=int(y),layer=layer))
            lines.append(f'attr "{n}" {x} {y} {int(x)+1} {int(y)+1} {layer} "res:drive"')
    annotated="\n".join(lines)+"\n"
    shutil.copyfile(base/(top+".mag"),out/(top+".mag"))
    (out/(top+".ext")).write_text(annotated)
    flow.write(out/"drive-attributes.json",dict(nodes=nodes,node_count=len(nodes),
        geometry_mutated=False,original_ext_sha256=flow.sha(original_path),
        annotated_ext_sha256=flow.sha(out/(top+".ext")),
        excluded_compact_resistor_body_nodes=excluded))
    tcl=out/"extract-driven.tcl"
    commands=["load "+top,"select top cell","extract style ngspice()",
              "extresist threshold 0","extresist minres 0","extresist mindelay 0"]
    commands += ['extresist ignore {'+n+'}' for n in excluded]
    commands += ["extresist all","ext2spice lvs","ext2spice cthresh 0",
                 "ext2spice rthresh 0","ext2spice extresist on",
                 "ext2spice -o "+top+"_rc.spice","quit -noprompt"]
    tcl.write_text("\n".join(commands)+"\n")
    text=flow.magic(tcl,out)
    result=dict(node_count=len(nodes), extracted_nodes=re.findall(r"^Extracting (\S+)\s*$",text,re.M),
        extraction_statistics=re.findall(r"Nets extracted:\s*(\d+)\s*\(([^)]+)\)",text),
        excluded_compact_resistor_body_nodes=excluded,
        exclusion_reason="Nonterminal resistor device marker; zero .ext C; PDK X resistor retained",
        only_attributes_added="\n".join(x for x in annotated.splitlines()
            if not(x.startswith('attr ') and '"res:drive"' in x))+"\n"==original)
    assert set(result["extracted_nodes"])==set(c["buses_um"]),result
    flow.write(out/"coverage.json",result)
    return result


def gold(route, folder, definition):
    """Normalize independent electrical source; never read physical devices."""
    source = ROOT / definition["schematic_source"]
    text = re.sub(r"\n\+\s*", " ", source.read_text())
    lines = ["* Independent electrical reference: " + str(source.relative_to(ROOT)),
             ".subckt " + definition["top"] + " " + " ".join(definition["ports"])]
    for line in text.splitlines():
        tokens = line.split()
        if not tokens or tokens[0].startswith("*"):
            continue
        if tokens[0][0].upper() == "X":
            is_resistor = tokens[4] == "ppolyf_u_1k_6p0"
            assert is_resistor or tokens[5] in ("nfet_03v3", "pfet_03v3"), tokens
            params = dict(re.findall(r"(\w+)=([^\s]+)", line))
            keys = ("r_width", "r_length") if is_resistor else ("w", "l")
            assert "{" not in "".join(params[key] for key in keys), "Resolve W/L explicitly in selected source"
            for key in keys:
                assert audit.number(params[key]) > 0
            mi = 4 if is_resistor else 5
            lines.append(" ".join([tokens[0].upper()] + [n.upper() for n in tokens[1:mi]] +
                                  [tokens[mi]] + [key+"="+params[key] for key in keys]))
        elif tokens[0][0].upper() in ("R", "C", "L", "V", "I", "B", "M", "D"):
            raise ValueError("Core source must contain only supported X MOS devices: " + line)
    assert len(lines) > 2
    lines.append(".ends " + definition["top"])
    target = folder / "schematic.spice"
    target.write_text("\n".join(lines) + "\n")
    return source, target


def generate(route, definition, output):
    resistors = definition.get("resistors", [])
    assert len(resistors) <= 1, "One input conditioning resistor supported"
    input_node = resistors[0]["nodes"][1] if resistors else "DATA"
    inner_ports = [input_node if n == "DATA" else n for n in definition["ports"]]
    generator.OUT = output
    generator.TOPS = {route: definition["top"]}
    generator.PORTS = {route: inner_ports}
    generator.PLACEMENT = {route: [
        (d["name"], d["polarity"], d["w_um"], d["l_um"], " ".join(d["nodes"]))
        for d in definition["devices"]]}
    generator.gold = lambda r, folder: gold(r, folder, definition)
    c = generator.make(route)
    c["resistors"] = resistors
    if resistors:
        append_input_resistor(c, output / route / "generate.tcl", resistors[0])
    c["external_components"] = definition.get("external_components", [])
    c["dimension_change"] = definition.get("dimension_change", [])
    c["design_changes"] = definition.get("design_changes", [])
    c["electrical_physical_independence"] = (
        "Physical D/G/S/B is hand-authored in selected specification; LVS gold is independently "
        "read from selected SPICE. No netlist-to-placement parser is used.")
    # The inherited bus-style router is deliberately simple. Fail instead of
    # pretending arbitrary fan-out/placement is automatically supported.
    assert max(v for n,v in c["buses_um"].items() if n != input_node) < 15, "Too many nets for fixed educational placement"
    flow.write(output / route / "contract.json", c)
    return c


def append_input_resistor(c, path, resistor):
    """Add a real public 6 V high-R-poly PCell and independently route its pins."""
    assert resistor["model"] == "ppolyf_u_1k_6p0"
    assert resistor["nodes"][0] == "DATA" and resistor["nodes"][2] == "VSS"
    width, length = resistor["r_width_um"], resistor["r_length_um"]
    assert width == 1, "Pinned pin-location derivation currently supports W=1 um"
    assert all(abs(x/.005-round(x/.005)) < 1e-8 for x in (width, length))
    top = c["top"]
    text = path.read_text()
    # The resistor is placed to the left of the MOS row. Its lower contact
    # drives DIN; its upper contact uses M4 to descend without shorting DIN.
    short_di = resistor.get("short_di", False)
    x, y = (-5., 22.5-length/2-.43) if short_di else (-5., length/2+2.43)
    lo, hi = y-length/2-.43, y+length/2+.43
    by = y
    bx = x-1.38
    data_pin,di_pin = (lo,hi) if short_di else (hi,lo)
    resistor.update(cx=x, cy=y, pins_um={"1":[x,data_pin], "2":[x,di_pin], "B":[bx,by]})
    guard_options = " gtc 1 gbc 1" if resistor.get("guard_all_sides") else ""
    insertion = ["load pcell_RIN", "box values 0 0 0 0",
        f"gf180mcu::ppolyf_u_1k_6p0_draw [dict merge [gf180mcu::ppolyf_u_1k_6p0_defaults] [dict create w {width} l {length} full_metal 1{guard_options}]]",
        "save pcell_RIN", "load assembly",
        f"getcell pcell_RIN child 0 0 parent {x}um {y}um"]
    marker = "select top cell\nflatten -nolabels " + top
    text = text.replace(marker, "\n".join(insertion)+"\n"+marker)
    din = resistor["nodes"][1]
    # Keep the inherited DIN bus but expose DATA as physical port 1 instead.
    old_port = "label "+din+" center metal3\nport make 1"
    assert old_port in text
    text = text.replace(old_port, "label "+din+" center metal3")
    if short_di:
        old_bus=c["buses_um"][din]
        new_bus=22.5
        text=re.sub(r"box values[^\n]+\nlabel "+re.escape(din)+r" center metal3\n","",text)
        for r in c["routes"]:
            if r["net"]!=din or r["layer"] not in ("metal3","metal4"):
                continue
            old="rect "+r["layer"]+" "+" ".join(map(str,r["rect_um"]))
            if r["layer"]=="metal3":
                r["rect_um"][1]=new_bus-.2;r["rect_um"][3]=new_bus+.2
            else:
                px=(r["rect_um"][0]+r["rect_um"][2])/2
                device=next(d for d in c["devices"] if d["nodes"][1]==din and d["cx"]==px)
                py=device["pins_um"]["G"][1]
                r["rect_um"][1]=min(py,new_bus)-.19
                r["rect_um"][3]=max(py,new_bus)+.19
                text=text.replace(f"via metal3 metal4 via3 {device['cx']} {old_bus}",
                                  f"via metal3 metal4 via3 {device['cx']} {new_bus}")
            r["rect_um"]=[round(z,6) for z in r["rect_um"]]
            new="rect "+r["layer"]+" "+" ".join(map(str,r["rect_um"]))
            assert old in text,old
            text=text.replace(old,new)
        c["buses_um"][din]=new_bus
    data_y = data_pin-1 if short_di else 1 + 1.2*len(c["buses_um"])
    c["buses_um"]["DATA"] = data_y
    c["bus_spans_um"]["DATA"] = [x-.5, x+.5]
    c["port_anchor_um"].pop(din)
    c["port_anchor_um"]["DATA"] = [x-.3, data_y]
    c["ports"][0] = "DATA"
    additions = []
    def rect(net, layer, x1,y1,x2,y2):
        coords = [round(z,6) for z in (x1,y1,x2,y2)]
        assert all(abs(z/.005-round(z/.005)) < 1e-6 for z in coords)
        additions.append("rect "+layer+" "+" ".join(map(str,coords)))
        c["routes"].append(dict(net=net,layer=layer,rect_um=coords))
    for node, pin_x in ((din,x),("VSS",bx)):
        bus_y=c["buses_um"][node]
        old=c["bus_spans_um"][node]
        rect(node,"metal3",pin_x-.5,bus_y-.2,old[1],bus_y+.2)
        old[0]=pin_x-.5
    rect("DATA","metal3",x-.5,data_y-.2,x+.5,data_y+.2)
    additions += [f"box values {x-.4}um {data_y-.1}um {x-.2}um {data_y+.1}um",
                  "label DATA center metal3", "port make 1"]
    if short_di:
        additions += [f"box values 3.6um {c['buses_um'][din]-.1}um 3.8um {c['buses_um'][din]+.1}um",
                      "label "+din+" center metal3"]
    for node,px,py in (("DATA",x,data_pin),(din,x,di_pin),("VSS",bx,by)):
        additions.append(f"via metal1 metal2 via1 {px} {py}")
        bus_y=c["buses_um"][node]
        if node=="DATA" and not short_di:
            additions += [f"via metal2 metal3 via2 {px} {py}",f"via metal3 metal4 via3 {px} {py}"]
            rect(node,"metal4",px-.19,bus_y-.19,px+.19,py+.19)
            additions.append(f"via metal3 metal4 via3 {px} {bus_y}")
        else:
            rect(node,"metal2",px-.19,min(py,bus_y)-.19,px+.19,max(py,bus_y)+.19)
            additions.append(f"via metal2 metal3 via2 {px} {bus_y}")
    if resistor.get("substrate_screen"):
        # A continuous p+ substrate contact strip between the resistor and
        # MOS row.  Contact geometry follows the same public PCell dimensions.
        tx=0.
        bottom=min(lo,0)-2
        upper=max(hi,27)+2
        rect("VSS","pwell",tx-.3,bottom-.12,tx+.3,upper+.12)
        rect("VSS","psd",tx-.18,bottom,tx+.18,upper)
        rect("VSS","psc",tx-.115,bottom+.065,tx+.115,upper-.065)
        rect("VSS","metal1",tx-.19,bottom+.065,tx+.19,upper-.065)
        rect("VSS","metal2",tx-.19,bottom+.065,tx+.19,upper-.065)
        for yy in [round(bottom+1+5*i,3) for i in range(int((upper-bottom-2)/5)+1)]:
            additions.append(f"via metal1 metal2 via1 {tx} {yy}")
        additions.append(f"via metal2 metal3 via2 {tx} {c['buses_um']['VSS']}")
        resistor["substrate_screen_geometry"]={"center_x_um":tx,"bottom_um":bottom,"top_um":upper,
            "diffusion_width_um":.36,"contact_width_um":.23,"metal_width_um":.38}
    marker="select top cell\ndrc style drc(full)"
    assert marker in text
    path.write_text(text.replace(marker,"\n".join(additions)+"\n"+marker))


def geometry_audit(out):
    """Independently measure channel/diffusion polygons from actual final GDS."""
    k = audit.k
    c = json.loads((out / "physical-contract.json").read_text())
    layout = k.Layout()
    layout.read(str(out / "generate" / (c["top"] + ".gds")))
    cell = layout.cell(c["top"])
    active = k.Region(cell.begin_shapes_rec(layout.layer(22, 0)))
    poly = k.Region(cell.begin_shapes_rec(layout.layer(30, 0)))
    results = []
    for d in c["devices"]:
        x, y, w, length = d["cx"], d["cy"], d["w_um"], d["l_um"]
        window = k.Region(k.DBox(x-length/2-.5, y-w/2-.01,
                                 x+length/2+.5, y+w/2+.01).to_itype(layout.dbu))
        isolated_active = (active & window).merged()
        channel = (isolated_active & poly).merged()
        diffusion = (isolated_active - poly).merged()
        channel_boxes = [p.bbox() for p in channel.each()]
        areas = sorted(p.area()*layout.dbu**2 for p in diffusion.each())
        perimeters = sorted(p.perimeter()*layout.dbu for p in diffusion.each())
        assert len(channel_boxes) == 1 and len(areas) == 2, d["name"]
        box = channel_boxes[0]
        actual_l, actual_w = box.width()*layout.dbu, box.height()*layout.dbu
        assert math.isclose(actual_l, length, abs_tol=1e-12)
        assert math.isclose(actual_w, w, abs_tol=1e-12)
        assert all(math.isclose(a, .44*w, abs_tol=1e-10) for a in areas)
        assert all(math.isclose(p, 2*(w+.44), abs_tol=1e-10) for p in perimeters)
        mapping = next(m for m in c["extracted_device_mapping"]
                       if m["original_instance"] == "X"+d["name"])
        p = mapping["params_si"]
        assert all(math.isclose(p[n]*1e12, a, abs_tol=1e-9)
                   for n,a in zip(("ad", "as"), areas))
        assert all(math.isclose(p[n]*1e6, a, abs_tol=1e-9)
                   for n,a in zip(("pd", "ps"), perimeters))
        results.append(dict(device=d["name"], w_um=actual_w, l_um=actual_l,
                            diffusion_areas_um2=areas, diffusion_perimeters_um=perimeters,
                            extracted_geometry_matches=True))
    resistor_results=[]
    marker=k.Region(cell.begin_shapes_rec(layout.layer(110,5)))
    for d in c.get("resistors",[]):
        x,y=d["cx"],d["cy"]
        window=k.Region(k.DBox(x-1,y-d["r_length_um"]/2-.1,
                              x+1,y+d["r_length_um"]/2+.1).to_itype(layout.dbu))
        body=(marker & poly & window).merged()
        polygons=list(body.each())
        assert len(polygons)==1
        box=polygons[0].bbox()
        w,l=box.width()*layout.dbu,box.height()*layout.dbu
        assert math.isclose(w,d["r_width_um"],abs_tol=1e-12)
        assert math.isclose(l,d["r_length_um"],abs_tol=1e-12)
        resistor_results.append(dict(device=d["name"],w_um=w,l_um=l,
            method="Intersection of actual GDS HRPOLY 110/5 and POLY 30/0"))
    result = dict(passed=True, gds_sha256=c["gds_sha256"], devices=results,
                  device_resistors=resistor_results,
                  method="Boolean intersection/difference of final GDS active and poly polygons; "
                         "isolated channel window excludes surrounding body contacts.")
    flow.write(out / "gds-geometry-audit.json", result)
    return result


def negative_controls(out):
    """Edit actual GDS; verify shape changes and require LVS rejection."""
    k = audit.k
    c = json.loads((out / "source/contract.json").read_text())
    results = []
    for mode in ("input-gate-open", "vdd-vss-short"):
        dest = out / "controls" / mode
        dest.mkdir(parents=True)
        layout = k.Layout()
        layout.read(str(out / "generate" / (c["top"] + ".gds")))
        cell = layout.cell(c["top"])
        if mode == "input-gate-open":
            input_net = c.get("resistors",[{}])[0].get("nodes",["DATA","DATA"])[1] if c.get("resistors") else "DATA"
            d = next(d for d in c["devices"] if d["nodes"][1] == input_net)
            x = d["cx"]
            y = round((c["buses_um"][input_net] + d["pins_um"]["G"][1])/2 / .005)*.005
            rect = [x-.3, y-.3, x+.3, y+.3]
            layer = layout.layer(46, 0)
            original = k.Region(cell.shapes(layer))
            mutated = original - k.Region(k.DBox(*rect).to_itype(layout.dbu))
        else:
            lo = max(c["bus_spans_um"][n][0] for n in ("VDD", "VSS"))
            hi = min(c["bus_spans_um"][n][1] for n in ("VDD", "VSS"))
            assert hi-lo > .4
            x = round((lo+hi)/2 / .005)*.005
            ys = [c["buses_um"][n] for n in ("VDD", "VSS")]
            rect = [x-.2, min(ys)-.2, x+.2, max(ys)+.2]
            layer = layout.layer(42, 0)
            original = k.Region(cell.shapes(layer))
            mutated = original | k.Region(k.DBox(*rect).to_itype(layout.dbu))
        delta = (original ^ mutated).area()*layout.dbu**2
        assert delta > 0, "Negative control must alter actual GDS polygons"
        cell.shapes(layer).clear()
        cell.shapes(layer).insert(mutated)
        gds = dest / (c["top"] + ".gds")
        layout.write(str(gds))
        drc = flow.extract(gds, c, dest / "extract", False)
        lvs = flow.lvs(dest/"extract"/(c["top"]+".spice"),
                       out/"source/schematic.spice", c["top"], dest)
        assert not lvs["passed"], mode
        results.append(dict(control=mode, passed=True, expected_lvs_match=False,
                            gds_sha256=flow.sha(gds), edit_rect_um=rect,
                            changed_polygon_area_um2=delta, drc=drc, lvs=lvs))
    flow.write(out / "negative-controls.json", results)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, help="Selected circuit and independent placement JSON")
    parser.add_argument("--run", required=True)
    parser.add_argument("--skip-klayout", action="store_true", help="Exploration only; no completed physical claim")
    args = parser.parse_args()
    specification = json.loads((ROOT / args.spec).read_text())
    target = ROOT / "build/highspeed-nrz-pvt-layout" / args.run
    target.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(ROOT / args.spec, target / "selected-spec.json")
    sources = [Path(__file__),Path(__file__).with_name("audit.py"),Path(__file__).with_name("correct_capacitance.py")] + [LEGACY / n for n in
               ("generate.py", "run.py", "audit.py", "correct_capacitance.py")]
    snapshot = target / "source_scripts"
    snapshot.mkdir()
    for src in sources:
        shutil.copyfile(src, snapshot / ("pvt_"+src.name if src.parent == Path(__file__).parent else src.name))
    lock = json.loads((ROOT / "layout/pdk-lock.json").read_text())
    for name, expected in lock["files"].items():
        assert flow.sha(flow.PDK / "gf180mcuD" / name) == expected, name
    status = {}
    for route, definition in specification["routes"].items():
        c = generate(route, definition, target / "sources")
        out = target / route
        out.mkdir()
        shutil.copytree(target / "sources" / route, out / "source")
        shutil.copyfile(ROOT / definition["schematic_source"], out / "selected-electrical-source.spice")
        gen = out / "generate"
        gen.mkdir()
        text = flow.magic(out / "source/generate.tcl", gen)
        counts = re.findall(r"NRZ_DRC_COUNT (\d+)", text)
        result = dict(magic_drc=dict(passed=counts == ["0"], counts=counts))
        status[route] = result
        flow.write(target / "status.json", status)
        assert result["magic_drc"]["passed"], route + " generated DRC"
        top = c["top"]
        gds = gen / (top+".gds")
        result["lvs"] = flow.lvs(gen/(top+".spice"), out/"source/schematic.spice", top, out)
        assert result["lvs"]["passed"], route + " native LVS"
        result["readback_drc"] = flow.extract(gds, c, out / "readback", True)
        result["readback_lvs"] = flow.lvs(out/"readback"/(top+".spice"),
                                          out/"source/schematic.spice", top, out, "readback-lvs")
        assert result["readback_drc"]["passed"] and result["readback_lvs"]["passed"]
        result["pex_coverage"] = force_pex(out / "readback", out / "full-rc", c)
        flow.write(target / "status.json", status)
        if not args.skip_klayout:
            result["klayout_drc"] = flow.klayout_drc(gds, c, out)
            assert result["klayout_drc"]["passed"]
        correction.correct(out)
        result["pex_audit"] = {key: value for key, value in audit.audit(out).items()
                               if key in ("passed", "counts", "all_nets_extracted", "full_rc_sha256")}
        result["gds_geometry"] = geometry_audit(out)
        result["negative_controls"] = negative_controls(out)
        flow.write(target / "status.json", status)
        print(route, json.dumps(result), flush=True)
    flow.write(target / "correction-provenance.json", dict(
        method="In-place new-run assembly with unmodified-full-rc retained alongside corrected model",
        original_october20_run_untouched=True, legacy_sources_unchanged=True,
        sources={str(p.relative_to(ROOT)): flow.sha(p) for p in sources}))
    files = sorted(p for p in target.rglob("*") if p.is_file())
    flow.write(target / "artifact-manifest.json", dict(
        schema_version=1, physical_pdk_lock=lock,
        tools={str(p.relative_to(ROOT)): flow.sha(p) for p in (flow.TOOLS/"magic", flow.TOOLS/"netgen")},
        artifacts=[dict(path=str(p.relative_to(target)), size=p.stat().st_size,
                        sha256=flow.sha(p)) for p in files]))
    print(target, flush=True)


if __name__ == "__main__":
    main()
