#!/usr/bin/env python3
"""Native-grid edge diagnostic, a fixed pre-fault symbol window only."""
from pathlib import Path
import gzip,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import run as a
plt.rcParams.update({'font.sans-serif':['PingFang SC','Hiragino Sans GB','DejaVu Sans'],'font.size':10,'svg.fonttype':'none','axes.unicode_minus':False})
def main():
 cases=[(a.FROZEN/'fault-f2-net1.6-s40','原 v3r','#5e6c78'),(a.BUILD/'trackwide4gm5-fixed/TT-fault-s40','输出 W×4、OTA gm 提升','#b67b31'),(a.BUILD/'trackwide4gm5pre2-fixed/TT-continuous-f1-s40','再将末级预驱动 W×2','#087c80'),(a.BUILD/'trackwide4gm5buf2-fixed/TT-continuous-f1-s40','再将前级 W×2','#704c95')]
 ui=(32/37)/1.6e9;start=600*ui;stop=624*ui;fig,axes=plt.subplots(2,1,figsize=(12,6),sharex=True);receipts=[]
 for folder,label,color in cases:
  if not (folder/'result.json').exists():continue
  m=a.read(folder/'manifest.json');r=a.read(folder/'result.json');ix=m['vectors'];keys=['iled_cond','xdrv.ctrl','xdrv.n1','out','d0'];rows=[]
  with gzip.open(folder/'waveform.dat.gz','rt') as f:
   next(f)
   for line in f:
    time=float(line.split(None,1)[0])
    if time>stop:break
    if time>=start:
     values=line.split();rows.append([time]+[float(values[ix[k]]) for k in keys])
  z=np.asarray(rows);assert len(z)>50
  axes[0].plot((z[:,0]-start)/ui,z[:,1]*1e6,color=color,lw=1,label=label);axes[1].plot((z[:,0]-start)/ui,z[:,2],color=color,lw=1,label=label)
  def events(col):
   y=z[:,col]-1.65;j=np.flatnonzero(y[:-1]*y[1:]<0);times=z[j,0]+(z[j+1,0]-z[j,0])*(-y[j])/(y[j+1]-y[j]);return list(zip(times,np.sign(y[j+1]-y[j])))
  ev_in,ev_n1,ev_ctrl=events(5),events(3),events(2);lat=[]
  for t,sgn in ev_in:
   n=[tt for tt,d in ev_n1 if d==-sgn and t<tt<t+ui]
   c=[tt for tt,d in ev_ctrl if d==sgn and t<tt<t+ui]
   if n and c:lat.append(dict(input_rising=bool(sgn>0),input_to_N1_ps=float((n[0]-t)*1e12),input_to_CTRL_ps=float((c[0]-t)*1e12)))
  receipts.append(dict(case=str(folder.relative_to(a.ROOT)),manifest_sha256=a.sha(folder/'manifest.json'),result_sha256=a.sha(folder/'result.json'),waveform_gzip_sha256=r['gzip_sha256'],window_symbols=[600,624],window_frame=1,window_before_fault=True,native_rows_in_window=len(z),range_current_uA=[float(z[:,1].min()*1e6),float(z[:,1].max()*1e6)],half_supply_crossing_latency=lat,mean_input_to_N1_ps=float(np.mean([x['input_to_N1_ps'] for x in lat])),mean_input_to_CTRL_ps=float(np.mean([x['input_to_CTRL_ps'] for x in lat])),scope='Same pre-fault first-frame bits. Local edge diagnostic only, not a fullframe rate verdict.'))
 axes[0].set_ylabel('LED 导通电流 / µA');axes[1].set_ylabel('CTRL 栅极电压 / V');axes[1].set_xlabel('相对第 600 个线符号的位置 / UI（1 UI = 540.54 ps）')
 for ax in axes:ax.grid(alpha=.17);ax.legend(loc='upper right',frameon=False,fontsize=8)
 fig.suptitle('相同数据边沿：输出栅电容增加与预驱动增强的竞争',x=.07,ha='left',fontsize=14,color='#17384a');fig.text(.08,.01,'标称 TT；均取原生波形第1帧、关断之前的同一符号段。此局部图只解释边沿，性能判定使用完整4096个验证bit。',fontsize=9)
 fig.tight_layout(rect=(0,.04,1,.97));out=a.ROOT/'docs/research/driver-pvt-20261117/assets';fig.savefig(out/'a-edge-waveforms.png',dpi=160);fig.savefig(out/'a-edge-waveforms.svg');plt.close(fig)
 a.emit(a.EV/'a-edge-waveforms-sources.json',dict(cases=receipts,script_sha256=a.sha(Path(__file__))))
if __name__=='__main__':main()
