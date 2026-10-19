#!/usr/bin/env python3
"""Original teaching schematics and conceptual floorplans; no circuit simulation.

Regenerate: python3 scripts/highspeed_routes/circuits.py [--raster]
All device connections are also saved as explicit D/G/S/B dictionaries.
"""
from pathlib import Path
from html import escape
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/research/highspeed-driver-routes-20261019/figures"
INK = "#233d4b"
MUTE = "#667c87"
LIGHT = "#e0e8ec"
ORANGE = "#c97925"
TEAL = "#188578"
PURPLE = "#8164a8"
BLUE = "#3d729e"


class Drawing:
    def __init__(self, title, subtitle, height=1120):
        self.title, self.height = title, height
        self.p = []
        self.devices = {}
        self.text(48, 62, title, 32, bold=True)
        self.text(48, 103, subtitle, 19, MUTE)
        self.line([(48, 128), (1552, 128)], LIGHT, 1.5)

    def text(self, x, y, s, size=20, color=INK, bold=False, anchor="start"):
        self.p.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{600 if bold else 400}" text-anchor="{anchor}">{escape(str(s))}</text>')

    def lines(self, x, y, ss, size=19, gap=30, color=INK, bold=False):
        for j, s in enumerate(ss):
            self.text(x, y+j*gap, s, size, color, bold)

    def line(self, xy, color=INK, width=2.7, dash=None):
        self.p.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in xy)+f'" fill="none" stroke="{color}" stroke-width="{width}"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')

    def dot(self, x, y, color=INK):
        self.p.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{color}"/>')

    def arrow(self, x1, y1, x2, y2, color=INK, dash=None):
        self.p.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}" stroke-width="3" marker-end="url(#a{color[1:]})"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')

    def box(self, x, y, w, h, title, lines=(), color=BLUE, fill="#f4f7f9", size=19):
        self.p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{color}" stroke-width="1.5"/>')
        if title:
            self.text(x+20, y+34, title, 21, color, True)
        self.lines(x+20, y+67, lines, size, 29)

    def ground(self, x, y):
        for dy, w in [(0, 20), (7, 13), (14, 6)]:
            self.line([(x-w,y+dy),(x+w,y+dy)])

    def resistor(self, x, y, label, color=INK):
        self.line([(x,y-44),(x,y-30)], color)
        self.p.append(f'<rect x="{x-12}" y="{y-30}" width="24" height="60" fill="white" stroke="{color}" stroke-width="2.7"/>')
        self.line([(x,y+30),(x,y+44)], color)
        self.text(x+24, y+7, label, 18, color)

    def led(self, x, y, color=ORANGE):
        self.line([(x,y-42),(x,y-20)],color)
        self.p.append(f'<path d="M{x-19},{y-20} H{x+19} L{x},{y+12} Z M{x-22},{y+18} H{x+22}" fill="none" stroke="{color}" stroke-width="2.7"/>')
        self.line([(x,y+18),(x,y+42)],color)
        self.arrow(x+28,y-8,x+48,y-28,color)
        self.arrow(x+34,y+7,x+54,y-13,color)
        self.text(x-35,y-22,"A",16,MUTE)
        self.text(x-35,y+34,"K",16,MUTE)

    def mos(self,x,y,name,nets,pmos=False,color=INK,label=True):
        self.devices[name] = dict(zip("DGSB",nets)) | {"type":"PMOS" if pmos else "NMOS"}
        self.p.append(f'<g data-device="{name}" data-terminal-order="D G S B" data-nets="{escape(" ".join(nets))}" transform="translate({x} {y})">')
        for a,b in [(-23,-13),(-5,5),(13,23)]:
            self.line([(-10,a),(-10,b)],color,3)
        self.line([(-28,-26),(-28,26)],PURPLE)
        self.line([(0,-52),(0,-21),(-10,-21)],color)
        self.line([(-10,21),(0,21),(0,52)],color)
        if pmos:
            self.line([(-62,0),(-43,0)],PURPLE)
            self.p.append(f'<circle cx="-38" cy="0" r="5" fill="white" stroke="{PURPLE}" stroke-width="2.6"/>')
            self.line([(-33,0),(-28,0)],PURPLE)
        else:
            self.line([(-62,0),(-28,0)],PURPLE)
        self.p.append('</g>')
        self.text(x+9,y-34,"S" if pmos else "D",15,MUTE)
        self.text(x+9,y+49,"D" if pmos else "S",15,MUTE)
        self.text(x-61,y-13,"G",15,MUTE)
        if label:
            self.text(x+36,y-4,name,21,color,True)

    def current_source(self,x,y,label):
        self.p.append(f'<circle cx="{x}" cy="{y}" r="25" fill="white" stroke="{TEAL}" stroke-width="2.6"/>')
        self.arrow(x,y-14,x,y+14,TEAL)
        self.text(x+40,y+5,label,18,TEAL)

    def footer(self,lines):
        y=self.height-92
        self.line([(48,y-22),(1552,y-22)],LIGHT,1.5)
        self.lines(48,y+4,lines,17,28,MUTE)

    def save(self,name):
        colors=[INK,ORANGE,TEAL,PURPLE,BLUE]
        defs=''.join(f'<marker id="a{c[1:]}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="{c}"/></marker>' for c in colors)
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{self.height}" viewBox="0 0 1600 {self.height}" role="img"><title>{escape(self.title)}</title><desc>原创教学示意。候选架构，未经高速晶体管或版图仿真。器件端子和电流方向有明确标注。</desc><style>text{{font-family:"PingFang SC","Noto Sans CJK SC",Arial,sans-serif}}path,polyline{{stroke-linecap:round;stroke-linejoin:round}}</style><defs>{defs}</defs><rect width="1600" height="{self.height}" fill="#fff"/>'+''.join(self.p)+'</svg>\n'
        (OUT/f'{name}.svg').write_text(svg)
        return {"file":f'{name}.svg',"size":[1600,self.height],"devices":self.devices,"sha256":hashlib.sha256(svg.encode()).hexdigest()}


def route_a():
    d=Drawing("路线 A｜受限摆幅 CMOS 电压驱动", "单 LED · OOK 两电平 · 独立候选原理图；电流与电压范围尚待器件模型校准")
    d.box(48,170,262,142,"数据与前置驱动",["DATA = 1：下拉导通","DATA = 0：上拉导通","含电平转换及交越控制"],PURPLE,size=18)
    d.box(48,360,262,140,"输出摆幅设定",["V_L ≤ V_OUT ≤ V_H","V_H、V_L 为可设电源轨","不是任意施加反向电压"],BLUE,size=18)
    d.text(595,188,"V_H",22,BLUE,True,"middle")
    d.line([(595,200),(595,278)],BLUE)
    d.mos(595,330,"MP",["OUT","CTRL","V_H","V_H"],True,BLUE)
    d.line([(595,382),(595,538)],BLUE)
    d.mos(595,590,"MN",["OUT","CTRL","V_L","V_L"],False,ORANGE)
    d.line([(595,642),(595,720)],ORANGE)
    d.text(595,754,"V_L",22,BLUE,True,"middle")
    d.line([(310,248),(385,248),(385,330),(533,330)],PURPLE)
    d.line([(385,330),(385,590),(533,590)],PURPLE)
    d.dot(385,330,PURPLE)
    d.text(395,564,"CTRL：V_L ↔ V_H",18,PURPLE)
    d.text(810,188,"VLED",22,ORANGE,True,"middle")
    d.line([(810,200),(810,203)],ORANGE)
    d.led(810,245)
    d.text(882,241,"片外 MicroLED",20,ORANGE,True)
    d.line([(810,287),(810,311)],ORANGE)
    d.resistor(810,355,"R_LIM",ORANGE)
    d.line([(810,399),(810,460),(595,460)],ORANGE)
    d.dot(595,460,ORANGE)
    d.text(639,441,"OUT",21,ORANGE,True)
    d.text(835,423,"限流／阻尼",18,MUTE)
    d.arrow(755,306,755,386,ORANGE)
    d.arrow(680,514,680,628,ORANGE)
    d.text(695,581,"数据 1",18,ORANGE)
    d.arrow(565,398,565,441,BLUE)
    d.text(395,424,"数据 0：OUT 上升",16,BLUE)
    d.box(1060,170,490,232,"两种稳态的闭合回路",[
        "1：VLED → LED → R_LIM → MN → V_L",
        "0：MP 将 OUT 拉近 V_H，LED 电流降至 I₀。",
        "V_L 回流与各电源负端共同闭合电流回路。",
        "若 V_H = VLED，理想暗态可接近零电流。",
        "I₀ 非零时，上轨须能吸收回灌或另设偏置。",
        "MP 的充电电流主要出现在切换边沿。"],ORANGE,size=18)
    d.box(1060,418,490,193,"电流不是天然恒定",[
        "VLED − V_OUT = VF(I,T) + I·R_LIM",
        "I₀、I₁ 随 LED、温度、电源及导通压降变化。",
        "要精确控流：增加检测、慢速反馈或数字校准；",
        "高速数据通路与慢速幅度设定分开验证。"],TEAL,size=18)
    d.box(1060,640,490,160,"速度与能耗的取舍",[
        "较小电压摆幅可减少输出节点充放电能量。",
        "电源轨、R_LIM、驱动强度共同决定边沿。",
        "必须计入 LED、前置驱动和电源转换损耗。"],BLUE,size=18)
    d.box(48,830,1502,142,"设计条件：先检查电压，再讨论速率",[
        "NMOS：B = V_L；PMOS：B = V_H。若 V_L 不等于公共衬底电位，需要工艺支持的隔离阱／隔离器件及相应规则。",
        "检查每只 MOS 的 VGS、VGD、VDS、体结偏压，以及启动／掉电／LED 开路／封装振铃；上下管交越会产生直通电流。",
        "可叠加分段驱动、FFE／边沿预加重；限制峰值电流与 LED 反向电压，并重新核算完整数据序列的能量。"],PURPLE,size=18)
    d.footer(["MOS 采用增强型三端符号；D/G/S 已标，体端 B 按上面的公共连接说明处理。实心点相连；同名网络相连。",
              "本图为独立教学电路，不对应特定论文的晶体管复刻；未选工艺、尺寸、电流或目标速率。"])
    return d.save('route-a')


def route_b():
    d=Drawing("路线 B｜差分电流转向 OOK", "单 LED · 尾电流连续建立 · 数据只改变电流去向；0 态的替代支路仍然耗电",1200)
    d.text(180,186,"VREF",21,TEAL,True,"middle")
    d.line([(180,200),(180,224)],TEAL)
    d.current_source(180,249,"等效 IREF")
    d.line([(180,274),(180,648)],TEAL)
    d.lines(42,332,["上游基准源", "与环路省略"],17,27,MUTE)
    d.mos(180,700,"MREF",["BIAS","BIAS","VSS","VSS"],color=TEAL)
    d.line([(118,700),(95,700),(95,590),(180,590)],PURPLE)
    d.dot(180,590,TEAL)
    d.line([(180,590),(490,590),(490,700),(813,700)],PURPLE)
    d.text(292,572,"BIAS：低噪声偏置",19,TEAL)
    d.text(700,186,"VLED",21,ORANGE,True,"middle")
    d.line([(700,200),(700,208)],ORANGE)
    d.led(700,250)
    d.line([(700,292),(700,398)],ORANGE)
    d.text(768,255,"片外 MicroLED",20,ORANGE,True)
    d.mos(700,450,"ML",["LED_K","G+","VX","VSS"],color=ORANGE)
    d.line([(560,450),(638,450)],PURPLE)
    d.text(551,431,"G+",20,PURPLE)
    d.text(1050,186,"VDUMMY",21,BLUE,True,"middle")
    d.line([(1050,200),(1050,228)],BLUE)
    d.resistor(1050,272,"R_DUMMY",BLUE)
    d.line([(1050,316),(1050,398)],BLUE)
    d.mos(1050,450,"MD",["DUMMY","G−","VX","VSS"],color=BLUE)
    d.line([(930,450),(988,450)],PURPLE)
    d.text(920,431,"G−",20,PURPLE)
    d.line([(700,502),(700,565),(1050,565),(1050,502)])
    d.dot(875,565)
    d.line([(875,565),(875,648)])
    d.text(889,604,"VX",21,INK,True)
    d.mos(875,700,"MI",["VX","BIAS","VSS","VSS"],color=TEAL)
    d.text(912,734,"尾电流管",18,TEAL)
    d.line([(180,752),(180,815),(875,815),(875,752)])
    d.ground(525,815)
    d.text(566,836,"VSS（共同回流）",19)
    d.arrow(652,319,652,384,ORANGE)
    d.arrow(1003,326,1003,384,BLUE)
    d.arrow(834,607,834,638,TEAL)
    d.box(350,185,262,152,"前置驱动器",["DATA → G+ 与 G−","设置共模与差分摆幅","验证两路延迟及负载"],PURPLE,size=18)
    d.box(1220,170,330,265,"转向方式",[
        "数据 1：ML 多导通，MD 少导通；",
        "LED 支路承担主要尾电流。",
        "数据 0：MD 多导通，ML 少导通；",
        "替代负载承担主要尾电流。",
        "切换期间允许两支路分流；",
        "内部电容也会吸收／释放电流。"],PURPLE,size=17)
    d.box(1220,465,330,292,"功耗边界",[
        "理想稳态：",
        "I_LED + I_DUMMY ≈ I_TAIL",
        "尾电流连续，不代表各电源恒流。",
        "P 包含 VLED、VDUMMY、偏置、",
        "前置驱动及其电源损耗。",
        "R_DUMMY 是可替换等效负载；",
        "应匹配压降及动态，不能随意短路。"],BLUE,size=17)
    d.box(48,885,1502,178,"电压余量、保护与速度必须一起校核",[
        "LED 支路：VLED ≥ VF + VDS(ML) + VDS(MI) + 互连压降 + 余量；dummy 支路也要满足自己的电压预算。",
        "MI 与 MREF 的 W/L 比只给出近似电流比例；输出阻抗、失配、温度及各管工作区会改变实际电流。",
        "可选 Cascode 能降低尾电流对节点扰动的敏感度，但会增加余量、偏置与寄生；不能直接当成更高速的保证。",
        "两开关栅极不是直接套用 PWM 的 0／3.3 V：需重新选择共模、摆幅、体端接法及可靠性限制。"],TEAL,size=18)
    d.footer(["所有 NMOS 的 B = VSS；D/G/S 已标。LED 与替代负载的电源负端接共同回流。IREF 圆符号仅代表待实现的上游基准。",
              "原理图未包含保护器件、ESD、封装 RLC 和实际前置驱动晶体管；本图不构成已验证的高速设计。"])
    return d.save('route-b')


def route_c():
    d=Drawing("路线 C｜分段电流 DAC：用四档电流发送 PAM4", "以三个等权电流单元示范最小 PAM4；产品 DAC 可采用温度计／二进制混合分段，不预设分辨率或位率",1270)
    d.text(120,177,"VLED",20,ORANGE,True,"middle")
    d.line([(120,188),(120,198)],ORANGE)
    d.led(120,240)
    d.text(181,242,"片外 MicroLED",19,ORANGE,True)
    d.line([(120,282),(120,344),(1050,344)],ORANGE)
    d.text(495,321,"同一 LED：三个单位电流相加",19,ORANGE,True)
    for i,x in enumerate([170,580,990],1):
        ml,md,tail=x+60,x+260,x+160
        d.text(x+145,394,f"单元 {i}：Iu",21,TEAL,True,"middle")
        d.line([(ml,344),(ml,448)],ORANGE)
        d.dot(ml,344,ORANGE)
        d.text(md,177,"VDUMMY",18,BLUE,True,"middle")
        d.line([(md,189),(md,218)],BLUE)
        d.resistor(md,262,f"RD{i}",BLUE)
        # A line jump makes the unconnected dummy/LED-bus crossing explicit.
        if i < 3:
            d.line([(md,306),(md,336)],BLUE)
            d.p.append(f'<path d="M{md},336 Q{md+16},344 {md},352" fill="none" stroke="{BLUE}" stroke-width="2.7"/>')
            d.line([(md,352),(md,448)],BLUE)
        else:
            d.line([(md,306),(md,448)],BLUE)
        d.mos(ml,500,f"ML{i}",["LED_K",f"G{i}+",f"VX{i}","VSS"],color=ORANGE)
        d.mos(md,500,f"MD{i}",[f"DUMMY{i}",f"G{i}−",f"VX{i}","VSS"],color=BLUE)
        d.text(ml-77,547,f"G{i}+",17,PURPLE)
        d.text(md-77,547,f"G{i}−",17,PURPLE)
        d.line([(ml,552),(ml,606),(md,606),(md,552)])
        d.dot(tail,606)
        d.line([(tail,606),(tail,678)])
        d.mos(tail,730,f"MI{i}",[f"VX{i}","BIAS","VSS","VSS"],color=TEAL)
        d.line([(tail-115,730),(tail-62,730)],PURPLE)
        d.text(tail-120,709,"BIAS",17,PURPLE)
        d.line([(tail,782),(tail,852)])
        d.arrow(ml-37,567,ml-37,594,ORANGE)
        d.arrow(md+40,563,md+40,593,BLUE)
    d.text(1460,399,"VREF",20,TEAL,True,"middle")
    d.line([(1460,412),(1460,457)],TEAL)
    d.current_source(1460,482,"")
    d.text(1488,536,"等效 IREF",17,TEAL)
    d.line([(1460,507),(1460,678)],TEAL)
    d.mos(1460,730,"MREF",["BIAS","BIAS","VSS","VSS"],color=TEAL,label=False)
    d.text(1490,735,"MREF",18,TEAL,True)
    d.line([(1398,730),(1375,730),(1375,622),(1460,622)],PURPLE)
    d.dot(1460,622,TEAL)
    d.text(1380,606,"BIAS",18,PURPLE)
    d.line([(1460,782),(1460,852),(330,852)])
    d.dot(740,852)
    d.dot(1150,852)
    d.ground(900,852)
    d.text(940,875,"VSS",18)
    d.box(48,925,476,198,"两位输入 → 三位温度计码",color=PURPLE)
    for x,label in [(68,"输入码"),(204,"t₁ t₂ t₃"),(336,"理想 LED 电流")]:
        d.text(x,992,label,18)
    for j,(code,therm,current) in enumerate([("00","0 0 0","0"),("01","1 0 0","Iu"),("10","1 1 0","2Iu"),("11","1 1 1","3Iu")]):
        for x,value in [(68,code),(204,therm),(336,current)]:
            d.text(x,1021+29*j,value,18)
    d.box(548,925,478,198,"图中的每个单元持续转向",[
        "ti = 1：Gi+ 高于 Gi−，主要电流流 LED。",
        "ti = 0：主要电流流 RDi → MDi。",
        "三只尾电流管一直偏置，理想总尾电流约 3Iu。",
        "关掉尾源是另一低功耗变体，需重新验证",
        "启动、建立时间和数据相关失真。"],TEAL,size=18)
    d.box(1050,925,500,198,"PAM4 的额外要求",[
        "输入码经锁存／译码／匹配前置驱动产生 Gi±。",
        "4 电平意味着每符号原始承载 2 bit。",
        "等电流间隔不自动等于等光功率间隔。",
        "需校准 L–I 非线性、失配、温漂和动态毛刺；",
        "相邻眼的裕量、BER 和接收复杂度决定收益。"],BLUE,size=18)
    d.footer(["所有 NMOS 的 B = VSS。同名 BIAS 相连，绕线跳弧表示交叉不连接。本图不含非零光偏置；如需 I₀，另加并验证偏置支路。",
              "等效 IREF、码表及电流比例用于讲解；没有规定实际 Iu、W/L、带宽、供电或光学效率，也没有产生仿真性能。"])
    return d.save('route-c')


def floorplan(route):
    titles={"a":"受限摆幅推挽", "b":"差分电流转向", "c":"分段电流 DAC"}
    d=Drawing(f"路线 {route.upper()}｜{titles[route]}的概念芯片分区", "用于讨论功能相邻关系与高频电流回路；不是 GDS、布线结果或可制造版图，面积与比例均未确定",1080)
    d.p.append('<rect x="48" y="170" width="1290" height="734" rx="18" fill="#fbfcfd" stroke="#233d4b" stroke-width="2.5"/>')
    d.text(72,204,"候选发送端 ASIC",23,bold=True)
    d.box(80,230,1200,64,"电源入口与局部去耦：数字电源、输出电源、偏置电源分别预算",color=BLUE)
    d.box(82,351,245,175,"数字输入／测试",["外部数据与时钟接口","PRBS／测试模式","必要时加 Serializer"],PURPLE,size=18)
    d.box(375,351,236,175,"重定时与控制",["时钟与数据对齐","电平／幅度配置","保护状态与校准"],PURPLE,size=18)
    d.box(659,351,235,175,"前置驱动",["共模与摆幅设定","匹配延迟与负载","局部快速栅极回流"],PURPLE,size=18)
    if route=="a":
        d.box(940,330,337,235,"输出区：推挽单元",["PMOS 上拉 ＋ NMOS 下拉","可分段调整驱动强度","摆幅电源轨与限流元件","输出监测／幅度校准"],ORANGE,size=18)
        outputnotes=["上下管交越、输出节点 C","多电源端压、局部供电扰动"]
    elif route=="b":
        d.box(940,330,337,235,"输出区：电流舵",["LED 与 dummy 开关相邻","尾电流管保持偏置","dummy 负载与支路压降","两路驱动和回流匹配"],ORANGE,size=18)
        outputnotes=["LED／dummy 两支路动态","尾节点扰动、负载匹配"]
    else:
        d.box(940,330,337,235,"输出区：电流单元阵列",["单位电流源与选择开关","分段译码及局部锁存","对称布置与公共偏置","可选 dummy／校准单元"],ORANGE,size=18)
        outputnotes=["单元匹配与时钟偏斜","寄生梯度、码相关毛刺"]
    for x1,x2 in [(327,375),(611,659),(894,940)]:
        d.arrow(x1,435,x2,435,PURPLE)
    d.box(82,618,529,170,"慢速模拟区：参考、偏置、监测",["参考源／偏置缓冲与温度或电流检测","保护关断与上电时序；偏置稳定性单独验证","与高摆幅数据和大电流共享阻抗保持可控"],TEAL,size=18)
    d.box(659,618,618,170,"该路线需要优先提取并检查",[
        *outputnotes,
        "所有路线：pad／ESD／封装／LED 接点及共同回流"],BLUE,size=18)
    d.line([(611,700),(635,700),(635,582),(1120,582),(1120,565)],TEAL,2.8,"8 5")
    d.text(681,602,"低噪声偏置／慢速设置",17,TEAL)
    d.box(82,825,1195,54,"供电回流与测试可达：实际金属宽度、过孔、屏蔽、去耦必须由 PEX／PI／EM 决定",color=BLUE,size=18)
    d.p.append('<rect x="1306" y="406" width="32" height="59" rx="3" fill="#f8ead9" stroke="#c97925" stroke-width="2"/>')
    d.text(1261,390,"输出焊盘／凸点",16,ORANGE)
    d.line([(1277,435),(1306,435)],ORANGE,4)
    d.arrow(1404,435,1338,435,ORANGE)
    d.box(1409,365,143,140,"MicroLED",["独立裸片","或外接器件"],ORANGE,size=16)
    d.line([(1280,262),(1478,262),(1478,365)],BLUE,3)
    d.arrow(1478,300,1478,347,BLUE)
    d.text(1381,242,"VLED 供电",18,BLUE)
    d.text(1500,344,"A",16,MUTE)
    d.text(1384,421,"K",16,MUTE)
    d.line([(1338,850),(1478,850)],BLUE,3)
    d.arrow(1355,850,1422,850,BLUE)
    d.ground(1478,850)
    d.lines(1365,568,["亮态电流：", "LED → 输出管", "→ 芯片回流", "→ 供电负端", "关键回路需", "整体建模"],18,30,BLUE)
    d.footer(["紫色箭头为数据信号；芯片外橙／蓝箭头为亮态传统电流及回流。方框大小不代表面积，电源线不代表已完成电源网络。",
              "仍需选 PDK／器件／封装并完成晶体管设计、时序、电气与光学模型、DRC／LVS／PEX、可靠性与实物验证。"])
    return d.save(f'floorplan-{route}')


def bench_linear():
    d=Drawing("研究平台｜DC 偏置＋AC 线性调制与 Bias-T", "用于 LED 电光响应、均衡与多载波波形研究；是台架架构，不是另一颗已实现的集成 ASIC",1080)
    d.box(48,354,228,152,"数据与 DSP",["PRBS／PAM／DMT","波形与预加重","记录采样率及码率"],PURPLE,size=18)
    d.box(331,354,222,152,"AWG／高速 DAC",["数字样本 → 电压","记录量化及摆幅","电气带宽与失真"],PURPLE,size=18)
    d.box(610,354,226,152,"RF 线性放大器",["偏置在放大工作区","检查压缩与噪声","计入直流供电功耗"],BLUE,size=18)
    d.arrow(276,430,331,430,PURPLE)
    d.arrow(553,430,610,430,PURPLE)
    d.line([(836,430),(939,430)],BLUE)
    d.line([(939,401),(939,459)],BLUE,4)
    d.line([(953,401),(953,459)],BLUE,4)
    d.line([(953,430),(1120,430)],BLUE)
    d.text(897,382,"C_AC",22,BLUE,True)
    d.text(875,491,"隔直、耦合交流",18,BLUE)
    d.box(998,159,317,110,"DC 偏置／限流电源",["设置 I₀；电流与电压均有上限"],TEAL,size=18)
    d.line([(1120,269),(1120,282)],TEAL)
    d.p.append(f'<path d="M1120,282 c26,0 26,20 0,20 c26,0 26,20 0,20 c26,0 26,20 0,20 c26,0 26,20 0,20" fill="none" stroke="{TEAL}" stroke-width="3"/>')
    d.line([(1120,362),(1120,508)],TEAL)
    d.text(1160,328,"L_DC",22,TEAL,True)
    d.text(1160,360,"通 DC、隔离 RF",18,TEAL)
    d.dot(1120,430)
    d.text(1142,455,"偏置与 AC 在此叠加",18)
    d.arrow(1075,352,1075,397,TEAL)
    d.arrow(985,403,1048,403,BLUE)
    d.led(1120,550)
    d.text(1170,619,"MicroLED",21,ORANGE,True)
    d.line([(1120,592),(1120,698)])
    d.ground(1120,698)
    d.text(1160,716,"DC 与 RF 回流",18)
    d.box(1305,510,246,153,"光接收／分析",["PD／TIA／采样仪","眼图、E/O S21、BER","校准与去嵌"],ORANGE,size=18)
    d.arrow(1188,551,1290,551,ORANGE,"8 5")
    d.text(1234,535,"光",18,ORANGE)
    d.box(48,575,788,155,"C 与 L 必须在实际频带内工作",[
        "C_AC、L_DC 与源／负载阻抗共同决定频响、低频下垂与谐振。",
        "检查电感自谐振、电流额定值及 LED 非线性；不默认全链路 50 Ω。",
        "RF 增益不等于 LED 光学带宽，也不等于接收后的可用数据速率。"],BLUE,size=18)
    d.box(48,784,1504,156,"与三类 ASIC 路线比较时保持同一测量边界",[
        "PAM／DMT／OFDM 属于调制与波形选择；不能仅凭平台名称确定电路能耗。平台总功耗应分别记录 AWG、RF 放大器、偏置及接收端。",
        "V_LED(t) 与 I_LED(t) 必须在允许范围内；负向交流摆幅不能任意使 LED 反偏。必要时增加限幅、保护和经过验证的放电支路。",
        "FFE／预加重能用于 A、B、C 或本平台；它改变瞬态峰值与平均能耗，需对相同数据、光接收条件及 BER 重新比较。"],PURPLE,size=18)
    d.footer(["本图的 L/C 为真实电路元件类别，其数值和模型尚未确定；简化图省略阻抗匹配、仪器电源与保护网络。",
              "台架能力、集成 ASIC 能力和完整链路能耗分别报告；不得把不同平台的最佳速率与最低能耗拼成一个产品指标。"])
    return d.save('bench-linear')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--raster',action='store_true')
    ap.add_argument('--raster-font',default='Arial Unicode MS',
                    help='Installed full-Unicode font for Cairo PNG previews; SVG keeps the preferred font stack.')
    args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    results=[route_a(),route_b(),route_c(),floorplan('a'),floorplan('b'),floorplan('c'),bench_linear()]
    metadata={"evidence_level":"original conceptual schematics, not transistor/physical validation", "schema":1,
              "terminal_order":"D G S B","connections":results,
              "scope":["route A voltage-mode limited swing with resistor and required calibration", "route B continuously biased current steering", "route C three unary steering cells explaining PAM4", "bench AC/DC characterization"],
              "checks":{"unique_device_names":all(len(r['devices'])==len(set(r['devices'])) for r in results),
                        "all_mos_four_terminal_assignments":all(set(v)=={'D','G','S','B','type'} for r in results for v in r['devices'].values()),
                        "route_b_dummy_and_led_share_tail":results[1]['devices']['ML']['S']==results[1]['devices']['MD']['S']==results[1]['devices']['MI']['D'],
                        "route_c_reference_diode_connected":results[2]['devices']['MREF']['D']==results[2]['devices']['MREF']['G'],
                        "route_a_complementary_common_output":results[0]['devices']['MP']['D']==results[0]['devices']['MN']['D']=='OUT',
                        "route_b_mirror_bias_connected":results[1]['devices']['MREF']['G']==results[1]['devices']['MREF']['D']==results[1]['devices']['MI']['G'],
                        "route_c_three_distinct_tails":len({results[2]['devices'][f'MI{i}']['D'] for i in range(1,4)})==3,
                        "route_c_led_bus_shared":all(results[2]['devices'][f'ML{i}']['D']=='LED_K' for i in range(1,4)),
                        "route_c_mirror_gates_share_bias":all(results[2]['devices'][f'MI{i}']['G']=='BIAS' for i in range(1,4)),
                        "route_c_steering_pairs_share_tail":all(results[2]['devices'][f'ML{i}']['S']==results[2]['devices'][f'MD{i}']['S']==results[2]['devices'][f'MI{i}']['D'] for i in range(1,4))},
              "visual_reviewed":False}
    assert all(metadata['checks'].values())
    if args.raster:
        # Deterministic SVG rasterization; no browser automation is required.
        import cairosvg
        for item in results:
            source=(OUT/item['file']).read_text().replace(
                '"PingFang SC","Noto Sans CJK SC",Arial,sans-serif',
                '"'+escape(args.raster_font, quote=True)+'"')
            cairosvg.svg2png(bytestring=source.encode('utf-8'),
                            write_to=str(OUT/item['file'].replace('.svg', '.png')),
                            output_width=item['size'][0], output_height=item['size'][1])
    (OUT/'circuit-metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({"figures":[r['file'] for r in results],"checks":metadata['checks']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
