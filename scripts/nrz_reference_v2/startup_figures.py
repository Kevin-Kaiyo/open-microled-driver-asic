#!/usr/bin/env python3
"""True integrated-PEX startup and wrong-sequence control plots with envelopes."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import run as r
W=r.BUILD/'selected-final-r2';OUT=r.ROOT/'docs/research/nrz-b-reference-power-20261024/electrical-figures'
def load(kind):
 p=next(p for p in (W/'cases').glob('*/result.json') if json.loads(p.read_text())['case']['kind']==kind);q=json.loads(p.read_text());r.module(W/'inputs/legacy/metrics.py','metrics');a=r.module(W/'inputs/legacy/analyze.py','startup_plot');a.ROOT=r.ROOT;tr,_=a.load_trace(q,p);vec=q['vectors'];node=lambda n:np.zeros(len(tr)) if n=='0' else tr[:,vec[n]]
 largest=np.zeros(len(tr));pair_records=[]
 for d in q['devices']:
  if '03v3' not in d['model']:continue
  for i,j in [(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)]:
   difference=np.abs(node(d['nodes'][i])-node(d['nodes'][j]));largest=np.maximum(largest,difference);pair_records.append((float(difference.max()),d['instance'],i,j))
 worst=max(pair_records);signals={'ILED_A':tr[:,vec['iled_cond']],'OUT_V':tr[:,vec['out']],'max03pair_V':largest,'anchor_source_V':tr[:,vec['vref_voltage']],'DISABLE_source_V':tr[:,vec['vdisable_voltage']]};t=tr[:,0]
 bins=np.linspace(0,100e-6,2001);rows=[]
 for lo,hi in zip(bins[:-1],bins[1:]):
  sel=(t>=lo)&(t<hi)
  if sel.any():rows.append([(lo+hi)/2]+[value for a in signals.values() for value in [float(a[sel].min()),float(a[sel].max())]])
 csv=OUT/(kind+'-envelope.csv');np.savetxt(csv,np.asarray(rows),delimiter=',',header=','.join(['time_s']+[name+suffix for name in signals for suffix in ['_min','_max']]),comments='')
 # Preserve actual samples around release to avoid claiming the envelope is a smooth trace.
 release=q['case']['startup']['disable_release_s'];sel=(t>release-.1e-6)&(t<release+1e-6);window=OUT/(kind+'-release.csv');np.savetxt(window,np.column_stack([t[sel]]+[a[sel] for a in signals.values()]),delimiter=',',header=','.join(['time_s']+list(signals)),comments='')
 record={'case':kind,'result':r.rel(p),'result_sha256':r.sha(p),'waveform_sha256':q['waveform_sha256'],'analysis_sha256':r.sha(p.with_name('startup-analysis.json')),'envelope':r.rel(csv),'envelope_sha256':r.sha(csv),'release_window':r.rel(window),'release_window_sha256':r.sha(window),'worst03':{'voltage_V':worst[0],'instance':worst[1],'node_pair_indices_DGSB':worst[2:]}}
 return t,signals,record
def main():
 OUT.mkdir(exist_ok=True,parents=True);plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'figure.dpi':160});records=[]
 fig,axes=plt.subplots(2,1,figsize=(7.2,6),layout='constrained')
 for label,col in [('TT','#236d8b'),('SS','#b77d27'),('FF','#9c4772')]:
  t,s,rec=load('startup_'+label);records.append(rec)
  for ax in axes:ax.plot(t*1e6,s['ILED_A']*1e6,label=label,color=col,lw=1.3)
 axes[0].set_xlim(0,100);axes[1].set_xlim(19.98,20.35);axes[0].set_title('Selected 21-MOS fullRC: external enable at 20 us');axes[0].legend(frameon=False);axes[0].set_ylabel('Conductive LED current (uA)');axes[1].set_ylabel('Release detail (uA)');axes[0].set_xlabel('Time (us)');axes[1].set_xlabel('Time (us)')
 for ext in ['png','svg']:fig.savefig(OUT/('selected-startup.'+ext))
 plt.close(fig);fig,axes=plt.subplots(3,2,figsize=(10,8),sharex=True,layout='constrained')
 for j,(kind,title) in enumerate([('startup_late_anchor','Correct: anchor30 us, release50 us'),('startup_early_release_NEG','Wrong: release20 us, anchor30 us')]):
  t,s,rec=load(kind);records.append(rec);u=t*1e6
  axes[0,j].plot(u,s['anchor_source_V'],label='Anchor source',color='#236d8b');axes[0,j].plot(u,s['DISABLE_source_V'],label='DISABLE source',color='#b77d27');axes[0,j].set_title(title,fontsize=11)
  axes[1,j].plot(u,s['OUT_V'],label='OUT',color='#236d8b');axes[1,j].plot(u,s['max03pair_V'],label='Largest 03v3 pair',color='#9c4772');axes[1,j].axhline(3.63,color='.4',ls=':',label='3.63 V project screen');axes[1,j].set_ylim(0,5.1)
  axes[2,j].plot(u,s['ILED_A']*1e6,color='#236d8b');axes[2,j].set_xlabel('Time (us)')
  for k in range(3):axes[k,j].set_xlim(0,60)
  axes[0,j].legend(frameon=False,fontsize=8);axes[1,j].legend(frameon=False,fontsize=8)
 axes[0,0].set_ylabel('Control sources (V)');axes[1,0].set_ylabel('Actual node / pair (V)');axes[2,0].set_ylabel('Conductive LED (uA)')
 fig.suptitle('Different sequencing conditions; same selected integrated PEX',fontsize=12)
 for ext in ['png','svg']:fig.savefig(OUT/('startup-sequencing-control.'+ext))
 plt.close(fig);r.emit(OUT/'startup-sources.json',{'script_sha256':r.sha(__file__),'records':records,'scope':'Allwaveformsactual21MOSintegratedfullRC; 50nsminmaxenvelopesretainextrema,rawactualsamplesplotted; notsameinputsequencecomparison.'})
if __name__=='__main__':main()
