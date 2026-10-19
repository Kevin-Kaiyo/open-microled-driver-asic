from pathlib import Path
import json,shutil,argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'docs/research/single-pixel-closure-20261015/figures'
plt.rcParams.update({'font.family':'Avenir Next','font.size':11,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.labelcolor':'#304b57','text.color':'#304b57','axes.edgecolor':'#91a4aa','figure.facecolor':'white'})
def save(fig,name):
 fig.tight_layout();fig.savefig(OUT/(name+'.svg'),bbox_inches='tight');fig.savefig(OUT/(name+'.png'),dpi=150,bbox_inches='tight');plt.close(fig)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--analog-tag',default='pex-r5-cc30');a=ap.parse_args()
 ac=json.loads((ROOT/'evidence/analog-v3/ac-pex-r5-bleed10M/summary.json').read_text());results=ac['results']
 fig,ax=plt.subplots(figsize=(8.8,3.1));x=np.arange(3);w=.34
 for shift,cc,col in [(-w/2,3,'#b56336'),(w/2,30,'#176e73')]:
  values=[next(r['crossings'][0]['phase_margin_deg'] for r in results if r['envelope']==e and r['cc_pf']==cc and r['csense_pf']==30) for e in ['tt','ss','ff']]
  bars=ax.bar(x+shift,values,w,label=f'CCOMP {cc} pF',color=col);ax.bar_label(bars,fmt='%.1f°',padding=3)
 ax.axhline(60,color='#789ba0',ls='--',label='60° target');ax.set(xticks=x,xticklabels=['TT / 27°C','SS / 85°C','FF / 0°C'],ylabel='Phase margin (degree)',ylim=(0,105));ax.legend(loc='upper right',ncol=3,fontsize=9);save(fig,'loop-margin')
 old=ROOT/'evidence/analog-v3/pex-r4-cc30/startup_tt_100/compact.csv';new=ROOT/'evidence/analog-v3/pex-r5-cc30/startup_tt_100/compact.csv'
 if new.exists():
  fig,axes=plt.subplots(1,2,figsize=(9,3.4))
  for ax,p,label in [(axes[0],old,'r4: long parallel routes'),(axes[1],new,'r5: shortened routes / low-R return')]:
   d=np.loadtxt(p,delimiter=',' if p.suffix=='.csv' else None,skiprows=1);m=d[:,0]<150e-9;ax.plot(d[m,0]*1e9,d[m,1]*1e9,color='#176e73');ax.set(xlabel='Time (ns)',ylabel='LED branch current (nA)',title=label);ax.grid(alpha=.18)
   if p==new:ax.axhline(1,color='#b56336',ls='--');ax.axhline(-1,color='#b56336',ls='--')
  save(fig,'startup-comparison')
 summary=ROOT/'evidence/analog-v3'/a.analog_tag/'summary.json'
 if summary.exists():
  s=json.loads(summary.read_text());fig,axes=plt.subplots(1,2,figsize=(9,3.4))
  for env,col in [('tt','#176e73'),('ss','#b56336'),('ff','#6577a2')]:
   p=summary.parent/f'startup_{env}_100/compact.csv'
   if not p.exists():p=ROOT/next(x['source_raw_directory'] for x in s['results'] if x['name']==f'startup_{env}_100')/'waveform.dat'
   if p.exists():
    d=np.loadtxt(p,delimiter=',' if p.suffix=='.csv' else None,skiprows=1);m=d[:,0]<200e-9;axes[0].plot(d[m,0]*1e9,d[m,1]*1e9,label=env.upper(),color=col)
   p=summary.parent/f'fault_{env}/compact.csv'
   if not p.exists():p=ROOT/next(x['source_raw_directory'] for x in s['results'] if x['name']==f'fault_{env}')/'waveform.dat'
   if p.exists():
    d=np.loadtxt(p,delimiter=',' if p.suffix=='.csv' else None,skiprows=1);m=(d[:,0]>50e-6)&(d[:,0]<51.125e-6);axes[1].plot((d[m,0]-50.125e-6)*1e9,d[m,1]*1e6,label=env.upper(),color=col)
  axes[0].set(xlabel='Time (ns)',ylabel='Startup branch current (nA)');axes[0].axhline(1,ls='--',color='#b56336');axes[0].axhline(-1,ls='--',color='#b56336');axes[0].legend()
  axes[1].set(xlabel='Time from FAULT (ns)',ylabel='LED branch current (µA)');axes[1].axhline(0,color='#91a4aa',lw=.8);axes[1].legend()
  for ax in axes:ax.grid(alpha=.18)
  save(fig,'pex-waveforms')
 for name in ['overview.svg','reference-detail.svg','fault-buffer-detail.svg','welltap-detail.svg']:
  p=ROOT/'evidence/layout-v3/r5'/name
  if p.exists():shutil.copyfile(p,OUT/('r5-'+name))
 p=ROOT/'evidence/startup-v3/numerical/figures/startup-numerical-convergence.svg'
 if p.exists():shutil.copyfile(p,OUT/'numerical.svg')
 shutil.copyfile(ROOT/'evidence/startup-v3/numerical/figures/pex-ff-initial-corner.svg',OUT/'pex-initial-corner.svg')
 p=ROOT/'evidence/control-v3/coupled-r5-bleed10/fault_stopped_recovery.csv'
 if p.exists():
  d=np.loadtxt(p,delimiter=',',skiprows=1);t=d[:,0]*1e6
  fig,axes=plt.subplots(2,1,figsize=(9,4.2),sharex=True)
  for i,l,col in [(2,'RAW PWM','#6577a2'),(3,'PERMIT','#176e73'),(4,'FAULT','#b56336')]:axes[0].plot(t,d[:,i],label=l,color=col)
  axes[0].set(ylabel='Control (V)');axes[0].legend(ncol=3,loc='upper right',fontsize=9)
  axes[1].plot(t,d[:,1]*1e6,color='#176e73');axes[1].set(xlabel='Time in replay window (µs)',ylabel='LED branch (µA)')
  for ax in axes:ax.grid(alpha=.18)
  save(fig,'sdf-fault')
if __name__=='__main__':main()
