"""Characterize assumptions without changing the one-pixel baseline.

Uses the locked full-PDK RC netlist, executed RTL events, and an explicitly
synthetic LED. The ranges are engineering probes, not qualified specifications.
"""
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
FRAME = 256e-6
LEFT, RIGHT, STOP = 514.5e-6, 1538.5e-6, 1540.5e-6


def run(command, folder, log):
    process = subprocess.run([str(x) for x in command], cwd=folder, capture_output=True, text=True)
    (folder / log).write_text(process.stdout + process.stderr)
    if process.returncode:
        raise RuntimeError(f"Command exit {process.returncode}: {folder / log}")
    return process.stdout


def integral(t, values, left=LEFT, right=RIGHT):
    if t[0] > left or t[-1] < right or np.any(np.diff(t) <= 0):
        raise ValueError("Incomplete or nonmonotonic solver output")
    inside = (t > left) & (t < right)
    x = np.r_[left, t[inside], right]
    y = np.r_[np.interp(left, t, values), values[inside], np.interp(right, t, values)]
    return float(np.sum(np.diff(x) * (y[:-1] + y[1:]) * 0.5))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish-evidence", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    lock = json.loads((ROOT / "layout/pdk-lock.json").read_text())
    pdk = ROOT / "build/layout/pdk/gf180mcuD"
    for file, expected in lock["files"].items():
        if hashlib.sha256((pdk / file).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"PDK hash differs: {file}")
    (ROOT / "build/review").mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="sensitivity-", dir=ROOT / "build/review"))
    # Freeze inputs before concurrent runs; an unrelated layout regeneration may
    # otherwise replace the included RC file while this sweep is in flight.
    source_files = ["scripts/review/sensitivity_audit.py", "rtl/pixel_pwm.v",
                    "sim/rtl/tb_pixel_pwm.v", "evidence/layout/pixel_driver_rc.spice",
                    "layout/pdk-lock.json"]
    source_hashes = {}
    for name in source_files:
        target = work / "inputs" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        source_hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    ngspice_version = run(["ngspice", "--version"], work, "ngspice-version.log")
    binary = work / "pixel_pwm.vvp"
    run(["iverilog", "-g2012", "-s", "tb_pixel_pwm", "-o", binary,
         work / "inputs/rtl/pixel_pwm.v", work / "inputs/sim/rtl/tb_pixel_pwm.v"], work, "rtl-compile.log")
    events = {}
    for duty in (0, 1, 64, 256):
        target = work / f"events-{duty}.csv"
        trace = run(["vvp", binary, f"+OUT={target}", f"+DUTY={duty}", "+ENABLE=1", "+TRACE_ONLY=1"],
                    work, f"rtl-{duty}.log")
        if "measure_start_ns=514500 measure_end_ns=1538500" not in trace:
            raise RuntimeError("RTL window drift")
        with target.open() as stream:
            events[duty] = [(float(x["time_ns"])*1e-9, int(x["pwm"])) for x in csv.DictReader(stream)]
    defaults = dict(corner="typical", temperature_c=27, vlogic_v=3.3, duty=1,
                    cjo_pF=2.0, tt_ns=1.0, slew_ns=10.0, maxstep_ns=200.0, gmin=1e-12)
    cases = []
    for corner, temp, logic, duty in product(("typical", "ff", "ss", "fs", "sf"),
                                           (0, 27, 85), (2.97, 3.3, 3.63), (1, 64, 256)):
        cases.append(defaults | dict(group="matrix", name=f"{corner}_t{temp}_v{logic:.2f}_d{duty}",
                                     corner=corner, temperature_c=temp, vlogic_v=logic, duty=duty))
    for key, values in (("cjo_pF", (0.2, 20.0)), ("tt_ns", (0.0, 10.0)), ("slew_ns", (1.0, 100.0))):
        for value, duty in product(values, (1, 64, 256)):
            cases.append(defaults | {"group": "sensitivity", "name": f"{key}_{value}_d{duty}",
                                     key: value, "duty": duty})
    # Fine-step repeats test numerical stability of the shortest PWM pulse.
    for corner, temp, logic in (("typical", 27, 3.3), ("ss", 85, 2.97), ("sf", 85, 2.97)):
        cases.append(defaults | dict(group="refinement", name=f"fine_{corner}_t{temp}_v{logic:.2f}",
                                     corner=corner, temperature_c=temp, vlogic_v=logic, maxstep_ns=20.0))
    for gmin in (1e-9, 1e-12, 1e-15):
        cases.append(defaults | dict(group="gmin", name=f"off_gmin_{gmin:.0e}", duty=0, gmin=gmin))
    diode_is = 100e-6 / math.expm1((2.8 - 100e-6*50)/(3*8.617333262145e-5*300.15))

    def simulate(case):
        folder = work / case["name"]
        folder.mkdir()
        for name in ("design.ngspice", "sm141064.ngspice"):
            (folder / name).symlink_to(os.path.relpath(pdk / "libs.tech/ngspice" / name, folder))
        # Changes to CJO or TT must leave the DC calibration anchor unchanged.
        (folder / "led.spice").write_text(
            ".subckt microled anode cathode\nDLED anode cathode LED_SYNTHETIC\n"
            f".model LED_SYNTHETIC D (IS={diode_is:.16g} N=3 RS=50 CJO={case['cjo_pF']}p "
            f"VJ=2.5 M=0.33 TT={case['tt_ns']}n EG=2.6 TNOM=27)\n.ends microled\n")
        points, previous = [(0.0, 0.0)], 0
        for stamp, value in events[case["duty"]]:
            if value != previous:
                points.extend([(stamp, previous*case["vlogic_v"]),
                               (stamp+case["slew_ns"]*1e-9, value*case["vlogic_v"])])
                previous = value
        points.append((STOP, previous*case["vlogic_v"]))
        if any(b[0] <= a[0] for a, b in zip(points, points[1:])):
            raise RuntimeError("PWL ramp overlap")
        pwl = "\n".join(f"+ {t:.15g} {v:.15g}" for t, v in points)
        deck = f"""One-pixel full-PDK RC assumption characterization
.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0
.lib sm141064.ngspice {case['corner']}
.include led.spice
.include "{work / 'inputs/evidence/layout/pixel_driver_rc.spice'}"
.temp {case['temperature_c']}
VDD vdd 0 5
VLOGIC vlogic 0 {case['vlogic_v']}
IREF vlogic bias DC 100u
VSENSE vdd led_a 0
VPWM pwm 0 PWL(
{pwl}
+)
XLED led_a led_k microled
XPIXEL 0 bias gate pwm pwm_b led_k vlogic pixel_driver_layout
.options reltol=1e-5 abstol=1e-12 vntol=1e-7 gmin={case['gmin']}
.control
set noaskquit
set numdgt=15
set wr_vecnames
set wr_singlescale
save v(pwm) v(pwm_b) v(bias) v(gate) v(led_k) i(VSENSE) i(VLOGIC) i(VPWM)
tran 100n {STOP:.15g} 0 {case['maxstep_ns']*1e-9:.15g}
wrdata waveform.dat v(pwm) v(pwm_b) v(bias) v(gate) v(led_k) i(VSENSE) i(VLOGIC) i(VPWM)
quit
.endc
.end
"""
        (folder / "testbench.spice").write_text(deck)
        run(["ngspice", "-b", "testbench.spice"], folder, "ngspice.log")
        data = np.loadtxt(folder / "waveform.dat", skiprows=1)
        if data.ndim != 2 or data.shape[1] != 9 or not np.isfinite(data).all():
            raise RuntimeError(f"Invalid output: {folder}")
        t, current = data[:, 0], data[:, 6]
        frame_currents = [integral(t, current, LEFT+i*FRAME, LEFT+(i+1)*FRAME)/FRAME*1e6 for i in range(4)]
        mean = integral(t, current)/(RIGHT-LEFT)*1e6
        state_drift = max(abs(np.interp(LEFT, t, data[:, i])-np.interp(RIGHT, t, data[:, i])) for i in range(1, 6))
        result = case | dict(average_current_uA=mean, frame_currents_uA=frame_currents,
                             frame_spread_uA=max(frame_currents)-min(frame_currents),
                             state_endpoint_drift_V=float(state_drift),
                             led_rail_power_uW=5*mean,
                             logic_rail_power_uW=-case['vlogic_v']*integral(t, data[:, 7])/(RIGHT-LEFT)*1e6,
                             pwm_source_power_uW=-integral(t, data[:, 1]*data[:, 8])/(RIGHT-LEFT)*1e6,
                             led_terminal_power_uW=integral(t, (5-data[:, 5])*current)/(RIGHT-LEFT)*1e6,
                             branch_peak_uA=float(current[(t >= LEFT)&(t <= RIGHT)].max()*1e6),
                             branch_min_uA=float(current[(t >= LEFT)&(t <= RIGHT)].min()*1e6))
        return result

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(simulate, cases):
            results.append(result)
            print(f"{len(results)}/{len(cases)} {result['name']} {result['average_current_uA']:.8f} uA", flush=True)
    indexed = {r["name"]: r for r in results}
    for result in results:
        if result["group"] == "matrix":
            name = f"{result['corner']}_t{result['temperature_c']}_v{result['vlogic_v']:.2f}_d256"
            full = indexed[name]["average_current_uA"]
            result["full_on_reference_error_pct"] = (full/100-1)*100
            result["duty_linearity_error_pct"] = (result["average_current_uA"]/(full*result["duty"]/256)-1)*100
        elif result["group"] == "sensitivity":
            name = result["name"].rsplit("_d", 1)[0]+"_d256"
            full = indexed[name]["average_current_uA"]
            result["duty_linearity_error_pct"] = (result["average_current_uA"]/(full*result["duty"]/256)-1)*100
    # Independent OP checks for every CJO/TT pair actually used above.
    calibrations = []
    for cjo, tt in sorted({(x["cjo_pF"], x["tt_ns"]) for x in cases}):
        reference = next(x for x in cases if x["cjo_pF"] == cjo and x["tt_ns"] == tt)
        folder = work / reference["name"]
        (folder / "calibration.spice").write_text("Independent synthetic LED anchor\n.include led.spice\n.temp 27\nITEST 0 led_a 100u\nXLED led_a 0 microled\n.options reltol=1e-7 abstol=1e-14\n.control\nset numdgt=15\nset wr_singlescale\nop\nwrdata calibration.dat v(led_a)\nquit\n.endc\n.end\n")
        run(["ngspice", "-b", "calibration.spice"], folder, "calibration.log")
        voltage = float(np.loadtxt(folder / "calibration.dat")[-1])
        calibrations.append(dict(cjo_pF=cjo, tt_ns=tt, actual_vf_v=voltage, target_vf_v=2.8,
                                 passed=abs(voltage-2.8)<1e-4))
    refinements = []
    for r in results:
        if r["group"] == "refinement":
            base = indexed[f"{r['corner']}_t{r['temperature_c']}_v{r['vlogic_v']:.2f}_d1"]
            relative = abs(r["average_current_uA"]-base["average_current_uA"])/abs(base["average_current_uA"])
            refinements.append(dict(case=r['name'], relative_delta=relative, passed=relative < 0.005))
    summary = dict(evidence_level="synthetic-load full-PDK RC simulation; assumption characterization only",
                   qualification=False, run_directory=str(work.relative_to(ROOT)),
                   host=dict(system=platform.system(), architecture=platform.machine(), python=platform.python_version(),
                             ngspice=ngspice_version),
                   measurement=dict(window_s=[LEFT, RIGHT], frame_s=FRAME, frames=4, rail_v=5, reference_uA=100),
                   ranges_basis="logic +/-10%, CJO x0.1/x10, TT 0/10ns and ramp 1/100ns are sensitivity probes, not fitted device ranges",
                   transient_runs=len(results), matrix_runs=sum(x['group']=='matrix' for x in results),
                   calibration_runs=len(calibrations), calibrations=calibrations, refinements=refinements,
                   numerical_checks_passed=all(x['passed'] for x in calibrations+refinements),
                   source_hashes=source_hashes,
                   results=results)
    (work / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    if not summary['numerical_checks_passed']:
        raise RuntimeError(f"Numerical checks failed; inspect {work}")
    if args.publish_evidence:
        destination = ROOT / "evidence/review/sensitivity-summary.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(work / "summary.json", destination)
    print(f"Completed {len(results)} transient and {len(calibrations)} DC calibration runs: {work}")


if __name__ == "__main__":
    main()
