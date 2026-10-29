#!/usr/bin/env python3
"""Original conceptual figures for the 2026-10-29 MicroLED device co-design study.

No paper artwork, device layout, TCAD field solution or measured curve is used.
All geometries and probability-density curves are didactic illustrations.

Run from the repository root:
  build/layout/venv/bin/python scripts/microled_device_codesign_20261029/figures.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/research/microled-device-codesign-20261029/figures"
LEDGER = ROOT / "evidence/microled-device-codesign-20261029/figure-ledger.json"
W = 1600
NAVY = "#203B50"
TEAL = "#167E82"
TEAL_LIGHT = "#DAF0EE"
BLUE = "#567E9B"
BLUE_LIGHT = "#E4EDF3"
ORANGE = "#B56C36"
ORANGE_LIGHT = "#F7E7D8"
PURPLE = "#896C95"
PURPLE_LIGHT = "#EEE7F1"
GRAY = "#63717A"
LIGHT = "#F4F7F8"
LINE = "#CDD9DF"
WHITE = "#FFFFFF"


def choose_font() -> str:
    # SVG keeps real text and names portable fallbacks; PNG embeds rendered glyphs.
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            font_manager.fontManager.addfont(candidate)
            return font_manager.FontProperties(fname=candidate).get_name()
    return "DejaVu Sans"


FONT = choose_font()
plt.rcParams.update({
    "font.family": [FONT, "sans-serif"],
    "font.size": 14,
    "svg.fonttype": "none",
    "svg.hashsalt": "microled-device-codesign-20261029",
    "axes.unicode_minus": False,
    "savefig.facecolor": WHITE,
})


class Drawing:
    def __init__(self, name: str, title: str, subtitle: str, height: int = 1200):
        self.name = name
        self.height = height
        self.fig = plt.figure(figsize=(W / 100, height / 100), dpi=100)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set(xlim=(0, W), ylim=(height, 0))
        self.ax.set_axis_off()
        self.texts = []
        self.t(50, 29, title, 23, weight="bold")
        self.t(50, 77, subtitle, 13.5, GRAY)
        self.line(50, 113, 1550, 113, LINE, 1.2)

    def t(self, x, y, s, size=14, color=NAVY, weight="normal", ha="left", va="top", rotation=0):
        # This system CJK face lacks several Latin math glyphs; let DejaVu supply them.
        face_weight = 300 if weight == "normal" else 600 if weight == "bold" else weight
        item = self.ax.text(x, y, s, fontsize=size, color=color, weight=face_weight,
                            ha=ha, va=va, rotation=rotation, linespacing=1.48,
                            fontfamily=[FONT, "DejaVu Sans"], zorder=8)
        self.texts.append(item)
        return item

    def rect(self, x, y, w, h, fill=WHITE, edge=LINE, lw=1.4, radius=0, alpha=1):
        if radius:
            p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={radius}",
                               facecolor=fill, edgecolor=edge, linewidth=lw, alpha=alpha)
        else:
            p = Rectangle((x, y), w, h, facecolor=fill, edgecolor=edge, linewidth=lw, alpha=alpha)
        self.ax.add_patch(p)
        return p

    def line(self, x1, y1, x2, y2, color=NAVY, lw=2, style="-", z=2):
        self.ax.plot([x1, x2], [y1, y2], color=color, lw=lw, linestyle=style, zorder=z)

    def path(self, points, color=NAVY, lw=2, style="-", z=2):
        self.ax.plot(*zip(*points), color=color, lw=lw, linestyle=style, zorder=z)

    def arrow(self, x1, y1, x2, y2, color=TEAL, lw=2.5, style="-|>", scale=17, curve=0, z=5):
        p = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=scale,
                            linewidth=lw, color=color,
                            connectionstyle=f"arc3,rad={curve}", zorder=z)
        self.ax.add_patch(p)

    def dot(self, x, y, color=NAVY, r=4):
        self.ax.add_patch(Circle((x, y), r, facecolor=color, edgecolor=color, zorder=6))

    def badge(self, x, y, n, color=TEAL):
        self.ax.add_patch(Circle((x, y), 17, facecolor=color, edgecolor=color, zorder=6))
        self.t(x, y - 1, str(n), 13, WHITE, "bold", ha="center", va="center")

    def panel(self, x, y, w, h, n, title, fill=LIGHT):
        self.rect(x, y, w, h, fill, LINE, radius=13)
        self.badge(x + 27, y + 30, n)
        self.t(x + 56, y + 15, title, 15, weight="bold")

    def resistor_h(self, x1, x2, y, label=None):
        mid = (x1 + x2) / 2
        self.line(x1, y, mid - 38, y)
        self.rect(mid - 38, y - 12, 76, 24, WHITE, NAVY, 2)
        self.line(mid + 38, y, x2, y)
        if label:
            self.t(mid, y - 48, label, 13.5, ha="center")

    def capacitor_v(self, x, y1, y2, label=None, side="right", color=NAVY):
        mid = (y1 + y2) / 2
        self.line(x, y1, x, mid - 9, color)
        self.line(x - 21, mid - 9, x + 21, mid - 9, color, 2.5)
        self.line(x - 21, mid + 9, x + 21, mid + 9, color, 2.5)
        self.line(x, mid + 9, x, y2, color)
        if label:
            dx = 30 if side == "right" else -30
            self.t(x + dx, mid - 18, label, 13.5, color,
                   ha="left" if side == "right" else "right")

    def footer(self, lines):
        y = self.height - 99
        self.line(50, y - 18, 1550, y - 18, LINE, 1.2)
        self.t(50, y, "\n".join(lines), 13, GRAY)

    def save(self):
        OUT.mkdir(parents=True, exist_ok=True)
        self.fig.canvas.draw()
        renderer = self.fig.canvas.get_renderer()
        clipped = []
        for text in self.texts:
            box = text.get_window_extent(renderer)
            if box.x0 < 9 or box.x1 > W - 9 or box.y0 < 9 or box.y1 > self.height - 9:
                clipped.append(text.get_text())
        if clipped:
            raise RuntimeError(f"Text outside safe canvas in {self.name}: {clipped}")
        paths = []
        for suffix in ("svg", "png"):
            target = OUT / f"{self.name}.{suffix}"
            self.fig.savefig(target, dpi=100, metadata={"Creator": "Original independent instructional drawing; matplotlib", "Date": "2026-10-29"})
            if suffix == "svg":
                data = target.read_text()
                # Real text with a cross-platform CJK fallback stack.
                data = data.replace(f"font-family: '{FONT}', 'DejaVu Sans'", "font-family: 'PingFang SC', 'Hiragino Sans GB', 'Noto Sans CJK SC', 'Microsoft YaHei UI', 'DejaVu Sans', sans-serif")
                target.write_text(data)
            paths.append({
                "path": str(target.relative_to(ROOT)),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "bytes": target.stat().st_size,
            })
        plt.close(self.fig)
        return {"width_px": W, "height_px": self.height, "min_font_pt": 13,
                "text_canvas_bounds_check": "pass", "artifacts": paths}


def cross_section():
    d = Drawing("01-device-cross-section", "图 1｜GaN MicroLED：电流、光、寄生与热走不同路径",
                "原创概念剖面 + 小信号端口模型；横向接触仅为教学示例，不代表工艺堆栈或实际尺寸。", 1180)
    d.panel(50, 139, 900, 665, 1, "先沿电流路径读结构")
    # Layers: p mesa on a continuous n-GaN layer; etched n contact is outside mesa.
    d.rect(145, 572, 720, 98, "#E8E6DF", "#ABA99E")
    d.t(505, 608, "衬底 / 缓冲层（材料与厚度待定）", 14, ha="center")
    d.rect(145, 425, 720, 147, BLUE_LIGHT, BLUE)
    d.t(500, 521, "n-GaN：横向电流扩展", 14, BLUE, ha="center")
    d.rect(145, 295, 465, 93, PURPLE_LIGHT, PURPLE)
    d.t(179, 317, "p-GaN / p⁺ 接触区", 14, PURPLE)
    d.rect(145, 388, 465, 37, TEAL_LIGHT, TEAL, 2)
    d.t(171, 396, "InGaN / GaN 量子阱 QW", 14, TEAL)
    d.rect(145, 274, 465, 21, ORANGE_LIGHT, ORANGE)
    d.t(175, 235, "p 接触金属 / 透明导电扩展层", 14, ORANGE)
    d.rect(735, 404, 115, 21, ORANGE_LIGHT, ORANGE)
    d.t(727, 354, "n 接触", 14, ORANGE)
    # Sidewall coating is dielectric, no conductive connection between p and n.
    d.rect(132, 286, 13, 150, "#D7DFE4", GRAY)
    d.rect(610, 286, 13, 150, "#D7DFE4", GRAY)
    d.line(619, 331, 668, 313, GRAY, 1.3)
    d.t(662, 261, "mesa 侧壁\n介质钝化", 14, GRAY)
    # Conventional current flows down p, across QWs, laterally in n, then up n contact.
    d.arrow(550, 275, 550, 440, ORANGE, 4)
    d.line(550, 440, 550, 479, ORANGE, 4)
    d.arrow(550, 479, 790, 479, ORANGE, 4)
    d.arrow(790, 479, 790, 427, ORANGE, 4)
    d.t(171, 451, "常规电流：p → QW → n", 14, ORANGE)
    # Emission from active region escapes around the illustrative top metal.
    for x, endx in [(440, 440), (480, 495), (510, 536)]:
        d.arrow(x, 409, endx, 194, TEAL, 2.4, scale=16)
    d.t(477, 174, "光逃逸（部分方向）", 13.5, TEAL)
    d.arrow(325, 678, 325, 748, ORANGE, 3)
    d.arrow(540, 678, 540, 748, ORANGE, 3)
    d.arrow(755, 678, 755, 748, ORANGE, 3)
    d.line(218, 757, 840, 757, ORANGE, 4)
    d.t(522, 768, "热：结区 → 衬底 / 键合层 → 散热边界", 13.5, ORANGE, ha="center")

    d.panel(980, 139, 570, 665, 2, "同一结构的电端口视图")
    d.t(1020, 211, "P（p 端）", 14)
    d.t(1020, 677, "N（n 端，参考端）", 14)
    d.line(1038, 270, 1120, 270)
    d.resistor_h(1120, 1370, 270, "Rs：接触 + 薄层扩展")
    d.line(1370, 270, 1495, 270)
    d.line(1038, 648, 1495, 648)
    d.dot(1080, 270)
    d.dot(1370, 270)
    d.dot(1080, 648)
    d.dot(1370, 648)
    d.capacitor_v(1080, 270, 648, color=BLUE)
    d.t(1118, 514, "Cpad", 14, BLUE)
    d.t(1118, 548, "焊盘 / 隔离层", 13, BLUE)
    # Effective active junction admittance. Cj is not a second independent lifetime pole.
    d.line(1302, 270, 1302, 400)
    d.rect(1288, 400, 28, 106, WHITE, NAVY, 2)
    d.line(1302, 506, 1302, 648)
    d.t(1246, 433, "gj", 14, ha="right")
    d.capacitor_v(1450, 270, 648, color=TEAL)
    d.t(1370, 677, "Cj(V,T,f)", 14, TEAL)
    d.arrow(1171, 346, 1171, 478, BLUE, 2.5)
    d.t(1191, 353, "iC", 14, BLUE)
    d.t(1020, 714, "gj、Cj：有效动态结区导纳。\nCpad 充放电不直接产生光子。\n结区储能与复合须用一致模型关联。", 13.5, GRAY)

    d.panel(50, 828, 1500, 217, 3, "从端口电流到光功率，要区分三件事", WHITE)
    for x, title, body, color in [
        (82, "① 注入与电荷", "端口总电流含储能变化 dQ/dt；\n不能直接当成瞬时发光电流。", ORANGE),
        (580, "② 复合与出光", "辐射复合产生光；非辐射复合发热。\n光提取与耦合决定可接收光功率。", TEAL),
        (1090, "③ 温度与偏置", "Rs、Cj、复合率依赖工作点；\n热路径也会改变效率与可靠性。", PURPLE),
    ]:
        d.t(x, 892, title, 14.5, color, "bold")
        d.t(x, 930, body, 13.5)
    d.footer(["证据等级：独立概念示意；不是实测剖面、掩模版图、TCAD 或已验证 SPICE 子电路。",
              "读图边界：未画出所有外延层 / 势垒层；gj 与 Cj 代表有效小信号行为，光响应还需联合拟合验证。"])
    return d.save()


def orientation_quantum_wells():
    d = Drawing("02-orientation-quantum-wells", "图 4｜晶向与量子阱：先看内部场，再看载流子与传输",
                "原创定性机制图；晶向、阱宽、阱数和材料质量共同作用，不能仅按一个名称判定速度或效率。", 1320)
    # Orientation geometry: growth/well normal upward in every panel.
    panels = [
        (50, "c 面 / polar", "阱法向 n 平行 c 轴", (0, -92)),
        (560, "m 面 / nonpolar", "阱法向 n 垂直 c 轴", (102, 0)),
        (1070, "半极性面 / semipolar", "阱法向 n 与 c 轴倾斜", (76, -63)),
    ]
    for i, (x, title, desc, (dx, dy)) in enumerate(panels, 1):
        d.panel(x, 139, 480, 302, i, title)
        cx = x + 210
        for yy in [296, 314, 332]:
            d.rect(x + 55, yy, 340, 8, TEAL_LIGHT, TEAL, 1.3)
        d.arrow(cx, 326, cx, 215, NAVY, 2.1)
        d.t(cx - 22, 211, "n", 14, ha="right")
        d.arrow(cx + 20, 285, cx + 20 + dx, 285 + dy, PURPLE, 3)
        if i == 1:
            d.t(cx + 38, 216, "c / P主轴", 13, PURPLE)
        elif i == 2:
            d.t(cx + 50, 252, "c / P主轴", 13, PURPLE)
        else:
            d.t(cx + 115, 246, "c / P主轴", 13, PURPLE)
        d.t(x + 48, 365, desc, 14, NAVY)
        d.t(x + 48, 404, "水平细层：QW 平面", 13, GRAY)
    d.t(66, 458, "界面极化片电荷取决于 ΔP · n。图中仅示意主轴；应变、组分和载流子屏蔽决定实际法向场。", 13.5, GRAY)

    d.panel(50, 507, 1500, 311, 4, "QCSE：法向场可使电子与空穴的空间分布分离", WHITE)
    for x, title, separation, field in [
        (90, "较强法向场：分离较明显", 93, True),
        (850, "较弱法向场：重叠可增大", 14, False),
    ]:
        d.t(x, 571, title, 14, PURPLE if field else TEAL, "bold")
        center = x + 254
        left, right = center - 130, center + 130
        d.rect(left, 633, 260, 106, LIGHT, LINE)
        d.line(left, 623, left, 748, LINE, 1.2, "--")
        d.line(right, 623, right, 748, LINE, 1.2, "--")
        z = np.linspace(left, right, 180)
        ecenter = center + separation / 2
        hcenter = center - separation / 2
        e = np.exp(-0.5 * ((z - ecenter) / 36) ** 2)
        h = np.exp(-0.5 * ((z - hcenter) / 36) ** 2)
        d.ax.fill_between(z, 733, 733 - e * 76, color=BLUE, alpha=.32)
        d.ax.fill_between(z, 733, 733 - h * 76, color=ORANGE, alpha=.32)
        d.ax.plot(z, 733 - e * 76, color=BLUE, lw=2.5)
        d.ax.plot(z, 733 - h * 76, color=ORANGE, lw=2.5)
        d.t(left + 4, 749, "阱内位置 z →", 13, GRAY)
        d.t(x + 2, 637, "空间\n概率\n示意", 13, GRAY)
        d.t(right + 23, 651, "电子 e⁻", 13, BLUE)
        d.t(right + 23, 688, "空穴 h⁺", 13, ORANGE)
        if field:
            d.arrow(left + 16, 612, right - 16, 612, PURPLE, 2)
            d.t(right + 14, 602, "F⊥", 13, PURPLE)
        else:
            d.t(left + 9, 609, "重叠大小取决于实际阱势与偏置", 13, GRAY)
    d.t(102, 780, "示意关系：辐射跃迁强度与电子 / 空穴波函数重叠有关；曲线没有长度、能量或概率数值刻度。", 13.5, GRAY)

    d.panel(50, 847, 480, 299, 5, "薄阱与厚阱：约束不同")
    d.rect(102, 929, 42, 86, TEAL_LIGHT, TEAL, 2)
    d.rect(215, 929, 106, 86, PURPLE_LIGHT, PURPLE, 2)
    d.t(122, 1027, "较薄", 13.5, ha="center")
    d.t(268, 1027, "较厚", 13.5, ha="center")
    d.t(351, 923, "同一材料 / 场\n条件下比较", 13, GRAY)
    d.t(82, 1075, "阱宽影响束缚能、重叠、态填充与逃逸；\n更薄或更厚都不是普遍最优。", 13.5)

    d.panel(560, 847, 480, 299, 6, "多阱：注入不一定均匀")
    for i in range(4):
        x = 620 + i * 84
        d.rect(x, 935, 24, 76, TEAL_LIGHT, TEAL)
        d.arrow(x + 28, 970, x + 70, 970, ORANGE, 2)
    d.t(607, 1025, "QW  |  势垒  |  QW  |  势垒 …", 13, GRAY)
    d.t(592, 1075, "阱数、势垒与极化共同影响捕获 / 逃逸、\n跨阱传输和各阱的载流子分配。", 13.5)

    d.panel(1070, 847, 480, 299, 7, "速度与效率要同时读")
    d.t(1102, 924, "更快复合可能来自", 14)
    d.t(1102, 964, "辐射通道  或  非辐射 SRH 通道", 14, TEAL)
    d.t(1102, 1022, "非辐射增强可缩短动态寿命，\n却可能降低效率。应在同一偏置 /\n温度下联测带宽与绝对光功率。", 13.5)
    d.footer(["证据等级：独立概念示意；没有求解 Schrödinger–Poisson 或量子阱传输方程，也不代表某一外延样品。",
              "读图边界：晶向不是材料质量、应变、缺陷或接触工艺的替代指标；动态寿命与直流效率不应互相代替。"])
    return d.save()


def size_electrodes():
    d = Drawing("03-size-electrode-tradeoffs", "图 2｜尺寸与电极：缩小发光区不会等比例缩小全部代价",
                "原创尺寸缩放与接触俯视图；L → L/2 仅为几何比较，未给定真实器件尺寸或制造规则。", 1260)
    d.panel(50, 139, 665, 365, 1, "几何缩放：面积、周长和焊盘不同步")
    d.rect(106, 236, 180, 180, TEAL_LIGHT, TEAL, 2)
    d.t(196, 296, "边长 L\n面积 A", 15, TEAL, ha="center")
    d.rect(376, 326, 90, 90, TEAL_LIGHT, TEAL, 2)
    d.t(421, 347, "L/2", 14, TEAL, ha="center")
    d.arrow(304, 367, 357, 367, GRAY, 2)
    d.t(505, 242, "A → A/4\nP → P/2\nP/A → 2 ×", 14.5)
    d.t(88, 451, "方形：A = L²，P/A = 4/L；圆形有相同的 1/L 趋势。", 13.5, GRAY)

    d.panel(745, 139, 805, 365, 2, "公平比较：先固定什么，再谈缩小的收益")
    d.line(774, 286, 1520, 286, LINE)
    d.t(779, 217, "比较口径", 14, weight="bold")
    d.t(1007, 217, "L → L/2", 14, weight="bold")
    d.t(1232, 217, "仍需验证", 14, weight="bold")
    d.t(779, 309, "同电流密度 J", 14, TEAL, "bold")
    d.t(1007, 309, "I → I/4", 14)
    d.t(1232, 309, "光功率 / 接收裕量", 13.5)
    d.line(774, 359, 1520, 359, LINE, 1)
    d.t(779, 386, "同总电流 I", 14, ORANGE, "bold")
    d.t(1007, 386, "J → 4J", 14)
    d.t(1232, 386, "复合 / droop / 温升", 13.5)
    d.t(779, 451, "C总 ≈ cA·A + cP·P + Cpad + C互连（仅缩放分解示意）", 13.5, GRAY)

    # Neutral alternative plan views. Metal at top p and exposed n are electrically isolated.
    for x, number, title, symmetric in [
        (50, 3, "偏置接触：需检查电流拥挤", False),
        (815, 4, "分布接触：需检查遮光与寄生", True),
    ]:
        d.panel(x, 534, 735, 429, number, title)
        bx, by = x + 50, 631
        d.rect(bx, by, 370, 260, BLUE_LIGHT, BLUE, 1.5)
        d.rect(bx + 70, by + 31, 220, 197, "#EDF5F3", TEAL, 1.5)
        d.rect(bx + 64, by + 25, 232, 209, "none", GRAY, 4)
        if symmetric:
            # n contact ring sits on exposed n-GaN outside the etched mesa.
            d.rect(bx + 14, by + 8, 342, 244, "none", BLUE, 10)
            for xx in [bx + 118, bx + 180, bx + 242]:
                d.rect(xx - 5, by + 54, 10, 152, ORANGE_LIGHT, ORANGE, 1.4)
            d.rect(bx + 92, by + 121, 176, 12, ORANGE_LIGHT, ORANGE, 1.4)
            for xx in [bx + 149, bx + 211]:
                d.arrow(xx, by + 129, xx, by + 76, ORANGE, 1.5, scale=11)
                d.arrow(xx, by + 135, xx, by + 188, ORANGE, 1.5, scale=11)
        else:
            d.rect(bx + 327, by + 24, 19, 210, BLUE, BLUE)
            d.rect(bx + 84, by + 54, 22, 153, ORANGE_LIGHT, ORANGE, 1.5)
            # Shading conveys a hypothesis of contact-proximal injection, not computed J.
            for j, alpha in enumerate([.30, .19, .10]):
                d.rect(bx + 108 + j * 45, by + 55, 45, 150, ORANGE, "none", 0, alpha=alpha)
            for yy in [by + 82, by + 128, by + 176]:
                d.arrow(bx + 108, yy, bx + 212, yy, ORANGE, 2, scale=12)
        tx = x + 453
        d.t(tx, 636, "橙：mesa 顶面 p 电极", 13.5, ORANGE)
        d.t(tx, 687, "蓝：露出 n-GaN 上\n的 n 接触", 13.5, BLUE)
        d.t(tx, 760, "灰：侧壁 / 介质隔离", 13.5, GRAY)
        d.t(tx, 812, "浅绿：发光 mesa\n箭头 / 阴影仅示意扩展", 13.5, TEAL)
        d.t(x + 32, 919, "p / n 金属未相连；外部引线未画，不能据此制造。", 13.5, GRAY)

    d.panel(50, 992, 1500, 134, 5, "焊盘下限与制造约束：最后要回到同一净码率、误码率和链路裕量")
    d.t(82, 1051, "Cpad / 互连不会自动随 mesa 缩小；侧壁损伤、钝化、接触电阻、对准容差与装配良率都需独立验证。", 13.5)
    d.footer(["证据等级：几何缩放公式 + 独立接触构型示意；无实测电流密度、效率、温度或寄生参数。",
              "读图边界：俯视图未按比例；对称 / 网格接触并非默认胜出，需要同面积与同偏置下的电光联合测量。"])
    return d.save()


def codesign_reference_planes():
    d = Drawing("04-codesign-reference-planes", "图 6｜把 Driver、封装、LED 与 RX 放在同一组参考面上",
                "目标净速率 3.2 Gb/s：线速需结合实际编码 / FEC 开销；以同一光通道和 BER 条件比较候选方案。", 1320)
    d.panel(50, 139, 1500, 310, 1, "先定义模型归属：每一段只计入一次")
    blocks = [
        (80, 204, "Driver", "输出阻抗 / 摆幅\n顺从电压 / 噪声", BLUE_LIGHT, BLUE),
        (370, 204, "封装 / 互连", "R / L / C 或\n实测网络 S 参数", LIGHT, GRAY),
        (660, 204, "MicroLED", "端口电荷 + 载流子\n电 → 光映射", TEAL_LIGHT, TEAL),
        (950, 204, "光通道", "耦合 / 传播损耗\n通道响应", LIGHT, GRAY),
        (1240, 204, "PD + TIA / RX", "响应度 / Cpd / 带宽\n噪声 → 眼图 / BER", PURPLE_LIGHT, PURPLE),
    ]
    for x, y, title, body, fill, col in blocks:
        d.rect(x, y, 240, 142, fill, col, radius=8)
        d.t(x + 120, y + 18, title, 15, col, "bold", ha="center")
        d.t(x + 120, y + 67, body, 13.5, NAVY, ha="center")
    for xa in [320, 610, 900, 1190]:
        d.arrow(xa + 4, 274, xa + 45, 274, NAVY, 2.4)
    for xp, letter, desc in [(345, "A", "Driver 焊盘"), (635, "B", "LED 焊盘"), (925, "C", "LED 光输出"), (1215, "D", "PD 入射光")]:
        d.line(xp, 195, xp, 368, GRAY, 1.3, "--")
        d.t(xp, 374, f"{letter}：{desc}", 13, GRAY, ha="center")
    d.t(82, 414, "A→B：封装网络　　B→C：LED 电光响应　　C→D：光通道　　D→RX：接收链；输入 / 输出端口必须写清。", 13.5, GRAY)

    d.panel(50, 478, 1500, 383, 2, "测量设置：电校准与光接收响应分别处理")
    # Measurement setup at the same LED port B, with DC bias fed through bias tee.
    measurement_blocks = [
        (85, 619, 206, "VNA Port 1", "复数 S11 / 激励"),
        (351, 619, 174, "Bias-T", "DC + RF"),
        (605, 619, 204, "LED @ B", "固定 I0、T0"),
        (1019, 619, 222, "校准 PD / TIA", "已知 Hrx(f)"),
        (1300, 619, 208, "VNA Port 2", "测量整链复数 S21"),
    ]
    for x, y, w, title, body in measurement_blocks:
        d.rect(x, y, w, 108, WHITE, TEAL if "LED" in title else LINE, 1.5, radius=7)
        d.t(x + w / 2, y + 16, title, 14, weight="bold", ha="center")
        d.t(x + w / 2, y + 61, body, 13, GRAY, ha="center")
    for x1, x2 in [(291, 351), (525, 605), (1241, 1300)]:
        d.arrow(x1 + 4, 672, x2 - 5, 672, NAVY, 2.1)
    d.arrow(814, 672, 1014, 672, TEAL, 2.7)
    d.t(910, 620, "光路", 13, TEAL, ha="center")
    d.t(910, 710, "记录耦合 / 通道响应", 13, GRAY, ha="center")
    d.rect(352, 553, 173, 42, ORANGE_LIGHT, ORANGE, radius=6)
    d.t(439, 562, "DC 偏置源", 13, ORANGE, ha="center")
    d.arrow(438, 595, 438, 617, ORANGE, 2)
    d.line(580, 586, 580, 757, BLUE, 1.8, "--")
    d.t(580, 555, "B", 14, BLUE, "bold", ha="center")
    d.t(82, 774, "电端：SOLT / TRL 等校准到探针参考面，再去嵌入夹具 / 互连，明确最终参考面 B（LED 焊盘）。", 13.5, BLUE)
    d.t(82, 817, "光端：记录 PD / TIA、光路和 VNA 归一化定义；去除已知响应后，才解释 LED 本征 E/O 响应。", 13.5, TEAL)

    d.panel(50, 890, 1500, 275, 3, "拟合不是终点：用不同测量约束同一组参数")
    steps = [
        (82, "I–V / P–I", "直流与绝对光功率"),
        (439, "复数 S11", "幅度 + 相位，多偏置 / 温度"),
        (822, "E/O S21", "同步约束电端与复合动态"),
        (1195, "独立大信号验证", "瞬态 / 眼图 / BER / 能量"),
    ]
    for i, (x, title, body) in enumerate(steps):
        d.t(x, 954, title, 14.5, TEAL, "bold")
        d.t(x, 995, body, 13.5)
        if i < 3:
            d.arrow(x + 270, 971, x + 325, 971, GRAY, 2)
    d.rect(80, 1045, 1440, 91, ORANGE_LIGHT, "#D6B394", radius=7)
    d.t(101, 1060, "避免重复计数：可选用动态结区导纳 + 一致光映射，或几何电容 + 显式载流子状态方程。", 13.5, ORANGE)
    d.t(101, 1100, "若 Cj 已含扩散 / 复合储能，不再无依据叠加同一寿命极点；已去嵌入的封装寄生也不再重复加入。", 13.5, ORANGE)
    d.footer(["证据等级：独立测量与模型分工示意；没有给出拟合结果，也不声明任何候选器件已达成净 3.2 Gb/s。",
              "读图边界：S21 为混合电光测量，数值依赖定义与校准；净速率、前 / 后 FEC BER、接收功率和全链能量需共同报告。"])
    return d.save()


FIGURE_METADATA = [
    {
        "id": "FIG01",
        "figure_number_in_report": 1,
        "basename": "01-device-cross-section",
        "title_zh": "GaN MicroLED：电流、光、寄生与热走不同路径",
        "explanation": "横向接触例子的层次剖面、正确的 p→QW→n 常规电流路径、侧壁介质钝化、局部光逃逸与向下热路径；用 Rs、Cpad、gj 和动态 Cj 区分端口储能与复合。",
        "source_basis_ids": ["ZHU2024", "ELBADAOUI2025", "WANG2019"],
        "source_basis": "独立机制综合；不追摹论文剖面或电路图。ZHU2024 / El Badaoui 2025 支持寄生网络与有源区动力学需联合分析的建模依据。",
        "supports": ["端口电流中的电容电流不能直接当作光输出", "接触与电流扩展、结区动态、焊盘和热路径具有不同作用"],
        "does_not_support": ["某种实际外延堆栈、层厚、材料参数或金属化已被选择", "所画有效电路已由本项目实测校准", "图示衬底散热方向是所有封装的唯一主要热路径"],
    },
    {
        "id": "FIG02",
        "figure_number_in_report": 4,
        "basename": "02-orientation-quantum-wells",
        "title_zh": "晶向与量子阱：先看内部场，再看载流子与传输",
        "explanation": "以同一水平阱平面展示 c 面、m 面和半极性面的晶轴 / 法向关系；以任意无量纲概率曲线解释 QCSE 波函数分离；并列阱宽、跨阱传输以及 SRH 使速度与效率分离的限制。",
        "source_basis_ids": ["RAJABI2018", "XU2023", "LI2025", "WANG2019"],
        "source_basis": "独立定性机制图；极化几何与波函数重叠不包含来源测量值。各晶向的实际 ΔP、应变、阱势与屏蔽必须在具体样品上确定。",
        "supports": ["晶向通过极化法向分量影响内部场", "较快复合可以来自辐射或非辐射通道，带宽不能替代光效率", "阱宽和阱数需要同时考虑束缚、捕获、逃逸及传输"],
        "does_not_support": ["图中的波函数来自数值求解或测量", "nonpolar 或 semipolar 必然比 c 面更快、更高效", "所有半极性面的法向场都严格处于另两者之间", "阱宽或阱数有一个普适最优值"],
    },
    {
        "id": "FIG03",
        "figure_number_in_report": 2,
        "basename": "03-size-electrode-tradeoffs",
        "title_zh": "尺寸与电极：缩小发光区不会等比例缩小全部代价",
        "explanation": "给出同形方形 L→L/2 的可核验面积 / 周长缩放；将同 J 与同 I 比较分开；独立画出 p 顶电极、露出 n-GaN 上 n 接触和介质隔离的两种俯视构型。",
        "source_basis_ids": ["LIN2026", "WANG2019", "ZHU2024", "ELBADAOUI2025"],
        "source_basis": "A=L²、P/A=4/L 为几何计算；接触图由作者独立构思，无实际 mask / GDS 参数。C 总分解仅为识别面积项、周长项和固定寄生的思考框架。",
        "supports": ["同 J 与同 I 下缩小面积对应不同的工作点", "周长 / 面积和固定焊盘项可限制单纯面积缩小的收益", "接触均匀性、遮光与寄生需要共同验证"],
        "does_not_support": ["接触图符合任一实际制造工艺的设计规则", "阴影或箭头代表 TCAD 电流密度", "分布 / 对称接触必然优于偏置接触", "器件面积缩小可直接推出净能量每比特下降"],
        "calculation": {"shape": "square", "scale_L": 0.5, "scale_area": 0.25, "scale_perimeter": 0.5, "scale_P_over_A": 2.0, "fixed_J_scale_I": 0.25, "fixed_I_scale_J": 4.0},
    },
    {
        "id": "FIG04",
        "figure_number_in_report": 6,
        "basename": "04-codesign-reference-planes",
        "title_zh": "把 Driver、封装、LED 与 RX 放在同一组参考面上",
        "explanation": "将 Driver-pad、LED-pad、LED optical output 与 PD input 定义为 A/B/C/D 参考面；示意 Bias-T、VNA 两端口和校准接收链；串起 I-V、P-I、复数 S11/S21 与独立大信号验证，并标明去嵌入和动态储能不得重复计数。",
        "source_basis_ids": ["ZHU2024", "ELBADAOUI2025", "LI2025"],
        "source_basis": "独立系统与测量分工示意，参考电光联合等效电路研究的一般方法；并非任何来源实验台的重绘。",
        "supports": ["联合拟合需记录参考面、复数响应与偏置温度", "电端校准和接收链光电响应去嵌入具有不同作用", "拟合后需要独立瞬态、BER 和净速率验证"],
        "does_not_support": ["一个孤立的 -3dB 带宽足以证明净 3.2 Gb/s", "已测 S11 的器件必然具有唯一可辨识的内部参数", "示意光路或接收机已具备实际所需带宽和噪声性能"],
    },
]


def main():
    rendered = [cross_section(), orientation_quantum_wells(), size_electrodes(), codesign_reference_planes()]
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    ledger = {
        "schema_version": "1.0",
        "date": "2026-10-29",
        "purpose": "MicroLED device / driver / package / receiver co-design research teaching figures",
        "evidence_class": "original conceptual diagrams plus explicitly stated elementary geometry",
        "reuse_status": "repository-original artwork; no borrowed source image or traced paper figure",
        "not_claimed": ["TCAD", "fabricated device", "mask layout or GDS", "process-qualified structure", "measured performance", "production readiness"],
        "generator": str(Path(__file__).relative_to(ROOT)),
        "generator_sha256": script_hash,
        "render_command": "build/layout/venv/bin/python scripts/microled_device_codesign_20261029/figures.py",
        "matplotlib_version": matplotlib.__version__,
        "numpy_version": np.__version__,
        "font_used_for_png": FONT,
        "font_fallbacks_in_svg": ["PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "Microsoft YaHei UI", "sans-serif"],
        "visual_review": {"status": "pending", "method": "Inspect each full PNG via view_image after rendering; record any repair before delivery."},
        "source_basis_locators": {
            "ZHU2024": {"title": "Modulation bandwidth analysis of GaN-based micro-LED deduced by an equivalent circuit model", "doi": "10.1364/OE.539321", "url": "https://pubmed.ncbi.nlm.nih.gov/39573804/", "use": "Mechanism / model decomposition only; no numerical result reproduced."},
            "ELBADAOUI2025": {"title": "SPICE Modeling of GaN MicroLEDs for Optical Communication", "doi": "10.1002/jsid.2105", "url": "https://sid.onlinelibrary.wiley.com/doi/full/10.1002/jsid.2105", "use": "Mechanism / electrical and optical modeling and de-embedding basis; no artwork copied."},
            "LI2025": {"doi": "10.1063/5.0258108", "preprint_url": "https://arxiv.org/abs/2502.21302", "use": "Mechanism / co-design context; source ID aligned with main report ledger."},
            "WANG2019": {"doi": "10.3390/mi10110767", "url": "https://doi.org/10.3390/mi10110767", "use": "Size / mechanism background; source ID aligned with main report ledger."},
            "RAJABI2018": {"doi": "10.1364/OE.26.024985", "url": "https://pubmed.ncbi.nlm.nih.gov/30469606/", "use": "Orientation / QW mechanism context; source ID supplied by report research owner."},
            "XU2023": {"doi": "10.1109/JPHOT.2023.3235108", "url": "https://doi.org/10.1109/JPHOT.2023.3235108", "use": "QW and orientation context; source ID supplied by report research owner."},
            "LIN2026": {"locator": "Main report source ledger, LIN2026", "use": "Size / current-density comparison context; source ID supplied by report research owner."},
        },
        "figures": [{**meta, **result} for meta, result in zip(FIGURE_METADATA, rendered)],
    }
    # A repeat render may preserve human visual QA only for byte-identical images.
    # New artwork always returns to pending until it is viewed again.
    current_hashes = {a["path"]: a["sha256"] for f in ledger["figures"] for a in f["artifacts"]}
    if LEDGER.exists():
        previous = json.loads(LEDGER.read_text()).get("visual_review", {})
        if previous.get("status") == "pass" and previous.get("artifact_sha256") == current_hashes:
            ledger["visual_review"] = previous
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"figures": len(rendered), "out": str(OUT), "ledger": str(LEDGER), "canvas_bounds": "pass"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
