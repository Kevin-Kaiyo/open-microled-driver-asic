#!/usr/bin/env python3
"""Build source-checked Chinese PWM teaching panels. No circuit simulation.

SVG device metadata preserves actual D/G/S/B net order; PNGs use Chrome's
SVG renderer at 2x resolution. The six-device subset is checked against the
physical test macro rather than the obsolete educational aliases.
"""
from pathlib import Path
from html import escape
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/research/blender-pwm-animation-20261018/figures'
NET = ROOT / 'layout/startup_v3/startup_test_macro.spice'
INK = '#294551'
MUTE = '#64777f'
REF = '#188b7d'
LED = '#d77a1d'
SIG = '#8a5ab3'
OFF = '#a0abb1'
EXPECTED = {
    'XP_REF': ['BIAS', 'BIAS', 'VSS', 'VSS'],
    'XP_OUT': ['LED_K', 'GATE', 'VSS', 'VSS'],
    'XP_PASS': ['BIAS', 'PWM_DRIVE', 'GATE', 'VSS'],
    'XP_CLAMP': ['GATE', 'PWM_B', 'VSS', 'VSS'],
    'XP_INV_N': ['PWM_B', 'PWM_DRIVE', 'VSS', 'VSS'],
    'XP_INV_P': ['PWM_B', 'PWM_DRIVE', 'VBUF', 'VBUF'],
}


class Panel:
    def __init__(self, high):
        self.high = high
        self.p = []

    def text(self, x, y, text, size=17, color=INK, bold=False, anchor='start'):
        self.p.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{600 if bold else 400}">{escape(text)}</text>')

    def wire(self, pts, color=INK, width=2.3, dash=None):
        self.p.append('<polyline points="' + ' '.join(f'{x},{y}' for x, y in pts) + f'" fill="none" stroke="{color}" stroke-width="{width}"' + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')

    def dot(self, x, y, color=INK):
        self.p.append(f'<circle cx="{x}" cy="{y}" r="3.8" fill="{color}"/>')

    def arrow(self, x1, y1, x2, y2, color, dashed=False):
        name = {REF: 'ref', LED: 'led', SIG: 'sig', INK: 'ink'}[color]
        self.p.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}" stroke-width="2.8" marker-end="url(#{name})"' + (' stroke-dasharray="5 4"' if dashed else '') + '/>')

    def ground(self, x, y):
        for dy, width in [(0, 15), (6, 10), (12, 5)]:
            self.wire([(x-width, y+dy), (x+width, y+dy)])

    def mos(self, x, y, name, pmos=False, horizontal=False, on=False, color=REF):
        self.p.append(f'<g data-device="{name}" data-nets="{" ".join(EXPECTED[name])}" data-terminal-order="D G S B" data-channel-on="{str(on).lower()}" transform="' + (f'matrix(0 1 1 0 {x} {y})' if horizontal else f'translate({x} {y})') + '">')
        # Standard enhancement-MOS three-terminal symbol; body ties are stated
        # explicitly in the footer and are preserved in D/G/S/B metadata.
        channel = color if on else OFF
        for y1, y2 in [(-22, -12), (-5, 5), (12, 22)]:
            self.wire([(-10, y1), (-10, y2)], channel, 3.3)
        self.wire([(-28, -24), (-28, 24)], SIG)
        self.wire([(0, -45), (0, -20), (-10, -20)], channel)
        self.wire([(-10, 20), (0, 20), (0, 45)], channel)
        if pmos:
            self.wire([(-55, 0), (-43, 0)], SIG)
            self.p.append(f'<circle cx="-39" cy="0" r="4" fill="white" stroke="{SIG}" stroke-width="2.3"/>')
            self.wire([(-35, 0), (-28, 0)], SIG)
        else:
            self.wire([(-55, 0), (-28, 0)], SIG)
        self.p.append('</g>')
        if horizontal:
            self.text(x-41, y+21, 'D', 13, MUTE)
            self.text(x+31, y+21, 'S', 13, MUTE)
            self.text(x+10, y-38, 'G', 13, MUTE)
        else:
            self.text(x+10, y-31, 'S' if pmos else 'D', 13, MUTE)
            self.text(x+10, y+43, 'D' if pmos else 'S', 13, MUTE)
            self.text(x-55, y-10, 'G', 13, MUTE)

    def build(self):
        h = self.high
        title = 'PWM 高电平：LED 导通' if h else 'PWM 低电平：LED 关闭'
        self.text(28, 43, title, 27, INK, True)
        self.text(28, 76, '像素局部 · FAULT = 0、PERMIT = 1、参考源已稳定', 17, MUTE)
        self.text(28, 103, 'PWM_DRIVE 是保护逻辑与输出缓冲之后的信号。', 16, MUTE)

        # Equivalent upstream reference output and the diode-connected mirror.
        self.text(130, 144, 'VREF', 17, INK, True, 'middle')
        self.wire([(130, 154), (130, 181)], REF)
        self.p.append(f'<circle cx="130" cy="205" r="24" fill="white" stroke="{REF}" stroke-width="2.3"/>')
        self.arrow(130, 191, 130, 219, REF)
        self.wire([(130, 229), (130, 350)], REF, 3)
        self.text(171, 193, '等效 IREF', 18, REF, True)
        self.text(171, 217, '上游参考输出', 15, MUTE)
        self.text(171, 240, '隔离级已导通', 15, MUTE)
        self.text(160, 283, 'BIAS', 18, REF, True)
        self.wire([(130, 300), (305, 300)], SIG)
        self.dot(130, 300, REF)
        self.mos(130, 395, 'XP_REF', on=True)
        self.wire([(75, 395), (59, 395), (59, 300), (130, 300)], SIG)
        self.text(161, 393, '① XP_REF', 18, INK, True)
        self.text(161, 417, '参考管 · 二极管连接', 15, MUTE)
        self.text(161, 439, 'W/L = 20/4 µm', 15, MUTE)
        self.arrow(104, 327, 104, 356, REF)
        self.text(28, 455, '参考支路', 16, REF, True)
        self.text(28, 478, '始终导通', 16, REF, True)

        # Pass device connects a gate-voltage node: no DC-current arrow here.
        self.mos(350, 300, 'XP_PASS', horizontal=True, on=h, color=SIG)
        self.wire([(350, 230), (350, 245)], SIG)
        self.text(350, 223, 'PWM_DRIVE', 16, SIG, True, 'middle')
        self.text(292, 345, '③ XP_PASS', 18, INK, True)
        self.text(292, 369, '偏置开关：' + ('导通' if h else '截止'), 15, SIG if h else MUTE)
        self.wire([(395, 300), (510, 300), (510, 395), (535, 395)], SIG)
        self.text(466, 282, 'GATE', 18, SIG, True)

        # Off-chip LED, correct anode/cathode diode orientation.
        self.text(590, 144, 'VLED', 17, INK, True, 'middle')
        ledcolor = LED if h else OFF
        self.wire([(590, 154), (590, 199)], ledcolor, 3)
        self.p.append(f'<path d="M576,199 H604 L590,224 Z M574,228 H606" fill="none" stroke="{ledcolor}" stroke-width="2.5"/>')
        self.wire([(590, 228), (590, 350)], ledcolor, 3)
        self.arrow(611, 209, 632, 189, ledcolor if h else INK)
        self.arrow(618, 221, 639, 201, ledcolor if h else INK)
        self.text(556, 193, 'A', 13, MUTE)
        self.text(556, 249, 'K', 13, MUTE)
        self.text(642, 223, '片外', 16, MUTE)
        self.text(642, 246, 'MicroLED', 16, MUTE)
        self.text(607, 291, 'LED_K', 18, INK, True)
        self.mos(590, 395, 'XP_OUT', on=h, color=LED)
        self.text(622, 378, '② XP_OUT', 17, INK, True)
        self.text(622, 404, '恒流下拉', 15, MUTE)
        self.text(622, 428, '20/4 µm', 15, MUTE)
        if h:
            self.arrow(675, 308, 675, 347, LED)
            self.text(640, 474, 'ILED', 17, LED, True)
            self.text(609, 499, '约 100 µA', 17, LED, True)
        else:
            self.text(622, 474, 'ILED ≈ 0', 17, MUTE, True)
            self.text(620, 499, '保留漏电', 15, MUTE)

        # Clamp removes gate charge, never a steady LED current path.
        self.wire([(510, 395), (410, 395), (410, 410)], SIG)
        self.dot(510, 395, SIG)
        self.mos(410, 455, 'XP_CLAMP', on=not h, color=SIG)
        self.wire([(300, 455), (355, 455)], SIG)
        self.text(296, 485, 'PWM_B', 16, SIG, True)
        self.text(439, 461, '④ XP_CLAMP', 17, INK, True)
        self.text(439, 486, '栅极下拉：' + ('截止' if h else '导通'), 15, MUTE if h else SIG)
        self.wire([(130, 440), (130, 530), (590, 530), (590, 440)], INK)
        self.wire([(410, 500), (410, 530)], SIG if not h else INK)
        self.dot(410, 530)
        self.ground(360, 530)
        self.text(360, 568, 'VSS（地）', 17, INK, True, 'middle')
        if not h:
            self.arrow(382, 486, 382, 519, SIG, dashed=True)
            self.text(154, 510, '虚线：仅切换瞬间放电', 15, SIG)

        self.wire([(28, 583), (732, 583)], '#dce5e7', 1)
        self.text(28, 612, '互补控制：CMOS 反相器', 19, INK, True)
        self.text(240, 639, 'VBUF', 16, INK, True)
        self.wire([(220, 625), (220, 640)])
        self.mos(220, 685, 'XP_INV_P', pmos=True, on=not h, color=SIG)
        self.mos(220, 790, 'XP_INV_N', on=h, color=SIG)
        self.wire([(220, 730), (220, 745)], SIG)
        self.dot(220, 738, SIG)
        self.wire([(220, 738), (430, 738)], SIG)
        self.text(282, 724, 'PWM_B = ' + ('0' if h else 'VBUF'), 17, SIG, True)
        self.wire([(165, 685), (100, 685), (100, 790), (165, 790)], SIG)
        self.wire([(58, 738), (100, 738)], SIG)
        self.dot(100, 738, SIG)
        self.text(30, 660, 'PWM_DRIVE', 15, SIG, True)
        self.text(33, 764, '高' if h else '低', 17, SIG, True)
        self.text(272, 671, '⑥ XP_INV_P', 17, INK, True)
        self.text(272, 695, 'PMOS：' + ('截止' if h else '导通'), 15, MUTE if h else SIG)
        self.text(272, 790, '⑤ XP_INV_N', 17, INK, True)
        self.text(272, 814, 'NMOS：' + ('导通' if h else '截止'), 15, SIG if h else MUTE)
        self.ground(220, 835)
        self.text(245, 844, 'VSS', 15, INK)

        self.p.append('<rect x="470" y="612" width="262" height="228" rx="12" fill="#f1f6f7"/>')
        self.text(488, 642, '工作原理', 19, INK, True)
        lines = (['• BIAS 传到 GATE', '• 输出管镜像参考电流', '• LED 电流流向 VSS', '', '栅极只有切换充电电流；', '稳态栅极电流近似为零。'] if h else
                 ['• GATE 被下拉至 VSS', '• 输出管截止，LED 关闭', '• 参考支路保持工作', '', '下拉电流只在放电时出现；', '稳态仅有器件漏电。'])
        for i, line in enumerate(lines):
            self.text(488, 674+i*27, line, 16, MUTE if i > 2 else INK)
        self.text(28, 877, 'NMOS 体端接 VSS；PMOS 体端接 VBUF。同名网络电气相连。', 15, MUTE)

        defs = ''.join(f'<marker id="{name}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="{color}"/></marker>' for name, color in [('ref',REF),('led',LED),('sig',SIG),('ink',INK)])
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="760" height="900" viewBox="0 0 760 900" role="img">'
                f'<title>{escape(title)}</title><desc>六只实际实例的像素局部原理图。LED位于片外；上游参考源、隔离级、保护逻辑与缓冲器省略。电流箭头采用传统电流方向，栅极无稳态直流。</desc>'
                '<style>text{font-family:"PingFang SC","Noto Sans CJK SC","Arial",sans-serif}path,polyline{stroke-linecap:round;stroke-linejoin:round}</style>'
                f'<defs>{defs}</defs><rect width="760" height="900" fill="white"/>' + ''.join(self.p) + '</svg>\n')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    net_text = NET.read_text()
    devices = {p[0]: p[1:5] for line in net_text.splitlines() if line.startswith('XP_') for p in [line.split()]}
    assert devices == EXPECTED, (devices, EXPECTED)
    for high in [True, False]:
        (OUT / ('pwm-high.svg' if high else 'pwm-low.svg')).write_text(Panel(high).build())
    js = r'''
const { chromium } = require('/Users/kimmy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
  const b=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  const p=await b.newPage({viewport:{width:760,height:900},deviceScaleFactor:2});
  for(const name of ['pwm-high','pwm-low']){
    await p.goto('file://'+process.argv[1]+'/'+name+'.svg');
    await p.evaluate(()=>document.fonts.ready);
    await p.screenshot({path:process.argv[1]+'/'+name+'.png'});
  }
  await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
'''
    subprocess.run(['node', '-e', js, str(OUT)], check=True)
    check = {
        'passed': True,
        'source': str(NET.relative_to(ROOT)),
        'source_sha256': hashlib.sha256(NET.read_bytes()).hexdigest(),
        'devices_d_g_s_b': EXPECTED,
        'source_checked_device_count': len(devices),
        'numbering': {'1':'XP_REF','2':'XP_OUT','3':'XP_PASS','4':'XP_CLAMP','5':'XP_INV_N','6':'XP_INV_P'},
        'colors': {'led_current': LED, 'reference_current': REF, 'gate_control': SIG},
        'assumptions': ['FAULT=0', 'PERMIT=1', 'reference_settled', 'LED_off_chip', 'upstream_reference_and_safety_buffer_omitted'],
        'high': {'XP_PASS': 'on', 'XP_CLAMP': 'off', 'XP_OUT': 'on', 'XP_REF': 'on', 'XP_INV_N': 'on', 'XP_INV_P': 'off', 'PWM_B':'VSS'},
        'low': {'XP_PASS': 'off', 'XP_CLAMP': 'on', 'XP_OUT': 'off', 'XP_REF': 'on', 'XP_INV_N': 'off', 'XP_INV_P': 'on', 'PWM_B':'VBUF'},
        'steady_gate_current_arrows': False,
        'low_state_dashed_arrow': 'gate-charge discharge during switching only',
        'pixel_dimensions': [760,900],
        'raster_dimensions': [1520,1800],
        'visual_reviewed': False,
        'evidence_level': 'source-checked explanatory drawing, not new electrical simulation',
    }
    (OUT / 'schematic-check.json').write_text(json.dumps(check, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(check, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
