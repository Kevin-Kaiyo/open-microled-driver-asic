"""Read-only integrity and electrical bookkeeping checks for physical delivery.

This validates archived evidence, not foundry signoff or a fresh DRC/LVS run.
The authoritative .ext capacitor matrix is parsed independently of the assembly
code. KLayout's Python geometry reader verifies the actual delivered polygons.
No Magic/Netgen executable, PDK or transient simulation is required.
"""
from pathlib import Path
from collections import defaultdict
import argparse
import hashlib
import json
import math
import re
import shlex
import xml.etree.ElementTree as ET
import klayout.db as k

ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def number(text):
    match = re.fullmatch(r"([-+0-9.eE]+)(meg|[fpnumk]?)", text.lower())
    require(match is not None, f"Unsupported numeric literal: {text}")
    return float(match[1]) * {"": 1, "f": 1e-15, "p": 1e-12, "n": 1e-9,
                              "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6}[match[2]]


def deck(path):
    lines = []
    for line in path.read_text().splitlines():
        if line.startswith("+"):
            require(bool(lines), f"Orphan continuation: {path}")
            lines[-1] += " " + line[1:]
        elif line.strip() and not line.lstrip().startswith("*"):
            lines.append(line.strip())
    parsed = [line.split() for line in lines]
    ports = [p[2:] for p in parsed if p[0].lower() == ".subckt"]
    require(len(ports) == 1, f"Expected one subcircuit: {path}")
    items = {kind: [p for p in parsed if p[0][0].upper() == kind] for kind in "XRC"}
    return ports[0], items


def ext_matrix(path):
    parsed = [shlex.split(line) for line in path.read_text().splitlines() if line.strip()]
    scale = [p for p in parsed if p[0] == "scale"]
    require(len(scale) == 1 and float(scale[0][2]) == 1, "Expected capacitance scale 1 aF")
    substrate = [p[1] for p in parsed if p[0] == "substrate"]
    require(len(substrate) == 1, "Expected one explicit substrate node")
    nodes = {p[1] for p in parsed if p[0] in ("node", "substrate")}
    matrix = defaultdict(float)
    for p in parsed:
        if p[0] == "node":
            matrix[tuple(sorted((p[1], substrate[0])))] += float(p[3]) * 1e-18
        elif p[0] == "cap":
            matrix[tuple(sorted(p[1:3]))] += float(p[3]) * 1e-18
    # A high-R-poly marker is a device-region record, not a fourth terminal.
    # Only the explicitly recognized zero-C/unconnected marker may be removed.
    for p in parsed:
        if p[:3] == ["device", "rsubckt", "ppolyf_u_1k_6p0"]:
            marker = p[10]
            require(marker in nodes, "Missing resistor body marker")
            require(all(v == 0 for pair, v in matrix.items() if marker in pair),
                    "Nonzero marker capacitance cannot be discarded")
            require(not any(q[0] == "cap" and marker in q[1:3] for q in parsed),
                    "Coupled marker cannot be discarded")
            nodes.remove(marker)
    return nodes, {k: v for k, v in matrix.items() if v != 0}


def collapse_map(resistors, logical_nodes):
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    for p in resistors:
        require(number(p[3]) > 0 and math.isfinite(number(p[3])), "Invalid resistor")
        parent[find(p[1])] = find(p[2])
    representatives = {}
    for n in logical_nodes:
        r = find(n)
        require(r not in representatives, f"Shorted logical nets: {n}")
        representatives[r] = n
    mapped = {}
    for n in parent:
        require(find(n) in representatives, f"Unassigned resistance component: {n}")
        mapped[n] = representatives[find(n)]
    return mapped


def capacitance_matrix(caps, mapping):
    matrix = defaultdict(float)
    for p in caps:
        value = number(p[3])
        require(value > 0 and math.isfinite(value), "Nonpositive/nonfinite capacitance")
        a, b = (mapping.get(n, n) for n in p[1:3])
        if a != b:
            matrix[tuple(sorted((a, b)))] += value
    return dict(matrix)


def same_matrix(actual, expected, serialized_12_digits=False):
    require(set(actual) == set(expected), "Capacitance matrix has missing/extra node pairs")
    error = max(abs(actual[k] - v) for k, v in expected.items())
    # The archived C-only control serializes each branch to 12 significant
    # digits; RC and RCLUMP preserve 17. This is a print-precision tolerance.
    agrees = (all(math.isclose(actual[k], v, rel_tol=5e-12, abs_tol=1e-30)
                  for k, v in expected.items()) if serialized_12_digits else error < 1e-27)
    require(agrees, f"Capacitance matrix mismatch: {error} F")
    return error


def canonical_devices(items, mapping):
    result = []
    for p in items:
        model_index = 4 if p[4] == "ppolyf_u_1k_6p0" else 5
        require(p[model_index] in ("ppolyf_u_1k_6p0", "nfet_03v3", "pfet_03v3"),
                "Unexpected compact model")
        nodes = [mapping.get(n, n) for n in p[1:model_index]]
        result.append((p[0], tuple(nodes), tuple(p[model_index:])))
    return sorted(result)


def geometry(folder, contract, controls):
    layout = k.Layout()
    layout.read(str(folder / (contract["top"] + ".gds")))
    cell = layout.cell(contract["top"])
    require(cell is not None, "Missing GDS top")
    active = k.Region(cell.begin_shapes_rec(layout.layer(22, 0)))
    poly = k.Region(cell.begin_shapes_rec(layout.layer(30, 0)))
    for d in contract["devices"]:
        x, y, width, length = d["cx"], d["cy"], d["w_um"], d["l_um"]
        win = k.Region(k.DBox(x-length/2-.5, y-width/2-.01,
                             x+length/2+.5, y+width/2+.01).to_itype(layout.dbu))
        channel = list(((active & win) & poly).merged().each())
        require(len(channel) == 1, "MOS channel polygon count")
        box = channel[0].bbox()
        require(math.isclose(box.width()*layout.dbu, length, abs_tol=1e-12)
                and math.isclose(box.height()*layout.dbu, width, abs_tol=1e-12), "GDS MOS W/L")
        diffusion = list(((active & win)-poly).merged().each())
        require(len(diffusion) == 2, "MOS diffusion count")
        extracted = next(m for m in contract["extracted_device_mapping"]
                         if m["original_instance"] == "X"+d["name"])["params_si"]
        for polygon, area_key, perimeter_key in zip(diffusion, ("ad", "as"), ("pd", "ps")):
            require(math.isclose(polygon.area()*layout.dbu**2, extracted[area_key]*1e12,
                                 abs_tol=1e-9), "GDS diffusion area")
            require(math.isclose(polygon.perimeter()*layout.dbu, extracted[perimeter_key]*1e6,
                                 abs_tol=1e-9), "GDS diffusion perimeter")
    resistor = contract["resistors"][0]
    marker = k.Region(cell.begin_shapes_rec(layout.layer(110, 5)))
    regions = list((marker & poly).merged().each())
    require(len(regions) == 1, "High-R poly body polygon count")
    box = regions[0].bbox()
    require(math.isclose(box.width()*layout.dbu, resistor["r_width_um"], abs_tol=1e-12)
            and math.isclose(box.height()*layout.dbu, resistor["r_length_um"], abs_tol=1e-12),
            "GDS resistor W/L")
    changes = {}
    for ctrl in controls:
        path = folder / "controls" / ctrl["control"] / (contract["top"]+".gds")
        require(sha(path) == ctrl["gds_sha256"], "Negative GDS hash")
        other = k.Layout()
        other.read(str(path))
        other_cell = other.cell(contract["top"])
        changed = 0.
        layers = {(layout.get_info(i).layer, layout.get_info(i).datatype) for i in layout.layer_indices()}
        layers |= {(other.get_info(i).layer, other.get_info(i).datatype) for i in other.layer_indices()}
        for layer, datatype in layers:
            a = k.Region(cell.begin_shapes_rec(layout.layer(layer, datatype)))
            b = k.Region(other_cell.begin_shapes_rec(other.layer(layer, datatype)))
            changed += (a ^ b).area()*layout.dbu**2
        require(changed > 0 and math.isclose(changed, ctrl["changed_polygon_area_um2"], abs_tol=1e-10),
                "Negative control actual polygon delta differs")
        changes[ctrl["control"]] = changed
    return dict(mos_channels=len(contract["devices"]), resistor_body_um2=box.area()*layout.dbu**2,
                negative_polygon_delta_um2=changes)


def validate(summary_path):
    summary, dest = load(summary_path), summary_path.parent
    manifest = load(dest / "artifact-manifest.json")
    seen = set()
    for item in manifest["artifacts"]:
        path = dest / item["path"]
        require(path.resolve().is_relative_to(dest.resolve()), "Manifest path escapes evidence")
        require(item["path"] not in seen, "Duplicate manifest path")
        seen.add(item["path"])
        require(path.is_file() and not path.is_symlink(), f"Missing/nonregular artifact: {path}")
        require(path.stat().st_size == item["size"] and sha(path) == item["sha256"], f"Artifact hash/size: {path}")
    actual = {str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file()}
    require(actual == seen | {"artifact-manifest.json"}, "Unlisted/missing evidence artifact")
    for item in summary["published_files"]:
        path = ROOT / item["published"]
        require(path.resolve().is_relative_to(dest.resolve()), "Published path escapes evidence")
        require(sha(path) == item["sha256"] and path.stat().st_size == item["size"], "Publication mismatch")
    require(sha(ROOT / summary["selected_public_spec"]) == summary["selected_spec_sha256"], "Public specification hash")
    require(sha(dest / "selected-spec.json") == summary["selected_spec_sha256"], "Frozen spec mismatch")
    selected = load(dest / "selected-spec.json")
    provenance = load(dest / "correction-provenance.json")
    for source, digest in provenance["sources"].items():
        prefix = "pvt_" if "highspeed_nrz_pvt_layout" in source else ""
        require(sha(dest / "scripts" / (prefix + Path(source).name)) == digest, "Executed-source hash mismatch")
    results = {}
    for route, expected_mos in (("A", 6), ("B", 9)):
        folder = dest / route
        audit, contract = load(folder / "pex-audit.json"), load(folder / "physical-contract.json")
        correction = load(folder / "capacitance-correction.json")
        require(audit["passed"] and audit["all_nets_extracted"], f"{route}: incomplete extraction")
        require(audit["extracted_nets"] == audit["expected_nets"] == (9 if route == "A" else 10), "Net coverage")
        for stage in ("magic_drc", "readback_drc", "lvs", "readback_lvs", "klayout_drc"):
            require(summary["routes"][route]["checks"][stage]["passed"], f"{route}: {stage}")
        require(audit["rc_collapse_lvs"]["passed"], "Collapsed RC LVS")
        for name in ("lvs.log", "readback-lvs.log", "rc-collapse-lvs.log"):
            require("Circuits match uniquely." in (folder / name).read_text(), f"Unique LVS missing: {name}")
        require("NRZ_DRC_COUNT 0" in (folder / "native-magic.log").read_text(), "Native DRC log")
        require("NRZ_DRC_COUNT 0" in (folder / "readback-magic.log").read_text(), "Readback DRC log")
        require(load(folder / "klayout-command.json")["exit_code"] == 0, "KLayout exit")
        require(len(ET.parse(folder / "klayout-main.lyrdb").findall(".//items/item")) == 0, "KLayout violations")
        controls = load(folder / "negative-controls.json")
        require(len(controls) == 2 and all(x["passed"] and not x["lvs"]["passed"] for x in controls), "Negative controls")
        for control in controls:
            log = (folder / "controls" / control["control"] / "lvs.log").read_text()
            require("Circuits match uniquely." not in log and any(s in log for s in
                    ("Netlists do not match.", "Top level cell failed pin matching.")), "Negative-control LVS log")
        top = contract["top"]
        expected_hashes = {top+".gds": contract["gds_sha256"], top+"_rc.spice": audit["full_rc_sha256"],
            "geometry-only.spice": audit["geometry_only_sha256"], "capacitance-only.spice": audit["capacitance_only_sha256"],
            "rc-lumped-capacitance.spice": correction["rc_lumped_capacitance_control"]["sha256"],
            "authoritative-readback.ext": correction["authoritative_ext_sha256"],
            "allocation-weights.res.ext": correction["weights_res_ext_sha256"],
            "invalid-native-control.spice": correction["original_rc_sha256"]}
        for name, digest in expected_hashes.items():
            require(sha(folder / name) == digest, "Cross-linked artifact hash: "+name)
        measured = load(dest / "final-metrics.json")["routes"][route]["final"]
        require(measured["transfer_resistance"]["rc_sha256"] == audit["full_rc_sha256"], "Metrics use different RC")
        require(measured["bbox_um"] == contract["bbox_um"] and measured["counts"] == audit["counts"],
                "Metrics geometry/count mismatch")
        require(math.isclose(measured["area_um2"], contract["width_um"]*contract["height_um"], abs_tol=1e-9),
                "Metrics area arithmetic")
        require(correction["passed"] and correction["not_unmodified_magic_output"] and
                not correction["geometry_changed"] and not correction["r_or_mos_changed"], "Correction provenance")
        require(correction["ground_c_without_weights"] == ["DATA"] and
                correction["ground_allocation"]["DATA"]["normalized_weights"] is None,
                "No-weight DATA C must be explicitly declared")
        logical, target = ext_matrix(folder / "authoritative-readback.ext")
        ports, rc = deck(folder / (top+"_rc.spice"))
        require(ports == contract["ports"], "Port order")
        mapping = collapse_map(rc["R"], logical)
        mos = [p for p in rc["X"] if p[4] != "ppolyf_u_1k_6p0"]
        xr = [p for p in rc["X"] if p[4] == "ppolyf_u_1k_6p0"]
        require(len(mos) == expected_mos and len(xr) == 1, "MOS vs designed resistor count")
        require(len(rc["R"]) == audit["counts"]["resistors"] and
                len(rc["C"]) == audit["counts"]["capacitors"], "Explicit R/C count")
        params = dict(t.split("=") for t in xr[0][5:])
        designed = selected["routes"][route]["resistors"][0]
        require(math.isclose(number(params["r_width"])*1e6, designed["r_width_um"]) and
                math.isclose(number(params["r_length"])*1e6, designed["r_length_um"]), "Design resistor W/L")
        require(set(mapping.get(n, n) for n in xr[0][1:3]) == {"DATA", "DI"} and
                mapping[xr[0][3]] == "VSS", "Designed resistor terminal connectivity")
        require(sha(folder / "selected-electrical-source.spice") ==
                sha(ROOT / selected["routes"][route]["schematic_source"]), "Selected electrical source changed")
        _, native = deck(folder / "invalid-native-control.spice")
        require(rc["R"] == native["R"] and rc["X"] == native["X"], "Native R/compact devices changed")
        errors = {"RC": same_matrix(capacitance_matrix(rc["C"], mapping), target)}
        canonical = canonical_devices(rc["X"], mapping)
        for filename, label in (("capacitance-only.spice", "C"), ("rc-lumped-capacitance.spice", "RCLUMP"),
                                ("geometry-only.spice", "GEOM")):
            p, d = deck(folder / filename)
            require(p == ports and canonical_devices(d["X"], mapping) == canonical, label+" compact-device mismatch")
            if label == "RCLUMP":
                require(d["R"] == rc["R"] and d["X"] == rc["X"], "RCLUMP R/devices differ")
            else:
                require(not d["R"], label+" contains interconnect R")
            if label == "GEOM":
                require(not d["C"], "GEOM contains explicit C")
            else:
                errors[label] = same_matrix(capacitance_matrix(d["C"], mapping), target, label == "C")
        geometry_result = geometry(folder, contract, controls)
        results[route] = dict(mos=len(mos), designed_resistors=len(xr), interconnect_resistors=len(rc["R"]),
            explicit_capacitors=len(rc["C"]), total_explicit_C_fF=sum(target.values())*1e15,
            collapsed_matrix_max_error_F=errors, actual_gds_geometry=geometry_result)
    return dict(passed=True, scope="Archived hashes, actual GDS polygons, check logs and independent C-matrix bookkeeping; no new EDA/signoff run",
                files_checked=len(seen), summary_sha256=sha(summary_path), routes=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", default="evidence/highspeed-nrz-pvt/physical/summary.json")
    parser.add_argument("--out", help="Optional receipt outside the frozen evidence folder")
    args = parser.parse_args()
    result = validate(ROOT / args.summary)
    if args.out:
        path = ROOT / args.out
        require(not path.resolve().is_relative_to((ROOT / args.summary).parent.resolve()), "Receipt must not mutate evidence")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
