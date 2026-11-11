#!/usr/bin/env python3
"""Draw the selected single-stage VCSEL signal path as an SVG schematic."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'evidence/driver-methods-20261111/vcsel-single-stage-circuit.svg'
S=[]
def line(x1,y1,x2,y2,c='#385366',w=2):S.append(f'<path d="M{x1},{y1} L{x2},{y2}" stroke="{c}" stroke-width="{w}" fill="none"/>')
def text(x,y,t,size=15,anchor='start',color='#233d4a'):S.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{color}" font-size="{size}">{t}</text>')
def dot(x,y):S.append(f'<circle cx="{x}" cy="{y}" r="3.5" fill="#385366"/>')
def resistor(x1,y,x2,label):
 line(x1,y,x1+15,y);line(x2-15,y,x2,y);S.append(f'<rect x="{x1+15}" y="{y-8}" width="{x2-x1-30}" height="16" fill="white" stroke="#385366" stroke-width="2"/>');text((x1+x2)/2,y-16,label,14,'middle')
def ground(x,y):
 line(x,y,x,y+10);line(x-12,y+10,x+12,y+10);line(x-8,y+16,x+8,y+16);line(x-3,y+22,x+3,y+22)
def mos(x,y,kind,label):
 line(x,y-20,x,y+20);line(x+13,y-19,x+13,y-7);line(x+13,y-4,x+13,y+4);line(x+13,y+7,x+13,y+19)
 line(x+13,y-16,x+32,y-16);line(x+32,y-16,x+32,y-40);line(x+13,y+16,x+32,y+16);line(x+32,y+16,x+32,y+40)
 if kind=='p':
  S.append(f'<circle cx="{x-6}" cy="{y}" r="5" fill="white" stroke="#385366" stroke-width="2"/>');line(x-25,y,x-11,y)
 else:line(x-25,y,x,y)
 text(x+47,y+4,label,13)
def inverter(x,y,label):
 # Return input, output and local rail positions.
 mos(x,y-70,'p','PMOS 24 / 0.28 um');mos(x,y+70,'n','NMOS 12 / 0.28 um')
 line(x-50,y-70,x-25,y-70);line(x-50,y-70,x-50,y+70);line(x-50,y+70,x-25,y+70)
 line(x+32,y-30,x+32,y+30);line(x+32,y,x+90,y);dot(x+32,y)
 line(x+32,y-110,x+32,y-135);text(x+32,y-146,'DR 约 3.1 V',14,'middle');ground(x+32,y+110)
 text(x+32,y+153,label,14,'middle');return (x-50,y),(x+90,y)
def main():
 S.append('<svg xmlns="http://www.w3.org/2000/svg" width="1240" height="940" viewBox="0 0 1240 940"><style>text{font-family:"PingFang SC","Hiragino Sans GB",Arial,sans-serif}</style><rect width="1240" height="940" fill="#fbfcfd"/>')
 text(40,45,'VCSEL 单级交叉预驱动：局部电路与电流路径',25)
 text(40,74,'69 MOS 候选；这里展开 4 MOS CMOS 预驱动 + 2 MOS 换流，参考与稳压回路以端口表示。',16)
 # P channel is driven by DBI; N channel by DI. Inputs use the same existing attenuation/shunt network.
 p_in,p_out=inverter(220,290,'GP = NOT(DBI)')
 n_in,n_out=inverter(220,620,'GN = NOT(DI)')
 text(45,290,'DB',15);resistor(90,290,170,'RADB 150 ohm');text(175,318,'DBI',14)
 text(45,620,'D',15);resistor(90,620,170,'RAD 150 ohm');text(175,648,'DI',14)
 text(40,835,'同名 GP / GN 网络表示电气连接；MOS 尺寸标注为 W / L。',14)
 text(40,810,'每路输入另有 2.5 kohm 接 VSS；外部源串联 50 ohm，20 ps / 3.3 V。',14)
 line(p_out[0],p_out[1],410,290);text(418,295,'GP',16);line(505,390,535,390);text(505,377,'GP',16)
 line(n_out[0],n_out[1],410,620);text(418,625,'GN',16);line(730,390,765,390);text(730,377,'GN',16)
 # Output steering NMOS devices. The source nodes join VX and a feedback controlled tail current.
 mos(560,390,'n','XSTEER');mos(790,390,'n','XDUMP')
 text(625,450,'20 / 0.28 um',13);text(855,450,'20 / 0.28 um',13)
 line(592,430,592,490);line(592,490,822,490);line(822,430,822,490);dot(704,490);text(715,514,'VX',15)
 line(704,490,704,545);S.append('<circle cx="704" cy="574" r="29" fill="white" stroke="#385366" stroke-width="2"/>');line(704,558,704,590);line(704,590,696,580);line(704,590,712,580);line(704,603,704,666);ground(704,666)
 text(750,568,'调制尾电流 4 mA',16);text(750,591,'实际反馈电流源（未展开）',13)
 # Laser and dummy branches both powered by VL; baseline current sink remains permanently on.
 line(592,350,592,245);line(822,350,822,245);text(604,288,'OUT',15);text(834,288,'DUMMY',15)
 S.append('<rect x="532" y="160" width="120" height="85" rx="4" fill="white" stroke="#385366" stroke-width="2"/>');text(592,187,'VCSEL 负载',15,'middle');text(592,210,'150 fF',14,'middle');text(592,230,'封装 R / L',13,'middle')
 S.append('<rect x="813" y="165" width="18" height="80" fill="white" stroke="#385366" stroke-width="2"/>');text(844,200,'RDUMMY',14);text(844,224,'500 ohm',14)
 line(592,160,592,130);line(592,130,822,130);line(822,130,822,165);text(704,117,'VL 约 3.1 V（实际稳压）',16,'middle')
 line(592,270,485,270);line(485,270,485,510);dot(592,270);S.append('<circle cx="485" cy="540" r="29" fill="white" stroke="#385366" stroke-width="2"/>');line(485,524,485,556);line(485,556,477,546);line(485,556,493,546);ground(485,569);text(485,650,'偏置 3 mA',14,'middle')
 text(930,340,'D = 1 / DB = 0',17);text(930,368,'GP 高，GN 低',16);text(930,396,'4 mA 流过光源',16);text(930,424,'总电流约 7 mA',16)
 text(930,485,'D = 0 / DB = 1',17);text(930,513,'GP 低，GN 高',16);text(930,541,'4 mA 转向虚支路',16);text(930,569,'光源维持约 3 mA',16)
 text(40,860,'NMOS 体接 VSS，CMOS PMOS 体接 DR。图中电流源符号对应实际 MOS 反馈电路，不是新增理想源。',14)
 text(40,890,'150 ohm 为阻尼确认值；元件没有按速率重调。原生仿真包含全部 69 MOS、7 个供能端口与参考/供轨电路。',14)
 S.append('</svg>');OUT.write_text('\n'.join(S)+'\n');print(OUT)
if __name__=='__main__':main()
