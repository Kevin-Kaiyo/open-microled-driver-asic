#!/usr/bin/env python3
"""Analyze frozen NRZ SPICE cases without rerunning or modifying simulations.

Usage: uv run python scripts/highspeed_nrz/analyze.py --work build/highspeed-nrz/run-...
Full traceable analysis is written inside that work directory. Compact records
default to evidence/highspeed-nrz or the explicit --output-dir directory.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import sys

import numpy as np

from metrics import (receiver_proxy, train_sampler, evaluate_validation,
                     energy_window, integrate_window, self_checks)

ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.0.0"
SCREEN = {"deterministic_errors": 0, "threshold_margin_normalized_min": .1,
          "timing_min_margin_ui_min": .1,
          "interpretation": "predeclared teaching comparison screen; not physical BER, qualification, or maximum-rate proof"}
STRESS_SCREEN_V = 3.63


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def load_trace(result: dict, result_path: Path) -> tuple[np.ndarray, dict]:
    path = Path(result["waveform"])
    if not path.is_absolute():
        path = ROOT/path
    if digest(path) != result["waveform_sha256"]:
        raise ValueError("compressed waveform hash mismatch")
    payload = gzip.decompress(path.read_bytes())
    if hashlib.sha256(payload).hexdigest() != result["uncompressed_sha256"]:
        raise ValueError("uncompressed waveform hash mismatch")
    deck = result_path.parent/"testbench.spice"
    if digest(deck) != result["deck_sha256"]:
        raise ValueError("simulation deck hash mismatch")
    a = np.atleast_2d(np.loadtxt(io.BytesIO(payload), skiprows=1))
    if a.shape[1] != len(result["vectors"])+1 or not np.isfinite(a).all():
        raise ValueError("invalid waveform dimensions or non-finite data")
    if len(a) != result["rows"]:
        raise ValueError("waveform row count differs from simulator record")
    if "dc_bit" not in result["case"] and (len(a) < 2 or not np.all(np.diff(a[:, 0]) > 0)):
        raise ValueError("transient time not strictly increasing; no silent de-duplication")
    provenance = {"result_json": relative(result_path), "result_sha256": digest(result_path),
                  "waveform": relative(path), "waveform_sha256": result["waveform_sha256"],
                  "uncompressed_sha256": result["uncompressed_sha256"],
                  "deck_sha256": result["deck_sha256"], "rows": len(a),
                  "hash_checks": "passed", "duplicates_removed": 0}
    return a, provenance


def stress_metrics(a: np.ndarray, result: dict) -> dict:
    """Six terminal differences, full waveform, including preheat and training."""
    vec = result["vectors"]
    time = a[:, 0]
    is_dc = "dc_bit" in result["case"]
    zeros = np.zeros(len(a))
    def node(name):
        return zeros if name == "0" else a[:, vec[name]]
    def extremes(value):
        j = int(np.argmax(np.abs(value)))
        return {"min_V": float(np.min(value)), "max_V": float(np.max(value)),
                "max_abs_V": float(abs(value[j])), "at_max_abs_signed_V": float(value[j]),
                "at_max_abs_time_s": None if is_dc else float(time[j])}
    devices = []
    for dev in result["devices"]:
        d, g, s, b = [node(n) for n in dev["nodes"]]
        pairs = {"VGS": g-s, "VGD": g-d, "VGB": g-b,
                 "VDS": d-s, "VDB": d-b, "VSB": s-b}
        voltages = {name: extremes(value) for name, value in pairs.items()}
        worst = max(voltages, key=lambda n: voltages[n]["max_abs_V"])
        # Positive values mean the physical p-side is above the n-side.
        body_forward = {"VBS": b-s, "VBD": b-d} if dev["model"].startswith("nfet") else {"VSB": s-b, "VDB": d-b}
        body = {name: {"max_forward_V": max(0., float(np.max(value))),
                       "max_signed_V": float(np.max(value))}
                for name, value in body_forward.items()}
        devices.append(dev | {"terminal_differences": voltages, "worst_pair": worst,
                              "max_abs_terminal_V": voltages[worst]["max_abs_V"],
                              "above_3p63V_screen": voltages[worst]["max_abs_V"] > STRESS_SCREEN_V,
                              "body_junction_forward": body,
                              "body_junction_interpretation": "record only; no diode-current or reliability pass criterion"})
    worst = max(devices, key=lambda d: d["max_abs_terminal_V"])
    return {"scope": "DC operating point" if is_dc else "entire transient including warmup, training, validation and guard",
            "screen_voltage_V": STRESS_SCREEN_V,
            "screen_caution": "sampled-waveform maxima, uniform absolute-difference screening only; not foundry reliability sign-off",
            "all_devices": devices, "max_abs_terminal_V": worst["max_abs_terminal_V"],
            "worst_instance": worst["instance"], "worst_pair": worst["worst_pair"],
            "above_3p63V_screen": any(d["above_3p63V_screen"] for d in devices),
            "maximum_recorded_body_forward_V": max(v["max_forward_V"] for d in devices for v in d["body_junction_forward"].values())}


def sum_energy(ports: dict[str, dict]) -> dict:
    keys = ["net_J", "positive_draw_J", "returned_J", "net_mean_W", "positive_draw_mean_W",
            "returned_mean_W", "net_J_per_gross_bit", "positive_draw_J_per_gross_bit", "returned_J_per_gross_bit"]
    total = {key: float(sum(p[key] for p in ports.values())) for key in keys}
    if not math.isclose(total["net_J"], total["positive_draw_J"]-total["returned_J"], rel_tol=1e-10, abs_tol=1e-23):
        raise AssertionError("summed source energy identity failed")
    total["ports"] = list(ports)
    total["scope"] = "sum of terminal-source contributions; no automatic recovery of returned energy"
    return total


def dc_metrics(a: np.ndarray, result: dict) -> dict:
    values = {name: float(a[-1, col]) for name, col in result["vectors"].items()}
    target = (25e-6, 100e-6)[result["case"]["dc_bit"]]
    led = values["iled_cond"]
    rails = {name: {"voltage_V": rail["voltage_V"],
                    "delivered_power_W": -rail["voltage_V"]*values[name.lower()+"_current"]}
             for name, rail in result["rails"].items()}
    return {"target_LED_current_A": target, "LED_current_A": led,
            "LED_current_error_A": led-target, "LED_current_error_percent": 100*(led-target)/target,
            "LED_voltage_V": values["led_voltage"], "output_voltage_V": values["out"],
            "bias_node_voltages_V": {k: v for k, v in values.items() if "bias" in k or k in ["vh", "vl", "vdd"]},
            "rail_ports": rails,
            "rail_net_power_W": sum(r["delivered_power_W"] for r in rails.values()),
            "rail_positive_draw_power_W": sum(max(0, r["delivered_power_W"]) for r in rails.values()),
            "rail_returned_power_W": sum(max(0, -r["delivered_power_W"]) for r in rails.values()),
            "ideal_data_delivered_power_W": -values["data"]*values["data_current"],
            "all_saved_DC_vectors": values}


def transient_metrics(a: np.ndarray, result: dict, stimulus: dict) -> dict:
    case, vec = result["case"], result["vectors"]
    t = a[:, 0]
    ui = 1/(case["rate_Gbps"]*1e9)
    proxy = receiver_proxy(t, a[:, vec["iled_cond"]], tau_opt_s=200e-12, rx_bw_hz=1e9)
    max_delay_ui = max(4, math.ceil(3e-9/ui))
    dropped = math.ceil(max_delay_ui)+1
    training = stimulus["training_bits"][:-dropped]
    if len(training) < 64:
        raise ValueError("training guard leaves fewer than64 symbols")
    train_start = stimulus["training_start_bit"]*ui
    validation_start = stimulus["validation_start_bit"]*ui
    validation_end = stimulus["validation_end_bit"]*ui
    if train_start + (len(training)-1+max_delay_ui)*ui >= validation_start:
        raise AssertionError("training search reads validation time")
    sampler = train_sampler(t, proxy["receiver_proxy_A"], training, train_start, ui,
                            max_delay_ui=max_delay_ui)
    sampler["training_guard"] = {"original_training_count": len(stimulus["training_bits"]),
                                 "tail_bits_omitted_from_training_score": dropped,
                                 "latest_training_candidate_sample_s": train_start+(len(training)-1+max_delay_ui)*ui,
                                 "validation_starts_s": validation_start,
                                 "no_validation_time_used": True}
    validation = evaluate_validation(t, proxy["receiver_proxy_A"], stimulus["validation_bits"], validation_start, ui, sampler)
    screen_flags = {"zero_deterministic_errors": validation["deterministic_errors"] == 0,
                    "threshold_margin_at_least_0p1": validation["threshold_margin_normalized"] >= .1,
                    "timing_margin_at_least_0p1UI": validation["timing_min_margin_ui"] >= .1}
    rails = {}
    for name, rail in result["rails"].items():
        rails[name] = energy_window(t, np.full(len(t), rail["voltage_V"]), a[:, vec[name.lower()+"_current"]],
                                    validation_start, validation_end, len(stimulus["validation_bits"]))
        rails[name]["voltage_V"] = rail["voltage_V"]
    data = energy_window(t, a[:, vec["data"]], a[:, vec["data_current"]], validation_start, validation_end,
                         len(stimulus["validation_bits"]))
    rail_total = sum_energy(rails)
    all_total = sum_energy(rails | {"ideal_DATA": data})
    in_window = (t >= validation_start) & (t <= validation_end)
    current = a[:, vec["iled_cond"]]
    current_stats = {"mean_A": integrate_window(t, current, validation_start, validation_end)/(validation_end-validation_start),
                     "min_saved_point_A": float(np.min(current[in_window])), "max_saved_point_A": float(np.max(current[in_window]))}
    nodekeys = [k for k in vec if k not in ["iled_cond", "package_current"] and not k.endswith("_current")]
    endpoints = {k: {"start": float(np.interp(validation_start, t, a[:, vec[k]])),
                     "end": float(np.interp(validation_end, t, a[:, vec[k]]))} for k in nodekeys}
    v = endpoints["led_voltage"]
    ipkg0, ipkg1 = np.interp([validation_start, validation_end], t, a[:, vec["package_current"]])
    known_storage = {"CLED_energy_change_J": .5*case["cap_F"]*(v["end"]**2-v["start"]**2),
                     "LPKG_energy_change_J": .5*case["l_pkg"]*(ipkg1**2-ipkg0**2),
                     "scope": "only explicit CLED and LPKG; excludes MOS internal stored energy"}
    return {"receiver_model": proxy["model"], "sampler": sampler, "validation": validation,
            "comparison_screen": {"definition": SCREEN, "conditions": screen_flags, "passed": all(screen_flags.values())},
            "energy": {"window": "same511 input UIs for both routes; no latency shift", "rails": rails,
                       "rail_total": rail_total, "ideal_DATA": data, "rail_plus_ideal_DATA_total": all_total,
                       "exclusions": ["upstream rail generators/regulator losses", "serializer and clock generation", "optical receiver", "cooling"],
                       "gross_not_net_bits": True, "no_free_energy_recovery_assumed": True},
            "conductive_LED_current_in_validation": current_stats, "node_voltage_endpoints_V": endpoints,
            "explicit_stored_energy_change": known_storage,
            "native_time_grid": {"minimum_dt_s": float(np.min(np.diff(t))), "maximum_dt_s": float(np.max(np.diff(t))),
                                  "declared_maximum_dt_s": ui/case["steps_per_ui"]}}


def compact_row(record: dict) -> dict:
    case = record["case"]
    row = {k: case.get(k) for k in ["name", "route", "kind", "rate_Gbps", "corner", "temp_C", "vdd_V", "cap_F", "r_pkg", "l_pkg", "edge_s", "steps_per_ui", "method", "reltol"]}
    row.update({"simulation_ok": record.get("simulation_ok", False), "analysis_ok": record.get("analysis_ok", False)})
    if not record.get("analysis_ok"):
        row["failure"] = record.get("analysis_error") or record.get("simulation_failure", {}).get("log", "simulation failed")
        return row
    stress = record["stress"]
    row.update({"max_abs_terminal_V": stress["max_abs_terminal_V"], "above_3p63V_screen": stress["above_3p63V_screen"],
                "maximum_body_forward_V": stress["maximum_recorded_body_forward_V"]})
    if "dc" in record:
        dc = record["dc"]
        row.update({"dc_bit": case["dc_bit"], "LED_current_A": dc["LED_current_A"],
                    "LED_current_error_percent": dc["LED_current_error_percent"], "rail_net_power_W": dc["rail_net_power_W"]})
    else:
        tx = record["transient"]
        v, en = tx["validation"], tx["energy"]
        row.update({"errors": v["deterministic_errors"], "validation_bits": v["sample_count"],
                    "eye_normalized": v["eye_opening_normalized"], "threshold_margin_normalized": v["threshold_margin_normalized"],
                    "timing_min_margin_ui": v["timing_min_margin_ui"], "sample_delay_ui": v["sample_delay_ui"],
                    "comparison_screen_passed": tx["comparison_screen"]["passed"],
                    "rail_net_fJ_per_gross_bit": en["rail_total"]["net_J_per_gross_bit"]*1e15,
                    "rail_positive_draw_fJ_per_gross_bit": en["rail_total"]["positive_draw_J_per_gross_bit"]*1e15,
                    "rail_returned_fJ_per_gross_bit": en["rail_total"]["returned_J_per_gross_bit"]*1e15,
                    "ideal_DATA_positive_draw_fJ_per_gross_bit": en["ideal_DATA"]["positive_draw_J_per_gross_bit"]*1e15,
                    "ideal_DATA_net_fJ_per_gross_bit": en["ideal_DATA"]["net_J_per_gross_bit"]*1e15,
                    "rail_plus_DATA_positive_draw_fJ_per_gross_bit": en["rail_plus_ideal_DATA_total"]["positive_draw_J_per_gross_bit"]*1e15,
                    "rail_net_power_W": en["rail_total"]["net_mean_W"],
                    "LED_mean_current_A": tx["conductive_LED_current_in_validation"]["mean_A"]})
    return row


def analyze(work: Path, output_dir: Path) -> dict:
    stimulus_path, manifest_path = work/"stimulus.json", work/"manifest.json"
    stimulus = json.loads(stimulus_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    paths = sorted((work/"cases").glob("*/result.json"))
    if not paths:
        raise FileNotFoundError("no completed case result.json files")
    checks = self_checks()
    records = []
    for path in paths:
        result = json.loads(path.read_text())
        rec = {"case": result["case"], "simulation_ok": result["simulation_ok"], "analysis_ok": False,
               "simulation_warnings": result.get("warnings", [])}
        if not result["simulation_ok"]:
            rec["simulation_failure"] = result
        else:
            try:
                a, source = load_trace(result, path)
                rec["sources"] = source
                rec["stress"] = stress_metrics(a, result)
                if "dc_bit" in result["case"]:
                    rec["dc"] = dc_metrics(a, result)
                else:
                    rec["transient"] = transient_metrics(a, result, stimulus)
                rec["analysis_ok"] = True
            except (ValueError, AssertionError, KeyError, OSError) as exc:
                rec["analysis_error"] = f"{type(exc).__name__}: {exc}"
        records.append(rec)
        print(rec["case"]["name"] + " " + ("ANALYZED" if rec["analysis_ok"] else "FAILED"), flush=True)
    identity = {"version": VERSION, "python_version": platform.python_version(), "numpy_version": np.__version__,
                "analysis_script_sha256": digest(Path(__file__)), "metrics_script_sha256": digest(Path(__file__).with_name("metrics.py")),
                "work": relative(work), "manifest_sha256": digest(manifest_path), "stimulus_sha256": digest(stimulus_path),
                "ngspice_version": manifest["ngspice_version"], "frozen_simulation_inputs": manifest["inputs"]}
    counts = {"case_results_found": len(records), "simulation_failures": sum(not r["simulation_ok"] for r in records),
              "analysis_failures": sum(r["simulation_ok"] and not r["analysis_ok"] for r in records),
              "analyzed_DC": sum(r["analysis_ok"] and "dc" in r for r in records),
              "analyzed_transient": sum(r["analysis_ok"] and "transient" in r for r in records)}
    full = {"schema_version": 1, "identity": identity, "counts": counts, "metrics_self_checks": checks,
            "common": manifest["common"], "comparison_screen": SCREEN,
            "stimulus_summary": {"warmup_bits": stimulus["warmup_bits"], "transmitted_training_bits": len(stimulus["training_bits"]),
                                 "validation_bits": len(stimulus["validation_bits"]), "validation_ones": sum(stimulus["validation_bits"]),
                                 "validation_zeros": len(stimulus["validation_bits"])-sum(stimulus["validation_bits"]),
                                 "validation_start_bit": stimulus["validation_start_bit"], "validation_end_bit": stimulus["validation_end_bit"],
                                 "whole_input_bits": len(stimulus["bits"])},
            "evidence_boundary": "GF180 transistor pre-layout simulation plus assumed LED dynamics and noiseless receiver; no optical BER, silicon, PEX, or tape-out claim",
            "cases": records}
    analysis_path = work/"analysis.json"
    analysis_path.write_text(json.dumps(full, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    rows = [compact_row(r) for r in records]
    compact = {k: v for k, v in full.items() if k != "cases"}
    compact.update({"analysis_json": relative(analysis_path), "analysis_sha256": digest(analysis_path), "rows": rows,
                    "simulation_failures": [r for r in records if not r["simulation_ok"]],
                    "analysis_failures": [r for r in records if r["simulation_ok"] and not r["analysis_ok"]]})
    compact["highest_nominal_comparison_screen_point_Gbps"] = {
        route: max((r["rate_Gbps"] for r in rows if r["route"] == route and r["kind"] == "nominal" and r.get("comparison_screen_passed")), default=None)
        for route in ["A", "B"]}
    compact["rate_caution"] = "highest passing point among this finite sweep; not the maximum link rate; stress screen reported separately"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir/"summary.json").write_text(json.dumps(compact, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (output_dir/"summary.csv").open("w", newline="") as fp:
        writer = csv.DictWriter(fp, fields)
        writer.writeheader()
        writer.writerows(rows)
    return compact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", help="frozen run directory; defaults to evidence/highspeed-nrz/latest-run.json")
    parser.add_argument("--output-dir", default="evidence/highspeed-nrz", help="compact summary output; full analysis always stays in work")
    args = parser.parse_args()
    work = Path(args.work or json.loads((ROOT/"evidence/highspeed-nrz/latest-run.json").read_text())["work"])
    if not work.is_absolute():
        work = ROOT/work
    output = Path(args.output_dir)
    if not output.is_absolute():
        output = ROOT/output
    summary = analyze(work.resolve(), output.resolve())
    print(json.dumps({"counts": summary["counts"], "highest_nominal_comparison_screen_point_Gbps": summary["highest_nominal_comparison_screen_point_Gbps"],
                      "summary_json": relative(output/"summary.json")}, ensure_ascii=False, indent=2))
    if summary["counts"]["analysis_failures"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
