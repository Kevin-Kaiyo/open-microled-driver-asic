#!/usr/bin/env python3
"""Draw inspectable transistor circuits from the new source netlist; no invented devices."""
from pathlib import Path
import sys,re,json,hashlib,importlib.util
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('circuit_drawing',ROOT/'scripts/highspeed_routes/circuits.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
OUT=ROOT/'docs/research/nrz-b-reference-power-20261024/figures';OUT.mkdir(parents=True,exist_ok=True);m.OUT=OUT
src=ROOT/'analog/nrz_reference_v2/bias_power_pilot.spice'
DEV={}
for line in src.read_text().splitlines():
 p=line.split()
 if not p or not p[0].startswith('X'):continue
 DEV[p[0][1:]]={'nets':p[1:5],'model':p[5],'w':next(x[2:] for x in p if x.startswith('w=')),'l':next(x[2:] for x in p if x.startswith('l='))}

def mos(d,x,y,name):
 s=DEV[name];d.mos(x,y,name,s['nets'],'pfet' in s['model'],label=False)
 d.text(x+34,y-9,name,18,m.INK,True);d.text(x+34,y+19,s['w']+'/'+s['l'],16,m.MUTE)

def cap(d,x,y,label):
 d.line([(x,y-36),(x,y-7)]);d.line([(x-20,y-7),(x+20,y-7)]);d.line([(x-20,y+7),(x+20,y+7)]);d.line([(x,y+7),(x,y+36)]);d.text(x+30,y+8,label,18)

def net(d,x,y,label,color=m.PURPLE):d.text(x,y-12,label,19,color,True);d.dot(x,y,color)

def amplifier(prefix,extra):
 vi=prefix=='I'; title='参考电流：电压反馈到 PMOS 电流镜' if vi else 'Dummy 供电：误差放大器与 PMOS 串联调整管'
 d=m.Drawing(title,'r1 真实晶体管连接 · 全部 GF180 06v0 · W/L 单位 um · 片外无源件单列',1390)
 d.line([(140,205),(1450,205)],m.BLUE);d.text(140,190,'VIN = 5 V',22,m.BLUE,True)
 for x,y,n in [(140,330,'PBIAS'),(550,330,'PTAIL'),(400,535,'PD1'),(700,535,'PD2'),(400,780,'ND1'),(700,780,'ND2'),(980,535,'PLOAD'),(980,780,'NSTAGE'),(1220,535,'PREG')]:mos(d,x,y,prefix+n)
 for x in [140,550]:d.line([(x,205),(x,278)],m.BLUE);d.dot(x,205,m.BLUE)
 d.line([(140,382),(140,470),(78,470),(78,330)]);d.dot(140,470);d.line([(140,470),(140,600)]);d.resistor(140,644,'RBIAS 100 kohm');d.line([(140,688),(140,1000)]);d.ground(140,1000)
 d.line([(78,470),(60,470),(60,420),(310,420),(310,330),(488,330)],m.PURPLE)
 d.line([(550,382),(550,440),(400,440),(400,483)]);d.line([(550,440),(700,440),(700,483)]);d.dot(550,440)
 d.line([(400,587),(400,728)]);d.line([(700,587),(700,728)])
 d.line([(400,640),(315,640),(315,780),(338,780)],m.PURPLE);d.dot(400,640)
 d.line([(315,780),(315,885),(615,885),(615,780),(638,780)],m.PURPLE);d.dot(315,780)
 d.line([(400,832),(400,1000),(980,1000)]);d.line([(700,832),(700,1000)]);d.dot(700,1000);d.line([(980,832),(980,1000)]);d.ground(700,1000)
 d.line([(700,665),(850,665),(850,780),(918,780)],m.PURPLE);d.dot(700,665);d.text(735,645,prefix+'N2',19,m.PURPLE,True)
 for x in [980,1220]:d.line([(x,205),(x,483)],m.BLUE);d.dot(x,205,m.BLUE)
 d.line([(980,587),(980,728)]);d.line([(980,635),(900,635),(900,535),(918,535)],m.PURPLE);d.dot(980,635)
 d.line([(980,635),(1110,635),(1110,535),(1158,535)],m.PURPLE);net(d,1030,635,prefix+'CTRL')
 d.line([(235,535),(338,535)],m.PURPLE);d.text(235,513,'VSET = 0.5 V',18,m.PURPLE,True)
 d.line([(590,535),(638,535)],m.PURPLE);d.text(574,508,'SENSE' if vi else 'REGFB',18,m.PURPLE,True)
 d.line([(1220,587),(1220,700)]);net(d,1220,700,'SENSE' if vi else 'VREG',m.TEAL)
 if vi:
  d.line([(1220,700),(1220,756)]);d.resistor(1220,800,'RSET 20 kohm');d.line([(1220,844),(1220,1000)]);d.ground(1220,1000)
  mos(d,1440,535,'IPOUT');d.line([(1440,205),(1440,483)],m.BLUE);d.dot(1440,205,m.BLUE)
  d.line([(1110,635),(1378,635),(1378,535)],m.PURPLE);d.dot(1110,635)
  d.line([(1440,587),(1440,850)]);d.arrow(1440,850,1440,925,m.TEAL);d.text(1370,960,'IOUT -> BIAS',18,m.TEAL,True)
  d.lines(1030,1092,['SENSE ~ VSET -> ISET ~ 0.5 / 20k = 25 uA','IPREG / IPOUT 同尺寸，输出镜像到 BIAS。','实际误差还含失调、VDS 差及输出压差。'],17,29)
 else:
  d.line([(1220,700),(1220,726)]);d.resistor(1220,770,'56 kohm');d.line([(1220,814),(1220,850)]);net(d,1220,850,'REGFB',m.PURPLE)
  d.line([(1220,850),(1220,876)]);d.resistor(1220,920,'10 kohm');d.line([(1220,964),(1220,1000)]);d.ground(1220,1000)
  d.line([(1220,700),(1490,700)]);d.arrow(1490,700,1490,850,m.TEAL);d.lines(1320,900,['接 Cout / ESR','及 RDUMMY / 核心','电流回到 VSS'],18,30)
  d.lines(1040,1092,['REGFB ~ VSET -> VREG ~ 0.5 x (1+56/10)','名义为 3.3 V；启动与瞬态还受环路影响。','PLOAD 支路也耗电，不能省略其静态功耗。'],17,29)
 d.box(48,1080,940,160,'连接及器件说明',['同名网络相连；实心点为电气连接，跨线无点不连接。','PMOS 体端 B 接 VIN；NMOS 体端 B 接 VSS，D/G/S 如图。','补偿接 IN2–ICTRL / LN2–LCTRL，参数按对应实验版本；此图保持 r1 源连接。'],size=19)
 d.footer(['这是源网表对应的电路图；19 MOS 模块已有独立实际版图提取。此图不代表最终启动/稳定性验收通过。','源：analog/nrz_reference_v2/bias_power_pilot.spice；片外基准、电阻、电容的误差另做验证。'])
 name='vi-servo-r1' if vi else 'ldo-r1';rec=d.save(name)
 p=OUT/(name+'.svg');s=p.read_text().replace('原创教学示意。候选架构，未经高速晶体管或版图仿真。器件端子和电流方向有明确标注。','r1 源网表的晶体管连接；模块已仿真和实际版图提取，启动与稳定性仍需按对应实验结果判断。');p.write_text(s)
 rec['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();rec['source']=str(src.relative_to(ROOT));rec['source_sha256']=hashlib.sha256(src.read_bytes()).hexdigest()
 for name,nets in d.devices.items():assert [nets[k] for k in 'DGSB']==DEV[name]['nets']
 return rec
if __name__=='__main__':
 rec=[amplifier('I',True),amplifier('L',False)]
 selected=ROOT/'analog/nrz_reference_v2/vi_reference_switched_keeper.spice'
 selected_devs={p[0][1:]:p[1:5] for line in selected.read_text().splitlines() if (p:=line.split()) and p[0].startswith('X')}
 for name,item in DEV.items():
  if name.startswith('I'):assert selected_devs[name]==item['nets']
 text=(OUT/'vi-servo-r1.svg').read_text().replace('r1 真实晶体管连接','选定参考部分的真实晶体管连接').replace('补偿接 IN2–ICTRL / LN2–LCTRL，参数按对应实验版本；此图保持 r1 源连接。','IN2 经 150 pF 补偿至 PCB 地；保护 MDIS、MK 在总图展开。').replace('这是源网表对应的电路图；19 MOS 模块已有独立实际版图提取。此图不代表最终启动/稳定性验收通过。','本图展开选定电路的10 MOS参考部分；实际寄生与接受状态按最终实验表判断。').replace('analog/nrz_reference_v2/bias_power_pilot.spice','analog/nrz_reference_v2/vi_reference_switched_keeper.spice').replace('r1 源网表的晶体管连接；模块已仿真和实际版图提取，启动与稳定性仍需按对应实验结果判断。','选定12 MOS模块中的10 MOS参考部分，另外两只保护MOS在总图展开。')
 q=OUT/'vi-servo-selected.svg';q.write_text(text)
 rec.append({'file':q.name,'source':str(selected.relative_to(ROOT)),'source_sha256':hashlib.sha256(selected.read_bytes()).hexdigest(),'sha256':hashlib.sha256(q.read_bytes()).hexdigest(),'connection_equality_to_r1_vi_checked':True})
 (OUT/'reference-circuit-manifest.json').write_text(json.dumps({'figures':rec,'scope':'r1 source circuit; body connections explicitly stated; external compensation and component versions follow experiment decks'},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'figures':[x['file'] for x in rec]}))
