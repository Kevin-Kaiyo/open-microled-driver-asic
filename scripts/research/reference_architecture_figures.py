"""Original teaching diagrams and independent arithmetic; does not run EDA.

Owns only architecture-* figures and sources.json in reference-safety-20261013.
Actual reference/fault diagrams carry D/G/S/B metadata checked against netlists.
"""
from pathlib import Path
from html import escape
import bisect
import csv
import hashlib
import json
import math
import re
import unicodedata
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/research/reference-safety-20261013'
FIG = OUT / 'figures'
INK = '#304b57'; TEAL = '#176e73'; ORANGE = '#b56336'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Drawing:
    def __init__(self, width, height, title, classification):
        self.width, self.height, self.title = width, height, title
        self.classification = classification; self.parts = []
        self.text(26, 38, title, 25, TEAL, bold=True)

    def text(self, x, y, text, size=19, color=INK, bold=False, anchor='start'):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}"'+(' font-weight="600"' if bold else '')+f'>{escape(str(text))}</text>')

    def wire(self, points, color=INK, dashed=False):
        self.parts.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in points)+f'" fill="none" stroke="{color}" stroke-width="2.2"'+(' stroke-dasharray="6 4"' if dashed else '')+'/>')

    def dot(self,x,y): self.parts.append(f'<circle cx="{x}" cy="{y}" r="3.5" fill="{INK}"/>')

    def arrow(self,x1,y1,x2,y2,color=TEAL):
        self.parts.append(f'<path d="M{x1} {y1} L{x2} {y2}" fill="none" stroke="{color}" stroke-width="2.5" marker-end="url(#arrow)"/>')

    def ground(self,x,y,label='VSS'):
        self.wire([(x,y-10),(x,y)])
        for dy,w in [(0,15),(5,10),(10,5)]: self.wire([(x-w,y+dy),(x+w,y+dy)])
        self.text(x,y+34,label,17,anchor='middle')

    def mos(self,x,y,name,typ='N',nets=None,dimensions='',body=None,dimension_dy=9):
        data = f' data-device="{name}" data-type="{typ}"'
        if nets: data += ' data-nets="'+' '.join(nets)+'" data-terminal-order="D G S B"'
        self.parts.append('<g'+data+'>')
        # Four-terminal enhancement MOS: source and drain are not body-tied.
        for a,b in [(-22,-12),(-5,5),(12,22)]: self.wire([(x-10,y+a),(x-10,y+b)])
        self.wire([(x-28,y-24),(x-28,y+24)])
        self.wire([(x,y-45),(x,y-20),(x-10,y-20)])
        self.wire([(x-10,y+20),(x,y+20),(x,y+45)])
        self.wire([(x-10,y),(x+45,y)])
        # Body arrow: NMOS p-body -> n-channel; PMOS direction reversed.
        points=(f'{x+8},{y-5} {x},{y} {x+8},{y+5}' if typ=='N' else f'{x},{y-5} {x+8},{y} {x},{y+5}')
        self.parts.append(f'<polygon points="{points}" fill="{INK}"/>')
        if typ=='P':
            self.wire([(x-55,y),(x-43,y)])
            self.parts.append(f'<circle cx="{x-39}" cy="{y}" r="4" fill="white" stroke="{INK}" stroke-width="2.2"/>')
            self.wire([(x-35,y),(x-28,y)])
        else: self.wire([(x-55,y),(x-28,y)])
        self.text(x+68,y-15,name,19,bold=True)
        if dimensions: self.text(x+68,y+dimension_dy,dimensions,15)
        if body:
            self.wire([(x+45,y),(x+60,y)])
            self.text(x+68,y+31,'B='+body,15)
        self.parts.append('</g>')
        return {'G':(x-55,y),'D':(x,y+(45 if typ=='P' else -45)),
                'S':(x,y+(-45 if typ=='P' else 45)),'B':(x+45,y)}

    def led(self,x,y,label='LED'):
        self.wire([(x,y-35),(x,y-16)])
        self.parts.append(f'<path d="M{x-14} {y-16} H{x+14} L{x} {y+9} Z M{x-16} {y+12} H{x+16}" fill="none" stroke="{INK}" stroke-width="2.2"/>')
        self.wire([(x,y+12),(x,y+35)])
        self.arrow(x+22,y-6,x+40,y-24,INK); self.arrow(x+29,y+3,x+47,y-15,INK)
        self.text(x-68,y+2,label,18); self.text(x-22,y-25,'A',14); self.text(x-22,y+31,'K',14)

    def resistor(self,x,y,label,dimensions='',nets=None):
        data=(' data-device="XRSET" data-nets="'+' '.join(nets)+'" data-terminal-order="P N B"') if nets else ''
        self.parts.append('<g'+data+'>')
        self.wire([(x,y-36),(x,y-23)])
        self.parts.append(f'<rect x="{x-9}" y="{y-23}" width="18" height="46" fill="white" stroke="{INK}" stroke-width="2.2"/>')
        self.wire([(x,y+23),(x,y+36)]); self.text(x+25,y,label,18)
        if dimensions:self.text(x+25,y+24,dimensions,15)
        self.parts.append('</g>')

    def current_source(self,x,y,label):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="24" fill="white" stroke="{INK}" stroke-width="2.2"/>')
        self.wire([(x,y-36),(x,y-24)]); self.wire([(x,y+24),(x,y+36)])
        self.arrow(x,y-13,x,y+13); self.text(x+40,y+5,label,19)

    def box(self,x,y,w,h,lines,technical=False):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="#f4f8f8" stroke="{INK}" stroke-width="1.7"/>')
        for n,line in enumerate(lines):self.text(x+w/2,y+25+27*n,line,18 if technical else 19,anchor='middle')

    def save(self,name):
        ratio=min(1,960/self.width)
        # Keep final visible text >=16px, rather than shrinking large schematics.
        adjusted=[];max_y=self.height*ratio
        for part in self.parts:
            if part.startswith('<text '):
                e=ET.fromstring(part);size=float(e.attrib['font-size']);size=max(16,size*ratio)/ratio
                e.attrib['font-size']=f'{size:.4f}'
                x=float(e.attrib['x']);y=float(e.attrib['y']);anchor=e.attrib.get('text-anchor','start')
                available=(960-x*ratio-22 if anchor=='start' else min(2*x*ratio,2*(960-x*ratio))-24 if anchor=='middle' else x*ratio-6)
                lines=[];line='';units=0
                for ch in (e.text or ''):
                    u=1 if unicodedata.east_asian_width(ch)in['W','F']else .57
                    if line and (units+u)*size*ratio>available:
                        lines.append(line);line='';units=0
                    line+=ch;units+=u
                lines.append(line);e.text=None
                for n,line in enumerate(lines):
                    span=ET.SubElement(e,'tspan',{'x':str(x),'y':str(y+n*size*1.35)});span.text=line
                max_y=max(max_y,(y+len(lines)*size*1.35)*ratio+20)
                part=ET.tostring(e,encoding='unicode')
            adjusted.append(part)
        text=f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{max_y:.2f}" viewBox="0 0 {min(self.width,960)} {max_y:.2f}" role="img" aria-labelledby="title desc" data-evidence="{escape(self.classification)}">\n'
        text+=f'<title id="title">{escape(self.title)}</title><desc id="desc">{escape(self.classification)}; independent drawing; no new EDA</desc>\n'
        text+='<style>text{font-family:"Avenir Next","PingFang SC",sans-serif}path,polyline,line,rect{stroke-linejoin:round;stroke-linecap:round}</style>\n'
        text+=f'<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10" fill="{TEAL}"/></marker></defs>\n'
        text+=f'<rect width="{min(self.width,960)}" height="{max_y:.2f}" fill="white"/>\n<g transform="scale({ratio})">'+'\n'.join(adjusted)+'\n</g></svg>\n'
        (FIG/name).write_text(text)


def mirror_dc():
    d=Drawing(1120,540,'IREF 先建立 VBIAS；电流镜再控制 LED 支路','existing DC mechanism; PWM gate controls omitted')
    d.text(160,88,'VLOGIC',20,anchor='middle');d.wire([(160,97),(160,124)])
    d.current_source(160,160,'IREF = 100 µA（外部）');d.wire([(160,196),(160,260),(160,285)])
    a=d.mos(160,330,'MREF',dimensions='20 / 4 µm',body='GND')
    b=d.mos(580,330,'MOUT',dimensions='20 / 4 µm',body='GND')
    d.wire([(160,260),(85,260),(85,330),a['G']]);d.dot(160,260)
    d.wire([(160,260),(470,260),(470,330),b['G']]);d.text(315,248,'VBIAS',20,TEAL,anchor='middle')
    d.text(580,88,'VLED',20,anchor='middle');d.wire([(580,97),(580,155)])
    d.led(580,190);d.wire([(580,225),b['D']]);d.text(612,258,'LED_K',17)
    for x,dev in [(160,a),(580,b)]:d.wire([dev['S'],(x,420)]);d.ground(x,430,'GND')
    d.arrow(127,211,127,252);d.arrow(540,224,540,287)
    d.text(795,177,'两条持续电流路径',20,TEAL,bold=True)
    for n,line in enumerate(['参考：IREF → MREF → GND','输出：VLED → LED → MOUT','VBIAS 导线没有理想 DC 栅电流','1:1 只给出近似电流关系','仍需 headroom 与失配检查']):d.text(795,215+43*n,line,17)
    d.text(26,508,'DC 示意：原像素开启机制；GND 为体端连接。PWM 的 MPASS / MCLAMP 未在此重复展开。',17)
    d.save('architecture-mirror-dc.svg')


def current_control():
    d=Drawing(1230,610,'单位电流单元并联：寄存器选中多少个，输出就叠加多少份','unimplemented thermometer current-bank candidate')
    d.text(645,88,'VLED',20,anchor='middle');d.wire([(645,98),(645,113)]);d.led(645,148)
    d.wire([(645,183),(645,221),(300,221)]);d.wire([(645,221),(990,221)]);d.dot(645,221)
    d.text(705,210,'共同 LED_K',17)
    for k,x in enumerate([300,645,990],1):
        m=d.mos(x,343,'M'+str(k),dimensions='同一单位尺寸',body='GND')
        d.wire([(x,221),m['D']]);d.dot(x,221)
        d.wire([m['S'],(x,439)]);d.ground(x,449,'GND')
        # Ideal SPDT gate selector is explicit, not a manufactured MOS switch.
        c=(x-90,343);a=(x-145,316);b=(x-145,369)
        d.wire([m['G'],c]);d.dot(*c);d.dot(*a);d.dot(*b)
        d.wire([c,a if k==1 else b],TEAL)
        d.wire([a,(x-205,316)]);d.text(x-208,306,'VBIAS',16,anchor='end')
        d.wire([b,(x-172,369),(x-172,416)]);d.ground(x-172,426,'GND')
        d.text(x-93,291,'S'+str(k),18,ORANGE,anchor='middle')
        d.text(x,504,'b'+str(k)+' = '+('1' if k==1 else '0'),18,anchor='middle')
    d.text(26,546,'图中仅画 3 个单元；70 单元 / 100 µA 单位电流是待验证方案。S 为理想偏置/下拉选择器。',17)
    d.text(26,576,'同名 VBIAS 相连；每单位实际偏置开关、下拉与缓冲器尚未实现。此图不等于改变 m 参数的范围仿真。',17)
    d.save('architecture-current-control.svg')


def sense_feedback():
    d=Drawing(1110,655,'低侧反馈电流源：比较 VSET 与 ILED × RSENSE','independent unimplemented DC feedback candidate; compensation TBD')
    d.text(715,88,'VLED',20,anchor='middle');d.wire([(715,98),(715,112)]);d.led(715,147);d.wire([(715,182),(715,272)])
    m=d.mos(715,317,'MREG',body='GND')
    d.wire([m['S'],(715,395)]);d.dot(715,373);d.text(754,382,'VSENSE',18,TEAL)
    d.resistor(715,432,'RSENSE','示例 100 Ω');d.wire([(715,468),(715,510)]);d.ground(715,520,'GND')
    d.parts.append(f'<path d="M310 253 L310 383 L461 318 Z" fill="white" stroke="{INK}" stroke-width="2.2"/>')
    d.text(326,290,'+',22);d.text(326,354,'−',22);d.text(337,326,'UERR',18,TEAL)
    d.wire([(138,283),(310,283)]);d.text(60,268,'VSET = 10–700 mV',18)
    d.wire([(461,318),(535,318)]);d.parts.append(f'<rect x="535" y="309" width="50" height="18" fill="white" stroke="{INK}" stroke-width="2.2"/>')
    d.text(553,300,'RG',17,anchor='middle');d.wire([(585,318),m['G']])
    d.wire([(715,373),(938,373),(938,578),(20,578),(20,352),(310,352)])
    d.text(468,605,'VSENSE 的独立检测返回路径',17,TEAL,anchor='middle')
    d.text(45,417,'VSET − VSENSE > 0：',18);d.text(45,448,'放大器抬高 gate，电流增加',18)
    d.text(45,489,'只有负反馈保持线性时，',18);d.text(45,520,'ILED ≈ VSET / RSENSE',19,TEAL)
    d.text(26,638,'UERR 电源、补偿与关断结构待选；本图给出 DC 关系，不证明闭环稳定或高速性能。体端独立接 GND。',17)
    d.save('architecture-sense-feedback.svg')


def layers():
    d=Drawing(1230,560,'PWM 时间码与通信幅度码：数字、前置驱动和模拟输出分别承担任务','functional architecture comparison; high-speed branch unimplemented')
    d.text(285,91,'当前 PWM 研究路径',22,TEAL,anchor='middle')
    d.text(925,91,'独立高速支线（待验证）',22,TEAL,anchor='middle')
    stages=[(125,135,320,80,['duty / amplitude 寄存器','counter 与 comparator']),
            (125,263,320,64,['数字 buffer → PWM / PWM_B']),
            (125,380,320,80,['偏置开关 → 电流镜 → LED','采集电流与每帧 Q']),
            (760,135,330,80,['串行数据 / PAM / OFDM samples','寄存器、decoder / DAC']),
            (760,263,330,64,['差分 pre-driver / 电平转换']),
            (760,380,330,80,['biased tails + switch → LED','采集 settling / 光响应 / BER'])]
    for x,y,w,h,l in stages:d.box(x,y,w,h,l)
    for x in [285,925]:d.arrow(x,215,x,253);d.arrow(x,327,x,370)
    d.text(478,285,'fault / permit',18,ORANGE);d.arrow(575,295,450,295,ORANGE)
    d.text(500,415,'VBIAS / IREF',18);d.arrow(615,429,452,429)
    d.text(26,507,'控制箭头不是 LED 主电流；buffer 驱动 gate 负载，电流源管承担 LED 支路电流。',18)
    d.text(26,536,'通信数据不能直接解释成每帧亮度 PWM；bit、symbol、sample、幅度码与 duty 必须分别定义。',18)
    d.save('architecture-control-layers.svg')


def parse_devices(path):
    result={}
    for line in path.read_text().splitlines():
        t=line.split()
        if t and t[0].startswith('X'):
            count=3 if t[0]=='XRSET' else 4
            result[t[0]]={'nets':t[1:1+count],'model':t[1+count],'parameters':t[2+count:]}
    return result


def actual_reference():
    devices=parse_devices(ROOT/'analog/reference/beta_multiplier.spice')
    d=Drawing(1320,880,'实际新增 beta-multiplier reference：8 MOS + 1 PDK 电阻','actual analog/reference/beta_multiplier.spice; pre-layout schematic only')
    d.wire([(120,96),(1215,96)]);d.text(120,83,'VDD（nominal 3.3 V）',19)
    positions={'XPUP':(175,240),'XNSENSE':(175,575),'XNKICK':(350,445),'XP1':(535,240),'XN2':(535,575),'XP2':(865,240),'XN1':(865,575),'XPOUT':(1080,365)}
    pins={}
    dims={'XPUP':'P 1 / 10 µm','XNSENSE':'N 10 / 1 µm','XNKICK':'N 2 / 1 µm','XP1':'P 40 / 4 µm','XP2':'P 40 / 4 µm','XPOUT':'P 40 / 4 µm','XN1':'N 20 / 4 µm','XN2':'N 80 / 4 µm'}
    for name,(x,y) in positions.items():
        p=name.startswith('XP');pins[name]=d.mos(x,y,name,'P' if p else 'N',devices[name]['nets'],dims[name], 'VDD' if p else 'VSS')
        if p:d.wire([pins[name]['S'],(x,96)]);d.dot(x,96)
    # Core PG leg, diode-connected P1, resistor-degenerated N2.
    d.wire([pins['XP1']['D'],(535,359),pins['XN2']['D']]);d.dot(535,359)
    d.wire([(535,359),(435,359),(435,240),pins['XP1']['G']]);d.text(575,385,'PG',19,TEAL)
    for name in ['XP2','XPOUT']:
        g=pins[name]['G'];d.wire([g,(g[0]-35,g[1])]);d.text(g[0]-40,g[1]-10,'PG',17,TEAL,anchor='end')
    d.wire([pins['XP2']['D'],(865,360),pins['XN1']['D']]);d.dot(865,360)
    d.wire([(865,360),(758,360),(758,575),pins['XN1']['G']]);d.text(905,391,'NB',19,TEAL)
    d.wire([pins['XN2']['G'],(428,575)]);d.text(420,565,'NB',17,TEAL,anchor='end')
    d.wire([pins['XN2']['S'],(535,684)]);d.text(557,663,'RS',17)
    d.resistor(535,720,'XRSET','ppolyf_u  L13.5 / W2 µm',devices['XRSET']['nets'])
    d.wire([(535,756),(535,800)]);d.ground(535,810)
    d.wire([pins['XN1']['S'],(865,800)]);d.ground(865,810)
    # Startup: SU pullup, NB detection, PG kickdown. Not POR or enable.
    d.wire([pins['XPUP']['D'],(175,426),pins['XNSENSE']['D']]);d.dot(175,426)
    d.wire([(175,426),(250,426),(250,445),pins['XNKICK']['G']]);d.text(190,393,'SU',19,TEAL)
    d.wire([pins['XPUP']['G'],(65,240)]);d.text(61,230,'VSS',17,anchor='end')
    d.wire([pins['XNSENSE']['G'],(65,575)]);d.text(61,565,'NB',17,TEAL,anchor='end')
    d.wire([pins['XNSENSE']['S'],(175,800)]);d.ground(175,810)
    d.wire([pins['XNKICK']['D'],(350,359),(535,359)])
    d.wire([pins['XNKICK']['S'],(350,800)]);d.ground(350,810)
    d.wire([pins['XPOUT']['D'],(1080,620)]);d.arrow(1132,480,1132,580)
    d.text(1090,650,'IOUT → pixel BIAS',18,TEAL,anchor='middle')
    d.text(1015,700,'PMOS source 输出',17)
    d.text(1015,732,'需 VSD 余量',17)
    d.text(26,875,'同名 PG / NB / VSS 相连；XRSET 体端=VSS；START=1。自启动支路不是 POR，也不保证零静态功耗。',17)
    d.save('architecture-actual-reference.svg')


def actual_fault():
    devices=parse_devices(ROOT/'analog/safety/fault_gate.spice')
    d=Drawing(1290,1010,'实际 fault gate：OUT = raw × permit × NOT fault','actual analog/safety/fault_gate.spice; 10 pre-layout MOS')
    d.text(30,65,'fault inverter',20,TEAL,bold=True);d.text(581,70,'三输入 NAND',20,TEAL,bold=True)
    positions={'XFP':(210,218),'XFN':(210,359),'XNP0':(630,218),'XNP1':(862,218),'XNP2':(1094,218),
               'XNN0':(862,469),'XNN1':(862,609),'XNN2':(862,749),'XOP':(425,638),'XON':(425,779)}
    pins={}
    for name,(x,y)in positions.items():
        p=devices[name]['model'].startswith('pfet');params=' '.join(devices[name]['parameters'])
        wh=re.search(r'w=(\d+)u l=(\d+)u',params);dimensions=('P' if p else 'N')+wh.group(1)+'/'+wh.group(2)+'µm'
        pins[name]=d.mos(x,y,name,'P' if p else 'N',devices[name]['nets'],dimensions,'VSAFE' if p else 'VSS',dimension_dy=54 if name.startswith('XNP') else 9)
    for name in ['XFP','XNP0','XNP1','XNP2']:
        p=pins[name];d.wire([p['S'],(p['S'][0],107)]);d.text(p['S'][0],98,'VSAFE',17,anchor='middle')
    d.wire([pins['XFP']['D'],(210,294),pins['XFN']['D']]);d.text(259,302,'fault_b',18,TEAL)
    d.wire([pins['XFP']['G'],(93,218),(93,359),pins['XFN']['G']]);d.dot(93,268)
    d.wire([(93,268),(22,268)]);d.text(24,255,'fault',18,ORANGE)
    d.resistor(93,154,'RFAULT','1 MΩ（外部/testbench）');d.wire([(93,118),(93,107)]);d.text(25,98,'VSAFE',16)
    d.wire([(93,190),(93,218)]);d.wire([pins['XFN']['S'],(210,441)]);d.ground(210,451)
    for name in ['XNP0','XNP1','XNP2']:
        p=pins[name];d.wire([p['D'],(p['D'][0],370)]);d.dot(p['D'][0],370)
    d.wire([(630,370),(1094,370)]);d.text(992,398,'nand_n',19,TEAL)
    for name,label in [('XNP0','A=raw'),('XNP1','B=permit'),('XNP2','C=fault_b')]:
        g=pins[name]['G'];d.wire([g,(g[0]-30,g[1])]);d.text(g[0]-35,g[1]-42,label,16,anchor='end')
    d.wire([(862,370),pins['XNN0']['D']]);d.dot(862,370)
    d.wire([pins['XNN0']['S'],pins['XNN1']['D']]);d.text(891,541,'stack1',16)
    d.wire([pins['XNN1']['S'],pins['XNN2']['D']]);d.text(891,682,'stack2',16)
    d.wire([pins['XNN2']['S'],(862,852)]);d.ground(862,862)
    for name,label in [('XNN0','A=raw'),('XNN1','B=permit'),('XNN2','C=fault_b')]:
        g=pins[name]['G'];d.wire([g,(g[0]-80,g[1])]);d.text(g[0]-85,g[1]-10,label,17,anchor='end')
    d.text(30,549,'输出 inverter',20,TEAL,bold=True)
    d.wire([pins['XOP']['S'],(425,566)]);d.text(425,557,'VSAFE',17,anchor='middle')
    d.wire([pins['XOP']['D'],(425,708),pins['XON']['D']]);d.dot(425,708)
    d.wire([pins['XOP']['G'],(309,638),(309,779),pins['XON']['G']]);d.text(302,613,'nand_n',18,TEAL,anchor='end')
    d.wire([pins['XON']['S'],(425,852)]);d.ground(425,862)
    d.wire([(425,708),(594,708)]);d.text(594,739,'OUT',17,TEAL,anchor='end')
    d.text(30,922,'OUT → 旧 joint 模型 I pin；fault gate 不承载 LED 主电流。',17,TEAL)
    d.text(30,953,'permit 来自异步 fault-set / 条件恢复 RTL；其存储没有晶体管或版图实现。fault-high 直接关断不依赖 clock。',17)
    d.text(30,986,'VSAFE 必须是有效 3.3 V 安全电源。外部 pull-up 建立断开默认高；POR / brownout / sensor / ESD 未实现。',17)
    d.save('architecture-actual-fault.svg')


def actual_servo():
    devices=parse_devices(ROOT/'analog/reference/vset_servo.spice')
    d=Drawing(1320,1160,'实际 VSET servo：10 MOS；精密设定与 sense 电阻在外部','actual analog/reference/vset_servo.spice; pre-layout with external precision boundaries')
    positions={'XPBIAS':(175,240),'XPTAIL':(535,218),'XPD1':(535,395),'XPD2':(850,395),
               'XND1':(535,597),'XND2':(850,597),'XPLOAD':(283,763),'XNSTAGE':(283,905),
               'XPREG':(650,877),'XPOUT':(1020,877)}
    pins={}
    for name,(x,y)in positions.items():
        p=devices[name]['model'].startswith('pfet');params=' '.join(devices[name]['parameters'])
        wh=re.search(r'w=(\d+)u l=(\d+)u',params);dimensions=('P 'if p else'N ')+wh.group(1)+' / '+wh.group(2)+' µm'
        pins[name]=d.mos(x,y,name,'P'if p else'N',devices[name]['nets'],dimensions,'VDD'if p else'VSS')
    for name,top in [('XPBIAS',98),('XPTAIL',98),('XPLOAD',683),('XPREG',797),('XPOUT',797)]:
        s=pins[name]['S'];d.wire([s,(s[0],top)]);d.text(s[0],top-12,'VDD',18,anchor='middle')
    d.wire([pins['XPBIAS']['D'],(175,332),(175,368)]);d.dot(175,332)
    d.wire([(175,332),(73,332),(73,240),pins['XPBIAS']['G']]);d.text(190,358,'PB',19,TEAL)
    d.parts.append('<g data-component="RBIAS" data-nets="pb vss" data-terminal-order="P N">')
    d.resistor(175,404,'RBIAS','nominal 100 kΩ');d.parts.append('</g>')
    d.wire([(175,440),(175,475)]);d.ground(175,485)
    d.wire([pins['XPTAIL']['G'],(415,218)]);d.text(410,207,'PB',18,TEAL,anchor='end')
    d.wire([pins['XPTAIL']['D'],(535,350),(850,350)]);d.dot(535,350)
    d.wire([(535,350),pins['XPD1']['S']]);d.wire([(850,350),pins['XPD2']['S']]);d.text(700,334,'TAIL',19,TEAL,anchor='middle')
    for name,node in [('XPD1','VSET'),('XPD2','SENSE')]:
        g=pins[name]['G'];d.wire([g,(g[0]-60,g[1])])
        if name=='XPD1': d.text(g[0]-67,g[1]-13,node,18,TEAL,anchor='end')
        else: d.text(745,425,node,18,TEAL)
    d.wire([pins['XPD1']['D'],(535,493),pins['XND1']['D']]);d.dot(535,493)
    d.wire([(535,493),(418,493),(418,597),pins['XND1']['G']]);d.text(553,521,'N1',19,TEAL)
    d.wire([pins['XPD2']['D'],(850,493),pins['XND2']['D']]);d.dot(850,493);d.text(884,521,'N2',19,TEAL)
    d.wire([pins['XND2']['G'],(775,597)]);d.text(735,574,'N1',18,TEAL)
    for name in ['XND1','XND2']:
        s=pins[name]['S'];d.wire([s,(s[0],680)]);d.ground(s[0],690)
    d.wire([pins['XPLOAD']['D'],(283,833),pins['XNSTAGE']['D']]);d.dot(283,833)
    d.wire([(283,833),(159,833),(159,763),pins['XPLOAD']['G']]);d.text(313,844,'CTRL',19,TEAL)
    d.wire([pins['XNSTAGE']['G'],(127,905)]);d.text(120,891,'N2',18,TEAL,anchor='end')
    d.wire([pins['XNSTAGE']['S'],(283,1000)]);d.ground(283,1010)
    for name in ['XPREG','XPOUT']:
        g=pins[name]['G'];d.wire([g,(g[0]-55,g[1])]);d.text(g[0]-62,g[1]-13,'CTRL',18,TEAL,anchor='end')
    d.wire([pins['XPREG']['D'],(650,986)]);d.dot(650,971);d.text(675,981,'SENSE',18,TEAL)
    d.resistor(650,1022,'RSET','外部精密 5 kΩ');d.wire([(650,1058),(650,1080)]);d.ground(650,1090)
    d.wire([pins['XPOUT']['D'],(1020,1050)]);d.arrow(978,961,978,1025);d.text(940,1080,'IOUT → pixel BIAS',18,TEAL)
    d.parts.append('<g data-component="CCOMP" data-nets="n2 ctrl" data-terminal-order="P N">')
    d.wire([(553,754),(670,754)]);d.text(580,739,'N2',18,TEAL)
    d.wire([(670,734),(670,774)]);d.wire([(686,734),(686,774)]);d.wire([(686,754),(821,754)])
    d.text(755,739,'CTRL',18,TEAL);d.text(678,714,'CCOMP = 3 pF',19,anchor='middle');d.parts.append('</g>')
    d.text(26,1142,'VSET=0.5 V / RSET=5 kΩ 是外部精密边界；RBIAS 仅设 tail bias。CCOMP 按稳定性验证选择，非物理提取 C。',17)
    d.save('architecture-actual-vset-servo.svg')


def actual_led_clamp():
    devices=parse_devices(ROOT/'analog/safety/fault_led_clamp.spice')
    d=Drawing(1120,700,'实际 active LED clamp：fault-high 旁路 LED 两端','actual analog/safety/fault_led_clamp.spice; 2 pre-layout MOS plus ideal100kohm; not ESD/POR')
    d.wire([(260,102),(930,102)]);d.text(285,87,'ANODE / VLED',20,TEAL)
    d.wire([(330,102),(330,199)]);d.dot(330,102);d.led(330,234)
    d.wire([(330,269),(330,367),(810,367)]);d.text(330,402,'CATHODE / LED_K',19,TEAL,anchor='middle')
    cp=d.mos(810,234,'XCP','P',devices['XCP']['nets'],'P 2 / 1 µm','ANODE')
    d.wire([cp['S'],(810,102)]);d.dot(810,102);d.wire([cp['D'],(810,367)]);d.dot(810,367)
    d.parts.append('<g data-component="RRELEASE" data-nets="anode fault_hb" data-terminal-order="P N">')
    d.resistor(565,164,'RRELEASE','100 kΩ');d.parts.append('</g>')
    d.wire([(565,128),(565,102)]);d.dot(565,102)
    d.wire([(565,200),(565,234),cp['G']]);d.dot(565,234)
    d.text(575,265,'FAULT_HB',18,TEAL)
    ln=d.mos(565,454,'XLN0','N',devices['XLN0']['nets'],'N 2 / 1 µm','VSS')
    d.wire([(565,234),ln['D']]);d.wire([ln['S'],(565,531)]);d.ground(565,541)
    d.wire([ln['G'],(424,454)]);d.text(305,443,'fault（安全逻辑）',18,ORANGE)
    d.arrow(850,141,850,188);d.arrow(850,286,850,342)
    d.text(50,479,'fault=1：',20,ORANGE,bold=True)
    d.text(50,513,'XLN0 下拉 FAULT_HB',18)
    d.text(50,547,'XCP 导通，LED 电压降低',18)
    d.text(50,581,'fault=0：RRELEASE 释放 clamp',18)
    d.text(26,630,'XCP 的 gate 必须回到 ANODE 才能关闭；3.3 V 互补信号不能直接关闭 5 V rail 上的 PMOS。',17)
    d.text(26,660,'新 gate 10 MOS + 本图 2 MOS 均为 pre-layout；体端按图连接。A/P 为落点假设，未提取。',17)
    d.text(26,690,'fault 解除不自动恢复 PWM；RTL inhibit 保持，需 recover_request + clock + pre-edge raw=0。',17)
    d.save('architecture-actual-led-clamp.svg')


def calculations():
    path=ROOT/'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv'
    rows=list(csv.DictReader(path.open()));currents=[float(x['current_A'])for x in rows]
    points=[]
    for current in [100e-6,500e-6,1e-3,3e-3,5e-3,7e-3]:
        i=bisect.bisect_left(currents,current);a,b=rows[i-1:i+1]
        vf=float(a['voltage_V'])+(current-float(a['current_A']))*(float(b['voltage_V'])-float(a['voltage_V']))/(float(b['current_A'])-float(a['current_A']))
        points.append({'current_a':current,'vf_v':vf,'five_volt_remaining_v':5-vf,'source_excel_rows':[int(a['source_excel_row']),int(b['source_excel_row'])]})
    return [
        {'id':'CAL01','method':'Independent linear interpolation of one measured static curve','input':str(path.relative_to(ROOT)),'input_sha256':sha(path),'results':points,'conditions':'yellow20/diamond; source measurement temperature unknown; not optical/dynamic/generalization'},
        {'id':'CAL02','method':'Ideal thermometer sum, k*100uA','unit_current_a':1e-4,'unit_count_range':[1,70],'range_a':[1e-4,.007],'minimum_count_bits':7,'not_supported':'70-unit switch implementation, matching, settling and physical area'},
        {'id':'CAL03','method':'Ideal zero-based linear DAC I=7mA*D/(2^bits-1), nearest rounding','results':[{'bits':n,'lsb_a':.007/(2**n-1),'half_lsb_relative_to_100uA_pct':.5*.007/(2**n-1)/1e-4*100}for n in[8,9,10]],'not_supported':'ENOB, physical current accuracy, exact 100uA code or optical resolution'},
        {'id':'CAL04','method':'Hypothetical feedback current I=VSET/100ohm','sense_resistor_ohm':100,'set_voltage_v':[.01,.7],'current_a':[1e-4,.007],'maximum_resistor_power_w':.007**2*100,'hypothetical_offset_v':.0001,'offset_current_a':.0001/100,'offset_relative_pct':[1,.0001/100/.007*100],'not_supported':'selected op amp, loop stability, accurate off or integrated design'},
        {'id':'CAL05','method':'Candidate output mirror total W/L gain70 at L4um, Cox-area charge scale','reference_unit_w_um':20,'reference_unit_l_um':4,'gain':70,'candidate_total_output_w_um':1400,'cox_typical_ff_um2':2.3,'candidate_oxide_area_capacitance_f':2.3e-15*1400*4,'hypothetical_gate_excursion_v':1.372,'geometric_charge_scale_c':2.3e-15*1400*4*1.372,'hypothetical_10ns_average_gate_current_a':2.3e-15*1400*4*1.372/1e-8,'not_supported':'actual Cgg/Qg, layout/junction area, pass/clamp timing, PDK transistor simulation or safe 7mA operation'},
        {'id':'CAL06','method':'Ideal average rectangular branch current Iavg=Ipeak*duty/256','duty':64,'frame_slots':256,'examples_a':[25e-6,.00175],'not_supported':'real pulse-area accuracy, optical output, safe-off or communication BER'}]


def record_sources(calcs, diagram_checks):
    old=json.loads((ROOT/'docs/research/driver-literature-20261012/sources.json').read_text())
    ids={'C01','C04','C06','G03','G04','G05','H03','H05','H06'}
    records=[dict(x)for x in old['records']if x['id']in ids]
    records.append({'id':'R01','title':'Voltage-to-current (V-I) converter circuit with MOSFET (Rev. A)','authors':'Texas Instruments','year':2021,'doi':None,'url':'https://www.ti.com/lit/an/sboa327a/sboa327a.pdf','source_type':'official_application_note','access_level':'fulltext_reviewed','locator':'SBOA327A pp.1–2 Design Description/Notes/Steps; pp.3–4 Design Simulations','supports':'Low-side sensed negative feedback yields I=Vi/Rsense; input range, gate isolation and loop compensation matter','does_not_support':'Our generic feedback example is not a selected TI device, reproduced TI figure, measured ASIC or high-speed optical driver','data':[{'label':'Original note design range','value':[0,2,0,.1,20],'unit':'V,V,A,A,ohm','conditions':'Original illustrative design; not our 0.1–7mA resistor values or measurements'}],'reuse':'Link facts only; generic functional topology independently drawn','checked_on':'2026-10-13'})
    records.append({'id':'L01','title':'Data for: Transfer-printed yellow and red InGaN micro-LEDs on diamond for ultra-low-power high-speed optical interconnects','authors':'Runze Lin et al.','year':2026,'doi':'10.5281/zenodo.20034288','url':'https://zenodo.org/records/20034288','source_type':'primary_source_dataset','access_level':'data_reviewed','locator':'I-V.xlsx Sheet1 A3:B102, 20μm yellow, one curve; local normalized CSV','supports':'One static curve contains requested currents up to7mA; CAL01 replays its interpolation','does_not_support':'5V driver reaches7mA, measured dynamic C/thermal/aging/optical model, procurable LED selection or array uniformity','publication_date':'2026-05-05','record_created':'2026-06-18','license':'CC-BY-4.0','checked_on':'2026-10-13'})
    records.append({'id':'G06','title':'GF180MCU design manual: Matched Pairs','authors':'GlobalFoundries','year':None,'doi':None,'url':'https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_10_6_2.html','source_type':'official_pdk_documentation','access_level':'official_documentation','locator':'Matched Pairs MP.1–13; linked parent section Matching','supports':'Unit elements, orientation, proximity, environment, dummy edges, interleaving and symmetric interconnect guidance','does_not_support':'DRC verifies not-coded matching guidance, current project already implements common centroid/dummies, or mismatch Monte Carlo proves silicon yield','checked_on':'2026-10-13'})
    inputs=['analog/driver/pixel_driver.spice','analog/reference/beta_multiplier.spice','analog/reference/vset_servo.spice','analog/safety/fault_gate.spice','analog/safety/fault_led_clamp.spice','rtl/safety/pixel_safety.v','analog/models/measured-led/lin2026-yellow20-diamond-iv.csv','scripts/research/reference_architecture_figures.py']
    result={'schema_version':1,'date':'2026-10-13','scope':'Teaching, independently recomputed arithmetic, primary-source locators and actual netlist connectivity; no new EDA in this script','records':records,'calculations':calcs,'source_hashes':{p:sha(ROOT/p)for p in inputs},'diagram_connectivity_checks':diagram_checks,'figure_hashes':{p.name:sha(p)for p in sorted(FIG.glob('architecture-*.svg'))},'limits':['7mA candidates are not the baseline100uA design or a completed70-unit DAC','New reference/fault are pre-layout; old joint signalPEX does not upgrade their evidence','Future main-report EDA results must be read from their separately frozen run records']}
    (OUT/'sources.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


def check_actual_svg(filename,netlist):
    expected=parse_devices(ROOT/netlist);svg=ET.parse(FIG/filename)
    observed={e.attrib['data-device']:e.attrib['data-nets'].split()for e in svg.iter()if 'data-device'in e.attrib}
    assert observed=={n:r['nets']for n,r in expected.items()},(filename,observed,expected)
    if filename in ['architecture-actual-vset-servo.svg','architecture-actual-led-clamp.svg']:
        passive={e.attrib['data-component']:e.attrib['data-nets'].split()for e in svg.iter()if'data-component'in e.attrib}
        actual={t[0]:t[1:3]for l in(ROOT/netlist).read_text().splitlines()if(t:=l.split())and t[0]in['RBIAS','CCOMP','RRELEASE']}
        assert passive==actual,(passive,actual)
    return {'figure':filename,'netlist':netlist,'device_count':len(observed),'passed':True,'checks':'Exact named D/G/S/B and resistor P/N/B, including actual bulk ties; pictorial routing separately inspected'}


def main():
    FIG.mkdir(parents=True,exist_ok=True)
    mirror_dc();current_control();sense_feedback();layers();actual_reference();actual_fault();actual_servo();actual_led_clamp()
    checks=[check_actual_svg('architecture-actual-reference.svg','analog/reference/beta_multiplier.spice'),check_actual_svg('architecture-actual-fault.svg','analog/safety/fault_gate.spice'),check_actual_svg('architecture-actual-vset-servo.svg','analog/reference/vset_servo.spice'),check_actual_svg('architecture-actual-led-clamp.svg','analog/safety/fault_led_clamp.spice')]
    record_sources(calculations(),checks)
    print(json.dumps({'figures':8,'calculation_groups':6,'actual_connectivity_checks':checks},ensure_ascii=False))


if __name__=='__main__':main()
