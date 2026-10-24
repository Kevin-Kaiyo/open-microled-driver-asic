"""Independent GF180 mixed 3.3 V / 6 V NRZ layout construction and schematic reference.

Uses the pinned public Magic PCells, without modifying their source or notices.
The physical connectivity below is authored separately from the original SPICE
parser used to write the gold LVS reference. All coordinates are micrometres.
"""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "layout/highspeed_nrz"
GRID = 0.005
# run.py provides independently authored physical devices and ports.
TOPS = {}
PORTS = {}
PLACEMENT = {}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def gold(route, folder):
    raise RuntimeError("Use robustness run.py with an independent electrical reference")


def make(route):
    folder = OUT / route
    folder.mkdir(parents=True, exist_ok=True)
    source, schematic = gold(route, folder)
    dev = []
    for i, (name, model, w, length, nodes) in enumerate(PLACEMENT[route]):
        assert model in ("nfet_03v3", "pfet_03v3", "nfet_06v0", "pfet_06v0")
        assert length >= {"nfet_03v3":.28,"pfet_03v3":.28,"nfet_06v0":.7,"pfet_06v0":.55}[model]
        assert w >= (.3 if model.endswith("06v0") else .22)
        cx, cy = 4 + 6 * i, 20
        dx = length / 2 + .26
        # Source/drain descend on M2. Gate rises to a stacked contact above
        # diffusion, then descends on M4 to avoid the 0.8um D/S pitch on M2.
        pins = {"D": [cx - dx, cy], "G": [cx, cy + w / 2 + .5],
                "S": [cx + dx, cy], "B": [cx - 2.5, cy]}
        dev.append(dict(name=name, model=model, w_um=w, l_um=length, cx=cx, cy=cy,
                        nodes=nodes.split(), pins_um=pins))
    nets = PORTS[route].copy()
    for d in dev:
        for n in d["nodes"]:
            if n not in nets:
                nets.append(n)
    buses = {n: 1 + 1.2 * i for i, n in enumerate(nets)}
    xs = {n: [] for n in nets}
    for d in dev:
        for key, n in zip("DGSB", d["nodes"]):
            xs[n].append(d["pins_um"][key][0])
    spans = {n: [min(v) - .5, max(v) + .5] for n, v in xs.items()}
    anchors = {n: [spans[n][0] + .2, buses[n]] for n in PORTS[route]}
    tcl = [
        "# Public GF180 PCells retained unchanged; independent project routing.",
        "proc rect {layer x1 y1 x2 y2} {",
        " box values ${x1}um ${y1}um ${x2}um ${y2}um",
        " paint $layer", "}",
        "proc via {lo hi cut x y} {",
        " foreach layer [list $lo $hi] {",
        "  rect $layer [expr {$x-.19}] [expr {$y-.19}] [expr {$x+.19}] [expr {$y+.19}]",
        " }",
        " set h [expr {$cut eq \"via1\" ? .13 : .14}]",
        " rect $cut [expr {$x-$h}] [expr {$y-$h}] [expr {$x+$h}] [expr {$y+$h}]",
        "}", "set devices {"]
    for d in dev:
        tcl.append(" {" + " ".join(map(str, [d["name"], d["model"], d["w_um"],
                   d["l_um"], d["cx"], d["cy"]] + d["nodes"])) + "}")
    tcl += [
        "}", "foreach device $devices {",
        " lassign $device name type w l cx cy d g s b",
        " load pcell_$name", " box values 0 0 0 0",
        " gf180mcu::${type}_draw [dict merge [gf180mcu::${type}_defaults] [dict create w $w l $l full_metal 0 gate_to_polycont .5]]",
        " save pcell_$name", "}", "load assembly",
        "foreach device $devices {",
        " lassign $device name type w l cx cy d g s b",
        " getcell pcell_$name child 0 0 parent ${cx}um ${cy}um", "}",
        "select top cell", f"flatten -nolabels {TOPS[route]}",
        f"load {TOPS[route]}"]
    routes = []

    def rect(net, layer, x1, y1, x2, y2):
        coords = [round(x, 6) for x in [x1, y1, x2, y2]]
        assert all(abs(v / GRID - round(v / GRID)) < 1e-6 for v in coords)
        tcl.append(f"rect {layer} " + " ".join(map(str, coords)))
        routes.append(dict(net=net, layer=layer, rect_um=coords))

    for n in nets:
        rect(n, "metal3", spans[n][0], buses[n] - .2,
             spans[n][1], buses[n] + .2)
        x = anchors[n][0] if n in anchors else spans[n][0] + .2
        y = buses[n]
        tcl += [f"box values {x-.1}um {y-.1}um {x+.1}um {y+.1}um",
                f"label {n} center metal3"]
        if n in PORTS[route]:
            tcl.append(f"port make {PORTS[route].index(n)+1}")
    for d in dev:
        # Unused lower poly contact remains connected to the gate. Its local
        # metal pad must satisfy minimum area even without a routing via.
        gx, gy = d["cx"], d["cy"] - d["w_um"] / 2 - .5
        rect(d["nodes"][1], "metal1", gx-.19, gy-.19, gx+.19, gy+.19)
        # Guard contact to explicit body terminal; guard metal remains intact.
        bx, by = d["pins_um"]["B"]
        ringx = d["cx"] - d["l_um"] / 2 - .98
        rect(d["nodes"][3], "metal1", bx, by - .19, ringx + .15, by + .19)
        for key, n in zip("DGSB", d["nodes"]):
            x, y = d["pins_um"][key]
            tcl.append(f"via metal1 metal2 via1 {x} {y}")
            if key == "G":
                tcl += [f"via metal2 metal3 via2 {x} {y}",
                        f"via metal3 metal4 via3 {x} {y}"]
                rect(n, "metal4", x - .19, buses[n] - .19, x + .19, y + .19)
                tcl.append(f"via metal3 metal4 via3 {x} {buses[n]}")
            else:
                rect(n, "metal2", x - .19, buses[n] - .19, x + .19, y + .19)
                tcl.append(f"via metal2 metal3 via2 {x} {buses[n]}")
    tcl += [
        "select top cell", "drc style drc(full)", "drc check", "drc catchup",
        'puts "NRZ_DRC_COUNT [drc list count total]"',
        'puts "NRZ_DRC_ERRORS [drc listall why]"',
        f"save {TOPS[route]}", "extract all", "ext2spice lvs", "ext2spice",
        f"gds write {TOPS[route]}.gds", "quit -noprompt"]
    (folder / "generate.tcl").write_text("\n".join(tcl) + "\n")
    contract = dict(
        schema_version=1, route=route, top=TOPS[route], ports=PORTS[route],
        grid_um=GRID, devices=dev, buses_um=buses, bus_spans_um=spans,
        port_anchor_um=anchors, routes=routes,
        external_components=(
            [{"name": "VH", "kind": "ideal bidirectional rail"},
             {"name": "VL", "kind": "ideal bidirectional rail"}] if route == "A" else
            [{"name": "RREF", "nodes": ["VDD", "BIAS"], "ohm": 88386.1064910889},
             {"name": "RDUMMY", "nodes": ["VDUMMY", "DUMMY"], "ohm": 28000}]),
        dimension_change=(
            [] if route == "A" else
            [dict(device="TAIL", parameter="W", original_um=5.75895881652832,
                  physical_um=5.76, reason="GF180 0.005um manufacturing grid")]),
        source_sha256={str(source.relative_to(ROOT)): sha(source),
                       str(schematic.relative_to(ROOT)): sha(schematic)},
        pcell_parameters=dict(full_metal=0, gate_to_polycont_um=.5,
                              guard=1, glc=1, grc=1, topc=1, botc=1),
        note="Transistor core only; no pads/ESD/regulators/external resistor implementation. "
             "Use extraction results for junction areas/perimeters, not schematic estimates.")
    (folder / "contract.json").write_text(json.dumps(contract, indent=2) + "\n")
    return contract


if __name__ == "__main__":
    for name in TOPS:
        c = make(name)
        print(name, c["top"], len(c["devices"]), "MOS")
