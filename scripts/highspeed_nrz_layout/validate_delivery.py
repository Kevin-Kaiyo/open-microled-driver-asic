"""Read-only integrity and electrical bookkeeping checks for physical delivery.

This validates archived evidence, not foundry signoff or a fresh DRC/LVS run.
No EDA package is required. The authoritative .ext capacitor matrix is parsed
independently and compared with all three delivered capacitance models.
"""
from pathlib import Path
from collections import defaultdict
import argparse
import hashlib
import json
import math
import re
import shlex

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


def validate(summary_path):
    summary = load(summary_path)
    dest = summary_path.parent
    seen = set()
    for item in summary["published_files"]:
        path = ROOT / item["published"]
        require(path.resolve().is_relative_to(ROOT.resolve()), "Published path escapes repository")
        require(item["published"] not in seen, "Duplicate manifest path")
        seen.add(item["published"])
        require(path.is_file() and not path.is_symlink(), f"Missing/nonregular file: {path}")
        require(path.stat().st_size == item["size"], f"Size mismatch: {path}")
        require(sha(path) == item["sha256"], f"SHA256 mismatch: {path}")
    revision = load(dest / "wording-revision.json")
    for relative, frozen_sha in revision["unchanged_model_sha256"].items():
        matched = [x for x in summary["published_files"]
                   if x["source"] == summary["raw_run"] + "/" + relative]
        require(len(matched) == 1 and matched[0]["sha256"] == frozen_sha,
                f"Frozen model/GDS no longer matches: {relative}")
    sr = revision["script_revision"]
    require(sha(dest / "scripts/correct_capacitance.executed.py") == sr["original_sha256"],
            "Executed correction source hash mismatch")
    require(sha(dest / "scripts/correct_capacitance.wording-revision.py") == sr["current_sha256"],
            "Revised correction source hash mismatch")
    require(sha(dest / "scripts/correct_capacitance.wording.diff") == sr["diff_sha256"],
            "Correction source diff hash mismatch")
    require(load(dest / "correction-provenance.json")["script_sha256"] == sr["original_sha256"],
            "Correction provenance must retain the executed source hash")
    results = {}
    for route, expected_mos in (("A", 6), ("B", 9)):
        folder = dest / route
        audit = load(folder / "pex-audit.json")
        contract = load(folder / "physical-contract.json")
        correction = load(folder / "capacitance-correction.json")
        require(audit["passed"] and audit["all_nets_extracted"], f"{route}: incomplete extraction")
        require(audit["extracted_nets"] == audit["expected_nets"], "Net coverage mismatch")
        for stage in ("magic_drc", "readback_drc", "lvs", "readback_lvs", "klayout_drc"):
            require(summary["routes"][route]["checks"][stage]["passed"], f"{route}: {stage} failed")
        require(audit["rc_collapse_lvs"]["passed"], "Collapsed RC LVS failed")
        controls = load(folder / "negative-controls.json")
        require(len(controls) == 2 and all(x["passed"] and not x["lvs"]["passed"]
                                         for x in controls), "Negative controls did not reject")
        for name in ("lvs.log", "readback-lvs.log", "rc-collapse-lvs.log"):
            require("Circuits match uniquely." in (folder / name).read_text(),
                    f"Missing unique LVS evidence: {name}")
        top = contract["top"]
        require(sha(folder / (top + ".gds")) == contract["gds_sha256"], "GDS hash mismatch")
        require(sha(folder / (top + "_rc.spice")) == audit["full_rc_sha256"], "RC hash mismatch")
        require(correction["passed"] and correction["not_unmodified_magic_output"],
                "Corrected C provenance missing")
        require(not correction["geometry_changed"] and not correction["r_or_mos_changed"],
                "Correction altered geometry or R/MOS")
        logical, target = ext_matrix(folder / "authoritative-readback.ext")
        ports, rc = deck(folder / (top + "_rc.spice"))
        require(ports == contract["ports"], "Port order mismatch")
        mapping = collapse_map(rc["R"], logical)
        require(len(rc["X"]) == expected_mos, "MOS count mismatch")
        require(len(rc["R"]) == audit["counts"]["resistors"], "R count mismatch")
        require(len(rc["C"]) == audit["counts"]["capacitors"], "C count mismatch")
        _, native = deck(folder / "invalid-native-control.spice")
        require(rc["R"] == native["R"] and rc["X"] == native["X"], "R/MOS bytes changed")
        errors = {"RC": same_matrix(capacitance_matrix(rc["C"], mapping), target)}
        for filename, key in (("capacitance-only.spice", "C"),
                              ("rc-lumped-capacitance.spice", "RCLUMP")):
            p, d = deck(folder / filename)
            require(p == ports and len(d["X"]) == expected_mos, f"{key}: interface mismatch")
            if key == "RCLUMP":
                require(d["R"] == rc["R"] and d["X"] == rc["X"], "RCLUMP R/MOS differs")
            else:
                require(not d["R"], "C-only still contains R")
            errors[key] = same_matrix(capacitance_matrix(d["C"], mapping), target,
                                      serialized_12_digits=(key == "C"))
        _, geom = deck(folder / "geometry-only.spice")
        require(not geom["R"] and not geom["C"] and len(geom["X"]) == expected_mos,
                "Geometry-only deck has parasitics or wrong MOS count")
        for d in audit["device_mapping"]:
            require(d["multiplicity"] == d["fingers"] == 1, "Unexpected MOS multiplicity")
            require(all(d["params_si"][k] > 0 for k in ("ad", "as", "pd", "ps", "w", "l")),
                    "Missing extracted junction geometry")
        require(len(audit["device_mapping"]) == expected_mos, "Device mapping incomplete")
        results[route] = dict(mos=len(rc["X"]), resistors=len(rc["R"]), capacitors=len(rc["C"]),
                              total_C_fF=sum(target.values()) * 1e15,
                              collapsed_matrix_max_error_F=errors)
    return dict(passed=True, scope="Archived physical evidence integrity and independent C bookkeeping",
                files_checked=len(seen), summary_sha256=sha(summary_path), routes=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", default="evidence/highspeed-nrz-pex/physical/summary.json")
    args = parser.parse_args()
    print(json.dumps(validate(ROOT / args.summary), indent=2))


if __name__ == "__main__":
    main()
