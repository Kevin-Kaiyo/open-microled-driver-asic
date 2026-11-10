#!/usr/bin/env python3
"""Compare matched-rate native results; no time scaling or failed-point ranking."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/ab-improvement-20261111';OUT=ROOT/'docs/research/driver-improvement-20261111/assets'
def read(p):return json.loads(p.read_text())
def setup():
    font='/System/Library/Fonts/Hiragino Sans GB.ttc';font_manager.fontManager.addfont(font)
    plt.rcParams.update({'font.family':[font_manager.FontProperties(fname=font).get_name(),'Arial'],'font.size':14,'axes.unicode_minus':False,'svg.fonttype':'none'})
    OUT.mkdir(parents=True,exist_ok=True)
def tidy(ax):
    ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15)
def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=180,bbox_inches='tight');fig.savefig(OUT/(name+'.svg'),bbox_inches='tight');plt.close(fig)

def main():
    setup();s=read(EV/'summary.json');sel=read(EV/'selection.json')
    old=read(ROOT/'evidence/blue-emitter-speed-review-20261110/speed-sweep-all.json')['rows']
    ideal=[r for r in read(EV/'ideal-bounds.json')['rows'] if r['current_edge_ps']==20]
    fig,axs=plt.subplots(2,2,figsize=(12,7),layout='constrained')
    for j,route in enumerate(['A','B']):
        base={r['net_Gbps']:r['full_receiver'] for r in old if r['family']=='MicroLED' and r['route']==route and abs(r['capacitance_fF']-200)<1e-6 and r['steps_per_symbol']==40}
        for r in s['transient']:
            if r['candidate'] in ['a-base','B_baseline'] and r['route']==route and r['case']['steps_per_symbol']==40:base[r['case']['net_rate_Gbps']]=r['full_receiver']
        new={r['case']['net_rate_Gbps']:r['full_receiver'] for r in s['transient'] if r['candidate']==sel[route]['candidate'] and r['case']['steps_per_symbol']==40}
        idealmap={r['net_Gbps']:r['full_receiver'] for r in ideal}
        for i,key in enumerate(['worst_signed_margin_uAeq','one_sided_margin_bit_UI']):
            ax=axs[i,j]
            for label,m,color,style in [('原版（含补测）',base,'#85959a','o--'),('改版',new,'#236e76','s-'),('理想两电平电流',idealmap,'#b98450',':')]:
                x=sorted(m);ax.plot(x,[m[v][key] for v in x],style,color=color,lw=2,ms=6,label=label)
            threshold=7.5 if i==0 else .37
            ax.axhline(threshold,color='#a75f5c',ls='--',lw=1)
            ax.set(xlim=(.3,3.3),xticks=[.4,.8,1.2,1.6,2,2.4,3.2],ylabel='最差幅度 / µAeq' if i==0 else '单侧时间 / bit UI')
            if i==0:ax.set_title(f'MicroLED {route}');ax.set_ylim(-42,42)
            else:ax.set_xlabel('净吞吐 / Gb/s');ax.set_ylim(-.01,.55)
            tidy(ax)
    axs[0,0].legend(frameon=False,fontsize=10,loc='lower left')
    save(fig,'rate-envelope')
    # Report energy only at each explicitly matched operating point.
    at=lambda c,r:next(x for x in s['transient'] if x['candidate']==c and x['case']['steps_per_symbol']==40 and x['case']['net_rate_Gbps']==r)
    a0=at('a-base',1.2);a=at(sel['A']['candidate'],1.2);b=at(sel['B']['candidate'],1.2)
    assert all(x['joint_screen_pass'] for x in [a0,a,b]),'Do not rank failed links by energy'
    vc=read(EV/'vcsel-causal-comparison.json')['rows'];v0=vc[0];v=next(x for x in vc if x['candidate']==sel['VCSEL']['candidate'])
    fig,axs=plt.subplots(1,3,figsize=(12,4.6),layout='constrained')
    values=[x['energy_pJ_per_attempted_payload_bit']['positive'] for x in [a0,a,b]]
    axs[0].bar(['A 原版','A 改版','B 改版'],values,color=['#94a4a7','#236e76','#b98450'])
    axs[0].set(title='MicroLED：净 1.2 Gb/s',ylabel='E+ / pJ 每尝试载荷位',ylim=(0,max(values)*1.3))
    for k,value in enumerate(values):axs[0].text(k,value+.025,f'{value:.3f}',ha='center',fontsize=12)
    values=[v0['positive_pJ_per_attempted_bit'],v['positive_pJ_per_attempted_bit']]
    axs[1].bar(['原版未过','改版通过'],values,color=['#94a4a7','#236e76'])
    axs[1].set(title='VCSEL：净 6.4 Gb/s',ylabel='E+ / pJ 每尝试载荷位',ylim=(0,7.5))
    for k,value in enumerate(values):axs[1].text(k,value+.08,f'{value:.3f}',ha='center',fontsize=12)
    for i,row in enumerate([a,b]):
        low,high=row['current_range_uA'];mean=row['mean_LED_current_uA']
        axs[2].vlines(i,low,high,color=['#236e76','#b98450'][i],lw=3)
        axs[2].plot([i,i],[low,high],'_',color=['#236e76','#b98450'][i],ms=16)
        axs[2].plot(i,mean,'D',color='#243d48',ms=7)
    for target in [25,100]:axs[2].axhline(target,color='#aaa',ls=':',lw=1)
    axs[2].set(title='MicroLED：净 1.2 Gb/s',ylabel='瞬态范围 / 平均电流 · µA',xticks=[0,1],xticklabels=['A 改版','B 改版'],xlim=(-.6,1.6))
    for ax in axs:tidy(ax);ax.tick_params(axis='x',labelsize=12)
    save(fig,'energy-and-current')

if __name__=='__main__':main()
