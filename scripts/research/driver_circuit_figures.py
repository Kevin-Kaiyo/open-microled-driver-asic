"""Standard component schematics explaining driver and interconnect mechanisms.

These are original teaching schematics, not layout masks or new transistor runs.
The six-MOS diagram follows analog/driver/pixel_driver.spice. Other diagrams
are simplified examples with explicitly stated voltage reference assumptions.
"""
from pathlib import Path
import base64
import io
import json
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BASE=Path(__file__).resolve().parents[2]/'docs/research/driver-circuit-layout-20261012'
FIG=BASE/'figures'
INK='#304b57';TEAL='#176e73';ORANGE='#b56336'


class Drawing:
    def __init__(self,width,height,title,desc):
        self.width=width;self.height=height;self.parts=[];self.title=title;self.desc=desc
        self.text(24,32,title,24,TEAL,True)

    def text(self,x,y,value,size=19,color=INK,bold=False):
        from html import escape
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}"'+(' font-weight="600"' if bold else '')+f'>{escape(value)}</text>')

    def wire(self,points,color=INK,dash=None):
        self.parts.append(f'<polyline points="'+ ' '.join(f'{x},{y}' for x,y in points)+f'" fill="none" stroke="{color}" stroke-width="2.2"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')

    def dot(self,x,y,color=INK):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="3.5" fill="{color}"/>')

    def arrow(self,x1,y1,x2,y2,color=TEAL):
        self.parts.append(f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{color}" stroke-width="2.5" fill="none" marker-end="url(#'+('orange' if color==ORANGE else ('gray' if color==INK else 'arrow'))+')"/>')

    def ground(self,x,y,label='GND₀'):
        self.wire([(x,y-10),(x,y)])
        for i,w in enumerate([15,10,5]): self.wire([(x-w,y+5*i),(x+w,y+5*i)])
        self.text(x-28,y+34,label,17)

    def mos(self,cx,cy,name,p=False,dimensions=None,terminals=False):
        # Standard three-terminal enhancement MOS symbol, body ties stated in caption.
        ch=cx-6;gx=cx-17;tx=cx+18
        for top,bot in [(-18,-8),(-4,4),(8,18)]: self.wire([(ch,cy+top),(ch,cy+bot)])
        self.wire([(gx,cy-19),(gx,cy+19)])
        self.wire([(tx,cy-40),(tx,cy-17),(ch,cy-17)])
        self.wire([(ch,cy+17),(tx,cy+17),(tx,cy+40)])
        if p:
            self.wire([(cx-40,cy),(cx-31,cy)]);self.parts.append(f'<circle cx="{cx-27}" cy="{cy}" r="4" fill="white" stroke="{INK}" stroke-width="2"/>');self.wire([(cx-23,cy),(gx,cy)])
        else: self.wire([(cx-40,cy),(gx,cy)])
        self.text(cx+43,cy-7,name,19,bold=True)
        self.text(cx+43,cy+16,('PMOS' if p else 'NMOS')+((' '+dimensions) if dimensions else ''),15)
        if terminals:
            self.text(cx-54,cy-9,'G',17);self.text(tx+7,cy-34,'S' if p else 'D',17);self.text(tx+7,cy+41,'D' if p else 'S',17)
        return {'G':(cx-40,cy),'D':(tx,cy+(40 if p else -40)),'S':(tx,cy+(-40 if p else 40))}

    def resistor(self,x,y,label,horizontal=False,color=ORANGE):
        if horizontal:
            self.wire([(x-36,y),(x-23,y)]);self.parts.append(f'<rect x="{x-23}" y="{y-9}" width="46" height="18" fill="white" stroke="{color}" stroke-width="2.2"/>');self.wire([(x+23,y),(x+36,y)]);self.text(x-20,y-18,label,18,color)
        else:
            self.wire([(x,y-36),(x,y-23)]);self.parts.append(f'<rect x="{x-9}" y="{y-23}" width="18" height="46" fill="white" stroke="{color}" stroke-width="2.2"/>');self.wire([(x,y+23),(x,y+36)]);self.text(x+24,y+6,label,18,color)

    def led(self,x,y,label='LED'):
        self.wire([(x,y-32),(x,y-14)]);self.parts.append(f'<path d="M{x-13} {y-14} L{x+13} {y-14} L{x} {y+9} Z M{x-16} {y+11} H{x+16}" fill="none" stroke="{INK}" stroke-width="2.2"/>');self.wire([(x,y+11),(x,y+32)])
        self.arrow(x+20,y-7,x+36,y-24,INK);self.arrow(x+26,y+3,x+42,y-13,INK)
        self.text(x-75,y+4,label,18);self.text(x-22,y-22,'A',14);self.text(x-22,y+29,'K',14)

    def source(self,x,y,label,current=False):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="22" fill="white" stroke="{INK}" stroke-width="2.2"/>')
        self.wire([(x,y-32),(x,y-22)]);self.wire([(x,y+22),(x,y+32)])
        if current: self.arrow(x,y-12,x,y+13)
        else: self.text(x-6,y-4,'+',18);self.text(x-5,y+16,'−',18)
        self.text(x+34,y+5,label,18)

    def save(self,name):
        from html import escape
        head=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(self.title)}</title><desc id="desc">{escape(self.desc)}</desc>
<style>text{{font-family:'Avenir Next','PingFang SC',sans-serif}}path,polyline,line,rect{{stroke-linejoin:round;stroke-linecap:round}}</style>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10" fill="{TEAL}"/></marker><marker id="orange" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10" fill="{ORANGE}"/></marker><marker id="gray" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10" fill="{INK}"/></marker></defs>
<rect width="{self.width}" height="{self.height}" fill="white"/>'''
        (FIG/name).write_text(head+'\n'.join(self.parts)+'</svg>\n')


def main():
    FIG.mkdir(parents=True,exist_ok=True)
    d=Drawing(1120,535,'六MOS像素：LED电流与栅极控制电路','按实际网表绘制。栅极偏置开关不在LED主电流支路中。')
    d.text(90,75,'Vlogic',19);d.wire([(128,80),(128,108)]);d.source(128,140,'IREF',True);d.wire([(128,172),(128,215),(128,260)])
    d.mos(110,300,'MREF',dimensions='20/4 µm');d.wire([(70,300),(45,300),(45,215),(128,215)]);d.dot(128,215);d.text(48,197,'VBIAS',18,TEAL)
    d.wire([(128,340),(128,365)]);d.ground(128,365,'GND')
    d.mos(365,240,'MPASS',dimensions='2/1 µm');d.wire([(128,215),(220,215),(220,172),(383,172),(383,200)],TEAL)
    d.wire([(325,240),(287,240)]);d.text(252,266,'PWM',18)
    d.wire([(383,280),(600,280),(600,300),(665,300)],TEAL);d.dot(600,300);d.text(602,265,'VG',18,TEAL)
    d.mos(520,365,'MCLAMP',dimensions='2/1 µm');d.wire([(600,300),(538,300),(538,325)],TEAL);d.wire([(538,405),(538,438)]);d.ground(538,438,'GND')
    d.wire([(480,365),(433,365)]);d.text(397,399,'PWM_B',18)
    d.mos(705,300,'MOUT',dimensions='20/4 µm',terminals=True);d.text(698,75,'VLED',19);d.wire([(723,82),(723,118)]);d.led(723,150);d.wire([(723,182),(723,260)])
    d.wire([(723,340),(723,405)]);d.ground(723,405,'GND');d.arrow(808,178,808,267);d.text(823,222,'ILED',18,TEAL)
    d.text(884,75,'Vlogic',19);d.mos(945,150,'MP',True,'4/1 µm');d.mos(945,290,'MN',dimensions='2/1 µm')
    d.wire([(963,82),(963,110)]);d.wire([(963,190),(963,250)]);d.dot(963,220);d.wire([(963,220),(1030,220)]);d.text(970,244,'PWM_B',17)
    d.wire([(905,150),(865,150),(865,290),(905,290)]);d.wire([(865,290),(865,365)]);d.text(838,399,'PWM',18)
    d.wire([(963,330),(963,365)]);d.ground(963,365,'GND')
    d.text(25,520,'同名网络电气相连；NMOS体端接GND，PMOS体端接Vlogic。IREF是外部理想电流源。',17)
    d.save('architectures.svg')

    d=Drawing(920,450,'电流舵型驱动：两只MOS开关选择电流支路','简化教学电路，不是论文电路复制，未包含共源共栅、偏置发生器和缓冲器。')
    d.text(133,75,'VLED',19);d.text(443,75,'VDUMMY',19);d.wire([(168,83),(168,93)]);d.led(168,125)
    d.wire([(168,157),(168,190)]);d.mos(150,230,'MS1',terminals=True)
    d.wire([(478,83),(478,99)]);d.resistor(478,135,'RDUMMY',color=INK);d.wire([(478,171),(478,190)]);d.mos(460,230,'MS2',terminals=True)
    d.wire([(168,270),(168,295),(478,295),(478,270)]);d.dot(323,295);d.wire([(323,295),(323,295)])
    d.mos(305,335,'MI');d.wire([(323,375),(323,390)]);d.ground(323,390)
    d.wire([(110,230),(55,230)]);d.text(38,211,'DATA',17);d.wire([(420,230),(372,230)]);d.text(360,207,'DATA_B',17)
    d.wire([(265,335),(185,335)]);d.text(125,323,'VBIAS',17,TEAL);d.arrow(277,351,277,379);d.text(250,374,'I',18,TEAL)
    d.text(614,139,'DATA=1：MS1导通',20,TEAL,True);d.text(614,169,'电流流过LED',19)
    d.text(614,221,'DATA=0：MS2导通',20,TEAL,True);d.text(614,251,'电流流过旁路负载',19)
    d.text(614,310,'MI保持偏置；旁路仍耗电',18)
    d.text(614,343,'新增串联MOS需要电压余量',18)
    d.text(20,445,'RDUMMY是示意等效负载；不表示H05采用该电阻。省略体端、缓冲及共源共栅器件。',16)
    d.save('current-steering.svg')

    d=Drawing(960,470,'源极走线电阻：抬高源极电位，改变VGS','假设VG相对远端GND0不变，源极串联电阻改变实际自洽电流。')
    for cx,xg,title in [(175,65,'① 理想源极接地'),(505,395,'② 加入源极走线电阻')]:
        tx=cx+18;d.text(cx-75,77,title,18,bold=True);d.text(tx-29,112,'VLED',17);d.wire([(tx,117),(tx,125)]);d.led(tx,157);d.wire([(tx,189),(tx,207)])
        d.mos(cx,247,'MOUT',terminals=True);d.source(xg,280,'VG');d.wire([(xg,248),(xg,247),(cx-40,247)])
        d.wire([(xg,312),(xg,343)]);d.ground(xg,343)
        if cx==175: d.wire([(tx,287),(tx,343)]);d.ground(tx,343);d.text(tx+25,315,'VS=0',18,TEAL)
        else:
            d.dot(tx,292);d.text(tx+22,299,'VS',18,ORANGE);d.wire([(tx,287),(tx,304)]);d.resistor(tx,340,'RS');d.wire([(tx,376),(tx,381)]);d.ground(tx,381)
    d.text(693,139,'VG固定于GND₀',20,bold=True);d.text(693,188,'VS = ID · RS',22,ORANGE);d.text(693,227,'VGS = VG − VS',22,TEAL)
    d.text(693,275,'ID为加入RS后的实际电流',17);d.text(693,309,'若栅极偏置跟随VS，',17);d.text(693,334,'须重新计算VGS的变化。',17)
    d.text(23,455,'简化直流例子；体端省略，未计体效应。参考管与输出管共用源极时，变化可能部分为共模。',16)
    d.save('source-resistance.svg')

    d=Drawing(960,460,'LED支路走线电阻：消耗输出NMOS的电压余量','主电流经LED、漏极走线电阻、输出NMOS、源极电阻回到GND0。')
    d.text(91,75,'VLED',19);d.wire([(128,82),(128,88)]);d.led(128,120);d.text(192,125,'VF(ID)',18,TEAL)
    d.wire([(128,152),(128,159)]);d.resistor(128,195,'RD');d.wire([(128,231),(128,247)]);d.mos(110,287,'MOUT',terminals=True)
    d.wire([(70,287),(25,287)]);d.text(20,273,'VG',17,TEAL);d.wire([(128,327),(128,331)]);d.resistor(128,367,'RS');d.wire([(128,403),(128,409)]);d.ground(128,409)
    d.arrow(285,95,285,396);d.text(294,249,'ID',18,TEAL)
    d.text(356,97,'VDS = VLED − VF(ID) − ID(RD+RS)',21,TEAL,True)
    d.text(356,145,'RD：漏极与LED连接的等效走线电阻',18);d.text(356,177,'RS：源极至GND₀的等效走线电阻',18)
    d.text(356,223,'VDS不足时，电流不能保持目标值。',20,ORANGE,True)
    d.text(356,263,'静态计算点：5 V − 3.76791 V = 1.23209 V',18)
    d.text(356,294,'这部分电压还未扣除走线压降。',18)
    d.text(356,335,'示意图的MPASS没有串入LED电流支路。',17)
    d.text(356,372,'VF随实际电流变化；需计算完整工作点。',17)
    d.text(356,410,'数值使用一条20 µm黄光LED静态曲线。',16)
    d.save('headroom.svg')

    d=Drawing(1040,430,'栅极走线RC：驱动电压与栅极电压不同步','理想阶跃驱动、线性等效Cg和固定源极电位下的解析计算，波形不是LED电流。')
    d.source(68,223,'VDRV');d.wire([(68,191),(68,140),(166,140)]);d.resistor(202,140,'RG',True);d.wire([(238,140),(320,140)]);d.dot(320,140);d.text(302,118,'VG',20,TEAL)
    d.wire([(320,140),(320,207)]);d.wire([(300,207),(340,207)]);d.wire([(300,221),(340,221)]);d.wire([(320,221),(320,309)]);d.ground(320,309)
    d.text(348,217,'CG',19,ORANGE);d.text(23,380,'CG：输出MOS栅极的等效电容',16)
    d.wire([(68,255),(68,309)]);d.ground(68,309);d.arrow(246,165,301,165);d.text(198,195,'充电电流',16,TEAL)
    plt.rcParams.update({'font.family':'Avenir Next','svg.fonttype':'none','font.size':12})
    fig,ax=plt.subplots(figsize=(5.3,2.6),layout='constrained');t=np.linspace(0,5,501)
    ax.plot([0,0,5],[0,1,1],color=INK,linestyle='--',label='VDRV / Vstep')
    for r,c in [(100,TEAL),(1000,ORANGE)]: ax.plot(t,1-np.exp(-t/(r*1e-3)),color=c,label=f'VG: RG={r} ohm')
    ax.set(xlabel='Time (ns)',ylabel='Normalized voltage',xlim=(0,5),ylim=(0,1.08));ax.grid(alpha=.15);ax.legend(frameon=False,fontsize=10,loc='lower right');ax.spines[['top','right']].set_visible(False)
    buf=io.BytesIO();fig.savefig(buf,format='svg');plt.close(fig);d.parts.append('<image x="445" y="65" width="570" height="300" href="data:image/svg+xml;base64,'+base64.b64encode(buf.getvalue()).decode()+'"/>')
    d.text(445,387,'CG=1 pF：RG=100 Ω时t10–90≈0.220 ns；1 kΩ时≈2.20 ns',17)
    d.text(23,421,'教学假设：CG为偏置附近的线性等效节点电容；不代表已测Cgg或光学响应。',16)
    d.save('gate-rc.svg')

    d=Drawing(1030,545,'共用地线阻抗：邻路电流改变本路的参考电位','两路NMOS源极电流共用RGND与LGND返回GND0。本图栅极偏置以远端GND0为参考。')
    for cx,name,ig in [(145,'M1','I1'),(455,'M2','I2')]:
        tx=cx+18;d.text(tx-20,76,'VLED',18);d.wire([(tx,82),(tx,91)]);d.led(tx,123);d.wire([(tx,155),(tx,185)]);d.mos(cx,225,name,terminals=True)
        gx=cx-80;d.parts.append(f'<circle cx="{gx}" cy="225" r="22" fill="white" stroke="{INK}" stroke-width="2.2"/>');d.text(gx+7,232,'+',18);d.text(gx-17,232,'−',18);d.text(gx-22,191,'VG'+('1' if cx==145 else '2'),17)
        d.wire([(gx+22,225),(cx-40,225)]);d.wire([(gx-22,225),(gx-32,225),(gx-32,255)]);d.ground(gx-32,255)
        d.wire([(tx,265),(tx,316)]);d.arrow(tx+48,266,tx+48,308);d.text(tx+60,289,ig,18,TEAL)
    d.wire([(163,316),(473,316)]);d.dot(325,316);d.text(213,355,'GNDL',20,ORANGE)
    d.wire([(325,316),(325,370),(407,370)]);d.resistor(443,370,'RGND',True);d.wire([(479,370),(525,370)])
    # Conventional inductor humps, two terminals, not an ideal ground at GNDL.
    d.parts.append(f'<path d="M525 370 c0 -22 18 -22 18 0 c0 -22 18 -22 18 0 c0 -22 18 -22 18 0" fill="none" stroke="{ORANGE}" stroke-width="2.2"/>');d.text(527,411,'LGND',18,ORANGE)
    d.wire([(579,370),(627,370),(627,420)]);d.ground(627,420)
    d.arrow(351,462,573,462);d.text(370,487,'共同回流：IΣ=I1+I2',18,TEAL)
    d.text(676,104,'ΔVGNDL ≈ RGND·ΔIΣ',20,ORANGE,True);d.text(692,137,'+ LGND·d(ΔIΣ)/dt',20,ORANGE,True)
    d.text(676,193,'本图VG1相对GND₀固定',18);d.text(676,227,'VGS1 = VG1 − VGNDL',20,TEAL)
    d.text(676,284,'若栅极驱动跟随GNDL，',18);d.text(676,313,'地电位变化不等于VGS扰动。',18)
    d.text(676,372,'GNDL为本地地，不是理想零伏。',18,ORANGE)
    d.text(20,530,'简化回流电阻/电感模型；未计算完整电源网络、衬底、封装及振铃。',16)
    d.save('shared-ground.svg')
    ledger={'classification':'Original teaching schematics and analytical RC calculation; no new EDA or measurement',
        'pixel_driver_netlist':'analog/driver/pixel_driver.spice',
        'pixel_devices':{'MREF':['bias','bias','0','0'],'MOUT':['led_k','gate','0','0'],
            'MPASS':['bias','pwm','gate','0'],'MCLAMP':['gate','pwm_b','0','0'],
            'MN':['pwm_b','pwm','0','0'],'MP':['pwm_b','pwm','vlogic','vlogic']},
        'terminal_order':'D G S B',
        'interconnect_assumptions':{'source_resistance':'Gate voltage fixed to GND0, current solved self-consistently; body effect omitted',
            'headroom':'VF depends on ID; MPASS is a gate switch, not a series LED switch',
            'gate_RC':'Ideal voltage drive, fixed source potential, linear equivalent CG, voltage waveform only',
            'shared_ground':'VG referenced to remote GND0; local-tracking driver is explicitly distinguished'},
        'RC_waveform':{'CG_pF':1,'RG_ohm':[100,1000],'t10_90_ns':[math.log(9)*r*1e-3 for r in [100,1000]]}}
    (BASE/'figure-ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__': main()
