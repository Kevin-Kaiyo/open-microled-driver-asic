#!/usr/bin/env python3
"""Display-only figures from compact previews; scoring uses complete native traces."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[3];BUILD=ROOT/'build/driver-interface-20261115/MicroLED';ASSETS=ROOT/'docs/research/driver-interface-20261115/assets'
plt.rcParams.update({'font.family':['Hiragino Sans GB','DejaVu Sans'],'font.size':13,'axes.unicode_minus':False,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'figure.facecolor':'white','axes.facecolor':'#fbfcfc'})
colors={'baseline':'#777f89','protected_v2':'#d17845','protected_v3':'#a34f70','protected_v5':'#9655a4','final':'#137d83'}
def read(p):return json.loads(p.read_text())
def case(route,var,kind='fault',frames=2):return BUILD/f'{route}-{var}'/f'{kind}-f{frames}-net1.6-s40'
def load(p):return read(p/'result.json'),np.load(p/'preview.npz')
def save(fig,name,refs):
 ASSETS.mkdir(parents=True,exist_ok=True);fig.savefig(ASSETS/(name+'.svg'),bbox_inches='tight');fig.savefig(ASSETS/(name+'.png'),dpi=165,bbox_inches='tight')
 panel_names={'micro-continuous-comparison':['energy','margin'],'micro-protection-A-waveforms':['overview','body','current','gate'],'micro-protection-B-waveforms':['overview','ready','recovery','assert']}
 # Figure-wide captions do not belong inside cropped single-panel exports.
 # Hide them rather than letting expanded panel bounds cut across a partial line.
 for artist in fig.texts:artist.set_visible(False)
 fig.canvas.draw()
 for ax,suffix in zip(fig.axes,panel_names.get(name,[])):
  bbox=ax.get_tightbbox(fig.canvas.get_renderer()).expanded(1.02,1.10).transformed(fig.dpi_scale_trans.inverted())
  fig.savefig(ASSETS/(name+'-'+suffix+'.svg'),bbox_inches=bbox);fig.savefig(ASSETS/(name+'-'+suffix+'.png'),dpi=165,bbox_inches=bbox)
 plt.close(fig)
 rows=[]
 for p in refs:
  q=p/'result.json';rows.append({'case':str(p.relative_to(ROOT)),'result_sha256':hashlib.sha256(q.read_bytes()).hexdigest(),'preview_sha256':hashlib.sha256((p/'preview.npz').read_bytes()).hexdigest() if (p/'preview.npz').exists() else None})
 (ASSETS/(name+'.source.json')).write_text(json.dumps({'sources':rows,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'method':'Figures use derived native-window previews. Full results use complete original native-time data; no figure interpolation is used for acceptance.'},ensure_ascii=False,indent=2)+'\n')
def energy(A,B):
 fig,axs=plt.subplots(1,2,figsize=(13,4.9));refs=[]
 for route,var,c in [('A',A,'#126d86'),('B',B,'#b46838')]:
  for variant,style,label in [('baseline','--',route+' 基线'),(var,'-',route+' 修正版')]:
   p=case(route,variant,'continuous',4)
   if not (p/'result.json').exists():continue
   r=read(p/'result.json');refs.append(p);frames=r['frames'];x=[f['frame'] for f in frames]
   axs[0].plot(x,[f['energy_pJ_per_attempted_payload_bit']['positive'] for f in frames],style+'o',color=c,label=label)
   axs[1].plot(x,[f['first_frame_phase_receiver']['timing_UI'] for f in frames],style+'o',color=c,label=label)
 axs[0].set(ylabel='七源 E+ / 尝试数据位 (pJ/bit)',xlabel='连续重复帧',xticks=[1,2,3,4],title='初始工作点储能会影响首帧源端能量');axs[0].legend(fontsize=11.5,ncol=2,loc='center',bbox_to_anchor=(.5,.27))
 axs[1].axhline(.37,color='#b44',lw=1.1,label='0.37 UI 研究门槛');axs[1].set(ylabel='单侧时间余量 / line UI',xlabel='连续重复帧',xticks=[1,2,3,4],title='固定第一帧训练相位，观察后续三帧');axs[1].legend(fontsize=11,ncol=2,loc='center',bbox_to_anchor=(.53,.49))
 fig.suptitle('净 1.6 Gb/s · 4 帧 / 10.24 us · 完整连续波形仅滤波一次',fontsize=16)
 fig.text(.08,-.02,'相同 20 um / 200 fF / 200 ps 光学代理 / 1 GHz 接收条件。有限电气周期筛选不等于热稳态或 BER 资格。',fontsize=10)
 fig.tight_layout();save(fig,'micro-continuous-comparison',refs)
def fault_A(A):
 rows=[('baseline','旧基线'),('protected_v2','v2 直接重接'),(A,'修正版慢开')];data=[];refs=[]
 for var,label in rows:
  p=case('A',var);r,a=load(p);data.append((var,label,r,a));refs.append(p)
 fig,axs=plt.subplots(4,1,figsize=(10,13));on=1.28e-6;off=.64e-6
 for var,label,r,a in data:
  c=colors.get(var,colors['final']);axs[0].plot(a['time_s']*1e6,a['iled_cond']*1e6,color=c,lw=.8,label=label)
 for var,label,r,a in data[1:]:
  c=colors.get(var,colors['final']);t=(a['time_s']-on)*1e9;mask=(t>=-5)&(t<=25)
  axs[1].plot(t[mask],(a['out'][mask]-a['xdrv.vh'][mask]),color=c,label=label+'：OUT−VH')
  axs[2].plot(t[mask],a['icled_derivative_A'][mask]*1e3,color=c,label=label+'：CLED dVAK/dt')
  axs[2].plot(t[mask],a['ipkg'][mask]*1e3,color=c,ls='--',lw=.8,label=label+'：封装支路')
  mask=(t>=-5)&(t<=65)
  gate='iso_p' if 'iso_p' in a else 'iso_g';axs[3].plot(t[mask],a[gate][mask],color=c,label=label+'：PISO 栅极');axs[3].plot(t[mask],a['led_a'][mask],color=c,ls='--',label=label+'：LED 阳极')
 axs[0].axvspan(off*1e6,on*1e6,color='#cee8e6',alpha=.65);axs[0].set(ylabel='LED 导通电流 (uA)',xlabel='连续运行时间 (us)',title='外部 DATA 一直翻转；阴影为 DISABLE 高电平')
 axs[1].axhline(.3,color='#b44',ls=':',label='0.3 V 体结研究屏障');axs[1].set(ylabel='输出 PMOS 体结正偏 (V)',xlabel='相对释放保护 (ns)',title='低导通电流不代表没有体结冲击')
 axs[2].set(ylabel='支路电流 (mA)',xlabel='相对释放保护 (ns)',title='重接时的主要脉冲是位移电流；CLED 导数只是数值估计')
 axs[3].set(ylabel='节点电压 (V)',xlabel='相对释放保护 (ns)',title='实际 MOS 栅电容与电阻共同限制高侧重接斜率')
 for ax in axs:ax.legend(fontsize=11.5,ncol=2)
 fig.suptitle('A 电压驱动：关断、重接冲击与受控恢复',fontsize=17);fig.text(.08,.005,'关断域低于 0.1 uA 为未校准 I–V 延拓；图仅供显示，全部验收由完整原生数据完成。',fontsize=10)
 fig.tight_layout(rect=[0,.02,1,.98]);save(fig,'micro-protection-A-waveforms',refs)
def fault_B(B):
 rows=[('baseline','旧基线'),('protected_v2','v2'),('protected_v3','v3 仅控斜率'),(B,'当前修正版')];data=[];refs=[]
 for var,label in rows:
  p=case('B',var);r,a=load(p);data.append((var,label,r,a));refs.append(p)
 final=data[-1][3];on=1.28e-6;off=.64e-6
 fig,axs=plt.subplots(4,1,figsize=(10,13))
 for var,label,r,a in data:
  c=colors.get(var,colors['final']);axs[0].plot(a['time_s']*1e6,a['iled_cond']*1e6,color=c,lw=.7,label=label)
  if var!='baseline':
   t=(a['time_s']-on)*1e9;mask=(t>=-5)&(t<=25);axs[2].plot(t[mask],a['out'][mask],color=c,lw=.9,label=label+' OUT')
 t=(final['time_s']-on)*1e9;mask=(t>=-20)&(t<=230)
 axs[1].plot(t[mask],final['d0'][mask],color='#8795a1',lw=.65,label='外部 DATA（持续翻转）');axs[1].plot(t[mask],final['data_safe'][mask],color='#137d83',lw=.8,label='内部 DATA_SAFE');axs[1].plot(t[mask],final['ready_rc'][mask],color='#b46838',lw=1.7,label='READY_RC（开环延迟）')
 # v5 vs final is the single-parameter controlled-off comparison where available.
 p=case('B','protected_v5',frames=1)
 if (p/'preview.npz').exists():
  refs.append(p);a=np.load(p/'preview.npz');t=(a['time_s']-off)*1e9;mask=(t>=-2)&(t<=20);axs[3].plot(t[mask],a['led_a'][mask],color='#9655a4',label='v5：快关 W20')
 t=(final['time_s']-off)*1e9;mask=(t>=-2)&(t<=20);axs[3].plot(t[mask],final['led_a'][mask],color='#137d83',label='修正版：受控关断');axs[3].axhline(5.3,color='#b44',ls=':',label='5 V + 0.3 V 体结屏障参考')
 axs[0].axvspan(.64,1.28,color='#cee8e6',alpha=.6);axs[0].set(ylabel='LED 导通电流 (uA)',xlabel='时间 (us)',title='关断窗口内对外部数据继续翻转进行真实响应')
 axs[1].set(ylabel='电压 (V)',xlabel='相对释放保护 (ns)',title='先接回光源，再延迟允许内部数据；READY_RC 不是 power-good')
 axs[2].axhline(-.3,color='#b44',ls=':');axs[2].set(ylabel='OUT 电压 (V)',xlabel='相对释放保护 (ns)',title='参考源保持运行；抑制关断中的 CFF 注入与恢复负冲击')
 axs[3].set(ylabel='LED 阳极电压 (V)',xlabel='相对发出关断命令 (ns)',title='快关也会通过栅漏电容抬高阳极：需要限制关闭斜率')
 for ax in axs:ax.legend(fontsize=11.5,ncol=2)
 fig.suptitle('B 电流转向：数据门控与高侧控制需要一起验证',fontsize=17);fig.text(.08,.005,'真实 MOS 逻辑与 RC 均计能耗；关断 nA 结果仍为未校准模型延拓，不能当漏电或消光资格。',fontsize=10)
 fig.tight_layout(rect=[0,.02,1,.98]);save(fig,'micro-protection-B-waveforms',refs)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--A',default='protected_v3r');p.add_argument('--B',default='protected_v6r');args=p.parse_args();energy(args.A,args.B);fault_A(args.A);fault_B(args.B)
