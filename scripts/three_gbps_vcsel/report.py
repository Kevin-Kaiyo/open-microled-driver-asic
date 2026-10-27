#!/usr/bin/env python3
"""Render the 2026-10-27 research addendum; calculations, not circuit simulation."""
from pathlib import Path
from html import escape
import hashlib
import json
import math
import re
import numpy as np
import markdown
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'docs/research/three-gbps-vcsel-20261027'
EV = ROOT / 'evidence/three-gbps-vcsel-20261027'
FIG = DEST / 'figures'
INK, TEAL, BLUE, GRAY = '#203440', '#147b78', '#39789e', '#657984'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def calculate():
    eta = 4096 / 4736
    tau_o, tau_r = 200e-12, 1 / (2 * math.pi * 1e9)
    # For two first-order poles: (1+w²*tau_o²)*(1+w²*tau_r²)=2.
    aa, bb = tau_o**2 * tau_r**2, tau_o**2 + tau_r**2
    w2 = 2 / (bb + math.sqrt(bb**2 + 4 * aa))
    rows = []
    for net in [3.0, 3.2]:
        line = net / eta
        row = {'net_Gbps': net, 'line_Gbps': line,
               'NRZ_GBd': line, 'PAM4_GBd': line / 2,
               'NRZ_UI_ps': 1000 / line, 'PAM4_UI_ps': 2000 / line,
               'training_guard_ns': 64 / line,
               'NRZ_legacy_100ps_UI': .1 * line}
        for name, f in [('NRZ', line / 2), ('PAM4', line / 4)]:
            a = 1 / math.sqrt((1 + (2 * math.pi * f * 1e9 * tau_o)**2)
                              * (1 + (2 * math.pi * f * 1e9 * tau_r)**2))
            row[name + '_Nyquist_GHz'] = f
            row[name + '_proxy_dB_at_Nyquist'] = 20 * math.log10(a)
        rows.append(row)
    audit = json.loads((EV / 'baseline-audit.json').read_text())
    for row in rows:
        independent = next(x for x in audit['rate_calculations'] if x['net_Gbps'] == row['net_Gbps'])
        assert math.isclose(row['line_Gbps'], independent['line_Gbps'], rel_tol=1e-12)
        for name in ['NRZ', 'PAM4']:
            assert math.isclose(row[name + '_proxy_dB_at_Nyquist'],
                                independent[name]['optical_rx_two_pole_dB_at_Nyquist'], abs_tol=1e-10)
    assert math.isclose(rows[1]['line_Gbps'], 3.7, abs_tol=1e-12)
    # Conditional iid zero-error binomial illustration; the deterministic simulation is not such a trial.
    n = math.ceil(math.log(.05) / math.log1p(-1e-12))
    r = {'evidence_class': 'analytic calculation; no new SPICE, optical or VCSEL measurement',
         'eta': eta, 'rates': rows, 'tau_optical_ps': 200,
         'RX_3dB_GHz': 1, 'cascade_3dB_GHz': math.sqrt(w2) / (2 * math.pi) / 1e9,
         'zero_error_iid_95pct_upper_4096': -math.expm1(math.log(.05) / 4096),
         'zero_error_iid_bits_for_95pct_upper_1e_minus_12': n,
         'illustrative_time_if_counting_every_3p7G_line_bit_s': n / (3.2e9 / eta),
         'illustrative_time_if_counting_only_3p2G_payload_bit_s': n / 3.2e9,
         'source_sha256': {'evidence/fair-driver-v1/summary.json': sha(ROOT / 'evidence/fair-driver-v1/summary.json'),
                           'scripts/fair_driver_v1/receiver_equal_latency_v2.py': sha(ROOT / 'scripts/fair_driver_v1/receiver_equal_latency_v2.py')},
         'limits': ['No carrier-rate or optical-noise model fitted.', 'Nyquist attenuation is not an achievable bit-rate limit.',
                    'The BER example assumes independent stationary Bernoulli errors, unlike the deterministic 4096-bit simulator.']}
    (EV / 'calculations.json').write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return r


class Drawing:
    def __init__(self, title, w=1200, h=1050):
        self.w, self.h, self.parts = w, h, []
        self.text(35, 48, title, 26, INK, bold=True)

    def text(self, x, y, text, size=18, color=INK, anchor='start', bold=False):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{600 if bold else 400}">{escape(text)}</text>')

    def line(self, points, color=INK, width=2, arrow=False, dashed=False):
        self.parts.append('<polyline points="' + ' '.join(f'{x},{y}' for x, y in points) + f'" fill="none" stroke="{color}" stroke-width="{width}"' + (' marker-end="url(#arrow)"' if arrow else '') + (' stroke-dasharray="7 5"' if dashed else '') + '/>')

    def dot(self, x, y):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{INK}"/>')

    def ground(self, x, y):
        self.line([(x, y - 15), (x, y)])
        for dy, half in [(0, 18), (7, 12), (14, 5)]:
            self.line([(x - half, y + dy), (x + half, y + dy)])

    def source(self, x, y, label):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="32" fill="white" stroke="{INK}" stroke-width="2"/>')
        self.line([(x, y - 18), (x, y + 18)], arrow=True)
        self.text(x + 47, y + 6, label, 19, TEAL)

    def nmos(self, x, y, label):
        self.line([(x, y - 65), (x, y - 34), (x - 22, y - 34), (x - 22, y + 34), (x, y + 34), (x, y + 65)])
        self.line([(x - 35, y - 32), (x - 35, y + 32)])
        self.line([(x - 75, y), (x - 35, y)])
        self.line([(x - 22, y), (x + 35, y)])
        self.parts.append(f'<polygon points="{x-18},{y} {x-8},{y-5} {x-8},{y+5}" fill="{INK}"/>')
        self.text(x + 40, y + 5, 'B=VSS', 15, GRAY)
        self.text(x + 23, y - 48, label, 20, BLUE, bold=True)
        self.text(x + 8, y - 28, 'D', 14, GRAY)
        self.text(x + 8, y + 50, 'S', 14, GRAY)
        self.text(x - 66, y - 10, 'G', 14, GRAY)

    def save(self, name):
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" role="img"><title>{escape(name)}</title><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="{TEAL}"/></marker></defs><style>text{{font-family:"PingFang SC","Noto Sans CJK SC",sans-serif}}polyline{{stroke-linecap:round;stroke-linejoin:round}}</style><rect width="100%" height="100%" fill="white"/>' + ''.join(self.parts) + '</svg>\n'
        (FIG / (name + '.svg')).write_text(svg)


def circuit():
    d = Drawing('VCSEL 共阳极电流转向：教学原理图（未实现、未仿真）', h=1030)
    d.text(35, 82, '电流源为功能符号；不代表已设计的参考源、尾源或保护模块。MOS 未指定工艺和 W/L。', 17, GRAY)
    # Shared laser supply; laser branch and dummy branch.
    d.line([(480, 135), (480, 190)])
    d.text(480, 121, 'V_LASER', 21, BLUE, anchor='middle', bold=True)
    d.line([(480, 155), (870, 155), (870, 190)])
    d.dot(480, 155)
    # Laser diode anode above, cathode below; two outgoing optical arrows.
    d.parts.append(f'<polygon points="450,207 510,207 480,250" fill="none" stroke="{INK}" stroke-width="2"/>')
    d.line([(480, 190), (480, 207)])
    d.line([(449, 252), (511, 252)])
    d.line([(480, 252), (480, 365)])
    d.line([(517, 226), (550, 202)], TEAL, arrow=True)
    d.line([(524, 246), (557, 222)], TEAL, arrow=True)
    d.text(330, 235, 'VCSEL', 21, BLUE)
    d.text(497, 290, 'K / OUT', 18, BLUE)
    d.text(460, 189, 'A', 14, GRAY)
    # Dummy load box deliberately not claimed to be a particular matched device.
    d.parts.append(f'<rect x="828" y="190" width="84" height="110" fill="#edf3f2" stroke="{INK}" stroke-width="2"/>')
    d.text(934, 232, 'Dummy 负载', 19, BLUE)
    d.text(934, 260, '压降须匹配验证', 15, GRAY)
    d.line([(870, 300), (870, 365)])
    d.nmos(480, 430, 'Q_LED')
    d.nmos(870, 430, 'Q_DUMMY')
    d.line([(480, 495), (480, 545), (675, 545), (870, 545), (870, 495)])
    d.dot(675, 545)
    d.line([(675, 545), (675, 598)])
    d.source(675, 630, 'I_MOD：尾电流')
    d.line([(675, 662), (675, 735)])
    d.ground(675, 750)
    # Independent base-bias sink at the actual cathode node.
    d.dot(480, 320)
    d.line([(480, 320), (200, 320), (200, 598)])
    d.source(200, 630, 'I_BIAS')
    d.line([(200, 662), (200, 735)])
    d.ground(200, 750)
    d.text(200, 800, '固定偏置：两种数据状态均存在', 17, GRAY, anchor='middle')
    d.text(675, 800, 'VSS；电流镜及顺从电压未展开', 17, GRAY, anchor='middle')
    d.text(390, 420, 'D+', 18, TEAL, anchor='end')
    d.text(780, 420, 'D-', 18, TEAL, anchor='end')
    d.line([(395, 430), (405, 430)], TEAL)
    d.line([(785, 430), (795, 430)], TEAL)
    d.text(35, 865, '数据 1：Q_LED 导通时：I_LASER = I_BIAS + I_MOD；Dummy 支路基本无调制电流。', 20, TEAL)
    d.text(35, 905, '数据 0：Q_DUMMY 导通时：I_LASER = I_BIAS；I_MOD 改走 Dummy，仍消耗供电能量。', 20, BLUE)
    d.text(35, 955, '限流、过温、异常关断、APC/温度补偿及负载寄生是完整设计的必要补充；本图未给出流片电路。', 17, GRAY)
    d.save('vcsel-current-steering')


def plots(calc):
    font = ROOT / 'build/fair-driver-v1/report-font/NotoSansCJKsc-Regular.otf'
    font_manager.fontManager.addfont(font)
    plt.rcParams.update({'font.family': font_manager.FontProperties(fname=font).get_name(),
                         'font.size': 11, 'svg.fonttype': 'none', 'svg.hashsalt': 'three-gbps-vcsel-20261027',
                         'axes.spines.top': False, 'axes.spines.right': False})
    f = np.geomspace(.03, 8, 500)
    fo, fr = 1 / (2 * np.pi * 200e-12) / 1e9, 1
    response = -10 * np.log10((1 + (f / fo)**2) * (1 + (f / fr)**2))
    fig, ax = plt.subplots(figsize=(10.5, 4.2))
    ax.semilogx(f, response, c=TEAL, lw=2, label='既有假设：200 ps 光学代理 × 1 GHz RX')
    for value, label, color in [(1.85, 'NRZ：1.850 GHz', BLUE), (.925, 'PAM4：0.925 GHz', '#a96c37')]:
        y = -10 * np.log10((1 + (value / fo)**2) * (1 + (value / fr)**2))
        ax.plot(value, y, 'o', c=color)
        ax.annotate(label + f'\n{y:.2f} dB', (value, y), xytext=(12, 12), textcoords='offset points', color=color)
    ax.axhline(-3, color=GRAY, ls='--', lw=1)
    ax.set(xlabel='频率 / GHz', ylabel='幅频响应 / dB', ylim=(-38, 2), title='净 3.2 Gb/s 的频谱预算：解析计算，不是链路仿真')
    ax.grid(alpha=.2); ax.legend(loc='lower left'); fig.tight_layout()
    for ext in ['svg', 'png']:
        fig.savefig(FIG / ('proxy-bandwidth.' + ext), dpi=160, metadata={'Date': '2026-10-27'})
    plt.close(fig)
    # Hypothetical levels deliberately normalized: no synthetic mA values assigned to a device.
    bits = np.array([0, 1, 1, 0, 1, 0, 0, 1])
    t = np.arange(9) / 3.7
    fig, axs = plt.subplots(2, 1, figsize=(10.5, 5.2), sharex=True)
    axs[0].step(t, np.r_[bits, bits[-1]], where='post', color=TEAL, lw=2)
    axs[0].set(yticks=[0, 1], yticklabels=['I_BIAS', 'I_BIAS + I_MOD'], ylim=(-.4, 1.6), ylabel='VCSEL 电流')
    for k, b in enumerate(bits):
        axs[0].text((k + .5) / 3.7, 1.28, str(b), ha='center', color=INK)
    axs[0].text(.03, -.29, 'I_BIAS 与 I_TH 的关系须由选定器件实测确定；本图未画阈值线。', fontsize=9, color=GRAY)
    axs[1].step(t, np.r_[1-bits, 1-bits[-1]], where='post', color=BLUE, lw=2)
    axs[1].set(yticks=[0, 1], yticklabels=['0', 'I_MOD'], ylim=(-.4, 1.6), ylabel='Dummy 电流', xlabel='时间 / ns；NRZ 每比特约 270 ps')
    for ax in axs:
        ax.grid(alpha=.2)
    fig.suptitle('电流转向的理想状态说明：非器件仿真，无边沿、噪声或激光动态')
    fig.tight_layout()
    for ext in ['svg', 'png']:
        fig.savefig(FIG / ('vcsel-current-states.' + ext), dpi=160, metadata={'Date': '2026-10-27'})
    plt.close(fig)
    for p in FIG.glob('*.svg'):
        p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines()) + '\n')


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    calc = calculate(); circuit(); plots(calc)
    old = (ROOT / 'docs/research/fair-driver-comparison-20261025/index.html').read_text()
    style = re.search(r'<style>.*?</style>', old, re.S).group(0)
    body = markdown.markdown((DEST / 'README.md').read_text(), extensions=['tables', 'fenced_code', 'toc'])
    html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>单通道超过3 Gb/s与VCSEL驱动研究</title>' + style + '</head><body><main><nav><a href="../fair-driver-comparison-20261025/index.html">A/B/C原始实验</a><a href="README.md">完整文字</a><a href="../../../evidence/three-gbps-vcsel-20261027/source-ledger.json">来源与证据</a></nav>' + body + '</main></body></html>\n'
    (DEST / 'index.html').write_text(html)
    files = [DEST / 'README.md', DEST / 'index.html', EV / 'baseline-audit.json', EV / 'calculations.json', EV / 'source-ledger.json', Path(__file__).resolve()] + sorted(FIG.glob('*'))
    manifest = {'date_JST': '2026-10-27', 'scope': 'Research addendum and analytic calculations only; no new circuit simulation or optical measurement',
                'files': [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in files]}
    (EV / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'report': str(DEST / 'index.html'), 'assets': len(files), 'new_SPICE_cases': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
