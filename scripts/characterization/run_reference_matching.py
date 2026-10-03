"""Locked-PDK reference budget, fixed-corner and Monte Carlo characterization.

All statistical device draws come from the unmodified PDK wrappers. Deterministic
reference-error bounds are a declared teaching specification, not a part model.
No baseline netlist/model/layout is edited. Failure to meet a candidate budget is
a scientific result; tool failures or statistical mechanism failures stop the run.
"""
from dataclasses import asdict, dataclass, replace
from pathlib import Path
import argparse
import csv
import hashlib
import itertools
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PDK = ROOT / "build/layout/pdk/gf180mcuD"
EVIDENCE = ROOT / "evidence/characterization"
REFERENCE = ROOT / "scripts/characterization/external_reference.spice"
PIXEL = ROOT / "evidence/layout/pixel_driver_rc.spice"
MC_N = 256
SEED_START = 20261004
TARGET_CURRENT_A = 100e-6
CAL_BOUND = 0.005
TC_BOUND_PPM = 25
LINE_BOUND_PPM_V = 3000
REFERENCE_ROUT_OHM = 10e6


@dataclass(frozen=True)
class Condition:
    library: str = "typical"
    temperature_c: float = 27
    logic_v: float = 3.3
    led_supply_v: float = 5
    local_mismatch: int = 0
    global_variation: int = 0
    reference: str = "ideal"
    calibration_error: float = 0
    tc_ppm: float = 0
    line_ppm_v: float = 0
    pwm_on: bool = True


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_models():
    lock = json.loads((ROOT / "layout/pdk-lock.json").read_text())
    for name, expected in lock["files"].items():
        if sha(PDK / name) != expected:
            raise RuntimeError(f"PDK hash mismatch: {name}")
    models = (PDK / "libs.tech/ngspice/sm141064.ngspice").read_text()
    # Guard the actual statistical mechanism used, not just a library label.
    for marker in (".LIB statistical", ".lib fets_mm", ".subckt nfet_06v0 d g s b", ".subckt pfet_06v0 d g s b",
                   "mis_vth=agauss(0,var_vth,1)", "delvto='mis_vth*sw_stat_mismatch'", "mulu0='1-mis_k*sw_stat_mismatch'"):
        if marker not in models:
            raise RuntimeError(f"PDK statistical mechanism changed: {marker}")
    if len(re.findall(r"^X\d+ .* (?:n|p)fet_06v0 ", PIXEL.read_text(), re.M)) != 6:
        raise RuntimeError("Expected six extracted PDK wrapper instances")
    return lock


def run_command(args, folder, log):
    proc = subprocess.run(list(map(str, args)), cwd=folder, capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    (folder / log).write_text(output)
    if proc.returncode or re.search(r"(?im)^(?:Error|fatal|Warning: unrecognized)", output):
        raise RuntimeError(f"Simulation/tool failed, inspect {folder / log}")
    return output


def case_prefix(c, title):
    # Same explicitly synthetic LED baseline; reference calibration remains 27 C.
    vt = 8.617333262145e-5 * 300.15
    saturation = TARGET_CURRENT_A / math.expm1((2.8 - TARGET_CURRENT_A * 50) / (3 * vt))
    if c.reference == "ideal":
        ref = "IREF ref_p bias 100u"
    else:
        ref = (f'.include "{REFERENCE}"\nXREF ref_p bias external_reference '
               f'cal_error={c.calibration_error:.12g} tc_ppm={c.tc_ppm:.12g} '
               f'line_ppm_v={c.line_ppm_v:.12g} r_out={REFERENCE_ROUT_OHM:.12g}')
    return f"""{title}
.include design.ngspice
.param sw_stat_global={c.global_variation} sw_stat_mismatch={c.local_mismatch}
.lib sm141064.ngspice {c.library}
.include "{PIXEL}"
.param LED_IS={saturation:.16g}
.include "{ROOT / 'analog/models/microled.spice'}"
.temp {c.temperature_c}
VLED led_a 0 {c.led_supply_v}
VLOGIC vlogic 0 {c.logic_v}
VREFSENSE vlogic ref_p 0
{ref}
VPWM pwm 0 {c.logic_v if c.pwm_on else 0}
XLED led_a led_k microled
XPIXEL 0 bias gate pwm pwm_b led_k vlogic pixel_driver_layout
.options reltol=1e-7 abstol=1e-15 vntol=1e-9
"""


def prepare(folder):
    folder.mkdir(parents=True, exist_ok=True)
    for basename in ("design.ngspice", "sm141064.ngspice"):
        (folder / basename).symlink_to(PDK / "libs.tech/ngspice" / basename)


def op(c, folder, seed=SEED_START):
    prepare(folder)
    expressions = {"iout": "-i(vled)", "iref": "i(vrefsense)", "bias": "v(bias)",
                   "headroom": "v(vlogic)-v(bias)", "led_k": "v(led_k)",
                   "power_w": "-v(led_a)*i(vled)-v(vlogic)*i(vlogic)",
                   "out_vth": "@m.xpixel.x2.m0[vth]", "ref_vth": "@m.xpixel.x4.m0[vth]"}
    for n in range(6):
        expressions[f"x{n}_dvth"] = f"@m.xpixel.x{n}.m0[delvto]"
        expressions[f"x{n}_mulu0"] = f"@m.xpixel.x{n}.m0[mulu0]"
    lets = "\n".join(f"let {key}={value}" for key, value in expressions.items())
    deck = case_prefix(c, "Independent reference and PDK mismatch characterization") + f""".control
set noaskquit
set numdgt=15
set wr_vecnames
set wr_singlescale
setseed {seed}
reset
op
{lets}
wrdata op.dat {' '.join(expressions)}
quit
.endc
.end
"""
    (folder / "op.spice").write_text(deck)
    run_command(["ngspice", "-b", "op.spice"], folder, "op.log")
    rows = (folder / "op.dat").read_text().splitlines()
    keys, values = rows[0].split()[1:], list(map(float, rows[1].split()[1:]))
    if keys != list(expressions) or len(rows) != 2 or not all(map(math.isfinite, values)):
        raise RuntimeError(f"Missing/non-finite OP data: {folder}")
    measured = dict(zip(keys, values))
    measured["mirror_ratio"] = measured["iout"] / measured["iref"]
    measured["reference_error_pct"] = 100 * (measured["iref"] / TARGET_CURRENT_A - 1)
    measured["absolute_error_pct"] = 100 * (measured["iout"] / TARGET_CURRENT_A - 1)
    measured["absolute_current_budget_pass"] = abs(measured["absolute_error_pct"]) <= 5
    return dict(seed=seed, **asdict(c), **measured)


def describe(rows):
    result = {"n": len(rows)}
    for name in ("iout", "iref", "mirror_ratio", "reference_error_pct", "absolute_error_pct", "out_vth", "ref_vth", "headroom", "power_w"):
        data = np.array([r[name] for r in rows])
        result[name] = {"mean": float(data.mean()), "sample_sd": float(data.std(ddof=1)) if len(data)>1 else 0,
                        "min": float(data.min()), "max": float(data.max()),
                        "quantiles_2p5_50_97p5": list(map(float, np.quantile(data, [.025, .5, .975])))}
    result["over_absolute_current_budget_count"] = sum(not r["absolute_current_budget_pass"] for r in rows)
    result["population_note"] = "finite conditional model sample; not measured manufacturing yield"
    return result


def save_csv(path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def pulse_check(c, folder, binary, dc_current_a, maxstep):
    # Reuse only the already independently reviewed actual-RTL replay bridge.
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_phase1 as phase
    prepare(folder)
    output = run_command(["vvp", binary, f"+OUT={folder / 'events.csv'}", "+DUTY=1", "+ENABLE=1", "+TRACE_ONLY=1"], folder, "rtl.log")
    phase.verify_trace_window(output)
    events = phase.read_events(folder / "events.csv")
    points = "\n".join(f"+ {t:.15g} {v*c.logic_v/3.3:.15g}" for t, v in phase.pwl_points(events))
    deck = re.sub(r"VPWM pwm 0 .*", "VPWM pwm 0 PWL(\n" + points + "\n+ )", case_prefix(c, "Actual RTL duty=1 with bounded external reference"))
    deck += f""".control
set noaskquit
set numdgt=15
set wr_vecnames
set wr_singlescale
setseed {SEED_START}
reset
save v(pwm) i(vled) i(vrefsense)
tran 10n {phase.STOP_S:.15g} 0 {maxstep:.15g}
let iout=-i(vled)
wrdata waveform.dat v(pwm) iout i(vrefsense)
quit
.endc
.end
"""
    (folder / "pulse.spice").write_text(deck)
    run_command(["ngspice", "-b", "pulse.spice"], folder, "pulse.log")
    data = np.loadtxt(folder / "waveform.dat", skiprows=1)
    # Independent direct time integral, with explicit boundary interpolation.
    per_frame = []
    for n in range(4):
        start = phase.WINDOW[0] + n*phase.FRAME_S
        end = start + phase.FRAME_S
        mask = (data[:,0]>start)&(data[:,0]<end)
        times = np.r_[start, data[mask,0], end]
        currents = np.r_[np.interp(start,data[:,0],data[:,2]),data[mask,2],np.interp(end,data[:,0],data[:,2])]
        charge = float(np.trapezoid(currents,times))
        per_frame.append(dict(charge_c=charge, area_error_pct=100*(charge/(dc_current_a*1e-6)-1)))
    return dict(condition=asdict(c), maxstep_s=maxstep, dc_current_a=dc_current_a,
                measurement_window_s=list(phase.WINDOW), measured_frames=4, per_frame=per_frame,
                max_abs_area_error_pct=max(abs(r["area_error_pct"]) for r in per_frame),
                within_two_pct=all(abs(r["area_error_pct"])<=2 for r in per_frame),
                note="area relative to actual same-condition full-on current; absolute current ±5% is checked separately")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=MC_N)
    args = parser.parse_args()
    if args.samples < 200:
        raise ValueError("At least 200 samples are required for this characterization record")
    lock = check_models()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (ROOT / "build/characterization").mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="reference-", dir=ROOT / "build/characterization"))
    files = [PIXEL, REFERENCE, Path(__file__).resolve(), ROOT / "analog/models/microled.spice", ROOT / "layout/pdk-lock.json",
             ROOT / "rtl/pixel_pwm.v", ROOT / "sim/rtl/tb_pixel_pwm.v", ROOT / "scripts/run_phase1.py"]
    source_hashes = {str(p.relative_to(ROOT)): sha(p) for p in files}
    conditions = {
        "local_only": Condition(local_mismatch=1),
        "global_only": Condition(library="statistical", global_variation=1),
        "global_and_local": Condition(library="statistical", global_variation=1, local_mismatch=1),
        "reference_nominal_and_global_local": Condition(library="statistical", global_variation=1, local_mismatch=1, reference="bounded"),
    }
    populations = {}
    for name, c in conditions.items():
        print(f"MC {name}: n={args.samples}", flush=True)
        rows = [op(c, work/name/f"sample_{n:04d}", SEED_START+n) for n in range(args.samples)]
        populations[name] = rows
        save_csv(EVIDENCE/f"mc-{name}.csv", rows)
    controls = []
    nulls = [op(Condition(), work/"null"/str(n), SEED_START+n) for n in range(8)]
    controls.append(dict(name="mismatch_and_global_off_null", passed=len({r["iout"] for r in nulls})==1 and all(r[f"x{n}_dvth"]==0 for r in nulls for n in range(6))))
    statnull = op(Condition(library="statistical"), work/"statistical_null")
    controls.append(dict(name="statistical_zero_switches_match_nominal", passed=abs(statnull["iout"]-nulls[0]["iout"])<1e-12))
    repeat = op(conditions["local_only"], work/"same_seed_repeat")
    first = populations["local_only"][0]
    controls.append(dict(name="same_seed_exact_repeat", passed=repeat==first))
    local = populations["local_only"]
    controls.append(dict(name="different_seeds_actually_change_local_draws", passed=len({r["x2_dvth"] for r in local})==args.samples))
    expected_sigma=.7071*.01155/math.sqrt(1.6*10.5)
    out_sigma=float(np.std([r["x2_dvth"] for r in local],ddof=1))
    ref_sigma=float(np.std([r["x4_dvth"] for r in local],ddof=1))
    pair_corr=float(np.corrcoef([r["x2_dvth"] for r in local],[r["x4_dvth"] for r in local])[0,1])
    controls.append(dict(name="local_threshold_draws_match_wrapper_scale", expected_sigma_v=expected_sigma, out_sigma_v=out_sigma, ref_sigma_v=ref_sigma, pair_correlation=pair_corr,
                         passed=.75<out_sigma/expected_sigma<1.25 and .75<ref_sigma/expected_sigma<1.25 and abs(pair_corr)<.25))
    global_rows=populations["global_only"]
    controls.append(dict(name="global_switch_changes_model_not_local_delta", passed=np.std([r["out_vth"] for r in global_rows])>.005 and all(r[f"x{n}_dvth"]==0 for r in global_rows for n in range(6))))
    if not all(r["passed"] for r in controls):
        (work/"failed-controls.json").write_text(json.dumps(controls,indent=2))
        raise RuntimeError(f"Statistical mechanism control failed: {work}")
    print("Reference tolerance and fixed-corner matrix",flush=True)
    matrix=[]
    for n,(corner,temp,vl,vs,gain,tc,line) in enumerate(itertools.product(
            ("typical","ff","ss","fs","sf"),(0,27,85),(2.97,3.3,3.63),(4.5,5,5.5),(-CAL_BOUND,CAL_BOUND),(-TC_BOUND_PPM,TC_BOUND_PPM),(-LINE_BOUND_PPM_V,LINE_BOUND_PPM_V))):
        c=Condition(library=corner,temperature_c=temp,logic_v=vl,led_supply_v=vs,reference="bounded",calibration_error=gain,tc_ppm=tc,line_ppm_v=line)
        matrix.append(op(c,work/"reference_pvt"/f"case_{n:04d}"))
    save_csv(EVIDENCE/"reference-pvt.csv",matrix)
    low=min(matrix,key=lambda r:r["iout"]); high=max(matrix,key=lambda r:r["iout"])
    for name,row in (("conditional_low",low),("conditional_high",high)):
        c=replace(Condition(**{k:row[k] for k in Condition.__dataclass_fields__}),local_mismatch=1)
        print(f"MC {name}: n={args.samples}; fixed boundary + local mismatch",flush=True)
        rows=[op(c,work/name/f"sample_{n:04d}",SEED_START+n) for n in range(args.samples)]
        populations[name]=rows
        save_csv(EVIDENCE/f"mc-{name}.csv",rows)
    # Reference DC calibration and actual RTL pulse checks retain the electrical chain.
    sys.path.insert(0,str(ROOT/"scripts"))
    import run_phase1 as phase
    calibration=phase.calibrate_led(work)
    binary=work/"pixel_pwm.vvp"
    run_command(["iverilog","-g2012","-Wall","-s","tb_pixel_pwm","-o",binary,ROOT/"rtl/pixel_pwm.v",ROOT/"sim/rtl/tb_pixel_pwm.v"],work,"rtl-compile.log")
    nominal=op(Condition(reference="bounded"),work/"reference_nominal")
    pulse_results=[]
    for name,row in (("nominal",nominal),("low",low),("high",high)):
        c=Condition(**{k:row[k] for k in Condition.__dataclass_fields__})
        for step in (50e-9,10e-9):
            print(f"Actual RTL pulse {name}, maxstep={step:g}s",flush=True)
            pulse_results.append(dict(case=name,**pulse_check(c,work/"pulses"/f"{name}_{step:g}",binary,row["iout"],step)))
    if {str(p.relative_to(ROOT)):sha(p) for p in files}!=source_hashes:
        raise RuntimeError("An input source changed during characterization; do not publish mixed evidence")
    summary={
        "date":"2026-10-04","evidence_level":"simulation characterization with candidate external reference bounds and PDK statistics; no physical redesign",
        "raw_directory":str(work.relative_to(ROOT)),"pdk_build":lock["open_pdks_commit"],"primitive_commit":lock["primitive_commit"],
        "pdk_model_sha256":lock["files"]["libs.tech/ngspice/sm141064.ngspice"],"source_hashes":source_hashes,
        "tools":{"ngspice":run_command(["ngspice","--version"],work,"ngspice-version.log"),"numpy":np.__version__,"python":sys.version},
        "candidate_targets":{"absolute_current_error_pct":5,"minimum_code_area_error_pct":2,"temperature_c":[0,85],"logic_v":[2.97,3.63],"led_supply_v":[4.5,5.5]},
        "reference_specification":{"source":"independent candidate teaching budget, no selected part or measured calibration", "nominal_a":TARGET_CURRENT_A,"calibration_temperature_c":27,"calibration_headroom_v":1.9,
                                   "calibration_error_bound_pct":100*CAL_BOUND,"tc_bound_ppm_per_c":TC_BOUND_PPM,"line_bound_ppm_per_v":LINE_BOUND_PPM_V,"output_resistance_ohm":REFERENCE_ROUT_OHM,"minimum_headroom_v":1},
        "mc":{"samples_per_population":args.samples,"seed_first":SEED_START,"seed_last":SEED_START+args.samples-1,"seed_method":"one process per sample; setseed then reset then op; PDK agauss only; no random reference errors", "populations":{k:describe(v) for k,v in populations.items()},"mechanism_controls":controls},
        "reference_pvt":{"n":len(matrix),"summary":describe(matrix),"minimum_case":low,"maximum_case":high,"all_within_five_pct":all(r["absolute_current_budget_pass"] for r in matrix),"all_reference_headrooms_valid":all(r["headroom"]>=1 for r in matrix)},
        "led_dc_calibration":calibration,"lowest_code_pulses":pulse_results,
        "limits":["Synthetic baseline LED electrical and temperature model remains unmeasured.","Statistics are conditional on this public PDK model; finite sample pass fractions are not manufacturing yield.","Local/systematic layout gradients, resistor/capacitor RC corners, reference noise and startup are not modeled by these populations.","Fixed-corner/reference bounds are deterministic checks, not a probability distribution.","PWM target uses charge relative to actual full-on current at the same condition; absolute current budget remains a separate check."]}
    (EVIDENCE/"reference-matching-summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    for name in ("ngspice-version.log",):shutil.copyfile(work/name,EVIDENCE/name)
    print(json.dumps({"mechanism_controls_pass":all(r["passed"] for r in controls),"pvt_current_range_uA":[low["iout"]*1e6,high["iout"]*1e6],"pvt_pass":summary["reference_pvt"]["all_within_five_pct"],"mc_exceedances":{k:v["over_absolute_current_budget_count"] for k,v in summary["mc"]["populations"].items()},"pulse_max_error_pct":max(p["max_abs_area_error_pct"] for p in pulse_results)},indent=2))


if __name__=="__main__":
    main()
