#!/usr/bin/env python3
"""Connected explanatory schematics, independently drawn from candidate netlists."""
from pathlib import Path
import importlib.util

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('drawing',ROOT/'scripts/ab_improvement_20261111/figures.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
d.ASSET=ROOT/'docs/research/driver-methods-20261111/assets'
tx,wire,dot,mos,ground=d.tx,d.wire,d.dot,d.mos,d.ground

def a():
    z=[tx(24,40,'A：反相信号提前补偿输出节点，串联电阻限制冲击',28),
       tx(24,80,'本轮新增橙色支路；20只MOS及真实VH/VL调节电路保持原样。',21)]
    for x,top,bot,pl,nl in [(270,'VDD 3.3 V','VSS','XP1','XN1'),(610,'VDD 3.3 V','VSS','XP2','XN2'),(960,'VH','VL','XPOUT','XNOUT')]:
        z += [tx(x-45,205,top,19),wire(f'M{x} 216 v4 M{x} 320 V370 M{x} 470 V500'),mos(x,270,pl,True),mos(x,420,nl),wire(f'M{x-80} 270 H{x-110} V420 H{x-80}')]
        z += [ground(x,500)] if bot=='VSS' else [tx(x-17,527,bot,21)]
    z += [wire('M24 345 H55 M55 333 H115 V357 H55 Z M115 345 H160'),tx(24,315,'D0',19),tx(55,393,'RIN',19),dot(160,345),tx(120,445,'DI',19),
          wire('M270 345 H500'),dot(270,345),dot(500,345),tx(370,327,'N1',20),
          wire('M610 345 H850'),dot(610,345),dot(850,345),tx(735,327,'CTRL',20),
          wire('M960 345 H1180 V260'),dot(960,345),dot(1100,345),tx(1080,376,'OUT',20),
          wire('M1180 110 V140 M1160 140 H1200 L1180 175 Z M1158 182 H1202 M1180 182 V200 M1170 200 H1190 V220 H1170 Z M1180 220 V230 C1198 230 1198 240 1180 240 C1198 240 1198 250 1180 250 V260'),
          tx(1084,101,'VLED = 5 V',19),tx(995,175,'MicroLED',18),tx(985,225,'Rpkg / Lpkg',17),
          wire('M1205 145 l20 -20 m-8 1 h8 v8 M1210 162 l20 -20 m-8 1 h8 v8'),
          wire('M420 345 V130 H540 M540 118 H620 V142 H540 Z M620 130 H750 M750 109 V151 M772 109 V151 M772 130 H1100 V345',d.ACCENT),
          dot(420,345),tx(516,105,'RFF ≈ 1 kΩ',19,d.ACCENT),tx(710,177,'CFF 31.275 fF',19,d.ACCENT)]
    z += [tx(24,600,'D0=1：N1先下降 → CFF拉低OUT → LED电流增加；CTRL随后接通VL。',22),
          tx(24,642,'D0=0：N1先上升 → CFF抬高OUT → LED电流减小；CTRL随后接通VH。',22),
          tx(24,686,'200 fF跨LED的A/K，位于串联封装R/L之前（未画）；Rpkg=1 Ω，Lpkg=0.5 nH。',20),
          tx(24,727,'体端：NMOS→VSS，XP1/XP2→VDD，XPOUT→VH；交叉无圆点表示不连接。',20),
          tx(24,769,'RFF为4 µm×4 µm的PDK电阻；CFF为理想集总值。本图是原理连接，不是PEX。',20)]
    d.save('a-new-circuit',z,800)

def b():
    z=[tx(25,40,'B：降低VIN，重新分配虚支路的电压余量',28),tx(25,80,'VLED与VDD保持不变；参考电流与LED两态目标保持25 / 100 µA。',21)]
    z += [tx(320,119,'VLED = 5 V',21),wire('M400 130 V155 M380 155 H420 L400 190 Z M378 197 H422 M400 197 V220'),tx(450,176,'MicroLED',20),wire('M426 162 l20 -20 m-8 1 h8 v8 M431 178 l20 -20 m-8 1 h8 v8'),
          wire('M400 220 V232 M390 232 H410 V252 H390 Z M400 252 V260 C418 260 418 270 400 270 C418 270 418 280 400 280 V300'),tx(445,264,'Rpkg / Lpkg',18),tx(319,287,'OUT',20),
          wire('M400 300 H180'),dot(400,300),mos(180,350,'XBASE'),mos(400,350,'XLED'),
          wire('M180 400 V440'),ground(180,440),
          tx(785,119,'VIN = 3.3 V',22,d.ACCENT),wire('M850 130 V170 M838 170 H862 V230 H838 Z M850 230 V300',d.ACCENT),tx(890,194,'RDUMMY',20,d.ACCENT),tx(890,224,'27.6 kΩ',20,d.ACCENT),tx(880,278,'DUMMY',19),mos(850,350,'XDUMMY'),
          wire('M400 400 V450 H850 V400 M620 450 V480'),dot(620,450),tx(650,438,'VX',20),mos(620,530,'XTAIL'),ground(620,580),
          tx(30,339,'BIAS',20),wire('M30 350 H100'),tx(270,339,'GP',20),wire('M270 350 H320'),tx(715,339,'GB',20),wire('M715 350 H770'),tx(470,519,'BIAS',20),wire('M470 530 H540'),
          wire('M400 300 H620 V270 H650 M650 250 V290 M672 250 V290 M672 270 H735 V350'),dot(735,350),tx(590,240,'CFF 31.275 fF',19)]
    z += [tx(25,645,'VIN同时供给晶体管参考源和虚支路；外部VREF=2.5 V仍保留。',22),
          tx(25,687,'低电流态：基准支路约25 µA持续流过LED；约75 µA调制电流流过RDUMMY。',21),
          tx(25,729,'高电流态：调制电流转向LED，总电流约100 µA。NMOS体端均接VSS。',21),
          tx(25,771,'200 fF跨LED的A/K、位于封装R/L前；参考源与缓冲器未展开，均已纳入仿真。',20)]
    d.save('b-new-circuit',z,805)

if __name__=='__main__':a();b()
