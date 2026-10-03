"""Independent DC/terminal audit of the locked six-MOS GF180 cell.

Does not reuse the phase-1 measurement code. Raw decks/logs stay in build.
These are model checks, not silicon/LED or reliability qualification.
"""
from pathlib import Path
import hashlib
import itertools
import json
import math
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "build/audit_mos"
PDK = ROOT / "build/layout/pdk/gf180mcuD/libs.tech/ngspice"
OUT = ROOT / "evidence/review/mos-audit.json"
VARIANTS = {
    "schematic": ROOT / "layout/pixel_driver_schematic.spice",
    "extracted_geometry": ROOT / "evidence/layout/pixel_driver_layout.spice",
    "extracted_rc": ROOT / "evidence/layout/pixel_driver_rc.spice",
}


def devices(path):
    result = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if parts and parts[0].lower().startswith("x"):
            result.append({"instance": parts[0].lower(), "terminals": parts[1:5], "model": parts[5]})
    return result


def run_op(variant, name, corner="typical", temp=27, vlogic=3.3, supply=5,
           on=True, iref=100e-6, fixed_cathode=None):
    folder = RAW / name
    folder.mkdir(parents=True, exist_ok=True)
    for basename in ("design.ngspice", "sm141064.ngspice"):
        link = folder / basename
        if not link.exists():
            link.symlink_to(PDK / basename)
    devs = devices(VARIANTS[variant])
    ports = {"VSS": "0", "bias": "bias", "gate": "gate", "pwm": "pwm", "pwm_b": "pwm_b", "led_k": "led_k", "vlogic": "vlogic"}
    values = []
    def voltage(node):
        return "0" if node == "VSS" else f"v({ports.get(node, 'xpixel.' + node)})"
    for d in devs:
        dname = d["instance"]
        for a, b in ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)):
            label = "dgsb"[a] + "dgsb"[b]
            values.append((f"{dname}_{label}", f"{voltage(d['terminals'][a])} - {voltage(d['terminals'][b])}"))
        for parameter in ("id", "vgs", "vds", "vbs", "vth", "vdsat", "gm", "gds"):
            values.append((f"{dname}_op_{parameter}", f"@m.xpixel.{dname}.m0[{parameter}]"))
    values += [("bias_v", "v(bias)"), ("gate_v", "v(gate)"), ("cathode_v", "v(led_k)"),
               ("pwm_b_v", "v(pwm_b)"), ("current_a", "-i(vdd)"), ("logic_current_a", "-i(vlogic)")]
    # Independently solve the explicit diode equation at 100 uA, 27 C.
    diode_is = 100e-6 / math.expm1((2.8 - 100e-6 * 50) / (3 * 8.617333262145e-5 * 300.15))
    if fixed_cathode is None:
        load = f"VDD led_a 0 {supply}\nDLED led_a led_k LEDMODEL\n.model LEDMODEL D(IS={diode_is:.16g} N=3 RS=50 CJO=2p VJ=2.5 M=.33 TT=1n EG=2.6 TNOM=27)"
    else:
        load = f"VDD led_k 0 {fixed_cathode}"
    lets = "\n".join(f"let {k} = {v}" for k, v in values)
    deck = f"""Independent locked-PDK DC audit: {name}
.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0
.lib sm141064.ngspice {corner}
.include "{VARIANTS[variant]}"
.temp {temp}
{load}
VLOGIC vlogic 0 {vlogic}
IREF vlogic bias {iref}
VPWM pwm 0 {vlogic if on else 0}
XPIXEL 0 bias gate pwm pwm_b led_k vlogic pixel_driver_layout
.options reltol=1e-7 abstol=1e-15 vntol=1e-9
.control
set noaskquit
set numdgt=15
set wr_vecnames
set wr_singlescale
op
{lets}
wrdata op.dat {' '.join(k for k, _ in values)}
quit
.endc
.end
"""
    (folder / "op.spice").write_text(deck)
    proc = subprocess.run(["ngspice", "-b", "op.spice"], cwd=folder, text=True, capture_output=True)
    (folder / "op.log").write_text(proc.stdout + proc.stderr)
    if proc.returncode or "Error" in proc.stdout + proc.stderr:
        raise RuntimeError(f"OP failure: {name}")
    rows = (folder / "op.dat").read_text().splitlines()
    data = dict(zip(rows[0].split()[1:], map(float, rows[1].split()[1:])))
    max_stress = max(abs(data[f"{d['instance']}_{label}"])
                     for d in devs for label in ("dg", "ds", "db", "gs", "gb", "sb"))
    return dict(variant=variant, corner=corner, temperature_c=temp, vlogic_v=vlogic,
                supply_v=supply, pwm_on=on, fixed_cathode_v=fixed_cathode,
                max_any_terminal_difference_v=max_stress, values=data,
                raw_directory=str(folder.relative_to(ROOT)))


def extra_checks():
    """Reproduce LVS negative controls and selected transient stress checks."""
    folder = RAW / "lvs-controls"
    folder.mkdir(exist_ok=True)
    source = VARIANTS["schematic"].read_text()
    variants = {
        "unchanged": source,
        "wrong_width": source.replace("XOUT led_k gate VSS VSS nfet_06v0 w=10u", "XOUT led_k gate VSS VSS nfet_06v0 w=20u"),
        "wrong_gate": source.replace("XOUT led_k gate VSS VSS", "XOUT led_k bias VSS VSS"),
    }
    controls = []
    for name, text in variants.items():
        path, log = folder / f"{name}.spice", folder / f"{name}.log"
        path.write_text(text)
        args = [ROOT / "build/layout/tools/install/bin/netgen", "-batch", "lvs",
                f"{VARIANTS['extracted_geometry']} pixel_driver_layout", f"{path} pixel_driver_layout",
                PDK.parent / "netgen/gf180mcuD_setup.tcl", log]
        proc = subprocess.run(list(map(str, args)), cwd=folder, capture_output=True, text=True)
        (folder / f"{name}-stdout.log").write_text(proc.stdout + proc.stderr)
        controls.append(dict(case=name, exit_code=proc.returncode, report_tail="\n".join(log.read_text().splitlines()[-10:]), log=str(log.relative_to(ROOT))))
    (OUT.parent / "mos-lvs-controls.json").write_text(json.dumps(controls, indent=2) + "\n")
    transients = []
    for name in ("nominal_extracted_rc_off", "matrix_ss_125_3.63_5.5_0", "matrix_ff_-40_3.63_5.5_1"):
        folder = RAW / f"tran_{name}"
        folder.mkdir(exist_ok=True)
        for basename in ("design.ngspice", "sm141064.ngspice"):
            link = folder / basename
            if not link.exists():
                link.symlink_to(PDK / basename)
        source = (RAW / name / "op.spice").read_text()
        vl = re.search(r"VLOGIC vlogic 0 (\S+)", source)[1]
        source = re.sub(r"VPWM pwm 0 .*", f"VPWM pwm 0 PULSE(0 {vl} 1u 10n 10n 64u 256u)", source)
        lets = [line for line in source.splitlines() if line.startswith("let x") and "_op_" not in line]
        measures = []
        for line in lets:
            key = line.split()[1]
            measures.extend((f"meas tran {key}_max MAX {key}", f"meas tran {key}_min MIN {key}"))
        deck = source.split(".control")[0] + ".control\nset noaskquit\nset numdgt=15\ntran 2n 67u 0 2n\n" + "\n".join(lets + measures) + "\nquit\n.endc\n.end\n"
        (folder / "tran.spice").write_text(deck)
        proc = subprocess.run(["ngspice", "-b", "tran.spice"], cwd=folder, text=True, capture_output=True)
        (folder / "tran.log").write_text(proc.stdout + proc.stderr)
        if proc.returncode or "Error" in proc.stdout + proc.stderr:
            raise RuntimeError(f"Transient failure: {name}")
        values = {key: float(value) for key, value in re.findall(r"^(x\w+_[a-z]+_(?:max|min))\s*=\s*([-+\deE.]+)", proc.stdout, re.M)}
        if len(values) != 72:
            raise RuntimeError(f"Incomplete terminal measures: {name}")
        transients.append(dict(name=name, measurements=values, max_terminal_stress_v=max(map(abs, values.values())), condition="synthetic LED; 10 ns edges; 64 us pulse; 2 ns maxstep; DC initial operating point", raw=str(folder.relative_to(ROOT))))
    (OUT.parent / "mos-terminal-transients.json").write_text(json.dumps(transients, indent=2) + "\n")


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / "layout/pdk-lock.json").read_text())
    pdk_checks = {name: hashlib.sha256((PDK.parent.parent / name).read_bytes()).hexdigest() == digest
                  for name, digest in lock["files"].items()}
    if not all(pdk_checks.values()):
        raise RuntimeError("Installed PDK differs from the locked source files")
    nominal = [run_op(v, f"nominal_{v}_{state}", on=(state == "on"))
               for v, state in itertools.product(VARIANTS, ("on", "off"))]
    matrix = []
    for corner, temp, vl, vs, on in itertools.product(
            ("typical", "ff", "ss", "fs", "sf"), (-40, 27, 125), (2.97, 3.3, 3.63), (4.5, 5, 5.5), (False, True)):
        name = f"matrix_{corner}_{temp}_{vl}_{vs}_{int(on)}"
        matrix.append(run_op("extracted_rc", name, corner, temp, vl, vs, on))
    # MOS-only compliance isolates the driver from unmeasured LED assumptions.
    compliance = [run_op("extracted_rc", f"compliance_{vk:.2f}", fixed_cathode=vk)
                  for vk in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1, 1.4, 2.2, 3)]
    on_cases = [c for c in matrix if c["pwm_on"]]
    off_cases = [c for c in matrix if not c["pwm_on"]]
    result = {
        "scope": "independent DC model checks; synthetic LED; no mismatch, transient, power sequencing or silicon qualification",
        "numerics": {"reltol": 1e-7, "abstol_a": 1e-15, "vntol_v": 1e-9, "gmin": "ngspice default (not a physical leakage guarantee)"},
        "pdk_build": lock["open_pdks_commit"], "pdk_file_hash_checks": pdk_checks,
        "audit_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "ngspice_version": subprocess.run(["ngspice", "--version"], capture_output=True, text=True, check=True).stdout,
        "source_hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in VARIANTS.values()},
        "nominal": nominal, "dc_matrix": matrix, "dc_matrix_points": len(matrix), "driver_compliance": compliance,
        "matrix_summary": {
            "on_current_min_uA": min(c["values"]["current_a"] for c in on_cases) * 1e6,
            "on_current_max_uA": max(c["values"]["current_a"] for c in on_cases) * 1e6,
            "off_current_max_pA": max(c["values"]["current_a"] for c in off_cases) * 1e12,
            "max_terminal_difference_v": max(c["max_any_terminal_difference_v"] for c in matrix),
            "bias_min_v": min(c["values"]["bias_v"] for c in matrix),
            "bias_max_v": max(c["values"]["bias_v"] for c in matrix),
        },
        "run_count": len(nominal) + len(matrix) + len(compliance),
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    extra_checks()
    print(json.dumps(result["matrix_summary"], indent=2))
    print(f"Completed {result['run_count']} independent OP solves.")


if __name__ == "__main__":
    main()
