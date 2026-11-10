#!/usr/bin/env python3
"""Original diagrams and clearly attributed plots for the stage report."""
from pathlib import Path
import html, os, subprocess, re, shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/blue-emitter-speed-review-20261110'
ASSET=DOC/'assets'

def setup():
    ASSET.mkdir(parents=True,exist_ok=True)
    font='/System/Library/Fonts/Hiragino Sans GB.ttc'
    font_manager.fontManager.addfont(font)
    plt.rcParams.update({'font.family':[font_manager.FontProperties(fname=font).get_name(),'DejaVu Sans'],'font.size':12,'axes.unicode_minus':False,'svg.fonttype':'none'})

def source_size():
    # Dai et al., Chinese Optics Letters 23,082501 (2025), Tables 1 and 2.
    # Independent reported maxima; not one common bias point.
    sizes=[10,20,40,50,60,80]
    fig,axs=plt.subplots(1,2,figsize=(11.8,4.4),layout='constrained')
    for ax,blue,violet,label in [(axs[0],[360,332,283,258,229,163],[336,313,228,203,185,168],'报告的最大调制带宽 / MHz'),(axs[1],[.890,1.032,.799,.741,.616,.580],[1.095,1.347,.856,.782,.768,.694],'报告的 OOK 最大数据率 / Gb/s')]:
        ax.plot(sizes,blue,'o-',color='#287b9d',label='蓝光',lw=2)
        ax.plot(sizes,violet,'s--',color='#7f63a4',label='紫光',lw=2)
        ax.set(xlabel='圆形器件直径 / µm',ylabel=label,xticks=sizes)
        ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.17);ax.legend(frameon=False)
    fig.savefig(ASSET/'size-bandwidth-rate.png',dpi=180);plt.close(fig)

def signal_map():
    font='font-family="PingFang SC,Hiragino Sans GB,Arial,sans-serif"'
    def text(x,y,s,size=21,col='#243f49'):
        return f'<text x="{x}" y="{y}" {font} font-size="{size}" fill="{col}">{html.escape(s)}</text>'
    def line(d,col='#527b82',width=3):return f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{width}"/>'
    def box(x,y,w,h):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="#edf4f3" stroke="#b7cecd" stroke-width="2"/>'
    z=[text(28,39,'先区分三条响应，再决定改电路还是改器件',27)]
    z +=[text(30,90,'电气参考面',22),text(432,90,'发光参考面',22),text(833,90,'接收参考面',22)]
    z +=[box(28,109,335,115),text(45,145,'输入 → 门驱 → 输出 MOS',23),text(45,181,'端口电流 = 导电 + 充放电',20),text(45,209,'观察门极摆幅 / 电荷 / 端压',18)]
    z +=[box(430,109,335,115),text(446,145,'MicroLED 或 VCSEL',23),text(446,181,'复合寿命或激光弛豫 / 阻尼',20),text(446,209,'观察 P(t)、OMA 和频响',18)]
    z +=[box(832,109,335,115),text(848,145,'光路 → PD/TIA → 判决',23),text(848,181,'光损耗、带宽、噪声、时钟',20),text(848,209,'独立训练后验证错误与余量',18)]
    for x in [365,767]:z +=[line(f'M{x} 161 L{x+58} 161 M{x+48} 153 L{x+58} 161 L{x+48} 169')]
    z +=[line('M28 252 L1166 252','#d3dfdf',2),text(30,291,'LED 电气负载分解（教学示意，参数扫描不能当作尺寸换算）',23)]
    z +=[line('M144 330 L330 330 M144 330 L144 358 M330 330 L330 365'),text(30,335,'阳极 VA',20),line('M120 358 L168 358 L144 402 Z M120 407 L168 407 M144 407 L144 449'),text(38,390,'I–V',20)]
    z +=[line('M305 365 L355 365 M305 386 L355 386 M330 386 L330 449 M144 449 L330 449 M240 449 L240 470 L230 470 L230 503 L250 503 L250 470 M240 503 L240 524'),text(363,379,'Cj + pad + ESD',20),text(267,497,'R / L 封装和回流',20),text(30,546,'阴极 VK → Driver 输出端',20)]
    z +=[box(566,310,600,244),text(585,347,'每个频率点都运行实际晶体管网表',24),text(585,388,'1. 保持 I0/I1、负载、光响应和 RX',21),text(585,428,'2. 改变真实输入码流的位周期',21),text(585,468,'3. 同时检查零错、幅度、时间和应力',21),text(585,508,'4. 找到通过点与失效点，再细扫',21)]
    p=ASSET/'reference-planes.svg';p.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="580" viewBox="0 0 1200 580"><rect width="1200" height="580" fill="white"/>'+''.join(z)+'</svg>\n')
    raster(p,ASSET/'reference-planes.png')

def raster(src,dst):
    import cairosvg
    # Cairo's chosen CJK face does not reliably fall back for arrow/math glyphs.
    # Substitute only text-node glyph spans for rendering; original SVG untouched.
    text=Path(src).read_text()
    text=re.sub(r'>([^<>]*)<',lambda m:'>'+''.join(
        '<tspan font-family="Arial">'+ch+'</tspan>' if ch in '→←↑↓Ωµμτ≈×²−≤≥' else ch
        for ch in m.group(1))+'<',text)
    cairosvg.svg2png(bytestring=text.encode(),write_to=str(dst),scale=1.35)

def reused_circuits():
    # Reuse the project's larger-label teaching schematic for printable legibility.
    shutil.copy2(ROOT/'docs/research/project-progress-review-20261108/assets/vcsel-core.png',ASSET/'vcsel-core.png')
    old=ROOT/'docs/research/highspeed-workbench-20261110/physical'
    # Preserve genuine rendered GDS geometry; compose views without editing geometry.
    ims=[Image.open(old/'actual-layout-2d.png').convert('RGB'),Image.open(old/'core-b-3d.png').convert('RGB')]
    canvas=Image.new('RGB',(1800,680),'white')
    for x,im in zip([0,900],ims):
        im.thumbnail((890,670));canvas.paste(im,(x+(890-im.width)//2,(680-im.height)//2))
    canvas.save(ASSET/'physical-evidence.png')

def switching_core():
    """Logical connectivity from the B schematic; bias generators not expanded."""
    font='font-family="PingFang SC,Hiragino Sans GB,Arial,sans-serif"'
    def tx(x,y,s,size=21):return f'<text x="{x}" y="{y}" {font} font-size="{size}" fill="#213e49">{html.escape(s)}</text>'
    def path(d,c='#286f76',w=3):return f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{w}"/>'
    def mos(x,y,label):
        # Gate insulated from the channel, drain top and source bottom.
        return path(f'M{x} {y-50} L{x} {y-25} L{x-18} {y-25} M{x-18} {y-25} L{x-18} {y+25} M{x-18} {y+25} L{x} {y+25} L{x} {y+50} M{x-30} {y-27} L{x-30} {y+27} M{x-80} {y} L{x-30} {y}')+tx(x+17,y+7,label,20)
    def gnd(x,y):return path(f'M{x} {y} L{x} {y+12} M{x-19} {y+12} L{x+19} {y+12} M{x-12} {y+20} L{x+12} {y+20} M{x-5} {y+28} L{x+5} {y+28}')
    z=[tx(25,38,'B 电流转向核心：直流支路设低位，数据把调制电流换到两条路径',25),
       tx(25,71,'连接关系摘自 B 网表。四只 NMOS 的体端接 VSS，偏置生成和预驱动级未展开。',19),
       path('M105 108 L450 108 M380 108 L380 144 M735 108 L920 108 M835 108 L835 150'),tx(110,98,'VLED',20),tx(738,98,'VIN',20),
       path('M359 144 L401 144 L380 181 Z M357 185 L403 185 M380 185 L380 215 L170 215 L170 244 M380 215 L380 244'),
       tx(460,170,'MicroLED',22),path('M414 155 L438 136 L429 138 M438 136 L435 145 M428 161 L452 142 L443 144 M452 142 L449 151'),
       path('M825 150 L845 150 L845 195 L825 195 Z M835 195 L835 244'),tx(874,176,'RDUMMY 50 kΩ',21),tx(397,229,'OUT',18),
       mos(170,294,'XBASE'),mos(380,294,'XLED'),mos(835,294,'XDUMMY'),
       tx(42,283,'BIAS',19),path('M42 294 L90 294'),tx(262,282,'GP',20),path('M270 294 L300 294'),tx(710,282,'GB',20),path('M710 294 L755 294'),
       path('M170 344 L170 450 M380 344 L380 376 L835 376 L835 344 M603 376 L603 402'),tx(620,367,'VX',18),gnd(170,450),mos(603,452,'XTAIL'),
       tx(472,440,'BIAS',20),path('M472 452 L523 452'),gnd(603,502),
       tx(25,548,'低位目标 25 µA：XBASE 保持导通；调制电流流过 RDUMMY / XDUMMY。',22),
       tx(25,581,'高位目标 100 µA：调制支路另提供约 75 µA，经 MicroLED / XLED。',22),
       tx(25,618,'限制来自门驱摆幅和时差、输出储能、尾管合规电压、dummy 匹配及回流寄生。',21)]
    z +=[f'<circle cx="{x}" cy="{y}" r="4" fill="#286f76"/>' for x,y in [(380,108),(380,215),(603,376)]]
    p=ASSET/'b-principle.svg';p.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="645" viewBox="0 0 1200 645"><rect width="1200" height="645" fill="white"/>'+''.join(z)+'</svg>\n')
    raster(p,ASSET/'b-principle.png')

if __name__=='__main__':
    setup();source_size();signal_map();reused_circuits();switching_core()
