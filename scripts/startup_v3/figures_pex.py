from pathlib import Path
import json,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[2];D=R/'evidence/startup-v3/numerical';s=json.loads((D/'pex-r5-bleed10M-ff-probe/summary.json').read_text());rows={r['name']:r for r in s['results']};out=D/'figures';out.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,ax=plt.subplots(1,3,figsize=(12,4.5),constrained_layout=True)
original=R/s['source_deck'];old=np.loadtxt(original.parent/'waveform.dat',skiprows=1,usecols=[0,1]);mask=old[:,0]<=25e-12;ax[0].plot(old[mask,0]*1e12,old[mask,1]*1e9,'.-',color='#bc5458',label='Original adaptive first step')
for name,color in [('gear1_mesh0.5tick_gmin1e-12_standard','#157c85'),('gear2_mesh0.5tick_gmin1e-12_standard','#626c96')]:
 a=np.loadtxt(R/rows[name]['raw_directory']/'waveform.dat',skiprows=1,usecols=[0,1]);mask=a[:,0]<=25e-12;ax[0].plot(a[mask,0]*1e12,a[mask,1]*1e9,color=color,label='Gear'+str(rows[name]['order'])+' / 0.05ps grid')
ax[0].axhline(-1,color='#777',ls='--',label='Absolute-current guard: ±1nA');ax[0].axhline(1,color='#777',ls='--');ax[0].set(title='A  Initial-corner current: same physical circuit',xlabel='Time from ramp start (ps)',ylabel='LED branch current (nA)');ax[0].legend(fontsize=7)
coarse=[p['current_max_difference_a'] for p in s['all_comparisons'] if p['same_op_numerical_control'] and ('mesh2tick' in p['a'] or 'mesh2tick' in p['b']) and 'tight' not in p['a'] and 'tight' not in p['b']]
final=[p['current_max_difference_a'] for p in s['selected_comparisons']];ax[1].bar([0,1],[max(coarse)*1e12,max(final)*1e12],width=.5,color=['#d59459','#157c85']);ax[1].axhline(2,color='#bc5458',ls='--');ax[1].set_xticks([0,1],['Includes 0.2ps grid','0.1/0.05ps final grids']);ax[1].set(title='B  Whole-waveform comparison, not peak only',ylabel='Worst pointwise difference (pA)')
labels=[];values=[];colors=[]
for g in ['1e-14','1e-12','1e-10']:
 row=rows[f'gear2_mesh1tick_gmin{g}_standard'];labels.append(g+('\nTransient OP fallback' if row['transient_op_fallback'] else '\nOrdinary DC OP'));values.append(row['peak_a']*1e9);colors.append('#d59459' if row['transient_op_fallback'] else '#157c85')
ax[2].bar(range(3),values,color=colors,width=.5);ax[2].axhline(1,color='#bc5458',ls='--');ax[2].set_xticks(range(3),labels,fontsize=7);ax[2].set(title='C  gmin sensitivity keeps OP paths separate',ylabel='Absolute branch peak (nA)',xlabel='gmin (S)')
for a in ax:a.grid(axis='y',alpha=.15)
fig.suptitle('r5 full-RC PEX + external CCOMP 30pF, CSENSE 30pF, REFOUT bleed 10MΩ\nFF, 0°C, 3.63V logic/reference, 5.5V LED; initial 20ns probe only',fontsize=11)
fig.savefig(out/'pex-ff-initial-corner.svg');fig.savefig(out/'pex-ff-initial-corner.png',dpi=180);plt.close(fig)
