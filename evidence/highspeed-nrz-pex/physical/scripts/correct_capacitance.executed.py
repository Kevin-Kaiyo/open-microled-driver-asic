"""Conservatively assemble RC from GDS-readback .ext and full-R extraction.

This is an explicit model assembly, not an unmodified Magic SPICE export.
For pinned Magic 8.3.684: ResReadNode omits substrate C; ResOpt_Signal turns
coupling C into each endpoint's substrate C; retained original node names add
that split C again. The hierarchical writer also applies resistor pi handling
to MOS subcircuits. We retain the complete R/MOS network and use original .ext
capacitances once. Ground C is allocated using Magic's normalized resistor-tile
area weights; coupling C stays at original net names. This is an approximation
of spatial C placement, not a field-solved local coupling network.
"""
from pathlib import Path
import argparse
import collections
import json
import math
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).parent))
import run as flow

ROOT = flow.ROOT
MAGIC_SOURCE = ROOT/"build/layout/tools/magic"
SOURCE_LOCATORS = {
    "resis/ResReadExt.c": [
        "ResReadNode: only location/type/resistance read, substrate C not assigned.",
        "ResReadCapacitor: ResOpt_Signal adds each coupling C to both nodes' capacitance."],
    "resis/ResRex.c": ["CmdExtResis unconditionally enables ResOpt_Signal."],
    "resis/ResSimple.c": [
        "ResDistributeCapacitance scales node geometric areas by totalcap/totalarea."],
    "resis/ResMakeRes.c": [
        "ResMakeRes adds geometric tile height*width area to rn_area at segment endpoints.",
        "Between breakpoints each resistor endpoint receives half the physical tile segment area."],
    "resis/ResPrint.c": [
        "ResPrintExtNode preserves original named nodes and emits additional rnode C."],
    "extflat/EFbuild.c": ["efBuildNode adds C for existing node names."],
    "ext2spice/ext2hier.c": [
        "DEV_MSUBCKT fall-through enters unconditional resistor-pi else."],
    "ext2spice/ext2spice.c": [
        "Flat MOS subcircuit writer breaks before resistor-pi branch."],
}


def ext_matrix(path):
    s = path.read_text()
    scale = next(x.split()[1:] for x in s.splitlines() if x.startswith("scale "))
    assert scale[1] == "1", "This audited exporter requires .ext cap unit 1aF"
    nodes = {n: float(v)*1e-18 for n, v in
             re.findall(r'^node "([^"]+)" \S+ (\S+)', s, re.M)}
    sub = re.findall(r'^substrate "([^"]+)" \S+ (\S+)', s, re.M)
    assert len(sub) == 1 and float(sub[0][1]) == 0
    substrate = sub[0][0]
    couplings = [(a, b, float(v)*1e-18) for a, b, v in
                 re.findall(r'^cap "([^"]+)" "([^"]+)" (\S+)', s, re.M)]
    assert all(v >= 0 and math.isfinite(v) for v in nodes.values())
    assert all(v >= 0 and a != b for a, b, v in couplings)
    matrix = collections.defaultdict(float)
    for n, v in nodes.items():
        matrix[tuple(sorted([n, substrate]))] += v
    for a, b, v in couplings:
        matrix[tuple(sorted([a, b]))] += v
    return nodes, substrate, couplings, matrix


def lumped_control(route_dir):
    c = json.loads((route_dir/"source/contract.json").read_text())
    top = c["top"]
    nodes, substrate, couplings, matrix = ext_matrix(route_dir/"readback"/(top+".ext"))
    full = route_dir/"full-rc"/(top+"_rc.spice")
    raw = full.read_text().splitlines()
    mos_r = [x for x in raw if x.startswith(("X", "R"))]
    portline = next(x for x in raw if x.startswith(".subckt"))
    out = route_dir/"rc-lumped-capacitance.spice"
    caps = [(n, substrate, v) for n, v in sorted(nodes.items())] + couplings
    out.write_text("\n".join([
        "* C-placement sensitivity control: same full R/MOS, all .ext C at original nets.",
        portline] + mos_r + [
        f"C{i} {a} {b} {v:.17g}" for i,(a,b,v) in enumerate(caps)] +
        [".ends "+top])+"\n")
    assert [x for x in out.read_text().splitlines() if x.startswith(("X", "R"))] == mos_r
    return dict(path=str(out.relative_to(ROOT)), sha256=flow.sha(out),
                same_r_and_mos=True, same_collapsed_c_matrix=True,
                cap_count=len(caps), total_fF=sum(matrix.values())*1e15)


def correct(route_dir):
    c = json.loads((route_dir/"source/contract.json").read_text())
    top = c["top"]
    original_dir = route_dir/"unmodified-full-rc"
    shutil.copytree(route_dir/"full-rc", original_dir)
    raw_rc = original_dir/(top+"_rc.spice")
    rc = route_dir/"full-rc"/(top+"_rc.spice")
    extraction = route_dir/"readback"/(top+".ext")
    nodes, substrate, couplings, target_matrix = ext_matrix(extraction)
    all_nets = set(nodes) | {substrate}
    assert all_nets == set(c["buses_um"])
    raw_lines = re.sub(r"\n\+\s*", " ", raw_rc.read_text()).splitlines()
    mos_r = [x for x in raw_lines if x.startswith(("X", "R"))]
    portline = next(x for x in raw_lines if x.startswith(".subckt"))
    assert portline.split()[2:] == c["ports"]
    weights = collections.defaultdict(dict)
    for n, value in re.findall(r'^rnode "([^"]+)" \S+ (\S+)',
                               (original_dir/(top+".res.ext")).read_text(), re.M):
        possible = [name for name in all_nets if n == name or
                    n.startswith(name+".n") or n.startswith(name+".t")]
        assert len(possible) == 1, (n, possible)
        weights[possible[0]][n] = float(value)
    assert set(weights) == all_nets
    incident = collections.defaultdict(float)
    for a, b, v in couplings:
        incident[a] += v
        incident[b] += v
    report = {}
    caps = []
    for net in sorted(nodes):
        values = weights[net]
        total_weight = sum(values.values())
        assert total_weight > 0, "No weights: cannot invent capacitance placement"
        # Independent causal check: rnode values are coupled-C copies, rather
        # than the actual node-to-substrate C. Recover only their area ratios.
        assert math.isclose(total_weight*1e-18, incident[net], rel_tol=1e-4, abs_tol=1e-23)
        total_ground = nodes[net]
        allocated = {}
        for n, w in sorted(values.items()):
            value = total_ground*w/total_weight
            if value:
                caps.append((n, substrate, value))
                allocated[n] = value
        assert math.isclose(sum(allocated.values()), total_ground, rel_tol=1e-13)
        report[net] = dict(
            raw_rnode_sum_farad=total_weight*1e-18,
            incident_coupling_farad=incident[net],
            authoritative_ground_farad=total_ground,
            normalized_weights={n: w/total_weight for n, w in sorted(values.items())},
            allocated_ground_farad=allocated)
    caps.extend(couplings)
    assembled = [f"* Audited RC model assembly from {extraction.relative_to(ROOT)}.",
                 "* Original Magic RC preserved in ../unmodified-full-rc/.",
                 "* R/MOS unchanged; C counted once with explicit area-weight allocation.",
                 "* Coupling remains at original logical nodes; no EM claim.", portline]
    assembled.extend(mos_r)
    assembled.extend(f"C{i} {a} {b} {v:.17g}" for i, (a, b, v) in enumerate(caps))
    assembled.append(".ends "+top)
    rc.write_text("\n".join(assembled)+"\n")
    out_matrix = collections.defaultdict(float)

    def logical(n):
        matches = [name for name in all_nets if n == name or
                   n.startswith(name+".n") or n.startswith(name+".t")]
        assert len(matches) == 1
        return matches[0]

    for a, b, v in caps:
        a, b = logical(a), logical(b)
        if a != b:
            out_matrix[tuple(sorted([a, b]))] += v
    assert set(out_matrix) == set(target_matrix)
    worst = max(abs(out_matrix[k]-target_matrix[k]) for k in out_matrix)
    assert worst < 1e-27
    assert [x for x in rc.read_text().splitlines() if x.startswith(("X", "R"))] == mos_r
    # Run an independent native flat writer with resistance disabled. Its
    # printed rounding is checked against raw .ext rather than treated as gold.
    flat = route_dir/"flat-c-control"
    flat.mkdir()
    for suffix in [".mag", ".ext"]:
        shutil.copyfile(route_dir/"readback"/(top+suffix), flat/(top+suffix))
    tcl = flat/"export.tcl"
    tcl.write_text(f"""load {top}
extract style ngspice()
ext2spice lvs
ext2spice hierarchy off
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist off
ext2spice -o flat-c.spice
quit -noprompt
""")
    flow.magic(tcl, flat)
    native_matrix = collections.defaultdict(float)
    from audit import number
    for line in (flat/"flat-c.spice").read_text().splitlines():
        if line.startswith("C"):
            t = line.split()
            native_matrix[tuple(sorted(t[1:3]))] += number(t[3])
    assert set(native_matrix) == set(target_matrix)
    native_errors = {str(k): native_matrix[k]-target_matrix[k] for k in target_matrix}
    assert max(map(abs, native_errors.values())) < 1.01e-18
    result = dict(
        schema_version=1, passed=True, method="Explicit .ext-ground-C assembly using "
        "normalized Magic resistor-tile area weights; original coupling C retained once.",
        not_unmodified_magic_output=True, geometry_changed=False, r_or_mos_changed=False,
        original_rc_sha256=flow.sha(raw_rc), assembled_rc_sha256=flow.sha(rc),
        authoritative_ext_sha256=flow.sha(extraction),
        weights_res_ext_sha256=flow.sha(original_dir/(top+".res.ext")),
        substrate_node=substrate, ground_allocation=report,
        original_couplings=[dict(nodes=[a,b],farad=v) for a,b,v in couplings],
        capacitance_matrix=[dict(nodes=list(k), target_farad=target_matrix[k],
                                assembled_collapsed_farad=out_matrix[k],
                                native_flat_writer_farad=native_matrix[k])
                            for k in sorted(target_matrix)],
        matrix_max_abs_error_farad=worst,
        authoritative_ground_sum_fF=sum(nodes.values())*1e15,
        authoritative_coupling_sum_fF=sum(v for _,_,v in couplings)*1e15,
        authoritative_total_sum_fF=sum(target_matrix.values())*1e15,
        native_flat_rounding_max_abs_error_farad=max(map(abs, native_errors.values())),
        native_flat_sha256=flow.sha(flat/"flat-c.spice"),
        source_code_evidence={p: dict(sha256=flow.sha(MAGIC_SOURCE/p), findings=notes)
                              for p, notes in SOURCE_LOCATORS.items()},
        limitations=["Ground C allocation follows Magic's area-weight approximation.",
                     "Coupling C is lumped at original named nets, not local spatial coupling.",
                     "PDK/Magic/GDS and complete extracted R/MOS network unchanged.",
                     "No intrinsic BSIM junction/gate capacitance is added or removed."])
    result["rc_lumped_capacitance_control"] = lumped_control(route_dir)
    flow.write(route_dir/"capacitance-correction.json", result)
    print(c["route"], "C corrected", result["authoritative_total_sum_fF"], "fF", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True)
    p.add_argument("--run", required=True)
    args = p.parse_args()
    base = ROOT/args.base
    dest = ROOT/"build/highspeed-nrz-layout"/args.run
    shutil.copytree(base, dest)
    for route in ["A", "B"]:
        correct(dest/route)
    flow.write(dest/"correction-provenance.json", dict(
        source_run=str(base.relative_to(ROOT)), corrected_run=str(dest.relative_to(ROOT)),
        script_sha256=flow.sha(Path(__file__)),
        geometry_source_gds_unchanged=True, original_run_untouched=True))
