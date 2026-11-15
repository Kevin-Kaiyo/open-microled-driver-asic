#!/usr/bin/env python3
"""Original node-accurate protection mechanism figure. No new SPICE or PEX."""
from pathlib import Path
import html,os
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/driver-interface-20261115/assets'
S=[];INK='#334e60';RED='#b65745';TEAL='#167c76';GRAY='#6b7e8a'
def line(x,y,X,Y,c=INK,w=2.3,dash=None):
 extra=f' stroke-dasharray="{dash}"' if dash else ''
 S.append(f'<path d="M{x},{y} L{X},{Y}" fill="none" stroke="{c}" stroke-width="{w}"{extra}/>')
def path(d,c=INK,w=2.3,arrow=False,dash=None):
 S.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{w}"'+(' marker-end="url(#arrow-red)"' if arrow else '')+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')
def text(x,y,t,size=19,anchor='start',c=INK):S.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{c}" text-anchor="{anchor}">{html.escape(t)}</text>')
def dot(x,y,c=INK):S.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{c}"/>')
def ground(x,y):
 line(x,y,x,y+12);line(x-14,y+12,x+14,y+12);line(x-9,y+19,x+9,y+19);line(x-4,y+26,x+4,y+26)
def resistor(x,y,X,label):
 line(x,y,x+13,y);line(X-13,y,X,y);S.append(f'<rect x="{x+13}" y="{y-9}" width="{X-x-26}" height="18" fill="white" stroke="{INK}" stroke-width="2.3"/>');text((x+X)/2,y-23,label,18,'middle')
def inductor(x,y,X,label):
 line(x,y,x+10,y);step=(X-x-20)/4
 d=f'M{x+10},{y}'
 for k in range(4):d+=f' a{step/2},{step/2} 0 0 1 {step},0'
 path(d);line(X-10,y,X,y);text((x+X)/2,y-23,label,18,'middle')
def cap(x,y,Y,label):
 mid=(y+Y)/2;line(x,y,x,mid-7);line(x-24,mid-7,x+24,mid-7);line(x-24,mid+7,x+24,mid+7);line(x,mid+7,x,Y);text(x+34,mid+4,label,18)
def cap_h(x,y,X,label):
 mid=(x+X)/2;line(x,y,mid-8,y);line(mid-8,y-25,mid-8,y+25);line(mid+8,y-25,mid+8,y+25);line(mid+8,y,X,y);text(mid,y-40,label,19,'middle')
def diode(x,anode_y,cathode_y,led=False,label=None):
 # Current direction: anode -> cathode. Triangle points toward cathode bar.
 sign=1 if cathode_y>anode_y else -1;mid=(anode_y+cathode_y)/2;base=mid-19*sign;tip=mid+14*sign
 line(x,anode_y,x,base);S.append(f'<path d="M{x-18},{base} L{x+18},{base} L{x},{tip} Z" fill="white" stroke="{INK}" stroke-width="2.3"/>');line(x-22,tip,x+22,tip);line(x,tip,x,cathode_y)
 if led:
  path(f'M{x+27},{mid-9} l24,-22 M{x+51},{mid-31} l-10,1 M{x+51},{mid-31} l-1,10',TEAL,2)
  path(f'M{x+40},{mid+5} l24,-22 M{x+64},{mid-17} l-10,1 M{x+64},{mid-17} l-1,10',TEAL,2)
 if label:text(x-38,mid+5,label,18,'end')
def mos(x,y,p,label,gate_label,source_top=True):
 # Vertical channel, external S/D defined in annotations. Body tie is explicit text.
 line(x,y-23,x,y+23);line(x+14,y-22,x+14,y-7);line(x+14,y-4,x+14,y+4);line(x+14,y+7,x+14,y+22)
 line(x+14,y-18,x+36,y-18);line(x+36,y-18,x+36,y-57);line(x+14,y+18,x+36,y+18);line(x+36,y+18,x+36,y+57)
 if p:S.append(f'<circle cx="{x-7}" cy="{y}" r="6" fill="white" stroke="{INK}" stroke-width="2.3"/>');line(x-54,y,x-13,y)
 else:line(x-54,y,x,y)
 text(x-59,y-13,gate_label,16,'end');text(x+53,y+5,label,18)
 return x+36,y-57,y+57
def panel(y,title,sub):
 S.append(f'<rect x="25" y="{y}" width="1290" height="505" rx="12" fill="white" stroke="#d5dfe5"/>');text(50,y+38,title,25);text(50,y+69,sub,18,c=GRAY)
def main():
 S.append('<svg xmlns="http://www.w3.org/2000/svg" width="1340" height="1220" viewBox="0 0 1340 1220"><defs><marker id="arrow-red" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="#b65745"/></marker></defs><style>text{font-family:"Arial Unicode MS","PingFang SC",Arial,sans-serif}</style><rect width="1340" height="1220" fill="#f5f8fa"/>')
 text(30,43,'保护不只是让导电电流变小：两条瞬态注入路径',29)
 text(30,76,'原 protected_v2 的原生波形定位；下图按电气连接解释机制，未按物理尺寸绘制，也不是 PEX。',19,c=GRAY)
 panel(100,'A｜恢复供电：CLED 充电冲击可进入输出 PMOS 的体结','恢复命令后约 1.267 ns：导电电流仅 0.0908 µA，封装支路电流却约 1.96 mA。')
 # A: high-side source to load; diode and capacitance in parallel.
 sx,sy,dy=mos(155,280,True,'XISO0..2','隔离控制')
 line(sx,sy,sx,205);text(sx,191,'VLED / led_feed',18,'middle');text(225,240,'高边 PMOS',18);text(225,264,'并联，B = led_feed',16)
 line(sx,dy,sx,355);line(sx,355,595,355);dot(420,355);dot(595,355);text(360,332,'LED_A ≈ 4.326 V',21)
 diode(420,355,480,True,'MicroLED');cap(595,355,480,'CLED 200 fF');line(420,480,650,480);dot(595,480);text(482,509,'LED_K',19)
 path('M325,375 L325,458',TEAL,2.2);text(50,410,'Icond 很小',19,c=TEAL);text(50,437,'此时不能用它代表总瞬态电流',16,c=TEAL)
 resistor(650,480,755,'RPKG 1 Ω');inductor(755,480,865,'LPKG 0.5 nH');line(865,480,1026,480);dot(945,480);text(887,510,'OUT ≈ 2.134 V',21)
 # Existing output PMOS and explicit intrinsic body-junction path.
 px,py,pdy=mos(990,310,True,'XPOUT','CTRL');line(px,pdy,px,480);line(px,py,px,210);line(px,210,1198,210);text(1110,190,'VH ≈ 1.623 V；B = VH',19,'middle')
 line(1026,480,1198,480);diode(1198,480,210);text(1225,300,'K',19);text(1225,405,'A',19);text(1145,352,'体结',18,'end');text(1145,377,'OUT → VH',18,'end');text(1145,402,'正偏 ≈ 0.511 V',18,'end',RED)
 path('M191,218 L191,262 L169,262 L169,298 L191,298 L191,355 L550,355',RED,3.3,True)
 path('M560,375 L560,461',RED,3.0,True,'6,5')
 path('M865,480 L1198,480 L1198,395',RED,3.3,True)
 path('M1198,320 L1198,220',RED,3.3,True)
 text(740,268,'Ipackage ≈ 1.96 mA',22,'middle',RED);text(740,298,'主路径：电容位移电流',18,'middle',RED)
 text(50,553,'候选改法：高边慢开 / 快关，降低实际 d(LED_A−LED_K)/dt；包络与寄生仍需原生验证。',19,c=TEAL)
 text(50,581,'只延迟开通未必降低冲击；Rg×Cg 不是通过保证。图中省略此时已撤销的跨 LED 钳位及其寄生。',17,c=GRAY)
 # B topology: GB -> CFF -> OUT -> LPKG -> RPKG -> LED_K. Clamp's source/body diode is separate.
 panel(630,'B｜稳定关断：高边已隔离，CFF 仍可把阴极拉到地以下','原生稳定 off：LED_K 最低 −0.307084 V；OUT 最低 −0.301491 V，发生时刻不同。')
 text(75,838,'GB 下降',22);path('M145,748 L175,748 L175,790 L210,790',INK,2.3);text(85,733,'内部数据仍翻转',17,c=GRAY)
 line(105,865,220,865);cap_h(220,865,410,'CFF 31.275 fF');line(410,865,505,865);dot(480,865);text(460,838,'OUT',21)
 inductor(505,865,625,'0.5 nH');resistor(625,865,745,'1 Ω');line(745,865,936,865);dot(850,865);text(780,897,'LED_K',21);text(758,923,'−0.307084 V',20,c=RED)
 # Load / isolation drawn above actual LED_K terminal.
 line(850,770,1146,770);text(848,752,'LED_A',20);cap(850,770,865,'');text(850,960,'CLED 200 fF',17);diode(960,770,865,True);line(850,865,1146,865);dot(960,865)
 ix,iy,idy=mos(1110,815,False,'XCLAMP','');line(ix,iy,ix,770);line(ix,idy,ix,865);text(1080,795,'DISABLE',16,'middle');text(1100,920,'3.3 V；B = VSS',17)
 # High-side isolation is explicit but the disconnected supply is outside the mechanism path.
 text(1025,735,'高边 PMOS 已关闭',18,c=GRAY)
 # Explicit clamp source-body diode: anode VSS, cathode LED_K.
 line(1146,865,1215,865);diode(1215,1045,865);ground(1215,1045);text(1240,902,'K',19);text(1240,1012,'A',19)
 text(1103,965,'XCLAMP',18,'middle');text(1103,991,'源 / 体结',18,'middle');text(1090,1030,'VSS → LED_K',18,'middle',RED)
 path('M1215,1035 L1215,995',RED,3.3,True);path('M1215,925 L1215,865 L758,865',RED,3.3,True)
 path('M495,865 L428,865',RED,3.3,True);path('M296,865 L232,865',RED,3.3,True)
 text(350,991,'GB 的负跳变经 CFF 抽走 OUT 节点电荷',20,'middle',RED)
 text(350,1020,'地 → 体结 → LED_K → 封装 → OUT → CFF',18,'middle',RED)
 text(50,1083,'候选改法：内部数据快禁用、延迟允许，抑制 off 时的 GB/CFF 翻转；释放要晚于高边接回。',19,c=TEAL)
 text(50,1111,'ready RC 仅是开环定时。必须测实际导通顺序、首个数据边沿、端压与能量；PVT 仍未闭合。',17,c=GRAY)
 text(30,1171,'红色箭头：常规电流 / 电荷注入方向的定性示意。体结 A 为阳极，K 为阴极；LED_K 与 OUT 由封装 R/L 分隔。',18)
 text(30,1200,'这些峰值是失败定位证据，不代表保护已通过；慢开与数据门控候选仍在验证。全部改法均需真实 MOS、供源计能和原生步长复查。',17,c=GRAY)
 S.append('</svg>');OUT.mkdir(parents=True,exist_ok=True);svg=OUT/'micro-protection-physics.svg';svg.write_text('\n'.join(S)+'\n')
 import cairosvg
 cairosvg.svg2png(url=str(svg),write_to=str(svg.with_suffix('.png')),scale=1.3);print(svg)
if __name__=='__main__':main()
