#!/usr/bin/env python3
"""Standard CMOS symbols with explicit finite upstream source/reference planes."""
from pathlib import Path
import html
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'docs/research/driver-interface-20261115/assets';S=[]
def line(x,y,X,Y,c='#345264',w=2):S.append(f'<path d="M{x},{y} L{X},{Y}" fill="none" stroke="{c}" stroke-width="{w}"/>')
def text(x,y,t,size=15,anchor='start',c='#233e4e'):S.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{c}" text-anchor="{anchor}">{html.escape(t)}</text>')
def dot(x,y):S.append(f'<circle cx="{x}" cy="{y}" r="3.4" fill="#345264"/>')
def ground(x,y):
 line(x,y,x,y+10);line(x-12,y+10,x+12,y+10);line(x-8,y+16,x+8,y+16);line(x-3,y+22,x+3,y+22)
def resistor(x,y,X,label):
 line(x,y,x+10,y);line(X-10,y,X,y);S.append(f'<rect x="{x+10}" y="{y-7}" width="{X-x-20}" height="14" fill="white" stroke="#345264" stroke-width="2"/>');text((x+X)/2,y-18,label,14,'middle')
def mos(x,y,p,label):
 line(x,y-19,x,y+19);line(x+12,y-18,x+12,y-6);line(x+12,y-3,x+12,y+3);line(x+12,y+6,x+12,y+18)
 line(x+12,y-16,x+32,y-16);line(x+32,y-16,x+32,y-40);line(x+12,y+16,x+32,y+16);line(x+32,y+16,x+32,y+40)
 if p:S.append(f'<circle cx="{x-6}" cy="{y}" r="5" fill="white" stroke="#345264" stroke-width="2"/>');line(x-25,y,x-11,y)
 else:line(x-25,y,x,y)
 text(x+47,y+5,label,13)
def inv(x,y,rail,p,n):
 mos(x,y-65,True,p);mos(x,y+65,False,n);line(x-45,y-65,x-25,y-65);line(x-45,y-65,x-45,y+65);line(x-45,y+65,x-25,y+65)
 line(x+32,y-25,x+32,y+25);dot(x+32,y);line(x+32,y,x+100,y)
 line(x+32,y-105,x+32,y-125);text(x+32,y-138,rail,15,'middle');ground(x+32,y+105)
def main():
 S.append('<svg xmlns="http://www.w3.org/2000/svg" width="1220" height="1090" viewBox="0 0 1220 1090"><style>text{font-family:"Arial Unicode MS","PingFang SC",Arial,sans-serif}</style><rect width="1220" height="1090" fill="#fbfcfd"/>')
 text(35,45,'VCSEL 有限 CMOS 输入：实际多出的器件、负载与供电边界',25)
 text(35,78,'展开新增 4 MOS 与原核心 4 MOS 预驱动；同名网络相连，W / L 单位为 µm。',16)
 for y,cmd,node,gate,dev in [(285,'DB_CMD','DI','GN','D'),(655,'D_CMD','DBI','GP','DB')]:
  inv(235,y,'VPHY ≈ 3.3 V',f'XPHY{dev}P',f'XPHY{dev}N')
  text(35,y-10,cmd,16);line(35,y,190,y);dot(190,y)
  text(35,y+35,'理想命令 0–3.3 V / 20 ps',13)
  text(267,y+160,'Wn / Wp = 4 / 8 或 12 / 24',13,'middle');text(267,y+182,'L = 0.28；P 体接 VPHY，N 体接 VSS',12,'middle')
  text(345,y+23,'d_src' if node=='DI' else 'db_src',14);line(335,y,345,y)
  resistor(345,y,460,'外部 50 Ω');resistor(460,y,595,'内部 150 Ω');line(595,y,760,y);dot(660,y);text(622,y-18,node,16)
  line(660,y,660,y+45);S.append(f'<rect x="653" y="{y+45}" width="14" height="52" fill="white" stroke="#345264" stroke-width="2"/>');ground(660,y+97)
  text(684,y+65,'RADI' if node=='DI' else 'RADBI',14);text(684,y+87,'2.5 kΩ → 25 kΩ',14);text(684,y+109,'仅负载实验改变',12)
  inv(805,y,'DR ≈ 3.1 V','PMOS 24 / 0.28','NMOS 12 / 0.28');line(905,y,1150,y);text(1070,y-15,gate,18)
  text(980,y+34,'→ 换流管栅极',14);text(837,y+160,'原 69 MOS 核心的一部分',14,'middle');text(837,y+182,'P 体接 DR；N 体接 VSS',13,'middle')
 text(35,897,'新增上游供电：VPHY 理想源 → 0.25 Ω → 0.2 nH → VPHY；去耦为 0.1 Ω + 1 nF 串联至地。',16)
 text(35,929,'D_CMD=1：DI 高、DBI 低 → GP 高、GN 低 → 4 mA 调制电流进 VCSEL，加 3 mA 偏置，共约 7 mA。',15)
 text(35,959,'D_CMD=0：DI 低、DBI 高 → GP 低、GN 高 → 4 mA 转向虚支路，VCSEL 保持约 3 mA。',15)
 text(35,997,'计能：保留 VLASER / VDD / VREF / VSET / VREGSET，新增 VPHY，同时计入 D_CMD / DB_CMD 的栅充电。',14)
 text(35,1026,'这是 GF180 3.3 V CMOS 有限驱动模型；未覆盖任何实物 FPGA、LVDS/CML 接收器、Pad、ESD、走线或实际 PHY 合规。',14)
 text(35,1055,'2.5 kΩ 的历史用途是输入衰减，不是已确认的传输线终端；增加下拉阻值不等于实现激光保护关断。',14)
 S.append('</svg>');OUT.mkdir(parents=True,exist_ok=True);p=OUT/'vcsel-interface-circuit.svg';p.write_text('\n'.join(S));print(p)
if __name__=='__main__':main()
