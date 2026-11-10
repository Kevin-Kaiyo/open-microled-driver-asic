"""Assess whether one fixed sampling delay can recover both gate signals."""

import argparse
import csv
import json

import matplotlib.pyplot as plt
import numpy as np

from predriver import COUNT, EVIDENCE, REPORT, ROOT, VDD, WARM, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=str, required=True)
    args = parser.parse_args()
    out = ROOT / args.run
    receipt = json.loads((EVIDENCE / "predriver-manifest.json").read_text())
    if args.run != receipt["run"]:
        raise ValueError("run differs from frozen manifest")

    def verified(name):
        path = out / name
        if sha(path) != receipt["raw_files_sha256"][name]:
            raise ValueError(f"Waveform input mismatch: {name}")
        return path

    bits = np.array(list(verified("bits.txt").read_text().strip()), dtype=int)
    # Common valid interval for the entire delay grid, with no wraparound.
    bit_index = np.arange(WARM, WARM + COUNT - 3)
    delay_ui = np.linspace(0, 2, 401)
    rows, plot_data = [], {}
    with (EVIDENCE / "predriver-metrics.csv").open() as file:
        for case in csv.DictReader(file):
            t, _, _, gp, gb, *_ = np.loadtxt(verified(case["case"]+"/waveform.dat"), skiprows=1).T
            ui_s = 1e-9 / float(case["rate_GBd"])
            sample_t = (bit_index[None, :] + delay_ui[:, None]) * ui_s
            vp, vb = np.interp(sample_t, t, gp), np.interp(sample_t, t, gb)
            high = np.where(bits[bit_index], vp, vb)
            low = np.where(bits[bit_index], vb, vp)
            margin = np.minimum(high - .8*VDD, .2*VDD - low).min(axis=1)
            best = int(margin.argmax())
            good = np.flatnonzero(margin >= 0)
            runs = np.split(good, np.flatnonzero(np.diff(good) > 1) + 1)
            longest = max((len(run) for run in runs), default=0)
            rows.append({
                "case": case["case"], "compared_bits": len(bit_index),
                "grid_spacing_UI": float(delay_ui[1]), "best_sample_delay_UI": delay_ui[best],
                "best_min_voltage_margin_V": margin[best], "passing_grid_points": len(good),
                "longest_passing_grid_span_UI": max(0, longest-1)*float(delay_ui[1]),
            })
            if (case["rate_GBd"], case["corner"], case["maxstep_ps"]) == ("3.7", "typical", "2"):
                plot_data[(case["shape"], case["cap_each_fF"])] = margin

    with (EVIDENCE / "predriver-phase.csv").open("w") as file:
        writer = csv.DictWriter(file, rows[0])
        writer.writeheader()
        writer.writerows(rows)
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True, layout="constrained")
    for ax, cap in zip(axs, ["10", "50"]):
        ax.axhline(0, color="#6f7987", ls="--", lw=1)
        ax.axvline(.5, color="#6f7987", ls=":", lw=1)
        for shape, color in [("tapped", "#006e6a"), ("balanced", "#aa5b1f")]:
            ax.plot(delay_ui, plot_data[(shape, cap)], label=shape, color=color)
        ax.set(title=f"3.7 GBd, {cap} fF / gate", xlabel="Sample delay from input bit boundary (UI)")
        ax.grid(alpha=.16)
        ax.legend(frameon=False, loc="lower right")
    axs[0].set_ylabel("Worst 20/80% rail margin (V)")
    fig.savefig(REPORT / "predriver-phase.png", dpi=160)


if __name__ == "__main__":
    main()
