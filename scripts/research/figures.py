"""Draw current research figures from public source data and actual evidence."""
from pathlib import Path
import csv
import json
import hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/figures'
OUT.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':['Avenir Next','Arial','sans-serif'],
                     'font.size':11,'axes.spines.top':False,'axes.spines.right':False,
                     'axes.labelcolor':'#314a57','text.color':'#314a57',
                     'axes.edgecolor':'#9eb1b8','xtick.color':'#526b77','ytick.color':'#526b77'})
inputs=[]
def read(name):
    inputs.append(name)
    return json.loads((ROOT/name).read_text())
def rows(name):
    inputs.append(name)
    with (ROOT/name).open() as f:return list(csv.DictReader(f))
def save(fig,name):
    fig.tight_layout()
    fig.savefig(OUT/name,dpi=190,bbox_inches='tight',facecolor='white')
    plt.close(fig)

led=rows('analog/models/measured-led/lin2026-yellow20-diamond-iv.csv')
keys=list(led[0])
ikey=next(k for k in keys if k.lower() in ['current_a','current_A'.lower()])
vkey=next(k for k in keys if k.lower()=='voltage_v')
i=np.array([float(x[ikey]) for x in led]);v=np.array([float(x[vkey]) for x in led])
fig,ax=plt.subplots(figsize=(8.5,3.4))
ax.semilogx(i*1e6,v,'o-',color='#1c7c83',markersize=2.7,linewidth=1.2,label='100 author data points')
ax.plot(100,3.767909545,'o',color='#ba6843',markersize=7)
ax.annotate('100 µA / 3.76791 V',xy=(100,3.767909545),xytext=(240,3.1),
            arrowprops={'arrowstyle':'->','color':'#9d785d'})
ax.set(xlabel='Forward current (µA, log scale)',ylabel='Forward voltage (V)',
       title='20 µm yellow InGaN LED on diamond: static I-V')
ax.legend(frameon=False,loc='upper left');ax.grid(alpha=.15)
save(fig,'measured-iv.png')

measured=read('evidence/characterization/measured-load-summary.json')
head=[r for r in measured['dc_results'] if r['group']=='headroom']
fig,ax=plt.subplots(figsize=(8.5,3.5))
ax.axhspan(95,105,color='#d9e9df',alpha=.7,label='Project target: 100 µA ±5%')
ax.plot([r['vled_v'] for r in head],[r['current_uA'] for r in head],'o-',color='#1b7881')
ax.axhline(100,color='#97a7ae',linewidth=.8,linestyle='--')
ax.set(xlabel='LED supply (V)',ylabel='Full-on current (µA)',ylim=(75,108),
       title='Actual 20/4 RC + measured static LED; TT MOS / 27°C')
ax.legend(frameon=False,loc='lower right');ax.grid(alpha=.15)
save(fig,'headroom.png')

old=rows('evidence/characterization/mc-conditional_high.csv')
new=rows('evidence/characterization/actual-w20-l4-mc-conditional_high.csv')
fig,ax=plt.subplots(figsize=(8.5,3.5))
bins=np.linspace(98,106,33)
ax.hist([float(x['iout'])*1e6 for x in old],bins=bins,color='#a9b7c2',alpha=.8,label='10/2 RC: 4/256 above 105 µA')
ax.hist([float(x['iout'])*1e6 for x in new],bins=bins,color='#1a8188',alpha=.7,label='Actual 20/4 RC: 0/256 outside target')
ax.axvline(105,color='#b06347',linewidth=1.5,linestyle='--')
ax.set(xlabel='Full-on current (µA)',ylabel='Count',title='Same-seed conditional high-current Monte Carlo')
ax.legend(frameon=False,fontsize=10);ax.grid(axis='y',alpha=.15)
save(fig,'matching.png')

sources={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sorted(set(inputs))}
data={'status':'derived figures, not copied paper illustrations',
      'source_hashes':sources,'measured_iv_attribution':'Lin et al. Zenodo 20034288, CC BY 4.0',
      'output_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob('*.png'))}}
(ROOT/'evidence/characterization/research-figures.json').write_text(json.dumps(data,indent=2)+'\n')
print('Created three source-backed scientific figures')
