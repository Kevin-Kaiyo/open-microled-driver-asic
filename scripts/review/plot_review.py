"""Render audit figures directly from compact JSON (matplotlib + numpy).

Run with the physical-flow Python environment. Figures are electrical model
results, not measured MicroLED characteristics or qualification envelopes.
"""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence/review"
plt.rcParams.update({"font.family": ["Avenir Next", "DejaVu Sans"], "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.labelcolor": "#203c4c", "text.color": "#203c4c",
                     "axes.titleweight": "bold", "axes.titlesize": 13,
                     "savefig.facecolor": "white"})
TEAL, NAVY, GRAY = "#227e89", "#26495d", "#b6c5ca"


def save(fig, name):
    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / name, dpi=200)
    plt.close(fig)


def main():
    sources = ["numeric-gmin-probes.json", "mos-audit.json", "sensitivity-summary.json"]
    gmin, mos, sweep = [json.loads((OUT / name).read_text()) for name in sources]
    fig, ax = plt.subplots(figsize=(8.2, 3.35))
    gmin = sorted(gmin, key=lambda x: x["gmin_s"])
    ax.loglog([x["gmin_s"] for x in gmin], [x["average_current_pA"] for x in gmin],
              "o-", color=TEAL, linewidth=2)
    for x in gmin:
        ax.annotate(f"{x['average_current_pA']:.4g} pA", (x["gmin_s"], x["average_current_pA"]),
                    xytext=(0, 10), textcoords="offset points", ha="center", fontsize=10)
    ax.set(xlabel="Solver GMIN (S)", ylabel="Average off current (pA)", ylim=(.009, 1500),
           xlim=(3e-17, 3e-10), title="Off current depends on the numerical conductance")
    ax.grid(which="major", alpha=.17)
    save(fig, "gmin-sensitivity.png")

    rows = mos["driver_compliance"]
    fig, ax = plt.subplots(figsize=(8.2, 3.25))
    ax.plot([r["fixed_cathode_v"] for r in rows], [r["values"]["current_a"]*1e6 for r in rows],
            "o-", color=TEAL, linewidth=2)
    ax.axhline(100, color=NAVY, linestyle="--", linewidth=1, label="Ideal IREF = 100 µA")
    ax.set(xlabel="Externally forced LED cathode voltage (V)", ylabel="DC output current (µA)",
           title="Voltage headroom must be tied to an accuracy target", ylim=(0, 110))
    ax.grid(alpha=.17)
    ax.legend(frameon=False, loc="lower right", fontsize=10)
    save(fig, "compliance.png")

    rows = sweep["results"]
    corners = ["typical", "ff", "ss", "fs", "sf"]
    volts = [2.97, 3.3, 3.63]
    matrix = np.array([[min(r["duty_linearity_error_pct"] for r in rows
                           if r["group"] == "matrix" and r["duty"] == 1
                           and r["corner"] == corner and r["vlogic_v"] == v)
                        for v in volts] for corner in corners])
    fig, ax = plt.subplots(figsize=(8.2, 3.5))
    p = ax.imshow(matrix, cmap="Blues_r", vmin=-.55, vmax=0, aspect="auto")
    ax.set_xticks(range(3), [f"{v:.2f} V" for v in volts])
    ax.set_yticks(range(5), [c.upper() for c in corners])
    ax.set(xlabel="Logic supply", title="Duty 1/256: most negative error over 0 / 27 / 85 °C")
    for i in range(5):
        for j in range(3):
            ax.text(j, i, f"{matrix[i,j]:.3f}%", ha="center", va="center",
                    color="white" if matrix[i,j] < -.34 else NAVY)
    fig.colorbar(p, ax=ax, label="Error (%)")
    save(fig, "low-duty-matrix.png")

    selected = [next(r for r in rows if r["group"] == "gmin" and r["gmin"] == 1e-12)]
    selected += [next(r for r in rows if r["group"] == "matrix" and r["corner"] == "typical"
                     and r["temperature_c"] == 27 and r["vlogic_v"] == 3.3 and r["duty"] == d)
                 for d in (1, 64, 256)]
    logic = np.array([r["logic_rail_power_uW"] for r in selected])
    led = np.array([r["led_rail_power_uW"] for r in selected])
    fig, ax = plt.subplots(figsize=(8.2, 3.3))
    x = np.arange(4)
    ax.bar(x, logic, color=GRAY, width=.55, label="3.3 V logic rail (includes ideal IREF)")
    ax.bar(x, led, bottom=logic, color=TEAL, width=.55, label="5 V LED rail")
    for i, value in enumerate(logic+led):
        ax.text(i, value+12, f"{value:.2f}", ha="center", fontsize=10)
    ax.set_xticks(x, ["0/256", "1/256", "64/256", "256/256"])
    ax.set(xlabel="PWM duty", ylabel="Electrical rail power (µW)", ylim=(0, 1050),
           title="The ideal reference branch stays on when the LED is off")
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.grid(axis="y", alpha=.15)
    save(fig, "rail-power.png")
    manifest = {str((OUT / n).relative_to(ROOT)): hashlib.sha256((OUT / n).read_bytes()).hexdigest()
                for n in sources}
    manifest["scripts/review/plot_review.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (OUT / "figure-inputs.json").write_text(json.dumps(manifest, indent=2)+"\n")


if __name__ == "__main__":
    main()
