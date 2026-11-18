"""Compare both limiting zero-bit edges after the isolated W6/L3 feed-forward change."""

import gzip
import json
from pathlib import Path

import numpy as np
from check import FRAME, UI, cascade, digest
from figures import ACCENT, EVIDENCE, INK, WARM, WORK, plt, save


def right(case):
    m = json.loads((case / "manifest.json").read_text())
    r = json.loads((case / "result.json").read_text())
    bit = 2129
    phase = r["frames"][0]["full_receiver"]["delay_bit_UI"]
    sample = FRAME + (bit + phase) * UI
    with gzip.open(case / "waveform.dat.gz", "rt") as stream:
        t, current = np.loadtxt(
            stream, usecols=(0, m["vectors"]["iled_cond"]), skiprows=1, unpack=True
        )
    y = cascade(t, current * 1e6)
    k = np.flatnonzero((t[:-1] >= sample) & (y[:-1] < 62.5) & (y[1:] >= 62.5))[0]
    crossing = t[k] + (62.5 - y[k]) / (y[k + 1] - y[k]) * (t[k + 1] - t[k])
    axis = np.linspace(0.335, 0.4, 150)
    return {
        "case": m["case"]["variant"],
        "result_sha256": digest(case / "result.json"),
        "raw_sha256": r["raw_sha256"],
        "line_bit": bit,
        "previous_frame_phase_UI": phase,
        "next_crossing_UI": (crossing - sample) / UI,
        "relative_UI": axis.tolist(),
        "RX_uAeq": np.interp(sample + axis * UI, t, y).tolist(),
    }


def main():
    geom = WORK.parent / "b_final"
    cases = [
        geom / v / "ss_hot_low-full-s40" for v in ["unit6-r260", "unit6-r260-ff36"]
    ]
    windows = [right(case) for case in cases]
    right_path = EVIDENCE / "ss-w6-rising-crossing.json"
    right_path.write_text(json.dumps(windows, indent=2) + "\n")
    left_paths = [EVIDENCE / f"ss-w6-{v}-rx.json" for v in ["base", "ff36"]]
    left = [json.loads(p.read_text())["sample_3511"] for p in left_paths]
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 3.6), sharey=True)
    for ax in axes:
        ax.axvspan(-0.37, 0.37, color="#d7eae7", alpha=0.6)
        ax.axhline(62.5, color=INK, ls=":", lw=0.9)
        ax.grid(axis="y", alpha=0.14)
        ax.set_xlabel("相对该位冻结采样中心 (UI)")
    axes[0].set(
        xlim=(-0.403, -0.338),
        ylim=(59.8, 65.1),
        title="码位 3511　采样前的下降交点",
        ylabel="接收等效电流 (µAeq)",
    )
    axes[1].set(xlim=(0.339, 0.397), title="码位 2129　采样后的上升交点")
    axes[0].axvline(-0.37, color=INK, ls=":", lw=0.9)
    axes[1].axvline(0.37, color=INK, ls=":", lw=0.9)
    for i, (label, color) in enumerate(
        [("原前馈 31.275 fF", WARM), ("仅将前馈改为 36 fF", ACCENT)]
    ):
        for ax, x, y, point in [
            (
                axes[0],
                left[i]["relative_UI"],
                left[i]["received_uAeq"],
                left[i]["prev_crossing_relative_UI"],
            ),
            (
                axes[1],
                windows[i]["relative_UI"],
                windows[i]["RX_uAeq"],
                windows[i]["next_crossing_UI"],
            ),
        ]:
            ax.plot(x, y, label=label, lw=1.9, color=color)
            ax.plot(point, 62.5, "o", mec=color, mfc="white", ms=6)
    axes[0].legend(fontsize=8, loc="lower left")
    axes[1].text(0.343, 64.55, "绿色区内须无阈值交点", fontsize=9, color=ACCENT)
    fig.tight_layout()
    save(
        fig,
        "br-w6-eye-edges",
        [*left_paths, right_path],
        generator=Path(__file__),
    )


if __name__ == "__main__":
    main()
