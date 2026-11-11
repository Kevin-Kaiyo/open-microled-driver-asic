#!/usr/bin/env python3
"""Native-node diagnostics for rejected VCSEL methods; no time shifting."""
from pathlib import Path
import gzip,hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[3];EV=ROOT/'evidence/driver-methods-20261111'
CASES={'baseline':ROOT/'build/ab-improvement-20261111/VCSEL/vc-atten50-steer20/net7.2-edge20-s40','ff20':ROOT/'build/driver-methods-20261111/VCSEL/vc-ff20/net7.2-s40','dr65':ROOT/'build/driver-methods-20261111/VCSEL/vc-dr65/net7.2-s40'}
NODES=['v(xdrv.di)','v(xdrv.dbi)','v(xdrv.np)','v(xdrv.nn)','v(xdrv.gp)','v(xdrv.gn)','v(xdrv.dr)','v(xdrv.vx)','v(jmon)']
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def crosses(t,y):
 k=np.flatnonzero((y[1:]>=0)!=(y[:-1]>=0));return t[k]-y[k]*(t[k+1]-t[k])/(y[k+1]-y[k])
def main():
 traces={};stats={}
 for name,p in CASES.items():
  m=json.loads((p/'manifest.json').read_text());r=json.loads((p/'result.json').read_text());ui=m['UI_ps']*1e-12
  wave=p/'waveform.dat.gz';assert sha(wave)==r['waveform']['sha256']
  with gzip.open(wave,'rt') as f:raw=np.loadtxt(f,skiprows=1,usecols=[0]+[m['expressions'].index(n)+1 for n in NODES])
  t=raw[:,0];nodes=dict(zip(NODES,raw[:,1:].T));g=nodes['v(xdrv.gp)']-nodes['v(xdrv.gn)'];d=nodes['v(xdrv.di)']-nodes['v(xdrv.dbi)'];edgeg=crosses(t,g);edged=crosses(t,d)
  # Broad interior excludes both frame start and pipeline tail; counts report only, no inferred bitwise timing map.
  eg=edgeg[(edgeg>=576*ui)&(edgeg<4672*ui)];ed=edged[(edged>=576*ui)&(edged<4672*ui)]
  window=(t>=576*ui)&(t<=584*ui);traces[name]={'time_ns_from_t0':((t[window]-576*ui)*1e9).tolist(),**{n:v[window].tolist() for n,v in nodes.items()}}
  stats[name]={'source_case':str(p.relative_to(ROOT)),'waveform_gzip_sha256':sha(wave),'waveform_raw_sha256':r['waveform']['raw_sha256'],'gate_diff_zero_crossings_in_576_4672UI':len(eg),'input_diff_zero_crossings_in_same_time_window':len(ed),'gate_crossings_spacing_min_UI':float(np.min(np.diff(eg))/ui),'gate_crossing_pairs_less_than_0p25UI':int(np.sum(np.diff(eg)<.25*ui)),'scope':'Same physical time interval; counts near window edges may differ due propagation delay. Extra close-pairs diagnose narrow crossings but no global equality assertion.'}
  for node in ['v(xdrv.di)','v(xdrv.np)','v(xdrv.gp)','v(xdrv.gn)']:stats[name][node+'_range_V']=[float(nodes[node].min()),float(nodes[node].max())]
 font='/System/Library/Fonts/Hiragino Sans GB.ttc';font_manager.fontManager.addfont(font);plt.rcParams.update({'font.family':[font_manager.FontProperties(fname=font).get_name(),'Arial'],'font.size':11,'axes.unicode_minus':False,'svg.fonttype':'none'})
 for variant,desc in [('ff20','20 fF 前馈'),('dr65','降低 DR 目标')]:
  fig,axs=plt.subplots(5,1,figsize=(11,10.4),sharex=True);fig.subplots_adjust(left=.10,right=.98,top=.91,bottom=.19,hspace=.22)
  for key,label,color in [('baseline','原版','#526579'),(variant,desc,'#b35f3f')]:
   s=traces[key];x=s['time_ns_from_t0']
   for ax,node,ylab,scale in zip(axs,['v(xdrv.di)','v(xdrv.np)','v(xdrv.gp)','v(xdrv.gn)','v(jmon)'],['DI / V','NP / V','GP / V','GN / V','VCSEL 电流 / mA'],[1,1,1,1,1000]):
    ax.plot(x,np.array(s[node])*scale,label=label,color=color,lw=1.35,alpha=.9);ax.set_ylabel(ylab);ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
  axs[0].legend(loc='upper right',frameon=False,ncol=2);axs[-1].set_xlabel('原生瞬态时间 − t0 / ns')
  fig.suptitle(f'VCSEL：{desc}与原版的逐级响应（同一时间轴）',fontsize=16,y=.965)
  fig.text(.10,.035,'净 7.2 Gb/s；20 ps 输入；3/7 mA；150 fF；5 GHz RX。t0 = '+f'{576*ui*1e9:.6f} ns。\nDI → 两级 CMOS 反相器（中间节点 NP）→ GP；互补支路输出 GN。\n波形没有平移、重定时或幅度归一化；完整通过/失败依据 4,096 个验证位。',fontsize=10)
  fig.savefig(EV/f'vcsel-{variant}-native.png',dpi=150);fig.savefig(EV/f'vcsel-{variant}-native.svg');plt.close(fig)
 out={'schema':'vcsel-method-native-diagnostics-v1','window_UI':[576,584],'net_Gbps':7.2,'t0_s':576*ui,'stats':stats,'native_excerpt':traces,'scope':'Saved native data only; no further solve. NP is first CMOS inverter output, GP/GN second-stage outputs. Gate difference crossings do not alone establish bit errors.'}
 (EV/'vcsel-native-diagnostics.json').write_text(json.dumps(out,indent=2)+'\n')
 short={}
 for name,s in traces.items():
  t=np.asarray(s['time_ns_from_t0']);early=(t>=0)&(t<.08);trough=(t>=.12)&(t<.30);g=np.asarray(s['v(xdrv.gp)'])[early];k=np.argmin(g)
  short[name]={'GP_min_in_0_to_80ps_V':float(g.min()),'GP_max_after_min_before80ps_V':float(g[k:].max()),'GP_min_in_120_to_300ps_V':float(np.asarray(s['v(xdrv.gp)'])[trough].min()),'LED_min_in_120_to_300ps_mA':float(1e3*np.asarray(s['v(jmon)'])[trough].min())}
 (EV/'vcsel-short-window-values.json').write_text(json.dumps(short,indent=2)+'\n');print(json.dumps(stats,indent=2))
if __name__=='__main__':main()
