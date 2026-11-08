#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Conditional whole-chain magnitude fitting, never physical transient calibration.

Run with the separately pinned calibration environment. Output is deliberately
separate from the historical 200 fF / 200 ps / RX 1 GHz baseline.
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import least_squares, minimize_scalar
from scipy.signal import TransferFunction, step

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/microled-dynamic-v1/calibration"
EVIDENCE = ROOT / "evidence/microled-dynamic-v1"
MODEL = ROOT / "analog/models/microled_dynamic_v1"
SOURCE = ROOT / "evidence/microled-dynamic-20261029"
FREF = 30e6
BIASES = [25, 50, 60, 80, 100]
FAMILIES = ["real2p", "real3p", "real4p", "real3p1z", "real4p2z", "complex3p1z", "complex4p2z"]
FAMILY_SIZE = {"real2p": (2, 0), "real3p": (3, 0), "real4p": (4, 0), "real3p1z": (3, 1), "real4p2z": (4, 2), "complex3p1z": (3, 1), "complex4p2z": (4, 2)}
# Descriptive engineering tolerances, not an instrument uncertainty budget.
TOLERANCE = {"rmse_dB": 0.35, "max_abs_dB": 1.25}


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_write(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(header)
        writer.writerows(rows)


def poly(family, theta):
    """Ascending coefficients in q=s/(2*pi*1e9); constant term is one."""
    values = 10 ** np.asarray(theta)
    num, den = np.array([1.]), np.array([1.])
    mul = np.polynomial.polynomial.polymul
    if family.startswith("real"):
        npoles, _ = FAMILY_SIZE[family]
        for p in values[:npoles]:
            den = mul(den, [1., 1. / p])
        for z in values[npoles:]:
            num = mul(num, [1., 1. / z])
    else:
        if family == "complex3p1z":
            p, w0, zeta, z = values
            den = mul([1., 1. / p], [1., 2 * zeta / w0, 1 / w0 ** 2])
            num = np.array([1., 1. / z])
        else:
            p, px, w0, zeta, z, zx = values
            den = mul(mul([1., 1. / p], [1., 1. / px]), [1., 2 * zeta / w0, 1 / w0 ** 2])
            num = mul([1., 1. / z], [1., 1. / zx])
    return num, den


def transfer(frequency, family, theta):
    num, den = poly(family, theta)
    q = 1j * np.asarray(frequency) / 1e9
    ev = np.polynomial.polynomial.polyval
    h = ev(q, num) / ev(q, den)
    h0 = ev(1j * FREF / 1e9, num) / ev(1j * FREF / 1e9, den)
    return h / abs(h0)


def predict(frequency, family, theta):
    return 20 * np.log10(abs(transfer(frequency, family, theta)))


def metrics(error, frequency):
    result = {}
    for label, mask in [("full_30MHz_to3GHz", np.ones(len(error), dtype=bool)),
                        ("restricted_30MHz_to2p5GHz", frequency <= 2.5e9)]:
        if not mask.any():
            result[label] = {"count": 0, "rmse_dB": None, "max_abs_dB": None, "mean_dB": None}
        else:
            residual = error[mask]
            result[label] = {"count": int(mask.sum()), "rmse_dB": float(np.sqrt(np.mean(residual ** 2))),
                             "max_abs_dB": float(max(abs(residual))), "mean_dB": float(np.mean(residual))}
    return result


def fit(frequency, db, family, starts=4):
    npoles, nzeros = FAMILY_SIZE[family]
    count = npoles + nzeros
    if family == "complex3p1z":
        initial = [[-.5, .35, -.2, -.4], [0., .35, -.25, 0.], [.4, .4, -.3, 1.7]]
    elif family == "complex4p2z":
        initial = [[-.5, 1., .35, -.2, -.4, .5], [-1.6, -.5, .35, -.25, -1.8, -.4], [0., .5, .35, -.2, 0., .8]]
    else:
        initial = [list(np.r_[np.linspace(.3, .8, npoles), np.linspace(-.3, .2, nzeros)])]
    rng = np.random.default_rng(20261108)
    while len(initial) < starts:
        initial.append(list(rng.uniform(-.5, .7, count)))
    trials = []
    for x in initial:
        opt = least_squares(lambda t: predict(frequency, family, t) - db, x,
                            bounds=(-2, 2), max_nfev=700, ftol=1e-10, xtol=1e-10, gtol=1e-10)
        trials.append({"theta_log10": opt.x.tolist(), "cost": float(opt.cost),
                       "success": bool(opt.success), "nfev": int(opt.nfev), "message": opt.message})
    best = min(trials, key=lambda r: r["cost"])
    theta = np.asarray(best["theta_log10"])
    return {"family": family, "theta_log10": theta.tolist(), "trials": trials,
            "residual": metrics(predict(frequency, family, theta) - db, frequency),
            "bound_hit": bool(np.any(abs(theta) >= 1.999))}


def coefficient_card(fit_result):
    family, theta = fit_result["family"], fit_result["theta_log10"]
    num, den = poly(family, theta)
    gain = 1 / abs(np.polynomial.polynomial.polyval(1j * FREF / 1e9, num) /
                   np.polynomial.polynomial.polyval(1j * FREF / 1e9, den))
    poles = np.roots(den[::-1])
    zeros = np.roots(num[::-1])
    # Dimensionless time u=t*(2*pi*1e9); rescale only for reporting time.
    slow = max(-1 / p.real for p in poles)
    u = np.linspace(0, max(30 * slow, 100), 30000)
    _, response = step(TransferFunction((num * gain)[::-1], den[::-1]), T=u)
    checks = {
        "all_poles_strictly_LHP": bool(np.all(poles.real < 0)),
        "all_zeros_strictly_LHP": bool(np.all(zeros.real < 0)),
        "strictly_proper": bool(len(num) < len(den)),
        "normalization_at30MHz_dB": float(predict(np.array([FREF]), family, theta)[0]),
        "DC_gain_conditional_extrapolation": float(gain),
        "step_final_relative_error_to_DC": float(abs(response[-1] - gain) / gain),
        "step_peak_relative_to_DC": float(max(response) / gain),
        "step_min_relative_to_DC": float(min(response) / gain),
        "step_window_ns": float(u[-1] / (2 * np.pi)),
        "causality_scope": "stable proper finite-dimensional real transfer; numerical post-t=0 response only; phase not measured",
        "passivity_scope": "not an impedance or calibrated power-wave S matrix; electrical passivity is not inferred from a normalized electro-optic gain",
    }
    assert checks["all_poles_strictly_LHP"] and checks["all_zeros_strictly_LHP"] and checks["strictly_proper"]
    assert abs(checks["normalization_at30MHz_dB"]) < 1e-12
    assert checks["step_final_relative_error_to_DC"] < 1e-6
    return {"family": family, "theta_log10": theta, "parameter_definition":
            ("10**theta = real pole frequencies GHz then real zero frequencies GHz" if family.startswith("real") else
             "complex3p1z: [real_pole_GHz, complex_pair_natural_GHz, damping_ratio, real_zero_GHz]; complex4p2z: [real_pole_GHz,extra_real_pole_GHz,complex_pair_natural_GHz,damping_ratio,real_zero_GHz,extra_real_zero_GHz]"),
            "q_definition": "q=s/(2*pi*1e9)", "numerator_ascending_q": (num * gain).tolist(),
            "denominator_ascending_q": den.tolist(),
            "poles_q_real_imag": [[float(p.real), float(p.imag)] for p in poles],
            "zeros_q_real_imag": [[float(z.real), float(z.imag)] for z in zeros], "checks": checks}


def compatible_chain(frequency, rd, cap, tau, rsource=50., detector=3e9):
    resistance = 1 / (1 / rd + 1 / rsource)
    def h(f):
        return (1 / (1 + 2j * np.pi * f * resistance * cap) /
                (1 + 2j * np.pi * f * tau) / (1 + 1j * f / detector))
    return 20 * np.log10(abs(h(frequency) / h(FREF)))


def main():
    for d in (BUILD, EVIDENCE, MODEL):
        d.mkdir(parents=True, exist_ok=True)
    source_paths = [SOURCE / name for name in ["yellow20-s21-selected.csv", "yellow20-optical-power.csv", "source-ledger.json", "response-contract.json"]]
    source_paths += [ROOT / "analog/models/measured-led/lin2026-yellow20-diamond-iv.csv", ROOT / "analog/models/measured-led/lin2026-yellow20-dc.spice"]
    sources = [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in source_paths]
    data = np.genfromtxt(source_paths[0], delimiter=",", names=True)
    frequency = data["frequency_Hz"]
    measured = {b: data[f"S21_dB_at_{b}uA"] for b in BIASES}
    assert len(frequency) == 2001 and np.all(np.diff(frequency) > 0)
    assert frequency[0] == FREF and frequency[-1] == 3e9
    assert all(v[0] == 0 for v in measured.values())
    allfits, chosen, residual_rows, summary_rows = {}, {}, [], []
    for bias in BIASES:
        trials = {family: fit(frequency, measured[bias], family) for family in FAMILIES}
        allfits[str(bias)] = trials
        best = min(r["residual"]["full_30MHz_to3GHz"]["rmse_dB"] for r in trials.values())
        eligible = [r for r in trials.values() if r["residual"]["full_30MHz_to3GHz"]["rmse_dB"] <= best + .03]
        # Use the smallest state/parameter count when improvement is <0.03 dB.
        result = min(eligible, key=lambda r: (FAMILY_SIZE[r["family"]][0], sum(FAMILY_SIZE[r["family"]]), r["residual"]["full_30MHz_to3GHz"]["rmse_dB"]))
        chosen[str(bias)] = result
        for family, r in trials.items():
            full, restricted = (r["residual"][k] for k in ["full_30MHz_to3GHz", "restricted_30MHz_to2p5GHz"])
            summary_rows.append([bias, family, family == result["family"], full["rmse_dB"], full["max_abs_dB"], restricted["rmse_dB"], restricted["max_abs_dB"], r["bound_hit"]])
        for f, y, pred in zip(frequency, measured[bias], predict(frequency, result["family"], result["theta_log10"])):
            residual_rows.append([bias, f, y, pred, pred - y])
        print(f"fit {bias}uA: {result['family']} {result['residual']}", flush=True)
    write(BUILD / "all-fit-trials.json", allfits)
    csv_write(EVIDENCE / "fit-family-summary.csv", ["bias_uA", "family", "selected", "rmse_full_dB", "peak_full_dB", "rmse_le2p5GHz_dB", "peak_le2p5GHz_dB", "bound_hit"], summary_rows)
    csv_write(EVIDENCE / "fit-residuals.csv", ["bias_uA", "frequency_Hz", "source_S21_dB", "conditional_model_dB", "model_minus_source_dB"], residual_rows)
    validation, validation_rows = [], []
    splits = {
        "interleaved_frequency_mod5eq2": np.arange(len(frequency)) % 5 == 2,
        "contiguous_frequency_0p8to1p2GHz": (frequency >= .8e9) & (frequency <= 1.2e9),
        "high_edge_extrapolation_2p6to3GHz": frequency >= 2.6e9,
    }
    # Family selection used the full curve; the validation of its coefficients is
    # conditional on that selected family, not nested model-selection validation.
    for bias in BIASES:
        family = chosen[str(bias)]["family"]
        for split, heldout in splits.items():
            result = fit(frequency[~heldout], measured[bias][~heldout], family)
            prediction = predict(frequency, family, result["theta_log10"])
            entry = {"bias_uA": bias, "split": split, "family": family, "training_count": int((~heldout).sum()),
                     "holdout_count": int(heldout.sum()), "training": metrics(prediction[~heldout] - measured[bias][~heldout], frequency[~heldout]),
                     "holdout": metrics(prediction[heldout] - measured[bias][heldout], frequency[heldout]), "bound_hit": result["bound_hit"]}
            validation.append(entry)
            write(BUILD / f"validation-{bias}uA-{split}.json", {"fit": result, "validation": entry})
            validation_rows.extend([bias, split, f, y, p, p - y] for f, y, p in zip(frequency[heldout], measured[bias][heldout], prediction[heldout]))
    bias_validation = []
    for bias in BIASES:
        others = [b for b in BIASES if b != bias]
        lo = max([b for b in others if b < bias], default=others[0])
        hi = min([b for b in others if b > bias], default=others[-1])
        if lo == hi:
            lo, hi = (others[:2] if bias == min(BIASES) else others[-2:])
        def curve(b):
            r = chosen[str(b)]
            return predict(frequency, r["family"], r["theta_log10"])
        weight = np.log(bias / lo) / np.log(hi / lo)
        prediction = (1 - weight) * curve(lo) + weight * curve(hi)
        bias_validation.append({"holdout_bias_uA": bias, "training_neighbor_biases_uA": [lo, hi], "log_bias_weight": float(weight),
                                "mode": "interpolation" if 0 <= weight <= 1 else "extrapolation", "residual": metrics(prediction - measured[bias], frequency)})
        validation_rows.extend([bias, "leave_one_bias_out_logI_magnitude", f, y, p, p - y] for f, y, p in zip(frequency, measured[bias], prediction))
    csv_write(EVIDENCE / "fit-validation-residuals.csv", ["bias_uA", "split", "frequency_Hz", "source_S21_dB", "prediction_dB", "prediction_minus_source_dB"], validation_rows)
    write(EVIDENCE / "fit-validation.json", {"frequency_holdouts": validation, "bias_holdouts": bias_validation,
        "scope": "same deposited processed magnitude curves only; no independent device/temperature/phase validation",
        "selection_caveat": "frequency holdouts refit coefficients after holding out frequencies, conditional on a family chosen using the full curve; model selection is not externally validated",
        "bias_method": "linear interpolation/extrapolation of normalized model dB in log bias; endpoint extrapolation explicitly labelled; no physical charge-state interpretation"})
    iv = np.genfromtxt(source_paths[4], delimiter=",", names=True)
    pi = np.genfromtxt(source_paths[1], delimiter=",", names=True)
    compatibility, chain_rows, static, best_taus = [], [], [], []
    for bias in BIASES:
        current = bias * 1e-6
        k = int(np.searchsorted(iv["current_A"], current) - 1)
        rd = float((iv["voltage_V"][k + 1] - iv["voltage_V"][k]) / (iv["current_A"][k + 1] - iv["current_A"][k]))
        static.append({"bias_uA": bias, "voltage_V": float(np.interp(current, iv["current_A"], iv["voltage_V"])),
                       "rd_ohm": rd, "IV_source_rows": [int(iv["source_excel_row"][k]), int(iv["source_excel_row"][k + 1])],
                       "static_optical_power_uW": float(np.interp(current, pi["current_A"], pi["source_optical_power_uW"])),
                       "same_physical_pixel_across_IV_PI_S21": "not established"})
        for cap_fF in [10, 50, 200, 800]:
            cap = cap_fF * 1e-15
            for tau_ps in [0, 25, 75, 200]:
                pred = compatible_chain(frequency, rd, cap, tau_ps * 1e-12)
                resid = metrics(pred - measured[bias], frequency)
                full = resid["full_30MHz_to3GHz"]
                entry = {"bias_uA": bias, "C_fF": cap_fF, "tau_ps": tau_ps, "residual": resid,
                         "inside_descriptive_tolerance": bool(full["rmse_dB"] <= TOLERANCE["rmse_dB"] and full["max_abs_dB"] <= TOLERANCE["max_abs_dB"]),
                         "electrical_tau_50ohm_ps": (50 * rd / (50 + rd)) * cap * 1e12,
                         "electrical_tau_ideal_current_rdC_ps": rd * cap * 1e12}
                compatibility.append(entry)
                chain_rows.append([bias, cap_fF, tau_ps, full["rmse_dB"], full["max_abs_dB"], resid["restricted_30MHz_to2p5GHz"]["rmse_dB"], resid["restricted_30MHz_to2p5GHz"]["max_abs_dB"], entry["electrical_tau_50ohm_ps"], entry["electrical_tau_ideal_current_rdC_ps"], entry["inside_descriptive_tolerance"]])
            # Conditional best single optical pole: a diagnostic, never lifetime extraction.
            opt = minimize_scalar(lambda tau: np.mean((compatible_chain(frequency, rd, cap, tau * 1e-12) - measured[bias]) ** 2), bounds=(0, 1000), method="bounded")
            best_tau = {"bias_uA": bias, "C_fF": cap_fF, "tau_ps": float(opt.x), "residual": metrics(compatible_chain(frequency, rd, cap, opt.x * 1e-12) - measured[bias], frequency), "status": "conditional source50ohm/detector3GHz single-pole shape diagnostic; not measured lifetime"}
            best_taus.append(best_tau)
            write(BUILD / f"best-synthetic-tau-{bias}uA-{cap_fF}fF.json", best_tau)
    csv_write(EVIDENCE / "fit-physical-compatibility.csv", ["bias_uA", "C_fF", "tau_ps", "rmse_full_dB", "peak_full_dB", "rmse_le2p5GHz_dB", "peak_le2p5GHz_dB", "tau_R50parallelrd_ps", "tau_idealcurrent_rdC_ps", "inside_descriptive_tolerance"], chain_rows)
    write(EVIDENCE / "fit-physical-compatibility.json", {"assumptions": {"Rsource_ohm": 50, "detector_onepole_Hz": 3e9, "package": "omitted/unknown", "formula": "H=1/(1+s*(50||rd)*C)/(1+s*tau)/(1+s/(2*pi*3GHz)), magnitude normalized at30MHz", "parameter_status": "all dynamic circuit parameters synthetic; neither source impedance nor detector response deembedded/calibrated"}, "tolerance": TOLERANCE, "static_replay_points": static, "matrix": compatibility,
        "conditional_best_single_tau_for_each_C": best_taus,
        "interpretation": "matching this restricted source-plane family does not identify C/tau or make it valid for another source impedance; failure rejects the specified simple family under its assumptions, not the measured LED",
        "no_double_counting": "Never cascade the fitted whole-chain H with physical electrical C, recombination pole or receiver; this compatibility matrix is an alternative illustrative source measurement chain."})
    cards = {str(b): coefficient_card(chosen[str(b)]) for b in BIASES}
    fit_summary = {str(b): {"family": chosen[str(b)]["family"], "residual": chosen[str(b)]["residual"], "bound_hit": chosen[str(b)]["bound_hit"]} for b in BIASES}
    for summary in fit_summary.values():
        for domain, values in summary["residual"].items():
            summary[domain + "_within_descriptive_tolerance"] = bool(values["rmse_dB"] <= TOLERANCE["rmse_dB"] and values["max_abs_dB"] <= TOLERANCE["max_abs_dB"])
        summary["physical_transient_admissibility"] = "not established regardless of magnitude residual"
    counterexamples = []
    for bias in BIASES:
        r = chosen[str(bias)]
        h = transfer(frequency, r["family"], r["theta_log10"])
        delay = np.exp(-2j * np.pi * frequency * 100e-12)
        a = 1 / 100e-12
        allpass = (a - 2j * np.pi * frequency) / (a + 2j * np.pi * frequency)
        counterexamples.append({"bias_uA": bias, "100ps_delay_max_magnitude_difference": float(max(abs(abs(h * delay) - abs(h)))),
                                "stable_allpass_max_magnitude_difference": float(max(abs(abs(h * allpass) - abs(h)))),
                                "allpass": "A(s)=(1/100ps-s)/(1/100ps+s): causal stable, nonminimum-phase, identical magnitude"})
        assert counterexamples[-1]["100ps_delay_max_magnitude_difference"] < 1e-12
        assert counterexamples[-1]["stable_allpass_max_magnitude_difference"] < 1e-12
    write(MODEL / "coefficients.json", {"schema_version": 1, "model_id": "yellow20-wholechain-magnitude-conditional-v1", "reference_Hz": FREF, "bias_uA": BIASES, "coefficients": cards,
        "application": "frequency-domain whole original chain only; no physical C/tau assignment and no transistor-transient activation"})
    card = {"schema_version": 1, "model_id": "yellow20-wholechain-magnitude-conditional-v1", "status": "conditional_frequency_fit_only",
        "usable_transient_family": False, "physical_dynamic_calibration_complete": False,
        "source_observable": "author-normalized measured-chain S21 magnitude in dB; 20log10(abs(H)) numeric convention;30MHz-to3GHz,25/50/60/80/100uA",
        "source_license": "numerical dataset CC BY4.0; Lin et al. Zenodo10.5281/zenodo.20034288; paper DOI10.1038/s41467-026-74151-4 cited, no paper figure reused",
        "sources": sources, "static_inputs": static,
        "fit_method": {"loss": "unweighted least squares in author S21 dB over uniform source frequency samples", "normalization": "exact unity magnitude at30MHz, conditional extrapolated DC gain is not measured", "bounded_parameters": "pole/zero characteristic frequencies10MHz..100GHz; damping0.01..100; deterministic multistart", "families": FAMILIES, "maximum_order": 4, "selection": "lowest state/parameter count within0.03dB RMSE of best tested family per bias; no order added to follow near3GHz noise", "tolerance": TOLERANCE, "tolerance_status": "descriptive diagnostic only; instrument uncertainty and repeatability unavailable"},
        "fit_summary": fit_summary,
        "non_identifiability": {"minimum_phase": "explicit mathematical convention, not measured phase", "counterexamples": counterexamples,
            "decomposition": "For each arbitrary C, H_residual=H_total*(1+s*(50||rd)*C)*(1+s/(2*pi*3GHz)) reproduces the exact same fitted magnitude and is stable/proper for the selected relative-degree2 models; it introduces zeros without establishing physical optical dynamics. Unknown package/receiver add more degrees of freedom.",
            "unique_C": False, "unique_lifetime": False, "unique_delay_or_phase": False, "electrical_passivity_identified": False},
        "missing_domains": ["complex S11/impedance and RF stimulus at calibrated same-device plane", "complex S21 and group delay", "absolute gain and calibrated detector/fiber/package deembedding", "same pixel identity and temperature across I-V/P-I/S21", "measurement uncertainty, repeatability and near3GHz noise floor", "large-signal charge/recombination dynamics, transitions and pattern effects", "cross-device/cross-temperature validation, optical noise and BER"],
        "permitted": ["source magnitude replay and residual inspection", "conditional stable/minimum-phase mathematical frequency curves", "separately labelled C/tau/source/RX sensitivity"],
        "prohibited": ["append Htotal after an electrical RC or receiver model", "promote synthetic C/tau to uniquely measured parameters", "use assigned minimum-phase response as validated phase/transient eye", "claim net3.2Gb/s BER or physical optical-link qualification"],
        "baseline_policy": "historical200fF/200ps/RX1GHz model and old results unchanged", "coefficients": "coefficients.json"}
    write(MODEL / "model-card.json", card)
    write(EVIDENCE / "fit-summary.json", {"status": card["status"], "usable_transient_family": False, "source_hashes": sources, "fit_summary": fit_summary,
        "frequency_holdouts": validation, "bias_holdouts": bias_validation, "numerical_checks": {b: cards[b]["checks"] for b in cards}, "allpass_delay_counterexamples": counterexamples,
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}, "script_sha256": sha(Path(__file__))})
    (MODEL / "requirements.txt").write_text("numpy==2.0.2\nscipy==1.13.1\n")
    (MODEL / "NOTICE.md").write_text("# Attribution and scope\n\nConditional numerical fits to the CC BY 4.0 source dataset by Runze Lin et al., Zenodo DOI 10.5281/zenodo.20034288. Source locators and original archive/workbook hashes are preserved in evidence/microled-dynamic-20261029/source-ledger.json. Paper DOI 10.1038/s41467-026-74151-4 is cited for context; no paper figure is copied here.\n\nThese are independent normalized whole-chain magnitude fits. Phase, capacitance, lifetime, package, temperature and large-signal behavior are not identified. Coefficients do not activate a physical transient model.\n")
    lines = ["# 黄色20µm MicroLED条件化幅频模型卡", "", "**状态：仅对原测量整链的normalized magnitude作条件化拟合；物理动态联合校准未闭合，不能激活为器件瞬态模型。**", "", "基于作者存档的30MHz–3GHz、25/50/60/80/100µA数据。保留原200fF/200ps/RX1GHz历史基线。静态I–V/P–I与S21是否来自同一颗像素，尚未建立。", "", "| 偏置/µA | 选中模型 | 全频RMSE/峰误差 dB | ≤2.5GHz RMSE/峰误差 dB |", "|---:|---|---:|---:|"]
    for b in BIASES:
        result = fit_summary[str(b)]
        full, restricted = (result["residual"][k] for k in ["full_30MHz_to3GHz", "restricted_30MHz_to2p5GHz"])
        lines.append(f"| {b} | {result['family']} | {full['rmse_dB']:.3f} / {full['max_abs_dB']:.3f} | {restricted['rmse_dB']:.3f} / {restricted['max_abs_dB']:.3f} |")
    lines.extend(["", "选阶最多4阶；3pole/1zero与最后4pole/2zero候选相比，误差收益小于0.03dB，采用较小模型。complex pair与zero是数学自由度，没有识别为LED复合、封装或检测器物理机制。80/100µA的zero触到100GHz边界，参数解释更弱。≤2.5GHz只是剔除近3GHz段后的残差，未证明该域的仪器SNR或绝对准确度。", "", "频率验证含每5点留1、0.8–1.2GHz整段留出、2.6–3GHz边缘外推；另有逐偏置留出。选阶使用过完整曲线，因此频率验证只检验给定family的系数，不是nested model-selection validation。所有留出均来自同一份已处理数据，不能代替独立器件/温度/相位验证。", "", "`coefficients.json`使用q=s/(2π×1GHz)，分子分母系数按升幂排列。归一化只固定30MHz幅值，DC增益是模型外推。数值检查覆盖LHP poles/zeros、strictly proper、30MHz归一和step终值；它们证明数学模型的稳定/因果结构，不能证明真实LED的phase、passivity或瞬态。", "", "在明确假定source50Ω、detector3GHz、未知封装省略的替代整链中，C10/50/200/800fF与tau0/25/75/200ps共80组，没有一组满足描述性RMSE≤0.35dB且峰误差≤1.25dB。逐C重新选单一tau也不能解释全部曲线形状。此结果约束该简单模型族；不能据此断言真实LED的C或lifetime。", "", "相同幅值可加100ps delay或稳定all-pass；相位与采样时刻仍不唯一。任意C也可通过修改稳定residual transfer保持同一整链拟合。因此缺失同器件complex S11/S21、RF幅度、校准面、RX/封装去嵌、温度与large-signal数据时，动态器件校准不闭合。", "", "**禁止将整链Htotal叠加到已有电学RC、optical tau或RX后。不得把这些拟合系数宣称为实测C/lifetime、净3.2Gb/s BER或光链路资格。**", "", "来源、hash、拟合与验证细节见model-card.json及evidence/microled-dynamic-v1/fit-*.json/CSV；原始失败候选和multistart日志在build/microled-dynamic-v1/calibration/。", ""])
    (MODEL / "MODEL_CARD.md").write_text("\n".join(lines))
    print(json.dumps({"status": card["status"], "usable_transient_family": False, "checks_passed": True, "selected": fit_summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
