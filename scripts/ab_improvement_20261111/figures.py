#!/usr/bin/env python3
"""Original connected circuit diagrams for the controlled improvements."""
from pathlib import Path
import html,re

ROOT=Path(__file__).resolve().parents[2]
ASSET=ROOT/'docs/research/driver-improvement-20261111/assets'
INK='#213e49';TEAL='#246e76';ACCENT='#bc6836'

def tx(x,y,s,size=23,color=INK):
    return f'<text x="{x}" y="{y}" font-family="PingFang SC,Hiragino Sans GB,Arial,sans-serif" font-size="{size}" fill="{color}">{html.escape(s)}</text>'

def wire(d,color=TEAL):
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round"/>'

def dot(x,y):return f'<circle cx="{x}" cy="{y}" r="4" fill="{TEAL}"/>'

def ground(x,y):
    return wire(f'M{x} {y} v12 m-20 0 h40 m-33 9 h26 m-19 9 h12')

def mos(x,y,label,p=False):
    # Enhancement-mode three-segment channel; insulated gate.
    s=wire(f'M{x} {y-50} v25 h-18 M{x-18} {y-28} v15 m0 6 v14 m0 6 v15 M{x-18} {y+28} h18 v22 M{x-31} {y-28} v56')
    if p:s+=f'<circle cx="{x-40}" cy="{y}" r="8" fill="white" stroke="{TEAL}" stroke-width="3"/>'+wire(f'M{x-80} {y} h32')
    else:s+=wire(f'M{x-80} {y} h49')
    return s+tx(x+14,y+7,label,20)

def save(name,z,height=730):
    import cairosvg
    ASSET.mkdir(parents=True,exist_ok=True)
    s=f'<svg xmlns="http://www.w3.org/2000/svg" width="1260" height="{height}" viewBox="0 0 1260 {height}"><rect width="1260" height="{height}" fill="white"/>'+''.join(z)+'</svg>'
    (ASSET/(name+'.svg')).write_text(s+'\n')
    s=re.sub(r'>([^<>]*)<',lambda m:'>'+''.join('<tspan font-family="Arial">'+c+'</tspan>' if c in '→←↑↓Ωµμτ≈×²−≤≥' else c for c in m.group(1))+'<',s)
    cairosvg.svg2png(bytestring=s.encode(),write_to=str(ASSET/(name+'.png')),scale=1.5)

def a_core():
    z=[tx(25,40,'A：把输入 RC、缓冲延迟和输出阻抗分开改',29),
       tx(25,80,'核心连接关系；两套真实 VH/VL 分流调节器保留，未在此展开。',22)]
    # Three CMOS pairs; first two run from digital VDD, final pair between VH/VL.
    for x,top,bot,pl,nl in [(300,'VDD','VSS','XP1','XN1'),(660,'VDD','VSS','XP2','XN2'),(1030,'VH','VL','XPOUT','XNOUT')]:
        z +=[wire(f'M{x} 135 v15 M{x} 250 v50 M{x} 400 v40'),mos(x,200,pl,True),mos(x,350,nl),tx(x-24,123,top,21)]
        z +=[wire(f'M{x-80} 200 H{x-110} V350 H{x-80}')]
        if bot=='VSS':z +=[ground(x,440)]
        else:z +=[tx(x-18,470,bot,21)]
    z +=[wire('M25 275 H65 M65 262 H130 V288 H65 Z M130 275 H190'),tx(30,245,'D0',20),tx(69,313,'RIN',21),dot(190,275),tx(152,330,'DI',20)]
    z +=[wire('M300 275 H550'),dot(300,275),dot(550,275),tx(428,260,'N1',21)]
    z +=[wire('M660 275 H920'),dot(660,275),dot(920,275),tx(780,260,'CTRL',21)]
    z +=[wire('M1030 275 H1220'),dot(1030,275),tx(1138,257,'OUT',21),tx(1100,312,'接 LED 阴极',20)]
    z +=[tx(25,525,'单项对照 1：8 方块输入电阻 → 1 方块；检查 DI 的边沿与瞬态应力。',22),
          tx(25,568,'单项对照 2：仅改缓冲 MOS；观察 N1 / CTRL，输出 MOS 与供电轨保持原状。',22),
          tx(25,611,'后续输出尺寸调整须重新校准 VH / VL，使直流电流仍为 25 / 100 µA。',22),
          tx(25,658,'体端：所有 NMOS → VSS；XP1/XP2 → VDD；XPOUT → VH。尺寸以各候选网表为准。',20)]
    save('a-circuit-method',z,700)

def steering(vcsel=False):
    z=[tx(25,40,'VCSEL：保留偏置和参考，独立修改输入与换流级' if vcsel else 'B：保持直流电流，用 CFF 补充边沿充放电',28)]
    z +=[tx(25,78,'核心连接图；实际参考源、调节器、数据缓冲与封装仍计入完整仿真。',22)]
    z +=[wire('M330 110 H560 M400 110 V145'),tx(330,101,'VL ≈ 3.1 V' if vcsel else 'VLED = 5 V',20)]
    z +=[wire('M379 145 H421 L400 185 Z M377 191 H423 M400 191 V210'),tx(594,146,'VCSEL' if vcsel else 'MicroLED',21),wire('M425 154 L446 135 M438 136 L446 135 L445 144 M436 164 L457 145 M449 146 L457 145 L456 154')]
    z +=[wire('M560 110 V167 M538 167 H582 M538 185 H582 M560 185 V210 H400'),tx(593,184,'150 fF' if vcsel else '200 fF',20),dot(400,210),wire('M400 210 V220 M390 220 H410 V240 H390 Z M400 240 V245 C418 245 418 255 400 255 C418 255 418 265 400 265 C418 265 418 275 400 275 V285'),tx(435,253,'Rpkg / Lpkg',18),tx(319,272,'OUT',19),dot(400,285)]
    z +=[wire('M400 285 H180'),mos(180,335,'XBASE'),mos(400,335,'XSTEER' if vcsel else 'XLED')]
    z +=[wire('M850 110 V145 M840 145 H860 V195 H840 Z M850 195 V285'),tx(815,101,'VL' if vcsel else 'VIN',20),tx(890,172,'RDUMMY',20),mos(850,335,'XDUMP' if vcsel else 'XDUMMY')]
    z +=[wire('M400 385 V420 H850 V385 M620 420 V445'),dot(620,420),tx(640,409,'VX',20),mos(620,495,'XTAIL')]
    z +=[tx(32,324,'BCTRL' if vcsel else 'BIAS',20),wire('M32 335 H100'),tx(267,324,'GP',20),wire('M270 335 H320'),tx(715,324,'GN' if vcsel else 'GB',20),wire('M720 335 H770'),tx(470,484,'TCTRL' if vcsel else 'BIAS',20),wire('M470 495 H540')]
    if vcsel:
        z +=[wire('M180 385 V400 M170 400 H190 V430 H170 Z M180 430 V445'),ground(180,445),tx(25,392,'SBASE',18),tx(210,423,'RBASE 50 Ω',20),
              wire('M620 545 V550 M610 550 H630 V580 H610 Z M620 580 V600'),ground(620,600),tx(470,555,'STAIL',18),tx(650,575,'RTAIL 37.5 Ω',20)]
    else:
        z +=[ground(180,415),wire('M180 385 V415'),ground(620,545)]
    if not vcsel:
        z +=[wire('M400 285 H620 V260 H650 M670 260 H735 V335',ACCENT),wire('M650 240 V280 M670 240 V280',ACCENT),dot(735,335),tx(620,221,'CFF',21,ACCENT),
              tx(25,620,'GB 上升：向 OUT 注入电荷，阴极电压升高，LED 导电电流下降。',22),
              tx(25,660,'GB 下降：从 OUT 抽走电荷，阴极电压降低，LED 导电电流上升。',22),
              tx(25,703,'CFF 直流开路；瞬态峰值、平均电流和驱动能耗会改变，必须另行验证。',21)]
    else:
        z +=[tx(25,675,'输入对照：ATTEN 200 → 50 Ω；两条差分输入通路保持对称。',22),
              tx(25,715,'换流对照：仅 XSTEER / XDUMP 的 W 40 → 20 µm，L 保持 0.28 µm。',22),
              tx(25,755,'基准约 3 mA + 调制约 4 mA；减小寄生电容的同时必须复查导通压降与电流。',21)]
    z +=[tx(25,805 if vcsel else 750,'NMOS 体端接 VSS；XBASE/XTAIL 各表示两只并联管；省略 0 V 电流采样源。' if vcsel else '四只 NMOS 体端均接 VSS。省略支路详见可复现网表；本图不是新版图或流片数据。',19)]
    save('vcsel-circuit-method' if vcsel else 'b-charge-assist',z,840 if vcsel else 780)

if __name__=='__main__':
    a_core();steering();steering(True)
