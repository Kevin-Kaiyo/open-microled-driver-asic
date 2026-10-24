#!/usr/bin/env python3
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import run as r
p=r.EVIDENCE/'sampler-diagnostic.json';data=json.loads(p.read_text());rows={x['rate_Gbps']:x for x in data['rows'] if x['kind'] in ['SSminus50','SSminus50_rate04']};rates=sorted(rows)
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(figsize=(8,4.8),layout='constrained');fig.patch.set_facecolor('#fcfcfa');ax.set_facecolor('#fcfcfa')
ax.scatter(rates,[rows[z]['threshold_margin_normalized'] for z in rates],s=90,marker='o',c='#145b78',label='Vertical threshold margin / 75 µA',zorder=3)
ax.scatter(rates,[min(rows[z]['timing_left_ui'],rows[z]['timing_right_ui']) for z in rates],s=90,marker='s',c='#218578',label='Minimum timing margin / UI',zorder=3)
ax.axhline(.1,color='#b35b48',ls='--',lw=1.3,label='Each screen requires ≥ 0.1')
for rate in rates:
 row=rows[rate];a=row['threshold_margin_normalized'];b=min(row['timing_left_ui'],row['timing_right_ui'])
 ax.annotate(f'{a:.4f}',(rate,a),xytext=(0,9),textcoords='offset points',ha='center',color='#145b78')
 ax.annotate(f'{b:.4f}',(rate,b),xytext=(0,-17),textcoords='offset points',ha='center',color='#218578')
 ax.text(rate,.065,'PASS' if a>=.1 and b>=.1 else 'FAIL',ha='center',weight='bold',color='#218578' if a>=.1 and b>=.1 else '#b35b48')
ax.set(xlabel='Discrete tested gross rate (Gb/s)',ylabel='Normalized margin',xticks=rates,xlim=(.20,.55),ylim=(.055,.195))
ax.set_title('A8 actual RC • SS / 125°C / 2.95 V\nFrozen receiver and training rule; no validation retuning',loc='left',pad=16,fontweight='bold')
ax.grid(axis='y',alpha=.15);ax.legend(loc='upper right',frameon=False,fontsize=9)
fig.savefig(r.EVIDENCE/'sampler-discrete-points.png',dpi=180);fig.savefig(r.EVIDENCE/'sampler-discrete-points.svg')
r.emit(r.EVIDENCE/'sampler-discrete-points-source.json',{'source':r.rel(p),'source_sha256':r.sha(p),'rows':list(rows.values()),'interpretation':'Markers are measured simulation points only; no interpolation or continuous maximum claim.'})
