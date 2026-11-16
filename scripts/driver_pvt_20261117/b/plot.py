#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[3];B=ROOT/'build/driver-pvt-20261117/b';A=ROOT/'docs/research/driver-pvt-20261117/assets'
plt.rcParams.update({'font.family':['Hiragino Sans GB','DejaVu Sans'],'font.size':12,'axes.unicode_minus':False,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.16})
def case(v,g,mode='assert'):return B/v/(g+'-'+mode+'-s40')
def data(p):return np.load(p/'preview.npz')
def save(f,name,refs):
 for ext in ['png','svg']:f.savefig(A/(name+'.'+ext),bbox_inches='tight',dpi=165)
 plt.close(f);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();(A/(name+'.source.json')).write_text(json.dumps({'generator_sha256':sha(Path(__file__)),'cases':[{'path':str(p.relative_to(ROOT)),'result_sha256':sha(p/'result.json')} for p in refs],'scope':'Original quantitative plot from native-derived diagnostics or DC. Short windows are not RX/full-protocol qualification.'},ensure_ascii=False,indent=2)+'\n')
grid=['tt','tt_cold','tt_hot','tt_low','tt_high','ss_hot_low','ff_cold_high','sf_hot_low','fs_cold_high'];labels=['TT27','TT−40','TT85','TT低压','TT高压','SS热低','FF冷高','SF热低','FS冷高'];x=np.arange(9)
for lev in [0,1]:
 fig,ax=plt.subplots(figsize=(11,5));refs=[]
 candidates=[('baseline','原单尾管','#b36a41','o-'),('unit_tail','3只同单位管','#9a9a9a','s:'),('unit_long','同单位管 W4/L2','#568fa8','^--'),('unit_long_trim','长单位管 + 固定校准','#137d83','o-')] if lev else [('baseline','原设计','#b36a41','o-'),('unit_long_trim','长单位管 + 固定校准','#137d83','o-')]
 for v,label,c,style in candidates:
  paths=[B/v/(g+f'-DC-L{lev}') for g in grid];refs+=paths;y=[json.loads((p/'result.json').read_text())['current_uA'] for p in paths];ax.plot(x,y,style,color=c,label=label,lw=1.6)
 target=25 if lev==0 else 100;ax.axhspan(target*.99,target*1.01,color='#dcebe8',alpha=.65,label='目标 ±1% 筛选带');ax.axhline(target,color='#536976',lw=.8);ax.set_xticks(x,labels);ax.set(ylabel='恒定输入时 LED 导通电流 (uA)',title=f'{target} uA DC 档：单位管几何与固定校准的作用')
 ax.legend(fontsize=10,ncol=2,loc='best');fig.text(.07,.01,'仅 DC；长单位管会改变电容和面积。固定 VREF / 理想参考电阻；不等于全温度、失配或高速通过。',fontsize=10);fig.tight_layout(rect=[0,.05,1,1]);save(fig,'b-dc-'+str(target),refs)
# Common, actual short PRBS phase; direct5V is retained as a failed transition candidate.
fig,ax=plt.subplots(figsize=(10,4.8));refs=[]
for v,label,c in [('baseline','原39MOS','#737e87'),('clamp5v','直接5V钳位','#bd7247'),('clamp5v_buffer','延迟钳位 + 缓冲（W4复位）','#137d83')]:
 p=case(v,'ss_hot_low');z=data(p);t=(z['time_s']-32e-9)*1e9;k=(t>=-2)&(t<=26);ax.semilogy(t[k],np.maximum(abs(z['iled_cond'][k])*1e6,1e-6),color=c,label=label);refs.append(p)
ax.axvline(20,color='#a34f70',ls=':',label='20 ns 研究截止');ax.axhline(.1,color='#a34f70',ls='--');ax.set(ylabel='|Icond| (uA)，对数轴',xlabel='相对发出关断命令 (ns)',title='SS85 / 供电−5%：提高驱动减少关断尾段，但必须限制接入冲击',ylim=(.003,200));ax.set_yticks([.01,.1,1,10,100],labels=['0.01','0.1','1','10','100']);ax.legend(fontsize=10);fig.text(.09,.01,'96 ns 局部 OP 初始化诊断；0.1 uA 以下为未校准 I–V 延拓。尚不代表恢复过程或光学消光通过。',fontsize=10);fig.tight_layout(rect=[0,.05,1,1]);save(fig,'b-shutdown-ss',refs)
fig,ax=plt.subplots(figsize=(10,4.8));refs=[]
for v,label,c in [('clamp5v','直接5V钳位','#bd7247'),('clamp5v_delayed','钳位门100k + 复位','#986781'),('clamp5v_delay200','钳位门200k + 复位','#137d83')]:
 p=case(v,'ff_cold_high');z=data(p);t=(z['time_s']-32e-9)*1e9;k=(t>=-1)&(t<=16);ax.plot(t[k],z['out'][k],color=c,label=label);refs.append(p)
ax.axhline(3.63,color='#a34f70',ls=':',label='3.63 V 端差筛选');ax.set(ylabel='OUT / XBASE 漏极电压 (V)',xlabel='相对发出关断命令 (ns)',title='FF−40 / 供电+5%：过强钳位把高侧电位传到阴极');ax.legend(fontsize=10);fig.tight_layout();save(fig,'b-clamp-delay-tradeoff',refs)
for label,lo,hi,ylim in [('negative',-2,7,(-.4,.5)),('positive',7,23,(-.1,4.0))]:
 fig,ax=plt.subplots(figsize=(10,4.8));refs=[]
 for v,name,c in [('clamp5v_buffer','W4 快撤','#bd7247'),('clamp5v_buffer_soft','W0.5 慢撤','#137d83')]:
  p=case(v,'ff_cold_high','release');z=data(p);t=(z['time_s']-32e-9)*1e9;k=(t>=lo)&(t<=hi);ax.plot(t[k],z['out'][k],color=c,label=name);refs.append(p)
 ax.axhline(-.3 if label=='negative' else 3.63,color='#a34f70',ls=':',label='−0.3 V 对应体结筛选' if label=='negative' else '3.63 V 端差筛选');ax.set(ylabel='OUT 电压 (V)',xlabel='相对释放关断 (ns)',ylim=ylim,title='FF恢复：慢撤减轻负冲；高侧重新充电的正峰仍未关闭' if label=='positive' else 'FF恢复：减小钳位复位管，降低栅电荷撤除的负冲');ax.legend(fontsize=10);fig.tight_layout();save(fig,'b-release-'+label,refs)
