#!/usr/bin/env python3
"""Exact two-pole concept calculation; no fitted LED, transistor, noise or BER model."""
import csv
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/research/product-framework-20261014"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)
RAW = ROOT / "build/product-framework-20261014/highspeed"
RAW.mkdir(parents=True, exist_ok=True)


def prbs9():
    state = [1] * 9
    initial = state.copy()
    bits = []
    for _ in range(511):
        bits.append(state[0])
        state = state[1:] + [state[0] ^ state[4]]
    assert state == initial and sum(bits) == 256
    return bits


def advance(a, x, y, dt, t1, t2):
    """Exact response to constant input a over dt, two cascaded first-order poles."""
    e1, e2 = math.exp(-dt / t1), math.exp(-dt / t2)
    yy = a + (y - a) * e2 + (x - a) * t1 / (t1 - t2) * (e1 - e2)
    xx = a + (x - a) * e1
    return xx, yy


def cutoff(t1, t2):
    # Let z=w^2; (1+z*t1^2)(1+z*t2^2)=2. Stable positive root.
    a, b = t1 * t1 * t2 * t2, t1 * t1 + t2 * t2
    z = 2 / (b + math.sqrt(b * b + 4 * a))
    return math.sqrt(z) / (2 * math.pi)


def scenario(label, rate, c, carrier):
    r, n = 100.0, 100
    t1, t2, ui = r * c, carrier, 1 / rate
    x = y = 0.0
    bits = prbs9()
    states, centers, trace = [], [], []
    for cycle in range(2):
        for bit_i, a in enumerate(bits):
            if cycle == 1:
                states.append((x, y))
                centers.append((a, advance(a, x, y, ui / 2, t1, t2)[1]))
                for j in range(n):
                    xx, yy = advance(a, x, y, j * ui / n, t1, t2)
                    trace.append([label, bit_i, j / n, (bit_i + j / n) * ui, a, xx, yy])
            x, y = advance(a, x, y, ui, t1, t2)
    lo = max(y for a, y in centers if a == 0)
    hi = min(y for a, y in centers if a == 1)
    # Independent substepping check at the decision sample.
    max_delta = 0.0
    for a, (xx, yy), (_, center) in zip(bits, states, centers):
        for _ in range(n // 2):
            xx, yy = advance(a, xx, yy, ui / n, t1, t2)
        max_delta = max(max_delta, abs(center - yy))
    assert max_delta < 2e-13
    rec = dict(label=label, bit_rate_bps=rate, ui_s=ui, effective_resistance_ohm=r,
               total_capacitance_F=c, electrical_tau_s=t1, carrier_tau_s=t2,
               f3dB_Hz=cutoff(t1, t2), sample_phase_UI=0.5,
               minimum_one_at_sample=hi, maximum_zero_at_sample=lo,
               signed_eye_opening_at_fixed_sample=hi - lo,
               repeated_substep_max_difference=max_delta)
    return rec, trace


cases = [
    ("A: 100 Mb/s, C=2 pF, tau=1 ns", 100e6, 2e-12, 1e-9),
    ("B: 1 Gb/s, C=2 pF, tau=1 ns", 1e9, 2e-12, 1e-9),
    ("C: 1 Gb/s, C=0.2 pF, tau=1 ns", 1e9, .2e-12, 1e-9),
    ("D: 1 Gb/s, C=2 pF, tau=0.1 ns", 1e9, 2e-12, .1e-9),
]
records, traces = [], []
for args in cases:
    rec, trace = scenario(*args)
    records.append(rec)
    traces.append(trace)

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "svg.fonttype": "none"})
fig, axes = plt.subplots(2, 2, figsize=(10.7, 6.7), sharex=True, sharey=True)
for ax, rec, trace in zip(axes.flat, records, traces):
    # 511-bit deterministic pattern, no noise/jitter, 2 UI display windows.
    for k in range(0, 510, 2):
        rows = trace[k * 100:(k + 2) * 100]
        ax.plot([r[1] - k + r[2] for r in rows], [r[6] for r in rows],
                color="#207c8a", linewidth=.5, alpha=.11)
    ax.axvline(.5, color="#b87333", linewidth=.8, linestyle="--")
    ax.set_title(rec["label"], loc="left", fontsize=11)
    ax.text(.04, .05, f"fixed-sample opening = {rec['signed_eye_opening_at_fixed_sample']:.3f}",
            transform=ax.transAxes, fontsize=9, bbox=dict(facecolor="white", alpha=.8, edgecolor="none"))
    ax.set_xlim(0, 2); ax.set_ylim(-.03, 1.03); ax.grid(alpha=.15)
for ax in axes[-1]: ax.set_xlabel("Time / UI (UI = one bit duration)")
for ax in axes[:, 0]: ax.set_ylabel("Normalized optical-response proxy")
fig.suptitle("Two-pole concept only: ideal OOK, no noise, no clock recovery, no measured LED", fontsize=12)
fig.tight_layout(rect=(0, 0, 1, .96))
for ext in ("svg", "png"):
    fig.savefig(FIG / f"highspeed-eye.{ext}", dpi=180)
plt.close(fig)

fig, ax = plt.subplots(figsize=(10.7, 3.7))
freq = [10 ** (6 + 4 * k / 400) for k in range(401)]
for rec, color in zip([records[1], records[2], records[3]], ["#17475d", "#b87333", "#207c8a"]):
    t1, t2 = rec["electrical_tau_s"], rec["carrier_tau_s"]
    db = [-10 * math.log10((1 + (2 * math.pi * f * t1) ** 2) * (1 + (2 * math.pi * f * t2) ** 2)) for f in freq]
    ax.semilogx(freq, db, label=rec["label"].split(": ", 1)[1] + f"; f3dB={rec['f3dB_Hz']/1e6:.1f} MHz", color=color)
ax.axhline(-3.0103, color="#666666", linestyle="--", linewidth=.7)
ax.set(xlabel="Frequency (Hz)", ylabel="Normalized response (dB)", ylim=(-40, 1), xlim=(1e6, 1e10))
ax.legend(fontsize=9, loc="lower left"); ax.grid(alpha=.2)
ax.set_title("Reducing parasitic C has limited benefit when carrier response is dominant", loc="left")
fig.tight_layout()
for ext in ("svg", "png"):
    fig.savefig(FIG / f"highspeed-bandwidth.{ext}", dpi=180)
plt.close(fig)

with (RAW / "highspeed-waveforms.csv").open("w") as f:
    w = csv.writer(f)
    w.writerow(["scenario", "bit_index", "within_bit_UI", "time_s", "input_bit", "electrical_proxy", "optical_proxy"])
    for trace in traces:
        w.writerows(trace)

with (OUT / "highspeed-samples.csv").open("w") as f:
    w = csv.writer(f)
    w.writerow(["scenario", "bit_index", "sample_phase_UI", "time_s", "input_bit", "electrical_proxy", "optical_proxy"])
    for trace in traces:
        w.writerows(trace[50::100])

out = dict(schema_version=1, evidence_class="independent_synthetic_two_pole_calculation",
           generated_from_script="scripts/research/product_framework_highspeed.py",
           script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           transfer_function="H(s)=1/[(1+s*R_eff*C_total)*(1+s*tau_carrier)]",
           solver="Exact piecewise-constant analytic state transition, compared with 50 substeps to 0.5 UI",
           stimulus="PRBS9, b[n+9]=b[n+4] xor b[n], all-ones seed, period 511; second full period evaluated",
           sampling="Fixed 0.5 UI from original bit boundary; no CDR or latency/phase optimization",
           raw_waveforms="build/product-framework-20261014/highspeed/highspeed-waveforms.csv",
           compact_samples="docs/research/product-framework-20261014/highspeed-samples.csv",
           assumptions=["R_eff=100 ohm assumed illustrative Thevenin resistance, not GF180 output resistance",
                        "C_total and tau_carrier chosen for sensitivity, not fitted measurements",
                        "Normalized linear response about an unspecified bias; no absolute current or optical watt conversion",
                        "The full 0-to-1 swing is teaching normalization; large-signal LED nonlinearity excluded",
                        "No MOS switching, LED IV, receiver, additive noise, jitter, package resonances, equalization or BER model"],
           metric="signed eye opening = minimum 1 sample minus maximum 0 sample at 0.5 UI; negative means overlap at that phase",
           does_not_establish=["GF180 transistor performance", "measured optical bandwidth", "a bit rate limit", "BER", "foundry readiness"],
           scenarios=records)
(OUT / "highspeed-calculations.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(records, indent=2))
