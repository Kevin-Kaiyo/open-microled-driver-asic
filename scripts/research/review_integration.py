"""Independently review frozen macro geometry and full top LVS with real controls.

Run using the existing KLayout Python environment and the already provisioned
project Lima VM. No PDK or baseline source is edited. Raw mutation copies remain
in build/; compact proof and complete small Netgen reports are published.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import klayout.db as k

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "ghcr.io/librelane/librelane@sha256:f91b21d75f79871f9ccf37451020b5d2f7b3236881a997ff709c561e8280a30f"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def logical_spice(path):
    lines = []
    for line in path.read_text().splitlines():
        if line.startswith("+"):
            lines[-1] += " " + line[1:].strip()
        elif line.strip() and not line.startswith("*"):
            lines.append(line.strip())
    blocks = {}
    current = None
    for line in lines:
        if line.lower().startswith(".subckt "):
            tokens = line.split()
            current = tokens[1]
            blocks[current] = {"pins": tokens[2:], "instances": []}
        elif line.lower().startswith(".ends"):
            current = None
        elif current and line.startswith("X"):
            blocks[current]["instances"].append(line.split())
    return blocks


def cell_content(layout, cell):
    shapes = []
    for index in layout.layer_indexes():
        layer = layout.get_info(index)
        shapes.extend((layer.layer, layer.datatype, shape.to_s())
                      for shape in cell.shapes(index).each())
    instances = [(layout.cell(inst.cell_index).name, inst.trans.to_s(),
                  inst.a.to_s(), inst.b.to_s(), inst.na, inst.nb)
                 for inst in cell.each_inst()]
    return sorted(shapes), sorted(instances)


def strict_lvs(report):
    return (re.findall(r"^Final result:\s*(.+)$", report, re.M)
            == ["Circuits match uniquely."]
            and not re.search(r"property errors|do not match|not equivalent", report, re.I))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=ROOT / "build/integration/r3",
                        help="Stable completed raw run, including Magic/KLayout logs")
    args = parser.parse_args()
    run = args.run.resolve()
    if not run.is_dir():
        raise RuntimeError("Completed integration run is required")
    outroot = ROOT / "build/integration-review"
    outroot.mkdir(parents=True, exist_ok=True)
    raw = Path(tempfile.mkdtemp(prefix="review-", dir=outroot))
    destination = ROOT / "evidence/research/integration-review"
    destination.mkdir(parents=True, exist_ok=True)
    checks = []

    def record(name, passed, data=None):
        checks.append(dict(check=name, passed=bool(passed), data=data))
        if not passed:
            raise RuntimeError(f"Independent review failed: {name}: {data}")

    # The raw run and all current baseline inputs are identified before tools run.
    inputs = [run / name for name in ("pixel_integrated.gds", "pixel_integrated.spice",
              "routing.json", "netgen-lvs.log", "netgen-lvs.json", "magic-linux.log",
              "klayout/pixel_integrated_main.lyrdb")]
    inputs += [ROOT / name for name in ("evidence/layout/pixel_driver_layout.gds",
               "evidence/physical/digital/gds/pixel_pwm.gds",
               "evidence/layout/pixel_driver_layout.lef",
               "evidence/physical/digital/lef/pixel_pwm.lef",
               "evidence/physical/digital/pnl/pixel_pwm.pnl.v",
               "layout/pixel_driver_schematic.spice", "layout/integration/pixel_integrated.v")]
    pdk = ROOT / "build/layout/pdk/gf180mcuD"
    sc = pdk / "libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice"
    setup = pdk / "libs.tech/netgen/gf180mcuD_setup.tcl"
    inputs += [sc, setup, Path(__file__)]
    hashes = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    pdk_lock = json.loads((ROOT / "scripts/physical/pdk-lock.json").read_text())["files"]
    for path in (sc, setup):
        if sha(path) != pdk_lock[str(path.relative_to(pdk))]:
            raise RuntimeError(f"Pinned PDK input changed: {path.name}")

    layout = k.Layout()
    layout.read(str(run / "pixel_integrated.gds"))
    top = layout.cell("pixel_integrated")
    if top is None or layout.dbu != .001:
        raise RuntimeError("Wrong top or database unit")
    sources = ["evidence/layout/pixel_driver_layout.gds",
               "evidence/physical/digital/gds/pixel_pwm.gds"]
    for source in sources:
        original = k.Layout()
        original.read(str(ROOT / source))
        same = [dict(cell=cell.name,
                     same_direct_shapes_and_instances=(
                         cell_content(original, cell)
                         == cell_content(layout, layout.cell(cell.name))))
                for cell in original.each_cell()]
        record("frozen_geometry:" + source,
               all(row["same_direct_shapes_and_instances"] for row in same), same)
    instances = [[layout.cell(inst.cell_index).name, inst.trans.to_s()]
                 for inst in top.each_inst()]
    record("hierarchy", layout.cells() == 37 and len(instances) == 2,
           dict(cells=layout.cells(), top_instances=instances))
    plan = json.loads((run / "routing.json").read_text())
    record("frozen_gds_lef_hashes",
           all(sha(ROOT / name) == value for name, value in plan["inputs_sha256"].items()),
           plan["inputs_sha256"])
    bbox = [value * layout.dbu for value in
            (top.bbox().left, top.bbox().bottom, top.bbox().right, top.bbox().top)]
    record("bbox", bbox == [25., 25., 330., 205.],
           dict(actual_bbox_um=bbox, width_height_um=[305., 180.], bbox_area_um2=54900.))

    # A connectivity graph independent of all GDS labels and SPICE net names.
    polygons, adjacency = {}, {}
    for layername, number in (("M3", 42), ("M4", 46), ("M5", 81)):
        region = k.Region(top.begin_shapes_rec(layout.layer(number, 0))).merged()
        polygons[layername] = list(region.each())
        for index in range(len(polygons[layername])):
            adjacency[(layername, index)] = set()
    for via, low, high in ((40, "M3", "M4"), (41, "M4", "M5")):
        for cut in k.Region(top.begin_shapes_rec(layout.layer(via, 0))).each():
            hits = {layer: [(layer, index) for index, polygon in enumerate(polygons[layer])
                            if not (k.Region(polygon) & k.Region(cut)).is_empty()]
                    for layer in (low, high)}
            for a in hits[low]:
                for b in hits[high]:
                    adjacency[a].add(b)
                    adjacency[b].add(a)

    def hit(layer, x, y):
        point = k.Point(round(x / layout.dbu), round(y / layout.dbu))
        nodes = [(layer, index) for index, polygon in enumerate(polygons[layer])
                 if polygon.inside(point)]
        if len(nodes) != 1:
            raise RuntimeError(f"Endpoint is not in one conductor: {layer}/{x}/{y}")
        return nodes[0]

    def connected(a, b):
        seen, pending = {a}, [a]
        while pending:
            node = pending.pop()
            for neighbor in adjacency[node] - seen:
                seen.add(neighbor)
                pending.append(neighbor)
        return b in seen

    endpoints = dict(pwm_dig=hit("M3", 150.28, 111.52),
                     pwm_analog=hit("M3", 119.7, 111.52),
                     vdd_dig=hit("M4", 173.04, 57.33),
                     vdd_analog=hit("M3", 26, 117.52),
                     vss_dig=hit("M5", 160, 60.63),
                     vss_analog=hit("M3", 26, 105.52))
    for net, a, b in (("PWM", "pwm_dig", "pwm_analog"),
                      ("VDD", "vdd_dig", "vdd_analog"),
                      ("VSS", "vss_dig", "vss_analog")):
        record("geometry_connectivity:" + net, connected(endpoints[a], endpoints[b]),
               [endpoints[a], endpoints[b]])
    for a, b in (("pwm_dig", "vdd_dig"), ("pwm_dig", "vss_dig"),
                 ("vdd_dig", "vss_dig")):
        record("geometry_no_short:" + a + ":" + b,
               not connected(endpoints[a], endpoints[b]))

    blocks = logical_spice(run / "pixel_integrated.spice")
    expected = {"VDD", "VSS", "clk", "rst", "enable", "bias", "led_k", "gate", "pwm_b",
                "pwm_monitor"} | {f"duty[{i}]" for i in range(9)}
    record("top_pin_set", set(blocks["pixel_integrated"]["pins"]) == expected
           and len(blocks["pixel_integrated"]["pins"]) == 19,
           blocks["pixel_integrated"]["pins"])
    topcalls = blocks["pixel_integrated"]["instances"]
    record("top_connections", len(topcalls) == 2, topcalls)
    for call in topcalls:
        model = call[-1]
        mapping = dict(zip(blocks[model]["pins"], call[1:-1]))
        record("top_macro_pinmap:" + model,
               mapping.get("pwm") == "pwm_monitor" and mapping.get("VSS") == "VSS"
               and (mapping.get("VDD") == "VDD" if model == "pixel_pwm"
                    else mapping.get("vlogic") == "VDD"), mapping)
    powered = (ROOT / "evidence/physical/digital/pnl/pixel_pwm.pnl.v").read_text()
    powered_calls = re.findall(r"(gf180mcu_fd_sc_mcu7t5v0__\w+)\s+(\S+)\s*\((.*?)\);",
                               powered, re.S)
    wrong_ties = []
    well_instances = 0
    for cell, instance, body in powered_calls:
        pinmap = dict(re.findall(r"\.(\w+)\s*\(\s*([^()]*)\s*\)", body))
        well_instances += "VNW" in pinmap and "VPW" in pinmap
        for pin, net in (("VDD", "VDD"), ("VSS", "VSS"), ("VNW", "VDD"), ("VPW", "VSS")):
            if pin in pinmap and pinmap[pin] != net:
                wrong_ties.append([instance, pin, pinmap[pin], net])
    record("powered_body_pinmap", len(powered_calls) == 887 and well_instances == 657
           and not wrong_ties, dict(instances=len(powered_calls),
                                    with_vnw_vpw=well_instances, wrong_ties=wrong_ties))
    retained = [name for name, block in blocks.items()
                if name.startswith("gf180mcu_fd_sc") and block["instances"]]
    record("digital_transistor_leafs", len(retained) == 30
           and all(any("nfet_05v0" in call for call in blocks[name]["instances"])
                   for name in retained), dict(count=len(retained), names=retained))
    lvs = json.loads((run / "netgen-lvs.json").read_text())
    comparisons = [row for row in lvs if "name" in row]
    record("lvs_top_and_leaf_checks", len(comparisons) == 33
           and all(not row.get("badnets") and not row.get("badelements")
                   and row["nets"][0] == row["nets"][1]
                   and row["devices"][0] == row["devices"][1] for row in comparisons),
           dict(compared_subcircuits=len(comparisons),
                primitive_class_placeholders=len(lvs) - len(comparisons)))
    record("strict_netgen", strict_lvs((run / "netgen-lvs.log").read_text()))
    log = (run / "magic-linux.log").read_text()
    record("magic_full_drc", "INTEGRATION_DRC_COUNT 0" in log
           and 'DRC style is now "drc(full)"' in log)
    database = ET.parse(run / "klayout/pixel_integrated_main.lyrdb").getroot()
    record("klayout_xml_actual_zero", len(database.findall("./items/item")) == 0,
           dict(items=len(database.findall("./items/item")),
                categories=len(database.findall("./categories/category"))))

    # Source-only mutations exercise the same real Netgen comparator as baseline.
    sc_text = sc.read_text()
    match = re.search(r"^\.SUBCKT\s+gf180mcu_fd_sc_mcu7t5v0__buf_2\s.*?^\.ENDS[^\n]*",
                      sc_text, re.M | re.S | re.I)
    if match is None:
        raise RuntimeError("Canonical buffer subckt missing")
    mutated = match.group(0).replace("W=8.2e-07", "W=1.64e-06", 1)
    if mutated == match.group(0):
        raise RuntimeError("Width mutation did not occur")
    width = raw / "canonical-sc-buf2-width.spice"
    width.write_text(sc_text[:match.start()] + mutated + sc_text[match.end():])
    pnl = ROOT / "evidence/physical/digital/pnl/pixel_pwm.pnl.v"
    pnl_text = pnl.read_text()
    match = re.search(r"gf180mcu_fd_sc_mcu7t5v0__buf_2 output12\s*\(.*?\);",
                      pnl_text, re.S)
    if match is None:
        raise RuntimeError("Actual output12 mapping missing")
    mutated = match.group(0).replace(".VNW(VDD)", ".VNW(VSS)")
    if mutated == match.group(0):
        raise RuntimeError("Body mutation did not occur")
    body = raw / "pwm-output12-body-mismatch.v"
    body.write_text(pnl_text[:match.start()] + mutated + pnl_text[match.end():])
    controls = []
    for name, library, powered in (("baseline", sc, pnl), ("buf2-width", width, pnl),
                                  ("body-tie", sc, body)):
        report = raw / (name + ".log")
        tcl = raw / (name + ".tcl")
        tcl.write_text(f'''set extracted [readnet spice {run}/pixel_integrated.spice]
set reference [readnet verilog /dev/null]
readnet spice {library} $reference
readnet spice {ROOT}/layout/pixel_driver_schematic.spice $reference
readnet verilog {powered} $reference
readnet verilog {ROOT}/layout/integration/pixel_integrated.v $reference
lvs "$extracted pixel_integrated" "$reference pixel_integrated" {setup} {report} -json
quit
''')
        argv = ["limactl", "shell", "asic", "nerdctl", "run", "--rm", "-v",
                f"{ROOT}:{ROOT}", "-w", str(raw), IMAGE, "netgen", "-batch", "source", str(tcl)]
        process = subprocess.run(argv, env=dict(os.environ,
                                 LIMA_HOME=str(ROOT / "build/physical-flow/lima")),
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (raw / (name + "-stdout.log")).write_text(process.stdout)
        if process.returncode != 0 or not report.exists():
            raise RuntimeError(f"Netgen control failed to run: {name}; inspect {raw}")
        text = report.read_text()
        passed = strict_lvs(text)
        if passed != (name == "baseline"):
            raise RuntimeError(f"Unexpected Netgen control acceptance: {name}")
        public_report = destination / (name + ".log")
        public_report.write_text(text.replace(str(ROOT), "<repo>"))
        controls.append(dict(control=name, tool_exit_code=process.returncode,
                             strict_lvs_passed=passed, rejected_by_strict_guard=not passed,
                             final_results=re.findall(r"^Final result:\s*(.*)$", text, re.M),
                             property_errors=bool(re.search("property errors", text, re.I)),
                             report=str(public_report.relative_to(ROOT)),
                             report_sha256=sha(public_report)))
    for path, expected_hash in hashes.items():
        if sha(ROOT / path) != expected_hash:
            raise RuntimeError("Input changed during independent review: " + path)
    summary = dict(schema_version=1, passed=True,
                   scope="Independent preserved-macro geometry, label-free metal/via graph, full-transistor hierarchical LVS and real source-mutation controls",
                   checks=checks, geometry_check_count=len(checks),
                   layered_graph_conductors=len(adjacency),
                   input_hashes=hashes, raw_directory=str(raw.relative_to(ROOT)),
                   controls=controls, tool_image=IMAGE,
                   mutations=dict(buf2_width="Canonical buf_2 input NMOS W: 0.82 -> 1.64 um, one instance only",
                                  body_tie="Final powered output12 VNW: VDD -> VSS, one instance only"),
                   limits="PG/body terminal connectivity and retained MOS topology/W/L under the pinned deck; ignored filltie/endcap/fill_* and deleted geometry properties remain excluded. Geometry graph covers M3/M4/M5 and Via3/Via4 only.")
    summary["output_hashes"] = {str(path.relative_to(ROOT)): sha(path)
                                for path in sorted(destination.glob("*.log"))}
    (ROOT / "evidence/research/integration-review.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    (raw / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(dict(passed=True, geometry_checks=len(checks),
                         real_netgen_controls=len(controls), raw_directory=str(raw.relative_to(ROOT))), indent=2))


if __name__ == "__main__":
    main()
