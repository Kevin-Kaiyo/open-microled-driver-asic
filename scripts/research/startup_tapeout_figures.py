"""Original explanatory figures; geometry is a baseline read, not new layout."""
from pathlib import Path
import sys, json
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/research'))
import reference_architecture_figures as ref
BASE=ROOT/'docs/research/startup-tapeout-20261014'
ref.FIG=BASE/'figures'
D=ref.Drawing;I=ref.INK;T=ref.TEAL

def main():
 ref.FIG.mkdir(parents=True,exist_ok=True)
 d=D(960,425,'同一块硅芯片：器件在下，互连在上','conceptual process stack; not to scale; GF180MCU D five-metal baseline')
 for n in range(5,0,-1):
  y=78+(5-n)*42
  d.parts.append(f'<rect x="65" y="{y}" width="490" height="21" fill="{T if n==5 else "#7899a3"}"/>')
  d.text(585,y+19,f'M{n} 金属互连',18)
  if n>1:
   d.parts.append(f'<rect x="155" y="{y+21}" width="15" height="21" fill="#849da2"/><rect x="445" y="{y+21}" width="15" height="21" fill="#849da2"/>')
 d.text(70,312,'多晶硅栅极／栅介质／源漏扩散／井区',19)
 d.parts.append('<rect x="65" y="328" width="490" height="40" fill="#e7eeee" stroke="#7d959c"/>')
 d.text(310,355,'硅衬底 Silicon',19,anchor='middle')
 d.text(585,294,'金属之间：绝缘介质＋Via',18)
 d.text(585,327,'五层金属 ≠ 五张光罩',18)
 d.text(585,360,'外接LED：独立光学器件',18)
 d.text(65,405,'功能层次示意，不表示真实厚度、掩模数量或制造截面。',17)
 d.save('process-stack.svg')
 d=D(960,430,'旧GDS外框面积：不要把栅区面积当成芯片面积','reconstruction from archived GDS macro translations; not new placement')
 # Scaled occupied span; analog and digital exact bounding rectangles.
 x0=70;y0=100;s=1.65
 d.parts.append(f'<rect x="{x0}" y="{y0}" width="{305*s}" height="{180*s}" fill="#f5f8f8" stroke="#96adb3" stroke-dasharray="5 5"/>')
 # y reversed from physical top. Digital placed150,25, analog25,105.22.
 d.parts.append(f'<rect x="{x0+125*s}" y="{y0}" width="{180*s}" height="{180*s}" fill="#edf3f4" stroke="{T}" stroke-width="2"/>')
 ay=y0+(205-142.88)*s
 d.parts.append(f'<rect x="{x0}" y="{ay}" width="{95*s}" height="{37.66*s}" fill="#dcebec" stroke="{T}" stroke-width="2"/>')
 d.text(x0+47.5*s,ay+24,'模拟像素',17,anchor='middle')
 d.text(x0+47.5*s,ay+49,'95×37.66 µm',16,anchor='middle')
 d.text(x0+215*s,y0+115,'数字PWM宏',22,anchor='middle')
 d.text(x0+215*s,y0+150,'180×180 µm',19,anchor='middle')
 d.text(650,125,'共同跨度：305×180 µm',19)
 d.text(650,165,'0.0549 mm²',24,T,bold=True)
 d.text(650,215,'新参考／隔离／保护：待布局',18)
 d.text(650,250,'pad / ESD / seal ring：待设计',18)
 d.text(650,285,'封装与板卡：面积另计',18)
 d.text(70,78,'复核既有GDS边界，2026-10-14；没有重新布置宏',17)
 d.save('baseline-area.svg')
 d=D(960,420,'从可运行电路，到能测量的芯片：每一步有不同验收','conceptual manufacturing responsibilities; no foundry acceptance established')
 labels=[['规格与测试','电流／PWM／故障'],['电路与RTL','DC／PVT／启动'],['版图与抽取','DRC／LVS／PEX'],['顶层签核','pads／PG／封装']]
 for n,lines in enumerate(labels):
  x=30+n*238;d.box(x,82,210,75,lines)
  if n<3:d.arrow(x+212,119,x+234,119)
 labels=[['制造交付','GDS＋报告＋manifest'],['晶圆制造','光罩／工艺／晶圆测试'],['封装与测试','bonding／ATE／板卡'],['系统验证','电流／光学／可靠性']]
 for n,lines in enumerate(labels):
  x=30+n*238;d.box(x,222,210,75,lines)
  if n<3:d.arrow(x+212,259,x+234,259)
 d.wire([(850,157),(850,189),(133,189),(133,222)],T);d.arrow(133,204,133,222)
 d.text(30,351,'设计方：证明功能、性能与可测性；制造方：按接受的数据和工艺执行。',19)
 d.text(30,390,'Manufacturable（可制造）与 Functional（能工作）需分别验收。',19)
 d.save('fabrication-flow.svg')
 print(json.dumps({'figures':3,'new_layout_generated':False}))

def isolation_figure():
 d=D(960,490,'CMOS传输门隔离：保留启动抑制，也保留电压余量','actual five-MOS GF180 schematic; pre-layout junction geometry assumed')
 p=d.mos(180,135,'XFP','P',['fault_b','fault','vdd','vdd'],'4 / 1 µm','VDD')
 n=d.mos(180,265,'XFN','N',['fault_b','fault','vss','vss'],'2 / 1 µm','VSS')
 d.wire([p['S'],(180,70)]);d.text(180,61,'VDD',18,anchor='middle')
 d.wire([p['D'],n['D']]);d.dot(180,200)
 d.wire([p['G'],(80,135),(80,265),n['G']]);d.dot(80,200);d.wire([(30,200),(80,200)]);d.text(28,189,'FAULT',18)
 d.ground(180,340);d.wire([n['S'],(180,330)])
 x=d.mos(505,140,'XISO','N',['refout','fault_b','bias','vss'],'20 / 1 µm','VSS')
 q=d.mos(735,140,'XPISO','P',['bias','fault','refout','vdd'],'20 / 1 µm','VDD')
 d.wire([x['D'],(505,75),(735,75),q['S']]);d.text(620,65,'REFOUT',19,anchor='middle')
 d.wire([(180,200),(370,200),(370,140),x['G']]);d.text(380,130,'FAULT_B',17)
 d.wire([q['G'],(635,140)]);d.text(636,130,'FAULT',17)
 d.wire([x['S'],(505,235),(735,235),q['D']]);d.dot(735,235);d.text(600,223,'BIAS → MREF',18,anchor='middle')
 z=d.mos(735,300,'XDIS','N',['bias','fault','vss','vss'],'2 / 1 µm','VSS')
 d.wire([(735,235),z['D']]);d.wire([z['G'],(625,300)]);d.text(623,305,'FAULT',17,anchor='end')
 d.wire([z['S'],(735,375)]);d.ground(735,385)
 d.text(28,423,'FAULT=1：N/P传输门关，XDIS开，BIAS固定至VSS；参考环路继续运行。',18)
 d.text(28,460,'FAULT=0：N/P传输门开；LED放行仍由PERMIT与PWM保护决定。',18)
 d.save('reference-isolator.svg')

def coupling_figure():
 d=D(960,425,'PWM关断时仍存在电容耦合：真实PEX的三条路径','selected real PEX capacitors; simplified circuit excludes other intrinsic and layout elements')
 def cap(x,y,label):
  d.wire([(x-30,y),(x-7,y)]);d.wire([(x-7,y-16),(x-7,y+16)])
  d.wire([(x+7,y-16),(x+7,y+16)]);d.wire([(x+7,y),(x+30,y)])
  d.text(x,y-24,label,17,anchor='middle')
 d.dot(100,170);d.text(95,200,'BIAS',19,anchor='middle')
 d.wire([(100,170),(100,90),(740,90),(740,170),(770,170)])
 # White interruption under capacitor symbol.
 d.parts.append('<rect x="515" y="73" width="60" height="36" fill="white"/>');cap(545,90,'C10 = 0.20686 fF')
 d.wire([(100,170),(420,170)])
 d.parts.append('<rect x="230" y="153" width="60" height="36" fill="white"/>');cap(260,170,'C9 = 2.0854 fF')
 d.dot(420,170);d.wire([(420,170),(420,270),(715,270)]);d.text(420,298,'GATE',19,anchor='middle')
 d.wire([(420,170),(770,170)])
 d.parts.append('<rect x="540" y="153" width="60" height="36" fill="white"/>');cap(570,170,'C19 = 1.22948 fF')
 d.dot(770,170);d.text(815,195,'LED_K',18)
 d.led(770,120);d.wire([(770,155),(770,170)]);d.wire([(770,85),(770,62)]);d.text(822,68,'VLED',18)
 m=d.mos(770,270,'MOUT','N',dimensions='PWM已关闭',body='VSS')
 d.wire([(770,170),m['D']]);d.wire([m['S'],(770,325)]);d.ground(770,335)
 d.text(30,381,'LED模型结电容约2 pF：端电压变化产生位移电流。',18)
 d.text(30,413,'仅展开因果相关连接；其他关断开关、钳位和寄生元件省略。',17)
 d.save('coupling-path.svg')

if __name__=='__main__':
 main()
 isolation_figure()
 coupling_figure()
