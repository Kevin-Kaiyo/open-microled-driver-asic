"""Copy a successful physical core result into compact, hash-checked evidence."""
from pathlib import Path
import argparse
import json
import shutil
import sys

sys.path.insert(0, str(Path(__file__).parent))
import run as flow

ROOT = flow.ROOT


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run")
    args = p.parse_args()
    raw = ROOT/args.run
    dest = ROOT/"evidence/highspeed-nrz-pex/physical"
    dest.mkdir(parents=True, exist_ok=True)
    status = json.loads((raw/"status.json").read_text())
    copied = []
    routes = {}

    def copy(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert flow.sha(source) == flow.sha(target)
        copied.append(dict(source=str(source.relative_to(ROOT)),
                           published=str(target.relative_to(ROOT)),
                           size=target.stat().st_size, sha256=flow.sha(target)))

    for route in ["A", "B"]:
        src, dst = raw/route, dest/route
        c = json.loads((src/"physical-contract.json").read_text())
        a = json.loads((src/"pex-audit.json").read_text())
        negative = json.loads((src/"negative-controls.json").read_text())
        assert a["passed"] and a["all_nets_extracted"]
        assert all(status[route][key]["passed"] for key in
                   ["magic_drc", "readback_drc", "lvs", "readback_lvs", "klayout_drc"])
        assert len(negative) == 2 and all(v["passed"] for v in negative)
        top = c["top"]
        for name in ["physical-contract.json", "pex-audit.json", "negative-controls.json",
                     "geometry-only.spice", "capacitance-only.spice", "lvs.log",
                     "capacitance-correction.json", "rc-lumped-capacitance.spice",
                     "readback-lvs.log", "rc-collapse-lvs.log", "klayout-result.json",
                     "klayout-command.json", "klayout.log"]:
            copy(src/name, dst/name)
        for source, target in [
            (src/"generate"/(top+".gds"), dst/(top+".gds")),
            (src/"generate"/(top+".mag"), dst/(top+".mag")),
            (src/"full-rc"/(top+"_rc.spice"), dst/(top+"_rc.spice")),
            (src/"full-rc/coverage.json", dst/"coverage.json"),
            (src/"full-rc/drive-attributes.json", dst/"drive-attributes.json"),
            (src/"full-rc/magic.log", dst/"full-rc-magic.log"),
            (src/"readback/magic.log", dst/"readback-magic.log"),
            (src/"generate/magic.log", dst/"generate-magic.log"),
            (src/"klayout"/(top+"_main.lyrdb"), dst/"independent-drc.lyrdb"),
            (src/"source/schematic.spice", dst/"schematic.spice"),
            (src/"unmodified-full-rc"/(top+"_rc.spice"), dst/"invalid-native-control.spice"),
            (src/"readback"/(top+".ext"), dst/"authoritative-readback.ext"),
            (src/"unmodified-full-rc"/(top+".res.ext"), dst/"weights-and-r-network.res.ext"),
            (src/"flat-c-control/flat-c.spice", dst/"native-flat-c-control.spice"),
        ]:
            copy(source, target)
        for control in negative:
            name = control["control"]
            copy(src/"controls"/name/"lvs.log", dst/"controls"/name/"lvs.log")
        # Source directory also carries the final exact geometry mapping.
        copy(src/"physical-contract.json", ROOT/"layout/highspeed_nrz"/route/"physical-contract.json")
        routes[route] = dict(
            top=top, ports=c["ports"], dimensions_um=[c["width_um"], c["height_um"]],
            core_area_um2=c["area_um2"], gds_sha256=c["gds_sha256"],
            counts=a["counts"], extracted_nets=a["extracted_nets"],
            explicit_capacitance_sum_fF=sum(x["farad"] for x in a["capacitors"])*1e15,
            checks=status[route], negative_controls_passed=True,
            full_rc_sha256=a["full_rc_sha256"],
            capacitor_scope=a["capacitor_scope"],
            external_components=c["external_components"])
    for name in ["status.json", "correction-provenance.json"]:
        copy(raw/name, dest/name)
    copy(raw/"artifact-manifest.json", dest/"initial-artifact-manifest.json")
    revision = {}
    if (raw/"wording-revision.json").exists():
        copy(raw/"wording-revision.json", dest/"wording-revision.json")
        revision = json.loads((raw/"wording-revision.json").read_text())
    for relative, wanted in revision.get("unchanged_model_sha256", {}).items():
        assert flow.sha(raw/relative) == wanted
    for item in revision.get("metadata", []):
        copy(raw/item["before_copy"], dest/item["before_copy"])
    if "script_revision" in revision:
        item = revision["script_revision"]
        copy(raw/item["original_snapshot"], dest/"scripts/correct_capacitance.executed.py")
        copy(ROOT/item["current_source"], dest/"scripts/correct_capacitance.wording-revision.py")
        copy(raw/item["diff_path"], dest/"scripts/correct_capacitance.wording.diff")
    artifact_files = sorted(p for p in raw.rglob("*") if p.is_file()
                            and p.name != "current-artifact-manifest.json")
    flow.write(raw/"current-artifact-manifest.json", dict(
        schema_version=1,
        purpose="Current artifact hashes after explanation-only revision; initial manifest retained.",
        artifacts=[dict(path=str(p.relative_to(raw)),size=p.stat().st_size,
                        sha256=flow.sha(p)) for p in artifact_files]))
    copy(raw/"current-artifact-manifest.json", dest/"artifact-manifest.json")
    copy(ROOT/"layout/pdk-lock.json", dest/"pdk-lock.json")
    copy(ROOT/"layout/highspeed_nrz/NOTICE.md", dest/"NOTICE.md")
    lock = json.loads((ROOT/"layout/pdk-lock.json").read_text())
    manifest = dict(
        schema_version=1, raw_run=str(raw.relative_to(ROOT)), routes=routes,
        evidence_level="Routed transistor core GDS; DRC/LVS and Magic extraction; not silicon.",
        rc_model_source="Audited assembly with exact .ext C matrix; not unmodified Magic export.",
        wording_revision=("Simulation input snapshot may contain prior explanatory wording. "
            "All 10 frozen model/GDS hashes are unchanged; before/after metadata hashes retained."
            if revision else None),
        publishing_script_sha256=flow.sha(Path(__file__)),
        pdk=lock,
        actual_tool_versions=dict(magic="8.3.684", netgen="1.5.324",
                                  independent_klayout="0.30.7",
                                  geometry_python_klayout="0.30.12"),
        klayout_scope=dict(variant="D", metal_stack="5LM", metal_top="11K",
                           FEOL=True, BEOL=True, offgrid=True, connectivity=True,
                           DUMMY=False, SLOW_VIA=False),
        limitations=[
            "Core only: no pads, ESD, power generation, physical reference/dummy resistors or package.",
            "Layout is not area/performance optimized; gate is contacted from one end.",
            "All body/supply R/C retained in main model, no signal-only projection.",
            "Magic extraction is not EM/3D/inductive extraction or foundry signoff.",
            "Ground C placement uses allocation weights after Magic R-network simplification; "
            "matrix conservation does not prove spatial accuracy. RCLUMP is the placement control.",
            "Dummy fill, full-chip density, antenna/EM/IR and reliability closure not established.",
            "A ideal VH/VL rails can absorb current; regulators are not implemented.",
            "B WTAIL snapped from 5.75895881652832 to 5.760um on 5nm grid.",
        ],
        published_files=copied)
    flow.write(dest/"summary.json", manifest)
    print(dest/"summary.json")


if __name__ == "__main__":
    main()
