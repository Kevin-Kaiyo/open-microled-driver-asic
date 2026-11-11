#!/usr/bin/env python3
"""Selected matched7.2G receiver/native-derived traces, no hidden time alignment."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[3];EV=ROOT/'evidence/driver-methods-20261111'
def main():
 cases=[('两级原版','#607285',ROOT/'build/ab-improvement-20261111/VCSEL/vc-atten50-steer20/net7.2-edge20-s40'),('单级 / 50 Ω','#b67c3e',ROOT/'build/driver-methods-20261111/VCSEL/vc-single/net7.2-s40'),('单级 / 100 Ω','#207d76',ROOT/'build/driver-methods-20261111/VCSEL/vc-single-r100/net7.2-s40')]
 final=ROOT/'build/driver-methods-20261111/VCSEL/vc-single-r150/net7.2-s40'
 if (final/'excerpt.json').exists():cases[-1]=('单级 / 150 Ω','#207d76',final)
 f='/System/Library/Fonts/Hiragino Sans GB.ttc';font_manager.fontManager.addfont(f);plt.rcParams.update({'font.family':[font_manager.FontProperties(fname=f).get_name(),'Arial'],'font.size':11,'axes.unicode_minus':False,'svg.fonttype':'none'})
 fig,axs=plt.subplots(4,1,figsize=(11,9.4),sharex=True);fig.subplots_adjust(left=.11,right=.98,top=.9,bottom=.19,hspace=.24)
 for label,color,p in cases:
  r=json.loads((p/'excerpt.json').read_text());m=json.loads((p/'manifest.json').read_text());t=np.asarray(r['time_UI'])*m['UI_ps']/1e3;mask=t<=.96
  for ax,key,ylab in zip(axs,['pin_V','gate_V','i_mA','actual_graph_5GHzRX'],['DI − DBI / V','GP − GN / V','导电电流 / mA','接收值 / µAeq']):
   ax.plot(t[mask],np.asarray(r[key])[mask],label=label,color=color,lw=1.3);ax.set_ylabel(ylab);ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
 axs[0].legend(frameon=False,ncol=3,loc='upper right');axs[2].axhline(7.5,ls='--',color='#a24d35',lw=.8);axs[2].text(.95,7.52,'模型上限 7.5 mA',ha='right',va='bottom',fontsize=9)
 axs[3].axhline(62.5,ls=':',color='#777',lw=.8);axs[-1].set_xlabel('统一物理时间 − t0 / ns');fig.suptitle('VCSEL：减少一级缓冲改善脉冲，阻尼控制尖峰',fontsize=16,y=.96)
 fig.text(.11,.035,'净 7.2 Gb/s，t0 = 69.189189 ns；相同 3/7 mA 目标、光源模型与 5 GHz RX。\n前三级来自原生 SPICE 波形，在 128 点/UI 分析网格插值；末级为固定光学/RX 模型响应。\n未平移时轴；GP − GN 是两门极差值，不是单个 MOS 的端间应力。阈值判断使用各自训练相位。',fontsize=10)
 fig.savefig(EV/'vcsel-single-stage-comparison.png',dpi=150);fig.savefig(EV/'vcsel-single-stage-comparison.svg');plt.close(fig)
if __name__=='__main__':main()
