"""Draw the SS late falling crossing against the unchanged per-side timing criterion."""

import json
from pathlib import Path

from figures import ACCENT, EVIDENCE, GREY, INK, WARM, plt, save

paths = [EVIDENCE / "ss-reference-rx.json", EVIDENCE / "ss-intermediate-rx.json"]
labels = ["原 44 MOS 保护版本", "W4/L2 单位镜 + 10 fF 输入电容"]
colors = [GREY, WARM]
if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument(
        "--w6",
        action="store_true",
        help="Plot the single CFF change on the W6/L3 circuit.",
    )
    p.add_argument("--repaired", type=Path)
    p.add_argument("--label", default="后续修改")
    args = p.parse_args()
    name = "br-ss-falling-crossing"
    if args.w6:
        paths = [EVIDENCE / "ss-w6-base-rx.json", EVIDENCE / "ss-w6-ff36-rx.json"]
        labels = ["W6/L3 原前馈电容 31.275 fF", "同电路前馈电容 36 fF"]
        colors = [WARM, ACCENT]
        name = "br-w6-falling-crossing"
    if args.repaired:
        paths.append(args.repaired)
        labels.append(args.label)
        colors.append(ACCENT)
    fig, (ax, zoom) = plt.subplots(
        1, 2, figsize=(9.8, 3.5), gridspec_kw={"width_ratios": [1.55, 1]}
    )
    for axis in [ax, zoom]:
        axis.axvspan(-0.37, 0.37, color="#d7eae7", alpha=0.6)
        axis.axhline(62.5, color=INK, lw=0.8, ls=":")
        axis.axvline(-0.37, color=INK, lw=1, ls=":")
        axis.grid(axis="y", alpha=0.17)
        axis.set_xlabel("相对采样时刻 (UI)")
    for path, label, color in zip(paths, labels, colors):
        case = json.loads(path.read_text())
        window = case["sample_3511"]
        for axis in [ax, zoom]:
            axis.plot(
                window["relative_UI"],
                window["received_uAeq"],
                color=color,
                lw=1.8,
                label=label,
            )
            axis.plot(
                window["prev_crossing_relative_UI"],
                62.5,
                marker="o",
                mfc="white",
                mec=color,
                ms=5,
            )
    ax.set(xlim=(-0.85, 0.30), ylim=(26, 94), ylabel="接收端等效电流 (µAeq)")
    zoom.set(xlim=(-0.435, -0.34), ylim=(59.8, 64.5), title="62.5 µAeq 交点放大")
    ax.axvline(0, color=ACCENT, lw=0.8, ls="--")
    ax.set_title("SS 恢复帧，第 3511 个线码位（从 0 计数）")
    ax.text(-0.34, 88, "绿色区内须无阈值交点", color=ACCENT, fontsize=9)
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    save(
        fig,
        name,
        paths
        + [
            Path(__file__).with_name("figures.py"),
            Path(__file__).with_name("ss_timing.py"),
        ],
        generator=Path(__file__),
    )
