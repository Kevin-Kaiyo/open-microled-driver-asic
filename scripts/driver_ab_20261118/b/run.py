#!/usr/bin/env python3
"""Reproduce the frozen B testbench and modify only the named circuit parameters."""
import argparse
import fcntl
import importlib.util
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / "build/driver-ab-20261118/b"
BASE_SCRIPT = ROOT / "scripts/driver_pvt_20261117/b/run.py"
spec = importlib.util.spec_from_file_location("pvt_b", BASE_SCRIPT)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
template = base.prepare
baseline = "clamp5v_buffer_soft"
base.BUILD = STAGE / "_templates"
source_bytes = Path(__file__).read_bytes()
# Resistance in kiloohms, explicit added IB1 load in fF, length-matched mirror.
variants = {
    "original": (100, 0, False),
    "reconnect220": (220, 0, False),
    "reconnect470": (470, 0, False),
    "buffer10": (100, 10, False),
    "combined220c10": (220, 10, False),
    "merged220c10": (220, 10, True),
    "merged220c10r260": (220, 10, True),
    "merged220c4r260": (220, 4, True),
    "merged220c10r260ff36": (220, 10, True),
    "merged220c10r260n4ff36": (220, 10, True),
    "merged220c10r260n4": (220, 10, True),
}
def change_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected one occurrence: {old!r}")
    return text.replace(old, new)

def prepare(variant, grid, mode, level=None, steps=40):
    resistance, load, matched = variants[variant]
    work = STAGE / variant
    work.mkdir(parents=True, exist_ok=True)
    with (STAGE / ".prepare.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        src, m = template(baseline, grid, mode, level, steps)
        folder = work / src.name
        if (folder / "manifest.json").exists():
            m = base.read(folder / "manifest.json")
            assert base.sha(folder / "testbench.spice") == m["deck_sha256"]
            assert all(base.sha(work / "inputs" / name) == digest for name,digest in m["inputs"].items())
            return folder, m
        unit_source = ROOT / "build/driver-pvt-20261117/b/unit_long_trim/inputs/route_b.spice"
        if not (work / "inputs").exists():
            shutil.copytree(src.parent / "inputs",work / "inputs")
            if matched:
                route = work / "inputs/route_b.spice"
                shutil.copy2(unit_source,route)
                if "r260n4" in variant:
                    reference = next(line for line in route.read_text().splitlines() if line.startswith("XINV2N "))
                    replacement = base.prior.mos("XINV2N", "GP", "GB", "VSS", "VSS", "nfet_03v3", 4, .28)
                    route.write_text(change_once(route.read_text(), reference, replacement))
                if variant.endswith("ff36"):
                    value = int(variant[-2:])
                    route.write_text(change_once(route.read_text(), "CFF GB OUT 31.275f", f"CFF GB OUT {value}f"))
        folder.mkdir()
        text = (src / "testbench.spice").read_text()
        m["case"]["variant"] = variant
        m["inputs"] = {str(p.relative_to(work/"inputs")):base.sha(p) for p in sorted((work/"inputs").rglob("*")) if p.is_file()}
        m["circuit_change"] = dict(RGATE_kohm=resistance, CIB1_fF=load, long_unit_mirror=matched,
            freeze_source="scripts/driver_pvt_20261117/b/run.py", freeze_source_sha256=base.sha(BASE_SCRIPT))
        text = change_once(text, "RGATE iso_g iso_p 100k", f"RGATE iso_g iso_p {resistance}k")
        if load:
            m.setdefault("extra_caps", []).append(["CIB1", load * 1e-15, "ib1", "0"])
            text = change_once(text, "RCLAMP iso_g clamp_g 200k", f"CIB1 ib1 0 {load}f\nRCLAMP iso_g clamp_g 200k")
        if "r260n4" in variant:
            m["circuit_change"]["XINV2N_W_um"] = 4
        if "r260" in variant:
            text = change_once(text, "RCLAMP iso_g clamp_g 200k", "RCLAMP iso_g clamp_g 260k")
            m["circuit_change"]["RCLAMP_kohm"] = 260
        if variant.endswith("ff36"):
            value = int(variant[-2:])
            m["circuit_change"]["CFF_fF"] = value
            m.setdefault("extra_caps", []).append(["CFF", value * 1e-15, "xdrv.gb", "out"])
        if matched:
            m["parameters"]["RSET"] *= .9925
            text,n = re.subn(r"(?m)^(XDRV .+ RSET=)\S+",lambda q:q.group(1)+f'{m["parameters"]["RSET"]:.16g}',text)
            assert n == 1
            tail = next(d for d in m["devices"] if d["instance"] == "xdrv.xtail")
            m["devices"] += [dict(tail,instance="xdrv.xtail1"),dict(tail,instance="xdrv.xtail2")]
            if mode != "dc":
                begin,end = text.index("let fs0x0="),text.index("wrdata waveform.dat")
                text = text[:begin]+base.prior.stress_commands(m["devices"])+"\n"+text[end:]
        (folder / "testbench.spice").write_text(text)
        (folder / "execution-source.py").write_bytes(source_bytes)
        shutil.copy2(src / "stimulus.json", folder / "stimulus.json")
        shutil.copytree(src / "execution-sources", folder / "execution-sources")
        helper = folder / "execution-sources/5-pvt_b_run.py"
        shutil.copy2(BASE_SCRIPT, helper)
        m["execution_helpers"][str(BASE_SCRIPT.relative_to(ROOT))] = {"path":str(helper.relative_to(folder)), "sha256":base.sha(helper)}
        m.update(template_manifest_sha256=base.sha(src / "manifest.json"),template_deck_sha256=base.sha(src / "testbench.spice"),deck_sha256=base.sha(folder/"testbench.spice"),execution_sha256=base.sha(folder/"execution-source.py"))
        base.emit(folder/"manifest.json",m)
    return folder,m

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("variant", choices=variants)
    p.add_argument("--grid", default="tt")
    p.add_argument("--mode", choices=["assert","release","normal1","continuous","full","dc"], default="release")
    p.add_argument("--steps", type=int, default=40)
    a = p.parse_args()
    base.prepare = prepare
    for grid in base.GRID if a.grid=="all" else a.grid.split(","):
        for level in [0,1] if a.mode=="dc" else [None]:
            base.run(a.variant,grid,a.mode,level,a.steps)
