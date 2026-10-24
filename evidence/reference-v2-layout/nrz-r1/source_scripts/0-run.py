"""Real public-PDK reference modules; old core sources and evidence stay read-only.

The physical specification is authored separately from the electrical SPICE.
This flow inherits the audited full-R/C accounting and independent DRC tools;
it never fabricates package/board passives as on-chip extracted components.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "scripts/highspeed_nrz_robustness_layout"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


helpers = module("reference_physical_helpers", OLD / "run.py")
generator = module("reference_module_generator", Path(__file__).with_name("generate.py"))
flow = helpers.flow


def generate(route, definition, output):
    assert not definition.get("resistors"), "Reference module currently contains MOS only"
    generator.OUT = output
    generator.TOPS = {route: definition["top"]}
    generator.PORTS = {route: definition["ports"]}
    generator.PLACEMENT = {route: [
        (d["name"], d["model"], d["w_um"], d["l_um"], " ".join(d["nodes"]))
        for d in definition["devices"]]}
    generator.gold = lambda r, folder: helpers.gold(r, folder, definition)
    c = generator.make(route)
    c.update(resistors=[], external_components=definition["external_components"],
             dimension_change=definition.get("dimension_change", []),
             design_changes=definition.get("design_changes", []),
             negative_control_gate=definition["negative_control_gate"],
             supply_port=definition["supply_port"], nmos_guard_all_sides=True,
             electrical_physical_independence="Physical D/G/S/B independently authored in JSON; "
             "gold independently parsed from electrical MOS source. No netlist-to-placement parser.")
    for d in c["devices"]:
        if d["model"] == "nfet_06v0":
            d["guard_all_sides"] = True
    flow.write(output / route / "contract.json", c)
    return c


def negative_controls(out):
    k = helpers.audit.k
    c = json.loads((out / "source/contract.json").read_text())
    results = []
    for mode in ("reference-gate-open", "supply-vss-short"):
        dest = out / "controls" / mode
        dest.mkdir(parents=True)
        layout = k.Layout()
        layout.read(str(out / "generate" / (c["top"] + ".gds")))
        cell = layout.cell(c["top"])
        if mode == "reference-gate-open":
            net = c["negative_control_gate"]
            d = next(d for d in c["devices"] if d["nodes"][1] == net)
            x = d["cx"]
            y = round((c["buses_um"][net] + d["pins_um"]["G"][1]) / 2 / .005) * .005
            rect = [x-.3, y-.3, x+.3, y+.3]
            layer = layout.layer(46, 0)
            original = k.Region(cell.shapes(layer))
            mutated = original - k.Region(k.DBox(*rect).to_itype(layout.dbu))
        else:
            nets = [c["supply_port"], "VSS"]
            lo = max(c["bus_spans_um"][n][0] for n in nets)
            hi = min(c["bus_spans_um"][n][1] for n in nets)
            assert hi-lo > .4
            x = round((lo+hi)/2/.005)*.005
            ys = [c["buses_um"][n] for n in nets]
            rect = [x-.2, min(ys)-.2, x+.2, max(ys)+.2]
            layer = layout.layer(42, 0)
            original = k.Region(cell.shapes(layer))
            mutated = original | k.Region(k.DBox(*rect).to_itype(layout.dbu))
        delta = (original ^ mutated).area()*layout.dbu**2
        assert delta > 0
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
    p = argparse.ArgumentParser()
    p.add_argument("--spec", required=True)
    p.add_argument("--run", required=True)
    p.add_argument("--skip-klayout", action="store_true", help="Exploration only")
    args = p.parse_args()
    assert shutil.disk_usage(ROOT).free > 4*1024**3
    target = ROOT / "build/reference-v2-layout" / args.run
    target.mkdir(parents=True, exist_ok=False)
    spec = ROOT / args.spec
    specification = json.loads(spec.read_text())
    shutil.copyfile(spec, target/"selected-spec.json")
    sources = [Path(__file__), Path(__file__).with_name("generate.py"),
               OLD/"run.py", OLD/"audit.py", OLD/"correct_capacitance.py",
               OLD/"generate.py", ROOT/"scripts/highspeed_nrz_layout/run.py"]
    snapshot = target / "source_scripts"
    snapshot.mkdir()
    for i, src in enumerate(sources):
        shutil.copyfile(src, snapshot / f"{i}-{src.name}")
    lock = json.loads((ROOT/"layout/pdk-lock.json").read_text())
    for f, digest in lock["files"].items():
        assert flow.sha(flow.PDK/"gf180mcuD"/f) == digest
    status = {}
    for route, definition in specification["routes"].items():
        c = generate(route, definition, target/"sources")
        out = target/route
        out.mkdir()
        shutil.copytree(target/"sources"/route, out/"source")
        shutil.copyfile(ROOT/definition["schematic_source"], out/"selected-electrical-source.spice")
        gen = out/"generate"
        gen.mkdir()
        text = flow.magic(out/"source/generate.tcl", gen)
        counts = re.findall(r"NRZ_DRC_COUNT (\d+)", text)
        s = status[route] = dict(magic_drc=dict(passed=counts == ["0"], counts=counts))
        flow.write(target/"status.json", status)
        assert s["magic_drc"]["passed"], (route, "native DRC", counts)
        top = c["top"]
        gds = gen/(top+".gds")
        s["lvs"] = flow.lvs(gen/(top+".spice"), out/"source/schematic.spice", top, out)
        assert s["lvs"]["passed"]
        s["readback_drc"] = flow.extract(gds, c, out/"readback", True)
        s["readback_lvs"] = flow.lvs(out/"readback"/(top+".spice"), out/"source/schematic.spice", top, out, "readback-lvs")
        assert s["readback_drc"]["passed"] and s["readback_lvs"]["passed"]
        s["pex_coverage"] = helpers.force_pex(out/"readback", out/"full-rc", c)
        flow.write(target/"status.json", status)
        if not args.skip_klayout:
            s["klayout_drc"] = flow.klayout_drc(gds, c, out)
            flow.write(target/"status.json", status)
            assert s["klayout_drc"]["passed"]
        helpers.correction.correct(out)
        s["pex_audit"] = {k:v for k,v in helpers.audit.audit(out).items()
                          if k in ("passed", "counts", "all_nets_extracted", "full_rc_sha256")}
        s["gds_geometry"] = helpers.geometry_audit(out)
        s["negative_controls"] = negative_controls(out)
        flow.write(target/"status.json", status)
        print(route, s["pex_audit"], flush=True)
    flow.write(target/"correction-provenance.json", dict(
        method="New independently routed reference module; unmodified native RC retained",
        source_hashes={str(s.relative_to(ROOT)):flow.sha(s) for s in sources},
        old_core_sources_and_artifacts_unchanged=True,
        physical_scope="Standalone modules. Intermodule PCB/package connections are external assumptions."))
    files = sorted(p for p in target.rglob("*") if p.is_file())
    assert sum(p.stat().st_size for p in (ROOT/"build/reference-v2-layout").rglob("*") if p.is_file()) < .5*1024**3
    flow.write(target/"artifact-manifest.json", dict(schema_version=1, physical_pdk_lock=lock,
        artifacts=[dict(path=str(p.relative_to(target)),size=p.stat().st_size,sha256=flow.sha(p)) for p in files]))
    print(target, flush=True)


if __name__ == "__main__":
    main()
