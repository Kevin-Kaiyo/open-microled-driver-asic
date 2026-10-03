"""Generate, verify and extract the standalone one-pixel analog cell."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PDK_HASH = "54435919abffb937387ec956209f9cf5fd2dfbee"


def verify_lvs_report(report):
    """Require connectivity AND property agreement in the pinned Netgen report.

    Netgen can exit zero and print 'Circuits match uniquely.' even when a MOS
    width is wrong. The subsequent property-error section is decisive.
    """
    finals = re.findall(r"^Final result:\s*(.+)$", report, flags=re.MULTILINE)
    if finals != ["Circuits match uniquely."]:
        raise ValueError("LVS did not report one unambiguous unique match")
    if re.search(r"property errors|do not match|not equivalent", report, flags=re.IGNORECASE):
        raise ValueError("LVS reports property or connectivity errors")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdk-root", type=Path, default=ROOT / "build/layout/pdk")
    parser.add_argument("--tools", type=Path, default=ROOT / "build/layout/tools/install/bin")
    parser.add_argument("--publish-evidence", action="store_true")
    args = parser.parse_args()
    pdk = args.pdk_root.resolve()
    lock = json.loads((ROOT / "layout/pdk-lock.json").read_text())
    if lock["open_pdks_commit"] != PDK_HASH:
        raise RuntimeError("Runner and layout PDK lock disagree")
    if f"open_pdks {PDK_HASH}" not in (pdk / "gf180mcuD/SOURCES").read_text():
        raise RuntimeError("PDK build does not match layout/pdk-lock.json")
    for relative, expected in lock["files"].items():
        actual = hashlib.sha256((pdk / "gf180mcuD" / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"Pinned PDK file hash differs: {relative}")
    workroot = ROOT / "build/layout"
    workroot.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="pixel-", dir=workroot))
    generate = run / "generate"
    roundtrip = run / "roundtrip"
    generate.mkdir()
    roundtrip.mkdir()
    env = os.environ | {"PDK_ROOT": str(pdk)}
    magic = args.tools.resolve() / "magic"
    netgen = args.tools.resolve() / "netgen"
    rc = pdk / "gf180mcuD/libs.tech/magic/gf180mcuD.magicrc"
    setup = pdk / "gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl"

    def command(arguments, directory, logname):
        result = subprocess.run([str(a) for a in arguments], cwd=directory, env=env,
                                capture_output=True, text=True)
        (run / logname).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Exit {result.returncode}; inspect {run / logname}")
        return result.stdout + result.stderr

    def magic_run(script, directory, logname):
        return command([magic, "-dnull", "-noconsole", "-rcfile", rc,
                        ROOT / "scripts/layout" / script], directory, logname)

    magic_version = command([magic, "--version"], ROOT, "magic-version.log").strip()
    netgen_version = command([netgen, "-batch", "quit"], ROOT, "netgen-version.log").strip()
    if magic_version != lock["tools"]["magic"]["version"] or f'Netgen {lock["tools"]["netgen"]["version"]}' not in netgen_version:
        raise RuntimeError(f"Physical tool version differs from layout lock; inspect {run}")
    ngspice_version = command(["ngspice", "--version"], ROOT, "ngspice-version.log").strip()
    iverilog_version = command(["iverilog", "-V"], ROOT, "iverilog-version.log").strip()

    generation_log = magic_run("generate_pixel.tcl", generate, "magic-generate.log")
    if "PIXEL_DRC_COUNT 0" not in generation_log or 'DRC style is now "drc(full)"' not in generation_log:
        raise RuntimeError(f"Magic DRC did not report zero; inspect {run}")
    command([netgen, "-batch", "lvs", f"{generate / 'pixel_driver_layout.spice'} pixel_driver_layout",
             f"{ROOT / 'layout/pixel_driver_schematic.spice'} pixel_driver_layout", setup,
             run / "netgen-lvs.log"], generate, "netgen-lvs-stdout.log")
    verify_lvs_report((run / "netgen-lvs.log").read_text())
    env["LAYOUT_GDS"] = str(generate / "pixel_driver_layout.gds")
    roundtrip_log = magic_run("roundtrip.tcl", roundtrip, "magic-roundtrip.log")
    if "ROUNDTRIP_DRC_COUNT 0" not in roundtrip_log or 'DRC style is now "drc(full)"' not in roundtrip_log:
        raise RuntimeError(f"GDS roundtrip DRC did not report zero; inspect {run}")
    command([netgen, "-batch", "lvs", f"{roundtrip / 'pixel_driver_layout.spice'} pixel_driver_layout",
             f"{ROOT / 'layout/pixel_driver_schematic.spice'} pixel_driver_layout", setup,
             run / "netgen-roundtrip-lvs.log"], roundtrip, "netgen-roundtrip-lvs-stdout.log")
    verify_lvs_report((run / "netgen-roundtrip-lvs.log").read_text())
    pex_log = magic_run("extract_pixel.tcl", generate, "magic-pex.log")
    if "Nets extracted: 7 (1.000000)" not in pex_log:
        raise RuntimeError(f"RC extraction did not cover all seven nets; inspect {run}")
    command([ROOT / "build/layout/venv/bin/python", ROOT / "scripts/layout/run_postlayout.py",
             "--pdk-root", pdk, "--rc-netlist", generate / "pixel_driver_rc.spice",
             "--output", run / "postlayout"], ROOT, "postlayout-regression.log")
    summary = json.loads((run / "postlayout/summary.json").read_text())
    summary["pdk_lock"] = lock
    summary["host"] = dict(system=platform.system(), release=platform.release(),
                           architecture=platform.machine(), python=platform.python_version())
    summary["tool_versions"] = dict(magic=magic_version, netgen=netgen_version.splitlines()[0],
                                    ngspice=ngspice_version, iverilog=iverilog_version.splitlines()[0])
    summary["physical_checks"] = dict(magic_drc_count=0, netgen_lvs="unique match",
                                      gds_roundtrip_drc_count=0, gds_roundtrip_lvs="unique match",
                                      lvs_property_errors=False, gds_roundtrip_lvs_property_errors=False,
                                      magic_drc_style="drc(full)", rc_nets_extracted=7, rc_nets_total=7)
    summary["lvs_property_scope"] = "Connectivity, model classes and W/L with pinned deck tolerance; AD/AS/PD/PS and other deleted geometry properties are not compared"
    netlist_lines = (generate / "pixel_driver_rc.spice").read_text().splitlines()
    summary["extracted_counts"] = {name: sum(line.startswith(prefix) for line in netlist_lines)
                                    for name, prefix in (("mos", "X"), ("resistors", "R"), ("capacitors", "C"))}
    summary["run_directory"] = str(run.relative_to(ROOT))
    summary["external_signoff"] = False
    source_suffixes = {".py", ".tcl", ".sh", ".txt", ".spice", ".json"}
    summary["source_hashes"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for folder in (ROOT / "scripts/layout", ROOT / "layout")
                               for p in sorted(folder.rglob("*")) if p.is_file() and p.suffix in source_suffixes
                               and "__pycache__" not in p.parts
                               and not any(part.startswith(".") for part in p.relative_to(ROOT).parts)}
    for relative in ("rtl/pixel_pwm.v", "sim/rtl/tb_pixel_pwm.v", "scripts/run_phase1.py",
                     "scripts/fetch_models.py", "analog/models/microled.spice"):
        summary["source_hashes"][relative] = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    summary["output_hashes"] = {name: hashlib.sha256((generate / name).read_bytes()).hexdigest()
                                for name in ("pixel_driver_layout.mag", "pixel_driver_layout.gds",
                                             "pixel_driver_layout.spice", "pixel_driver_rc.spice")}
    (run / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if args.publish_evidence:
        dest = ROOT / "evidence/layout"
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("magic-generate.log", "magic-roundtrip.log", "magic-pex.log", "netgen-lvs.log",
                     "netgen-roundtrip-lvs.log", "postlayout-regression.log", "summary.json",
                     "magic-version.log", "netgen-version.log", "ngspice-version.log", "iverilog-version.log"):
            shutil.copyfile(run / name, dest / name)
        for name in ("pixel_driver_layout.gds", "pixel_driver_layout.spice", "pixel_driver_rc.spice"):
            shutil.copyfile(generate / name, dest / name)
        shutil.copyfile(generate / "pixel_driver_layout.mag", ROOT / "layout/pixel_driver_layout.mag")
        command([ROOT / "build/layout/venv/bin/python", ROOT / "scripts/layout/render_layout.py",
                 "--gds", generate / "pixel_driver_layout.gds"], ROOT, "render-layout.log")
    print(f"PASS standalone cell DRC/LVS, GDS roundtrip, 7/7 RC nets, paired regression; {run}")


if __name__ == "__main__":
    main()
