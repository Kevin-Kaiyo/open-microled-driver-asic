#!/usr/bin/env python3
"""Deterministic receiver and energy metrics for the NRZ teaching experiment.

The optical/Rx filters are assumed linear proxies, not measured LED/TIA models.
No output of this module is a measured, extrapolated, or noise-derived BER.
Run ``uv run python scripts/highspeed_nrz/metrics.py`` for analytical controls.
"""
from __future__ import annotations

import json
import math
from typing import Any

import numpy as np

I0_A = 25e-6
I1_A = 100e-6
THRESHOLD_A = (I0_A + I1_A) / 2
SPAN_A = I1_A - I0_A


def _trace(time_s, values) -> tuple[np.ndarray, np.ndarray]:
    t, x = np.asarray(time_s, dtype=float), np.asarray(values, dtype=float)
    if t.ndim != 1 or x.shape != t.shape or len(t) < 2:
        raise ValueError("time and signal must be equal-length 1-D arrays (at least two points)")
    if not np.all(np.isfinite(t)) or not np.all(np.isfinite(x)):
        raise ValueError("non-finite trace samples")
    if not np.all(np.diff(t) > 0):
        raise ValueError("time must be strictly increasing; explicitly de-duplicate simulator output first")
    return t, x


def _bits(bits) -> np.ndarray:
    raw = np.asarray(bits)
    if raw.ndim != 1 or len(raw) < 2 or not np.all((raw == 0) | (raw == 1)):
        raise ValueError("bits must be a 1-D binary array")
    b = raw.astype(int)
    if not np.any(b == 0) or not np.any(b == 1):
        raise ValueError("both bit classes are needed for an eye measurement")
    return b


def first_order_lowpass(time_s, values, tau_s: float, initial: float | None = None) -> np.ndarray:
    """Exact one-pole solution for the piecewise-linear sampled input.

    Solves tau*dy/dt + y = x at native (possibly irregular) sample times.
    This avoids imposing an extra arbitrary uniform filter sampling interval.
    Input interpolation between solver points is still an approximation to the
    continuous transistor solution; timestep convergence remains necessary.
    """
    t, x = _trace(time_s, values)
    if tau_s <= 0 or not math.isfinite(tau_s):
        raise ValueError("tau_s must be finite and positive")
    h = np.diff(t) / tau_s
    a = np.exp(-h)
    one_minus_a = -np.expm1(-h)
    beta = 1 - one_minus_a / h
    tiny = h < 1e-4
    z = h[tiny]
    beta[tiny] = z / 2 - z*z / 6 + z**3 / 24 - z**4 / 120
    y = np.empty_like(x)
    y[0] = x[0] if initial is None else float(initial)
    for k in range(1, len(t)):
        y[k] = a[k-1]*y[k-1] + one_minus_a[k-1]*x[k-1] + beta[k-1]*(x[k]-x[k-1])
    return y


def receiver_proxy(time_s, i_led_A, tau_opt_s: float = 200e-12,
                   rx_bw_hz: float = 1e9, initial_A: float | None = None) -> dict[str, Any]:
    """Filter conductive LED current, excluding capacitor displacement current.

    Returns numpy arrays for plotting plus JSON-safe model metadata.  The second
    cascade stage sees a PWL approximation of the first-stage sampled output.
    """
    t, current = _trace(time_s, i_led_A)
    if rx_bw_hz <= 0 or not math.isfinite(rx_bw_hz):
        raise ValueError("rx_bw_hz must be finite and positive")
    optical = first_order_lowpass(t, current, tau_opt_s, initial_A)
    rx_tau = 1 / (2 * math.pi * rx_bw_hz)
    rx = first_order_lowpass(t, optical, rx_tau, optical[0])
    return {"optical_proxy_A": optical, "receiver_proxy_A": rx,
            "model": {"optical_tau_s": tau_opt_s, "receiver_bw_hz": rx_bw_hz,
                      "receiver_tau_s": rx_tau, "linear_dc_gain": 1,
                      "threshold_A": THRESHOLD_A, "nominal_span_A": SPAN_A,
                      "noise": "omitted", "evidence": "assumed linear current-equivalent proxy"}}


def _sample(t, x, sample_times):
    if np.min(sample_times) < t[0] or np.max(sample_times) > t[-1]:
        raise ValueError("sampling window exceeds trace; add a warmup/trailing guard, never extrapolate")
    return np.interp(sample_times, t, x)


def _decision(samples, bits, threshold_A=THRESHOLD_A, span_A=SPAN_A) -> dict[str, Any]:
    one, zero = samples[bits == 1], samples[bits == 0]
    minimum_one, maximum_zero = float(np.min(one)), float(np.max(zero))
    errors = int(np.count_nonzero((samples >= threshold_A) != bits))
    eye = minimum_one - maximum_zero
    margin = min(minimum_one - threshold_A, threshold_A - maximum_zero)
    return {"sample_count": int(len(bits)), "deterministic_errors": errors,
            "error_fraction_on_this_finite_pattern": errors / len(bits),
            "min_one_A": minimum_one, "max_zero_A": maximum_zero,
            "mean_one_A": float(np.mean(one)), "mean_zero_A": float(np.mean(zero)),
            "eye_opening_A": eye, "eye_opening_normalized": eye / span_A,
            "threshold_margin_A": margin, "threshold_margin_normalized": margin / span_A,
            "threshold_A": threshold_A, "nominal_span_A": span_A,
            "scope": "deterministic finite-pattern samples; not physical BER"}


def train_sampler(time_s, receiver_A, bits, bit_start_s: float, ui_s: float,
                  max_delay_ui: float = 4.0, phase_steps_per_ui: int = 128,
                  threshold_A: float = THRESHOLD_A, span_A: float = SPAN_A) -> dict[str, Any]:
    """Choose a delay only from the separate training pattern.

    Delays span 0..max_delay_ui UI, inclusive, with 1/128-UI resolution by
    default. Minimize training errors, then maximize the WORST fixed-threshold
    margin. A near-flat best plateau is centered (tolerance 1e-6 of nominal
    span) to avoid arbitrary earliest/last-point tie-breaking. No threshold,
    equalizer, amplitude, optical gain, or validation data is fitted here.
    """
    t, x = _trace(time_s, receiver_A)
    b = _bits(bits)
    if ui_s <= 0 or max_delay_ui < 1 or phase_steps_per_ui < 16 or span_A <= 0:
        raise ValueError("invalid sampling contract")
    offsets = np.arange(int(round(max_delay_ui*phase_steps_per_ui)) + 1) / phase_steps_per_ui
    starts = bit_start_s + np.arange(len(b)) * ui_s
    results = [_decision(_sample(t, x, starts + d*ui_s), b, threshold_A, span_A) for d in offsets]
    errors = np.asarray([r["deterministic_errors"] for r in results])
    margins = np.asarray([r["threshold_margin_A"] for r in results])
    best_errors = int(np.min(errors))
    eligible = errors == best_errors
    best_margin = float(np.max(margins[eligible]))
    candidates = np.flatnonzero(eligible & (margins >= best_margin - span_A*1e-6))
    # Use the longest contiguous near-optimal plateau, then its center.
    groups = np.split(candidates, np.flatnonzero(np.diff(candidates) != 1) + 1)
    plateau = max(groups, key=lambda a: len(a))
    k = int(plateau[(len(plateau)-1)//2])
    delay_ui = float(offsets[k])
    return {"sample_delay_s": delay_ui*ui_s, "sample_delay_ui": delay_ui,
            "integer_delay_ui": int(math.floor(delay_ui)), "phase_ui": delay_ui % 1,
            "ui_s": ui_s, "rate_bps": 1/ui_s, "threshold_A": threshold_A,
            "nominal_span_A": span_A, "training_bit_start_s": bit_start_s,
            "search_max_delay_ui": max_delay_ui, "phase_steps_per_ui": phase_steps_per_ui,
            "training": results[k], "selection": "training only: minimum errors, then maximum worst fixed-threshold margin",
            "requires_retraining_at_each_rate": True, "frozen_for_validation": True}


def evaluate_validation(time_s, receiver_A, bits, bit_start_s: float, ui_s: float,
                        sampler: dict[str, Any], timing_steps: int = 129) -> dict[str, Any]:
    """Evaluate independent bits at the frozen trained delay and threshold.

    A +/-0.5-UI diagnostic sweep reports the contiguous zero-error timing region
    *containing the fixed sample point*. It never reselects the sample point.
    Bounds reaching the sweep edge are lower bounds, not measured eye edges.
    """
    t, x = _trace(time_s, receiver_A)
    b = _bits(bits)
    if not math.isclose(ui_s, sampler["ui_s"], rel_tol=1e-12):
        raise ValueError("training/validation UI mismatch")
    if timing_steps < 17 or timing_steps % 2 != 1:
        raise ValueError("timing_steps must be odd and >=17")
    threshold = float(sampler["threshold_A"])
    span = float(sampler["nominal_span_A"])
    centers = bit_start_s + np.arange(len(b))*ui_s + sampler["sample_delay_s"]
    fixed = _decision(_sample(t, x, centers), b, threshold, span)
    delta_ui = np.linspace(-.5, .5, timing_steps)
    sweep = [_decision(_sample(t, x, centers + d*ui_s), b, threshold, span) for d in delta_ui]
    safe = np.array([m["deterministic_errors"] == 0 and m["threshold_margin_A"] > 0 for m in sweep])
    mid = timing_steps//2
    left = right = mid
    if safe[mid]:
        while left > 0 and safe[left-1]:
            left -= 1
        while right < timing_steps-1 and safe[right+1]:
            right += 1
    fixed.update({"validation_bit_start_s": bit_start_s, "sample_delay_s": sampler["sample_delay_s"],
                  "sample_delay_ui": sampler["sample_delay_ui"],
                  "timing_left_ui": float(-delta_ui[left]) if safe[mid] else 0,
                  "timing_right_ui": float(delta_ui[right]) if safe[mid] else 0,
                  "timing_window_ui": float(delta_ui[right]-delta_ui[left]) if safe[mid] else 0,
                  "timing_min_margin_ui": float(min(-delta_ui[left], delta_ui[right])) if safe[mid] else 0,
                  "timing_left_is_lower_bound": bool(safe[mid] and left == 0),
                  "timing_right_is_lower_bound": bool(safe[mid] and right == timing_steps-1),
                  "timing_sweep_step_ui": 1/(timing_steps-1),
                  "sampling_reoptimized_on_validation": False,
                  "passes_deterministic_sample_gate": bool(fixed["deterministic_errors"] == 0 and fixed["threshold_margin_A"] > 0),
                  "phase_sweep": {"delta_ui": delta_ui.tolist(),
                                  "errors": [r["deterministic_errors"] for r in sweep],
                                  "threshold_margin_normalized": [r["threshold_margin_normalized"] for r in sweep]}})
    return fixed


def eye_segments(time_s, receiver_A, bits, bit_start_s: float, ui_s: float,
                 sampler: dict[str, Any], max_segments: int = 96, points: int = 129) -> dict[str, Any]:
    """Uniform phase-grid interpolation for DISPLAY, never additional evidence."""
    t, x = _trace(time_s, receiver_A)
    b = _bits(bits)
    ids = np.linspace(0, len(b)-1, min(max_segments, len(b)), dtype=int)
    phase = np.linspace(-.5, .5, points)
    centers = bit_start_s + ids*ui_s + sampler["sample_delay_s"]
    waves = [_sample(t, x, c + phase*ui_s).tolist() for c in centers]
    return {"phase_from_frozen_sample_ui": phase.tolist(), "signal_A": waves,
            "bits": b[ids].tolist(), "bit_indices": ids.tolist(),
            "note": "uniform display grid from linear interpolation; no new bandwidth or samples claimed"}


def clipped_window(time_s, values, start_s: float, end_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Clip to exact requested endpoints without extrapolation."""
    t, x = _trace(time_s, values)
    if not (t[0] <= start_s < end_s <= t[-1]):
        raise ValueError("integration bounds must lie inside the trace")
    inside = (t > start_s) & (t < end_s)
    tc = np.r_[start_s, t[inside], end_s]
    xc = np.r_[np.interp(start_s, t, x), x[inside], np.interp(end_s, t, x)]
    return tc, xc


def integrate_window(time_s, values, start_s: float, end_s: float) -> float:
    t, x = clipped_window(time_s, values, start_s, end_s)
    return float(np.trapezoid(x, t))


def energy_window(time_s, voltage_V, source_current_A, start_s: float, end_s: float,
                  n_bits: int, spice_voltage_source_sign: bool = True) -> dict[str, Any]:
    """Source-terminal energy; separate draw/return rather than assuming recovery.

    SPICE current is into a voltage source's positive terminal: delivered power
    is -V*I. Set spice_voltage_source_sign=False only when current is already
    positive outward. Voltage is differential across that source, not merely
    a node-to-ground potential. Zero crossings are added to the PWL power
    integration so positive/negative areas are not biased by clipping first.
    """
    t, v = _trace(time_s, voltage_V)
    _, i = _trace(time_s, source_current_A)
    if n_bits <= 0:
        raise ValueError("n_bits must be positive")
    delivered = (-1 if spice_voltage_source_sign else 1)*v*i
    tc, p = clipped_window(t, delivered, start_s, end_s)
    crossings = np.flatnonzero(p[:-1]*p[1:] < 0)
    if len(crossings):
        tz = tc[crossings] - p[crossings]*(tc[crossings+1]-tc[crossings])/(p[crossings+1]-p[crossings])
        old_t, old_p = tc, p
        tc = np.sort(np.r_[tc, tz])
        p = np.interp(tc, old_t, old_p)
        for z in tz:
            p[np.flatnonzero(tc == z)] = 0.
    net = float(np.trapezoid(p, tc))
    draw = float(np.trapezoid(np.maximum(p, 0), tc))
    returned = float(np.trapezoid(np.maximum(-p, 0), tc))
    if not math.isclose(net, draw-returned, rel_tol=1e-10, abs_tol=1e-24):
        raise AssertionError("source energy conservation arithmetic failed")
    duration = end_s-start_s
    return {"start_s": start_s, "end_s": end_s, "duration_s": duration,
            "n_gross_bits": int(n_bits), "net_J": net, "positive_draw_J": draw,
            "returned_J": returned, "net_mean_W": net/duration,
            "positive_draw_mean_W": draw/duration, "returned_mean_W": returned/duration,
            "net_J_per_gross_bit": net/n_bits, "positive_draw_J_per_gross_bit": draw/n_bits,
            "returned_J_per_gross_bit": returned/n_bits,
            "boundary": "this source's electrical terminals only; upstream regulator/recovery loss excluded"}


def self_checks() -> dict[str, Any]:
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    t = np.array([0, .03, .11, .33, .5, 1, 2, 4.])
    tau = .7
    ramp = first_order_lowpass(t, t, tau, 0)
    exact_ramp = t-tau+tau*np.exp(-t/tau)
    check("irregular-time ramp exact one-pole response", np.allclose(ramp, exact_ramp, rtol=1e-12, atol=1e-14))
    decay = first_order_lowpass(t, np.zeros_like(t), tau, 3.)
    check("irregular-time homogeneous exponential exact", np.allclose(decay, 3*np.exp(-t/tau), rtol=1e-12))
    dc = first_order_lowpass(t, np.full_like(t, 4.), tau)
    check("DC gain and initialized steady state", np.allclose(dc, 4, atol=1e-14))
    check("clipped irregular ramp integral", math.isclose(integrate_window(t, t, .13, 1.8), (1.8**2-.13**2)/2, rel_tol=1e-12))
    e = energy_window([0., 2.], [1., 1.], [1., -1.], .5, 1.5, 2)
    check("power sign + clipped zero crossing", math.isclose(e["net_J"], 0, abs_tol=1e-15) and math.isclose(e["positive_draw_J"], .125) and math.isclose(e["returned_J"], .125))
    check("energy per bit and draw-return identity", math.isclose(e["positive_draw_J_per_gross_bit"], .0625) and math.isclose(e["net_J"], e["positive_draw_J"]-e["returned_J"]))
    # Independent pseudo-random vectors, exact delayed ideal NRZ positive control.
    rng = np.random.default_rng(119)
    train, valid = rng.integers(0, 2, 254), rng.integers(0, 2, 511)
    prefix, suffix = np.tile([0, 1], 16), np.tile([1, 0], 16)
    bits = np.r_[prefix, train, valid, suffix]
    ui, delay = 1e-9, .29e-9
    ts = np.arange(0, len(bits)*ui, ui/256)
    index = np.clip(np.floor((ts-delay)/ui).astype(int), 0, len(bits)-1)
    signal = I0_A + bits[index]*SPAN_A
    sampler = train_sampler(ts, signal, train, 32*ui, ui)
    outcome = evaluate_validation(ts, signal, valid, (32+254)*ui, ui, sampler)
    check("independent delayed ideal NRZ zero-error control", outcome["deterministic_errors"] == 0)
    check("ideal amplitude eye opening", math.isclose(outcome["eye_opening_normalized"], 1, rel_tol=1e-10))
    check("known latency retained, not validation retuned", abs(sampler["sample_delay_ui"]-.79) < .02 and not outcome["sampling_reoptimized_on_validation"])
    check("ideal horizontal eye around frozen phase", outcome["timing_window_ui"] > .95)
    inverted = evaluate_validation(ts, 2*THRESHOLD_A-signal, valid, (32+254)*ui, ui, sampler)
    check("inverted-data negative control fails", inverted["deterministic_errors"] == len(valid) and not inverted["passes_deterministic_sample_gate"])
    for name, fn in [
        ("extrapolation rejected", lambda: integrate_window(t, t, -.1, 1)),
        ("duplicate time rejected", lambda: first_order_lowpass([0, 0, 1], [0, 0, 1], 1)),
        ("single bit-class eye rejected", lambda: train_sampler(ts, signal, [0, 0], 32*ui, ui)),
        ("fractional pseudo-bits rejected", lambda: train_sampler(ts, signal, [0, .5, 1], 32*ui, ui)),
    ]:
        try:
            fn()
        except ValueError:
            checks.append(name)
        else:
            raise AssertionError(name)
    return {"status": "passed", "count": len(checks), "checks": checks,
            "scope": "analytical code controls, not electrical/optical circuit validation"}


if __name__ == "__main__":
    print(json.dumps(self_checks(), ensure_ascii=False, indent=2))
