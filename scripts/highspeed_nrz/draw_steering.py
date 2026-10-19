#!/usr/bin/env python3
"""Draw the frozen, actual nine-MOS steering prototype; no netlist edits.

All D/G/S/B connections and W/L values are embedded as SVG JSON metadata.
Net names are electrical connections, not a depiction of physical routing.
"""
from pathlib import Path
from html import escape
import hashlib, importlib.util, json

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('route_drawing',ROOT/'scripts/highspeed_routes/circuits.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
OUT=ROOT/'docs/research/highspeed-nrz-20261019/figures';OUT.mkdir(parents=True,exist_ok=True)
m.OUT=OUT
d=m.Drawing('单通道 NRZ：基线偏置 + 电流转向驱动',
 '实际 9 MOS 晶体管级电路 · GF180MCU 3.3 V MOS · TT，27 C；尺寸和端子对应冻结网表',1950)
details={}

def mos(x,y,tag,inst,nets,w,l,pmos=False,color=m.INK):
    d.mos(x,y,tag,nets,pmos,color)
    details[tag]=dict(netlist_instance=inst,terminals=dict(zip('DGSB',nets)),width_um=w,length_um=l,type='PMOS' if pmos else 'NMOS',
      diffusion_extension_um=.6,AD_m2=w*.6e-12,AS_m2=w*.6e-12,PD_m=2*(w+.6)*1e-6,PS_m=2*(w+.6)*1e-6)

def port(x,y,label,color=m.PURPLE,side='left'):
    # Named-net connector; no electrical distinction from a continuous wire.
    d.p.append(f'<circle cx="{x}" cy="{y}" r="5" fill="white" stroke="{color}" stroke-width="2"/>')
    d.text(x-10 if side=='left' else x+10,y-12,label,19,color,True,'end' if side=='left' else 'start')

def inv(x,name,gate,result):
    mos(x,265,'MP'+name,'XINV'+name+'P',[result,gate,'vdd','vdd'],2,.28,True,m.BLUE)
    mos(x,555,'MN'+name,'XINV'+name+'N',[result,gate,'0','0'],1,.28,False,m.ORANGE)
    d.line([(x,180),(x,213)],m.BLUE)
    d.text(x,164,'VDD = 3.3 V',20,m.BLUE,True,'middle')
    d.line([(x,317),(x,503)])
    d.dot(x,410)
    d.line([(x,607),(x,640)])
    d.ground(x,640)
    d.lines(x+37,293,['W/L=2/0.28 um','B = VDD'],16,24,m.MUTE)
    d.lines(x+37,583,['W/L=1/0.28 um','B = VSS'],16,24,m.MUTE)
    b=x-140
    d.line([(b,265),(x-62,265)],m.PURPLE)
    d.line([(b,265),(b,555),(x-62,555)],m.PURPLE)
    d.dot(b,410,m.PURPLE)
    return b

b1=inv(280,'1','data','gb');b2=inv(660,'2','gb','gp')
d.line([(48,410),(b1,410)],m.PURPLE)
d.lines(48,360,['DATA','0 / 3.3 V'],19,27,m.PURPLE,True)
d.text(48,620,'输入边沿 20 ps',17,m.MUTE)
d.line([(280,410),(b2,410)],m.PURPLE)
d.line([(455,410),(455,677)],m.PURPLE)
d.dot(455,410,m.PURPLE);port(455,677,'GB',side='right')
d.text(330,381,'GB = NOT(DATA)',18,m.PURPLE)
d.line([(660,410),(910,410)],m.PURPLE);port(910,410,'GP',side='right')
d.text(714,381,'GP = DATA',18,m.PURPLE)
d.text(230,701,'INV1',20,m.INK,True)
d.text(608,701,'INV2',20,m.INK,True)
d.box(1025,180,528,228,'互补信号由真实 MOS 产生',[
 'GB 经过 1 级反相器，GP 经过 2 级。',
 '两路不是理想同时互补，存在传播延迟偏差。',
 '转向瞬间可能出现双支路重叠或空档。',
 '这会改变尾节点 VX、电流波形和功耗。',
 '统一 PRBS 仿真已包含这些效应。'],m.PURPLE,size=18)
d.box(1025,445,528,228,'图中连接约定',[
 'GP、GB、BIAS：同名网络电气相连。',
 '为便于阅读，偏置线与高速控制线分区绘制。',
 '全部 NMOS 的体端 B 接 VSS = 0。',
 'PMOS 的体端 B 接 VDD = 3.3 V。',
 '体结由 PDK 模型包含；尺寸单位为 um。'],m.BLUE,size=18)
d.line([(48,733),(1552,733)],m.LIGHT,1.5)
d.text(48,774,'电流建立、转向与同一 MicroLED 负载',24,m.INK,True)

# Reference branch, resistor supply and diode-connected NMOS.
x=185
d.text(x,850,'VDD = 3.3 V',20,m.TEAL,True,'middle')
d.line([(x,865),(x,916)],m.TEAL)
d.resistor(x,960,'RREF = 88.386 kohm',m.TEAL)
d.line([(x,1004),(x,1278)],m.TEAL)
mos(x,1330,'MREF','XREF',['bias','bias','0','0'],2,1,color=m.TEAL)
d.line([(x-62,1330),(100,1330),(100,1180),(x,1180)],m.PURPLE)
d.dot(x,1180,m.TEAL)
d.line([(x,1180),(410,1180)],m.PURPLE);port(410,1180,'BIAS',side='right')
d.text(215,1133,'1.111721 V',18,m.TEAL,True)
d.line([(x,1382),(x,1520)]);d.ground(x,1520)
d.lines(226,1359,['W/L=2/1 um','D = G = BIAS','B = VSS'],16,24,m.MUTE)
d.arrow(144,1035,144,1110,m.TEAL)
d.text(48,1069,'IREF',17,m.TEAL)
d.lines(310,1457,['IREF = 24.758 uA','电阻偏置，尚非温补基准'],17,27,m.TEAL)

# Static measured LED branch. The assumed capacitor bypasses the 0 V monitor.
x=1020
d.text(x,820,'VLED = 5 V',20,m.ORANGE,True,'middle')
d.line([(x,835),(x,850)],m.ORANGE);d.dot(x,842,m.ORANGE)
d.p.append(f'<circle cx="{x}" cy="871" r="21" fill="white" stroke="{m.ORANGE}" stroke-width="2.6"/>')
d.text(x,877,'0 V',14,m.ORANGE,False,'middle')
d.text(760,864,'VMON：仅测 LED 传导电流',16,m.ORANGE)
d.line([(x,892),(x,901)],m.ORANGE)
d.led(x,943)
d.lines(752,928,['MicroLED','实测静态 I–V 模型'],18,28,m.ORANGE)
d.line([(x,985),(x,998)],m.ORANGE);d.dot(x,992,m.ORANGE)
d.resistor(x,1042,'Rpkg = 1 ohm',m.ORANGE)
d.line([(x,1086),(x,1092)],m.ORANGE)
d.p.append(f'<path d="M{x},1092 c18,0 18,8 0,8 c18,0 18,8 0,8 c18,0 18,8 0,8 c18,0 18,8 0,8" fill="none" stroke="{m.ORANGE}" stroke-width="2.7"/>')
d.text(x+30,1119,'Lpkg = 0.5 nH',17,m.ORANGE)
d.line([(x,1124),(x,1198)],m.ORANGE);d.dot(x,1147,m.ORANGE)
d.text(x-66,1175,'OUT',19,m.ORANGE,True)
d.line([(x,842),(1175,842),(1175,910)],m.ORANGE)
d.line([(1157,910),(1193,910)],m.ORANGE)
d.line([(1157,929),(1193,929)],m.ORANGE)
d.line([(1175,929),(1175,992),(x,992)],m.ORANGE)
d.lines(1195,920,['CLED','200 fF'],17,26,m.ORANGE)
d.text(1047,1016,'LED_K',16,m.ORANGE)

# Always-on 25uA baseline sink, electrically connected to the same OUT node.
x=645
d.line([(1020,1147),(x,1147),(x,1278)],m.ORANGE)
mos(x,1330,'MBASE','XBASE',['out','bias','0','0'],2,1,color=m.TEAL)
d.line([(x-62,1330),(545,1330)],m.PURPLE);port(545,1330,'BIAS')
d.line([(x,1382),(x,1520)]);d.ground(x,1520)
d.lines(x+36,1360,['W/L=2/1 um','B = VSS'],16,24,m.MUTE)
d.arrow(x-34,1188,x-34,1255,m.TEAL)
d.lines(443,1217,['常开基线','约 25 uA'],18,29,m.TEAL,True)

# Current-steering pair, dummy resistor, common source, tail sink.
mos(1020,1250,'ML','XLED',['out','gp','vx','0'],1,.28,color=m.ORANGE)
d.line([(958,1250),(915,1250)],m.PURPLE);port(915,1250,'GP')
d.lines(1056,1281,['W/L=1/0.28 um','B = VSS'],16,24,m.MUTE)
d.text(1370,850,'VDUMMY = 3.3 V',19,m.BLUE,True,'middle')
d.line([(1370,865),(1370,916)],m.BLUE)
d.resistor(1370,960,'RDUMMY',m.BLUE)
d.text(1400,995,'28 kohm',17,m.BLUE)
d.line([(1370,1004),(1370,1198)],m.BLUE)
d.text(1400,1142,'DUMMY',18,m.BLUE,True)
mos(1370,1250,'MD','XDUMMY',['dummy','gb','vx','0'],1,.28,color=m.BLUE)
d.line([(1308,1250),(1270,1250)],m.PURPLE);port(1270,1250,'GB')
d.lines(1406,1281,['W/L=1/0.28 um','B = VSS'],16,24,m.MUTE)
d.line([(1020,1302),(1020,1360),(1370,1360),(1370,1302)])
d.dot(1020,1360);d.line([(1020,1360),(1020,1408)])
d.text(1140,1390,'VX：公共源节点',19,m.INK,True)
mos(1020,1460,'MI','XTAIL',['vx','bias','0','0'],5.75895881652832,1,color=m.TEAL)
d.line([(958,1460),(915,1460)],m.PURPLE);port(915,1460,'BIAS')
d.line([(1020,1512),(1020,1540)]);d.ground(1020,1540)
d.lines(1056,1489,['W/L=5.75896/1 um','B = VSS；尾电流约 75 uA'],16,24,m.MUTE)
d.arrow(984,1390,984,1430,m.TEAL)
d.arrow(984,1178,984,1210,m.ORANGE)
d.arrow(1334,1178,1334,1210,m.BLUE)
d.text(1056,1218,'DATA = 1',17,m.ORANGE,True)
d.text(1400,1218,'DATA = 0',17,m.BLUE,True)

d.box(48,1597,730,206,'为什么低电平仍然有电流',[
 'DATA = 1：ML 导通，约 75 uA 加到基线电流上；',
 'LED 的 DC 目标为 25 + 75 = 100 uA。',
 'DATA = 0：MD 导通，尾电流流过 RDUMMY；',
 'LED 的 DC 目标仍为 25 uA，尾电流并未关闭。',
 '高速码型下，有限带宽使瞬时电流不再等于 DC 目标。'],m.TEAL,size=18)
d.box(802,1597,750,206,'能耗统计与模型边界',[
 '分别积分 VLED、VDD、VDUMMY 的供能；',
 'VDD 包含 MREF 参考支路及 4 MOS 前置驱动器。',
 '输入激励源、稳压器、接收机及光学功率尚未实测。',
 'CLED、Rpkg、Lpkg 为共同假设，尚非实测或 PEX。',
 'AD/AS = W × 0.6 um；扩散周长同样估计，尚非 PEX。'],m.BLUE,size=18)
d.footer(['同名网络相连；实心点为结点。各 MOS 的 D/G/S 已标注，B 连接与 W/L 同列；元数据保存完整端子映射。',
 '本图对应 steering_driver.spice 的预版图电路。DC 校准、瞬态眼图与能耗有各自证据边界；不能据此宣称光学 BER 或流片就绪。'])
d.save('steering-schematic')
p=OUT/'steering-schematic.svg'
metadata={'netlist':'analog/highspeed_nrz/steering_driver.spice','netlist_sha256':hashlib.sha256((ROOT/'analog/highspeed_nrz/steering_driver.spice').read_bytes()).hexdigest(),
 'devices':details,'device_count':len(details),'assumptions':{'cled_f':200e-15,'rpkg_ohm':1,'lpkg_h':.5e-9},
 'resistors_ohm':{'RREF':88386.1064910889,'RDUMMY':28000},'net_aliases':{'VSS':'0','GP':'gp','GB':'gb','BIAS':'bias','OUT':'out'}}
s=p.read_text().replace('原创教学示意。候选架构，未经高速晶体管或版图仿真。器件端子和电流方向有明确标注。',
 '原创电路原理图，对应真实 GF180MCU 晶体管级预版图仿真；采用实测静态 LED 曲线，动态电容和封装 R/L 为假设。')
s=s.replace('<style>',f'<metadata id="circuit-netlist-mapping">{escape(json.dumps(metadata,ensure_ascii=False))}</metadata><style>',1)
p.write_text(s)
assert len(details)==9
print(p)
