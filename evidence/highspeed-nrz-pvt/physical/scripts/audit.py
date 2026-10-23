"""Audit full-RC topology, devices, junction geometry and physical LVS controls.

R collapse is an explicitly named control; raw full-RC is never overwritten.
No extracted capacitor or resistor is deleted from the main simulation model.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import klayout.db as k

sys.path.insert(0, str(Path(__file__).parent))
import run as flow

ROOT = flow.ROOT
LAYERS = {21: "N-well", 204: "P-well", 22: "Active", 30: "Poly",
          31: "P+ implant", 32: "N+ implant",
          33: "Contact", 34: "Metal1", 35: "Via1", 36: "Metal2",
          38: "Via2", 42: "Metal3", 40: "Via3", 46: "Metal4"}


def number(s):
    m = re.fullmatch(r"([-+0-9.eE]+)([A-Za-z]*)", s)
    factors = {"": 1, "f": 1e-15, "p": 1e-12, "n": 1e-9,
               "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6}
    return float(m[1]) * factors[m[2].lower()]


def audit(out):
    c = json.loads((out / "source/contract.json").read_text())
    top = c["top"]
    rc = out / "full-rc" / (top + "_rc.spice")
    text = rc.read_text()
    lines = re.sub(r"\n\+\s*", " ", text).splitlines()
    ports = next(l.split()[2:] for l in lines if l.lower().startswith(".subckt"))
    parent = {}

    def find(n):
        parent.setdefault(n, n)
        if parent[n] != n:
            parent[n] = find(parent[n])
        return parent[n]

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    resistors, capacitors, mos = [], [], []
    for line in lines:
        t = line.split()
        if not t:
            continue
        if t[0].startswith("R"):
            union(t[1], t[2])
            resistors.append(dict(name=t[0], nodes=t[1:3], ohm=number(t[3])))
        elif t[0].startswith("C"):
            capacitors.append(dict(name=t[0], nodes=t[1:3], farad=number(t[3])))
        elif t[0].startswith("X"):
            params = {name: number(value) for name, value in
                      re.findall(r"(\w+)=([^\s]+)", line)}
            mos.append(dict(name=t[0], nodes=t[1:5], model=t[5],
                            params_si=params, original_line=line))
    groups = {}
    for n in list(parent):
        groups.setdefault(find(n), []).append(n)
    known = set(c["buses_um"])
    canonical = {}
    for key, nodes in groups.items():
        names = [n for n in nodes if n in known]
        if len(names) != 1:
            raise RuntimeError(f"R network must map to exactly one logical net: {nodes}")
        canonical[key] = names[0]

    def logical(n):
        return canonical.get(find(n), n)

    mapping = []
    for d in c["devices"]:
        wanted = d["nodes"]
        matches = []
        for m in mos:
            actual = [logical(n) for n in m["nodes"]]
            p = m["params_si"]
            if (actual[1] == wanted[1] and actual[3] == wanted[3] and
                set(actual[::2]) == set(wanted[::2]) and m["model"] == d["model"] and
                math.isclose(p["w"], d["w_um"]*1e-6, rel_tol=1e-12) and
                math.isclose(p["l"], d["l_um"]*1e-6, rel_tol=1e-12)):
                matches.append(m)
        if len(matches) != 1:
            raise RuntimeError(f"Device mapping not unique: {d['name']}: {matches}")
        m = matches[0]
        p = m["params_si"]
        if p.get("m", 1) != 1 or p.get("nf", 1) != 1:
            raise RuntimeError("Unexpected extracted multiplicity/finger count")
        direct = logical(m["nodes"][0]) == wanted[0]
        terminal_indices = [0, 1, 2, 3] if direct else [2, 1, 0, 3]
        for a in ["ad", "as", "pd", "ps"]:
            if not (p[a] > 0 and math.isfinite(p[a])):
                raise RuntimeError("Invalid junction geometry: " + m["name"])
        # Isolated PCell diffusion: W x 0.44um, closed diffusion perimeter.
        if not (math.isclose(p["ad"], d["w_um"]*.44e-12, rel_tol=1e-9) and
                math.isclose(p["as"], d["w_um"]*.44e-12, rel_tol=1e-9) and
                math.isclose(p["pd"], 2*(d["w_um"]+.44)*1e-6, rel_tol=1e-9) and
                math.isclose(p["ps"], 2*(d["w_um"]+.44)*1e-6, rel_tol=1e-9)):
            raise RuntimeError("Junction geometry disagrees with isolated PCell: " + m["name"])
        mapping.append(dict(original_instance="X"+d["name"],
            extracted_instance=m["name"], original_nodes=dict(zip("DGSB", wanted)),
            rc_nodes=dict(zip("DGSB", [m["nodes"][i] for i in terminal_indices])),
            extracted_spice_nodes=dict(zip("DGSB", m["nodes"])),
            drain_source_swapped=not direct, params_si=p,
            multiplicity=1, fingers=1,
            cx_um=d["cx"], cy_um=d["cy"], pin_coordinate_um=d["pins_um"]))
    if len({m["extracted_instance"] for m in mapping}) != len(mos):
        raise RuntimeError("Not all extracted MOS mapped exactly once")
    # Produce same-geometry and same-C controls from this one raw full-RC deck.
    prefix = ["* Explicit control derived from full raw RC; original RC retained.",
              ".subckt " + top + " " + " ".join(ports)]
    mapped_mos = []
    for m in mos:
        t = m["original_line"].split()
        mapped_mos.append(" ".join([t[0]]+[logical(n) for n in t[1:5]]+t[5:]))
    geometry = out / "geometry-only.spice"
    geometry.write_text("\n".join(prefix+mapped_mos+[".ends "+top])+"\n")
    cap_lines = [f"{v['name']} {logical(v['nodes'][0])} "
                 f"{logical(v['nodes'][1])} {v['farad']:.12g}" for v in capacitors]
    cap_path = out / "capacitance-only.spice"
    cap_path.write_text("\n".join(prefix+mapped_mos+cap_lines+[".ends "+top])+"\n")
    result_lvs = flow.lvs(geometry, out/"source/schematic.spice", top, out, "rc-collapse-lvs")
    if not result_lvs["passed"]:
        raise RuntimeError("Full RC collapsed topology failed LVS")
    coverage = json.loads((out / "full-rc/coverage.json").read_text())
    # The substrate record is not an ordinary "node" record; it still must be extracted.
    expected = set(c["buses_um"])
    extracted = set(coverage["extracted_nodes"])
    coverage_ok = expected == extracted and coverage["extraction_statistics"] == [
        [str(len(expected)), "1.000000"]]
    if not coverage_ok:
        raise RuntimeError("Not every logical net expanded in full RC")
    per_net = {}
    for n in sorted(expected):
        rs = [r for r in resistors if logical(r["nodes"][0]) == n]
        cs = [v for v in capacitors if n in [logical(x) for x in v["nodes"]]]
        per_net[n] = dict(resistor_count=len(rs), sum_branch_resistance_ohm=sum(r["ohm"] for r in rs),
                          max_branch_resistance_ohm=max([r["ohm"] for r in rs] or [0]),
                          incident_capacitance_farad=sum(v["farad"] for v in cs),
                          rc_nodes=sorted(nod for nod in parent if logical(nod) == n))
    layout = k.Layout()
    gds = out / "generate" / (top+".gds")
    layout.read(str(gds))
    cell = layout.cell(top)
    b = cell.bbox()
    bbox = [x*layout.dbu for x in [b.left, b.bottom, b.right, b.top]]
    actual_layers = []
    grid_violations = 0
    for index in layout.layer_indexes():
        info = layout.get_info(index)
        region = k.Region(cell.begin_shapes_rec(index))
        if not region.is_empty():
            for polygon in region.each():
                for point in polygon.each_point_hull():
                    for coord in (point.x, point.y):
                        scaled = coord*layout.dbu/c["grid_um"]
                        grid_violations += abs(scaled-round(scaled)) > 1e-6
            actual_layers.append(dict(gds_layer=info.layer, datatype=info.datatype,
                name=LAYERS.get(info.layer, "PDK marker"), area_um2=region.area()*layout.dbu**2))
    if grid_violations:
        raise RuntimeError("GDS polygon vertices off manufacturing grid")
    contract = c | dict(
        gds_sha256=flow.sha(gds), bbox_um=bbox,
        width_um=bbox[2]-bbox[0], height_um=bbox[3]-bbox[1],
        area_um2=(bbox[2]-bbox[0])*(bbox[3]-bbox[1]),
        drawn_layers=actual_layers,
        routed_metal_layers=["Metal1", "Metal2", "Metal3", "Metal4"],
        pdk_available_metal_layers=5, extracted_device_mapping=mapping,
        manufacturing_grid_check=dict(grid_um=c["grid_um"], polygon_vertex_violations=0),
        pex_port_order=ports)
    flow.write(out / "physical-contract.json", contract)
    result = dict(
        passed=True, full_rc=rc.relative_to(ROOT).as_posix(), full_rc_sha256=flow.sha(rc),
        geometry_only=geometry.relative_to(ROOT).as_posix(),
        geometry_only_sha256=flow.sha(geometry),
        capacitance_only=cap_path.relative_to(ROOT).as_posix(),
        capacitance_only_sha256=flow.sha(cap_path),
        counts=dict(mos=len(mos), resistors=len(resistors), capacitors=len(capacitors),
                    zero_valued_capacitors=sum(v["farad"] == 0 for v in capacitors)),
        extracted_nets=len(extracted), expected_nets=len(expected),
        all_nets_extracted=coverage_ok, rc_collapse_lvs=result_lvs,
        device_mapping=mapping, per_net=per_net,
        resistors=resistors, capacitors=capacitors,
        capacitor_scope="Magic PDK distributed ground capacitance on extracted .n/.t "
            "nodes plus lumped coupling/residual capacitance at original logical nets; "
            "all raw resistances and capacitances retained. Not a 3D field solution, "
            "no package EM or inductance extraction.",
        junction_scope="All extracted AD/AS/PD/PS are retained identically. "
            "GF180 tech disables explicit active-diffusion junction area/perimeter C, "
            "handled inside BSIM through these geometry parameters.",
        body_and_supply_scope="All raw extracted body and supply RC nodes retained; "
            "no ideal shorting or signal-only projection in main full-RC deck.",
        sum_resistance_warning="Sum of branch R is not port-to-device effective resistance.")
    correction_path = out/"capacitance-correction.json"
    if correction_path.exists():
        correction = json.loads(correction_path.read_text())
        assert correction["passed"] and correction["assembled_rc_sha256"] == flow.sha(rc)
        result["capacitance_correction"] = correction
        result["model_source"] = "Audited RC assembly, not unmodified Magic ext2spice output"
        result["capacitor_scope"] = (
            "Original GDS-readback .ext ground C distributed by normalized allocation "
            "weights retained after Magic resistor-network simplification; original .ext coupling C retained once at "
            "logical net nodes. All R/MOS unchanged. After shorting extracted R, "
            "the full C matrix matches .ext. Weights originate in geometric tile area "
            "but may move during R-weighted merging; conservation does not establish "
            "high-frequency spatial accuracy. This is an explicit spatial-C approximation, "
            "not a 3D field solution. Native r3 export is an invalid numerical control.")
    else:
        result["model_source"] = "Unmodified Magic output; capacitance correctness not established"
        result["passed"] = False
    logs = {str(p.relative_to(out)): p.read_text() for p in [
        out/"generate/magic.log", out/"readback/magic.log", out/"full-rc/magic.log"]}
    result["log_notices"] = [
        dict(log=name, line=line) for name, contents in logs.items()
        for line in contents.splitlines()
        if "WARNING:" in line or "out-of-date timestamp" in line]
    result["timestamp_notice_interpretation"] = (
        "Magic DBio.c CDGETNEWSTAMP notice concerns serialized cell timestamp; "
        "readback geometry passes DRC and LVS and full RC collapse passes LVS. "
        "Raw notice retained; not suppressed or counted as an electrical result.")
    flow.write(out / "pex-audit.json", result)
    return result


def negative_controls(out):
    c = json.loads((out / "source/contract.json").read_text())
    top = c["top"]
    results = []
    for mode in ["input-gate-open", "vdd-vss-short"]:
        dest = out / "controls" / mode
        dest.mkdir(parents=True, exist_ok=False)
        lay = k.Layout()
        lay.read(str(out / "generate" / (top+".gds")))
        cell = lay.cell(top)
        if mode == "input-gate-open":
            index = lay.layer(46, 0)
            region = k.Region(cell.shapes(index))
            x = c["devices"][0]["cx"]
            cut = [x-.3, 14, x+.3, 15]
            region -= k.Region(k.DBox(*cut).to_itype(lay.dbu))
            cell.shapes(index).clear()
            cell.shapes(index).insert(region)
        else:
            # Explicit bridge at x=9um intersects both existing supply buses.
            cut = [8.8, c["buses_um"]["VDD"]-.2, 9.2, c["buses_um"]["VSS"]+.2]
            cell.shapes(lay.layer(42, 0)).insert(k.DBox(*cut))
        gds = dest / (top+".gds")
        lay.write(str(gds))
        drc = flow.extract(gds, c, dest/"extract", False)
        lvs = flow.lvs(dest/"extract"/(top+".spice"),
                       out/"source/schematic.spice", top, dest)
        result = dict(control=mode, gds_sha256=flow.sha(gds),
            edit_rect_um=cut, layer="Metal4" if mode == "input-gate-open" else "Metal3",
            expected_lvs_match=False, lvs=lvs, drc=drc, passed=not lvs["passed"])
        results.append(result)
        if lvs["passed"]:
            raise RuntimeError("Negative control was not detected: " + mode)
    flow.write(out/"negative-controls.json", results)
    return results


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("run", help="Repository-relative raw run directory")
    p.add_argument("--route", choices=["A", "B", "both"], default="both")
    p.add_argument("--negative-controls", action="store_true")
    args = p.parse_args()
    base = ROOT / args.run
    for route in (["A", "B"] if args.route == "both" else [args.route]):
        out = base/route
        result = audit(out)
        if args.negative_controls:
            negative_controls(out)
        print(route, result["counts"], "full RC nets", result["extracted_nets"])
    snapshot = base/"source_scripts"
    snapshot.mkdir(exist_ok=True)
    sources = [Path(__file__), Path(__file__).with_name("run.py"),
               Path(__file__).with_name("generate.py"),
               Path(__file__).with_name("correct_capacitance.py"),
               Path(__file__).with_name("publish.py")]
    for source in sources:
        shutil.copyfile(source, snapshot/source.name)
    files = [p for p in base.rglob("*") if p.is_file() and p.name != "artifact-manifest.json"]
    flow.write(base/"artifact-manifest.json", dict(
        schema_version=1, physical_pdk_lock=json.loads((ROOT/"layout/pdk-lock.json").read_text()),
        tool_binary_sha256={str(p.relative_to(ROOT)): flow.sha(p)
            for p in [flow.TOOLS/"magic", flow.TOOLS/"netgen"]},
        source_sha256={str(p.relative_to(ROOT)): flow.sha(p) for p in sources},
        artifacts=[dict(path=str(p.relative_to(base)), size=p.stat().st_size,
                        sha256=flow.sha(p)) for p in sorted(files)]))
