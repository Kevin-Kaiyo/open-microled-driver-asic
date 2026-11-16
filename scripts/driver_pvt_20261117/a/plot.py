#!/usr/bin/env python3
"""Figures from stored case data only; does not modify any simulation case."""
import json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Rectangle,Circle
import run as a
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['PingFang SC','Hiragino Sans GB','Arial Unicode MS','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10,'svg.fonttype':'none'})
OUT=a.ROOT/'docs/research/driver-pvt-20261117/assets';OUT.mkdir(parents=True,exist_ok=True)
NAVY='#17384a';TEAL='#087c80';RED='#ad4e42';GOLD='#ba8c37'
def save(fig,name,sources):
 fig.savefig(OUT/(name+'.png'),dpi=160,bbox_inches='tight',facecolor='white');fig.savefig(OUT/(name+'.svg'),bbox_inches='tight',facecolor='white');plt.close(fig)
 a.emit(a.EV/(name+'-sources.json'),dict(figure=str((OUT/(name+'.png')).relative_to(a.ROOT)),sources=[dict(path=str(p.relative_to(a.ROOT)),sha256=a.sha(p)) for p in sources],script_sha256=a.sha(Path(__file__))))
def dcplot():
 fams=['baseline','track-fixed','trackwide4-fixed','trackwide4gm5-fixed'];names=['原固定阴极电压','供电差分感测','感测 + 输出W×4','感测 + 输出W×4 + 输入对W×5']
 fig,axes=plt.subplots(1,2,figsize=(12,4.6));sources=[]
 for j,ax in enumerate(axes):
  selected=fams if j==0 else fams[1:]
  for family in selected:
   vals=[]
   for g in a.GRID:
    rows=[]
    for l in [0,1]:
     p=a.BUILD/family/(g[0]+f'-DC-L{l}')/'result.json';sources.append(p);rows.append(a.read(p)['DC_error_percent'])
    vals.append(rows)
   v=np.array(vals);k=fams.index(family);ax.plot(np.arange(9)-.08,v[:,0],'-o',color=[RED,NAVY,GOLD,TEAL][k],lw=1.3,markersize=4,label=names[k]+' · 25 µA');ax.plot(np.arange(9)+.08,v[:,1],'--s',color=[RED,NAVY,GOLD,TEAL][k],lw=1.1,markersize=3,label=names[k]+' · 100 µA')
  ax.axhspan(-1,1,color=TEAL,alpha=.12);ax.axhline(0,color='#aab7c0',lw=.6);ax.set_xticks(range(9),[g[0] for g in a.GRID],rotation=45,ha='right');ax.set_ylabel('DC 电流误差 / %');ax.grid(axis='y',alpha=.2);ax.set_title(['供电波动暴露原电压驱动的精度限制','固定 TT 校准后，跨角仍有残差'][j],loc='left',color=NAVY)
  if j:ax.set_ylim(-4.5,4)
 axes[0].legend(fontsize=7,loc='upper left',frameon=False);axes[1].legend(fontsize=7,loc='upper left',frameon=False)
 fig.suptitle('A 路线：相同 25 / 100 µA 目标，九点工艺／温度／供电检查',x=.05,ha='left',color=NAVY,fontsize=14)
 fig.text(.05,-.06,'LED I–V、200 fF、200 ps、RX 1 GHz 固定；仅 MOS/PDK 电阻随温度。阴影为 ±1% 目标；电阻容差与 TC 尚未施加。',fontsize=9,color=NAVY)
 fig.tight_layout();save(fig,'a-dc-grid',list(dict.fromkeys(sources)))
def schematic():
 family='trackwide4gm5-fixed';cal=a.read(a.EV/'trackwide4gm5-calibration.json');fig,ax=plt.subplots(figsize=(13,7.5));ax.set_xlim(0,16);ax.set_ylim(0,10);ax.axis('off')
 def wire(points,c=NAVY,lw=1.4):ax.plot(*zip(*points),color=c,lw=lw)
 def text(x,y,s,**kw):ax.text(x,y,s,color=NAVY,va='center',**kw)
 def dot(x,y):ax.add_patch(Circle((x,y),.045,color=NAVY))
 def ground(x,y):
  for k,w in enumerate([.36,.24,.12]):wire([(x-w/2,y-.09*k),(x+w/2,y-.09*k)])
 def resistor(x1,y1,x2,y2,label):
  p=np.array([x1,y1]);q=np.array([x2,y2]);d=q-p;u=d/np.linalg.norm(d);n=np.array([-u[1],u[0]]);pts=[p,p+d*.24]
  for i in range(9):pts.append(p+d*(.28+i*.055)+n*(.09 if i%2 else -.09))
  pts.extend([p+d*.76,q]);wire(pts);mid=(p+q)/2
  text(mid[0]+.24,mid[1],label,fontsize=8,ha='left') if abs(d[1])>abs(d[0]) else text(mid[0],mid[1]+.3,label,fontsize=8,ha='center')
 text(.25,9.6,'差分感测让阴极电压随供电移动；输出电流仍通过 LED 的 I–V 确定',fontsize=16)
 text(.25,9.05,'只展开高轨反馈与分流支路；低轨连接相同。三角形表示实际 5-MOS OTA，偏置支路从略。',fontsize=10)
 # HSET divider and reference summing network.
 text(.7,8.25,'LEDREF = led_feed',fontsize=10);wire([(1.4,8),(1.4,7.6)]);resistor(1.4,7.6,1.4,5.45,'3 MΩ');dot(1.4,5.45);resistor(1.4,5.45,1.4,4.1,'1 MΩ');ground(1.4,4.1);wire([(1.4,5.45),(2.9,5.45),(2.9,3.4),(7,3.4),(7,5.45),(7.4,5.45)]);text(1.9,5.85,'HSET = 0.25 × LEDREF',fontsize=9)
 text(3.7,8.25,'VREF = 2.5 V');wire([(4.6,8),(4.6,7.6)]);resistor(4.6,7.6,4.6,6.3,f'RH_REF\n{cal["RH_ohm"]/1e6:.4f} MΩ');dot(4.6,6.3);wire([(4.6,6.3),(7.4,6.3)]);resistor(4.6,6.3,4.6,3.9,f'RH_GND\n{cal["RH_GND_ohm"]/1e6:.4f} MΩ');ground(4.6,3.9);text(5.2,6.65,'HSENSE',fontsize=10)
 ax.add_patch(Polygon([[7.4,6.8],[7.4,4.95],[9.2,5.87]],closed=True,fill=False,edgecolor=NAVY,lw=1.5));text(7.58,6.28,'+',fontsize=13);text(7.58,5.5,'−',fontsize=15);text(8.05,5.89,'OTA',fontsize=11)
 wire([(9.2,5.87),(10.3,5.87)]);text(9.45,6.15,'HG',fontsize=10)
 # NMOS shunt: vertical channel; gate separate, body/source tied to ground.
 wire([(10.3,5.4),(10.3,6.35)]);wire([(10.47,5.4),(10.47,6.35)]);wire([(10.47,6.18),(11,6.18),(11,7.05)]);wire([(10.47,5.57),(11,5.57),(11,4.7)]);ground(11,4.7);text(11.4,5.7,'XHSHUNT\n6 V NMOS\nW/L = 20/0.7 µm',fontsize=9)
 wire([(11,7.05),(11,7.3)]);dot(11,7.05);resistor(11,8.55,11,7.3,'100 kΩ');text(10.65,8.8,'VIN',fontsize=10);wire([(11,7.05),(14.5,7.05)]);text(11.65,7.5,'VH → 输出 PMOS 源/体',fontsize=9)
 resistor(14.5,7.05,14.5,6.1,'0.2 Ω');wire([(14.5,6.1),(14.5,5.7)]);wire([(14.15,5.7),(14.85,5.7)]);wire([(14.15,5.56),(14.85,5.56)]);wire([(14.5,5.56),(14.5,4.9)]);ground(14.5,4.9);text(14.95,5.65,'10 nF\n外部',fontsize=8)
 # Feedback routes above OTA, no accidental cross-junctions.
 wire([(11,7.05),(10,7.05),(10,8.4),(6.6,8.4),(6.6,7.35)]);resistor(6.6,7.35,6.6,6.3,'4 MΩ');dot(6.6,6.3)
 text(.5,3.1,'HSENSE = 0.25·VH + bH·VREF；OTA 令 HSENSE ≈ HSET',fontsize=12)
 text(.5,2.65,'因此  LEDREF − VH ≈ 4·bH·VREF。低轨将 VH/H 换为 VL/L，连接相同。',fontsize=11)
 text(.5,2.13,f'低轨固定值：RL_REF = {cal["RL_ohm"]/1e6:.4f} MΩ；RL_GND = {cal["RL_GND_ohm"]/1e6:.4f} MΩ。',fontsize=10)
 text(.5,1.62,'本候选：输出 XNOUT/XPOUT 的 W ×4；两个 OTA 的输入对 W ×5；全部 31 MOS 数量不变。',fontsize=10)
 text(.5,1.13,'LEDREF 取隔离开关之前的 led_feed：关断时不会把阴极伺服拉向被隔离的 LED 阳极。',fontsize=10)
 text(.5,.62,'局限：这是压差稳定，不是实际 LED 电流闭环；MOS R_on、隔离开关压降、OTA 误差与电阻失配仍会改变电流。',fontsize=9)
 text(.5,.15,'源：build/driver-pvt-20261117/a/trackwide4gm5-fixed/inputs/route_a.spice；fault 测试的独立隔离/钳位网络保持原连接。',fontsize=8)
 save(fig,'a-feedback-schematic',[a.BUILD/family/'inputs/route_a.spice',a.EV/'trackwide4gm5-calibration.json'])
def waves():
 cases=[('baseline','SShotlow'),('trackwide4gm5-fixed','SShotlow'),('trackwide4gm5-fixed','TT'),('trackwide4gm5-fixed','FFcoldhigh')];fig,ax=plt.subplots(2,2,figsize=(12,7));sources=[]
 for axes,(variant,point) in zip(ax.flat,cases):
  work=a.BUILD/variant/(point+'-fault-s40');p=work/'preview.npz'
  if not p.exists():axes.text(.5,.5,'仿真进行中',ha='center',transform=axes.transAxes);continue
  z=np.load(p);r=a.read(work/'result.json');sources.extend([p,work/'result.json']);t=z['time_s']*1e6
  axes.plot(t,z['iled_cond']*1e6,color=TEAL,lw=.5,label='LED 导通电流');axes.plot(t,z['received_uAeq'],color=NAVY,lw=.5,alpha=.7,label='光学 + RX 后 µAeq');axes.axvspan(.64,1.28,color=RED,alpha=.1,label='DISABLE 高');axes.set_title(f'{point} · '+('原电路' if variant=='baseline' else '差分感测 + W×4 + gm提升'),loc='left',fontsize=10);axes.set_xlabel('时间 / µs');axes.set_ylabel('电流 / µA（或接收代理 µAeq）');axes.grid(alpha=.15);axes.legend(fontsize=7,frameon=False)
 fig.suptitle('含真实数据切换的独立关断和恢复检查 · 净 1.6 Gb/s',x=.06,ha='left',color=NAVY,fontsize=14);fig.tight_layout();save(fig,'a-fault-waveforms',sources)
if __name__=='__main__':
 dcplot();schematic();waves()
