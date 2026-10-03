"""Independent arithmetic and solver sensitivity audit; never imports runners.

Run with .venv/bin/python scripts/review/numeric_audit.py [--solver-probes].
Raw results stay in build/audit_numeric; compact output is numeric-summary.json.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import re
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LEFT, RIGHT = 514500e-9, 1538500e-9
FRAME = 256000e-9
RAW = ROOT / "build/audit_numeric"
OUT = ROOT / "evidence/review"


def integral(data, a=LEFT, b=RIGHT, col=6):
    """Clip each linear segment, integrate analytically, and compensated-sum.

    Deliberately does not construct the runner's endpoint-interpolated arrays,
    call np.trapezoid, or import its integration helper.
    """
    if not a < b or data[0, 0] > a or data[-1, 0] < b:
        raise ValueError("Invalid or uncovered audit window")
    if not np.isfinite(data).all() or np.any(np.diff(data[:, 0]) <= 0):
        raise ValueError("Nonfinite or unordered solver samples")
    terms = []
    for p, q in zip(data[:-1], data[1:]):
        lo, hi = max(a, p[0]), min(b, q[0])
        if hi <= lo:
            continue
        slope = (q[col] - p[col]) / (q[0] - p[0])
        ylo = p[col] + slope * (lo - p[0])
        yhi = p[col] + slope * (hi - p[0])
        terms.append((hi - lo) * (ylo + yhi) / 2)
    return math.fsum(terms) / (b - a)


def exact_event_fraction(path):
    """Integer-ns event overlap counting avoids the runner's floating lookup."""
    with path.open() as handle:
        events = [(int(r["time_ns"]), int(r["pwm"])) for r in csv.DictReader(handle)]
    if not events or events[0][1] != 0:
        raise ValueError("Missing known low initial trace")
    if any(b[0] <= a[0] for a, b in zip(events, events[1:])):
        raise ValueError("Unordered events")
    events.append((2000000, events[-1][1]))
    high_ns = sum(max(0, min(b[0], 1538500) - max(a[0], 514500)) * a[1]
                  for a, b in zip(events, events[1:]))
    return high_ns / 1024000, events[:-1]


def pwl_audit(folder, events, data):
    deck = (folder / "testbench.spice").read_text()
    pwl = deck.split("VPWM pwm 0 PWL(", 1)[1].split("+ )", 1)[0]
    points = [(float(a), float(b)) for a, b in re.findall(r"\+\s+([\deE.+-]+)\s+([\deE.+-]+)", pwl)]
    expected = [(0.0, 0.0)]
    old = 0
    for ns, value in events:
        if old != value:
            expected.extend([(ns * 1e-9, old * 3.3), (ns * 1e-9 + 10e-9, value * 3.3)])
            old = value
    expected.append((.0015405, old * 3.3))
    same = len(points) == len(expected) and all(abs(a-c) < 1e-15 and abs(b-d) < 1e-12
                                               for (a, b), (c, d) in zip(points, expected))
    raw_voltage_error = float(np.max(np.abs(data[:, 1] - np.interp(data[:, 0],
                              [p[0] for p in points], [p[1] for p in points]))))
    return dict(matches_independent_expected_ramps=same,
                maximum_recorded_pwm_error_v=raw_voltage_error,
                input_slew_ns=10, threshold_50_percent_delay_ns=5)


def inspect_case(group, name, expected, folder):
    data = np.loadtxt(folder / "waveform.dat", skiprows=1)
    duty, events = exact_event_fraction(folder / "events.csv")
    actual = integral(data) * 1e6
    frame_means = [integral(data, LEFT + i * FRAME, LEFT + (i+1)*FRAME) * 1e6 for i in range(4)]
    where = (data[:, 0] >= LEFT) & (data[:, 0] <= RIGHT)
    in_window = data[where, 6] * 1e6
    fields = dict(group=group, name=name, average_current_uA=actual,
                  public_average_current_uA=expected["average_current_uA"],
                  recomputation_difference_uA=actual-expected["average_current_uA"],
                  expected_digital_duty=(min(expected["duty"], 256)/256 if expected.get("enable", 1) else 0),
                  exact_digital_duty=duty, stored_digital_duty=expected["measured_duty"],
                  sample_count=len(data), all_finite=bool(np.isfinite(data).all()),
                  strict_time_order=bool(np.all(np.diff(data[:, 0]) > 0)),
                  min_step_s=float(np.min(np.diff(data[:, 0]))),
                  max_step_s=float(np.max(np.diff(data[:, 0]))),
                  frame_means_uA=frame_means,
                  measured_frame_mean_spread_uA=max(frame_means)-min(frame_means),
                  unweighted_sample_mean_uA=float(np.mean(in_window)),
                  sample_peak_to_peak_uA=float(np.ptp(in_window)),
                  raw_file_sha256=hashlib.sha256((folder / "waveform.dat").read_bytes()).hexdigest(),
                  pwl=pwl_audit(folder, events, data))
    fields["arithmetic_passed"] = abs(fields["recomputation_difference_uA"]) < 1e-9 and duty == fields["expected_digital_duty"]
    return fields


def resolved_probe_deck(source, target, options, maxstep):
    deck = (source / "testbench.spice").read_text()
    for line in list(deck.splitlines()):
        if line.startswith((".include ", ".lib ")):
            parts = line.split()
            item = parts[1].strip('"')
            absolute = (source / item).resolve()
            deck = deck.replace(line, f'{parts[0]} "{absolute}"' + (" " + parts[2] if len(parts) > 2 else ""))
    deck = re.sub(r"^\.options .*", ".options " + options, deck, flags=re.M)
    deck = re.sub(r"^tran .*", f"tran 100n .0015405 0 {maxstep}", deck, flags=re.M)
    deck = re.sub(r"set numdgt=\d+\n", "", deck).replace("set wr_vecnames", "set numdgt=15\nset wr_vecnames")
    target.mkdir(parents=True, exist_ok=True)
    (target / "testbench.spice").write_text(deck)
    # The GF model self-includes sm141064.ngspice by basename.
    for name in ("design.ngspice", "sm141064.ngspice"):
        link = target / name
        link.unlink(missing_ok=True)
        link.symlink_to((source / name).resolve())


def solver_probes(base):
    result = []
    for case in ("duty_000", "duty_001", "duty_064", "duty_256"):
        source = base / "layout_rc" / case
        baseline = np.loadtxt(source / "waveform.dat", skiprows=1)
        for method, options, maxstep in (
            ("gear2_tight", "reltol=1e-7 abstol=1e-14 vntol=1e-9 method=gear maxord=2", "200n"),
            ("trap_tight_20ns", "reltol=1e-7 abstol=1e-14 vntol=1e-9 method=trap", "20n"),
        ):
            folder = RAW / "solver-probes" / f"{case}_{method}"
            resolved_probe_deck(source, folder, options, maxstep)
            (folder / "waveform.dat").unlink(missing_ok=True)
            p = subprocess.run(["ngspice", "-b", "testbench.spice"], cwd=folder, capture_output=True, text=True)
            (folder / "ngspice.log").write_text(p.stdout + p.stderr)
            if p.returncode or not (folder / "waveform.dat").exists():
                raise RuntimeError(f"Probe failed: {folder}")
            data = np.loadtxt(folder / "waveform.dat", skiprows=1)
            where = (data[:, 0] >= LEFT) & (data[:, 0] <= RIGHT)
            avg, ref = integral(data)*1e6, integral(baseline)*1e6
            frames = [integral(data, LEFT+i*FRAME, LEFT+(i+1)*FRAME)*1e6 for i in range(4)]
            row = dict(name=case, method=method, average_current_uA=avg, baseline_uA=ref,
                       delta_uA=avg-ref, relative_delta=(avg-ref)/ref,
                       peak_uA=float(np.max(data[where,6])*1e6), min_uA=float(np.min(data[where,6])*1e6),
                       frame_means_uA=frames, sample_count=len(data),
                       raw_directory=str(folder.relative_to(ROOT)))
            result.append(row)
            print(json.dumps(row), flush=True)
    return result


def gmin_probes(base):
    results = []
    source = base / "layout_rc" / "duty_000"
    for gmin in ("1e-10", "1e-12", "1e-14", "1e-16"):
        folder = RAW / "gmin-probes" / gmin
        options = f"reltol=1e-7 abstol=1e-16 vntol=1e-9 method=gear maxord=2 gmin={gmin}"
        resolved_probe_deck(source, folder, options, "200n")
        (folder / "waveform.dat").unlink(missing_ok=True)
        p = subprocess.run(["ngspice", "-b", "testbench.spice"], cwd=folder, capture_output=True, text=True)
        (folder / "ngspice.log").write_text(p.stdout + p.stderr)
        if p.returncode or not (folder / "waveform.dat").exists():
            raise RuntimeError(f"GMIN probe failed: {folder}")
        data = np.loadtxt(folder / "waveform.dat", skiprows=1)
        results.append(dict(gmin_s=float(gmin), average_current_pA=integral(data)*1e12,
                            cathode_v=integral(data, col=5), raw_directory=str(folder.relative_to(ROOT))))
    (OUT / "numeric-gmin-probes.json").write_text(json.dumps(results, indent=2) + "\n")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solver-probes", action="store_true")
    parser.add_argument("--phase1-summary", type=Path, default=ROOT / "evidence/phase1/summary.json")
    parser.add_argument("--layout-summary", type=Path, default=ROOT / "evidence/layout/summary.json")
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    phase_summary = args.phase1_summary.resolve()
    layout_summary = args.layout_summary.resolve()
    phase = json.loads(phase_summary.read_text())
    layout = json.loads(layout_summary.read_text())
    post = ROOT / layout["run_directory"] / "postlayout"
    records = [inspect_case("phase1", c["name"], c, ROOT / "build/phase1" / c["name"]) for c in phase["cases"]]
    for variant, cases in layout["results"].items():
        records.extend(inspect_case(variant, n, c, post / variant / n) for n, c in cases.items())
    # Convergence outputs are stored as guards, not in layout's result dictionary.
    for duty in (1, 64):
        check = next(c for c in layout["checks"] if c["name"] == f"rc_step_convergence_{duty}")
        fields = dict(duty=duty, measured_duty=duty/256, average_current_uA=check["fine_uA"])
        records.append(inspect_case("layout_rc_fine", f"convergence_{duty:03d}", fields, post / "layout_rc" / f"convergence_{duty:03d}"))
    calibration = []
    for study, cases in (("phase1", phase["led_calibration"]), ("full_pdk", layout["isolated_led_calibrations"])):
        for c in cases:
            thermal_voltage = 1.380649e-23 * 300.15 / 1.602176634e-19
            predicted = 3 * thermal_voltage * math.log1p(100e-6/c["saturation_current_A"]) + 100e-6*50
            rawbase = ROOT / "build/phase1" if study == "phase1" else post
            calibration_file = rawbase / f"led_calibration_{c['target_vf_v']:.1f}/calibration.dat"
            raw_voltage = float(np.loadtxt(calibration_file)[-1])
            calibration.append(dict(group=study, target_v=c["target_vf_v"], independently_calculated_v=predicted,
                                    ngspice_v=c["simulated_vf_v"], raw_voltage_v=raw_voltage,
                                    public_matches_raw=raw_voltage == c["simulated_vf_v"],
                                    raw_sha256=hashlib.sha256(calibration_file.read_bytes()).hexdigest(),
                                    delta_v=c["simulated_vf_v"]-predicted))
    hashes = []
    phase_hashes = json.loads((ROOT / "evidence/phase1/source-hashes.json").read_text())
    for group, manifest in (("phase1", phase_hashes), ("layout", layout["source_hashes"])):
        for relative, sha in manifest.items():
            hashes.append(dict(group=group, path=relative,
                               matches=hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == sha))
    extra_dirs = sorted(p.name for p in (ROOT/"build/phase1").iterdir()
                        if p.is_dir() and (p/"waveform.dat").exists() and p.name not in {c["name"] for c in phase["cases"]})
    result = dict(schema_version=1, evidence_level="independent numeric audit of existing saved solver data",
                  method="segment-clipped analytic linear integral with math.fsum; integer-ns digital event overlap",
                  window_seconds=[LEFT, RIGHT], measured_frames=4,
                  waveform_count=len(records), all_arithmetic_passed=all(r["arithmetic_passed"] for r in records),
                  maximum_absolute_recomputation_difference_uA=max(abs(r["recomputation_difference_uA"]) for r in records),
                  records=records, calibration=calibration, source_hash_checks=hashes,
                  stale_raw_case_directories_not_in_published_summary=extra_dirs,
                  solver_probes=solver_probes(post) if args.solver_probes else [])
    if args.solver_probes:
        result["gmin_probes"] = gmin_probes(post)
    result["audit_inputs_sha256"] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (phase_summary, layout_summary,
                     Path(__file__).resolve())
    }
    target = OUT / "numeric-summary.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Saved {target}; audited {len(records)} waveforms; pass={result['all_arithmetic_passed']}")


if __name__ == "__main__":
    main()
