#!/usr/bin/env python3
"""Named-net board power connections, checked against the frozen final TT deck."""
from pathlib import Path
import importlib.util,hashlib,json
ROOT=Path(__file__).resolve().parents[2]
sp=importlib.util.spec_from_file_location('draw',ROOT/'scripts/highspeed_routes/circuits.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
OUT=ROOT/'docs/research/nrz-b-reference-power-20261024/figures';m.OUT=OUT
deck=ROOT/'build/nrz-reference-v2/selected-final-r2/cases/REFERENCE-B-NRZ_TT-0.5G-typical-27C-3.3V-C200-L0.5-e20-s40/testbench.spice'
expected=['RVIN vin_source pvin 0.25','LVIN pvin vin 5e-10','RANCHOR ref_source vref 0.2','RDIVH vref vset 200000.0','RDIVL vset 0 50000.0','CICOMP in2 0 1.5e-10','RCAP vin vcap 0.2','CIN vcap 0 1e-07','RGPIO disable_source disable 100']
lines=deck.read_text().splitlines();assert all(x in lines for x in expected)
d=m.Drawing('高速 B：片外供电、基准分压与补偿接口','同名网络接前页真实21 MOS宏；下面的元件属于明确的片外边界，不能计入芯片面积',1110)
def hr(x,y,label):
 d.line([(x-50,y),(x-30,y)]);d.p.append(f'<rect x="{x-30}" y="{y-12}" width="60" height="24" fill="white" stroke="{m.INK}" stroke-width="2.7"/>');d.line([(x+30,y),(x+50,y)]);d.text(x,y-30,label,18,anchor='middle')
def cap(x,y,label):
 d.line([(x,y-40),(x,y-8)]);d.line([(x-20,y-8),(x+20,y-8)]);d.line([(x-20,y+8),(x+20,y+8)]);d.line([(x,y+8),(x,y+40)]);d.text(x+28,y+7,label,19)
d.text(60,185,'1. RAW 电源：供电阻抗与去耦分开建模',23,m.BLUE,True)
d.text(80,250,'外部 5 V',20,m.BLUE,True);d.line([(80,280),(190,280)]);hr(240,280,'0.25 ohm');d.line([(290,280),(370,280)])
d.p.append(f'<path d="M370,280 a8,12 0 0 1 16,0 a8,12 0 0 1 16,0 a8,12 0 0 1 16,0 a8,12 0 0 1 16,0" fill="none" stroke="{m.INK}" stroke-width="2.7"/>');d.text(400,250,'0.5 nH',18,anchor='middle');d.line([(434,280),(700,280)],m.BLUE);d.dot(540,280);d.text(640,255,'VIN',22,m.BLUE,True)
d.line([(540,280),(540,326)]);d.resistor(540,370,'ESR 0.2 ohm');d.line([(540,414),(540,440)]);cap(540,480,'100 nF');d.line([(540,520),(540,545)]);d.ground(540,545)
d.lines(60,380,['VIN 同时供给 VI 参考与 RDUMMY。','没有片内 3.3 V LDO。','数字 VDD 与 LED 电源仍独立。','额外封装 R/L 在专门应力点加入。'],19,32)
d.text(820,185,'2. 电压基准：分压得到 VSET',23,m.PURPLE,True)
d.text(840,250,'外部 2.5 V',20,m.PURPLE,True);d.line([(840,280),(960,280)]);hr(1010,280,'Rout 0.2 ohm');d.line([(1060,280),(1150,280)]);hr(1200,280,'200 kohm');d.line([(1250,280),(1510,280)],m.PURPLE);d.dot(1350,280);d.text(1400,255,'VSET',22,m.PURPLE,True)
d.line([(1350,280),(1350,326)]);d.resistor(1350,370,'50 kohm');d.line([(1350,414),(1350,545)]);d.ground(1350,545)
d.lines(830,420,['VSET = 2.5 x 50 / (200 + 50)','          = 0.5 V','电压基准内部启动、噪声及 Iq','目前仍是待补的系统边界。'],19,32)
d.line([(800,190),(800,965)],m.LIGHT,1.2)
d.text(60,650,'3. 补偿接口：稳定参考，不跟随每一数据位',23,m.TEAL,True)
d.text(100,720,'IN2 引脚',21,m.PURPLE,True);d.line([(100,750),(340,750)]);d.dot(340,750);d.line([(340,750),(340,770)]);cap(340,810,'150 pF');d.line([(340,850),(340,900)]);d.ground(340,900)
d.lines(460,760,['主矩阵为外部补偿支路。','另测 1 ohm / 5 nH 外引线','及 0.5 ohm ESR 的 FF 点；','未覆盖全部通信矩阵。'],18,30)
d.text(830,650,'4. 外部启动互锁：先禁止，再等待参考',23,m.TEAL,True)
d.text(850,720,'0 / 3.3 V',20,m.PURPLE,True);d.line([(850,750),(1050,750)]);hr(1100,750,'100 ohm');d.line([(1150,750),(1510,750)],m.PURPLE);d.text(1290,725,'DISABLE',22,m.PURPLE,True)
d.lines(850,810,['高：MDIS、MK 导通，限制电流与悬空电压。','低：退出保护，正常传输。','参考从 0 us 上升 -> 20 us 释放；','参考从 30 us 上升 -> 50 us 释放。'],19,32)
d.footer(['示意采用最终TT原始网表逐项核对；器件取值、容差和寄生应力点分别记录，不把理想端口称为已实现的电源IC。','所有地符号为PCB参考地；实际芯片互连RC仍留在宏内。RSET与RIBIAS见晶体管参考原理图。'])
r=d.save('board-power-circuit');p=OUT/'board-power-circuit.svg';p.write_text(p.read_text().replace('原创教学示意。候选架构，未经高速晶体管或版图仿真。器件端子和电流方向有明确标注。','与最终TT冻结网表核对的片外接口图；器件实现和验收范围见正文。'))
(OUT/'board-power-circuit-manifest.json').write_text(json.dumps({'svg_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'deck':str(deck.relative_to(ROOT)),'deck_sha256':hashlib.sha256(deck.read_bytes()).hexdigest(),'verified_lines':expected,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n')
