#!/usr/bin/env python3
"""Plot before/after A at the same rate on an unshifted native time axis."""
from pathlib import Path
import importlib.util,hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/ab-improvement-20261111';OUT=ROOT/'docs/research/driver-improvement-20261111/assets';EV=ROOT/'evidence/ab-improvement-20261111'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
spec=importlib.util.spec_from_file_location('A_wave_dynamics',ROOT/'scripts/microled_dynamic_v1/analyze.py');dyn=importlib.util.module_from_spec(spec);spec.loader.exec_module(dyn)
font='/System/Library/Fonts/Hiragino Sans GB.ttc';font_manager.fontManager.addfont(font)
plt.rcParams.update({'font.family':[font_manager.FontProperties(fname=font).get_name(),'Arial'],'font.size':12.5,'axes.unicode_minus':False,'svg.fonttype':'none'})
ui=(32/37)/(1.6e9);first,last=600,612;t0=first*ui;t1=last*ui
fig,axs=plt.subplots(4,1,figsize=(8.4,7.8),sharex=True,gridspec_kw={'height_ratios':[.75,1,1.1,1.1]})
meta=[]
for name,label,color,style,marker in [('a-base','原版：06v0 器件核心','#9a6b43','--','o'),('a-rin1wide-core03-matched','改版：03v3 器件核心','#236e76','-','^')]:
 p=BUILD/name/'cases/TT-net1.6-C200-S40';r=json.loads((p/'result.json').read_text());wave=p/'waveform.dat.gz';assert sha(wave)==r['gzip_sha256']
 v=r['metadata']['vectors'];a=np.loadtxt(wave,skiprows=1,usecols=[0,v['d0'],v['xdrv.ctrl'],v['iled_cond']]);t,d0,ctrl,current=a.T
 _,rx=dyn.cascade_pwl(t,current,200e-12,1/(2*np.pi*1e9));rx*=1e6
 keep=(t>=t0)&(t<=t1);x=(t[keep]-t0)*1e9
 for ax,y in zip(axs,[d0,ctrl,current*1e6,rx]):ax.plot(x,y[keep],style,color=color,lw=1.7,label=label)
 delay=r['analysis']['full_receiver']['delay_ps']*1e-12
 indices=np.arange(first-4,last+1);sample_t=indices*ui+delay;valid=(sample_t>=t0)&(sample_t<=t1)
 axs[3].plot((sample_t[valid]-t0)*1e9,np.interp(sample_t[valid],t,rx),marker,ls='none',color=color,ms=4.5)
 meta.append({'candidate':name,'result_sha256':sha(p/'result.json'),'waveform_gzip_sha256':r['gzip_sha256'],'waveform_raw_sha256':r['raw_sha256'],'source_case':str(p.relative_to(ROOT)),'training_selected_sample_delay_ps':delay*1e12,'shown_native_samples':int(keep.sum())})
for ax in axs:
 ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.16)
 for bit in range(first,last+1):ax.axvline((bit*ui-t0)*1e9,color='#bec9cb',lw=.65,alpha=.55,zorder=0)
 ax.set_xlim(0,(t1-t0)*1e9)
axs[0].set(ylim=(-.2,4.15),yticks=[0,3.3],ylabel='D0 / V')
st=json.loads((BUILD/'a-base/stimulus.json').read_text())
for bit in range(first,last):axs[0].text(((bit+.5)*ui-t0)*1e9,3.75,str(st['bits'][bit]),ha='center',fontsize=11)
axs[1].set(ylim=(-.25,3.65),yticks=[0,1.65,3.3],ylabel='CTRL / V')
axs[2].set(ylim=(0,145),yticks=[0,25,100,140],ylabel='LED 导通\n电流 / µA')
for target in [25,100]:axs[2].axhline(target,color='#9ca9aa',lw=.8,ls=':')
axs[3].set(ylim=(10,115),yticks=[25,62.5,100],ylabel='RX 等效电流\n/ µAeq',xlabel='距同一窗口起点的时间 / ns')
axs[3].axhline(62.5,color='#a75f5c',ls=':',lw=1)
axs[0].legend(ncol=2,frameon=False,loc='upper center',bbox_to_anchor=(.5,1.65),fontsize=12)
fig.suptitle('A：同一输入、同一物理时间轴下的逐级响应',fontsize=16,y=.985)
fig.text(.06,.035,'净 1.6 Gb/s，两者 VDD 均为 3.3 V；200 fF / 200 ps / 1 GHz RX。\n输入第 600–611 位，t0 = 324.324 ns；波形未平移或缩放时间。\n末行标记来自各自训练段相位；通过/失败依据全部 4,096 个验证位。',fontsize=10.5,ha='left',va='bottom')
fig.subplots_adjust(left=.145,right=.98,top=.855,bottom=.19,hspace=.22)
OUT.mkdir(parents=True,exist_ok=True)
fig.savefig(OUT/'a-waveforms.png',dpi=200);fig.savefig(OUT/'a-waveforms.svg');plt.close(fig)
meta={'scope':'Native time axis, common display origin only, no independent time shift or waveform rescaling. Plot window is not claimed to contain worst-case margin.',
 'net_Gbps':1.6,'window_input_bits':[first,last],'common_origin_s':t0,'end_s':t1,'optical_tau_ps':200,'receiver_GHz':1,
 'sampling_markers':'Each circuit uses its own training-only selected delay; points are interpolated on that native RX time grid, not aligned by validation labels.',
 'sources':meta,'script_path':str(Path(__file__).relative_to(ROOT)),'script_sha256':sha(Path(__file__))}
(EV/'a-waveform-figure.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
print(OUT/'a-waveforms.png')
