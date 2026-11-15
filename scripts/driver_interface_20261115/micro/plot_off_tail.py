#!/usr/bin/env python3
"""Show the final B candidate's short remaining shutdown margin; native scoring is separate."""
from pathlib import Path
import hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[3]
P=ROOT/'build/driver-interface-20261115/MicroLED/B-protected_v6r/fault-f2-net1.6-s40'
A=ROOT/'docs/research/driver-interface-20261115/assets'
plt.rcParams.update({'font.family':['Hiragino Sans GB','DejaVu Sans'],'font.size':13,'axes.unicode_minus':False,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18})
z=np.load(P/'preview.npz');t=(z['time_s']-.64e-6)*1e9;k=(t>=-1)&(t<=25)
fig,ax=plt.subplots(2,1,figsize=(10,7.4))
ax[0].semilogy(t[k],np.maximum(abs(z['iled_cond'][k])*1e6,1e-6),color='#137d83',label='LED 导通电流绝对值')
ax[0].axhline(.1,color='#b46838',ls='--',label='0.1 uA 研究筛选')
ax[0].axvline(20,color='#a34f70',ls=':',label='20 ns 守护窗口结束')
ax[0].scatter([20.000333944],[.08909743202],color='#137d83',zorder=4)
ax[0].set(ylabel='|Icond| (uA)，对数轴',xlabel='相对关断命令 (ns)',ylim=(.001,200),title='达到数值关断门槛，但只剩约 2.96 ns / 10.90 nA 名义余量')
ax[0].set_yticks([.001,.01,.1,1,10,100],labels=['0.001','0.01','0.1','1','10','100'])
ax[0].text(.98,.93,'0.1 uA 以下为未校准 I–V 延拓',transform=ax[0].transAxes,ha='right',fontsize=11,color='#535e68')
ax[1].plot(t[k],z['led_a'][k],color='#137d83',label='LED_A')
ax[1].plot(t[k],z['led_k'][k],color='#b46838',label='LED_K')
ax[1].plot(t[k],z['led_a'][k]-z['led_k'][k],color='#365b89',label='VAK')
ax[1].plot(t[k],z['disable'][k]-z['led_k'][k],color='#a34f70',ls='--',label='XCLAMP 有效 VGS')
ax[1].axvline(20,color='#a34f70',ls=':')
ax[1].set(ylabel='节点 / 器件电压 (V)',xlabel='相对关断命令 (ns)',title='20 ns 处 VAK 仍约 2.153 V；命令 3.3 V 不等于钳位 VGS')
for a in ax:a.legend(fontsize=11,ncol=2)
fig.tight_layout()
name='micro-protection-B-offtail'
for ext in ['svg','png']:fig.savefig(A/f'{name}.{ext}',dpi=165,bbox_inches='tight')
fig.canvas.draw()
for a,suffix in zip(ax,['current','voltage']):
 b=a.get_tightbbox(fig.canvas.get_renderer()).expanded(1.02,1.10).transformed(fig.dpi_scale_trans.inverted())
 for ext in ['svg','png']:fig.savefig(A/f'{name}-{suffix}.{ext}',dpi=165,bbox_inches=b)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(A/f'{name}.source.json').write_text(json.dumps({'case':str(P.relative_to(ROOT)),'result_sha256':sha(P/'result.json'),'preview_sha256':sha(P/'preview.npz'),'native_point_record':'evidence/driver-interface-20261115/micro-off-tail-B.json','generator_sha256':sha(Path(__file__)),'limitations':'Display uses dense native preview. Current below 0.1 uA is uncalibrated linear I-V extension. VTH/channel current were not exported; body effect is not proved the unique cause.'},ensure_ascii=False,indent=2)+'\n')
