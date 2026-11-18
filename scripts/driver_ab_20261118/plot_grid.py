"""Show the measured current-error envelope across the DC factorial, including RSET tolerance."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'evidence/driver-ab-20261118'
OUT=ROOT/'docs/research/driver-ab-20261118/assets'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('later',help='Name of the larger-unit final grid')
    args=p.parse_args()
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['PingFang SC','Noto Sans CJK SC','Arial'],'axes.unicode_minus':False})
    fig, axes = plt.subplots(1,2,figsize=(10.5,3.6),sharey=True,layout='constrained')
    for ax,target in zip(axes,(25,100)):
        ax.axhspan(-1,1,color='#eaf4f0')
        ax.axhline(1,color='#6a8885',ls='--',lw=1)
        ax.axhline(-1,color='#6a8885',ls='--',lw=1)
        ax.axhline(0,color='#bdc9c8',lw=.6)
        for i,(variant,color,label) in enumerate([('merged220c10','#a55e33','4/2 µm'),(args.later,'#176870','6/3 µm')]):
            rows=json.loads((EV/f'b-grid-{variant}.json').read_text())['runs']
            for ix,tol in enumerate((-10,0,10)):
                values=[r['error_percent'] for r in rows if r['RSET_offset_bp']==tol and r['target_uA']==target]
                assert len(values)==45
                x=ix+(i-.5)*.23
                ax.plot([x,x],[min(values),max(values)],c=color,lw=2.4,solid_capstyle='round',label=label if ix==0 else None)
                ax.scatter([x,x],[min(values),max(values)],color=color,s=23,zorder=3)
        ax.set(xticks=[0,1,2], xticklabels=['−0.1%','标称','+0.1%'],xlim=(-.45,2.45),ylim=(-1.3,1.3),
               title=f'{target} µA 档', xlabel='设定电阻 RSET 偏差')
        ax.spines[['top','right']].set_visible(False)
    axes[0].set_ylabel('LED 直流误差 (%)')
    axes[0].legend(title='镜像单位 W/L',loc='lower left',fontsize=8,frameon=False,ncol=2)
    fig.savefig(OUT/'b-grid-tolerance.png',dpi=170)
    plt.close(fig)

if __name__=='__main__':main()
