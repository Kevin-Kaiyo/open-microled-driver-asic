#!/usr/bin/env python3
"""Actual route-A prototype schematic. Netlist is authoritative, not this SVG."""
from pathlib import Path
import importlib.util, json

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('route_drawing',ROOT/'scripts/highspeed_routes/circuits.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
OUT=ROOT/'docs/research/highspeed-nrz-20261019/figures';OUT.mkdir(parents=True,exist_ok=True)
m.OUT=OUT
d=m.Drawing('单通道 NRZ：受限输出摆幅电压驱动', '晶体管级原理图，GF180MCU 3.3 V MOS，TT，27 C；6 只 MOS 包括前置驱动器，非旧版像素电路',1250)

def inverter(x, name, gate, result, nw,pw,upper='vdd',lower='0'):
    d.mos(x,320,'XP'+name,[result,gate,upper,upper],True,m.BLUE)
    d.mos(x,660,'XN'+name,[result,gate,lower,'0'],False,m.ORANGE)
    d.line([(x,215),(x,268)],m.BLUE)
    d.line([(x,372),(x,608)])
    d.dot(x,500)
    d.line([(x,712),(x,770)],m.ORANGE)
    d.lines(x+35,350,[f'W/L={pw}/0.28 um',f'B = {"VH" if upper=="vh" else "VDD"}'],16,24,m.MUTE)
    d.lines(x+35,690,[f'W/L={nw}/0.28 um','B = VSS'],16,24,m.MUTE)
    if upper=='vdd':d.text(x,193,'VDD = 3.3 V',21,m.BLUE,True,'middle')
    if lower=='0':
        d.ground(x,770);d.text(x+28,785,'VSS = 0',17,m.MUTE)
    bus=x-140
    d.line([(bus,320),(x-62,320)],m.PURPLE)
    d.line([(bus,320),(bus,660),(x-62,660)],m.PURPLE)
    d.dot(bus,500,m.PURPLE)
    return bus

bus1=inverter(310,'1','data','n1',1,2)
bus2=inverter(635,'2','n1','ctrl',4,8)
bus3=inverter(975,'OUT','ctrl','out',4,8,'vh','vl')
d.line([(50,500),(bus1,500)],m.PURPLE)
d.text(49,465,'DATA',22,m.PURPLE,True)
d.text(49,536,'0 / 3.3 V',17,m.PURPLE)
d.text(49,562,'输入边沿 20 ps',16,m.MUTE)
d.line([(310,500),(bus2,500)],m.PURPLE)
d.text(342,478,'n1 = NOT(DATA)',16,m.PURPLE)
d.line([(635,500),(bus3,500)],m.PURPLE)
d.text(682,472,'CTRL = DATA',18,m.PURPLE,True)
d.text(682,534,'0 / 3.3 V',18,m.PURPLE)
d.text(975,181,'VH = 1.611025 V',21,m.BLUE,True,'middle')
d.arrow(938,220,938,262,m.BLUE);d.arrow(1012,262,1012,220,m.BLUE)
d.text(975,814,'VL = 1.172154 V',21,m.BLUE,True,'middle')
d.text(975,843,'两条电源轨须能吸收回流',17,m.BLUE,False,'middle')
d.arrow(938,730,938,765,m.BLUE)

# The 0-V VMON probe is in the static LED branch only. CLED bypasses it.
x=1370
d.text(x,181,'VLED = 5 V',21,m.ORANGE,True,'middle')
d.line([(x,194),(x,219)],m.ORANGE)
d.dot(x,203,m.ORANGE)
d.p.append(f'<circle cx="{x}" cy="240" r="21" fill="white" stroke="{m.ORANGE}" stroke-width="2.6"/>')
d.text(x,246,'0 V',14,m.ORANGE,False,'middle')
d.text(1190,239,'VMON：测 ILED',17,m.ORANGE)
d.line([(x,261),(x,278)],m.ORANGE)
d.led(x,320)
d.text(1185,309,'MicroLED',19,m.ORANGE,True)
d.text(1185,338,'实测静态 I–V 模型',17,m.MUTE)
d.line([(x,362),(x,376)],m.ORANGE)
d.dot(x,370,m.ORANGE)
d.resistor(x,420,'Rpkg = 1 ohm',m.ORANGE)
d.line([(x,464),(x,470)],m.ORANGE)
d.p.append(f'<path d="M{x},470 c18,0 18,8 0,8 c18,0 18,8 0,8 c18,0 18,8 0,8 c18,0 18,8 0,8" fill="none" stroke="{m.ORANGE}" stroke-width="2.7"/>')
d.text(x+28,491,'Lpkg = 0.5 nH',17,m.ORANGE)
d.line([(x,502),(x,540),(975,540)],m.ORANGE)
d.dot(975,540,m.ORANGE)
d.text(1115,575,'OUT（ASIC 端）',19,m.ORANGE,True)
d.text(1190,398,'LED_K',16,m.ORANGE)
d.line([(x,203),(1495,203),(1495,274)],m.ORANGE)
d.line([(1477,274),(1513,274)],m.ORANGE)
d.line([(1477,292),(1513,292)],m.ORANGE)
d.line([(1495,292),(1495,370),(x,370)],m.ORANGE)
d.text(1516,322,'CLED',17,m.ORANGE)
d.text(1516,347,'200 fF',17,m.ORANGE)
d.text(1170,620,'CLED、Rpkg、Lpkg 均为假设，非实测或 PEX。',17,m.MUTE)
d.arrow(1328,278,1328,353,m.ORANGE)
d.arrow(943,462,943,389,m.BLUE)
d.text(1025,435,'DATA = 0',18,m.BLUE,True)
d.text(1025,465,'LED -> XPOUT -> VH',16,m.BLUE)
d.arrow(943,551,943,600,m.ORANGE)
d.text(1180,680,'DATA = 1',18,m.ORANGE,True)
d.text(1180,710,'LED -> XNOUT -> VL',16,m.ORANGE)

d.box(48,892,730,192,'DC 校准：同一负载，设定两档电流',[
 'DATA = 0：OUT = 1.638636 V，ILED = 25.000 uA；',
 'DATA = 1：OUT = 1.231990 V，ILED = 100.000 uA。',
 '输出摆幅约 0.407 V；栅极仍由 0 / 3.3 V 全摆幅控制。',
 'NMOS 体端接 VSS；PMOS 体端分别接自身上电源轨。'],m.TEAL,size=18)
d.box(802,892,750,192,'能耗与可靠性的边界',[
 '统计 VLED、VDD、VH、VL：分别记录供能与吸收的能量。',
 '理想电源可吸收电流；实际稳压器及其损耗尚未实现。',
 '前置驱动节点有瞬态过冲：继续检查各管 VGS / VGD / VDS。',
 'AD/AS/PD/PS 已非零；为几何估计，尚无实际版图寄生。'],m.BLUE,size=18)
d.footer(['D/G/S 已在器件旁标注；B 连接写在各管尺寸下方。um 为微米，uA 为微安；体二极管未单独画出，PDK 模型中包含体结。',
 '此图对应 voltage_driver.spice 的晶体管级预版图仿真；不代表 DRC/LVS/PEX、光学带宽或误码率已验证。'])
d.save('voltage-schematic')
p=OUT/'voltage-schematic.svg'
s=p.read_text().replace('原创教学示意。候选架构，未经高速晶体管或版图仿真。器件端子和电流方向有明确标注。','原创原理图，对应 GF180MCU 晶体管级预版图仿真。LED 动态参数和封装寄生为假设，未完成 PEX 或光链路验证。')
p.write_text(s)
print(p)
