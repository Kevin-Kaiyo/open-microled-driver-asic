#!/usr/bin/env python3
"""Focused reference compensation and real MOS soft-start candidate schematics."""
from pathlib import Path
import importlib.util,hashlib,json
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('drawing',ROOT/'scripts/highspeed_routes/circuits.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
OUT=ROOT/'docs/research/pwm-reference-startup-20261024/figures';OUT.mkdir(parents=True,exist_ok=True);m.OUT=OUT

def cap(d,x,y,label,horiz=False):
 if horiz:
  d.line([(x-40,y),(x-8,y)]);d.line([(x-8,y-22),(x-8,y+22)]);d.line([(x+8,y-22),(x+8,y+22)]);d.line([(x+8,y),(x+40,y)]);d.text(x-55,y-37,label,18)
 else:
  d.line([(x,y-40),(x,y-8)]);d.line([(x-22,y-8),(x+22,y-8)]);d.line([(x-22,y+8),(x+22,y+8)]);d.line([(x,y+8),(x,y+40)]);d.text(x+30,y+7,label,18)

def saved(d,name,srcs):
 r=d.save(name);p=OUT/(name+'.svg');p.write_text(p.read_text().replace('原创教学示意。候选架构，未经高速晶体管或版图仿真。器件端子和电流方向有明确标注。','本轮仿真电路局部图；实验版本及验收状态见报告，不代表整片物理或生产签核。'))
 r['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();r['sources']={x:hashlib.sha256((ROOT/x).read_bytes()).hexdigest() for x in srcs};return r

def compensation():
 d=m.Drawing('显示 PWM：改变补偿连接，分别控制栅极响应与环路带宽','局部电路图：保留原39 MOS；图中展示关键第二级，前级和镜像输出按同名网络连接',1030)
 for off,title,new in [(0,'原补偿：N2 与 CTRL 之间 30 pF',False),(800,'修改：N2 经 150 pF 回 PCB 地',True)]:
  d.text(off+50,185,title,23,m.TEAL,True)
  x=off+490;d.text(x-30,235,'VREF',20,m.BLUE,True);d.line([(x,250),(x,298)],m.BLUE)
  d.mos(x,350,'PLOAD',['CTRL','CTRL','VREF','VREF'],True,label=False);d.text(x+38,350,'PLOAD',18)
  d.line([(x,402),(x,598)]);d.dot(x,460);d.line([(x,460),(x-100,460),(x-100,350),(x-62,350)],m.PURPLE)
  d.mos(x,650,'NSTAGE',['CTRL','N2','VSS','VSS'],label=False);d.text(x+38,650,'NSTAGE',18)
  d.line([(x,702),(x,770)]);d.ground(x,770)
  d.line([(off+100,650),(x-62,650)],m.PURPLE);d.text(off+95,620,'N2 / 前级输出',20,m.PURPLE,True)
  d.dot(x,500);d.line([(x,500),(off+720,500)],m.PURPLE);d.text(off+570,478,'CTRL',20,m.PURPLE,True);d.text(off+550,545,'至 PREG / POUT 栅极',17,m.MUTE)
  if new:
   d.dot(off+250,650);d.line([(off+250,650),(off+250,700)]);cap(d,off+250,740,'150 pF');d.line([(off+250,780),(off+250,810)]);d.ground(off+250,810)
  else:
   d.dot(off+250,650);d.line([(off+250,650),(off+250,500),(off+305,500)]);cap(d,off+345,500,'30 pF',True);d.line([(off+385,500),(x,500)]);d.dot(x,500)
 d.line([(800,210),(800,845)],m.LIGHT,1.4)
 d.footer(['原补偿电容使 CTRL 的快速变化与 N2 耦合；新接法把主要补偿留在 N2，使 CTRL 更易跟随电源。','这是待各工艺角、容差、启动和故障复验的结构修改。右侧150pF回PCB地；其外引线与ESR的建模边界见最终实验表。'])
 # Repeated panel device names are allowed visually; source connections stated explicitly in each panel.
 return saved(d,'compensation-change',['analog/reference/vset_servo.spice','analog/pwm_reference_v2/experiment-03.json'])

def softstart():
 d=m.Drawing('显示 PWM：MOS 受控参考电源候选','两只并联 PMOS 降低导通压降；NMOS 接受外部 START；图示为 v1 实验连接，验收见结果',1130)
 d.line([(340,230),(1200,230)],m.BLUE);d.text(340,207,'VIN / 原参考电源输入',22,m.BLUE,True)
 for x,n in [(780,'P0'),(1120,'P1')]:
  d.line([(x,230),(x,318)],m.BLUE);d.mos(x,370,n,['VOUT','GSOFT','VIN','VIN'],True);d.line([(x,422),(x,500)]);d.dot(x,230,m.BLUE)
 d.line([(780,500),(1350,500)],m.TEAL);d.dot(1120,500,m.TEAL);d.text(1190,475,'VOUT',22,m.TEAL,True);d.arrow(1350,500,1450,500,m.TEAL);d.lines(1220,545,['供给原参考宏','不改变 LED 负载'],19,30)
 d.line([(600,370),(718,370)],m.PURPLE);d.line([(600,370),(600,300),(1058,300),(1058,370)],m.PURPLE);d.dot(600,370);d.text(430,345,'GSOFT',22,m.PURPLE,True)
 d.line([(340,230),(340,316)]);d.resistor(340,360,'RUP 1 Mohm');d.line([(340,404),(340,450),(600,450),(600,370)],m.PURPLE);d.dot(600,450)
 d.line([(450,230),(450,256)]);cap(d,450,296,'CBOOT 33 pF');d.line([(450,336),(450,450)]);d.dot(450,450,m.PURPLE);d.dot(450,230,m.BLUE)
 d.line([(600,450),(600,526)]);d.resistor(600,570,'RDOWN 100 kohm');d.line([(600,614),(600,708)]);d.text(620,667,'NDRAIN',19,m.PURPLE)
 d.mos(600,760,'N0',['NDRAIN','START','VSS','VSS']);d.line([(600,812),(600,880)]);d.ground(600,880)
 d.line([(260,760),(538,760)],m.PURPLE);d.text(260,736,'START / 外部控制',21,m.PURPLE,True)
 d.box(860,650,680,225,'启动顺序的物理含义',['START=0：RUP 将 GSOFT 拉向 VIN，PMOS 关断。','START=1：N0 通过 RDOWN 放电，PMOS 逐渐导通。','CBOOT 接 VIN，减小上电时瞬间 VSG 的变化。','FAULT 与参考供电启动分别控制；这不是自主 POR。','P0/P1：W/L=100/1 um；N0：W/L=2/1 um。'],size=18)
 d.footer(['全部06v0器件；PMOS B=VIN，NMOS B=VSS。RUP、RDOWN、CBOOT 为片外建模。','源：analog/pwm_reference_v2/softstart_v1.spice。是否收敛、是否满足保持电流及恢复门槛，以对应实验表为准。'])
 return saved(d,'softstart-v1',['analog/pwm_reference_v2/softstart_v1.spice'])
def external_network():
 cf=json.loads((ROOT/'analog/pwm_reference_v2/final-network.json').read_text())['selected_filter_c_nf']
 d=m.Drawing('显示 PWM：板级元件、封装与片内 PEX 的连接边界','最终候选网络示意：器件和取值按 final-network.json；图中电阻、电容及封装电感是显式模型',1170)
 def hr(x,y,label):
  d.line([(x-50,y),(x-30,y)]);d.p.append(f'<rect x="{x-30}" y="{y-12}" width="60" height="24" fill="white" stroke="{m.INK}" stroke-width="2.7"/>');d.line([(x+30,y),(x+50,y)]);d.text(x,y-27,label,18,anchor='middle')
 def hl(x,y,label):
  d.line([(x-45,y),(x-32,y)]);d.p.append(f'<path d="M{x-32},{y} a8,12 0 0 1 16,0 a8,12 0 0 1 16,0 a8,12 0 0 1 16,0 a8,12 0 0 1 16,0" fill="none" stroke="{m.INK}" stroke-width="2.7"/>');d.line([(x+32,y),(x+45,y)]);d.text(x,y-27,label,18,anchor='middle')
 d.box(1080,225,430,570,'原 39 MOS 实际 PEX 宏',['参考电流 / 镜像','隔离 / 故障保护','buffer / 像素驱动'],fill='#edf4f3',size=22)
 d.line([(80,320),(190,320)]);d.text(80,290,'VREF 输入',22,m.BLUE,True);hr(240,320,'100 ohm');d.line([(290,320),(430,320)]);d.dot(430,320)
 d.line([(430,320),(430,370)]);cap(d,430,410,f'{cf:g} nF');d.line([(430,450),(430,490)]);d.ground(430,490);d.text(470,490,'PCB GND',19,m.BLUE)
 d.line([(430,320),(580,320)]);hr(630,320,'1 ohm');d.line([(680,320),(745,320)]);hl(790,320,'5 nH');d.line([(835,320),(1080,320)]);d.text(945,300,'VREF pin',20,m.BLUE)
 d.line([(1080,560),(840,560)]);d.text(945,540,'N2 pin',20,m.PURPLE);hr(790,560,'1 ohm');d.line([(740,560),(675,560)]);hl(630,560,'5 nH');d.line([(585,560),(510,560)]);hr(460,560,'阻尼 10 ohm');d.line([(410,560),(360,560)]);hr(310,560,'ESR 0.5 ohm');d.line([(260,560),(150,560),(150,630)]);cap(d,150,670,'150 pF');d.line([(150,710),(150,750)]);d.ground(150,750);d.text(85,790,'PCB GND',19,m.BLUE)
 d.line([(1080,740),(840,740)]);d.text(950,717,'VSS pin',20,m.BLUE);hr(790,740,'1 ohm');d.line([(740,740),(675,740)]);hl(630,740,'5 nH');d.line([(585,740),(510,740),(510,810)]);d.ground(510,810)
 d.box(48,875,1505,150,'为什么要把返回点画出来',[f'{cf:g} nF 滤波电容在封装之前回 PCB 地；150 pF 补偿支路新增 N2 外引 R/L、10 ohm 阻尼和 ESR。','片内提取 R/C 保留在宏内；上图 1 ohm / 5 nH 与 0.5 ohm ESR 是工程应力假设，不是封装实测或场解结果。','PWM / FAULT / PERMIT 输入另含 10 ohm 外部驱动阻抗；VSET、RSET 及其误差保持独立测试。'],size=19)
 d.footer(['本轮改变的是外部补偿与输入边界，原39MOS实际版图不变；不能把板级电容算入芯片面积或新PEX统计。','实际电路包含其它供电与LED支路，本图只展开参考电源、N2补偿和公共回流这三条关键路径。'])
 source='analog/pwm_reference_v2/final-network.json'
 return saved(d,'external-network',[source] if (ROOT/source).exists() else ['analog/pwm_reference_v2/scope.json'])
if __name__=='__main__':
 (OUT/'circuit-manifest.json').write_text(json.dumps({'figures':[compensation(),softstart(),external_network()]},ensure_ascii=False,indent=2)+'\n')
