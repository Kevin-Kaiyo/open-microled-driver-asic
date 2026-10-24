#!/usr/bin/env python3
"""Plot frozen r1 evidence as the failed first revision, not final selected performance."""
from pathlib import Path
import json,hashlib,csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'docs/research/nrz-b-reference-power-20261024/figures';OUT.mkdir(parents=True,exist_ok=True)
oldp=ROOT/'evidence/highspeed-nrz-robustness/summary-verified.json';newp=ROOT/'evidence/nrz-reference-v2/selected-r1-summary.json'
old=json.loads(oldp.read_text())['selected']['rows'];new=json.loads(newp.read_text())['rows'];energy='rail_plus_DATA_positive_draw_fJ_per_gross_bit'
rows=[]
for lab,oldkind in [('TT','TT'),('SS','SSminus50'),('FF','FFplus50')]:
 a=next(r for r in old if r['route']=='B' and r['kind']==oldkind and r['rate_Gbps']==.5);b=next(r for r in new if r['kind']==lab+'_nrz')
 assert a['corner']==b['corner'] and a['temp_C']==b['temp_C'] and a['vdd_V']==b['vdd_V']
 for ver,r in [('Original ideal VDUMMY',a),('r1 MOS reference + LDO',b)]:rows.append({'condition':lab,'revision':ver,'energy_pJ_per_bit':r[energy]/1000,'vertical_margin':r['threshold_margin_normalized'],'timing_margin_ui':r['timing_min_margin_ui'],'errors':r['errors'],'result_json':r['result_json']})
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,ax=plt.subplots(1,2,figsize=(12,4.4),layout='constrained');x=list(range(3));w=.36
for j,(label,color) in enumerate([('Original ideal VDUMMY','#9bacb4'),('r1 MOS reference + LDO','#178579')]):
 rs=[r for r in rows if r['revision']==label];xx=[i+(j-.5)*w for i in x]
 for k,key in enumerate(['energy_pJ_per_bit','vertical_margin']):
  bars=ax[k].bar(xx,[r[key] for r in rs],width=w,color=color,label=label)
  ax[k].bar_label(bars,fmt='%.2f' if k==0 else '%.3f',padding=4,fontsize=9)
for a in ax:a.set_xticks(x,['TT / 27 C','SS / 125 C','FF / -40 C']);a.grid(axis='y',alpha=.2);a.set_axisbelow(True)
ax[0].set_ylabel('Positive terminal energy (pJ / gross bit)');ax[1].set_ylabel('Normalized vertical RX margin');ax[0].set_ylim(0,7);ax[1].set_ylim(0,.31);ax[0].legend(frameon=False,fontsize=9)
fig.suptitle('0.5 Gb/s, unchanged LED / RX / data: r1 steady-state diagnostic only',fontsize=14)
fig.savefig(OUT/'nrz-r1-comparison.svg');fig.savefig(OUT/'nrz-r1-comparison.png',dpi=160);plt.close(fig)
with (OUT/'nrz-r1-comparison.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
(OUT/'nrz-r1-comparison-sources.json').write_text(json.dumps({'sources':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [oldp,newp]},'note':'r1 startup fails; these short communication-window metrics do not establish LDO stability or startup acceptance','generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n')
print('Wrote matched r1 evidence plots')
