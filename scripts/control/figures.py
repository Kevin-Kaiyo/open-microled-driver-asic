"""Plot measured-in-simulation frame averages; no optical/hardware claim."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
def main():
    s=json.loads((ROOT/'evidence/control/summary.json').read_text())
    rows=s['analog']['clean']['frames']
    x=[r['frame'] for r in rows]
    ideal=[s['dc_current_a']['1']*1e6*r['duty']/256 for r in rows]
    actual=[r['current_uA'] for r in rows]
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Avenir Next','Arial'],
                         'font.size':13,'svg.fonttype':'none'})
    fig,ax=plt.subplots(figsize=(8,2.65))
    ax.step(x+[14],ideal+[ideal[-1]],where='post',color='#87aeb4',label='DC full-on x quantized duty')
    ax.plot([v+.5 for v in x],actual,'o',color='#176977',ms=4,label='Transient frame average')
    ax.set(xlim=(0,14),ylim=(-5,115),xlabel='Complete PWM frame index (256 us/frame)',ylabel='LED branch current (uA)')
    ax.set_xticks(range(0,15,2)); ax.grid(axis='y',alpha=.2)
    ax.spines[['top','right']].set_visible(False)
    ax.legend(frameon=False,fontsize=12,loc='upper left')
    fig.tight_layout()
    base=ROOT/'docs/research/control-experiment'; base.mkdir(parents=True,exist_ok=True)
    fig.savefig(base/'frame-current.svg'); fig.savefig(base/'frame-current.png',dpi=180)
    svg=base/'frame-current.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)
if __name__=='__main__':main()
