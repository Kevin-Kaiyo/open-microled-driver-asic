#!/usr/bin/env python3
"""Protection-node native-waveform diagnostics; no source case changes."""
import gzip
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import run as a
plt.rcParams.update({'font.sans-serif':['PingFang SC','Hiragino Sans GB','DejaVu Sans'],'font.size':10,'svg.fonttype':'none','axes.unicode_minus':False})
def main():
 fig,axes=plt.subplots(2,2,figsize=(11.5,6),sharey=True);receipts=[]
 for row,variant in enumerate(['baseline','trackwide4gm5-fixed']):
  folder=a.BUILD/variant/'SShotlow-fault-s40';m=a.read(folder/'manifest.json');r=a.read(folder/'result.json');ix=m['vectors'];windows=[m['fault']['assert_s'],m['fault']['release_s']];records=[[],[]]
  with gzip.open(folder/'waveform.dat.gz','rt') as f:
   next(f)
   for line in f:
    t=float(line.split(None,1)[0])
    if t>windows[-1]+25e-9:break
    for k,edge in enumerate(windows):
     if edge-5e-9<=t<=edge+25e-9:
      v=line.split();records[k].append([t]+[float(v[ix[n]]) for n in ['led_a','led_feed','iso_g']])
  for k,values in enumerate(records):
   z=np.array(values);ax=axes[row,k];ax.plot((z[:,0]-windows[k])*1e9,np.maximum(z[:,1]-z[:,2],0),color='#b16f2a',label='隔离PMOS：阳极−体');ax.plot((z[:,0]-windows[k])*1e9,np.maximum(-z[:,3],0),color='#087c80',label='XLS_N1：体−漏极');ax.axhline(.3,color='#ae4d43',ls='--',label='原0.3 V筛选');ax.set_ylim(-.01,.4);ax.grid(alpha=.16);ax.set_title(('原 A' if row==0 else '差分感测/W×4/gm提升')+' · '+('关断断言' if k==0 else '释放'),loc='left');ax.set_xlabel('相对控制边沿 / ns');ax.set_ylabel('体结正偏 / V');ax.legend(frameon=False,fontsize=7)
  receipts.append(dict(case=str(folder.relative_to(a.ROOT)),manifest_sha256=a.sha(folder/'manifest.json'),result_sha256=a.sha(folder/'result.json'),raw_sha256=r['raw_sha256'],gzip_sha256=r['gzip_sha256'],nodes=['led_a','led_feed','iso_g'],windows_relative_ns=[-5,25],scope='Terminal voltage diagnostic, not junction current or latch-up qualification. Fulltrace native MOS screen kept separately.'))
 fig.suptitle('SS / 85°C / −5% 电源：关断电流合格仍不代表所有节点应力合格',x=.065,ha='left',fontsize=13,color='#17384a');fig.tight_layout(rect=(0,0,1,.96));out=a.ROOT/'docs/research/driver-pvt-20261117/assets';fig.savefig(out/'a-protection-waveforms.png',dpi=160);fig.savefig(out/'a-protection-waveforms.svg');plt.close(fig);a.emit(a.EV/'a-protection-waveforms-sources.json',dict(cases=receipts,script_sha256=a.sha(Path(__file__))))
if __name__=='__main__':main()
