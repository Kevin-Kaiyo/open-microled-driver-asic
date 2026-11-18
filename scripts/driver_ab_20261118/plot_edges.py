"""Plot the unthinned key local windows from the frozen B experiments."""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
NEW=ROOT/'build/driver-ab-20261118'
EARLY=ROOT/'build/driver-pvt-20261117/b/clamp5v_buffer_soft'
OUT=ROOT/'docs/research/driver-ab-20261118/assets'
EV=ROOT/'evidence/driver-ab-20261118'
SOURCES={}


def waveform(ax,folder,signal,limits,label,color,scale=1):
    p=folder/'preview.npz'
    SOURCES[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    with np.load(p) as trace:
        tm=trace['time_s']*1e9-32.
        selected=(tm>=limits[0]) & (tm<=limits[1])
        ax.plot(tm[selected],trace[signal][selected]*scale,label=label,color=color,lw=1.35)


def main():
    fig,axes=plt.subplots(1,3,figsize=(12,3.75),layout='constrained')
    plt.rcParams['axes.unicode_minus']=False
    old,mid,end=EARLY,NEW/'b/merged220c10',NEW/'b_final/unit6-r260'
    for ax,title,field,window,unit,gr,curves in [
        (axes[0],'快冷 · 释放','out',(-1,45),'OUT (V)','ff_cold_high-release-s40',[(old,'原保护版'),(end,'6/3 合并版')]),
        (axes[1],'快冷 · 关断','out',(-1,22),'OUT (V)','ff_cold_high-assert-s40',[(mid,'4/2、钳位 200 kΩ'),(end,'6/3、钳位 260 kΩ')]),
        (axes[2],'慢热 · 关断','iled_cond',(-1,32),'LED 导电电流 (µA)','ss_hot_low-assert-s40',[(old,'原保护版'),(end,'6/3 合并版')])]:
        for (folder,label),color in zip(curves,['#ad613e','#096c75']):
            waveform(ax,folder/gr,field,window,label,color,1 if field=='out' else 1e6)
        ax.set(title=title,ylabel=unit,xlabel='相对保护命令的时间 (ns)',xlim=window)
        if field=='out':
            ax.axhline(3.63,ls='--',color='#454f52',lw=.9,label='3.63 V 筛查')
        else:
            ax.set_yscale('symlog',linthresh=.035)
            ax.axhline(.1,ls='--',color='#454f52',lw=.9,label='0.1 µA 门槛')
            ax.axvline(20,ls=':',color='#45545a',lw=1)
        ax.grid(alpha=.15)
        ax.spines[['top','right']].set_visible(False)
        ax.legend(frameon=False,fontsize=8,loc='upper right')
    fig.savefig(OUT/'b-final-edges.png',dpi=175)
    (EV/'b-final-edges.sources.json').write_text(json.dumps(SOURCES,indent=2)+'\n')


if __name__=='__main__':
    plt.rcParams.update({'font.family':['PingFang SC','DejaVu Sans'],'axes.unicode_minus':False})
    main()
