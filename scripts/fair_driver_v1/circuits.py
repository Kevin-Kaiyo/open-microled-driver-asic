#!/usr/bin/env python3
"""Source-bound four-terminal MOS schematics; no EDA or circuit-source mutation.

Render: DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib build/layout/venv/bin/python
        scripts/fair_driver_v1/circuits.py
The connected net labels are authoritative, like schematic global/local labels.
"""
from pathlib import Path
from html import escape
import hashlib
import importlib.util
import json
import re
import argparse

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/fair-driver-comparison-20261025/figures'
MANIFEST=ROOT/'evidence/fair-driver-v1/circuit-figure-manifest.json'
BASE=ROOT/'scripts/highspeed_routes/circuits.py'
sp=importlib.util.spec_from_file_location('existing_circuit_primitives',BASE)
old=importlib.util.module_from_spec(sp);sp.loader.exec_module(old)
INK,MUTE,LIGHT,BLUE,TEAL,PURPLE,ORANGE=old.INK,old.MUTE,old.LIGHT,old.BLUE,old.TEAL,old.PURPLE,old.ORANGE
SOURCES={k:ROOT/f'analog/fair_driver_v1/{k}.spice' for k in ['route_a','route_b','route_c','common']}
HARNESS=ROOT/'scripts/fair_driver_v1/run.py'
RECEIVER=ROOT/'scripts/fair_driver_v1/receiver.py'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def parse(path):
    mos={};passives={};instances={}
    for line in path.read_text().splitlines():
        z=line.split()
        if not z or z[0].startswith(('*','.')):continue
        if z[0].startswith('X') and len(z)>5 and z[5] in ['nfet_03v3','nfet_06v0','pfet_06v0']:
            params=dict(p.split('=',1) for p in z[6:] if '=' in p)
            mos[z[0]]=dict(name=z[0],nets=z[1:5],model=z[5],w=params['w'],l=params['l'])
        elif z[0][0] in 'RC':passives[z[0]]=dict(name=z[0],nets=z[1:3],value=z[3])
        elif z[0].startswith('X'):instances[z[0]]=dict(name=z[0],tokens=z[1:])
    return dict(mos=mos,passives=passives,instances=instances)

DATA={k:parse(p) for k,p in SOURCES.items()}
SOURCE_HASHES={str(p.relative_to(ROOT)):sha(p) for p in SOURCES.values()}
HARNESS_HASHES={str(p.relative_to(ROOT)):sha(p) for p in [HARNESS,RECEIVER]}
CALIBRATION={
    'route_a':dict(RH_ohm=177683.3997653013,RL_ohm=87444.56014738003),
    'route_b':dict(RSET_ohm=20126.535444301146,WTAIL_m=5.76e-6,RINL_m=8e-6),
    'route_c':dict(RSET_ohm=20125.4238,WUNIT_m=2.02e-6,RINL_m=8e-6),
}
RECORDS=[]

class Drawing(old.Drawing):
    def __init__(self,title,subtitle,height,source_keys):
        self.title=title;self.height=height;self.width=1800;self.p=[];self.devices={};self.source_keys=source_keys;self.extra_source_hashes={}
        self.text(48,58,title,31,INK,True)
        self.text(48,99,subtitle,18,MUTE)
        self.line([(48,125),(1752,125)],LIGHT,1.5)

    def label(self,x,y,s,color=PURPLE,anchor='middle',size=18):
        self.text(x,y,s,size,color,True,anchor)

    def section(self,x,y,w,h,title):
        self.p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#fbfcfc" stroke="{LIGHT}" stroke-width="1.5"/>')
        self.text(x+20,y+32,title,21,BLUE,True)

    def mos4(self,x,y,source,name,display=None):
        s=DATA[source]['mos'][name];pm=s['model'].startswith('p')
        key=source+'.'+name
        assert key not in self.devices
        self.devices[key]=dict(s,terminals=dict(zip('DGSB',s['nets'])),source=str(SOURCES[source].relative_to(ROOT)),representation='four-terminal MOS with named-net connectivity')
        old.Drawing.mos(self,x,y,key,s['nets'],pm,label=False)
        # old primitive puts the name in devices; replace that record with source data.
        self.devices[key]=dict(s,terminals=dict(zip('DGSB',s['nets'])),source=str(SOURCES[source].relative_to(ROOT)),representation='four-terminal MOS with named-net connectivity')
        # Explicit fourth-terminal body line and conventional inward/outward arrow.
        self.line([(x-4,y),(x+35,y)],INK,2.3)
        points=([(x-4,y),(x+5,y-5),(x+5,y+5)] if not pm else [(x+20,y),(x+11,y-5),(x+11,y+5)])
        self.p.append('<polygon points="'+' '.join(f'{a},{b}' for a,b in points)+f'" fill="{INK}"/>')
        self.text(x+45,y+6,'B='+s['nets'][3],16,MUTE)
        self.text(x+45,y-42,display or name,19,INK,True)
        self.text(x+45,y-18,s['model'].replace('fet_',' / '),15,MUTE)
        self.text(x+45,y+57,'W/L '+s['w']+' / '+s['l'],16,MUTE)
        return s

    def named(self,x,y,source,name,display=None):
        s=self.mos4(x,y,source,name,display);pm=s['model'].startswith('p')
        top=s['nets'][2 if pm else 0];bot=s['nets'][0 if pm else 2]
        self.line([(x,y-52),(x,y-72)]);self.line([(x,y+52),(x,y+77)])
        self.label(x,y-83,top,BLUE)
        self.label(x,y+102,bot,TEAL)
        self.line([(x-62,y),(x-74,y)],PURPLE)
        self.label(x-80,y+6,s['nets'][1],PURPLE,'end',16)

    def passive(self,x,y,source,name,override_label=None):
        s=DATA[source]['passives'][name]
        if name.startswith('C'):
            self.line([(x,y-44),(x,y-8)]);self.line([(x-18,y-8),(x+18,y-8)])
            self.line([(x-18,y+8),(x+18,y+8)]);self.line([(x,y+8),(x,y+44)])
        else:
            self.resistor(x,y,'')
        self.label(x,y-62,s['nets'][0],BLUE)
        self.label(x,y+72,s['nets'][1],TEAL)
        self.text(x+30,y-5,name,17,INK,True)
        self.text(x+30,y+24,override_label or s['value'],16,MUTE)

    def footer(self,lines=()):
        y=self.height-112
        self.line([(48,y-20),(1752,y-20)],LIGHT,1.5)
        for j,t in enumerate(lines):self.text(48,y+8+j*27,t,16,MUTE)
        source='  ·  '.join(f'{k}: {sha(SOURCES[k])[:12]}' for k in self.source_keys)
        if self.extra_source_hashes:source+='  ·  '.join(f'{Path(k).name}: {v[:12]}' for k,v in self.extra_source_hashes.items())
        self.text(48,self.height-24,'源 SHA-256 前缀：'+source+'；完整哈希及逐器件覆盖见 manifest。',15,MUTE)

    def save(self,name,notes=()):
        colors=[INK,ORANGE,TEAL,PURPLE,BLUE]
        defs=''.join(f'<marker id="a{c[1:]}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="{c}"/></marker>' for c in colors)
        desc='源网表对应的原理级四端MOS原理图。同名网络电气相连，体端明确；非GDS，非PEX，不表示比较或可靠性验证完成。'
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="{self.height}" viewBox="0 0 1800 {self.height}" role="img"><title>{escape(self.title)}</title><desc>{desc}</desc><style>text{{font-family:"PingFang SC","Noto Sans CJK SC",Arial,sans-serif}}path,polyline{{stroke-linecap:round;stroke-linejoin:round}}</style><defs>{defs}</defs><rect width="1800" height="{self.height}" fill="white"/>'+''.join(self.p)+'</svg>\n'
        path=OUT/(name+'.svg');path.write_text(svg)
        rec=dict(file=str(path.relative_to(ROOT)),size=[1800,self.height],svg_sha256=sha(path),devices=self.devices,
                 source_sha256={str(SOURCES[k].relative_to(ROOT)):sha(SOURCES[k]) for k in self.source_keys}|self.extra_source_hashes,notes=list(notes))
        RECORDS.append(rec)
        return rec

def note(d,y,lines):
    for i,line in enumerate(lines):d.text(58,y+i*28,line,18,MUTE)

def inverter(d,x,y,source,n,p,title):
    sn=DATA[source]['mos'][n];sp=DATA[source]['mos'][p]
    assert sn['nets'][0:2]==sp['nets'][0:2]
    d.text(x-100,y-130,title,22,BLUE,True)
    d.mos4(x,y,source,p);d.mos4(x,y+235,source,n)
    d.line([(x,y-52),(x,y-85)]);d.label(x,y-102,sp['nets'][2],BLUE)
    d.line([(x,y+52),(x,y+183)]);d.dot(x,y+115)
    d.line([(x,y+115),(x+120,y+115)]);d.label(x+122,y+104,sn['nets'][0],TEAL,'start')
    d.line([(x,y+287),(x,y+312)]);d.label(x,y+337,sn['nets'][2],TEAL)
    d.line([(x-62,y),(x-105,y),(x-105,y+235),(x-62,y+235)],PURPLE)
    d.label(x-113,y+120,sn['nets'][1],PURPLE,'end');d.dot(x-105,y+115,PURPLE)

def draw_a_core():
    d=Drawing('路线 A｜六 MOS 输出核心与实际辅助轨接口','原理级候选；所有器件 W/L 与源网表一致。真实 VH/VL 发生器见 a-rails。',1050,['route_a'])
    inverter(d,280,330,'route_a','XN1','XP1','第一级反相器')
    inverter(d,800,330,'route_a','XN2','XP2','第二级缓冲')
    inverter(d,1320,330,'route_a','XNOUT','XPOUT','受限摆幅输出对')
    d.text(60,170,'同名网络相连；PMOS 上端为 S、下端为 D，NMOS 相反；每只体端 B 单独标明。',18,MUTE)
    d.resistor(180,790,'XRIN：D0 ↔ DI，PDK 高阻 poly 8 × 1 µm')
    d.label(180,730,'D0',PURPLE);d.label(180,865,'DI',PURPLE)
    d.box(780,735,930,150,'与辅助轨及负载的连接',[
        '独立 VLED → 片外 LED / CLED / Rpkg / Lpkg → OUT。',
        'OUT 经 XPOUT / XNOUT 向 VH / VL 注入电流；由实际 shunt 耗散。',
        'D1 未使用；DISABLE 尚未实现，不能据接口名称声称启动保护。'],size=18)
    d.footer(['同名网络是电气连接标签；XRIN 的第三端接 VSS。此图只展开 6 MOS，另外 14 MOS 在 a-rails。',
              '结面积/周长为共同原理级估计，不是实际布局提取；正常通信与启动诊断分别报告。'])
    d.save('a-core')

def draw_a_rails():
    d=Drawing('路线 A｜两套独立的真实吸流辅助轨','每轨 5 MOS OTA + PMOS/R 偏置 + NMOS shunt = 7 MOS；两轨全部 14 MOS 在此展开。',1900,['route_a'])
    groups=[('H',48,'VH 高辅助轨'),('L',920,'VL 低辅助轨')]
    for pre,x,title in groups:
        d.section(x,155,832,1100,title+'：同名网络相连')
        names=[f'X{pre}PBIAS',f'X{pre}PTAIL',f'X{pre}P1',f'X{pre}P2',f'X{pre}N1',f'X{pre}N2',f'X{pre}SHUNT']
        for j,n in enumerate(names):d.named(x+150+(j%2)*395,310+(j//2)*255,'route_a',n)
        d.lines(x+440,1080,['轨电压上升','→ OTA 输出 gate 上升','→ NMOS shunt 吸流增加'],17,29,TEAL)
        # Real passive terminals are explicitly paired, including ESR/cap midpoint.
        pn=[f'R{pre}_TOP',f'R{pre}_BOTTOM',f'R{pre}BIAS',f'R{pre}FEED',f'R{pre}ESR',f'C{pre}_EXT']
        for j,n in enumerate(pn):
            xx=x+90+(j%3)*270;yy=1380+(j//3)*220
            val={'RH_BOTTOM':'RH = 177.6834 kΩ','RL_BOTTOM':'RL = 87.44456 kΩ'}.get(n)
            d.passive(xx,yy,'route_a',n,val)
    d.footer(['以上 R/C 在此候选中明确作为片外元件；每轨 10 nF + 0.2 Ω ESR，VIN 经 100 kΩ feed 供电。',
              'LED 注入轨的电流由 shunt 耗散，不假设回收；源默认 RH/RL 为 180k/88k，图示为 TT 单次校准值。'])
    d.save('a-rails')

def draw_reference():
    d=Drawing('公共参考｜12 MOS 电压—电流反馈与受控禁止','B、C 共用 nrz_vi_reference；IOUT 在上层接 BIAS。所有 12 MOS 逐只展开，不是行为源。',1210,['common'])
    names=list(DATA['common']['mos'])
    for j,n in enumerate(names):d.named(190+(j%4)*430,285+(j//4)*275,'common',n)
    note(d,1035,['IN2 经上层 RCOMP / 150 pF 到 VSS；IPB 经 100 kΩ 到 VSS；SENSE 经 RSET 到 VSS。',
                 'XDIS 钳 IOUT；XKEEP 控制 KRET 泄放路径。DISABLE 为外部控制，不是自主 POR。'])
    d.footer(['每只 MOS 的 D/G/S/B 均以端子及同名网络确定；所有器件为 06v0，尺寸单位按 u=µm。'])
    d.save('common-reference')

def draw_b():
    d=Drawing('路线 B｜9 MOS NRZ 电流转向核心与参考连接','12 MOS 公共参考另图完整展开；本图 9 MOS + 公共 12 MOS = 21 MOS。',1610,['route_b','common'])
    inverter(d,220,350,'route_b','XINV1N','XINV1P','第一反相器')
    inverter(d,720,350,'route_b','XINV2N','XINV2P','第二反相器')
    for x,y,n in [(1200,315,'XLED'),(1570,315,'XDUMMY'),(1400,650,'XTAIL'),(250,920,'XREF'),(700,920,'XBASE')]:d.named(x,y,'route_b',n)
    d.text(1050,825,'OUT → XLED / DUMMY → XDUMMY',20,TEAL,True)
    d.text(1050,856,'两支源端同接 VX → XTAIL → VSS',20,TEAL,True)
    d.box(1010,895,720,165,'XVI 公共参考接口（12 MOS 另图）',[
        'VIN VSS VSET SENSE BIAS IPB IN2 ICTRL DISABLE KRET',
        'IOUT → BIAS；RSET = 20.12654 kΩ；WTAIL = 5.76 µm。',
        'RIN：D0 ↔ DI，体端 VSS，1 µm × RINL（默认 8 µm）。'],size=17)
    names=list(DATA['route_b']['passives'])
    for j,n in enumerate(names):d.passive(100+(j%8)*214,1220+(j//8)*170,'route_b',n,'20.12654 kΩ' if n=='RSET1' else None)
    d.footer(['每只 MOS 显式标体端；同名节点相连。RDUMMY 接 VIN，RKEEP 在 OUT 与 KRET 之间。',
              'RTOP/RBOT/RSET/RBIAS、RCOMP/CCOMP/RKEEP/RDUMMY 为片外 R/C 范围；不声称新 GDS 或 PEX。'])
    d.save('b-core')

def draw_c_overview():
    d=Drawing('路线 C｜49 MOS 的分层展开与实际单元映射','本图展开 REF/BASE；译码器 14 MOS、单位单元 7 MOS、公共参考 12 MOS 分别有完整器件图。',1320,['route_c','common'])
    d.named(200,310,'route_c','XREF');d.named(650,310,'route_c','XBASE')
    d.box(980,180,740,245,'器件账本：12 + 2 + 14 + 3 × 7 = 49 MOS',[
        '12：common-reference（真实 V-to-I + 2 MOS 禁止/keeper）',
        '2：本图 XREF、XBASE（基础电流）',
        '14：c-decoder（真实静态 CMOS，非理想逻辑源）',
        '21：c-unit 的 7 MOS 单元重复三次（下表逐项对应）',
        '另有 3 个 PDK RIN；不计作 MOS。'],size=17)
    d.text(70,490,'实际输入与内部网络映射（同名 OUT / BIAS / VIN / VDD / VSS 为公共网络）',21,BLUE,True)
    rows=[['单元','输入 → RIN → DI','缓冲管实例','转向/尾管','内部节点'],
          ['1','T1 → XRIN1 → DI1','XBUF1N/P；XBUF2N/P','XLED1 / XDUMMY1 / XTAIL1','GB1 GP1 VX1 DUMMY1'],
          ['2','D1 → XRIN2 → DI2','XBUF3N/P；XBUF4N/P','XLED2 / XDUMMY2 / XTAIL2','GB2 GP2 VX2 DUMMY2'],
          ['3','T3 → XRIN3 → DI3','XBUF5N/P；XBUF6N/P','XLED3 / XDUMMY3 / XTAIL3','GB3 GP3 VX3 DUMMY3']]
    xs=[70,190,580,1020,1430]
    for i,row in enumerate(rows):
        for x,s in zip(xs,row):d.text(x,540+i*43,s,17,BLUE if i==0 else INK,i==0)
    d.text(70,745,'校准实例参数：RSET = 20125.4238 Ω；WUNIT = 2.02 µm；源默认值未被图修改。',20,TEAL,True)
    d.text(70,781,'Gray 输入 D1D0：00 / 01 / 11 / 10 → 0 / 1 / 2 / 3 个开启单元；这是码映射，不保证实测电平。',18,MUTE)
    names=list(DATA['route_c']['passives'])[:7]
    for j,n in enumerate(names):d.passive(110+j*235,920,'route_c',n)
    d.box(50,1050,1700,105,'公共参考层级接口',[
        'XREFMOD：VIN VSS VSET SENSE BIAS IPB IN2 ICTRL DISABLE KRET；参考 IOUT 映射到 BIAS。',
        'RSET、分压、补偿、keeper、dummy 为片外元件；真实上游电源端口共同计能，未含 RX / ADC / DSP。'],size=18)
    d.footer(['完整 49 MOS 的表示由四张 C/common 图共同组成；单独本页不是完整晶体管电路。',
              'C 的 netlist 是新原理级候选，不继承历史 B 的 actual-GDS / PEX 资格；所有结几何为共同估计。'])
    d.save('c-overview')

def draw_decoder():
    d=Drawing('路线 C｜14 MOS 静态 CMOS Gray→温度计译码器','所有 D/G/S/B 逐只展开；网络标签表示真实连接。T2 直接使用 D1，不增加理想功能源。',1540,['route_c'])
    groups=[('NB0 = ¬D0：2 MOS',['XD0P','XD0N']),
            ('T1 = D1 ∨ D0：NOR2 → INV，6 MOS',['XORPA','XORPB','XORNA','XORNB','XORTP','XORTN']),
            ('T3 = D1 ∧ NB0：NAND2 → INV，6 MOS',['XANDPA','XANDPB','XANDNA','XANDNB','XANDTP','XANDTN'])]
    # The inverter is a fully wired pair; the two six-device gates use explicit net labels.
    inverter(d,230,370,'route_c','XD0N','XD0P','NB0 = ¬D0')
    for title,names,x in [(groups[1][0],groups[1][1],590),(groups[2][0],groups[2][1],1200)]:
        d.text(x-20,180,title,19,BLUE,True)
        for j,n in enumerate(names):d.named(x+90+(j%2)*300,310+(j//2)*280,'route_c',n)
    d.box(60,850,460,230,'实际串/并接法',[
        'NOR：PMOS 经 P_OR 串联；NMOS 并联。',
        'NAND：NMOS 经 N_STACK 串联；PMOS 并联。',
        '所有 PMOS 体端接 VDD；NMOS 接 VSS。',
        'N_OR、N_AND 为实际内部节点。'],size=16)
    rows=[['D1D0','NB0','T1','T2 = D1','T3','开启单元数'],['00','1','0','0','0','0'],['01','0','1','0','0','1'],['11','0','1','1','0','2'],['10','1','1','1','1','3']]
    for i,row in enumerate(rows):
        for x,s in zip([150,430,690,940,1250,1490],row):d.text(x,1160+i*40,s,20,BLUE if i==0 else INK,i==0)
    d.footer(['T1 / D1 / T3 分别接三单元的 XRIN1 / XRIN2 / XRIN3；图中无行为电压源或理想逻辑门。'])
    d.save('c-decoder')

def draw_unit():
    d=Drawing('路线 C｜七 MOS 标准电流转向单元（单元 1 的完整展开）','此七管结构实际重复三次；所有实例、局部网络映射见 c-overview 与 manifest。',1250,['route_c'])
    inverter(d,220,350,'route_c','XBUF1N','XBUF1P','输入缓冲第一级')
    inverter(d,720,350,'route_c','XBUF2N','XBUF2P','输入缓冲第二级')
    for x,y,n in [(1200,300,'XLED1'),(1570,300,'XDUMMY1'),(1380,650,'XTAIL1')]:d.named(x,y,'route_c',n)
    d.passive(1180,930,'route_c','RDUMMY1')
    d.resistor(190,890,'XRIN1：T1 ↔ DI1')
    d.label(190,823,'T1',PURPLE);d.label(190,964,'DI1',PURPLE)
    d.lines(500,825,['XRIN：PDK 高阻 poly，1 µm × RINL。','XTAIL 的 W = WUNIT，L = 1 µm；','三只 WUNIT 均用同一校准值 2.02 µm。','OUT / BIAS 为三个单元共有网络。'],19,35)
    d.text(1070,1050,'VIN → RDUMMY1 → DUMMY1 → XDUMMY1 → VX1',17,TEAL)
    d.text(1070,1080,'OUT → XLED1 → VX1 → XTAIL1 → VSS',17,TEAL)
    d.footer(['共 7 MOS：4 缓冲 + 2 转向 + 1 尾管；另外的公共 XREF / XBASE 在 c-overview。',
              'RDUMMY1/2/3 各为 150 kΩ；单元 2 输入 D1，单元 3 输入 T3；不能把本图误作仅 7 MOS 的 C。'])
    d.save('c-unit')

def draw_testbench():
    d=Drawing('共同测试台｜七路源端口、真实连接与计算接收边界',
              '正常通信从已建立 OP 开始；本图为共同标称连接，角落 VDD 与扰动参数按各冻结 case。',2100,[])
    d.extra_source_hashes=HARNESS_HASHES
    d.p.append(f'<rect x="48" y="160" width="1704" height="1480" rx="16" fill="#fdfefe" stroke="{TEAL}" stroke-width="2" stroke-dasharray="10 7"/>')
    d.text(70,194,'TX 输入端口计能范围：VIN、VDD、VREF、VLED、VD0、VD1、VDISABLE（七路）',21,TEAL,True)

    def source(x,y,name,value):
        d.p.append(f'<circle cx="{x}" cy="{y}" r="29" fill="white" stroke="{BLUE}" stroke-width="2.7"/>')
        d.line([(x,y-50),(x,y-29)],BLUE);d.line([(x,y+29),(x,y+52)],BLUE)
        d.text(x,y-4,'+',20,BLUE,False,'middle');d.text(x,y+19,'−',20,BLUE,False,'middle')
        d.ground(x,y+52);d.text(x+43,y-4,name,19,BLUE,True);d.text(x+43,y+25,value,17,MUTE)
        return (x,y-50)

    def hres(x,y,name,value):
        d.line([(x-60,y),(x-35,y)]);d.line([(x+35,y),(x+60,y)])
        d.p.append(f'<rect x="{x-35}" y="{y-12}" width="70" height="24" fill="white" stroke="{INK}" stroke-width="2.7"/>')
        d.text(x,y-29,name,17,INK,True,'middle');d.text(x,y+41,value,17,MUTE,False,'middle')

    def hind(x,y,name,value):
        d.line([(x-60,y),(x-40,y)]);d.line([(x+40,y),(x+60,y)])
        path=f'M{x-40},{y} '+''.join('a10,14 0 0 1 20,0 ' for _ in range(4))
        d.p.append(f'<path d="{path}" fill="none" stroke="{INK}" stroke-width="2.7"/>')
        d.text(x,y-29,name,17,INK,True,'middle');d.text(x,y+41,value,17,MUTE,False,'middle')

    def cap(x,y,name,value):
        d.line([(x,y-44),(x,y-8)]);d.line([(x-22,y-8),(x+22,y-8)])
        d.line([(x-22,y+8),(x+22,y+8)]);d.line([(x,y+8),(x,y+44)])
        d.text(x+32,y-8,name,18,INK,True);d.text(x+32,y+23,value,17,MUTE)

    for name,y,value,rval,lval in [('VIN',290,'5 V','0.25 Ω','0.5 nH'),('VDD',640,'随 corner','1 Ω','2 nH')]:
        x,top=source(150,y,name,value)
        d.line([(x,top),(290,top)]);hres(350,top,'R'+name,rval)
        d.line([(410,top),(450,top)]);hind(510,top,'L'+name,lval)
        d.line([(570,top),(720,top)]);d.dot(650,top);d.label(720,top-15,name,BLUE)
        d.line([(650,top),(650,top+36)]);d.resistor(650,top+80,'RC'+name+' 0.2 Ω')
        d.line([(650,top+124),(650,top+146)]);cap(650,top+190,'C'+name,'100 nF')
        d.line([(650,top+234),(650,top+248)]);d.ground(650,top+248)
        d.text(605,top+287,'VSS = 0',16,MUTE)
    x,top=source(150,990,'VREF','2.5 V');d.line([(x,top),(290,top)]);hres(350,top,'RREF','0.2 Ω')
    d.line([(410,top),(720,top)]);d.label(720,top-15,'VREF',BLUE)
    d.text(80,1110,'VIN：只供辅助轨 / 参考 / dummy。',19,TEAL,True)
    d.text(80,1143,'VDD：TT 3.3 V；SS 2.95 V；FF 3.65 V。',18,MUTE)
    d.text(80,1176,'上述供电元件位于 XDRV 之外，不属于片内 PEX。',18,MUTE)

    # The LED's DC conduction branch and CLED displacement branch are parallel.
    x,top=source(1110,290,'VLED','独立 5 V');d.line([(x,top),(1320,top)])
    hres(1380,top,'RLEDSRC','0.25 Ω');d.line([(1440,top),(1630,top),(1630,390),(1270,390)])
    d.dot(1630,390);d.label(1630,365,'led_a',BLUE)
    d.line([(1270,390),(1270,438)]);d.led(1270,480);d.text(1350,475,'XLED：公开静态 I–V 模型',18,ORANGE,True)
    d.line([(1270,522),(1270,555)]);d.label(1238,547,'led_dc_k',ORANGE,'end',16)
    d.p.append(f'<circle cx="1270" cy="584" r="29" fill="white" stroke="{INK}" stroke-width="2.7"/>')
    d.text(1270,579,'+',19,INK,False,'middle');d.text(1270,601,'−',19,INK,False,'middle')
    d.text(1320,584,'VSENSE = 0 V',18,INK,True);d.text(1320,614,'仅测导电电流 i(VSENSE)',16,MUTE)
    d.line([(1270,613),(1270,700),(1630,700)])
    d.line([(1630,390),(1630,506)]);cap(1630,550,'CLED','200 fF');d.line([(1630,594),(1630,700)])
    d.dot(1450,700);d.label(1490,729,'led_k',TEAL)
    d.line([(1450,700),(1450,756)]);d.resistor(1450,800,'RPKG 1 Ω')
    d.line([(1450,844),(1450,875)])
    d.p.append(f'<path d="M1450,875 '+''.join('a14,10 0 0 1 0,20 ' for _ in range(4))+f'" fill="none" stroke="{INK}" stroke-width="2.7"/>')
    d.text(1490,920,'LPKG 0.5 nH',18,INK,True);d.line([(1450,955),(1450,1000)])
    d.label(1495,991,'OUT',TEAL)
    d.box(990,1000,720,215,'XDRV：fair_a / fair_b / fair_c（逐 MOS 另图）',[
        'OUT、VIN、VDD、VREF、D0、D1、VSS、DISABLE',
        '同名网络相连；VSS 在此标称图接电路 0。',
        'B / C 禁止由外部控制；A 的 DISABLE 未实现。',
        '本页不把供电电压源的内部损耗计作已实现。'],size=18)

    for i,x in [(0,150),(1,700)]:
        _,top=source(x,1395,'VD'+str(i),'0 ↔ VDD；20 ps 边沿')
        d.line([(x,top),(x+120,top)]);hres(x+180,top,'RD'+str(i),'100 Ω')
        d.line([(x+240,top),(x+340,top)]);d.label(x+340,top-16,'D'+str(i),PURPLE)
    x,top=source(1250,1395,'VDISABLE','正常通信 0 V')
    d.line([(x,top),(1660,top)]);d.label(1660,top-16,'DISABLE',PURPLE)
    d.text(80,1520,'计能在七个源端口进行：分别积分正向取能、返回能量与净能量；VSENSE 是 0 V 测量支路，不是第八路供电。',18,TEAL)
    d.text(80,1555,'包含图示供电 R/L、去耦、LED、XDRV 及 DATA 端口；不包含上游电源 IC 内部损耗、实体 RX 或主机/时钟电路。',18,MUTE)
    d.text(80,1590,'D0/D1 在 NRZ / PAM4 中按各自符号率生成；0/1 是电平命令，不代表理想光输出。',18,MUTE)

    d.box(48,1700,1704,205,'计算接收代理（不在实体 TX 原理图或所报七源能耗范围内）',[
        'i(VSENSE) → 200 ps 光学等效一阶模型 → 1 GHz RX 一阶模型 → 训练 / 阈值 / 采样判决。',
        '这是以等效电流表示的计算链，不是已实现的光路、TIA、ADC 或 DSP，也不是测得光功率。',
        'MOS：公开 GF180 PDK 晶体管级原理图，结几何共同估计；没有本阶段 GDS / PEX。',
        'LED：公开静态 I–V 拟合；200 fF 与光学/RX 动态是另行声明的假设，不是实测动态或温度模型。'],size=19)
    d.footer(['此图逐项对应共同 harness 的默认网络；额外供电/地扰动或参数覆盖以相应冻结 case 的实际网表为准。'])
    d.save('common-testbench',notes=['Seven-source port boundary; VSENSE is measurement only; RX is a computational proxy.'])

def coverage():
    visible={k:r['file'] for r in RECORDS for k in r['devices']}
    expanded={}
    for route in ['route_a','route_b','route_c']:
        items=[]
        for name,s in DATA[route]['mos'].items():
            key=route+'.'+name;template=key
            if route=='route_c' and key not in visible:
                # Each real unit's seven MOS maps to its corresponding unit-1 symbol.
                matches=re.match(r'X(TAIL|LED|DUMMY)([23])$',name)
                if matches:template='route_c.X'+matches[1]+'1'
                matches=re.match(r'XBUF([3-6])([NP])$',name)
                if matches:template='route_c.XBUF'+str(1 if int(matches[1])%2 else 2)+matches[2]
            assert template in visible,(key,template)
            mapping={}
            if template!=key:
                unit=int(re.search(r'([23])$',name).group(1)) if not name.startswith('XBUF') else (int(re.search(r'XBUF([3-6])',name).group(1))+1)//2
                mapping={n+'1':n+str(unit) for n in ['DI','GB','GP','VX','DUMMY']}
                original=DATA['route_c']['mos'][template.split('.')[1]]
                assert [mapping.get(n,n) for n in original['nets']]==s['nets']
                assert all(original[k]==s[k] for k in ['model','w','l'])
            items.append(dict(instance=name,source_device=s,figure=visible[template],symbol=template,
                              represented_by_repeated_template=template!=key,template_net_mapping=mapping))
        if route in ['route_b','route_c']:
            prefix='XVI' if route=='route_b' else 'XREFMOD'
            for name,s in DATA['common']['mos'].items():
                mapped=dict(s,nets=['BIAS' if n=='IOUT' else n for n in s['nets']])
                items.append(dict(instance=prefix+'.'+name,source_device=mapped,figure=visible['common.'+name],symbol='common.'+name,represented_by_shared_reference=True))
        expected={'route_a':20,'route_b':21,'route_c':49}[route]
        assert len(items)==expected
        assert len({x['instance'] for x in items})==expected
        expanded[route]=dict(mos_count=expected,all_mos_represented=True,instances=items)
    return expanded

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--no-raster',action='store_true')
    ap.add_argument('--visual-reviewed',action='store_true',help='Only set after inspecting every generated PNG.')
    args=ap.parse_args()
    harness=HARNESS.read_text()
    for token in ["('VIN','vin',.25,.5e-9,100e-9)","('VDD','vdd',1.,2e-9,100e-9)",
                  'RREF vref_src vref .2','RLEDSRC led_src led_a .25','VDISABLE disable 0 0',
                  'RD{i} data{i}_src d{i} 100','XLED led_a led_dc_k lin2026_yellow20_dc',
                  'VSENSE led_dc_k led_k 0','RPKG led_k pk 1','LPKG pk out .5n',
                  "case.get('led_cap_F',200e-15)",'pwl(d0,sym_ui,vdd,20e-12)']:
        assert token in harness,'testbench drawing contract changed: '+token
    OUT.mkdir(parents=True,exist_ok=True)
    for fn in [draw_a_core,draw_a_rails,draw_b,draw_reference,draw_c_overview,draw_decoder,draw_unit,draw_testbench]:fn()
    cov=coverage()
    if not args.no_raster:
        import cairosvg
        for r in RECORDS:
            p=ROOT/r['file'];source=p.read_text().replace('"PingFang SC","Noto Sans CJK SC",Arial,sans-serif','"Arial Unicode MS"')
            png=p.with_suffix('.png');cairosvg.svg2png(bytestring=source.encode(),write_to=str(png))
            r['png']=str(png.relative_to(ROOT));r['png_sha256']=sha(png)
    assert SOURCE_HASHES=={str(p.relative_to(ROOT)):sha(p) for p in SOURCES.values()},'electrical source changed while rendering'
    assert HARNESS_HASHES=={str(p.relative_to(ROOT)):sha(p) for p in [HARNESS,RECEIVER]},'harness changed while rendering'
    payload=dict(schema=1,status='source-bound schematic figures; not layout/PEX or comparison qualification',terminal_order=['D','G','S','B'],
                 sources=SOURCE_HASHES,generator_sha256=sha(Path(__file__)),
                 reused_primitives=dict(path=str(BASE.relative_to(ROOT)),sha256=sha(BASE)),
                 font=dict(svg='PingFang SC / Noto Sans CJK SC / Arial',png='Arial Unicode MS'),
                 figures=RECORDS,coverage=cov,calibrated_instance_parameters=CALIBRATION,
                 calibration_scope='One TT calibration from parent harness; no per-PVT tuning; source defaults remain unchanged.',
                 repetitions={'c-unit':dict(template_mos_count=7,repeat_count=3,expanded_mos_count=21),
                              'common-reference':dict(template_mos_count=12,instances_per_route={'route_b':1,'route_c':1})},
                 passive_inventory={k:dict(basic_R_C=v['passives'],other_subcircuits=v['instances']) for k,v in DATA.items()},
                 common_testbench=dict(source_sha256=HARNESS_HASHES,
                    input_sources=['VIN','VDD','VREF','VLED','VD0','VD1','VDISABLE'],
                    measurement_source='VSENSE 0V between led_dc_k and led_k; excluded from seven-input count',
                    LED_supply='VLED led_src 0 5; RLEDSRC led_src led_a 0.25; independent of VIN',
                    receiver='Computational equivalent-current proxy, no physical RX power claim'),
                 visual_review_status='passed' if args.visual_reviewed else 'pending',
                 checks=dict(all_route_mos_represented=True,all_mos_have_D_G_S_B=True,
                             source_parameters_unmodified=True,route_c_unit_repeat_count=3,
                             route_c_static_cmos_decoder_count=14,common_reference_count=12))
    MANIFEST.parent.mkdir(parents=True,exist_ok=True);MANIFEST.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(figures=len(RECORDS),mos_counts={k:v['mos_count'] for k,v in cov.items()},manifest=str(MANIFEST.relative_to(ROOT))),ensure_ascii=False))

if __name__=='__main__':main()
