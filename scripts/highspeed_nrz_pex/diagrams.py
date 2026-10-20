#!/usr/bin/env python3
"""Original circuit diagrams explaining the PEX experiment's boundaries.

These figures are topology/method illustrations. Numerical PEX and layout plots
are generated separately from the actual extracted files and GDS.
"""
from pathlib import Path
import importlib.util
import json
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/research/highspeed-nrz-pex-20261020/figures"
spec = importlib.util.spec_from_file_location("drawing", ROOT / "scripts/highspeed_routes/circuits.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.OUT = OUT


def save(d, name, description):
    d.save(name)
    p = OUT / (name + ".svg")
    text = re.sub(r"<desc>.*?</desc>", "<desc>" + description + "</desc>", p.read_text(), flags=re.S)
    p.write_text(text)


def capacitor(d, x, y, label, color=m.BLUE):
    d.line([(x, y - 40), (x, y - 8)], color)
    d.line([(x - 22, y - 8), (x + 22, y - 8)], color)
    d.line([(x - 22, y + 8), (x + 22, y + 8)], color)
    d.line([(x, y + 8), (x, y + 40)], color)
    d.text(x + 34, y + 7, label, 20, color)


def hr(d, x1, x2, y, label):
    mid = (x1 + x2) / 2
    d.line([(x1, y), (mid - 34, y)])
    d.p.append(f'<rect x="{mid-34}" y="{y-12}" width="68" height="24" fill="white" stroke="{m.INK}" stroke-width="2.7"/>')
    d.line([(mid + 34, y), (x2, y)])
    d.text(mid, y - 28, label, 20, m.INK, anchor="middle")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = m.Drawing("一根理想导线，为什么会变成多个电路节点？",
                  "局部等效电路：用于解释 PEX；符号 Rwire、Cground、Ccouple 不是本次提取数值", 1020)
    d.text(52, 190, "① 原理图：输出缓冲器直接驱动 MOS 栅极", 24, bold=True)
    d.box(60, 245, 265, 120, "前置 CMOS 缓冲器", ["输出节点 CTRL"], m.PURPLE)
    d.line([(325, 305), (800, 305), (800, 350), (998, 350)], m.PURPLE)
    d.mos(1060, 350, "MN", ["OUT", "CTRL", "VSS", "VSS"], color=m.ORANGE)
    d.line([(1060, 298), (1060, 230)], m.ORANGE)
    d.text(1060, 205, "OUT", 21, m.ORANGE, True, "middle")
    d.line([(1060, 402), (1060, 440)])
    d.ground(1060, 440)
    d.text(380, 280, "整条线同一个电位 V(CTRL)", 20, m.PURPLE)
    d.text(1110, 410, "B = VSS", 20, m.MUTE)
    d.line([(48, 492), (1552, 492)], m.LIGHT, 1.5)
    d.text(52, 545, "② 提取后：金属 / 通孔有电阻；导线与其他网络有电容", 24, bold=True)
    d.box(60, 620, 265, 120, "同一个 CMOS 缓冲器", ["驱动端 CTRL"], m.PURPLE)
    d.line([(325, 680), (400, 680)], m.PURPLE)
    hr(d, 400, 750, 680, "Rwire：金属 + 通孔")
    hr(d, 750, 998, 680, "局部接触 R")
    d.mos(1060, 680, "MN", ["OUT", "Glocal", "Slocal", "Blocal"], color=m.ORANGE)
    d.dot(750, 680, m.PURPLE)
    d.text(760, 620, "中间节点", 20, m.PURPLE)
    d.text(1000, 620, "Glocal", 20, m.PURPLE)
    d.line([(1060, 628), (1060, 565)], m.ORANGE)
    d.text(1120, 592, "OUT 也有自身互连 RC", 20, m.ORANGE)
    d.line([(1060, 732), (1060, 810)])
    d.text(1090, 790, "Slocal / Blocal", 20, m.MUTE)
    d.line([(750, 680), (750, 720)])
    capacitor(d, 750, 760, "Cground")
    d.line([(750, 800), (750, 828)])
    d.ground(750, 828)
    d.line([(480, 680), (480, 645)])
    capacitor(d, 480, 605, "Ccouple", m.TEAL)
    d.line([(480, 565), (700, 565)], m.TEAL)
    d.text(720, 572, "相邻网 Vaggressor", 20, m.TEAL)
    d.footer(["Rwire 使两端产生压降；Cground 需要充放电；Ccouple 的电流取决于两条线的电压差变化。",
              "MOS 内部电容仍由 PDK 模型提供。提取 AD/AS/PD/PS 替换原扩散估计，不能把两套几何电容重复相加。"])
    save(d, "wire-to-rc", "原创局部等效电路。用于解释分布式 RC 与器件模型的区别，数值不代表实际提取。")

    d = m.Drawing("两条路线的版图范围与外部电路",
                  "虚线范围内为本次 MOS 核心；电源、LED 与电阻的边界在两条路线之间保持明确", 1150)
    for x, title, core, rails, external in [
        (55, "A · 受限摆幅电压驱动", "6 MOS：INV1 → INV2 → 输出 CMOS",
         ["VDD 3.3 V", "VH / VL：原 DC 校准值"], ["VH / VL 仍为可吸收电流的理想电源", "稳压器、pad / ESD 未进入版图"]),
        (835, "B · 电流转向", "9 MOS：偏置镜 + 基线 + 转向 + 2级反相器",
         ["VDD 3.3 V", "外部 RREF → BIAS；RDUMMY → DUMMY"], ["RREF = 88.386106 kΩ；RDUMMY = 28 kΩ", "外部电阻及其布线寄生未物理实现"]),
    ]:
        d.text(x, 195, title, 27, m.BLUE, True)
        d.p.append(f'<rect x="{x}" y="275" width="710" height="295" rx="8" fill="#f6f9fa" stroke="{m.BLUE}" stroke-width="2" stroke-dasharray="10 7"/>')
        d.text(x + 24, 325, "实际 GDS / DRC / LVS / PEX 的核心范围", 22, m.BLUE, True)
        d.text(x + 24, 380, core, 20)
        d.line([(x + 24, 422), (x + 680, 422)], m.LIGHT, 1.5)
        d.lines(x + 24, 465, rails, 21, 42, m.MUTE)
        d.text(x + 16, 248, "DATA →", 21, m.PURPLE, True)
        d.text(x + 24, 620, "OUT → 同一封装 R/L → 同一 MicroLED", 21, m.ORANGE, True)
        d.lines(x + 24, 690, external, 20, 40, m.MUTE)
    d.box(55, 815, 1490, 105, "固定比较条件", ["5 V LED；25 / 100 µA 目标；CLED = 200 fF；Rpkg = 1 Ω；Lpkg = 0.5 nH；同一 PRBS 与接收代理"], m.TEAL, size=20)
    d.footer(["本阶段面积只统计 MOS 核心的实际 GDS 包围盒，不能称为最终 ASIC die area。",
              "实测静态 LED I–V 与假设的高速电容、封装及接收模型分开记录；不由 PEX 推导实测光学 BER。"])
    save(d, "comparison-boundary", "本项目两条高速 NRZ 路线的核心和外部边界；不显示制造完成的完整 ASIC。")

    (OUT / "diagram-scope.json").write_text(json.dumps({
        "wire-to-rc.svg": "Topology/method illustration with symbolic parasitics, not fitted or extracted numbers.",
        "comparison-boundary.svg": "Declared simulation/physical boundary; actual passed checks come from the evidence tables."
    }, indent=2) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
