#!/usr/bin/env python3
"""Reproducible teaching calculations, never a fitted MicroLED model.

Run from any directory with Python >= 3.9. No third-party dependency is used.
The JSON contains synthetic examples, exact accounting and algebraic checks;
it does not run SPICE, change a circuit, or establish optical BER.
"""

from __future__ import annotations

import argparse
import cmath
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence/microled-device-codesign-20261029/calculations.json"
CONTRACT = ROOT / "evidence/microled-dynamic-20261029/response-contract.json"
SPEC = ROOT / "docs/superpowers/specs/2026-10-25-fair-driver-v1.md"
RX_CONTRACT = ROOT / "evidence/fair-driver-v1/rx-equal-latency-v2-contract.md"
RX_V3 = ROOT / "scripts/three_gbps_experiment/vcsel_driver_receiver_v3.py"
Q_C = 1.602176634e-19
# Python 3.9/3.12 differ by ~1 ULP at these three derived ABC leaves.
# Deliberately do not relax all floats, inputs, integer counts or identities.
FLOAT_REL_TOLERANCE_PATHS = {
    "/abc/rows/2/recombination_cm_inv3_s_inv": 1e-12,
    "/abc/rows/2/density_over_recombination_lifetime_ns": 1e-12,
    "/abc/rows/2/radiative_fraction_ABC_only": 1e-12,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one_pole_amplitude(f_hz: float, pole_hz: float) -> float:
    return 1 / math.sqrt(1 + (f_hz / pole_hz) ** 2)


def cascade_amplitude(f_hz: float, poles_hz: list[float]) -> float:
    return math.prod(one_pole_amplitude(f_hz, p) for p in poles_hz)


def cascade_half_power_hz(poles_hz: list[float]) -> float:
    """Solve |H|**2 = 1/2, i.e. -3.0102999566 dB of amplitude."""
    lo, hi = 0.0, max(poles_hz)
    for _ in range(150):
        mid = (lo + hi) / 2
        if cascade_amplitude(mid, poles_hz) ** 2 > 0.5:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def zero_error_upper_bound(n_bits: int, alpha: float = 0.05) -> float:
    # expm1 avoids cancellation at BER targets near 1e-12.
    return -math.expm1(math.log(alpha) / n_bits)


def zero_error_required_bits(target_ber: float, alpha: float = 0.05) -> int:
    return math.ceil(math.log(alpha) / math.log1p(-target_ber))


def comparison_differences(stored: object, fresh: object, path: str = "") -> list[str]:
    """Strict structural comparison with three explicitly bounded float leaves."""
    if type(stored) is not type(fresh):
        return [f"{path}: type differs ({type(stored).__name__}/{type(fresh).__name__})"]
    if isinstance(stored, dict):
        if stored.keys() != fresh.keys():
            return [f"{path}: keys differ"]
        return [diff for key in stored
                for diff in comparison_differences(stored[key], fresh[key], path + "/" + str(key))]
    if isinstance(stored, list):
        if len(stored) != len(fresh):
            return [f"{path}: list length differs"]
        return [diff for i, (old, new) in enumerate(zip(stored, fresh))
                for diff in comparison_differences(old, new, path + "/" + str(i))]
    if isinstance(stored, float) and path in FLOAT_REL_TOLERANCE_PATHS:
        if (math.isfinite(stored) and math.isfinite(fresh)
                and math.isclose(stored, fresh, rel_tol=FLOAT_REL_TOLERANCE_PATHS[path], abs_tol=0.0)):
            return []
    elif stored == fresh:
        return []
    return [f"{path}: value differs ({stored!r}/{fresh!r})"]


def build() -> dict:
    contract = json.loads(CONTRACT.read_text())
    assert contract["observed_response"]["phase"] is None
    assert "no new transient model activated" in contract["status"]

    payload, frame = 4096, 4736
    eta, net_bps = payload / frame, 3.2e9
    line_bps = net_bps / eta
    frame_s = frame / line_bps
    nrz_symbol_hz = line_bps
    pam4_symbol_hz = line_bps / 2
    frame_data = {
        "evidence_class": "arithmetic from existing frozen test-frame contract",
        "payload_bits": payload,
        "frame_bits": frame,
        "overhead_bits": frame - payload,
        "parts_bits": {"warm": 64, "training_scoring": 448, "training_guard": 64,
                       "validation": 4096, "tail": 64},
        "ranges_bits_left_closed_right_open": {"warm": [0, 64], "training_scoring": [64, 512],
                                               "training_guard": [512, 576],
                                               "validation": [576, 4672], "tail": [4672, 4736]},
        "payload_efficiency_exact": "32/37",
        "payload_efficiency": eta,
        "net_payload_bps": net_bps,
        "line_bit_rate_bps": line_bps,
        "frame_duration_us": frame_s * 1e6,
        "nrz": {"symbols_per_frame": frame, "baud": nrz_symbol_hz,
                "symbol_UI_ps": 1e12 / nrz_symbol_hz, "nyquist_Hz": nrz_symbol_hz / 2},
        "pam4": {"symbols_per_frame": frame // 2, "baud": pam4_symbol_hz,
                 "symbol_UI_ps": 1e12 / pam4_symbol_hz, "nyquist_Hz": pam4_symbol_hz / 2,
                 "condition": "2 bits/symbol; same 32/37 test-frame efficiency; no added FEC/encoding overhead"},
        "boundary": "The original 512-bit training overhead consists of 448 scoring bits and 64 guard bits; the guard does not train the receiver. This is test accounting, not an implemented product protocol. Extra framing/FEC must reduce efficiency or raise line rate. Nyquist alone does not predict eye opening or BER.",
    }

    geometry = []
    for side in (5, 10, 20, 40):
        area_um2 = side ** 2
        area_cm2 = area_um2 * 1e-8
        circle_area_um2 = math.pi * side ** 2 / 4
        geometry.append({
            "square_side_um": side, "square_area_um2": area_um2,
            "square_area_cm2": area_cm2, "square_perimeter_um": 4 * side,
            "square_perimeter_over_area_um_inv": 4 / side,
            "same_I_25uA_J_A_cm2": 25e-6 / area_cm2,
            "same_I_100uA_J_A_cm2": 100e-6 / area_cm2,
            "same_J_25A_cm2_I_uA": 25 * area_cm2 * 1e6,
            "circle_if_same_numerical_DIAMETER_um": side,
            "circle_area_um2": circle_area_um2,
            "circle_J_at_100uA_A_cm2": 100e-6 / (circle_area_um2 * 1e-8),
            "circle_DIAMETER_um_for_equal_square_area": 2 * side / math.sqrt(math.pi),
        })

    # Deliberately chosen dimensions, not extracted device parameters.
    c_area_ff_um2, c_perimeter_ff_um, c_fixed_ff = 0.25, 0.1, 100.0
    nvt_v, source_ohm = 0.05, 50.0
    rc_rows = []
    for g in geometry:
        area, perimeter = g["square_area_um2"], g["square_perimeter_um"]
        c_geom_ff = c_area_ff_um2 * area + c_perimeter_ff_um * perimeter
        c_total_f = (c_geom_ff + c_fixed_ff) * 1e-15
        row = {"square_side_um": g["square_side_um"], "geometric_C_fF": c_geom_ff,
               "fixed_C_fF": c_fixed_ff, "total_C_fF": c_total_f * 1e15,
               "fixed_C_fraction": c_fixed_ff / (c_geom_ff + c_fixed_ff),
               "fixed_50ohm_tau_ps": source_ohm * c_total_f * 1e12,
               "fixed_50ohm_pole_GHz": 1 / (2 * math.pi * source_ohm * c_total_f) / 1e9}
        for key, i_a in (("same_I_100uA", 100e-6),
                         ("same_J_25A_cm2", g["same_J_25A_cm2_I_uA"] * 1e-6)):
            rd = nvt_v / i_a
            tau_i = rd * c_total_f
            tau_v = (1 / (1 / rd + 1 / source_ohm)) * c_total_f
            row[key] = {"I_uA": i_a * 1e6, "rd_ohm": rd,
                        "ideal_current_input_tau_ps": tau_i * 1e12,
                        "ideal_current_input_pole_GHz": 1 / (2 * math.pi * tau_i) / 1e9,
                        "voltage_via_50ohm_tau_ps": tau_v * 1e12,
                        "voltage_via_50ohm_pole_GHz": 1 / (2 * math.pi * tau_v) / 1e9,
                        "ideal_current_area_C_only_tau_ps": rd * c_area_ff_um2 * area * 1e-15 * 1e12}
        rc_rows.append(row)
    rc = {
        "evidence_class": "synthetic illustrative lumped electrical calculation; never measured/fitted",
        "assumptions": {"area_capacitance_fF_per_um2": c_area_ff_um2,
                        "perimeter_capacitance_fF_per_um": c_perimeter_ff_um,
                        "fixed_pad_package_capacitance_fF": c_fixed_ff,
                        "n_times_thermal_voltage_V": nvt_v, "voltage_source_series_R_ohm": source_ohm},
        "equations": {"C": "c_area*A + c_perimeter*P + C_fixed",
                      "rd": "nVT/I (hypothetical local exponential slope, no added contact resistance)",
                      "current_input": "I_conductive/I_terminal = 1/(1+s*rd*C)",
                      "voltage_input_normalized": "H/H(0) = 1/(1+s*(Rs||rd)*C)"},
        "rows": rc_rows,
        "fixed_50ohm_Cfloor_only_tau_ps": source_ohm * c_fixed_ff * 1e-15 * 1e12,
        "fixed_50ohm_Cfloor_only_pole_GHz": 1 / (2 * math.pi * source_ohm * c_fixed_ff * 1e-15) / 1e9,
        "boundary": "The pad floor limits capacitance scaling; it is a time-constant floor and an RC-pole ceiling only under the stated fixed resistance. Real Zout(f,state), contact/spreading R, distributed electrodes, lifetime, optical gain and heat are omitted. This table is not an EO bandwidth prediction.",
    }

    # ABC is one spatially uniform effective reservoir, not a MQW fit.
    a_s, b_cm3_s, c_cm6_s, d_cm = 1e7, 1e-11, 1e-30, 9e-7
    abc_rows = []
    for n_cm3 in (1e18, 3e18, 1e19):
        rates = [a_s * n_cm3, b_cm3_s * n_cm3 ** 2, c_cm6_s * n_cm3 ** 3]
        r_total = sum(rates)
        rate_differential = a_s + 2 * b_cm3_s * n_cm3 + 3 * c_cm6_s * n_cm3 ** 2
        abc_rows.append({"carrier_density_cm_inv3": n_cm3,
                         "recombination_cm_inv3_s_inv": r_total,
                         "differential_recombination_rate_s_inv": rate_differential,
                         "differential_lifetime_ns": 1e9 / rate_differential,
                         "density_over_recombination_lifetime_ns": n_cm3 / r_total * 1e9,
                         "intrinsic_one_reservoir_pole_MHz": rate_differential / (2 * math.pi) / 1e6,
                         "radiative_fraction_ABC_only": rates[1] / r_total,
                         "J_if_uniform_9nm_and_injection_efficiency_1_A_cm2": Q_C * d_cm * r_total})
    abc = {
        "evidence_class": "synthetic illustrative rate-equation calculation; not any published device fit",
        "assumptions": {"A_s_inv": a_s, "B_cm3_per_s": b_cm3_s,
                        "C_cm6_per_s": c_cm6_s, "uniform_effective_active_thickness_nm": 9,
                        "injection_efficiency": 1, "q_C_exact_SI": Q_C},
        "equations": {"R": "A*n+B*n^2+C*n^3", "tau_differential": "1/(A+2*B*n+3*C*n^2)",
                      "intrinsic_pole": "1/(2*pi*tau_differential)", "J": "q*d*R/eta_injection"},
        "rows": abc_rows,
        "boundary": "This assumes one uniform charge reservoir and locally constant ABC coefficients. QW transport/capture/escape, polarization, sidewalls, leakage, photon extraction and self-heating are omitted. Increasing A can speed nonradiative loss while lowering efficiency. Neither nominal QW count nor a magnitude-only cutoff uniquely determines this lifetime.",
    }

    nyquist_hz = nrz_symbol_hz / 2
    ratio_3db = math.sqrt(10 ** (3 / 10) - 1)
    ratio_6db = math.sqrt(10 ** (6 / 10) - 1)
    poles = [3e9, 2e9, 1e9]
    cascade_at_nyquist = cascade_amplitude(nyquist_hz, poles)
    pure_delay_s = 100e-12
    base_response = 1 / (1 + 1j * nyquist_hz / 2e9)
    delayed = base_response * cmath.exp(-2j * math.pi * nyquist_hz * pure_delay_s)
    conventions = {
        "evidence_class": "algebra for H=1/(1+j*f/fp), DC normalized, no peaking/delay",
        "detector_voltage_or_VNA_wave_amplitude_dB": "20*log10(|H|)",
        "optical_modulation_amplitude_is_watts": "If a source reports 10*log10(deltaP/deltaP0), its numerical dB is half 20*log10(|H|), assuming the detector is linear and no other transfer changes. Preserve the source definition/reference plane; optical carrier power and modulation amplitude are different quantities.",
        "at_pole_f_over_fp_1": {"amplitude_ratio": 1 / math.sqrt(2),
                                 "20log10_amplitude_dB": 20 * math.log10(1 / math.sqrt(2)),
                                 "10log10_optical_modulation_amplitude_dB": 10 * math.log10(1 / math.sqrt(2))},
        "at_amplitude_ratio_half": {"f_over_fp": math.sqrt(3),
                                    "20log10_amplitude_dB": 20 * math.log10(0.5),
                                    "10log10_optical_modulation_amplitude_dB": 10 * math.log10(0.5)},
        "exact_minus3dB_20log_f_over_fp": ratio_3db,
        "exact_minus6dB_20log_f_over_fp": ratio_6db,
        "exact_minus6_over_minus3_frequency_ratio_20log": ratio_6db / ratio_3db,
        "tau_ps_if_a_single_intrinsic_pole_is_1p85GHz": 1e12 / (2 * math.pi * nyquist_hz),
        "synthetic_cascade": {"poles_Hz": {"electrical": poles[0], "intrinsic_EO": poles[1], "RX": poles[2]},
                              "half_power_cutoff_Hz": cascade_half_power_hz(poles),
                              "amplitude_at_1p85GHz": cascade_at_nyquist,
                              "20log10_amplitude_at_1p85GHz_dB": 20 * math.log10(cascade_at_nyquist),
                              "condition": "Three distinct nonoverlapping blocks only. Do not count a recombination charge state both as diffusion capacitance in an electrical RC pole and again as an independent lifetime pole."},
        "magnitude_does_not_identify_phase": {"counterexample": "H(s) and H(s)*exp(-s*100ps)",
                                              "additional_delay_ps": pure_delay_s * 1e12,
                                              "additional_phase_at_1p85GHz_deg": -360 * nyquist_hz * pure_delay_s,
                                              "amplitude_ratio_between_delayed_and_original": abs(delayed) / one_pole_amplitude(nyquist_hz, 2e9)},
        "no_double_counting": "Use either an observed full measured chain with its original electrical source and detector, or calibrated separately deembedded blocks. Never fit full E-to-E S21 and append the same electrical/optical/RX pole again. Magnitude does not identify phase or delay.",
        "boundary": "A pole at Nyquist is a diagnostic example, not a required/sufficient BER criterion. Cascaded half-power frequency is not the minimum of the individual pole frequencies.",
    }

    ber_targets = []
    for target in (1e-12, 3e-12):
        n = zero_error_required_bits(target)
        ber_targets.append({"proposed_target_ber": target, "minimum_zero_error_bits_95percent_one_sided": n,
                            "exact_upper_bound_at_N": zero_error_upper_bound(n),
                            "wall_time_s_at_3p2G_validated_payload_bps": n / net_bps})
        assert n * math.log1p(-target) <= math.log(0.05)
        assert (n - 1) * math.log1p(-target) > math.log(0.05)
    ber = {
        "evidence_class": "exact one-sided binomial zero-error confidence calculation, conditional on IID stationary bit errors",
        "confidence": 0.95, "equation": "p_upper=1-alpha^(1/N); N_min=ceil(ln(alpha)/ln(1-p_target))",
        "N_4096_exact_upper": zero_error_upper_bound(payload),
        "N_4096_rule_of_three_upper": 3 / payload,
        "targets": ber_targets,
        "boundary": "1e-12 and 3e-12 are proposed planning thresholds, not the frozen project acceptance contract. A deterministic no-noise 0/4096 SPICE run is not random optical BER sampling. Repeating an identical trace creates no new independent evidence. Burst/correlated errors, drifting temperature, confidence across corners and FEC require additional design.",
        "source": "NIST/SEMATECH e-Handbook section 7.2.4.1 exact binomial interval; use alpha rather than alpha/2 for a one-sided upper limit: https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm",
    }

    vf_v, i_avg_a = 3.0, 100e-6
    energy = {
        "evidence_class": "synthetic LED-terminal-only constant-voltage/current example",
        "assumptions": {"Vf_V": vf_v, "Iavg_A": i_avg_a, "net_payload_bps": net_bps},
        "LED_terminal_average_power_uW": vf_v * i_avg_a * 1e6,
        "LED_terminal_pJ_per_offered_payload_bit": vf_v * i_avg_a / net_bps * 1e12,
        "equations": {"LED_exact": "integral_frame(V_LED(t)*I_LED(t) dt)/N_payload",
                      "LED_constant_approximation": "Vf*Iavg/Rnet",
                      "source_port_energy": "For each declared input port separately integrate positive, returned and net V*I over the same whole frame; divide by offered payload bits; report successfully delivered payload separately if errors occur."},
        "boundaries": {"LED_only": "Electrical energy at LED terminals, not emitted optical energy or full link energy.",
                       "declared_driver_ports": "State VIN5V, VDD3.3V, VREF2.5V, D0/D1 and DISABLE source planes plus included auxiliary devices/passives. External reference IC generation, upstream regulation and serializer/clock/encoding/DSP may be outside; explicitly list exclusions. Avoid counting terminal LED energy twice if its supply energy is already included.",
                       "closed_TX": "Include all physical TX supplies, LED, regulation/reference generation, serializer/clock, mapping/FEC and equalization/control overhead for the same net delivered payload. Summing an incomplete driver boundary and LED-only number does not close TX.",
                       "closed_link": "Additionally include optical loss assumptions, calibrated detector/TIA/CDR/equalization/FEC and RX power; this calculation supplies none of those."},
    }

    checks = {
        "frame_parts_sum": sum(frame_data["parts_bits"].values()) == frame,
        "exact_eta_32_over_37": eta == 32 / 37,
        "line_rate_3p7Gbps": math.isclose(line_bps, 3.7e9),
        "frame_1p28us": math.isclose(frame_s * 1e6, 1.28),
        "payload_and_frame_time_agree": math.isclose(payload / net_bps, frame_s),
        "sameJ_area_only_current_drive_tau_is_constant": all(math.isclose(r["same_J_25A_cm2"]["ideal_current_area_C_only_tau_ps"], 50) for r in rc_rows),
        "fixed_pad_fraction_grows_when_size_shrinks": all(rc_rows[i]["fixed_C_fraction"] > rc_rows[i + 1]["fixed_C_fraction"] for i in range(3)),
        "voltage_time_constants_below_current_time_constants": all(r[k]["voltage_via_50ohm_tau_ps"] < r[k]["ideal_current_input_tau_ps"] for r in rc_rows for k in ("same_I_100uA", "same_J_25A_cm2")),
        "cascade_cutoff_below_all_individual_poles": cascade_half_power_hz(poles) < min(poles),
        "cascade_root_half_power": math.isclose(cascade_amplitude(cascade_half_power_hz(poles), poles) ** 2, 0.5, rel_tol=1e-12),
        "allpass_delay_preserves_magnitude_but_changes_phase": math.isclose(abs(delayed), abs(base_response), rel_tol=1e-12) and not math.isclose(cmath.phase(delayed), cmath.phase(base_response)),
        "square_vs_same_numeric_diameter_area_ratio": all(math.isclose(g["square_area_um2"] / g["circle_area_um2"], 4 / math.pi) for g in geometry),
        "ABC_differential_lifetime_smaller_than_density_over_R": all(r["differential_lifetime_ns"] < r["density_over_recombination_lifetime_ns"] for r in abc_rows),
        "LED_example_0p09375pJ": math.isclose(energy["LED_terminal_pJ_per_offered_payload_bit"], 0.09375),
        "zero_4096_does_not_qualify_1e_minus12": zero_error_upper_bound(payload) > 1e-12,
        "no_phase_added_to_source_contract": contract["observed_response"]["phase"] is None,
    }
    assert all(checks.values()), checks
    return {"schema": "microled-device-codesign-illustrative-calculations-v1", "date": "2026-10-29",
            "status": "teaching arithmetic and proposed protocol only; no new transistor or optical pass claim",
            "recomputation_comparison_policy": {"strict": "all structure, types, keys, identities, hashes, integer counts and all other values",
                                                 "explicit_float_paths_rel_tol": FLOAT_REL_TOLERANCE_PATHS,
                                                 "float_abs_tol": 0.0,
                                                 "reason": "Three derived ABC leaves differ by approximately one ULP between Python 3.9.6 and 3.12.13; this is arithmetic rounding, not evidence uncertainty or a physical tolerance."},
            "provenance": {"script": str(Path(__file__).resolve().relative_to(ROOT)),
                           "script_sha256": sha256(Path(__file__)),
                           "frozen_response_contract": str(CONTRACT.relative_to(ROOT)), "frozen_response_contract_sha256": sha256(CONTRACT),
                           "frozen_test_frame_spec": str(SPEC.relative_to(ROOT)), "frozen_test_frame_spec_sha256": sha256(SPEC),
                           "receiver_training_guard_contract": str(RX_CONTRACT.relative_to(ROOT)), "receiver_training_guard_contract_sha256": sha256(RX_CONTRACT),
                           "receiver_v3_source": str(RX_V3.relative_to(ROOT)), "receiver_v3_source_sha256": sha256(RX_V3)},
            "frame": frame_data, "geometry": geometry, "rc": rc, "abc": abc,
            "bandwidth_conventions": conventions, "ber": ber, "energy": energy,
            "logical_checks": checks, "all_logical_checks_pass": all(checks.values())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Recompute and compare the existing JSON without writing")
    args = parser.parse_args()
    result = build()
    if args.check:
        if not OUT.exists():
            raise SystemExit("FAIL: stored calculations are missing")
        differences = comparison_differences(json.loads(OUT.read_text()), result)
        if differences:
            raise SystemExit("FAIL: stored calculations differ from recomputation\n" + "\n".join(differences))
        print(f"PASS: recomputation; {len(result['logical_checks'])} logical checks; strict identities/structure, only 3 declared ABC float leaves rel_tol=1e-12")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(f"Wrote {OUT.relative_to(ROOT)}; {len(result['logical_checks'])} logical checks passed")


if __name__ == "__main__":
    main()
