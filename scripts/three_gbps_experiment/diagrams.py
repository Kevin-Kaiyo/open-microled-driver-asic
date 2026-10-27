#!/usr/bin/env python3
"""Source-bound VCSEL MOS drawings; original electrical schematics, not layout."""
from pathlib import Path
from html import escape
import hashlib, importlib.util, json, re
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/three-gbps-experiment-20261027/figures'
SOURCE=ROOT/'analog/circuits/vcsel_research_20261027/vcsel_bias_mod.spice'
spec=importlib.util.spec_from_file_location('primitives',ROOT/'scripts/highspeed_routes/circuits.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
INK,MUTE,TEAL,BLUE,PURPLE,LIGHT=p.INK,p.MUTE,p.TEAL,p.BLUE,p.PURPLE,p.LIGHT

class Drawing(p.Drawing):
    def text(self,x,y,s,*args,**kwargs):
        return super().text(x,y,str(s).replace('→',' > ').replace('｜',' / ').replace('Ω','ohm').replace('µ','u'),*args,**kwargs)
    def mos4(self,x,y,name):
        s=DEV[name];pm=s['model'].startswith('p')
        self.mos(x,y,name,s['nets'],pm,label=False)
        self.line([(x-10,y),(x+28,y)],INK,2)
        pts=[(x-8,y),(x+2,y-5),(x+2,y+5)] if not pm else [(x+15,y),(x+5,y-5),(x+5,y+5)]
        self.p.append('<polygon points="'+' '.join(f'{a},{b}' for a,b in pts)+f'" fill="{INK}"/>')
        self.text(x+36,y+5,'B='+s['nets'][3],15,MUTE)
        self.text(x+36,y-43,name,20,BLUE,True)
        self.text(x+36,y-20,s['model'],15,MUTE)
        self.text(x+36,y+66,'W/L '+s['w']+'/'+s['l'],16,MUTE)
    def named(self,x,y,name):
        self.mos4(x,y,name);s=DEV[name];pm=s['model'].startswith('p')
        top,bot=s['nets'][2 if pm else 0],s['nets'][0 if pm else 2]
        self.line([(x,y-52),(x,y-78)]);self.line([(x,y+52),(x,y+92)])
        self.text(x,y-94,top,19,TEAL,True,'middle');self.text(x,y+119,bot,19,TEAL,True,'middle')
        self.text(x-72,y+7,s['nets'][1],18,PURPLE,True,'end')
    def save_new(self,name):
        colors=[INK,p.ORANGE,TEAL,PURPLE,BLUE]
        defs=''.join(f'<marker id="a{c[1:]}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="{c}"/></marker>' for c in colors)
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{self.height}" viewBox="0 0 1600 {self.height}" role="img"><title>{escape(self.title)}</title><desc>逐器件绑定源网表。相同网络标签电气相连，D/G/S/B明确；原理图级，无版图和PEX结论。</desc><defs>{defs}</defs><style>text{{font-family:"PingFang SC","Noto Sans CJK SC",Arial,sans-serif}}polyline,path{{stroke-linejoin:round;stroke-linecap:round}}</style><rect width="1600" height="{self.height}" fill="white"/>'+''.join(self.p)+'</svg>\n'
        f=OUT/(name+'.svg');f.write_text(svg)
        return dict(path=str(f.relative_to(ROOT)),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),devices={n:DEV[n] for n in self.devices})

def inverter(d,x,y,n,pn):
    sn,sp=DEV[n],DEV[pn];assert sn['nets'][:2]==sp['nets'][:2]
    d.mos4(x,y,pn);d.mos4(x,y+255,n)
    d.line([(x,y-52),(x,y-85)]);d.text(x,y-100,sp['nets'][2],19,TEAL,True,'middle')
    d.line([(x,y+52),(x,y+203)]);d.dot(x,y+128)
    d.line([(x,y+128),(x+100,y+128)]);d.text(x+106,y+134,sn['nets'][0],19,TEAL,True)
    d.line([(x-62,y),(x-95,y),(x-95,y+255),(x-62,y+255)],PURPLE)
    d.dot(x-95,y+128,PURPLE);d.text(x-110,y+134,sn['nets'][1],20,PURPLE,True,'end')
    d.line([(x,y+307),(x,y+345)]);d.text(x,y+371,sn['nets'][2],19,TEAL,True,'middle')

def main():
    global DEV
    DEV={}
    for line in SOURCE.read_text().splitlines():
        a=line.split()
        if len(a)>5 and a[0].startswith('X') and a[5] in ['nmos_3p3','pmos_3p3']:
            z=dict(s.split('=',1) for s in a[6:]);DEV[a[0]]=dict(nets=a[1:5],model=a[5],w=z['w'],l=z['l'])
    assert len(DEV)==13
    OUT.mkdir(parents=True,exist_ok=True);records=[]
    d=Drawing('VCSEL｜有限参考、直流偏置与电流转向输出','5 MOS 输出/参考核心；其余 8 MOS 是下一图的两条真实 CMOS 缓冲链。同名网络相连。',1180)
    for x,y,n in [(230,380,'XREF'),(680,380,'XBASE'),(1200,380,'XTAIL'),(620,795,'XSTEER'),(1190,795,'XDUMP')]:d.named(x,y,n)
    d.resistor(230,205,'RREF1 = RREF');d.text(230,145,'VREF',20,TEAL,True,'middle')
    d.line([(230,157),(230,161)]);d.line([(230,249),(230,302)])
    d.line([(168,380),(110,380),(110,280),(230,280)]);d.dot(230,280)
    d.text(420,180,'RREF → 二极管连接 XREF → BIAS',23,BLUE,True)
    d.lines(420,210,['BIAS 同时控制 XBASE、XTAIL 的栅极。','XBASE 是 VCSEL 的基础吸流支路；XTAIL 是连续的调制尾源。','这是电阻偏置电流镜，尚非精密基准；WBASE/WTAIL/RREF 为校准参数。'],18,24)
    d.text(52,620,'输出连接：VLASER → VCSEL 电学负载与封装 R/L → OUT；VLASER → RDUMMY1 → DUMMY。',20,TEAL,True)
    d.text(52,660,'XSTEER 与 XDUMP 的源极同接 VX；VX 经 XTAIL 到 VSS。GP/GN 来自下一图。',20,TEAL)
    d.line([(620,847),(620,952),(1190,952),(1190,847)]);d.dot(900,952);d.text(900,986,'VX → VITAIL (0 V) → TS → XTAIL.D',20,TEAL,True,'middle')
    d.text(52,1030,'支路测流探针：OUT → VIBASE (0 V) → BS → XBASE.D；两个 0 V 电压源仅用于读取电流。',19,MUTE)
    d.footer(['D=1：GP 高、GN 低，OUT 的调制电流流经 XSTEER→XTAIL；D=0：调制电流经 RDUMMY1→XDUMP→XTAIL。',
              'XBASE 两态都吸流。体端全部按 B 标签连接。实际校准值、源哈希及完整供电/负载见报告和 testbench。'])
    records.append(d.save_new('vcsel-core'))
    d=Drawing('VCSEL｜两条对称的 CMOS 前置缓冲','每条两级反相器，合计 8 MOS；外部 D / DB 为互补数据，各经 50 Ω 接入。',1500)
    for y,title,prefix,inp,out in [(310,'正向数据链：D → NP → GP','P','D','GP'),(920,'反向数据链：DB → NN → GN','N','DB','GN')]:
        d.text(65,y-150,title,25,BLUE,True)
        inverter(d,360,y,'XB'+prefix+'1N','XB'+prefix+'1P')
        inverter(d,1090,y,'XB'+prefix+'2N','XB'+prefix+'2P')
        d.arrow(650,y+128,830,y+128,TEAL)
        d.text(650,y+91,'同名网络相连',19,MUTE)
    d.footer(['各级 N 管 B/S 接 VSS；P 管 B/S 接 VDD。NP/NN 为中间节点；GP/GN 分别连接 XSTEER/XDUMP 的栅极。',
              '外部互补输入产生器内部、CDR、串行器没有实现；仅计入 D/DB 输入端口供能。W/L 单位 u=µm。'])
    records.append(d.save_new('vcsel-buffers'))
    represented={n for r in records for n in r['devices']};assert represented==set(DEV)
    ev=ROOT/'evidence/three-gbps-experiment-20261027';ev.mkdir(parents=True,exist_ok=True)
    (ev/'circuit-figures.json').write_text(json.dumps(dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),mos_count=13,figures=records),ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
