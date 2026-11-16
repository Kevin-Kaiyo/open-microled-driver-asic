#!/usr/bin/env python3
"""Derived PVT figures; all plotted values refer to exact native result hashes."""
from pathlib import Path
import importlib.util,json,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.dont_write_bytecode=True
import run
OUT=run.ROOT/'docs/research/driver-pvt-20261117/assets';OUT.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':['Arial Unicode MS'],'font.size':14,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','axes.unicode_minus':False})
COL={'frozen':'#8a6a50','cmd-r100':'#8b95a2','cmd-r330':'#158375','cmd-r470':'#336cb1'}
NAMES={'frozen':'原有限 CMOS','cmd-r100':'命令栅串100Ω','cmd-r330':'命令栅串330Ω','cmd-r470':'命令栅串470Ω'}
COL['cmd-r330-atten75']='#336cb1';NAMES['cmd-r330-atten75']='命令330Ω + 内部75Ω'
def finish(fig,name):
 for ext in ['svg','png']:fig.savefig(OUT/f'vcsel-{name}.{ext}',bbox_inches='tight',dpi=170)
 plt.close(fig)
def summarize():
 rows=[]
 receipt=run.EV/'nominal-reuse.json'
 if receipt.exists():
  z=run.read(receipt);p=run.ROOT/z['case'];a=run.read(p/'analysis.json');r=run.read(p/'result.json')
  assert run.sha(p/'analysis.json')==z['analysis_sha256']
  rows.append(dict(case=z['case'],reused_nominal=True,reuse_receipt_sha256=run.sha(receipt),config=dict(variant='frozen',corner='tt25',net_Gbps=8.8,steps_per_UI=40,kind='full'),analysis_sha256=z['analysis_sha256'],manifest_sha256=z['manifest_sha256'],combined_pass=a['combined_screen_pass'],rx=a['pathways']['actual_graph_5GHzRX'],energy=a['source_energy_pJ_per_attempted_net_bit'],energy_by_source=a['energy_by_source_pJ_per_attempted_net_bit'],terminal_peak=a['observed']['terminal_peak'],max_body_forward_V=a['observed']['max_body_forward_V'],I_range_mA=a['observed']['electrical_current_range_mA'],DC_pass=True))
 for p in sorted(run.BUILD.glob('*/*/*/analysis.json')):
  a=run.read(p);m=run.read(p.parent/'manifest.json');r=run.read(p.parent/'result.json');q=a['pathways']['actual_graph_5GHzRX']
  rows.append(dict(case=str(p.parent.relative_to(run.ROOT)),config=m['pvt_config'],analysis_sha256=run.sha(p),manifest_sha256=run.sha(p.parent/'manifest.json'),combined_pass=a['combined_screen_pass'],rx=q,energy=a['source_energy_pJ_per_attempted_net_bit'],energy_by_source=a['energy_by_source_pJ_per_attempted_net_bit'],terminal_peak=r['terminal_peak'],max_body_forward_V=r['max_body_forward_V'],I_range_mA=[r['current_min_mA'],r['current_max_mA']],DC_pass=a['DC_screen_pass']))
 return rows

def grid():
 fig,axs=plt.subplots(2,1,figsize=(12,7),sharex=True);x=np.arange(len(run.GRID));labels=['TT25','TT−40','TT85','TT低压','TT高压','SS热低压','FF冷高压','SF热低压','FS冷高压']
 for variant in ['frozen','cmd-r100','cmd-r330','cmd-r330-atten75']:
  xx=[];body=[];term=[]
  for i,c in enumerate(run.GRID):
   p=run.BUILD/variant/c/'short-net8.8-s40/result.json'
   if p.exists():
    r=run.read(p);xx.append(i);body.append(r['max_body_forward_V']);term.append(r['terminal_peak']['value_V'])
  if xx:
   axs[0].plot(xx,body,'o-',label=NAMES[variant],color=COL[variant]);axs[1].plot(xx,term,'o-',color=COL[variant])
 for ax,lim in zip(axs,[.3,3.63]):ax.axhline(lim,color='#b34339',ls='--');ax.grid(alpha=.15)
 axs[0].set_ylabel('最坏体结正偏 / V');axs[1].set_ylabel('最坏 |端口电压| / V');axs[1].set_xticks(x,labels,rotation=20);axs[0].legend(fontsize=12,ncol=2)
 fig.suptitle('8.8Gb/s 短帧电气筛查：DC 通过并不保证切换应力通过',fontsize=18);fig.tight_layout();fig.text(.5,-.03,'1024 line bits；3.63V / 0.3V为项目筛查线。连线只引导阅读，无点条件未测。',ha='center',fontsize=12);finish(fig,'pvt-stress-grid')

def waveform():
 fig,axs=plt.subplots(3,1,figsize=(11,7.5),sharex=True)
 ref=run.BUILD/'frozen/sshotlow/short-net8.8-s40/minimum-event.npz'
 if not ref.exists():plt.close(fig);return
 event=run.read(run.EV/'native-diagnostics.json')['events'];refevent=next(q for q in event if q['case'].endswith('frozen/sshotlow/short-net8.8-s40'));t0=refevent['event_time_s']
 for variant in ['frozen','cmd-r100','cmd-r330','cmd-r330-atten75']:
  p=run.BUILD/variant/'sshotlow/short-net8.8-s40/comparison-event.npz'
  if not p.exists():continue
  z=np.load(p);t=(z['time_s']-t0)*1e12;c=COL[variant]
  gate='v(phy_db_gate)' if 'v(phy_db_gate)' in z else 'v(db_cmd)';axs[0].plot(t,z[gate],color=c,label=NAMES[variant]);axs[1].plot(t,z['v(d_src)'],color=c);axs[2].plot(t,z['v(xdrv.di)'],color=c)
 axs[0].legend(fontsize=12,ncol=2);axs[1].axhline(-.3,color='#b34339',ls='--');axs[1].text(30,-.3,'体结筛查 −0.3V',fontsize=12,va='top',color='#b34339')
 for ax,label in zip(axs,['上游实际栅电压 / V','d_src / V','内部 DI / V']):ax.set_ylabel(label);ax.grid(alpha=.15);ax.set_xlim(-45,85)
 axs[-1].set_xlabel('相对原方案负峰时间 / ps（原生采样，无波形平移）');fig.suptitle('SS / 85°C / 低压：减小栅 dV/dt，观察负向注入与恢复',fontsize=18);fig.tight_layout();finish(fig,'pvt-negative-kick')

def full(rows):
 if not rows:return
 selected=[q for q in rows if q['config']['steps_per_UI']==40 and not q['config'].get('holdout_protocol')]
 group={('tt25',8.8):0,('tthigh',8.8):1,('sshotlow',8.8):2,('sshotlow',6.4):3};order={'frozen':0,'cmd-r330':1,'cmd-r330-atten75':2}
 selected.sort(key=lambda q:(group[(q['config']['corner'],q['config']['net_Gbps'])],order[q['config']['variant']]))
 vl={'frozen':'原方案','cmd-r330':'330Ω','cmd-r330-atten75':'330Ω+75Ω'};cl={'tt25':'TT25','tthigh':'TT高压','sshotlow':'SS热低压'}
 labels=[f"{vl[q['config']['variant']]}{'*' if q.get('reused_nominal') else ''}\n{cl[q['config']['corner']]} / {q['config']['net_Gbps']:g}G" for q in selected];x=np.arange(len(selected))
 fig,axs=plt.subplots(3,1,figsize=(max(10,len(selected)*1.2),9),sharex=True)
 for ax,key,title in [(axs[0],'timing','单侧时间余量 / UI'),(axs[1],'amp','最坏幅度距离 / µAeq'),(axs[2],'energy','供出能量 / pJ·bit⁻¹')]:
  v=[q['rx']['one_sided_margin_UI'] if key=='timing' else q['rx']['worst_signed_margin_uAeq'] if key=='amp' else q['energy']['positive'] for q in selected]
  bars=ax.bar(x,v,color=[COL[q['config']['variant']] for q in selected]);ax.set_ylabel(title);ax.grid(axis='y',alpha=.15)
  for bar,q in zip(bars,selected):
   if not q['combined_pass']:bar.set_hatch('///');bar.set_edgecolor('#334653');bar.set_linewidth(.8)
 axs[0].axhline(.37,color='#b34339',ls='--');axs[1].axhline(7.5,color='#b34339',ls='--');axs[-1].set_xticks(x,labels,fontsize=13,rotation=18)
 fig.suptitle('完整4736位帧：接收、应力与能耗必须同时判断',fontsize=18);fig.tight_layout();fig.text(.5,-.02,'斜线：总筛查未过（含应力）。能量分母为4096次尝试载荷位，失败点不称合格能耗。',ha='center',fontsize=12);fig.text(.5,-.055,'* TT25原完整帧复用2026-11-15冻结记录；其余为本轮新仿真。',ha='center',fontsize=12);finish(fig,'pvt-full-comparison')

def received_waveforms(rate):
 names=['frozen','cmd-r330']+(['cmd-r330-atten75'] if rate==8.8 else [])
 folders=[run.BUILD/v/'sshotlow'/f'full-net{rate:g}-s40' for v in names]
 if not all((p/'excerpt.json').exists() for p in folders):return
 fig,axs=plt.subplots(5,1,figsize=(12,10),sharex=True,gridspec_kw={'height_ratios':[.45,1,1,1,1]})
 for v,p in zip(names,folders):
  e=run.read(p/'excerpt.json');x=np.asarray(e['time_UI'])
  if v=='frozen':axs[0].step(np.arange(17),e['bits']+[e['bits'][-1]],where='post',color='#314c60');axs[0].set(yticks=[0,1],ylim=(-.1,1.1),ylabel='命令位')
  for ax,k in zip(axs[1:],['pin_V','gate_V','i_mA','actual_graph_5GHzRX']):ax.plot(x,e[k],label=NAMES[v],color=COL[v])
 for ax,label in zip(axs[1:],['DI−DBI / V','GP−GN / V','VCSEL电流 / mA','固定光/RX / µAeq']):ax.set_ylabel(label)
 for ax in axs:ax.set_xlim(0,10);ax.grid(alpha=.15)
 axs[-1].axhline(62.5,color='#b34339',ls='--');axs[-1].set_xlabel('验证位576起的时间 / UI（不作波形平移）')
 handles,labels=axs[1].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.952),ncol=3,fontsize=12)
 fig.suptitle(f'SS / 85°C / 低压，净{rate:g}Gb/s：短脉冲如何经过各级',fontsize=18);fig.tight_layout(rect=(0,0,1,.93));fig.text(.5,-.025,'命令到输出保留电路延迟；固定10UI只解释波形，完整帧错误与训练后余量另见数据表。',ha='center',fontsize=12);finish(fig,f'pvt-ss{rate:g}-waveforms')

def energy_tradeoff(rows):
 rs=[r for r in rows if r['config']['corner']=='sshotlow' and r['config']['net_Gbps']==8.8 and r['config']['steps_per_UI']==40]
 rs=sorted(rs,key=lambda r:['frozen','cmd-r330','cmd-r330-atten75'].index(r['config']['variant']))
 if len(rs)!=3:return
 fig,(a,b)=plt.subplots(1,2,figsize=(12,5.5));x=np.arange(3);bottom=np.zeros(3)
 for label,ports,color in [('激光供电',['VLASER'],'#314c60'),('内部缓冲',['VDD'],'#5484a0'),('参考边界',['VREF','VSET','VREGSET'],'#a7bfcc'),('上游VPHY',['VPHY'],'#158375'),('命令VD+VDB',['VD','VDB'],'#bd824e')]:
  vals=np.asarray([sum(q['energy_by_source'][p]['positive'] for p in ports) for q in rs]);a.bar(x,vals,bottom=bottom,label=label,color=color);bottom+=vals
 a.set_ylabel('八源供出 / pJ·bit⁻¹');a.legend(fontsize=11,ncol=2)
 for i,k in enumerate(['positive','returned','net']):
  vals=[sum(q['energy_by_source'][p][k] for p in ['VD','VDB']) for q in rs];b.bar(x+(i-1)*.23,vals,width=.23,label={'positive':'命令供出','returned':'返能','net':'命令净能'}[k],color=['#bd824e','#a8c5c1','#158375'][i])
 b.set_ylabel('两路命令源 / pJ·bit⁻¹');b.legend(fontsize=12)
 for ax in [a,b]:ax.set_xticks(x,['原方案','330Ω','330Ω +75Ω'],fontsize=13);ax.grid(axis='y',alpha=.15)
 fig.suptitle('SS8.8：只看VPHY下降，会漏掉命令端和返能的变化',fontsize=18);fig.tight_layout();fig.text(.5,-.035,'三个SS8.8点均未满足总门槛；这些是尝试发送能量，不是合格运行效率。',ha='center',fontsize=12);finish(fig,'pvt-energy-boundary')

def schematic():
 old=run.ROOT/'scripts/driver_interface_20261115/vcsel/schematic.py';spec=importlib.util.spec_from_file_location('symbols',old);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
 s.S=['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="720" viewBox="0 0 1100 720"><style>text{font-family:"Arial Unicode MS","PingFang SC",Arial,sans-serif}</style><rect width="1100" height="720" fill="#fbfcfd"/>']
 t=s.text;s.text=lambda x,y,txt,size=17,anchor='start',c='#233e4e':t(x,y,txt,max(17,size),anchor,c)
 l=s.line;t(35,42,'VCSEL 输入修复：在实际 CMOS 栅前增加串联阻尼',26)
 t(35,77,'同一69 MOS核心 + 4 MOS上游；下图展开其中一路，另一互补路完全对称。',18)
 s.inv(300,300,'VPHY', 'XPHYDP 24/0.28','XPHYDN 12/0.28')
 t(35,255,'DB_CMD',18);s.resistor(35,300,205,'RCMD');t(35,375,'试验：0 / 100 / 330 Ω',17);l(205,300,255,300);s.dot(255,300)
 t(35,345,'源仍0–3.3V、20ps',17);t(235,222,'phy_db_gate',17,'end')
 l(400,300,425,300);t(380,333,'d_src',18);s.resistor(425,300,535,'外部 50 Ω');s.resistor(535,300,690,'内部150 / 75 Ω');l(690,300,820,300);s.dot(740,300);t(700,278,'DI',18)
 l(740,300,740,355);s.S.append('<rect x="733" y="355" width="14" height="55" fill="white" stroke="#345264" stroke-width="2"/>');s.ground(740,410);t(760,385,'2.5 kΩ',18)
 s.S.append('<rect x="820" y="260" width="230" height="80" rx="4" fill="#edf3f5" stroke="#345264" stroke-width="2"/>');t(935,292,'原内部 CMOS 预驱动',18,'middle');t(935,320,'DI → GN',18,'middle')
 t(35,490,'原理：栅极下降通过 MOS 的寄生 Cgd 向输出耦合负向电荷。',19)
 t(35,521,'串联电阻使实际栅 dV/dt 减小；负峰可能降低，但延迟与短路电流会改变。',19)
 t(35,552,'Cgd 属于 PDK MOS 模型，并非人为新增电容；本图不宣称提取到独立 Cgd 数值。',17)
 t(35,591,'另一支路：D_CMD → 同值RCMD → XPHYDBP/N → db_src → DBI → GP。',18)
 t(35,622,'P管体接 VPHY，N管体接 VSS；W/L单位 µm。实际候选以各网表为准。',18)
 t(35,653,'8源计能包含 VPHY 与两路理想命令端；不代表实物 FPGA / LVDS / CML / Pad / ESD。',17)
 t(35,684,'顺序：先只改RCMD；再在330Ω条件只改内部150→75Ω，分开检验应力与速率。',17)
 s.S.append('</svg>');p=OUT/'vcsel-pvt-input-circuit.svg';p.write_text('\n'.join(s.S));import cairosvg;cairosvg.svg2png(url=str(p),write_to=str(p.with_suffix('.png')),scale=1.4)
 return {'symbol_script':str(old.relative_to(run.ROOT)),'sha256':run.sha(old)}

def main():
 rows=summarize();run.emit(run.EV/'comparison.json',dict(schema='vcsel-pvt-comparison-v1',rows=rows,scope=run.protocol()['scope']));grid();waveform();full(rows);received_waveforms(8.8);received_waveforms(6.4);energy_tradeoff(rows);symbols=schematic()
 run.emit(OUT/'vcsel-pvt-figures.source.json',dict(script_sha256=run.sha(Path(__file__)),symbols=symbols,summary_sha256=run.sha(run.EV/'summary.json'),comparison_sha256=run.sha(run.EV/'comparison.json'),diagnostic_sha256=run.sha(run.EV/'native-diagnostics.json') if (run.EV/'native-diagnostics.json').exists() else None,files={p.name:run.sha(p) for p in OUT.glob('vcsel-pvt-*') if p.suffix in ['.png','.svg']}))
if __name__=='__main__':main()
