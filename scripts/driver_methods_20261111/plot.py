#!/usr/bin/env python3
"""Independent plots of fixed-current optical/RX sensitivity and source energy."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/driver-methods-20261111';OUT=ROOT/'docs/research/driver-methods-20261111/assets'
def setup():
    font='/System/Library/Fonts/Hiragino Sans GB.ttc';font_manager.fontManager.addfont(font)
    plt.rcParams.update({'font.family':[font_manager.FontProperties(fname=font).get_name(),'Arial'],'font.size':13,'axes.unicode_minus':False,'svg.fonttype':'none'})
    OUT.mkdir(parents=True,exist_ok=True)
def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=180,bbox_inches='tight');fig.savefig(OUT/(name+'.svg'),bbox_inches='tight');plt.close(fig)
def main():
    setup();d=json.loads((EV/'link-sensitivity.json').read_text())
    fig,axs=plt.subplots(1,2,figsize=(12.5,5),layout='constrained')
    taus=d['grid']['optical_tau_ps'];bws=d['grid']['receiver_GHz']
    for ax,route in zip(axs,['A','B']):
        rows={(r['optical_tau_ps'],r['receiver_GHz']):r['full_receiver'] for r in d['rows'] if r['route']==route}
        values=np.array([[rows[t,b]['one_sided_margin_bit_UI'] for b in bws] for t in taus])
        ax.imshow(values,vmin=0,vmax=.5,cmap='YlGnBu',aspect='auto')
        for y,t in enumerate(taus):
            for x,b in enumerate(bws):
                r=rows[t,b];ok=r['research_margin_pass'];val=values[y,x]
                ax.text(x,y,f'{val:.3f} UI\n'+('通过' if ok else f"未过 · {r['errors']}错"),ha='center',va='center',color='white' if val>.29 else '#173a48',fontsize=12)
        ax.set(title=f'上一版 {route} · 净 3.2 Gb/s',xticks=range(len(bws)),xticklabels=bws,yticks=range(len(taus)),yticklabels=[str(t) if t else '0（理想对照）' for t in taus],xlabel='假设 RX 带宽 / GHz',ylabel='假设光学时间常数 / ps')
    fig.suptitle('改变光源/RX假设后的条件性结果，未改变驱动硬件',fontsize=18)
    save(fig,'link-sensitivity')
if __name__=='__main__':main()
