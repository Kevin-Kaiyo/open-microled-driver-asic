"""Native edge comparison; include model thresholds and the unknown optical leakage regime."""
import json
import numpy as np
import matplotlib.pyplot as plt
import report

def main():
    folders=report.a.BUILD/'edge-SS'
    fig,axes=plt.subplots(1,2,figsize=(10.5,4))
    for c,color in [(0,report.GRAY),(150,report.TEAL)]:
        z=np.load(folders/f'assert-c{c}-s40'/'preview.npz')
        t=z['time_s']*1e9-32
        for ax,key,bounds,yscale in [(axes[0],'iso_g',[-.3,2.5],'linear'),(axes[1],'iled_uA',[0,24],'log')]:
            mask=(t>=bounds[0])&(t<=bounds[1])
            y=z[key][mask]
            ax.plot(t[mask],np.abs(y) if yscale=='log' else y,label=f'CISOEDGE = {c} fF',color=color,lw=2)
            ax.set_yscale(yscale);ax.set_xlim(*bounds)
            ax.set_xlabel('相对 DISABLE 断言 / ns')
    for ax,lim,yl,title in [(axes[0],-.30,'ISO_G / V','负向耦合峰减小'),(axes[1],.10,'|LED 导通电流| / µA','关断阈值的穿越时间')]:
        ax.axhline(lim,color=report.RUST,ls='--',lw=.9)
        ax.set_ylabel(yl);ax.set_title(title,loc='left',color=report.NAVY)
        ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.14)
    axes[0].set_ylim(-.43,.65)
    axes[0].legend(frameon=False,fontsize=9)
    fig.tight_layout();report.save(fig,'a-shutdown-cap')
    rows=[report.a.read(p) for p in sorted(folders.glob('*/result.json'))]
    report.a.emit(report.a.EV/'edge-summary.json',dict(source='Matched 128ns native time-grid, local DC start. S40 includes both topologies; S80 refines the 150fF design.',cases=rows))

if __name__=='__main__':main()
