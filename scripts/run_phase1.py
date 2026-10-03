"""Run actual RTL, replay its edges into GF180 transistor SPICE, verify and plot."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from fetch_models import ROOT, MODEL_DIR, fetch_models

FRAME_S = 256e-6
WINDOW = (514.5e-6, 1538.5e-6)  # TB: two warmup frames + four measured frames
STOP_S = WINDOW[1] + 2e-6
SLEW_S = 10e-9


def source_hashes(root=ROOT):
    """Hash inspectable source inputs, excluding local metadata and outputs."""
    suffixes = {".v", ".sv", ".spice", ".json", ".py", ".sh"}
    sources = {}
    for folder in ("rtl", "sim/rtl", "analog", "scripts"):
        for path in sorted((root / folder).rglob("*")):
            relative = path.relative_to(root)
            if (path.is_file() and path.suffix in suffixes
                    and not any(part.startswith(".") or part == "__pycache__"
                                for part in relative.parts)):
                sources[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return sources


def command(args, log, cwd=ROOT):
    result = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed ({result.returncode}); see {log}")
    return result.stdout


def read_events(path):
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    events = [(float(row["time_ns"]) * 1e-9, int(row["pwm"])) for row in rows]
    if not events or events[0][1] != 0:
        raise ValueError("RTL trace must start with a known reset-low value")
    if any(value not in (0, 1) for _, value in events):
        raise ValueError("Unknown RTL value")
    if any(b[0] <= a[0] for a, b in zip(events, events[1:])):
        raise ValueError("RTL event times must strictly increase")
    return events


def pwl_points(events, stop=STOP_S, slew=SLEW_S):
    # Each voltage transition STARTS at the actual RTL timestamp. A physical
    # 10ns ramp is added; it does not move the digital frame boundaries.
    points = [(0.0, 0.0)]
    previous = 0
    for stamp, value in events:
        if value == previous:
            continue
        if stamp < points[-1][0] or stamp + slew >= stop:
            raise ValueError("PWL transitions overlap or exceed stop time")
        points.extend([(stamp, previous * 3.3), (stamp + slew, value * 3.3)])
        previous = value
    points.append((stop, previous * 3.3))
    return points


def digital_duty(events, window=WINDOW):
    left, right = window
    edges = [left] + [t for t, _ in events if left < t < right] + [right]
    high = 0.0
    for a, b in zip(edges, edges[1:]):
        level = next((v for t, v in reversed(events) if t <= a + 1e-15), 0)
        high += (b - a) * level
    return high / (right - left)


def verify_trace_window(log):
    trace = re.search(r"TRACE first_frame_ns=(\d+) measure_start_ns=(\d+) measure_end_ns=(\d+)", log)
    if not trace:
        raise ValueError("RTL did not report its trace timing")
    first, start, end = (int(value) * 1e-9 for value in trace.groups())
    if abs(first - 2.5e-6) > 1e-14 or any(abs(a - b) > 1e-14 for a, b in zip((start, end), WINDOW)):
        raise ValueError("RTL timing differs from SPICE measurement window; update both together")


def windowed(time, values, window=WINDOW):
    left, right = window
    if time[0] > left or time[-1] < right or np.any(np.diff(time) <= 0):
        raise ValueError("SPICE samples do not cover the integration interval monotonically")
    selected = (time > left) & (time < right)
    times = np.r_[left, time[selected], right]
    samples = np.r_[np.interp(left, time, values), values[selected], np.interp(right, time, values)]
    return times, samples


def average(time, values, window=WINDOW):
    t, y = windowed(time, values, window)
    return float(np.trapezoid(y, t) / (window[1] - window[0]))


def led_is(vf):
    # Synthetic diode calibration at 27 C and 100 uA. Uses physical k/q.
    vt = 8.617333262145e-5 * 300.15
    # Effective ideality factor 3 is an educational assumption, and keeps IS
    # within ngspice's usable range over the selected 2.4..3.2V calibration.
    return 100e-6 / math.expm1((vf - 100e-6 * 50) / (3.0 * vt))


def calibrate_led(build):
    """Independent 100uA DC calibration catches silent diode IS clamping."""
    results = []
    for vf in (2.4, 2.8, 3.2):
        folder = build / f"led_calibration_{vf:.1f}"
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / "calibration.dat"
        deck = folder / "calibration.spice"
        # Calibration is independent of the mirror and does not need MOS models.
        deck.write_text(f"""Synthetic LED independent DC calibration
.param LED_IS={led_is(vf):.16g}
.include "{os.path.relpath(ROOT / 'analog/models/microled.spice', folder)}"
.temp 27
ITEST 0 led_a 100u
XLED led_a 0 microled
.options reltol=1e-7 abstol=1e-14
.control
set wr_singlescale
op
wrdata calibration.dat v(led_a)
quit
.endc
.end
""")
        output.unlink(missing_ok=True)
        command(["ngspice", "-b", deck], folder / "ngspice.log", cwd=folder)
        if not output.exists():
            raise RuntimeError("LED calibration produced no data")
        values = np.loadtxt(output)
        actual = float(values[-1])
        result = dict(target_vf_v=vf, simulated_vf_v=actual, reference_current_uA=100,
                      temperature_c=27, saturation_current_A=led_is(vf), tolerance_v=1e-4,
                      passed=math.isfinite(actual) and abs(actual - vf) < 1e-4)
        results.append(result)
    (build / "led-calibration.json").write_text(json.dumps(results, indent=2) + "\n")
    if not all(r["passed"] for r in results):
        raise RuntimeError("Independent LED calibration failed; inspect led-calibration.json")
    return results


def make_deck(case, folder, events, maxstep=200e-9):
    relative = lambda p: Path(os.path.relpath(p, folder)).as_posix()
    points = "\n".join(f"+ {t:.12g} {v:.9g}" for t, v in pwl_points(events))
    deck = f"""GF180MCU one-pixel feed-forward RTL/SPICE simulation
.include design.ngspice
.param sw_stat_global=0 sw_stat_mismatch=0
.lib sm141064.ngspice {case['corner']}
.param LED_IS={led_is(case['vf_v']):.16g}
.include "{relative(ROOT / 'analog/models/microled.spice')}"
.include "{relative(ROOT / 'analog/driver/pixel_driver.spice')}"
.temp {case['temperature_c']}
VDD vdd 0 {case['supply_v']}
VLOGIC vlogic 0 3.3
IREF vlogic bias DC 100u
VSENSE vdd led_a 0
VPWM pwm 0 PWL(
{points}
+ )
XLED led_a led_k microled
XPIXEL led_k pwm vlogic bias gate pwm_b pixel_driver
.options reltol=1e-5 abstol=1e-12 vntol=1e-7
.control
set noaskquit
set wr_vecnames
set wr_singlescale
save v(pwm) v(pwm_b) v(bias) v(gate) v(led_k) i(VSENSE)
tran 100n {STOP_S:.12g} 0 {maxstep:.12g}
wrdata waveform.dat v(pwm) v(pwm_b) v(bias) v(gate) v(led_k) i(VSENSE)
quit
.endc
.end
"""
    path = folder / "testbench.spice"
    path.write_text(deck)
    return path


def run_case(case, build, binary, maxstep=200e-9):
    folder = build / case["name"]
    folder.mkdir(parents=True, exist_ok=True)
    # Original models self-reference a basename. Local relative symlinks allow
    # running in the case folder; wrdata then uses a plain filename even when
    # the user's workspace/output path contains spaces (wrdata preserves quotes).
    for name in ("design.ngspice", "sm141064.ngspice"):
        link = folder / name
        link.unlink(missing_ok=True)
        link.symlink_to(os.path.relpath(MODEL_DIR / name, folder))
    rtl_log = command(["vvp", binary, f"+OUT={folder / 'events.csv'}", f"+DUTY={case['duty']}",
                       f"+ENABLE={case.get('enable', 1)}", "+TRACE_ONLY=1"], folder / "rtl.log")
    verify_trace_window(rtl_log)
    events = read_events(folder / "events.csv")
    duty = digital_duty(events)
    expected_duty = min(case["duty"], 256) / 256 if case.get("enable", 1) else 0
    if abs(duty - expected_duty) > 1e-10:
        raise RuntimeError(f"RTL duty mismatch in {case['name']}")
    deck = make_deck(case, folder, events, maxstep)
    data_file = folder / "waveform.dat"
    # Prevent an ngspice failure with exit=0 from reusing stale output.
    data_file.unlink(missing_ok=True)
    command(["ngspice", "-b", deck], folder / "ngspice.log", cwd=folder)
    if not data_file.exists():
        raise RuntimeError(f"SPICE produced no waveform in {case['name']}")
    data = np.loadtxt(data_file, skiprows=1)
    if data.ndim != 2 or data.shape[1] != 7 or not np.isfinite(data).all():
        raise RuntimeError(f"Invalid SPICE samples in {case['name']}")
    t, current = data[:, 0], data[:, 6]
    measured_t, measured_i = windowed(t, current)
    result = dict(case, measured_duty=duty, average_current_uA=average(t, current) * 1e6,
                  peak_branch_current_uA=float(np.max(measured_i) * 1e6),
                  minimum_branch_current_uA=float(np.min(measured_i) * 1e6),
                  spice_samples=len(t), maxstep_ns=maxstep * 1e9)
    # Plateau samples exclude 100ns after a PWM edge. Branch current includes
    # displacement current, so transient peaks are reported separately.
    on = (t >= WINDOW[0]) & (t <= WINDOW[1]) & (data[:, 1] > 3.0)
    for stamp, _ in events:
        on &= ~((t >= stamp) & (t < stamp + 100e-9))
    if np.any(on):
        result["on_plateau_current_uA"] = float(np.median(current[on]) * 1e6)
        result["on_led_vf_v"] = float(np.median(case["supply_v"] - data[on, 5]))
        result["on_vds_v"] = float(np.median(data[on, 5]))
    result["frames_measured"] = 4
    return result, data


def plot_results(results, data_by_name, build):
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Avenir Next", "DejaVu Sans"],
                         "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titleweight": "semibold", "figure.facecolor": "white"})
    base = data_by_name["duty_064"]
    view = (base[:, 0] >= WINDOW[0]) & (base[:, 0] <= WINDOW[0] + 2 * FRAME_S)
    b = base[view]
    fig, axes = plt.subplots(3, 1, figsize=(10, 7.5), sharex=True, layout="constrained")
    x = (b[:, 0] - WINDOW[0]) * 1e6
    axes[0].plot(x, b[:, 1], color="#24536d", label="RTL PWM replay (10 ns slew)")
    axes[0].plot(x, b[:, 4], color="#8a8065", label="MOUT gate")
    axes[0].set_ylabel("Voltage (V)"); axes[0].legend(loc="upper right")
    axes[1].plot(x, b[:, 6] * 1e6, color="#267f7b", label="LED branch current")
    axes[1].set_ylabel("Current (uA)"); axes[1].legend(loc="upper right")
    axes[2].plot(x, 5.0 - b[:, 5], color="#24536d", label="LED forward voltage")
    axes[2].set_ylabel("Voltage (V)"); axes[2].set_xlabel("Time from measured frame boundary (us)")
    axes[2].legend(loc="lower right")
    for ax in axes: ax.grid(alpha=0.18)
    fig.suptitle("1 Pixel | GF180MCU typical, 27 C | duty 64/256\nSynthetic LED load; transistor simulation")
    fig.savefig(build / "waveforms.png", dpi=180)
    fig.savefig(build / "waveforms.svg")
    plt.close(fig)
    nominal = [r for r in results if r["name"].startswith("duty_")]
    full = next(r["average_current_uA"] for r in nominal if r["duty"] == 256)
    fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
    x = [r["measured_duty"] for r in nominal]
    ax.plot(x, [r["average_current_uA"] for r in nominal], "o-", color="#267f7b", label="Simulated average branch current")
    ax.plot([0, 1], [0, full], "--", color="#8a8065", label="Duty x full-on average")
    ax.set(xlabel="PWM duty", ylabel="Average LED branch current (uA)",
           title="Current-based brightness proxy | no optical calibration")
    ax.grid(alpha=0.18); ax.legend()
    fig.savefig(build / "duty-current.png", dpi=180); fig.savefig(build / "duty-current.svg")
    plt.close(fig)
    sweep = [r for r in results if r["name"].startswith("vf_")]
    sweep += [next(r for r in results if r["name"] == "duty_256")]
    sweep.sort(key=lambda r: r["vf_v"])
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    ax = axes[0]
    ax.plot([r["vf_v"] for r in sweep], [r["average_current_uA"] for r in sweep], "o-", color="#24536d")
    ax.axhline(100, color="#8a8065", linestyle="--", label="External IREF = 100 uA")
    ax.set(xlabel="Synthetic Vf calibrated at 100 uA / 27 C (V)", ylabel="Full-on average LED current (uA)",
           title="Vf variation | VLED = 5 V")
    ax.grid(alpha=0.18); ax.legend()
    limited = [r for r in results if r["name"].startswith("headroom_")]
    limited += [next(r for r in results if r["name"] == "duty_256")]
    limited.sort(key=lambda r: r["supply_v"])
    ax = axes[1]
    ax.plot([r["supply_v"] for r in limited], [r["average_current_uA"] for r in limited], "o-", color="#267f7b")
    ax.set(xlabel="LED supply (V)", ylabel="Full-on average LED current (uA)",
           title="Compliance limit | synthetic Vf = 2.8 V")
    ax.grid(alpha=0.18)
    fig.savefig(build / "vf-current.png", dpi=180); fig.savefig(build / "vf-current.svg")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/phase1")
    parser.add_argument("--rtl-only", action="store_true")
    parser.add_argument("--publish-evidence", action="store_true", help="Copy compact verified evidence into the repository")
    args = parser.parse_args()
    build = args.output.resolve()
    build.mkdir(parents=True, exist_ok=True)
    required = ["iverilog", "vvp"] + ([] if args.rtl_only else ["ngspice"])
    for tool in required:
        if not shutil.which(tool):
            raise RuntimeError(f"Missing tool: {tool}. See docs/environment.md")
    binary = build / "pixel_pwm.vvp"
    command(["iverilog", "-g2012", "-Wall", "-s", "tb_pixel_pwm", "-o", binary,
             "rtl/pixel_pwm.v", "sim/rtl/tb_pixel_pwm.v"], build / "compile.log")
    checked = command(["vvp", binary, f"+OUT={build / 'selfcheck-events.csv'}"], build / "rtl-selfcheck.log")
    if "PASS" not in checked:
        raise RuntimeError("RTL testbench did not report PASS")
    verify_trace_window(checked)
    print(checked.strip())
    if args.rtl_only:
        return
    lock = fetch_models()
    calibration = calibrate_led(build)
    cases = [dict(name=f"duty_{d:03d}", duty=d) for d in (0, 1, 64, 128, 192, 255, 256)]
    cases += [dict(name="disabled", duty=128, enable=0)]
    cases += [dict(name=f"vf_{vf:.1f}", duty=256, vf_v=vf) for vf in (2.4, 3.2)]
    cases += [dict(name=f"headroom_{v:.1f}", duty=256, supply_v=v) for v in (2.9, 3.0, 3.3)]
    cases += [dict(name=f"corner_{c}", duty=256, corner=c) for c in ("ff", "ss")]
    cases += [dict(name=f"temp_{temp}", duty=256, temperature_c=temp) for temp in (0, 85)]
    results, data_by_name = [], {}
    defaults = dict(vf_v=2.8, supply_v=5.0, temperature_c=27, corner="typical", enable=1)
    for partial in cases:
        case = defaults | partial
        result, data = run_case(case, build, binary)
        results.append(result); data_by_name[case["name"]] = data
        print(f"{case['name']}: average={result['average_current_uA']:.6f} uA")
    full = next(r for r in results if r["name"] == "duty_256")["average_current_uA"]
    checks = []
    def check(name, passed, details):
        checks.append(dict(name=name, passed=bool(passed), details=details))
    for result in calibration:
        check(f"led_dc_calibration_{result['target_vf_v']}", result["passed"],
              f"100 uA / 27 C: Vf={result['simulated_vf_v']:.9g} V; target={result['target_vf_v']} V; tolerance=0.1 mV")
    for result in results[:7]:
        ideal = full * result["measured_duty"]
        error = abs(result["average_current_uA"] - ideal)
        check(f"linearity_{result['name']}", error <= max(0.01, ideal * 0.03), f"error={error:.8g} uA; limit=max(0.01 uA, 3% of expected)")
    for name in ("duty_000", "disabled"):
        result = next(r for r in results if r["name"] == name)
        check(f"off_{name}", abs(result["average_current_uA"]) < 0.001, "absolute average < 1 nA after warmup")
    normal = [r["average_current_uA"] for r in results if r["name"] in ("vf_2.4", "duty_256", "vf_3.2")]
    check("vf_regulation", (max(normal) - min(normal)) / full < 0.10, "Vf 2.4/2.8/3.2 V spread < 10% of nominal full-on current; an educational baseline criterion")
    for name in ("vf_2.4", "duty_256", "vf_3.2"):
        result = next(r for r in results if r["name"] == name)
        check(f"vf_calibration_{name}", abs(result["on_led_vf_v"] - result["vf_v"]) < 0.01,
              "actual simulated full-on Vf must be within 10 mV of the synthetic 100 uA / 27 C calibration")
    limited = next(r for r in results if r["name"] == "headroom_2.9")["average_current_uA"]
    check("headroom_negative_control", limited < full * 0.9, "LED supply=2.9 V / synthetic Vf=2.8 V must expose current droop")
    for d in (1, 64):
        case = defaults | dict(name=f"convergence_{d:03d}", duty=d)
        fine, _ = run_case(case, build, binary, maxstep=20e-9)
        base = next(r for r in results if r["name"] == f"duty_{d:03d}")
        relative_error = abs(fine["average_current_uA"] - base["average_current_uA"]) / base["average_current_uA"]
        check(f"timestep_convergence_{d}", relative_error < 0.005, f"200 ns vs 20 ns maximum step relative difference={relative_error:.8g}; limit=0.5%")
        results.append(fine)
    plot_results(results, data_by_name, build)
    summary = dict(schema_version=1, evidence_level="RTL plus pre-layout PDK transistor simulation",
                   coupling="feed-forward RTL edge replay; no analog-to-RTL feedback",
                   optical_status="unmeasured; average current is a brightness proxy only",
                   host=dict(system=platform.system(), architecture=platform.machine(), python=platform.python_version()),
                   models=lock, rtl_selfcheck=checked.strip(), led_calibration=calibration,
                   tools=dict(ngspice=subprocess.run(["ngspice", "--version"], capture_output=True, text=True).stdout.strip(),
                              iverilog=subprocess.run(["iverilog", "-V"], capture_output=True, text=True).stdout.splitlines()[0]),
                   assumptions=dict(clock_hz=1_000_000, pwm_frequency_hz=3906.25, frame_cycles=256,
                                    pwm_input_slew_ns=10, reference_current_uA=100,
                                    led_model="synthetic exponential diode + Rs + CJO + TT",
                                    led_parameters=dict(N=3, Rs_ohm=50, CJO_pF=2, TT_ns=1, EG_eV=2.6),
                                    measurement_window_s=WINDOW),
                   checks=checks, passed=all(c["passed"] for c in checks), cases=results)
    (build / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    fields = list(defaults) + ["name", "duty", "measured_duty", "average_current_uA", "peak_branch_current_uA", "minimum_branch_current_uA", "on_plateau_current_uA", "on_led_vf_v", "on_vds_v", "spice_samples", "maxstep_ns", "frames_measured"]
    with (build / "metrics.csv").open("w") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(results)
    if not summary["passed"]:
        failed = [c["name"] for c in checks if not c["passed"]]
        raise RuntimeError(f"Verification failed: {failed}; inspect {build / 'summary.json'}")
    if args.publish_evidence:
        evidence = ROOT / "evidence/phase1"
        evidence.mkdir(parents=True, exist_ok=True)
        for name in ("summary.json", "metrics.csv", "rtl-selfcheck.log", "led-calibration.json", "waveforms.png", "duty-current.png", "vf-current.png"):
            shutil.copyfile(build / name, evidence / name)
        # Uniform 200ns waveform sample for two measured frames. Linear
        # interpolation is an explicit derived view; raw solver data stay in build.
        data = data_by_name["duty_064"]
        times = np.arange(WINDOW[0], WINDOW[0] + 2 * FRAME_S + 1e-12, 200e-9)
        trace = np.column_stack([times] + [np.interp(times, data[:, 0], data[:, i]) for i in range(1, 7)])
        np.savetxt(evidence / "waveform-duty064.csv", trace, delimiter=",", fmt="%.10g",
                   header="time_s,pwm_v,pwm_b_v,bias_v,gate_v,led_k_v,led_branch_current_A", comments="")
        edge = (data[:, 0] >= WINDOW[0] - 100e-9) & (data[:, 0] <= WINDOW[0] + 300e-9)
        np.savetxt(evidence / "edge-duty064.csv", data[edge], delimiter=",", fmt="%.10g",
                   header="time_s,pwm_v,pwm_b_v,bias_v,gate_v,led_k_v,led_branch_current_A", comments="")
        provenance = source_hashes()
        (evidence / "source-hashes.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"PASS: {len(checks)} analog checks, {len(results)} transistor runs + {len(calibration)} isolated LED calibrations. Results: {build.relative_to(ROOT) if build.is_relative_to(ROOT) else build}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
