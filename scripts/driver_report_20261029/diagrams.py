#!/usr/bin/env python3
"""Source-bound engineering drawings. Parallel symbols are explicit electrical groups."""
from pathlib import Path
from html import escape
import argparse,hashlib,importlib.util,json,re
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/vcsel-reference-microled-dynamics-20261029/figures'
EV=ROOT/'evidence/vcsel-robustness-20261029'
s=importlib.util.spec_from_file_location('primitive',ROOT/'scripts/highspeed_routes/circuits.py')
p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
INK,TEAL,BLUE,PURPLE,MUTE,LIGHT=p.INK,p.TEAL,p.BLUE,p.PURPLE,p.MUTE,p.LIGHT
DEV={};RECORDS=[];PARAMS={};PASSIVES={};REGTARGET=3.1
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class D(p.Drawing):
 def text(self,x,y,s,*args,**kwargs):
  s=str(s).replace('Ω','ohm').replace('−','-').replace('→',' > ').replace('≈','~').replace('×','x').replace('µ','u').replace('²','^2')
  return super().text(x,y,s,*args,**kwargs)
 def __init__(self,title,subtitle,height=1160):
  self.groups=[];super().__init__(title,subtitle,height)
 def mos_group(self,x,y,ids):
  ds=[DEV[k] for k in ids];a=ds[0]
  assert all(z['nets']==a['nets'] and z['model']==a['model'] and z['w']==a['w'] and z['l']==a['l'] for z in ds)
  label=ids[0] if len(ids)==1 else ids[0]+' ... ×'+str(len(ids))
  pm=a['model'].startswith('p');self.mos(x,y,label,a['nets'],pm,label=False)
  self.line([(x-10,y),(x+25,y)],INK,2)
  pts=[(x-8,y),(x+2,y-5),(x+2,y+5)] if not pm else [(x+15,y),(x+5,y-5),(x+5,y+5)]
  self.p.append('<polygon points="'+' '.join(f'{u},{v}' for u,v in pts)+f'" fill="{INK}"/>')
  self.text(x+36,y-38,label,17,BLUE,True)
  w={'{WBASE}':'60u','{WTAIL}':'84u'}.get(a['w'],a['w'])
  self.text(x+36,y-14,'W/L '+w+'/'+a['l'],16,MUTE)
  self.text(x+36,y+12,'B='+a['nets'][3],15,MUTE)
  self.groups.append(dict(instances=ids,**a))
 def named(self,x,y,ids,continued=False):
  self.mos_group(x,y,ids);a=DEV[ids[0]];pm=a['model'].startswith('p')
  self.line([(x,y-52),(x,y-80)]);self.line([(x,y+52),(x,y+82)])
  self.text(x,y-94,a['nets'][2 if pm else 0],18,TEAL,True,'middle')
  self.text(x+30 if continued else x,y+108,a['nets'][0 if pm else 2],18,TEAL,True,'start' if continued else 'middle')
  self.text(x-72,y-22 if continued else y+7,a['nets'][1],17,PURPLE,False,'end')
 def cap(self,x,y,label,horizontal=False):
  if horizontal:
   self.line([(x-45,y),(x-7,y)]);self.line([(x+7,y),(x+45,y)])
   self.line([(x-7,y-22),(x-7,y+22)]);self.line([(x+7,y-22),(x+7,y+22)])
   self.text(x,y-35,label,17,MUTE,False,'middle')
  else:
   self.line([(x,y-40),(x,y-6)]);self.line([(x,y+6),(x,y+40)])
   self.line([(x-22,y-6),(x+22,y-6)]);self.line([(x-22,y+6),(x+22,y+6)])
   self.text(x+30,y+6,label,17,MUTE)
 def triangle(self,x,y,label,positive,negative):
  self.p.append(f'<polygon points="{x},{y-75} {x},{y+75} {x+160},{y}" fill="#f3f7f8" stroke="{BLUE}" stroke-width="2.5"/>')
  self.text(x+16,y-28,'+',24,BLUE);self.text(x+16,y+41,'−',24,BLUE)
  self.text(x+57,y+5,label,18,BLUE,True)
  self.text(x-12,y-45,positive,18,PURPLE,False,'end');self.text(x-12,y+23,negative,18,TEAL,False,'end')
 def save_new(self,name):
  colors=[INK,p.ORANGE,TEAL,PURPLE,BLUE]
  defs=''.join(f'<marker id="a{c[1:]}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="{c}"/></marker>' for c in colors)
  svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{self.height}" viewBox="0 0 1600 {self.height}" role="img"><title>{escape(self.title)}</title><desc>源网表绑定原理图；同名网络电气相连。并联组不是版图指状结构或独立测量。</desc><defs>{defs}</defs><style>text{{font-family:"PingFang SC","Noto Sans CJK SC",Arial,sans-serif}}polyline,path{{stroke-linejoin:round;stroke-linecap:round}}</style><rect width="1600" height="{self.height}" fill="white"/>'+''.join(self.p)+'</svg>\n'
  file=OUT/(name+'.svg');file.write_text(svg)
  RECORDS.append(dict(path=str(file.relative_to(ROOT)),sha256=sha(file),groups=self.groups))

def group(prefix):return [k for k in DEV if k.startswith(prefix)]

def core():
 d=D('电流控制核心：低频反馈设定电流，高速开关选择路径','真实 MOS 与感测电阻；OTA 内部在后续图展开。VL 来自激光支路稳压器，GP/GN 来自真实缓冲。',1320)
 d.line([(400,190),(1360,190)],TEAL);d.text(400,172,f'VL 目标 {REGTARGET:.2f} V（低输入时 dropout）',21,TEAL,True)
 d.line([(710,190),(710,238)]);d.led(710,280);d.line([(710,322),(710,420)])
 d.text(755,285,'VCSEL + 封装 R/L',21,p.ORANGE,True);d.text(755,319,'保持上一轮负载',17,MUTE)
 d.line([(1330,190),(1330,236)]);d.resistor(1330,280,'RDUMMY 500 Ω');d.line([(1330,324),(1330,478)])
 d.dot(710,420);d.text(720,411,'OUT',20,TEAL,True)
 d.line([(710,420),(410,420),(410,548)]);d.text(432,488,'VIBASE：0 V 测流探针',17,MUTE)
 d.line([(710,420),(880,420),(880,478)])
 d.mos_group(410,600,group('XBASE'))
 d.mos_group(880,530,group('XSTEER'))
 d.mos_group(1330,530,group('XDUMP'))
 d.text(808,530,'GP',19,PURPLE,True,'end');d.text(1258,530,'GN',19,PURPLE,True,'end')
 d.text(1340,450,'DUMMY',19,TEAL,True)
 d.line([(880,582),(880,700),(1330,700),(1330,582)])
 d.dot(1080,700);d.text(1100,692,'VX',20,TEAL,True)
 d.line([(1080,700),(1080,848)]);d.text(1100,780,'VITAIL：0 V 测流探针',17,MUTE)
 d.mos_group(1080,900,group('XTAIL'))
 d.line([(410,652),(410,806)]);d.dot(410,730);d.text(432,734,'SBASE',19,TEAL,True)
 d.resistor(410,850,'RBASE 50 Ω');d.line([(410,894),(410,942)]);d.ground(410,942)
 d.line([(1080,952),(1080,1016)]);d.dot(1080,980);d.text(1100,991,'STAIL',19,TEAL,True)
 d.resistor(1080,1060,'RTAIL 37.5 Ω');d.line([(1080,1104),(1080,1140)]);d.ground(1080,1140)
 d.triangle(175,550,'OTA-B','VSET','')
 d.line([(335,550),(348,550),(348,600)],PURPLE);d.text(344,514,'BCTRL',17,PURPLE,True)
 d.line([(410,730),(90,730),(90,590),(175,590)],TEAL)
 d.triangle(790,890,'OTA-T','VSET','')
 d.line([(950,890),(995,890),(995,900),(1018,900)],PURPLE);d.text(977,855,'TCTRL',17,PURPLE,True)
 d.line([(1080,980),(720,980),(720,930),(790,930)],TEAL)
 d.lines(85,1040,['VSET = 0.15 V（外部精密电压接口）','IBIAS ≈ 0.15 / 50 = 3 mA','IMOD ≈ 0.15 / 37.5 = 4 mA'],21,35)
 d.footer(['D=1：IMOD 经 VCSEL → XSTEER → XTAIL；D=0：IMOD 经 RDUMMY → XDUMP → XTAIL。IBIAS 两态都存在。',
           '图中 ×N 表示源网表中 N 只相同并联 MOS。体端依 B 标签；OTA 由 VREF 供电，三角形并非理想放大器。'])
 d.save_new('servo-current-core')

def ota(q,title):
 d=D(title,'PMOS 输入对 + NMOS 镜像负载 + 共源第二级；器件名和网络标签直接来自冻结网表。',1390)
 power=DEV['X'+q+'T_0']['nets'][2];bias=DEV['X'+q+'T_0']['nets'][1]
 d.mos_group(760,300,group('X'+q+'T_'))
 d.line([(760,248),(760,205)]);d.text(760,185,power,20,TEAL,True,'middle')
 d.text(688,305,bias,18,PURPLE,False,'end')
 d.line([(760,352),(760,410),(470,410),(470,468)]);d.line([(760,410),(910,410),(910,468)]);d.dot(760,410)
 d.mos_group(470,520,group('X'+q+'P1_'));d.mos_group(910,520,group('X'+q+'P2_'))
 d.text(398,525,DEV['X'+q+'P1_0']['nets'][1],19,PURPLE,True,'end');d.text(838,525,DEV['X'+q+'P2_0']['nets'][1],19,PURPLE,True,'end')
 d.line([(470,572),(470,758)]);d.line([(910,572),(910,758)])
 d.mos_group(470,810,group('X'+q+'N1_'));d.mos_group(910,810,group('X'+q+'N2_'))
 d.dot(470,650);d.text(480,630,q+'n1',18,TEAL,True)
 d.line([(470,650),(365,650),(365,810),(408,810)])
 d.line([(365,720),(805,720),(805,810),(848,810)]);d.dot(365,720)
 for x in [470,910]:d.line([(x,862),(x,915)]);d.ground(x,915)
 d.dot(910,650);d.text(930,638,q+'n2',18,TEAL,True)
 d.mos_group(1320,420,group('X'+q+'PL_'));d.mos_group(1320,810,group('X'+q+'NS_'))
 d.line([(1320,368),(1320,205)]);d.text(1320,185,power,20,TEAL,True,'middle')
 d.line([(1320,472),(1320,758)]);d.dot(1320,600);d.line([(1320,600),(1510,600)])
 d.text(1495,578,DEV['X'+q+'NS_0']['nets'][0],19,PURPLE,True,'end')
 d.text(1248,425,bias,18,PURPLE,False,'end')
 d.line([(910,650),(1155,650),(1155,810),(1258,810)])
 d.line([(1320,862),(1320,915)]);d.ground(1320,915)
 cap=PARAMS['CLDO']+'F' if q in ['L','D'] else PARAMS['CC']+'F'
 d.cap(1130,1055,'C'+q+'MILLER = '+cap,True)
 if 'R'+q+'ZERO' in PASSIVES:
  val=PASSIVES['R'+q+'ZERO'][-1];val=PARAMS.get(val.strip('{}'),val)
  d.line([(1085,1055),(1020,1055)]);d.p.append(f'<rect x="960" y="1043" width="60" height="24" fill="white" stroke="{INK}" stroke-width="2.7"/>')
  d.line([(960,1055),(870,1055)]);d.text(860,1063,q+'n2',19,TEAL,True,'end');d.text(990,1120,'R'+q+'ZERO '+val+' ohm',17,MUTE,False,'middle');d.text(1058,1085,q+'zc',16,TEAL,False,'middle')
 else:
  d.line([(1085,1055),(930,1055)]);d.text(920,1063,q+'n2',19,TEAL,True,'end')
 d.line([(1175,1055),(1340,1055)]);d.text(1350,1063,DEV['X'+q+'NS_0']['nets'][0],19,PURPLE,True)
 b={'B':'XAB_0','T':None,'L':'XLB_0','D':'XDB_0'}[q]
 if b:
  d.named(160,1060,[b]);d.text(250,1180,'二极管连接偏置管：D、G 同名相连',17,MUTE)
  d.text(550,984,bias,18,TEAL,True,'middle');d.line([(550,1000),(550,1036)])
  d.resistor(550,1080,'RBIAS 100 kohm');d.line([(550,1124),(550,1150)]);d.ground(550,1150)
 else:d.lines(80,1070,['ABIAS 与 OTA-B 共用；','不复制一套理想尾电流源。'],20,32)
 d.footer(['所有 D/G/S/B 及并联实例见图源清单。输入误差经两级放大后调整控制栅；补偿电容用于控制环路动态。',
           '这里只展开连接。增益、启动与受扰恢复应看仿真；近似 AC 诊断不替代稳定性签核、噪声/失配或版图提取。'])
 d.save_new('ota-'+q.lower())

def rails():
 d=D('两条实际 MOS 稳压支路：为 dummy 与缓冲器留下端压余量','激光支路 VL 与缓冲支路 DR 分开调节；外部供电与输入数据幅度仍采用原工况。',1690)
 for q,raw,out,y in [('L','VLASER','VL',340),('D','VDD','DR',1010)]:
  d.text(70,y-145,raw+' → '+out,25,BLUE,True)
  d.named(950,y,group('X'+q+'PASS_'),continued=True)
  d.text(1170,y-100,'10 × 100u/0.28u PMOS',20,MUTE)
  d.line([(950,y+82),(950,y+160),(1370,y+160)])
  d.dot(1140,y+160);d.line([(1140,y+160),(1140,y+186)])
  d.resistor(1140,y+230,'85 kΩ');d.line([(1140,y+274),(1140,y+326)]);d.dot(1140,y+300)
  d.resistor(1140,y+370,'10 kΩ');d.line([(1140,y+414),(1140,y+450)]);d.ground(1140,y+450)
  d.triangle(570,y+160,'OTA-'+q,q+'fb','VREGSET')
  d.line([(730,y+160),(815,y+160),(815,y),(888,y)],PURPLE)
  d.line([(1140,y+300),(460,y+300),(460,y+125),(570,y+125)],TEAL)
  d.resistor(1370,y+230,'0.1 Ω');d.line([(1370,y+160),(1370,y+186)])
  cv=PASSIVES['C'+q+'OUT'][-1];cv=PARAMS.get(cv.strip('{}'),cv)
  d.cap(1370,y+350,'Cout '+cv+'F');d.line([(1370,y+274),(1370,y+310)]);d.line([(1370,y+390),(1370,y+450)]);d.ground(1370,y+450)
  d.lines(65,y+20,[f'VREGSET = {REGTARGET/9.5:.6f} V','VOUT ≈ VREGSET × (1 + 85/10)',f'目标 {REGTARGET:.2f} V；低压 dropout 时达不到目标。'],19,31)
  if 'R'+q+'BLEED' in PASSIVES:
   val=PARAMS['RBLEED'];d.line([(950,y+160),(950,y+326)]);d.dot(950,y+160);d.resistor(950,y+370,'');d.text(900,y+358,'R'+q+'BLEED',17,MUTE,False,'end');d.text(900,y+385,val+' ohm',17,MUTE,False,'end');d.line([(950,y+414),(950,y+450)]);d.ground(950,y+450)
 d.footer(['每个 OTA 内部与 Miller 补偿在独立图展开；Cout 与电阻为原理图假设的无源器件，尚未做片上面积/封装实现。',
           'VLASER/VDD/VREF/VSET/VREGSET 与两个数据端口全部纳入供能统计；外部精密基准内部功耗另作系统预算。'])
 d.save_new('regulated-rails')

def buffers():
 d=D('缓冲器：保留真实两级 CMOS，输入增加有耗衰减','原 D/DB 源幅度不变。串联 200 Ω、对地 2.5 kΩ 的网络参与瞬态和输入端口能量。',1510)
 for lab,di,nd,gate,y in [('P','DI','NP','GP',360),('N','DBI','NN','GN',970)]:
  d.text(65,y-175,('D → DI' if lab=='P' else 'DB → DBI')+' → '+nd+' → '+gate,25,BLUE,True)
  for stage,x in [(1,420),(2,1120)]:
   n='XB'+lab+str(stage)+'N_0';pm='XB'+lab+str(stage)+'P_0'
   d.mos_group(x,y,[pm]);d.mos_group(x,y+250,[n])
   d.line([(x,y-52),(x,y-90)]);d.text(x,y-105,'DR',20,TEAL,True,'middle')
   d.line([(x,y+52),(x,y+198)]);d.dot(x,y+125);d.line([(x,y+125),(x+175,y+125)]);d.text(x+185,y+132,DEV[n]['nets'][0],20,TEAL,True)
   d.line([(x-62,y),(x-100,y),(x-100,y+250),(x-62,y+250)],PURPLE)
   d.text(x-115,y+132,DEV[n]['nets'][1],20,PURPLE,True,'end')
   d.line([(x,y+302),(x,y+345)]);d.ground(x,y+345)
  d.arrow(710,y+125,910,y+125,TEAL)
 d.footer(['相同网络标签电气相连；GP/GN 驱动 XSTEER/XDUMP。P 管源/体接 DR，N 管源/体接 VSS。',
           '输入分压不等于免费降低外部逻辑摆幅：分压电流与交越电流均由 VD/VDB 端口积分统计。'])
 d.save_new('buffer-detail')

def input_network():
 d=D('输入电阻网络：降低门极摆幅，同时增加真实耗能','RD/RDB=50 ohm 来自冻结测试平台；RAD/RADB 与 RADI/RADBI 来自驱动源网表。',1060)
 for inp,port,node,y in [('D','VD','DI',330),('DB','VDB','DBI',720)]:
  d.p.append(f'<circle cx="160" cy="{y}" r="38" fill="white" stroke="{BLUE}" stroke-width="2.7"/>')
  d.text(160,y+7,'V',24,BLUE,True,'middle');d.text(160,y-67,port,22,BLUE,True,'middle')
  d.line([(160,y+38),(160,y+130)]);d.ground(160,y+130)
  d.line([(198,y),(340,y)])
  for x,value in [(370,'50 ohm'),(700,'200 ohm')]:
   d.p.append(f'<rect x="{x-30}" y="{y-12}" width="60" height="24" fill="white" stroke="{INK}" stroke-width="2.7"/>')
   d.text(x,y-35,value,21,MUTE,False,'middle')
  d.line([(400,y),(670,y)]);d.dot(515,y);d.text(515,y-25,inp,21,TEAL,True,'middle')
  d.line([(730,y),(1320,y)]);d.dot(1010,y);d.text(1010,y-25,node,21,TEAL,True,'middle')
  d.line([(1010,y),(1010,y+46)]);d.resistor(1010,y+90,'2.5 kohm');d.line([(1010,y+134),(1010,y+175)]);d.ground(1010,y+175)
  d.text(1330,y+7,'第一级 CMOS 栅极',21,PURPLE)
 d.footer(['TT 静态估算：两路互补输入任一时刻一路为高；P≈3.3²/(50+200+2500)=3.96 mW。',
           '折合净 3.2 Gb/s 约 1.24 pJ/bit；动态栅电流另由真实瞬态积分。此图不包含外部数据源芯片内部功耗。'])
 d.save_new('input-network')

def main():
 global DEV,PARAMS,PASSIVES,REGTARGET
 ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);ap.add_argument('--rail-target',type=float,default=3.1);a=ap.parse_args();src=ROOT/a.source;REGTARGET=a.rail_target
 for line in src.read_text().splitlines():
  z=line.split()
  if line.startswith('.subckt'):PARAMS=dict(x.split('=',1) for x in z if '=' in x)
  if z and z[0][0] in ['R','C']:PASSIVES[z[0]]=z[1:]
  if len(z)>5 and z[5] in ['nmos_3p3','pmos_3p3']:
   par=dict(x.split('=',1) for x in z[6:]);DEV[z[0]]=dict(nets=z[1:5],model=z[5],w=par['w'],l=par['l'])
 OUT.mkdir(parents=True,exist_ok=True);core()
 for q,title in [('B','基础偏置 OTA-B：源极电阻反馈'),('T','调制尾源 OTA-T：低频电流反馈'),('L','激光供电 OTA-L：控制 PMOS 调整管'),('D','缓冲供电 OTA-D：控制 PMOS 调整管')]:ota(q,title)
 rails();buffers();input_network()
 represented={n for r in RECORDS for g in r['groups'] for n in g['instances']}
 assert represented==set(DEV),(set(DEV)-represented,represented-set(DEV))
 (EV/'circuit-figures.json').write_text(json.dumps(dict(source=a.source,source_sha256=sha(src),mos_count=len(DEV),parameters=PARAMS,passives=PASSIVES,rail_target_V=REGTARGET,representation='Identical parallel devices may share one explicitly multiplied symbol; all source instances accounted for.',figures=RECORDS),ensure_ascii=False,indent=2)+'\n')
 print(f'{len(DEV)} source MOS represented across {len(RECORDS)} drawings')
if __name__=='__main__':main()
