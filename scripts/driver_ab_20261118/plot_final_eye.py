"""Overlay three circuit revisions at the same two difficult payload positions."""
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/driver-ab-20261118'
sys.path.insert(0,str(Path(__file__).parent/'b_review'))
from plot_w6_edges import right
from ss_timing import inspect

def main():
    final=ROOT/'build/driver-ab-20261118/b_final/unit6-r260-n4ff36/ss_hot_low-full-s40'
    previous=[json.loads((EV/'b_review'/f'ss-w6-{name}-rx.json').read_text())['sample_3511'] for name in ['base','ff36']]
    earlier_right=json.loads((EV/'b_review/ss-w6-rising-crossing.json').read_text())
    last=inspect(final)
    new_right=right(final)
    (EV/'b_final/final-crossings.json').write_text(json.dumps(dict(left=last,right=new_right),indent=2)+'\n')
    left=previous+[last['sample_3511']]
    right_set=earlier_right+[new_right]
    plt.rcParams.update({'font.family':['PingFang SC','DejaVu Sans'],'axes.unicode_minus':False})
    fig,axes=plt.subplots(1,2,figsize=(10.4,3.5),sharey=True,layout='constrained')
    for ax,side,xlim in zip(axes,['采样前 · 码位 3511','采样后 · 码位 2129'],[(-.42,-.32),(.32,.42)]):
        ax.axhspan(62.5,62.5,color='#566')
        ax.axhline(62.5,color='#555',ls=':',lw=1)
        ax.axvspan(-.37,.37,color='#dcece8')
        ax.axvline(-.37 if xlim[0]<0 else .37,color='#5f757b',ls='--',lw=1)
        ax.set(xlim=xlim,ylim=(59.5,65.5),title=side,xlabel='相对冻结的采样中心 (UI)')
        ax.spines[['top','right']].set_visible(False)
    for i,(name,color) in enumerate([('原 6/3','#a65c34'),('前馈 36 fF','#6587a2'),('前馈 36 fF + 栅极放电管加宽','#096d70')]):
        for ax,trace,y,cross in [(axes[0],left[i],'received_uAeq',left[i]['prev_crossing_relative_UI']),
                                (axes[1],right_set[i],'RX_uAeq',right_set[i]['next_crossing_UI'])]:
            ax.plot(trace['relative_UI'],trace[y],color=color,label=name,lw=1.6)
            ax.plot(cross,62.5,'o',ms=5,mfc='white',mec=color)
    axes[0].legend(loc='lower left',fontsize=8,frameon=False)
    axes[0].set_ylabel('接收等效电流 (µAeq)')
    fig.savefig(ROOT/'docs/research/driver-ab-20261118/assets/b-final-eye.png',dpi=170)

if __name__=='__main__':main()
