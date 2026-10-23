#!/usr/bin/env python3
"""Same-rate before/after evidence plots; failed points stay visible."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from tables import find,KINDS,LABEL,ENERGY
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/highspeed-nrz-pvt-20261023/figures'
font=ROOT/'build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf'
font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams['svg.fonttype']='none'

def main():
    s=json.loads((ROOT/'evidence/highspeed-nrz-pvt/summary.json').read_text());rows=s['rows']
    fig,axs=plt.subplots(3,3,figsize=(13,11),sharex=True)
    names=['A 旧','A 新','B 旧','B 新'];co=['#b1c2ce','#3d729e','#aaccc3','#188578']
    fields=[(ENERGY,1/1000,'全部激励源正向取能 (pJ / gross bit)',None),('threshold_margin_normalized',1,'接收垂直余量 / 75 µA',.1),('max_abs_terminal_V',-1000,'3.63 V − 最大端差 (mV)',0)]
    for j,kind in enumerate(KINDS):
        rr=[find(rows,r,v,kind,.5) for r in 'AB' for v in ['BEFORE','AFTER']]
        assert all(rr), 'Comparison plot requires all same-rate rows'
        for i,(key,factor,ylabel,threshold) in enumerate(fields):
            ax=axs[i,j];values=[x[key]*factor+(3630 if key=='max_abs_terminal_V' else 0) for x in rr]
            ax.bar(range(4),values,color=co,width=.65)
            for x,y,r in zip(range(4),values,rr):
                ax.annotate(f'{y:.3f}' if i<2 else f'{y:+.1f}',(x,y),xytext=(0,5 if y>=0 else -15),textcoords='offset points',ha='center',fontsize=9)
            if threshold is not None:ax.axhline(threshold,color='#a34c33',ls='--',lw=1)
            ax.set_xticks(range(4),names);ax.spines[['top','right']].set_visible(False);ax.margins(y=.25)
            if j==0:ax.set_ylabel(ylabel)
            if i==0:ax.set_title(LABEL[kind],fontsize=13)
            ax.set_ylim([(0,1.8),(-.08,.65),(-210,700)][i])
    fig.suptitle('相同 0.5 Gb/s：取能、接收余量与电压余量分别比较',fontsize=17,x=.06,ha='left')
    fig.text(.06,.025,'旧 = 原版 RC；新 = 修改后 RC。负电压余量表示超过项目筛查线；接收垂直余量要求 ≥ 0.1。\n零比特错误仍需满足水平余量与电压检查；图中能量是仿真激励源取能，不含尚未实现的稳压器效率。',fontsize=10,color='#547078')
    fig.tight_layout(rect=(0,.07,1,.95))
    for ext in ['svg','png']:fig.savefig(OUT/f'same-rate-comparison.{ext}',dpi=160,bbox_inches='tight')
    plt.close(fig)

if __name__=='__main__':main()
