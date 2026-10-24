#!/usr/bin/env python3
"""Standalone scientific plots tied to retained CSVs and source hashes."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import run as r
OUT=r.ROOT/'docs/research/nrz-b-reference-power-20261024/electrical-figures'
def main():
 OUT.mkdir(parents=True,exist_ok=True);sources=[]
 plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'figure.dpi':160})
 fig,ax=plt.subplots(2,1,figsize=(7.2,6),sharex=True,layout='constrained')
 for corner,label,color in [('typical','TT 27 C','#236d8b'),('ss','SS 125 C','#b77d27'),('ff','FF -40 C','#9c4772')]:
  folder=r.BUILD/f'vi-loop-shunt150-{corner}-b1-final-r2';p=folder/'loop.csv';a=np.loadtxt(p,delimiter=',',skiprows=1)
  for z,col in zip(ax,[1,2]):z.semilogx(a[:,0],a[:,col],label=label,color=color,lw=1.4)
  target=OUT/(corner+'-loop.csv');target.write_bytes(p.read_bytes());sources.append({'path':r.rel(p),'sha256':r.sha(p),'csv':r.rel(target),'result_sha256':r.sha(folder/'result.json')})
 ax[0].axhline(0,color='.45',ls=':',lw=.8);ax[1].axhline(-180,color='.45',ls=':',lw=.8);ax[0].set_ylabel('Return-ratio estimate (dB)');ax[1].set_ylabel('Phase (degrees)');ax[1].set_xlabel('Frequency (Hz)');ax[0].legend(frameon=False);ax[0].set_title('Selected 21-MOS fullRC: local two-injection estimate');ax[1].set_xlim(1e2,1e8)
 for ext in ['png','svg']:fig.savefig(OUT/('selected-loop.'+ext));plt.close(fig) if ext=='svg' else None
 fig,axes=plt.subplots(2,1,figsize=(7.2,6),sharex=False,layout='constrained')
 for workname,kind,label,color in [('clamped-r1','clamped_start_FF','3 pF Miller, same prelayout core','#9c4772'),('clamped-r2','shunt150_only_control','150 pF shunt, same prelayout core','#236d8b')]:
  work=r.BUILD/workname;p=next(p for p in (work/'cases').glob('*/result.json') if json.loads(p.read_text())['case']['kind']==kind);q=json.loads(p.read_text());r.module(work/'inputs/legacy/metrics.py','metrics');a=r.module(work/'inputs/legacy/analyze.py','plot_analysis');a.ROOT=r.ROOT;trace,_=a.load_trace(q,p);t=trace[:,0];i=trace[:,q['vectors']['iled_cond']]
  axes[0].plot(t*1e6,i*1e6,color=color,lw=.7,label=label);mask=t>90e-6;axes[1].plot(t[mask]*1e6,i[mask]*1e6,color=color,lw=.7)
  # Each0.1us bin exports both extrema; plotting source is the original trace.
  bins=np.linspace(0,100e-6,1001);data=[]
  for lo,hi in zip(bins[:-1],bins[1:]):
   sel=(t>=lo)&(t<hi)
   if sel.any():data.append([(lo+hi)/2,float(i[sel].min()),float(i[sel].max())])
  csv=OUT/(workname+'-FF-current-envelope.csv');np.savetxt(csv,np.array(data),delimiter=',',header='time_s,ILED_min_A,ILED_max_A',comments='');sources.append({'path':r.rel(p),'sha256':r.sha(p),'waveform_sha256':q['waveform_sha256'],'csv':r.rel(csv)})
 axes[0].legend(frameon=False,fontsize=9);axes[0].set_title('Single-factor compensation control, FF -40 C');axes[0].set_ylabel('Conductive LED current (uA)');axes[1].set_ylabel('Late current (uA)');axes[0].set_xlabel('Time (us)');axes[1].set_xlabel('Time (us)');axes[1].set_xlim(90,100)
 for ext in ['png','svg']:fig.savefig(OUT/('compensation-control.'+ext));plt.close(fig) if ext=='svg' else None
 r.emit(OUT/'sources.json',{'script_sha256':r.sha(__file__),'sources':sources,'scope':'Bodefigureactual21MOSintegratedPEX; waveformfigureprelayout11MOS+oldBPEXsinglefactorcontrol, identical10Mohmconstantkeeper. Distinctevidencelevels.'})
if __name__=='__main__':main()
