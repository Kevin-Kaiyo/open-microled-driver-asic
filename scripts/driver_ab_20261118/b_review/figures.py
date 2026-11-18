"""Draw native-node evidence and a netlist-checked local B schematic."""

import argparse
import hashlib
import html
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/microled-br-mpl")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "build/driver-ab-20261118/b"
OUT = ROOT / "docs/research/driver-ab-20261118/assets"
EVIDENCE = ROOT / "evidence/driver-ab-20261118/b_review"
INK, ACCENT, GREY, WARM = "#233d50", "#087a78", "#576a77", "#98643a"
plt.rcParams.update(
    {
        "font.family": ["PingFang SC", "DejaVu Sans"],
        "font.size": 12,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.labelcolor": INK,
        "text.color": INK,
        "svg.fonttype": "none",
        "axes.unicode_minus": False,
        "axes.titlelocation": "left",
    }
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provenance(name, paths, generator=Path(__file__)):
    payload = {
        "generator": str(generator.resolve().relative_to(ROOT)),
        "generator_sha256": sha(generator),
        "source": {str(p.relative_to(ROOT)): sha(p) for p in paths},
    }
    (EVIDENCE / (name + ".sources.json")).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )


def save(fig, name, paths, generator=Path(__file__)):
    fig.savefig(OUT / (name + ".svg"), bbox_inches="tight", pad_inches=0.12)
    fig.savefig(OUT / (name + ".png"), bbox_inches="tight", pad_inches=0.12, dpi=150)
    plt.close(fig)
    provenance(name, paths, generator)


def n(v, g, mode, step=40):
    return WORK / v / (g + "-" + mode + "-s" + str(step))


def wave(variant):
    fig, axes = plt.subplots(
        2, 1, figsize=(9.8, 5.7), sharex=True, gridspec_kw={"hspace": 0.12}
    )
    refs = []
    rows = []
    for v, label, color in [
        ("original", "原保护电路（100 kΩ）", WARM),
        ("reconnect220", "仅改变栅电阻（220 kΩ）", GREY),
        (variant, "保护与单位镜合并", ACCENT),
    ]:
        p = n(v, "ff_cold_high", "release")
        refs.extend([p / "result.json", p / "preview.npz"])
        with np.load(p / "preview.npz") as z:
            t = (z["time_s"] - 32e-9) * 1e9
            mask = (t >= -1) & (t <= 51)
            idx = np.flatnonzero(mask)
            peak = idx[np.argmax(z["out"][idx])]
            axes[0].plot(
                t[mask],
                z["iso_p"][mask],
                color=color,
                label=label,
                ls={"original": "-", "reconnect220": "--"}.get(v, "-."),
                lw=1.7,
            )
            axes[1].plot(
                t[mask],
                z["out"][mask],
                color=color,
                ls={"original": "-", "reconnect220": "--"}.get(v, "-."),
                lw=1.7,
            )
            axes[1].scatter(t[peak], z["out"][peak], s=26, color=color, zorder=5)
            rows.append(
                {
                    "variant": v,
                    "peak_OUT_V": float(z["out"][peak]),
                    "time_after_release_ns": float(t[peak]),
                    "at_peak": {
                        k: float(z[k][peak])
                        for k in [
                            "iso_p",
                            "led_a",
                            "led_k",
                            "data_safe",
                            "iled_cond",
                            "ipkg",
                        ]
                    },
                }
            )
    axes[0].legend(fontsize=10, ncol=3, loc="lower left")
    axes[0].set_ylabel("PISO 栅电压 (V)")
    axes[1].axhline(3.63, lw=1, ls=":", color="#923b50")
    axes[1].text(39, 3.68, "3.63 V 端差上限", fontsize=10)
    axes[1].set(
        ylabel="阴极侧 OUT (V)", xlabel="距 DISABLE 释放命令 (ns)", ylim=(-0.45, 4.17)
    )
    for ax in axes:
        ax.grid(axis="y", alpha=0.18)
    axes[0].set_title(
        "FF，−40 °C，供电 +5%    相同数据片段下的高侧重接", fontsize=15, loc="left"
    )
    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.13, top=0.91)
    name = "br-release-comparison"
    save(fig, name, refs)
    (EVIDENCE / (name + ".json")).write_text(
        json.dumps(
            {
                "window_after_ns": [-1, 51],
                "scope": "local DC-initialized native trace",
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


def dc(variant):
    order = [
        "tt",
        "tt_cold",
        "tt_hot",
        "tt_low",
        "tt_high",
        "ss_hot_low",
        "ff_cold_high",
        "sf_hot_low",
        "fs_cold_high",
    ]
    labels = [
        "TT 27",
        "TT −40",
        "TT 85",
        "TT 低压",
        "TT 高压",
        "SS 热低",
        "FF 冷高",
        "SF 热低",
        "FS 冷高",
    ]
    x = np.arange(9)
    fig, ax = plt.subplots(1, 1, figsize=(9.6, 3.7))
    refs = []
    for variant_dir, label, color, symbol in [
        (
            ROOT / "build/driver-pvt-20261117/b/clamp5v_buffer_soft",
            "原保护与单尾管",
            WARM,
            "o--",
        ),
        (WORK / variant, "合并保护与单位电流镜", ACCENT, "s-"),
    ]:
        ps = [variant_dir / (g + "-DC-L1") / "result.json" for g in order]
        refs += ps
        points = [json.loads(p.read_text())["current_uA"] for p in ps]
        ax.plot(x, points, symbol, lw=1.5, ms=5, color=color, label=label)
    ax.axhspan(99, 101, color=ACCENT, alpha=0.1, label="99–101 µA 允许区间")
    ax.axhline(100, color=INK, lw=0.5)
    ax.set(
        xlabel="工艺、温度和供电组合",
        ylabel="LED 导通电流 (µA)",
        xticks=x,
        xticklabels=labels,
    )
    ax.set_title("同一 100 µA 指令在九个既定工作点的 DC 结果", loc="left", fontsize=15)
    ax.legend(fontsize=10, ncol=3, loc="upper left")
    ax.grid(axis="y", alpha=0.14)
    save(fig, "br-dc-current", refs)


class Drawing:
    def __init__(self):
        self.parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" viewBox="0 0 1200 720"><rect width="1200" height="720" fill="white"/><g stroke-linecap="round" stroke-linejoin="round"><style>text{font-family: Bahnschrift, PingFang SC, Noto Sans CJK SC, sans-serif}</style>'
        ]

    def wire(self, *pts, color=INK, w=2):
        self.parts.append(
            f'<polyline points="{" ".join(f"{x},{y}" for x, y in pts)}" fill="none" stroke="{color}" stroke-width="{w}"/>'
        )

    def label(self, x, y, s, size=17, col=INK, weight=400, anchor="start"):
        self.parts.append(
            f'<text x="{x}" y="{y}" font-weight="{weight}" font-size="{size}" text-anchor="{anchor}" fill="{col}">{html.escape(s)}</text>'
        )

    def dot(self, x, y):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="3.5" fill="{INK}"/>')

    def mos(self, x, y, n, p=False, body="0"):
        # Visual terminal order from top to bottom, pMOS S/G/D, nMOS D/G/S.
        self.wire((x, y - 36), (x, y - 22), (x - 16, y - 22))
        self.wire((x, y + 36), (x, y + 22), (x - 16, y + 22))
        for a, b in [(-22, -9), (-5, 5), (9, 22)]:
            self.wire((x - 16, y + a), (x - 16, y + b))
        self.wire((x - 24, y - 23), (x - 24, y + 23))
        self.wire((x - 65, y), (x - 24, y))
        if p:
            self.parts.append(
                f'<circle cx="{x - 31}" cy="{y}" r="5" fill="white" stroke="{INK}" stroke-width="1.8"/>'
            )
        self.wire((x - 16, y), (x + 9, y))
        self.label(x + 13, y + 4, "B=" + body, 13, GREY)
        self.label(x + 12, y - 21, n, 16, INK, 600)

    def r(self, x, y, dx):
        self.wire((x, y), (x + 9, y))
        self.parts.append(
            f'<rect x="{x + 9}" y="{y - 6}" width="{dx - 18}" height="12" fill="white" stroke="{INK}" stroke-width="2"/>'
        )
        self.wire((x + dx - 9, y), (x + dx, y))

    def gnd(self, x, y):
        self.wire((x, y), (x, y + 8))
        for i, l in enumerate([12, 8, 4]):
            self.wire((x - l, y + 8 + 5 * i), (x + l, y + 8 + 5 * i))

    def rule(self, y):
        self.wire((25, y), (1175, y), color="#c7d5d8", w=1)

    def section(self, x, y, n, word):
        self.label(x, y, n, 18, ACCENT, 600)
        self.label(x + 42, y, word, 21, INK, 600)


def diagram(variant, path=None, name="br-integrated-schematic"):
    p = path if path is not None else n(variant, "ff_cold_high", "release")
    deck = (p / "testbench.spice").read_text()
    route = (p.parent / "inputs/route_b.spice").read_text()
    import re

    res = re.search(r"RGATE iso_g iso_p (\S+)", deck).group(1)
    assert (
        "CIB1 ib1 0 10f" in deck and "XFASTOFF iso_p iso_gb led_feed led_feed" in deck
    )
    dimensions = {
        tuple(
            re.search(
                r"^" + mos + r" .*?nfet_03v3 w=(\d+)u l=(\d+)u ", route, re.MULTILINE
            ).groups()
        )
        for mos in ["XREF", "XBASE", "XTAIL", "XTAIL1", "XTAIL2"]
    }
    assert len(dimensions) == 1
    w, l = next(iter(dimensions))
    for mos in ["XISO0", "XISO1", "XISO2"]:
        assert re.search(
            r"^" + mos + " led_a iso_p led_feed led_feed", deck, re.MULTILINE
        )
    d = Drawing()
    d.label(
        28, 37, f"B 电流转向驱动器　保护电路与 W{w}/L{l} 电流镜的连接", 28, INK, 600
    )
    d.rule(55)
    d.section(26, 92, "01", "高侧开关的关断与重接")
    d.section(605, 92, "02", "单位管产生 25 µA 基流与 75 µA 尾流")
    d.wire((579, 78), (579, 544), color="#c7d5d8", w=1)
    d.label(30, 145, "5 V 电平转换器", 16, GREY)
    d.label(30, 207, "iso_g", 17)
    d.r(80, 200, 80)
    d.label(82, 178, res.replace("k", " kΩ"), 17, ACCENT, 600)
    d.wire((160, 200), (260, 200), (260, 259), (325, 259))
    d.dot(260, 200)
    d.label(176, 189, "iso_p", 16)
    d.label(291, 125, "LED_FEED", 17)
    d.wire((280, 134), (390, 134), (390, 223))
    d.dot(280, 134)
    d.mos(260, 157, "", True, "feed")
    d.wire((260, 121), (260, 110), (280, 110), (280, 134))
    d.wire((260, 193), (260, 200))
    d.label(68, 161, "iso_gb", 14)
    d.wire((120, 157), (195, 157))
    d.label(316, 176, "XFASTOFF", 15, GREY)
    d.mos(390, 259, "PISO ×3", True, "feed")
    d.wire((390, 295), (390, 327), (227, 327))
    d.dot(390, 327)
    d.label(341, 351, "LED_A", 15)
    d.wire((227, 327), (227, 365))
    d.parts.append(
        f'<path d="M213 365 H241 L227 386 Z" fill="none" stroke="{INK}" stroke-width="2"/>'
    )
    d.wire((213, 387), (241, 387))
    d.wire((227, 387), (227, 427), (390, 427))
    d.label(141, 381, "MicroLED", 16)
    d.wire((275, 327), (275, 368))
    d.dot(275, 327)
    d.wire((262, 368), (288, 368))
    d.wire((262, 377), (288, 377))
    d.wire((275, 377), (275, 427))
    d.dot(275, 427)
    d.label(282, 405, "200 fF", 15)
    d.mos(390, 377, "XCLAMP", False, "0")
    d.wire((390, 327), (390, 341))
    d.wire((390, 413), (390, 427))
    # Same-net gate label, not attached to capacitance terminal.
    d.wire((322, 377), (325, 377))
    d.label(337, 368, "G*", 13, ACCENT)
    d.label(374, 448, "LED_K", 15)
    d.wire((227, 427), (227, 461))
    d.label(44, 478, "LED_K ─ 1 Ω ─ 0.5 nH ─ OUT", 17, INK, 600)
    rclamp = re.search(r"RCLAMP iso_g clamp_g (\S+)", deck).group(1).replace("k", " kΩ")
    d.label(30, 510, f"关断时 XFASTOFF 拉高 iso_p，iso_g 经 {rclamp} 开启钳位。", 16)
    d.label(30, 535, "释放时 EN 放电 G*（clamp_g），iso_p 经栅电阻缓降。", 16)
    d.label(608, 135, "电压转电流参考源", 17, INK, 600)
    d.label(608, 157, "VSET ≈ 0.5 V", 15, GREY)
    d.label(608, 175, "RSET ≈ 19.976 kΩ", 15, GREY)
    # XREF tied D=G and mirror inputs use same BIAS net labels.
    d.label(613, 189, "IOUT / BIAS", 15)
    d.wire((656, 198), (690, 198), (690, 215))
    d.mos(690, 251, "XREF")
    d.wire((625, 251), (610, 251), (610, 198), (656, 198))
    d.dot(656, 198)
    d.label(609, 285, "BIAS", 16, ACCENT, 600)
    d.gnd(690, 287)
    d.label(826, 158, "OUT", 18)
    d.wire((845, 171), (845, 216))
    d.mos(845, 252, "XBASE")
    d.gnd(845, 288)
    d.label(776, 242, "BIAS", 15, ACCENT)
    d.label(957, 158, "OUT", 17)
    d.label(1075, 158, "DUMMY", 16)
    d.wire((975, 170), (975, 212))
    d.wire((1097, 170), (1097, 212))
    d.mos(975, 248, "XLED")
    d.mos(1097, 248, "XDUMMY")
    d.label(910, 239, "GP", 15)
    d.label(1033, 239, "GB", 15)
    d.wire((975, 284), (975, 318), (1097, 318), (1097, 284))
    d.dot(1025, 318)
    d.label(1037, 309, "VX", 17)
    d.wire((1025, 318), (1025, 349))
    d.mos(1025, 385, "XTAIL ×3")
    d.gnd(1025, 421)
    d.label(957, 376, "BIAS", 15, ACCENT)
    d.label(607, 348, "XREF、XBASE 与三只 XTAIL 同尺寸", 16, INK, 600)
    d.label(607, 374, f"W/L = {w} µm / {l} µm，体端接地。", 16)
    d.label(607, 411, "低位时尾流转到 DUMMY 支路，", 16)
    d.label(607, 436, "高位时尾流和基流在 OUT 相加。", 16)
    d.label(607, 487, "DUMMY 经 27.6 kΩ 接 VIN。GP、GB 来自互补预驱动。", 16)
    d.label(607, 514, "高侧 XISO0/1/2 均为 6 V PMOS，体端接 LED_FEED。", 16)
    d.rule(555)
    d.section(28, 588, "03", "输入缓冲一级输出的附加电容")
    d.label(35, 645, "DATA_GATE", 16)
    d.wire((140, 639), (172, 639))
    d.parts.append(
        f'<path d="M172 619 L172 659 L212 639 Z" stroke="{INK}" fill="white" stroke-width="2"/>'
    )
    d.parts.append(
        f'<circle cx="217" cy="639" r="5" stroke="{INK}" fill="white" stroke-width="2"/>'
    )
    d.wire((222, 639), (380, 639))
    d.dot(300, 639)
    d.label(248, 623, "IB1", 16, ACCENT)
    d.wire((300, 639), (300, 656))
    d.wire((286, 657), (314, 657))
    d.wire((286, 665), (314, 665))
    d.gnd(300, 666)
    d.label(319, 679, "10 fF", 16, ACCENT)
    d.parts.append(
        f'<path d="M380 619 L380 659 L420 639 Z" stroke="{INK}" fill="white" stroke-width="2"/>'
    )
    d.parts.append(
        f'<circle cx="425" cy="639" r="5" stroke="{INK}" fill="white" stroke-width="2"/>'
    )
    d.wire((430, 639), (470, 639))
    d.label(484, 645, "DATA_BUFFERED → 原 READY 门控 → DATA_SAFE", 16)
    d.label(607, 695, "图中仅画改动涉及的支路。同名网络直接连接。", 15, GREY)
    target = OUT / (name + ".svg")
    target.write_text("\n".join(d.parts) + "\n</g></svg>\n")
    provenance(name, [p / "testbench.spice", p.parent / "inputs/route_b.spice"])


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("variant")
    args = a.parse_args()
    OUT.mkdir(exist_ok=True, parents=True)
    EVIDENCE.mkdir(exist_ok=True, parents=True)
    wave(args.variant)
    dc(args.variant)
    diagram(args.variant)
    larger = WORK.parent / "b_final/unit6-r260/ff_cold_high-release-s40"
    if (larger / "testbench.spice").is_file():
        diagram(None, larger, "br-unit6-schematic")
