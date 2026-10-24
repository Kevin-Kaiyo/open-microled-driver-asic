#!/usr/bin/env python3
"""Exact tested RC placement topology drawn as a small circuit diagram."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2]
FONT=ROOT/'build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf'
font_manager.fontManager.addfont(str(FONT))
FONT_NAME=font_manager.FontProperties(fname=str(FONT)).get_name()
plt.rcParams.update({'font.family':FONT_NAME,'svg.fonttype':'path'})
P=Path(__file__).resolve().parents[2]/'docs/research/driver-robustness-20261024/pwm-figures'
P.mkdir(parents=True,exist_ok=True)
fig,axes=plt.subplots(2,1,figsize=(10,6.2));fig.patch.set_facecolor('#fafbf9')
for ax,board in zip(axes,[False,True]):
    ax.set_xlim(0,11);ax.set_ylim(-.3,3.7);ax.axis('off');ax.set_facecolor('#fafbf9')
    color='#168377' if board else '#3d6b9d'
    ax.text(.3,3.35,'PCB侧滤波（相同100 Ω / 100 nF）' if board else '芯片端口电容假设（不是PCB侧放置）',fontsize=12,color=color,weight='normal')
    ax.plot([.8,9.4],[2.6,2.6],c='#233343',lw=1.5)
    ax.plot([.8,6.9],[.2,.2],c='#233343',lw=1.5)
    ax.plot([6.9,6.9,9.4],[.2,.8,.8],c='#233343',lw=1.5)
    ax.plot([.8,.8],[.2,1.1],c='#233343',lw=1.5);ax.plot([.8,.8],[2.1,2.6],c='#233343',lw=1.5)
    ax.add_patch(Circle((.8,1.6),.5,ec='#233343',fc='#fafbf9',lw=1.5));ax.text(.8,1.6,'参考供电\nVREF',ha='center',va='center',fontsize=9)
    def box(x,y,w,label):
        ax.add_patch(Rectangle((x,y-.26),w,.52,ec='#233343',fc='#fafbf9',zorder=3));ax.text(x+w/2,y,label,ha='center',va='center',fontsize=9,zorder=4)
    box(7.25,.8,1.6,'封装回流R/L')
    box(1.8,2.6,1.6,'滤波电阻\n100 Ω' if board else '封装VREF R/L')
    box(5.3 if board else 4.3,2.6,1.6,'封装VREF R/L' if board else '滤波电阻\n100 Ω')
    cx=4.1 if board else 7.5;bottom=.2 if board else 1.15
    ax.plot([cx,cx],[2.6,1.8],c=color,lw=1.7);ax.plot([cx-.35,cx+.35],[1.8,1.8],c=color,lw=1.7);ax.plot([cx-.35,cx+.35],[1.6,1.6],c=color,lw=1.7);ax.plot([cx,cx],[1.6,bottom],c=color,lw=1.7)
    if not board:ax.plot([cx,9.05,9.05,9.4],[1.15,1.15,.8,.8],c=color,lw=1.7)
    ax.text(cx+.45,1.7,'滤波电容\n100 nF',va='center',fontsize=9,color=color)
    ax.add_patch(Rectangle((9.4,.5),1.25,2.4,ec='#233343',fc='#e9f0ef',lw=1.4))
    ax.text(10.025,1.7,'r5模拟宏\n39 MOS',ha='center',va='center',fontsize=10);ax.text(9.53,2.62,'VREF',fontsize=8);ax.text(9.53,.65,'VSS',fontsize=8)
    ax.text(1,.0,'板级地（GND）',fontsize=9,color='#596c78');ax.text(8.9,.15,'芯片地（VSS）',fontsize=9,color='#596c78')
    ax.scatter([cx],[bottom],color=color,s=15,zorder=5)
fig.tight_layout();fig.savefig(P/'pwm-filter-topology.svg');fig.savefig(P/'pwm-filter-topology.png',dpi=180)
