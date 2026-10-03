"""Independently recalculate actual-extraction CSV and waveform summary values.

Uses Python's standard-library statistics and an explicit piecewise-linear
integrator, independently from the runner's NumPy reduction/integration.
"""
from bisect import bisect_right
from pathlib import Path
import csv
import hashlib
import json
import math
import statistics

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/characterization"


def close(a,b):
    if not math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-18):
        raise AssertionError(f"Independent recalculation differs: {a!r} != {b!r}")


def integrate(times,values,start,end):
    # Split at sample times; linear interpolation gives exact area of the saved
    # piecewise-linear waveform, including partial boundary segments.
    if times[0]>start or times[-1]<end or any(b<=a for a,b in zip(times,times[1:])):
        raise AssertionError("Waveform does not cover the interval monotonically")
    total = 0.0
    first = max(0,bisect_right(times,start)-1)
    for i in range(first,len(times)-1):
        t0,t1 = times[i],times[i+1]
        a,b = max(start,t0),min(end,t1)
        if a>=end:
            break
        if b<=a:
            continue
        slope = (values[i+1]-values[i])/(t1-t0)
        ya = values[i]+slope*(a-t0)
        yb = values[i]+slope*(b-t0)
        total += (ya+yb)*(b-a)/2
    return total


def main():
    summary_file = EVIDENCE / "actual-w20-l4-summary.json"
    summary = json.loads(summary_file.read_text())
    checks = []
    paths = [summary_file]
    for name,population in summary["mc"]["populations"].items():
        path = EVIDENCE / f"actual-w20-l4-mc-{name}.csv"
        paths.append(path)
        rows = list(csv.DictReader(path.open()))
        candidate_path = EVIDENCE / f"candidate-w20-l4-mc-{name}.csv"
        candidate_rows = list(csv.DictReader(candidate_path.open()))
        assert len(rows)==256
        assert len(candidate_rows)==len(rows)
        assert [int(r["seed"]) for r in rows]==list(range(20261004,20261260))
        for row,prior in zip(rows,candidate_rows):
            assert row["seed"]==prior["seed"]
            for device in range(6):
                for suffix in ("dvth","mulu0"):
                    assert float(row[f"x{device}_{suffix}"])==float(prior[f"x{device}_{suffix}"])
        for field in ("iout","iref","mirror_ratio","headroom","power_w"):
            values = [float(r[field]) for r in rows]
            for actual,expected in ((statistics.mean(values),population[field]["mean"]),
                                    (statistics.stdev(values),population[field]["sample_sd"]),
                                    (min(values),population[field]["min"]),(max(values),population[field]["max"])):
                close(actual,expected)
        outside = 0
        for row in rows:
            current,reference = float(row["iout"]),float(row["iref"])
            close(float(row["mirror_ratio"]),current/reference)
            close(float(row["reference_error_pct"]),100*(reference/100e-6-1))
            close(float(row["absolute_error_pct"]),100*(current/100e-6-1))
            outside += abs(100*(current/100e-6-1))>5
        assert outside==population["over_absolute_current_budget_count"]
        checks.append({"name":name,"n":256,"passed":True,"outside_absolute_five_pct":outside,
                       "all_6_devices_same_random_draws_as_conceptual_candidate":True})
    path = EVIDENCE / "actual-w20-l4-reference-pvt.csv"
    paths.append(path)
    rows = list(csv.DictReader(path.open()))
    assert len(rows)==1080
    keys = ("library","temperature_c","logic_v","led_supply_v","calibration_error","tc_ppm","line_ppm_v")
    assert len({tuple(r[k] for k in keys) for r in rows})==1080
    for row in rows:
        close(float(row["mirror_ratio"]),float(row["iout"])/float(row["iref"]))
    close(min(float(r["iout"]) for r in rows),summary["reference_pvt"]["minimum_case"]["iout"])
    close(max(float(r["iout"]) for r in rows),summary["reference_pvt"]["maximum_case"]["iout"])
    checks.append({"name":"reference_pvt","n":1080,"passed":True})
    for pulse in summary["lowest_code_pulses"]:
        path = ROOT / summary["raw_directory"] / "pulses" / f"{pulse['case']}_{pulse['maxstep_s']:g}" / "waveform.dat"
        paths.append(path)
        with path.open() as handle:
            next(handle)
            data = [list(map(float,line.split())) for line in handle]
        times = [row[0] for row in data]
        currents = [row[2] for row in data]
        start,end = pulse["measurement_window_s"]
        duration = (end-start)/4
        errors = []
        for i,frame in enumerate(pulse["per_frame"]):
            charge = integrate(times,currents,start+i*duration,start+(i+1)*duration)
            close(charge,frame["charge_c"])
            error = 100*(charge/(pulse["dc_current_a"]*1e-6)-1)
            # Floating accumulation affects tiny percentages much more than Q.
            assert abs(error-frame["area_error_pct"])<1e-8
            errors.append(error)
        checks.append({"name":f"pulse_{pulse['case']}_{pulse['maxstep_s']:g}","n_frames":4,
                       "independently_integrated_max_abs_error_pct":max(map(abs,errors)),"passed":True})
    frozen = ROOT / summary["snapshot_directory"]
    for name,expected in summary["source_hashes"].items():
        path = frozen / name
        if not path.exists():
            path = ROOT / name
        assert hashlib.sha256(path.read_bytes()).hexdigest()==expected,name
    checks.append({"name":"all_frozen_inputs_match_recorded_hashes","passed":True})
    output = {"date":"2026-10-04","method":"Independent standard-library statistics, explicit waveform integration and frozen-input hashes",
              "checks":checks,"source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "output_sha256":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    (EVIDENCE / "actual-w20-l4-validation.json").write_text(json.dumps(output,indent=2)+"\n")
    print(json.dumps({"checks":len(checks),"passed":all(c["passed"] for c in checks)},indent=2))


if __name__ == "__main__":
    main()
