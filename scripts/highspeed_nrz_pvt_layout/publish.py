"""Publish an allowlisted, byte-preserved physical evidence package.

No PDK sources, tool binaries or raw transient waveforms are copied. The raw run
and previous revision are never changed. Repeating this command is idempotent
only when existing destination bytes already agree.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    data = (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == data, f"Refusing to replace different evidence: {path}"
    else:
        path.write_bytes(data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", default="build/highspeed-nrz-pvt-layout/final-r4")
    p.add_argument("--out", default="evidence/highspeed-nrz-pvt/physical")
    args = p.parse_args()
    raw, dest = ROOT / args.run, ROOT / args.out
    status = json.loads((raw / "status.json").read_text())
    specification = json.loads((raw / "selected-spec.json").read_text())
    metrics = json.loads((raw.parent / "final-metrics.json").read_text())
    for route in ("A", "B"):
        assert (ROOT / metrics["routes"][route]["final"]["directory"]).resolve() == (raw / route).resolve(), \
            "Metrics must be regenerated for the selected run before publication"
    entries = []

    def copy(source, relative):
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert sha(target) == sha(source), f"Refusing to replace different evidence: {target}"
        else:
            shutil.copyfile(source, target)
        entries.append(dict(source=str(source.relative_to(ROOT)), published=str(target.relative_to(ROOT)),
                            size=target.stat().st_size, sha256=sha(target)))

    for name in ("selected-spec.json", "status.json", "correction-provenance.json"):
        copy(raw / name, name)
    copy(raw / "artifact-manifest.json", "raw-run-manifest.json")
    for source in sorted((raw / "source_scripts").iterdir()):
        copy(source, "scripts/" + source.name)
    for name in ("final-metrics.json", "substrate-transfer-final.json"):
        copy(raw.parent / name, name)
    for source in sorted((raw.parent / "resistor-dc").rglob("*")):
        if source.is_file():
            copy(source, "resistor-dc/" + str(source.relative_to(raw.parent / "resistor-dc")))
    # Failed first physical candidate is a compact, inspectable negative result.
    # Its original raw files remain in build/ for the milestone Release archive.
    failed = raw.parent / "poly58-r1"
    copy(failed / "status.json", "failed-poly58-r1/status.json")
    routes = {}
    for route in ("A", "B"):
        folder = raw / route
        contract = json.loads((folder / "physical-contract.json").read_text())
        audit = json.loads((folder / "pex-audit.json").read_text())
        top = contract["top"]
        for check in ("magic_drc", "readback_drc", "lvs", "readback_lvs", "klayout_drc"):
            assert status[route][check]["passed"], f"{route}: {check}"
        assert audit["passed"] and audit["rc_collapse_lvs"]["passed"]
        for name in ("physical-contract.json", "pex-audit.json", "capacitance-correction.json",
                     "gds-geometry-audit.json", "negative-controls.json", "geometry-only.spice",
                     "capacitance-only.spice", "rc-lumped-capacitance.spice",
                     "selected-electrical-source.spice", "lvs.log", "readback-lvs.log",
                     "rc-collapse-lvs.log", "klayout-command.json", "klayout-result.json", "klayout.log"):
            copy(folder / name, route + "/" + name)
        aliases = {
            "generate/"+top+".gds": top+".gds",
            "generate/"+top+".mag": top+".mag",
            "generate/"+top+".spice": "native-extracted.spice",
            "generate/magic.log": "native-magic.log",
            "readback/magic.log": "readback-magic.log",
            "readback/"+top+".ext": "authoritative-readback.ext",
            "readback/"+top+".spice": "readback-extracted.spice",
            "full-rc/"+top+"_rc.spice": top+"_rc.spice",
            "full-rc/"+top+".res.ext": "allocation-weights.res.ext",
            "full-rc/coverage.json": "extraction-coverage.json",
            "full-rc/drive-attributes.json": "drive-attributes.json",
            "full-rc/extract-driven.tcl": "extract-driven.tcl",
            "full-rc/magic.log": "full-rc-magic.log",
            "unmodified-full-rc/"+top+"_rc.spice": "invalid-native-control.spice",
            "flat-c-control/flat-c.spice": "native-flat-c-control.spice",
            "klayout/"+top+"_main.lyrdb": "klayout-main.lyrdb",
        }
        for source, target in aliases.items():
            copy(folder / source, route + "/" + target)
        for source in sorted((folder / "source").iterdir()):
            copy(source, route + "/source/" + source.name)
        for control in ("input-gate-open", "vdd-vss-short"):
            for name in (top+".gds", "lvs.log", "extract/magic.log", "extract/"+top+".spice"):
                copy(folder / "controls" / control / name, route + "/controls/" + control + "/" + name)
        for name in ("physical-contract.json", "pex-audit.json", "capacitance-correction.json"):
            copy(failed / route / name, "failed-poly58-r1/" + route + "/" + name)
        for source, target in (("generate/"+top+".gds", top+".gds"),
                               ("full-rc/"+top+"_rc.spice", top+"_rc.spice"),
                               ("readback/"+top+".ext", "authoritative-readback.ext")):
            copy(failed / route / source, "failed-poly58-r1/" + route + "/" + target)
        routes[route] = dict(top=top, checks=status[route], counts=audit["counts"],
                             complete_electrical_net_count=audit["expected_nets"],
                             gds_sha256=contract["gds_sha256"], rc_sha256=audit["full_rc_sha256"])
    # The public input is the exact frozen specification used by the flow.
    public_spec = ROOT / "layout/highspeed_nrz_pvt/selected-design.json"
    public_spec.parent.mkdir(parents=True, exist_ok=True)
    if public_spec.exists():
        assert sha(public_spec) == sha(raw / "selected-spec.json")
    else:
        shutil.copyfile(raw / "selected-spec.json", public_spec)
    summary = dict(schema_version=1, raw_run=args.run, scope="Experimental transistor cores; not tape-out signoff",
        selected_public_spec=str(public_spec.relative_to(ROOT)), selected_spec_sha256=sha(public_spec),
        routes=routes,
        resistor_count_definition="One designed three-terminal PDK XR per route, separate from the R-prefix extracted interconnect resistor count. Compact-device internal R/C are not counted as explicit PEX elements.",
        coverage_count_note="Frozen force_pex node_count counts node records excluding the substrate record; extracted_nets/expected_nets include VSS and are the authoritative complete electrical-net counts (A=9,B=10).",
        limitations=["The 6 V high-R poly compact model is retained intact alongside 3.3 V MOS models.",
            "Corrected RC is explicit capacitance assembly, not unmodified Magic output or a 3D field solution.",
            "Ground C uses post-simplification allocation weights; DATA has no weights/couplings so its exact C is explicitly lumped at DATA. RCLUMP is a spatial-allocation sensitivity control.",
            "PVT electrical verdicts are published separately. Physical checks alone do not prove receiver/stress/energy requirements.",
            "No pad/ESD, full-chip density/antenna, EM/IR, package, silicon or optical signoff."],
        published_files=sorted(entries, key=lambda x: x["published"]))
    write(dest / "summary.json", summary)
    artifacts = sorted(p for p in dest.rglob("*") if p.is_file() and p.name != "artifact-manifest.json")
    write(dest / "artifact-manifest.json", dict(schema_version=1, artifacts=[dict(
        path=str(p.relative_to(dest)), size=p.stat().st_size, sha256=sha(p)) for p in artifacts]))
    print(json.dumps(dict(published=str(dest.relative_to(ROOT)), files=len(artifacts),
                          bytes=sum(p.stat().st_size for p in artifacts)), indent=2))


if __name__ == "__main__":
    main()
