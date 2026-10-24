#!/usr/bin/env python3
"""Explain the actually added supply/return R-L network using a CMOS stage detail."""
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('circuits',ROOT/'scripts/highspeed_routes/circuits.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.OUT=ROOT/'docs/research/driver-robustness-20261024/figures';m.OUT.mkdir(exist_ok=True)
d=m.Drawing('供电与回地必须构成完整回路', '实际实验在VDD和VSS各串入1 ohm + 2 nH；下图仅展开一个CMOS级，便于读懂局部端电压',1140)
def hres(x,y,name):
 d.line([(x-60,y),(x-38,y)]);d.p.append(f'<rect x="{x-38}" y="{y-12}" width="76" height="24" fill="white" stroke="{m.INK}" stroke-width="2.7"/>');d.line([(x+38,y),(x+60,y)]);d.text(x,y-30,name,20,m.INK,True,'middle')
def hind(x,y,name):
 d.line([(x-60,y),(x-32,y)]);d.p.append(f'<path d="M{x-32},{y} c0,-22 16,-22 16,0 c0,-22 16,-22 16,0 c0,-22 16,-22 16,0 c0,-22 16,-22 16,0" fill="none" stroke="{m.INK}" stroke-width="2.7"/>');d.line([(x+32,y),(x+60,y)]);d.text(x,y-30,name,20,m.INK,True,'middle')
d.p.append('<circle cx="160" cy="470" r="40" fill="white" stroke="#233d4b" stroke-width="2.7"/>')
d.text(160,458,'+',25,anchor='middle');d.text(160,495,'-',25,anchor='middle')
d.text(35,391,'理想电源',22,m.BLUE,True);d.text(25,425,'固定3.600 V',20,m.BLUE)
d.line([(160,430),(160,220),(360,220)]);hres(420,220,'R_VDD = 1 ohm');d.line([(480,220),(580,220)]);hind(640,220,'L_VDD = 2 nH');d.line([(700,220),(970,220),(970,298)])
d.dot(970,220);d.text(1020,225,'VDD_die',22,m.BLUE,True)
d.mos(970,350,'MP',['out','in','vdd_die','vdd_die'],True,m.BLUE);d.mos(970,650,'MN',['out','in','vss_die','vss_die'],False,m.ORANGE)
d.line([(970,402),(970,598)]);d.dot(970,500);d.line([(970,500),(1350,500),(1350,570)])
d.line([(1330,570),(1370,570)],m.TEAL);d.line([(1330,590),(1370,590)],m.TEAL);d.line([(1350,590),(1350,810),(970,810),(970,702)])
d.lines(1380,583,['后级栅电容','与布线电容'],19,28,m.TEAL)
d.text(1010,381,'B 接 VDD_die',18,m.MUTE);d.text(1010,679,'B 接 VSS_die',18,m.MUTE)
d.line([(908,350),(820,350),(820,650),(908,650)],m.PURPLE);d.dot(820,500,m.PURPLE);d.line([(520,500),(820,500)],m.PURPLE)
d.text(530,475,'DATA / 上一级输出',21,m.PURPLE,True)
d.text(530,539,'外部DATA以板级地为参考',18,m.PURPLE)
d.dot(970,810);d.text(1010,849,'VSS_die 并非板级地',22,m.ORANGE,True)
d.line([(970,810),(970,930),(700,930)]);hind(640,930,'L_VSS = 2 nH');d.line([(580,930),(480,930)]);hres(420,930,'R_VSS = 1 ohm');d.line([(360,930),(160,930),(160,510)])
d.dot(160,930);d.ground(160,950);d.text(215,987,'板级地 = 0 V',21,m.INK,True)
d.arrow(745,195,855,195,m.ORANGE);d.text(760,170,'供电电流',18,m.ORANGE)
d.arrow(1320,620,1320,735,m.ORANGE);d.text(1120,756,'给电容充电的回流',18,m.ORANGE)
d.arrow(865,955,755,955,m.ORANGE);d.text(750,989,'回地电流',18,m.ORANGE)
d.lines(210,627,['VDD_die = V源 - R_VDD·I_VDD - L_VDD·dI_VDD/dt',
 'VSS_die = R_VSS·I_VSS + L_VSS·dI_VSS/dt',
 '器件应力由本地D/G/S/B相减决定；',
 '示波器只盯板端3.600 V，会漏掉芯片端扰动。'],22,42,m.TEAL)
d.footer(['电容是后级与布线负载的等效画法，未在正式网表中重复添加；MOS内禀C与互连C来自PDK/PEX。',
 '其他LED/偏置电源未在此局部图展开，但正式仿真全部保留；R/L是集总敏感度假设，不是实测封装。'])
d.save('supply-return-circuit')
p=m.OUT/'supply-return-circuit.svg';p.write_text(p.read_text().replace('原创教学示意。候选架构，未经高速晶体管或版图仿真。器件端子和电流方向有明确标注。','实际仿真供电回路的原理解释；仅展开一个CMOS级，完整网表和局部波形另有证据。'))
