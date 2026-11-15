#!/usr/bin/env python3
"""Original explicit-node schematic of the 10-MOS independent cutoff candidate."""
from pathlib import Path
import html
ROOT=Path(__file__).resolve().parents[3]
out=ROOT/'docs/research/driver-interface-20261115/assets/micro-protection-v2.svg'
out.parent.mkdir(parents=True,exist_ok=True)
ss=['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1080" viewBox="0 0 1600 1080"><defs><marker id="arr" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#157a76"/></marker></defs><rect width="1600" height="1080" fill="#fbfcfc"/><style>text{font-family:"PingFang SC","Hiragino Sans GB","Arial",sans-serif;fill:#233b50} .wire{stroke:#233b50;stroke-width:2.5;fill:none;stroke-linejoin:round}.box{stroke:#c9d7df;stroke-width:1.5;fill:white}</style>']
def line(x1,y1,x2,y2,c='#233b50',w=2.5):ss.append(f'<path d="M{x1} {y1}L{x2} {y2}" stroke="{c}" stroke-width="{w}" fill="none"/>')
def path(d,c='#233b50',w=2.5):ss.append(f'<path d="{d}" stroke="{c}" stroke-width="{w}" fill="none"/>')
def text(x,y,s,size=19,c=None):ss.append(f'<text x="{x}" y="{y}" font-size="{size}"'+(f' style="fill:{c}"' if c else '')+'>'+html.escape(s.replace('µ','u').replace('Ω','ohm').replace('→',' 至 ').replace('≈','~').replace('①','1.').replace('②','2.'))+'</text>')
def dot(x,y):ss.append(f'<circle cx="{x}" cy="{y}" r="4" fill="#233b50"/>')
def gnd(x,y):line(x,y,x,y+12);line(x-12,y+12,x+12,y+12);line(x-8,y+18,x+8,y+18);line(x-4,y+24,x+4,y+24)
def mos(x,y,p=False,name='',label='',body='0'):
 # p: source at top, drain at bottom. n: drain at top, source at bottom.
 line(x,y-50,x,y-30);line(x,y+30,x,y+50);line(x,y-30,x-20,y-30);line(x,y+30,x-20,y+30)
 for a,b in [(-30,-10),(-7,7),(10,30)]:line(x-20,y+a,x-20,y+b)
 line(x-32,y-32,x-32,y+32);line(x-65,y,x-32,y)
 if p:ss.append(f'<circle cx="{x-38}" cy="{y}" r="5" fill="white" stroke="#233b50" stroke-width="2"/>')
 # Body lead represented and labeled explicitly, to avoid suggesting source ties where none exist.
 line(x-20,y,x+20,y);text(x+23,y+6,'B='+body,12)
 text(x+6,y-55,name,17);text(x+6,y-20 if p else y+71,label,14)
 return (x,y-50),(x,y+50),(x-65,y)
text(40,48,'MicroLED 独立保护：切断阳极供电，并在关断时将 LED 两端等电位',29)
text(40,82,'v2 失效候选 · 低电流筛选通过，但恢复应力失败 · A 30 MOS，B 31 MOS（新增 10 MOS）',19)
ss.append('<rect class="box" x="30" y="110" width="740" height="570" rx="12"/><rect class="box" x="790" y="110" width="780" height="710" rx="12"/>')
text(50,145,'① 3.3 V 控制 → 5 V 交叉耦合电平转换',23)
# enable inverter
mos(195,260,True,'XEN_P','3.93 / 0.28 µm','VDD');mos(195,430,False,'XEN_N','2.5 / 0.28 µm')
line(195,190,195,210);text(155,182,'VDD = 3.3 V',16);line(195,310,195,380);dot(195,345);line(195,345,290,345);text(235,332,'EN',18)
line(95,260,130,260);line(95,260,95,430);line(95,430,130,430);dot(95,345);line(52,345,95,345);text(48,315,'DISABLE',16)
gnd(195,480)
# level shift
for x,side in [(420,1),(650,2)]:
 mos(x,260,True,'XLS_P'+str(side),'4 / 0.7 µm','VLED');mos(x,430,False,'XLS_N'+str(side),'10 / 0.7 µm')
 line(x,190,x,210);line(x,310,x,380);dot(x,345);gnd(x,480)
line(420,190,650,190);text(460,181,'VLED / led_feed ≈ 5 V',17)
text(352,248,'iso_gb',16);text(583,248,'iso_g',16);text(353,418,'EN',16);text(573,418,'DISABLE',15)
line(420,345,475,345);text(443,332,'iso_g',17);line(650,345,722,345);text(659,332,'iso_gb',17)
text(50,558,'同名网络标签表示直接连接；两只 PMOS 的栅极交叉连接。',19)
text(50,592,'DISABLE = 0：EN 为高，iso_g 为低 → 高侧 PMOS 导通。',18)
text(50,625,'DISABLE = 3.3 V：EN 为低，iso_g 为高 → 高侧 PMOS 截止。',18)
text(810,145,'② 高侧隔离与跨 LED 钳位',23)
# three isolating parallel MOS
for k,x in enumerate([920,1120,1320]):
 mos(x,260,True,'XISO'+str(k),'100 / 0.7 µm','VLED');line(x,190,x,210);line(x,310,x,355);text(x-70,245,'iso_g',16)
line(920,190,1445,190);text(1370,178,'VLED = 5 V',17)
line(920,355,1480,355);text(825,346,'led_a',18)
for x in [920,1120,1320]:dot(x,355)
# LED & cap at x1000 1250
line(1000,355,1000,410);path('M980 410 L1020 410 L1000 440 Z');line(980,440,1020,440);line(1000,440,1000,530)
path('M1022 420 L1045 402 M1030 432 L1053 414','#157a76');path('M1034 403 L1045 402 L1043 413 M1042 415 L1053 414 L1051 425','#157a76');text(825,455,'20 µm LED',18);text(825,480,'黄光静态 I–V',17)
line(1250,355,1250,420);line(1228,420,1272,420);line(1228,435,1272,435);line(1250,435,1250,530);text(1190,480,'CLED = 200 fF',17)
mos(1480,430,False,'XCLAMP','10 / 0.7 µm');line(1480,355,1480,380);line(1480,480,1480,530);text(1380,420,'DISABLE',15)
line(1000,530,1480,530);dot(1250,530);dot(1480,530);text(810,535,'led_k',18)
line(1000,530,1000,555);path('M1000 555 l-7 8 l14 12 l-14 12 l14 12 l-7 8');line(1000,607,1000,630);text(1030,588,'Rpkg = 1 Ω',18)
path('M1000 630 c18 0 18 13 0 13 c18 0 18 13 0 13 c18 0 18 13 0 13 c18 0 18 13 0 13');line(1000,682,1000,710);text(1030,660,'Lpkg = 0.5 nH',18)
ss.append('<rect x="855" y="710" width="600" height="80" rx="8" fill="#eef5f5" stroke="#648d8d"/>');text(875,740,'OUT → 冻结 A / B 驱动核心；DATA 始终翻转',20);text(875,771,'B 的原参考关断端接 0：参考持续工作，其静态功耗仍计入',16)
text(40,726,'工作原理',23)
text(40,763,'正常：VLED → 并联 PMOS → LED → 驱动核心。',18)
text(40,797,'保护：切断 VLED；XCLAMP 导通，把 A、K 两端',18)
text(40,830,'拉到接近同一电位，吸收 CFF 在输出端的注入。',18)
text(40,869,'关断不等于断掉 DATA，也不等于仅把参考电流拉低。',18)
line(40,905,1560,905,'#c9d7df',1)
text(40,941,'器件类型与实现边界',22)
text(40,976,'XEN 为 GF180MCU 3.3 V MOS，其余新增器件为 6 V MOS；PMOS 体端接各自高侧供电，NMOS 体端接地。',19)
text(40,1008,'W = 300 µm 单管超出当前模型 bin，现显式采用三只 W = 100 µm；面积与端部寄生按三只分别计入。',19)
text(40,1040,'这是原理图级候选，未经过新版图 DRC/LVS/PEX；低于 0.1 µA 的关断电流仍位于静态 I–V 校准域之外。',18)
ss.append('</svg>');out.write_text('\n'.join(ss))
print(out)
