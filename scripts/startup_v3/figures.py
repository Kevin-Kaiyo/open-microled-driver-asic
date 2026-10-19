"""Plot actual startup numerical diagnostics; no smoothing or artificial waves."""
from pathlib import Path
import json, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[2];D=R/'evidence/startup-v3/numerical';W=R/'build/startup-v3/numerical'
s=json.loads((D/'refined-summary.json').read_text());o=json.loads((D/'summary.json').read_text());out=D/'figures';out.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,ax=plt.subplots(2,2,figsize=(11.4,7.5),constrained_layout=True)
colors=['#157c85','#ec965b','#546783','#a2639a']
# Older and new waveforms around the actual sharp corner at 100 ns.
for n,label,col in [('base_10ns','Original Gear2 / 10ns',colors[2]),('base_2ns','Original Gear2 / 2ns',colors[1])]:
 a=np.loadtxt(W/n/'waveform.dat',skiprows=1,usecols=[0,9]);mask=(a[:,0]>=99.99e-9)&(a[:,0]<=100.04e-9);ax[0,0].plot((a[mask,0]-100e-9)*1e12,a[mask,1]*1e12,label=label,color=col,marker='.',ms=3)
for order,col in [(1,colors[0]),(2,colors[3])]:
 n=f'gear{order}_mesh1tick_s2_r1e-8';a=np.loadtxt(W/'localmesh-final'/n/'waveform.dat',skiprows=1,usecols=[0,1]);mask=(a[:,0]>=99.99e-9)&(a[:,0]<=100.04e-9);ax[0,0].plot((a[mask,0]-100e-9)*1e12,a[mask,1]*1e12,label=f'Refined Gear{order} / 0.1ps knots',color=col,lw=1)
ax[0,0].set(title='A  The 100ns ramp corner needs local time resolution',xlabel='Time relative to ramp corner (ps)',ylabel='LED branch current (pA)');ax[0,0].legend(fontsize=7)
# Error norm evolves with mesh refinement.
for order,col in [(1,colors[0]),(2,colors[3])]:
 rows=[r for r in s['results'] if r['order']==order and r['maxstep_ns']==2 and r['reltol']==1e-8];rows.sort(key=lambda r:r['local_mesh_ps'],reverse=True)
 ax[0,1].plot([r['local_mesh_ps'] for r in rows],[r['charge']['positive_c']/1e-21 for r in rows],marker='o',label=f'Gear{order}',color=col)
ax[0,1].set_xscale('log');ax[0,1].invert_xaxis();ax[0,1].set(title='B  Tiny positive charge still has relative sensitivity',xlabel='Local time mesh (ps, finer to right)',ylabel='Q+ (10^-21 C)');ax[0,1].legend(fontsize=8)
# Show maximum pairwise error, with all final methods/tolerance comparisons.
coarse=[p['maximum_current_difference_a']*1e12 for p in s['all_comparisons'] if 'mesh10tick' in p['a'] or 'mesh10tick' in p['b']]
sel=[p['maximum_current_difference_a']*1e12 for p in s['selected_comparisons']]
ax[1,0].bar([0,1],[max(coarse),max(sel)],color=[colors[1],colors[0]],width=.5)
ax[1,0].axhline(2,color='#bd4146',ls='--',label='Declared 2pA difference limit');ax[1,0].set_xticks([0,1],['Including 1ps coarse controls','0.2/0.1ps final controls']);ax[1,0].set(title='C  All 45 final comparisons, including solver/tolerance',ylabel='Maximum waveform difference (pA)');ax[1,0].legend(fontsize=8)
# Trap diagnostic illustrates why net charge alone hides ringing.
for n,col in [('trap_10ns',colors[1]),('base_10ns',colors[0])]:
 a=np.loadtxt(W/n/'waveform.dat',skiprows=1,usecols=[0,9]);mask=(a[:,0]>=1e-6)&(a[:,0]<=1.2e-6);ax[1,1].plot(a[mask,0]*1e6,a[mask,1]*1e12,color=col,label=n)
ax[1,1].set(title='D  TRAP numerical ringing must not be called LED light',xlabel='Time (us)',ylabel='LED branch current (pA)');ax[1,1].legend(fontsize=8)
for a in ax.flat:a.grid(alpha=.15)
fig.suptitle('Unchanged startup-v2 circuit: numerical convergence and an explicit criterion revision',fontsize=13)
fig.savefig(out/'startup-numerical-convergence.svg');fig.savefig(out/'startup-numerical-convergence.png',dpi=180);plt.close(fig)
