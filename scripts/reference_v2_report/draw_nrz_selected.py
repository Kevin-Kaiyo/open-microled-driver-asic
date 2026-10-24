#!/usr/bin/env python3
"""Selected NRZ reference/disable/dummy circuit; fast buffer detail is linked separately."""
from pathlib import Path
import importlib.util,json,hashlib
ROOT=Path(__file__).resolve().parents[2];sp=importlib.util.spec_from_file_location('draw',ROOT/'scripts/highspeed_routes/circuits.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
OUT=ROOT/'docs/research/nrz-b-reference-power-20261024/figures';OUT.mkdir(parents=True,exist_ok=True);m.OUT=OUT
CFG=json.loads((ROOT/'layout/highspeed_nrz_robustness/selected-design.json').read_text())['routes']['B'];D={x['name']:x for x in CFG['devices']}
d=m.Drawing('高速 B：真实电流参考、独立禁止与 5 V dummy 供电','选定候选：10 MOS V-to-I + 2只保护MOS + 原9 MOS高速核心；原LED模型、200fF、接收器保持',1420)
def device(x,y,name,inst):
 s=D[inst];nets=s['nodes'];d.mos(x,y,name,nets,'pfet' in s['model'],label=False);d.text(x+34,y-8,name,19,m.INK,True);d.text(x+34,y+22,s['model'],16,m.MUTE)

def cp(x,y,label):
 d.line([(x,y-42),(x,y-8)]);d.line([(x-20,y-8),(x+20,y-8)]);d.line([(x-20,y+8),(x+20,y+8)]);d.line([(x,y+8),(x,y+42)]);d.text(x+27,y+7,label,18)

d.box(48,180,520,200,'10 MOS 电流参考（另图展开）',['VIN = 5 V；外部 VREF = 2.5 V','分压 VSET = 0.5 V；RSET = 20 kohm','IN2 经 150 pF 补偿至板地','IOUT 输出至原核心 BIAS'],size=19)
d.line([(350,380),(350,680)]);d.dot(350,610,m.TEAL);d.text(375,590,'BIAS / IOUT',22,m.TEAL,True)
device(350,820,'MREF','REF');d.line([(350,680),(350,768)]);d.line([(288,820),(270,820),(270,680),(350,680)],m.PURPLE);d.dot(350,680)
d.line([(350,872),(350,1100)]);d.ground(350,1100)
d.line([(350,610),(100,610),(100,768)],m.TEAL);d.mos(100,820,'DIS',['BIAS','DISABLE','VSS','VSS'],label=False);d.text(135,812,'MDIS',19,m.INK,True);d.text(120,900,'06v0 / 10/0.7 um',17,m.MUTE);d.line([(100,872),(100,1100)]);d.ground(100,1100)
d.line([(38,820),(20,820),(20,740)]);d.text(20,718,'DISABLE 经 100 ohm',18,m.PURPLE,True)
d.lines(130,950,['高：钳位 BIAS','低：允许电流建立','驱动端串联 100 ohm'],18,28)
# Named BIAS connection avoids an ambiguous line crossing through high-speed nodes.
d.line([(588,820),(555,820)],m.PURPLE);d.text(535,797,'BIAS',18,m.PURPLE,True)
device(650,820,'MBASE','BASE');d.line([(650,872),(650,1100)]);d.ground(650,1100)
# LED and the fixed parallel electrical capacitor.
d.text(950,196,'VLED = 5 V',22,m.ORANGE,True,'middle');d.line([(950,212),(950,268)],m.ORANGE);d.dot(950,245,m.ORANGE);d.led(950,310);d.text(1025,306,'MicroLED',20,m.ORANGE,True)
d.line([(950,352),(950,395)],m.ORANGE);d.dot(950,375,m.ORANGE)
d.line([(950,245),(1150,245),(1150,268)],m.ORANGE);cp(1150,310,'200 fF');d.line([(1150,352),(1150,375),(950,375)],m.ORANGE)
d.resistor(950,439,'Rpkg 1 ohm',m.ORANGE);d.line([(950,483),(950,500)],m.ORANGE);d.p.append(f'<path d="M950,500 c20,0 20,10 0,10 c20,0 20,10 0,10 c20,0 20,10 0,10 c20,0 20,10 0,10" fill="none" stroke="{m.ORANGE}" stroke-width="2.7"/>');d.text(985,527,'Lpkg 0.5 nH',18,m.ORANGE)
d.line([(950,540),(950,678)],m.ORANGE);d.dot(950,620,m.ORANGE);d.text(970,598,'OUT',21,m.ORANGE,True)
d.line([(950,620),(650,620),(650,768)],m.ORANGE)
d.line([(950,620),(800,620),(800,780)]);d.dot(800,620);d.resistor(800,824,'RKEEP',m.TEAL);d.text(830,866,'1.8 Mohm',17,m.TEAL);d.line([(800,868),(800,958)]);d.mos(800,1010,'MK',['KRET','DISABLE','VSS','VSS'],label=False);d.text(835,990,'MK',18,m.INK,True);d.text(835,1016,'06v0',14,m.MUTE);d.text(790,1152,'MK W/L = 1/0.7 um',16,m.MUTE,anchor='middle');d.line([(738,1010),(700,1010)],m.PURPLE);d.text(690,983,'DISABLE',16,m.PURPLE);d.line([(800,1062),(800,1100)]);d.ground(800,1100)
device(950,730,'ML','LED');d.line([(888,730),(860,730)],m.PURPLE);d.text(837,706,'GP',18,m.PURPLE,True)
# Real raw rail feeds the dummy resistor; no ideal3.3V generator remains.
d.text(1360,196,'VIN = 5 V',22,m.BLUE,True,'middle');d.line([(1360,212),(1360,395)],m.BLUE);d.resistor(1360,439,'RDUMMY',m.BLUE);d.text(1390,485,'50 kohm',17,m.BLUE);d.line([(1360,483),(1360,678)],m.BLUE)
device(1360,730,'MD','DUMMY');d.line([(1298,730),(1270,730)],m.PURPLE);d.text(1248,706,'GB',18,m.PURPLE,True)
d.line([(950,782),(950,920),(1360,920),(1360,782)]);d.dot(950,920);d.text(1110,950,'VX：公共源',19)
device(950,1030,'MTAIL','TAIL');d.line([(950,920),(950,978)]);d.line([(888,1030),(860,1030)],m.PURPLE);d.text(830,1068,'BIAS',18,m.PURPLE,True);d.line([(950,1082),(950,1120)]);d.ground(950,1120)
d.box(1100,1010,445,168,'数字高速路径保持',['DATA -> RIN -> INV1 / INV2','GP、GB 驱动 ML、MD','反相器4 MOS另见原核心图','低电平仍有基础 LED 电流'],size=18)
d.arrow(918,550,918,600,m.ORANGE);d.text(1000,690,'DATA = 1',18,m.ORANGE,True);d.arrow(1325,540,1325,600,m.BLUE);d.text(1390,690,'DATA = 0',18,m.BLUE,True)
d.box(48,1185,1504,108,'电流与电压保护的两个独立作用',['DIS 钳位防止参考未稳定时向 LED 输出大电流；RKEEP + MK 在禁止期间泄放，避免 OUT 悬空使 03v3 MBASE 端压过大。','正常通信时 MK 关闭，消除常接 RKEEP 造成的低电平电流偏移；完整模型仍保留其泄漏及寄生。'],size=18)
d.footer(['同名网络相连；PMOS体端按电源接法、NMOS体端接VSS。参考基准、设定电阻、补偿和去耦目前在片外建模。','图中为逻辑连接，未画完所有供电封装R/L；以冻结最终网表为准。禁止信号来自外部控制，未宣称自主POR。'])
r=d.save('selected-b-circuit');p=OUT/'selected-b-circuit.svg';p.write_text(p.read_text().replace('原创教学示意。候选架构，未经高速晶体管或版图仿真。器件端子和电流方向有明确标注。','所选候选的实际逻辑电路；完整物理与电气接受状态见对应研究报告。'))
r['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();r['source_hashes']={str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest() for q in [ROOT/'analog/nrz_reference_v2/vi_reference_switched_keeper.spice',ROOT/'layout/highspeed_nrz_robustness/selected-design.json']}
(OUT/'selected-b-circuit-manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
