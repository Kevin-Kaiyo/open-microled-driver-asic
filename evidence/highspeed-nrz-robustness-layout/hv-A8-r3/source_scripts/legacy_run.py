"""Reproduce NRZ core GDS, DRC/LVS, GDS-readback C/RC and negative controls."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PDK = ROOT / "build/layout/pdk"
TOOLS = ROOT / "build/layout/tools/install/bin"
MAGICRC = PDK / "gf180mcuD/libs.tech/magic/gf180mcuD.magicrc"
SETUP = PDK / "gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl"
ENV = os.environ | {"PDK_ROOT": str(PDK)}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, value):
    Path(p).write_text(json.dumps(value, indent=2) + "\n")


def command(args, cwd, log):
    args = list(map(str, args))
    r = subprocess.run(args, cwd=cwd, env=ENV, capture_output=True, text=True)
    Path(log).write_text(r.stdout + r.stderr)
    write(str(log) + ".command.json",
          dict(argv=args, cwd=str(cwd), exit_code=r.returncode))
    if r.returncode:
        raise RuntimeError(f"{log}: exit {r.returncode}")
    return r.stdout + r.stderr


def magic(tcl, out):
    return command([TOOLS / "magic", "-dnull", "-noconsole", "-rcfile",
                    MAGICRC, tcl], out, out / "magic.log")


def lvs(extracted, schematic, top, out, name="lvs"):
    log = out / (name + ".log")
    command([TOOLS / "netgen", "-batch", "lvs",
             f"{extracted} {top}", f"{schematic} {top}", SETUP, log],
            out, out / (name + "-stdout.log"))
    text = log.read_text()
    final = re.findall(r"^Final result:\s*(.+)$", text, re.M)
    passed = (final == ["Circuits match uniquely."] and
              not re.search(r"property errors|do not match|not equivalent", text, re.I))
    return dict(passed=bool(passed), final_result=final, log=str(log.relative_to(ROOT)))


def readback_tcl(gds, c, pex=False):
    top = c["top"]
    lines = [f"gds read {gds}", f"load {top}", "select top cell"]
    for i, n in enumerate(c["ports"], 1):
        x, y = c["port_anchor_um"][n]
        lines += [f"box values {x-.1}um {y-.1}um {x+.1}um {y+.1}um",
                  f"label {n} center metal3", f"port make {i}"]
    lines += ["drc style drc(full)", "drc check", "drc catchup",
              'puts "NRZ_DRC_COUNT [drc list count total]"',
              'puts "NRZ_DRC_ERRORS [drc listall why]"',
              f"save {top}", "extract all", "ext2spice lvs", "ext2spice"]
    if pex:
        lines += ["extract style ngspice()", "extract do capacitance",
                  "extract do coupling", "extract do resistance", "extract all",
                  "ext2spice lvs", "ext2spice cthresh 0", "ext2spice rthresh 0",
                  "ext2spice extresist off", f"ext2spice -o {top}_c.spice",
                  "extresist threshold 0", "extresist minres 0",
                  "extresist mindelay 0", "extresist all", "ext2spice extresist on",
                  f"ext2spice -o {top}_rc.spice"]
    return "\n".join(lines + ["quit -noprompt"]) + "\n"


def extract(gds, c, out, pex=False):
    out.mkdir(parents=True, exist_ok=False)
    tcl = out / "extract.tcl"
    tcl.write_text(readback_tcl(gds, c, pex))
    text = magic(tcl, out)
    count = re.findall(r"NRZ_DRC_COUNT (\d+)", text)
    return dict(passed=count == ["0"], counts=count)


def force_pex(base, out, c):
    """Annotate all extraction nodes with documented res:drive, geometry intact."""
    out.mkdir()
    top = c["top"]
    shutil.copyfile(base / (top + ".mag"), out / (top + ".mag"))
    original = (base / (top + ".ext")).read_text()
    nodes = []
    lines = []
    for line in original.splitlines():
        lines.append(line)
        m = re.match(r'^node "([^"]+)" \S+ \S+ (\S+) (\S+) (\S+)', line)
        if m:
            n, x, y, layer = m.groups()
            nodes.append(dict(node=n, x=int(x), y=int(y), layer=layer))
            lines.append(f'attr "{n}" {x} {y} {int(x)+1} {int(y)+1} {layer} "res:drive"')
    annotated = "\n".join(lines) + "\n"
    (out / (top + ".ext")).write_text(annotated)
    write(out / "drive-attributes.json", dict(
        nodes=nodes, node_count=len(nodes), geometry_mutated=False,
        original_ext_sha256=sha(base / (top + ".ext")),
        annotated_ext_sha256=sha(out / (top + ".ext")),
        annotation="Documented Magic res:drive; original node coordinates/layer"))
    tcl = out / "extract-driven.tcl"
    tcl.write_text(f"""load {top}
select top cell
extract style ngspice()
extresist threshold 0
extresist minres 0
extresist mindelay 0
extresist all
ext2spice lvs
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice -o {top}_rc.spice
quit -noprompt
""")
    text = magic(tcl, out)
    extracted = re.findall(r"^Extracting (\S+)\s*$", text, re.M)
    total = re.findall(r"Nets extracted:\s*(\d+)\s*\(([^)]+)\)", text)
    clean = "\n".join(x for x in annotated.splitlines()
                      if not (x.startswith("attr ") and '"res:drive"' in x)) + "\n"
    result = dict(node_count=len(nodes), extracted_nodes=extracted,
                  extracted_count=len(extracted), extraction_statistics=total,
                  only_attributes_added=clean == original,
                  original_ext_nodes=[n["node"] for n in nodes])
    write(out / "coverage.json", result)
    return result


def klayout_drc(gds, c, out):
    deck = PDK / "gf180mcuD/libs.tech/klayout/tech/drc/run_drc.py"
    image = "ghcr.io/librelane/librelane@sha256:f91b21d75f79871f9ccf37451020b5d2f7b3236881a997ff709c561e8280a30f"
    args = ["limactl", "shell", "asic", "nerdctl", "run", "--rm",
            "-v", f"{ROOT}:{ROOT}", "-w", str(out), "-e", "QT_QPA_PLATFORM=offscreen",
            "-e", f"PYTHONPATH={ROOT}/build/physical-flow/linux-python", "-e",
            f"PDK_ROOT={PDK}", image, "python3", str(deck), f"--path={gds}",
            "--variant=D", f"--topcell={c['top']}", "--mp=1", "--thr=4",
            f"--run_dir={out}/klayout"]
    env = ENV | {"LIMA_HOME": str(ROOT / "build/physical-flow/lima")}
    with (out / "klayout.log").open("w") as f:
        r = subprocess.run(args, env=env, stdout=f, stderr=subprocess.STDOUT)
    write(out / "klayout-command.json", dict(argv=args, exit_code=r.returncode,
          image=image, deck_sha256=sha(deck), main_deck_sha256=sha(deck.parent/"gf180mcu.drc")))
    if r.returncode:
        raise RuntimeError("Independent DRC execution failed")
    xml = out / "klayout" / f"{c['top']}_main.lyrdb"
    items = ET.parse(xml).findall(".//item")
    cats = {}
    for item in items:
        key = item.findtext("category")
        cats[key] = cats.get(key, 0) + 1
    result = dict(passed=not items, item_count=len(items), categories=cats)
    write(out / "klayout-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run")
    parser.add_argument("--route", choices=["A", "B", "both"], default="both")
    parser.add_argument("--skip-klayout", action="store_true")
    args = parser.parse_args()
    run = ROOT / "build/highspeed-nrz-layout" / (
        args.run or datetime.datetime.now().strftime("run-%Y%m%d-%H%M%S"))
    run.mkdir(parents=True, exist_ok=False)
    lock = json.loads((ROOT / "layout/pdk-lock.json").read_text())
    for f, expected in lock["files"].items():
        if sha(PDK / "gf180mcuD" / f) != expected:
            raise RuntimeError("Pinned PDK mismatch: " + f)
    command([sys.executable, Path(__file__).with_name("generate.py")],
            ROOT, run / "generator.log")
    results = {}
    for route in (["A", "B"] if args.route == "both" else [args.route]):
        source = ROOT / "layout/highspeed_nrz" / route
        c = json.loads((source / "contract.json").read_text())
        out = run / route
        out.mkdir()
        shutil.copytree(source, out / "source")
        source = out / "source"
        gen = out / "generate"
        gen.mkdir()
        text = magic(source / "generate.tcl", gen)
        drc = re.findall(r"NRZ_DRC_COUNT (\d+)", text)
        result = dict(magic_drc=dict(passed=drc == ["0"], counts=drc))
        results[route] = result
        write(run / "status.json", results)
        if drc != ["0"]:
            raise RuntimeError(f"{route} generated DRC {drc}")
        top = c["top"]
        gds = gen / (top + ".gds")
        result["lvs"] = lvs(gen/(top+".spice"), source/"schematic.spice", top, out)
        if not result["lvs"]["passed"]:
            raise RuntimeError(f"{route} generated LVS failed")
        result["readback_drc"] = extract(gds, c, out / "readback", True)
        result["readback_lvs"] = lvs(out/"readback"/(top+".spice"),
            source/"schematic.spice", top, out, "readback-lvs")
        result["pex_coverage"] = force_pex(out/"readback", out/"full-rc", c)
        if not args.skip_klayout:
            result["klayout_drc"] = klayout_drc(gds, c, out)
        write(run / "status.json", results)
        print(route, json.dumps(result), flush=True)
    print(run, flush=True)


if __name__ == "__main__":
    main()
