#!/usr/bin/env python3
"""Original transistor-level difference drawings, checked against the actual candidate deck."""
from pathlib import Path
import hashlib,html,json
ROOT=Path(__file__).resolve().parents[3];A=ROOT/'docs/research/driver-pvt-20261117/assets';P=ROOT/'build/driver-pvt-20261117/b/clamp5v_buffer_soft/ss_hot_low-full-s40';deck=(P/'testbench.spice').read_text()
for s in ['RCLAMP iso_g clamp_g 200k','XCLAMPRST clamp_g en 0 0 nfet_06v0 w=0.5u l=0.7u','XIB1N ib1 data_gate 0 0','XIB2N data_buffered ib1 0 0','XCLAMP led_a clamp_g led_k 0','r_width=4u r_length=8u']:assert s in deck
assert 'XIBDAMP' not in deck
C='#203b50';ss=[]
def init(h):
 global ss
 ss=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{h}" viewBox="0 0 1200 {h}"><rect width="1200" height="{h}" fill="white"/><style>text{{font-family:"PingFang SC","Hiragino Sans GB",Arial,sans-serif;fill:{C}}}</style>']
def line(x,y,a,b,c=C,w=2.3):ss.append(f'<path d="M{x} {y} L{a} {b}" fill="none" stroke="{c}" stroke-width="{w}"/>')
def text(x,y,t,s=20,c=C):ss.append(f'<text x="{x}" y="{y}" font-size="{s}" fill="{c}">{html.escape(t.replace("×","x").replace("→","至"))}</text>')
def dot(x,y):ss.append(f'<circle cx="{x}" cy="{y}" r="3.7" fill="{C}"/>')
def gnd(x,y):line(x,y,x,y+12);line(x-12,y+12,x+12,y+12);line(x-8,y+18,x+8,y+18);line(x-4,y+24,x+4,y+24)
def resistor(x,y,length=100):
 line(x,y,x+12,y);ss.append(f'<rect x="{x+12}" y="{y-8}" width="{length-24}" height="16" fill="white" stroke="{C}" stroke-width="2.3"/>');line(x+length-12,y,x+length,y)
def mos(x,y,p,name,size,body):
 line(x,y-50,x,y-28);line(x,y+28,x,y+50);line(x,y-28,x-20,y-28);line(x,y+28,x-20,y+28)
 for a,b in [(-28,-10),(-7,7),(10,28)]:line(x-20,y+a,x-20,y+b)
 line(x-32,y-31,x-32,y+31);line(x-70,y,x-32,y)
 if p:ss.append(f'<circle cx="{x-39}" cy="{y}" r="5" fill="white" stroke="{C}" stroke-width="2"/>')
 line(x-20,y,x+18,y);text(x+23,y+7,'B='+body,15);text(x+7,y-57,name,19);text(x+8 if p else x+25,y-27 if p else y+72,size,17)
def save(name):
 ss.append('</svg>');p=A/(name+'.svg');p.write_text('\n'.join(ss));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 (A/(name+'.source.json')).write_text(json.dumps({'actual_case':str(P.relative_to(ROOT)),'deck_sha256':sha(P/'testbench.spice'),'manifest_sha256':sha(P/'manifest.json'),'generator_sha256':sha(Path(__file__)),'scope':'Original local circuit difference schematic of44MOS candidate. Other frozen core devices omitted explicitly; no PVT/PEX qualification implied.'},ensure_ascii=False,indent=2)+'\n')
 try:
  import cairosvg;cairosvg.svg2png(url=str(p),write_to=str(A/(name+'.png')),scale=1.4)
 except Exception as e:print('render',e)
init(700);text(35,45,'B 关断执行器：提高钳位驱动，同时控制接入与撤除斜率',27);text(35,79,'44 MOS 研究候选 · 图示改动局部；原参考源、高侧隔离和数据核心仍工作',19)
text(35,126,'旧连接：XCLAMP 栅极直接接 DISABLE（3.3 V 控制）',20,'#8b653e')
text(35,160,'iso_g（原 5 V 电平转换输出）',19);line(70,202,140,202);resistor(140,202,130);line(270,202,430,202);text(143,184,'RCLAMP 200k',18);text(315,184,'clamp_g',20);dot(430,202)
line(430,202,430,340);line(850,340,900,340);text(845,316,'clamp_g',17);mos(970,340,False,'XCLAMP','W10 / L0.7 um','0');line(970,240,970,290);line(970,390,970,490);text(850,222,'LED_A',20);text(860,519,'LED_K',20)
line(690,240,970,240);line(690,490,970,490);text(660,222,'来自原高侧 PISO',17)
line(690,240,690,310);ss.append(f'<path d="M670 310 L710 310 L690 342 Z" fill="none" stroke="{C}" stroke-width="2.3"/>');line(671,343,709,343);line(690,343,690,490);text(600,380,'MicroLED',19)
line(810,240,810,317);line(790,317,830,317);line(790,334,830,334);line(810,334,810,490);text(760,380,'200 fF',18)
line(430,340,430,400);dot(430,340);mos(430,450,False,'XCLAMPRST','W0.5 / L0.7 um','0');line(430,500,430,530);gnd(430,530);line(195,450,360,450);text(80,440,'EN = !DISABLE',19);text(80,473,'原 3.3 V 反相输出',17)
line(690,490,690,548);text(620,575,'1 ohm / 0.5 nH 封装 → OUT / 电流转向核心',19)
text(35,623,'关断：clamp_g 经电阻缓升以减少重叠电流；恢复：小尺寸复位管限制栅极撤除冲击。',19)
text(35,658,'XCLAMP / XCLAMPRST 均为 GF180 6 V NMOS，体端接 0；RC 是开环控制，并非 power-good。',18)
text(35,687,'同名网络标签直接电连接；没有用理想延迟元件替代这些 MOS。',17)
save('b-clamp-circuit')
init(760);text(35,46,'B 输入缓冲：隔开 NAND 的控制边沿与上游数据栅极',27);text(35,82,'新增 4 只 3.3 V MOS；原 RDATA 两方块与原核心 XRIN 均保留。',20)
for x,n in [(400,1),(810,2)]:
 mos(x,265,True,'XIB'+str(n)+'P','W3.93 / L0.28 um','VDD');mos(x,455,False,'XIB'+str(n)+'N','W2.5 / L0.28 um','0');line(x,170,x,215);line(x,315,x,405);dot(x,360);gnd(x,505);text(x-60,153,'VDD = 3.3 V × s',18)
line(50,360,110,360);resistor(110,360,100);line(210,360,270,360);line(270,265,270,455);line(270,265,330,265);line(270,455,330,455);dot(270,360);text(40,337,'DATA',19);text(80,395,'PDK poly',17);text(80,420,'W4 / L8 um',17);text(216,338,'data_gate',18)
line(400,360,665,360);line(665,265,665,455);line(665,265,740,265);line(665,455,740,455);dot(665,360);text(546,338,'ib1',20)
line(810,360,1115,360);text(956,336,'data_buffered',19);text(945,391,'→ 原 NAND + INV',18);text(945,420,'→ DATA_SAFE',18)
text(35,608,'NAND 的 READY 单独变化时，新增输出级吸收反向电容注入，外部 DATA 仍持续翻转。',19)
text(35,646,'代价：增加输入电容、静态/交越及翻转功耗和传播延迟；须重新测实际接收余量。',19)
text(35,684,'保留缺口：TT 高电压短窗 ib1 达 3.639 V，仍超过 3.63 V 研究筛选；此图不是全角通过声明。',18)
save('b-input-buffer-circuit')
