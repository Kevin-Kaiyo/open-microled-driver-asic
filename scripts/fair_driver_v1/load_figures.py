#!/usr/bin/env python3
"""Trace-bound diagnostic plots, not full-frame architecture qualification."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import run as e

def main():
 root=e.ROOT;work=e.BUILD/'c-transition-probe/run-03';meta=json.loads((work/'identity.json').read_text());v=meta['vectors'];st=json.loads((work/'diagnostic-stimulus.json').read_text());r=json.loads((work/'result.json').read_text());a=np.loadtxt(work/'waveform.dat.gz',skiprows=1);t=a[:,0];cols=lambda n:a[:,v[n]];folder=root/'docs/research/fair-driver-comparison-20261025/figures'
 font=root/'build/fair-driver-v1/report-font/NotoSansCJKsc-Regular.otf';font_manager.fontManager.addfont(str(font));fp=font_manager.FontProperties(fname=str(font));plt.rcParams.update({'font.family':fp.get_name(),'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.16,'svg.fonttype':'none'})
 save=lambda fig,name:[fig.savefig(folder/f'{name}.{x}',dpi=150,bbox_inches='tight') for x in ['svg','png']]
 event=next(x for x in st['events'] if (x['from'],x['to'])==(3,0));at=event['transition_symbol']*st['symbol_UI_s'];x=(t-at)*1e9;inside=(x>=-.5)&(x<=6);xx=x[inside];delay=json.loads((e.BUILD/'matched-r2/cases/RX-TT-C-0.5G/result.json').read_text())['metrics']['receiver']['sampling']['delay_s']*1e9
 rx=e.module(e.BUILD/'matched-r2/inputs/receiver.py','load_fig_rx');opt,filt=rx.filter_trace(t,cols('iled_cond'))
 fig,axs=plt.subplots(3,1,figsize=(10.6,9),sharex=True)
 for n,l,c in [('d1','D1（数据）','#687d87'),('xdrv.gp1','GP1','#377eb8'),('xdrv.gp2','GP2','#168780'),('xdrv.gp3','GP3','#aa6b3b')]:axs[0].plot(xx,cols(n)[inside],label=l,c=c,lw=1.5)
 axs[0].axhline(1.65,c='grey',ls=':',lw=.7);axs[0].set(ylabel='栅极/数据电压 / V',title='C：3→0（Gray10→00，仅D1变化），4symbol保持型短诊断');axs[0].legend(ncol=4,fontsize=9)
 for y,l,c in [(cols('sink_package'),'实际sink：i(LPKG)','#203440'),(cols('iled_cond'),'LED导通：i(VSENSE)','#168780'),(filt,'共同接收代理','#aa6b3b')]:axs[1].plot(xx,y[inside]*1e6,label=l,c=c,lw=1.6)
 calc=json.loads((e.BUILD/'load-only-step.json').read_text());curve=np.array(calc['time_current_A']);ci=np.linspace(0,6e-9,500);axs[1].plot(ci*1e9,np.interp(ci,curve[:,0],curve[:,1])*1e6,ls='--',c='#377eb8',label='仅负载解析：理想sink立刻100→25µA')
 axs[1].axhline(25,c='grey',ls=':');axs[1].axhline(30,c='#aa6b3b',ls='--',lw=.8);axs[1].text(5.6,31,'30µA：最低眼7.5µA余量对应上界',ha='right',fontsize=8);axs[1].set(ylabel='电流 / µA');axs[1].legend(fontsize=9,loc='upper right')
 diff=(cols('sink_package')-cols('iled_cond'))*1e6;axs[2].plot(xx,diff[inside],c='#377eb8',label='由KCL推算 I_C = I_sink − I_LED');axs[2].axhline(0,c='grey',ls=':');axs[2].set(ylabel='电容支路电流 / µA',xlabel='距输入跳变的时间 / ns');axs[2].legend(fontsize=9)
 for ax in axs:ax.axvline(delay,c='#ad5145',ls='--',lw=1);ax.set_xlim(-.5,6)
 axs[2].annotate(f'诊断观测 {delay:.3f}ns（v1延迟）',xy=(delay,-6),xytext=(4.2,-36),arrowprops={'arrowstyle':'->','color':'#ad5145'},fontsize=9)
 fig.tight_layout();save(fig,'c-current-tail');plt.close(fig)
 # Body voltage observation, not extrapolated reliability/current qualification.
 fig,axs=plt.subplots(1,3,figsize=(12,3.8))
 probes=[((0,2),'xdrv.p_or',True,'P_OR − VDD（PMOS体结）'),((2,0),'xdrv.n_or',False,'N_OR − VSS（NMOS体结）'),((3,0),'xdrv.n_and',False,'N_AND − VSS（NMOS体结）')]
 for ax,(transition,node,relative_vdd,title) in zip(axs,probes):
  ev=next(z for z in st['events'] if (z['from'],z['to'])==transition);x=(t-ev['transition_symbol']*st['symbol_UI_s'])*1e9;sel=(x>=-.3)&(x<=1.5);y=cols(node)-(cols('vdd') if relative_vdd else 0);ax.plot(x[sel],y[sel],c='#377eb8');ax.axhline(0,c='grey',ls='--',lw=.7);ax.fill_between(x[sel],0,y[sel],where=(y[sel]>0 if relative_vdd else y[sel]<0),color='#b26454',alpha=.3);ax.set(title=f'{transition[0]}→{transition[1]} | {title}',xlabel='距输入跳变 / ns',ylabel='节点相对体端电压 / V')
 fig.tight_layout();save(fig,'c-body-forward');plt.close(fig)
 source=Path(__file__);source_hash=e.sha(source);snapshot=e.BUILD/('load-plot-source-'+source_hash+'.py');snapshot.write_bytes(source.read_bytes())
 e.emit(root/'evidence/fair-driver-v1/load-diagnostic-figures.json',{'plotter_sha256':source_hash,'plotter_source_snapshot':str(snapshot.relative_to(root)),'font_sha256':e.sha(font),'source_work':str(work.relative_to(root)),'identity_sha256':e.sha(work/'identity.json'),'result_sha256':e.sha(work/'result.json'),'raw_gzip_sha256':e.sha(work/'waveform.dat.gz'),'full_frame_source':'matched-r2 TT C0.5G frozen sampling delay only; held4symbol test is a distinct diagnostic','frozen_sampling_delay_ns':delay,'figures':{p.name:e.sha(p) for name in ['c-current-tail','c-body-forward'] for p in folder.glob(name+'.*')},'limits':'Plots use native diagnostic values. HalfVDD gate crossing is not measured full channel shutoff. KCL current and C*dV integrated agreement support the load-current tail; no fabricated optical or reliability proof.'})
 print('Native C current-tail and body-voltage figures generated')
if __name__=='__main__':main()
