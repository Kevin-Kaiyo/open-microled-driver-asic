#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[3];A=ROOT/'docs/research/driver-pvt-20261117/assets';P=ROOT/'build/driver-pvt-20261117/b/clamp5v_buffer_soft/ss_hot_low-full-s40';r=json.loads((P/'result.json').read_text());z=np.load(P/'preview.npz')
plt.rcParams.update({'font.family':['Hiragino Sans GB','DejaVu Sans'],'font.size':13,'axes.unicode_minus':False,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.17})
def save(fig,name):
 for ext in ['svg','png']:fig.savefig(A/(name+'.'+ext),dpi=165,bbox_inches='tight')
 plt.close(fig);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();(A/(name+'.source.json')).write_text(json.dumps({'case':str(P.relative_to(ROOT)),'result_sha256':sha(P/'result.json'),'preview_sha256':sha(P/'preview.npz'),'generator_sha256':sha(Path(__file__)),'scope':'Full5.12us electrical/RX evidence; figure uses display-only native subset, scoring uses complete native data.'},ensure_ascii=False,indent=2)+'\n')
fig,ax=plt.subplots(figsize=(11,4.6));ax.plot(z['time_s']*1e6,z['iled_cond']*1e6,color='#137d83',lw=.7);ax.axvspan(.64,1.28,color='#d8e9e5',alpha=.8,label='有意关断；外部DATA仍翻转');ax.axvspan(2.56,5.12,color='#eef3fa',alpha=.45,label='完整恢复帧：0观察错误');ax.set(xlabel='连续仿真时间 (us)',ylabel='LED 导通电流 (uA)',title='SS85 / 供电−5%：完整5.12us连续输入、关断与恢复');ax.legend(fontsize=10,loc='upper center',ncol=2);fig.text(.08,.01,'第一帧含有意关断625个错误；第二帧恢复后的4096位0错。不能把关断窗口错误当正常链路BER。',fontsize=10);fig.tight_layout(rect=[0,.05,1,1]);save(fig,'b-full-SS-overview')
for label,edge,limit in [('assert',.64e-6,28),('release',1.28e-6,105)]:
 t=(z['time_s']-edge)*1e9;k=(t>=-3)&(t<=limit);fig,ax=plt.subplots(figsize=(11,4.8))
 for n,name,c in [('iso_p','PISO实际栅极','#8e6b9a'),('clamp_g','XCLAMP栅极','#b36a41'),('led_a','LED阳极','#137d83'),('led_k','LED阴极','#496e97')]:ax.plot(t[k],z[n][k],label=name,color=c,lw=1.3)
 ax.set(xlabel='相对关断命令 (ns)' if label=='assert' else '相对释放保护 (ns)',ylabel='原生节点电压 (V)',title='SS全协议：RC约束实际钳位栅极，保持高侧隔离' if label=='assert' else 'SS全协议：撤钳位、缓慢重接和参考/输出恢复');ax.legend(fontsize=11,ncol=2);fig.tight_layout();save(fig,'b-full-SS-'+label)
fig,ax=plt.subplots(figsize=(11,4.8));t=(z['time_s']-1.28e-6)*1e9;k=(t>=-8)&(t<=120)
for n,label,c,lw in [('d0','外部DATA持续翻转','#9da5ae',.6),('data_safe','内部DATA_SAFE','#137d83',.9),('ready_rc','开环READY_RC','#b36a41',1.5)]:ax.plot(t[k],z[n][k],color=c,label=label,lw=lw)
ax.set(xlabel='相对释放保护 (ns)',ylabel='逻辑 / 控制电压 (V)',title='SS完整恢复：按原首帧相位验收，约81.0ns后持续满足余量');ax.legend(fontsize=11,ncol=3);fig.tight_layout();save(fig,'b-full-SS-ready')
