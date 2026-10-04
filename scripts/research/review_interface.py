"""Independent raw-data recomputation and exact as-run R/C identity review.

No functions from interface simulation, validation, or input-mapping scripts are
imported. This reads existing successful raw outputs without rerunning SPICE.
"""
from collections import Counter
from decimal import Decimal
from pathlib import Path
import csv
import hashlib
import json
import math
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rc_signature(text):
    ports, elements, ended = None, [], False
    scales = {"": Decimal(1), "f": Decimal("1e-15"), "p": Decimal("1e-12"),
              "n": Decimal("1e-9"), "u": Decimal("1e-6"), "m": Decimal("1e-3")}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        tokens = line.split()
        if tokens[0].lower() == ".subckt":
            if ports is not None:
                raise ValueError("Multiple subcircuits")
            ports = tuple(tokens[1:])
            continue
        if tokens[0].lower() == ".ends":
            ended = True
            continue
        if ports is None or ended or len(tokens) != 4 or tokens[0][0].upper() not in ("R", "C"):
            raise ValueError("Unsupported R/C signature statement")
        number = re.fullmatch(r"([0-9.eE+-]+)([fpnum]?)", tokens[3])
        if number is None:
            raise ValueError("Unsupported value")
        value = Decimal(number[1]) * scales[number[2]]
        if not value.is_finite() or value <= 0:
            raise ValueError("Non-positive R/C value")
        elements.append((tokens[0][0].upper(), tuple(sorted(tokens[1:3])), value))
    if not ended:
        raise ValueError("Incomplete subcircuit")
    return ports, Counter(elements)


def panel_integral(time, value, left, right):
    """Integrate each original linear panel clipped to the requested window."""
    if (time[0] > left or time[-1] < right or np.any(np.diff(time) <= 0)
            or not np.isfinite(value).all()):
        raise ValueError("Invalid raw data or incomplete integration window")
    lo = np.maximum(time[:-1], left)
    hi = np.minimum(time[1:], right)
    mask = hi > lo
    slope = (value[1:] - value[:-1]) / np.diff(time)
    # Analytic antiderivative on each original panel; no resampled waveform.
    u = lo[mask] - time[:-1][mask]
    v = hi[mask] - time[:-1][mask]
    panels = value[:-1][mask] * (v - u) + .5 * slope[mask] * (v * v - u * u)
    return float(np.sum(panels))


def crossings(time, value, threshold, sign):
    intervals = np.flatnonzero((value[:-1] < threshold) & (value[1:] >= threshold)
                              if sign > 0 else
                              (value[:-1] > threshold) & (value[1:] <= threshold))
    return time[intervals] + ((threshold - value[intervals])
           * (time[intervals + 1] - time[intervals])
           / (value[intervals + 1] - value[intervals]))


def edge_metrics(time, value, supply, left, right):
    result = {}
    midpoints = {}
    for sign, name in ((1, "rise"), (-1, "fall")):
        midpoint = crossings(time, value, .5 * supply, sign)
        before = crossings(time, value, (.3 if sign > 0 else .7) * supply, sign)
        after = crossings(time, value, (.7 if sign > 0 else .3) * supply, sign)
        selected = midpoint[(midpoint > left) & (midpoint < right)]
        widths = []
        for center in selected:
            a = np.searchsorted(before, center, side="right") - 1
            b = np.searchsorted(after, center, side="left")
            if a < 0 or b >= len(after):
                raise ValueError("Unbounded edge")
            widths.append((after[b] - before[a]) * 1e9)
        result["rise_30_70_ns" if sign > 0 else "fall_70_30_ns"] = max(widths) if widths else None
        result[name + "_edges"] = len(selected)
        midpoints[name] = midpoint
    for name, a, b in (("high", midpoints["rise"], midpoints["fall"]),
                       ("low", midpoints["fall"], midpoints["rise"])):
        widths = []
        for start in a[(a > left) & (a < right)]:
            stop = np.searchsorted(b, start, side="right")
            if stop < len(b) and b[stop] < right:
                widths.append((b[stop] - start) * 1e9)
        result[name + "_pulse_min_ns"] = min(widths) if widths else None
    return result


def main():
    main_path = ROOT / "evidence/interface/summary.json"
    stress_path = ROOT / "evidence/interface/slew-budget-summary.json"
    mapping_path = ROOT / "evidence/interface/input-mapping.json"
    main_result = json.loads(main_path.read_text())
    stress = json.loads(stress_path.read_text())
    mapping = json.loads(mapping_path.read_text())
    work = ROOT / main_result["run_directory"]
    checks, maximum_errors = [], {}
    frozen_hashes = {str(path.relative_to(ROOT)): sha(path)
                     for path in [main_path, stress_path, mapping_path, Path(__file__)]}

    def check(name, passed, data=None):
        checks.append(dict(check=name, passed=bool(passed), data=data))
        if not passed:
            raise RuntimeError(f"Independent interface review failed: {name}: {data}")

    def equal(name, actual, expected, tolerance):
        if actual is None or expected is None:
            check(name, actual is None and expected is None)
            return
        delta = abs(actual - expected)
        group = name.rsplit(":", 1)[-1]
        maximum_errors[group] = max(maximum_errors.get(group, 0.), delta)
        check(name, delta <= tolerance, dict(actual=actual, expected=expected, abs_error=delta))

    check("run_counts", (main_result["transient_runs"], main_result["dc_runs"],
          main_result["AC_runs"], main_result["input_charge_runs"], stress["transient_runs"])
          == (54, 12, 5, 3, 6))
    check("reported_guards", main_result["passed"] and stress["passed"]
          and all(row["passed"] for row in main_result["checks"]))
    for name, wanted in main_result["source_hashes"].items():
        if name in mapping["paths"]:
            record = mapping["paths"][name]
            check("as_run_snapshot:" + name, wanted == record["as_run_sha256"]
                  == sha(ROOT / record["snapshot_path"]))
            check("current_serialization:" + name, sha(ROOT / name) == record["current_sha256"])
        else:
            check("frozen_source:" + name, sha(ROOT / name) == wanted)
    for name, wanted in main_result["pdk_inputs_sha256"].items():
        check("pdk_input:" + name, sha(ROOT / "build/layout/pdk/gf180mcuD" / name) == wanted)
    raw_link = (ROOT / mapping["paths"]["evidence/integration/pwm_link_rc.spice"]["snapshot_path"]).read_text()
    current_link = (ROOT / "evidence/integration/pwm_link_rc.spice").read_text()
    old, current = rc_signature(raw_link), rc_signature(current_link)
    check("exact_R_C_multiset", old == current)
    check("four_port_order", old[0] == ("pwm_link_rc", "A", "Y", "VDD", "VSS"))
    check("element_count_and_multiplicity", sum(old[1].values()) == 7
          and sum(number for (kind, ends, value), number in old[1].items() if kind == "R") == 1)
    line = next(row for row in raw_link.splitlines() if row.startswith("C1 "))
    mutations = dict(resistance=raw_link.replace("4.81871", "4.9"),
                     removed_cap=raw_link.replace(line, ""),
                     duplicated_cap=raw_link.replace(".ends", line.replace("C1 ", "C99 ") + "\n.ends"),
                     changed_endpoint=raw_link.replace(line, line.replace("VDD Y", "VDD A")),
                     changed_type=raw_link.replace("R0 A Y", "C0extra A Y"),
                     swapped_ports=raw_link.replace("pwm_link_rc A Y VDD VSS", "pwm_link_rc Y A VDD VSS"))
    for name, text in mutations.items():
        check("mapping_negative_control:" + name, rc_signature(text) != current)
    equal("RC:signal_cap_fF", float(sum(value * number for (kind, ends, value), number
          in old[1].items() if kind == "C" and ("A" in ends or "Y" in ends))) * 1e15,
          2.34604, 1e-10)
    physical = json.loads((ROOT / "evidence/integration/summary.json").read_text())
    current_gds = sha(ROOT / "evidence/integration/pixel_integrated.gds")
    check("full_top_GDS_identity", current_gds == mapping["full_top_GDS_sha256"]
          == physical["output_hashes"]["pixel_integrated.gds"])
    for name, control in physical["negative_controls"].items():
        path = ROOT / "evidence/integration/negative-controls" / name / "netgen-lvs.log"
        text = path.read_text()
        check("physical_negative_log:" + name,
              re.findall(r"^Final result:\s*(.+)$", text, re.M) != ["Circuits match uniquely."]
              and control["rejected_by_both_electrical_checks"])

    left, right = main_result["conditions"]["measurement_window_s"]
    duration = right - left
    check("four_frame_denominator", math.isclose(duration, 4 * 256e-6, abs_tol=1e-15)
          and main_result["conditions"]["measured_frames"] == 4)
    check("actual_slew_thresholds", main_result["conditions"]["actual_liberty_slew_thresholds_pct"] == [30, 70])

    def waveform_checks(record, folder, prefix):
        path = folder / record["name"] / "waveform.dat"
        data = np.loadtxt(path, skiprows=1)
        check(prefix + ":raw_waveform_shape", data.shape[1] == 9 and np.isfinite(data).all())
        wanted = (main_result["raw_artifacts_sha256"] if folder == work
                  else stress["raw_artifacts_sha256"])[record["name"] + "/waveform.dat"]
        check(prefix + ":raw_waveform_hash", sha(path) == wanted)
        t = data[:, 0]
        charge = -panel_integral(t, data[:, 1], left, right)
        current_uA = charge / duration * 1e6
        equal(prefix + ":current_uA", current_uA, record["average_led_current_uA"], 1e-7)
        equal(prefix + ":buffer_power_uW",
              -panel_integral(t, data[:, 3], left, right) / duration * record["logic_v"] * 1e6,
              record["average_buffer_power_uW"], 1e-7)
        full = next(row for row in main_result["transient_results"]
                    if row["envelope"] == record["envelope"]
                    and row["driver"] == record.get("driver", "buffer_joint")
                    and row["led"] == record.get("led", "synthetic") and row["duty"] == 256)
        if record["duty"]:
            area = (current_uA / (full["average_led_current_uA"] * record["duty"] / 256) - 1) * 100
            equal(prefix + ":area_pct", area, record["area_error_pct"], 1e-5)
        if record["duty"] == 1:
            # Four frames contain four 1-us pulses: charge per pulse = Q/4.
            q1 = charge / 4
            error = (q1 / (full["average_led_current_uA"] * 1e-6 * 1e-6) - 1) * 100
            equal(prefix + ":direct_Q1_area_pct", error, record["area_error_pct"], 1e-5)
            check(prefix + ":lowest_charge_guard", abs(error) <= 2)
        elif record["duty"] == 256:
            check(prefix + ":full_current_guard", 95 <= current_uA <= 105)
        elif record["duty"] == 0:
            check(prefix + ":off_model_guard", abs(current_uA) < .001)
        metrics = edge_metrics(t, data[:, 4], record["logic_v"], left, right)
        for key, value in metrics.items():
            equal(prefix + ":" + key, value, record[key], 1e-5 if "ns" in key else 0)
        if folder == work:
            equal(prefix + ":analog_power_uW",
                  -panel_integral(t, data[:, 2], left, right) / duration * record["logic_v"] * 1e6,
                  record["average_analog_logic_power_uW"], 1e-7)
            equal(prefix + ":LED_power_uW", current_uA * record["led_v"],
                  record["average_led_rail_power_uW"], 1e-7)
            equal(prefix + ":buffer_charge_c", -panel_integral(t, data[:, 3], left, right),
                  record["buffer_supply_charge_c"], 1e-17)

    for index, record in enumerate(main_result["transient_results"], 1):
        waveform_checks(record, work, record["name"])
        if index % 18 == 0:
            print(f"Independently recomputed {index} / 54 main waveforms", flush=True)
    for record in stress["results"]:
        waveform_checks(record, ROOT / stress["run_directory"], "slow_input:" + record["name"])
    for record in main_result["dc_results"]:
        data = np.loadtxt(work / record["name"] / "values.dat", skiprows=1)
        equal(record["name"] + ":dc_current_uA", -float(data[1]) * 1e6,
              record["led_current_uA"], 1e-10)
        equal(record["name"] + ":dc_buffer_uA", -float(data[3]) * 1e6,
              record["buffer_supply_current_uA"], 1e-10)
    for record in main_result["ac_results"]:
        bias_fraction = record["pwm_dc_v"] / 3.3
        choices = {0.: "0", .25: "0.25", .5: "0.5", .75: "0.75", 1.: "1"}
        fraction = min(choices, key=lambda value: abs(value - bias_fraction))
        data = np.loadtxt(work / ("ac_" + choices[fraction]) / "admittance.dat", skiprows=1)
        row = data[np.argmin(abs(data[:, 0] - record["frequency_hz"]))]
        equal(f"AC_{fraction}_{row[0]}:parallel_C_fF", float(row[2] / (2 * math.pi * row[0]) * 1e15),
              record["effective_parallel_capacitance_f"] * 1e15, 1e-9)
    windows = main_result["conditions"]["charge_integral_windows_s"]
    for record in main_result["input_charge_results"]:
        path = work / ("charge_" + str(record["input_full_ramp_ns"]).rstrip("0").rstrip(".")
                       if record["input_full_ramp_ns"] != 10 else "charge_10") / "waveform.dat"
        data = np.loadtxt(path, skiprows=1)
        t, source_i, voltage = data[:, 0], -data[:, 1], data[:, 2]
        for edge in ("rise", "fall"):
            a, b = windows[edge]
            q = panel_integral(t, source_i, a, b)
            equal(f"charge_{record['input_full_ramp_ns']}_{edge}:charge_fC", q * 1e15,
                  record[edge + "_signed_charge_c"] * 1e15, 1e-8)
            equal(f"charge_{record['input_full_ramp_ns']}_{edge}:equivalent_C_fF",
                  q / 3.3 * (1 if edge == "rise" else -1) * 1e15,
                  record[edge + "_charge_equivalent_cap_f"] * 1e15, 1e-8)
            equal(f"charge_{record['input_full_ramp_ns']}_{edge}:source_energy_pJ",
                  panel_integral(t, source_i * voltage, a, b) * 1e12,
                  record["source_energy_" + edge + "_j"] * 1e12, 1e-10)
            a, b = windows["short_" + edge]
            short = panel_integral(t, source_i, a, b)
            equal(f"charge_{record['input_full_ramp_ns']}_{edge}:short_tail_relative",
                  (q - short) / abs(q), record[edge + "_long_minus_short_relative"], 1e-8)
    for filename, records in (("dc.csv", main_result["dc_results"]),
                              ("ac.csv", main_result["ac_results"]),
                              ("input-charge.csv", main_result["input_charge_results"]),
                              ("transients.csv", main_result["transient_results"]),
                              ("slew-budget.csv", stress["results"])):
        with (ROOT / "evidence/interface" / filename).open() as stream:
            rows = list(csv.DictReader(stream))
        check("public_csv_count:" + filename, len(rows) == len(records))
        for row, record in zip(rows, records):
            for name, value in row.items():
                if name not in record:
                    raise RuntimeError("CSV field absent from summary: " + name)
                expected = record[name]
                if isinstance(expected, (int, float)):
                    check("CSV:" + filename + ":" + name, float(value) == expected)
                else:
                    check("CSV:" + filename + ":" + name, value == ("" if expected is None else str(expected)))
    for path, wanted in frozen_hashes.items():
        check("unchanged_during_review:" + path, sha(ROOT / path) == wanted)
    result = dict(schema_version=1, passed=True, checks=checks,
                  assertion_count=len(checks), maximum_absolute_recomputation_errors=maximum_errors,
                  input_hashes=frozen_hashes,
                  reviewed_counts=dict(main_transients=54, slow_input_transients=6,
                                       DC_points=12, AC_bias_runs=5, AC_table_points=25, switching_charge_probes=3),
                  exact_linear_RC_identity=dict(as_run_sha256=sha(ROOT / mapping["paths"]["evidence/integration/pwm_link_rc.spice"]["snapshot_path"]),
                                               current_sha256=sha(ROOT / "evidence/integration/pwm_link_rc.spice"),
                                               ordered_subckt_ports=list(old[0]),
                                               component_multiset_equal=True,
                                               negative_control_count=len(mutations)),
                  methods=dict(integration="Analytic clipped integral on each original raw linear panel; no simulation-runner functions imported",
                               lowest_code="Four-frame charge / 4 divided by full-on current times 1 us",
                               small_signal="Im(Y)/(2*pi*f) in farads; bias-dependent whole analog port response",
                               switching_charge="Signed terminal current integral and Q/3.3V; includes settling and coupled-node response",
                               slew="Actual voltage crossings at 30/70 percent, with 50-percent pulse widths"),
                  limits=["isolated canonical six-MOS output buffer is schematic SPICE, not its internal device/metal PEX",
                          "digital output net SPEF and new top metal-only PWM span are included; preceding FF/CQ/logic waveforms are not transistor simulated",
                          "macro supplies and reference are ideal; no full PG/substrate impedance simulation",
                          "real measured LED static curve + assumed capacitor remains a hypothesis, not dynamic or optical qualification",
                          "ideal-source 10ns and buffer-input 1ns ramps are different stimulus locations; their current difference is not solely an output-resistance effect"])
    (ROOT / "evidence/research/interface-review.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(passed=True, assertion_count=len(checks), maximum_errors=maximum_errors), indent=2))


if __name__ == "__main__":
    main()
