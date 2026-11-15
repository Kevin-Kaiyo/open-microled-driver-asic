#!/usr/bin/env python3
"""Draw actual v3r/v4 candidate deck connections; no simulation or passing claim."""
from pathlib import Path
import hashlib,json,sys
sys.dont_write_bytecode=True
import protection_physics as d
ROOT=d.ROOT;OUT=d.OUT
CASES={'v3r':'A-protected_v3r','v4':'B-protected_v4'}
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(kind):
 p=ROOT/'build/driver-interface-20261115/MicroLED'/CASES[kind]/'fault-f2-net1.6-s40';m=json.loads((p/'manifest.json').read_text());txt=(p/'testbench.spice').read_text();defs={x.split()[0]:x.split() for x in txt.splitlines() if x and x[0] not in ['+','*']}
 for name,nodes in {'XFASTOFF':['iso_p','iso_gb','led_feed','led_feed'],'XCLAMP':['led_a','disable','led_k','0'],'XLS_N1':['iso_g','en','0','0'],'XLS_N2':['iso_gb','disable','0','0'],'XLS_P1':['iso_g','iso_gb','led_feed','led_feed'],'XLS_P2':['iso_gb','iso_g','led_feed','led_feed']}.items():assert defs[name][1:5]==nodes
 for k in range(3):assert defs['XISO'+str(k)][1:5]==['led_a','iso_p','led_feed','led_feed']
 assert defs['RGATE'][1:]==['iso_g','iso_p','100k'];assert defs['XFASTOFF'][6:8]==['w=20u','l=0.7u']
 if kind=='v3r':assert defs['RDISABLE'][1:]==['disable_src','disable','100'] and len(m['devices'])==31
 else:
  assert 'RDISABLE' not in defs and len(m['devices'])==39
  for name,nodes in {'XREADYRESET':['ready_rc','disable','0','0'],'XNAND_PDATA':['nand_o','d0','vdd','vdd'],'XNAND_PREADY':['nand_o','ready_rc','vdd','vdd'],'XNAND_NDATA':['nand_o','d0','nand_s','0'],'XNAND_NREADY':['nand_s','ready_rc','0','0'],'XSAFE_N':['data_safe','nand_o','0','0'],'XSAFE_P':['data_safe','nand_o','vdd','vdd']}.items():assert defs[name][1:5]==nodes
  assert defs['RREADY'][1:]==['en','ready_rc','100k'] and defs['CREADY'][1:]==['ready_rc','0','1p'];assert defs['XDRV'][1]=='data_safe' and defs['XDRV'][8]=='0'
 return p,m,defs
def begin(height,title,subtitle):
 d.S.clear();d.S.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="1340" height="{height}" viewBox="0 0 1340 {height}"><style>text{{font-family:"Arial Unicode MS","PingFang SC",Arial,sans-serif}}</style><rect width="1340" height="{height}" fill="#f7f9fb"/>');d.text(35,45,title,27);d.text(35,80,subtitle,18,c=d.GRAY)
def box(y,h,title):
 d.S.append(f'<rect x="25" y="{y}" width="1290" height="{h}" rx="10" fill="white" stroke="#d2dce4"/>');d.text(45,y+34,title,23)
def label_size(defs,name,x,y):
 w=defs[name][6].split('=')[1].rstrip('u');l=defs[name][7].split('=')[1].rstrip('u');d.text(x,y,f'W/L = {w}/{l}',16)
def stacked(x,y,pname,nname,p_gate,n_gate,rail,defs,join_gate=False):
 d.mos(x,y-65,True,pname,p_gate);d.mos(x,y+65,False,nname,n_gate)
 d.line(x+36,y-8,x+36,y+8);d.dot(x+36,y);d.line(x+36,y-122,x+36,y-145);d.text(x+36,y-158,rail,18,'middle');d.ground(x+36,y+122)
 label_size(defs,pname,x+53,y-40);label_size(defs,nname,x+53,y+90)
 if join_gate:
  d.line(x-54,y-65,x-75,y-65);d.line(x-75,y-65,x-75,y+65);d.line(x-75,y+65,x-54,y+65)
def finish(kind,p,m,defs):
 d.S.append('</svg>');svg=OUT/f'micro-protection-{kind}.svg';svg.write_text('\n'.join(d.S)+'\n')
 import cairosvg
 cairosvg.svg2png(url=str(svg),write_to=str(svg.with_suffix('.png')),scale=1.3)
 receipt=dict(status='candidate_schematic_not_qualification',source_case=str(p.relative_to(ROOT)),manifest_sha256=sha(p/'manifest.json'),deck_sha256=sha(p/'testbench.spice'),generator_sha256=sha(Path(__file__)),drawing_helper_sha256=sha(Path(d.__file__)),MOS_count=len(m['devices']),top_level_added_MOS={k:v for k,v in defs.items() if k.startswith(('XEN','XLS','XISO','XCLAMP','XFAST','XREADY','XNAND','XSAFE'))},source_ports=m['sources'],scope='Drawn from actual candidate netlist. W20 fast-off remains explicit. No new SPICE, no PEX, no final passing claim. Same named nets are connected. Internal existing reference/core omitted where stated.')
 (OUT/f'micro-protection-{kind}.source.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(svg)
def v3r():
 p,m,defs=load('v3r');begin(1340,'A · protected_v3r：实际慢开 / 快关保护候选','新增 11 MOS；连同既有 A 核心共 31 MOS。W/L 单位为 µm；同名网络相连。验证状态以报告为准。')
 box(110,455,'1｜3.3 V 保护命令与 5 V 电平转换')
 d.text(55,185,'VDISABLE / disable_src',18);d.line(55,200,275,200);d.resistor(275,200,420,'RDISABLE 100 Ω');d.line(420,200,540,200);d.text(460,182,'disable',19)
 stacked(210,365,'XEN_P','XEN_N','disable','disable','',defs,True);d.text(270,235,'vdd ≈ 3.3 V',18);d.line(246,365,415,365);d.text(350,344,'en = NOT(disable)',18)
 stacked(650,365,'XLS_P1','XLS_N1','iso_gb','en','led_feed ≈ 5 V',defs)
 stacked(1035,365,'XLS_P2','XLS_N2','iso_g','disable','led_feed ≈ 5 V',defs)
 d.line(686,365,820,365);d.text(720,344,'iso_g',20);d.line(1071,365,1235,365);d.text(1145,344,'iso_gb',20)
 d.text(45,542,'上排 PMOS 体接各自源轨；下排 NMOS 体接 VSS。交叉 PMOS 栅分别接 iso_gb / iso_g。',17,c=d.GRAY)
 box(590,650,'2｜输出 PMOS 共栅慢开，XFASTOFF 快速关断；LED 两端另有钳位')
 d.text(55,695,'VLED / led_src',18);d.line(55,710,160,710);d.resistor(160,710,320,'既有 0.25 Ω');d.line(320,710,966,710);d.text(650,685,'led_feed（PISO 与 XFASTOFF 的 S/B）',19,'middle')
 d.mos(450,820,True,'XFASTOFF','iso_gb');d.line(486,763,486,710);d.line(486,877,486,910);label_size(defs,'XFASTOFF',503,846)
 d.text(45,898,'iso_g',20);d.line(45,910,145,910);d.resistor(145,910,345,'RGATE 100 kΩ');d.line(345,910,820,910);d.dot(486,910);d.text(500,935,'iso_p：实际功率管共栅',19)
 d.mos(930,820,True,'XISO0..2','');d.line(966,763,966,710);d.line(966,877,966,970);d.line(820,910,820,820);d.line(820,820,876,820);d.text(983,846,'每只 100 / 0.7，3 只并联',17)
 d.line(650,970,1156,970);d.dot(966,970);d.text(980,955,'LED_A',20)
 d.cap(650,970,1150,'');d.text(620,1030,'CLED 200 fF',18,'end');d.diode(820,970,1150,True);d.text(820,945,'MicroLED',18,'middle')
 d.mos(1120,1060,False,'XCLAMP','disable');d.line(1156,1003,1156,970);d.line(1156,1117,1156,1150);label_size(defs,'XCLAMP',1173,1085)
 d.line(650,1150,1156,1150);d.dot(820,1150);d.text(840,1180,'LED_K；XCLAMP 的 S，B = VSS',18)
 d.resistor(470,1150,570,'RPKG 1 Ω');d.line(570,1150,650,1150);d.inductor(330,1150,450,'LPKG 0.5 nH');d.line(450,1150,470,1150);d.line(230,1150,330,1150);d.text(170,1157,'OUT',21)
 d.text(35,1280,'关断：iso_gb 低，XFASTOFF 给 iso_p 充电；恢复：iso_gb 高，iso_p 经 100 kΩ 放电。实际速度须看波形。',18)
 d.text(35,1310,'100 Ω 仅是 A-v3r 保护命令接口的一部分；所有 7 个已有源仍计能。图未展开原参考源/六管输出核心，未取得新版图或保护资格。',17,c=d.GRAY)
 finish('v3r',p,m,defs)
def v4():
 p,m,defs=load('v4');begin(1260,'B · protected_v4：真实 READY RC 与 6 MOS 数据门控候选','本图展开新增 7 MOS；加上 11 MOS 高边保护，整条 B 电路共 39 MOS。外部数据继续翻转，候选仍在验证。')
 box(110,390,'1｜ready_rc 慢充 / 快复位：开环延迟允许，不是电源良好检测')
 d.text(65,205,'en = NOT(disable)',19);d.line(65,225,230,225);d.resistor(230,225,405,'RREADY 100 kΩ');d.line(405,225,1150,225);d.dot(450,225);d.dot(706,225);d.text(1000,207,'ready_rc',21)
 d.cap(450,225,415,'');d.text(425,350,'CREADY 1 pF',18,'end');d.ground(450,415)
 d.mos(670,330,False,'XREADYRESET','disable');d.line(706,273,706,225);d.ground(706,387);label_size(defs,'XREADYRESET',723,356)
 d.text(885,329,'RC 量级 = 100 ns',20);d.text(885,360,'实际门限/允许时间由 MOS 决定',17);d.text(885,391,'并非理想 100 ns 延时器',17,c=d.GRAY)
 d.text(45,475,'disable 高时复位管主动放电；disable 低时从 en 经电阻充电。复位和充电都有真实有限速度与能耗。',18,c=d.GRAY)
 box(520,620,'2｜静态 CMOS NAND + 反相器：data_safe = d0 AND ready_rc')
 # Parallel PMOS pull-up, two NMOS in series, output inverter; all3.3V.
 d.line(236,600,1076,600);d.text(685,583,'vdd ≈ 3.3 V；所有 PMOS 体接 vdd，NMOS 体接 VSS',18,'middle')
 d.mos(200,680,True,'XNAND_PDATA','d0');d.line(236,623,236,600);d.line(236,737,236,790);label_size(defs,'XNAND_PDATA',253,707)
 d.mos(550,680,True,'XNAND_PREADY','ready_rc');d.line(586,623,586,600);d.line(586,737,586,790);label_size(defs,'XNAND_PREADY',603,707)
 d.line(236,790,900,790);d.dot(386,790);d.dot(586,790);d.text(690,770,'nand_o',21)
 d.mos(350,855,False,'XNAND_NDATA','d0');d.line(386,798,386,790);label_size(defs,'XNAND_NDATA',403,882)
 d.mos(350,1040,False,'XNAND_NREADY','ready_rc');d.line(386,912,386,983);d.text(401,951,'nand_s',18);d.ground(386,1097);label_size(defs,'XNAND_NREADY',403,1067)
 # Two MOS restoring inverter; source rails explicit.
 d.mos(1040,725,True,'XSAFE_P','');d.mos(1040,855,False,'XSAFE_N','');d.line(1076,782,1076,798);d.dot(1076,790);d.line(1076,668,1076,600);d.ground(1076,912)
 d.line(986,725,965,725);d.line(965,725,965,855);d.line(965,855,986,855);d.line(900,790,965,790);d.dot(965,790)
 label_size(defs,'XSAFE_P',1093,752);label_size(defs,'XSAFE_N',1093,882);d.line(1076,790,1270,790);d.text(1165,770,'data_safe',21,'middle')
 d.text(800,995,'data_safe → XDRV.D0 → 既有 XRIN → DI / GB / GP',18)
 d.text(800,1025,'d0 仍由 VD0 经既有 100 Ω 提供；VD0 的原 PRBS 不变。',17)
 d.text(800,1055,'XDRV.DISABLE 接 0：参考源保持工作，额外功耗保留。',17)
 d.text(800,1085,'慢 RC 直接进入 NAND；首次脉冲与接收恢复必须实测。',17,c=d.GRAY)
 d.text(35,1180,'高边 11 MOS 与 A-v3r 的慢开/快关连接相同：RGATE=100 kΩ、XFASTOFF=20/0.7、PISO=3×100/0.7；B 不加命令源 100 Ω。',17)
 d.text(35,1210,'输入门控的 MOS、CREADY、命令栅充电计入既有 VDD / VD0 / VDISABLE；无理想 delay、理想 AND 或新增免费电源。',17)
 d.text(35,1240,'此图对应 W20 的实际 v4 网表，不代表后续 W4 修改或验证通过；PVT、误码、保护与版图资格仍需分别闭合。',17,c=d.GRAY)
 finish('v4',p,m,defs)
if __name__=='__main__':v3r();v4()
