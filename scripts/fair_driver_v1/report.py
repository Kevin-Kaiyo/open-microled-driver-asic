#!/usr/bin/env python3
"""Build a Chinese, data-bound fair-comparison research report."""
from pathlib import Path
import hashlib,importlib.util,json,math,re,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import markdown
import run as e
ROOT=e.ROOT;WORK=e.BUILD/'matched-r2';DEST=ROOT/'docs/research/fair-driver-comparison-20261025';EV=ROOT/'evidence/fair-driver-v1'
COLORS={'A':'#377eb8','B':'#168780','C':'#aa6b3b'}
FONT=FontProperties(fname=str(ROOT/'build/fair-driver-v1/report-font/NotoSansCJKsc-Regular.otf'))
plt.rcParams.update({'font.family':FONT.get_name(),'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.16,'svg.fonttype':'none','savefig.facecolor':'white'})
from matplotlib import font_manager
font_manager.fontManager.addfont(FONT.get_file())

def compact(r,work=WORK):
 c=r['case'];m=r.get('metrics',{});rx=m.get('receiver',{});v=rx.get('validation',{});h=rx.get('horizontal_margin',{})
 return {'case':c,'simulation_ok':r['simulation_ok'],'analysis_error':r.get('analysis_error'),'case_result_sha256':e.sha(work/'cases'/c['name']/'result.json'),'runner_sha256':r['runner_sha256'],'deck_sha256':r['deck_sha256'],'raw_sha256':r.get('raw_sha256'),'gzip_sha256':r.get('gzip_sha256'),'native_samples':m.get('sample_count'),'DC_I_uA':m['i_led_A']*1e6 if c.get('kind')=='dc' and m else None,'final_LED_current_uA':m['i_led_A']*1e6 if m and c.get('kind')!='dc' else None,'mean_LED_current_uA':m['mean_LED_current_A']*1e6 if 'mean_LED_current_A' in m else None,'DC_error_percent':m.get('current_error_percent'),'DC_power_mW':m['DC_power_W']*1e3 if 'DC_power_W' in m else None,'energy':m.get('energy'),'total_energy':m.get('total_energy'),'receiver':{k:({x:y for x,y in rx[k].items() if x!='training_scan'} if k=='sampling' else rx[k]) for k in ['rates','sampling','checks','horizontal_margin','conditional_noise_BER'] if k in rx},'rx_v2_evidence':r.get('rx_v2_evidence'),'validation':{k:v[k] for k in ['bit_errors','bit_count','raw_BER','symbol_errors','symbol_count','SER','decision_distance_min_uA','transition_counts','symbol_counts'] if k in v},'device_voltage_passed':m.get('device_voltage_passed'),'max_body_forward_V':m.get('max_body_forward_V'),'stress':m.get('stress'),'communication_screen_passed':m.get('passed')}
def figsave(fig,name):
 for suffix in ['svg','png']:fig.savefig(DEST/'figures'/f'{name}.{suffix}',bbox_inches='tight',dpi=150)
 plt.close(fig)
def table(headers,rows):
 return '| '+' | '.join(headers)+' |\n|'+'|'.join(['---']*len(headers))+'|\n'+''.join('| '+' | '.join(str(x) for x in row)+' |\n' for row in rows)+'\n'
def disclosure_table(headers,rows):return markdown.markdown(table(headers,rows),extensions=['tables'])
def image(name,caption):
 svg=(DEST/'figures'/f'{name}.svg').read_text();box=re.search(r'viewBox="([0-9. \-]+)"',svg);v=[float(x) for x in box.group(1).split()];w,h=v[2:];return f'<figure><a href="figures/{name}.svg"><img src="figures/{name}.svg" alt="{caption}" width="{math.ceil(w)}" height="{math.ceil(h)}" style="aspect-ratio:{w}/{h}" loading="lazy"></a><figcaption>{caption}（点击查看大图）</figcaption></figure>\n'

def use_v2(r,group):
 if r['case'].get('kind')=='dc' or not r.get('metrics'):return r
 p=e.BUILD/'rx-equal-latency-v2-final-r1/cases'/group/r['case']['name']/'result.json'
 assert p.exists(),'Wait for v2 reanalysis: '+str(p)
 x=json.loads(p.read_text());origin=WORK if group=='baseline' else e.BUILD/'controls-r1'
 assert x['source_result_sha256']==e.sha(origin/'cases'/r['case']['name']/'result.json')
 r['metrics']['receiver']=x['receiver'];r['metrics']['passed']=x['communication_screen_passed'];r['rx_v2_evidence']={'path':str(p.relative_to(ROOT)),'sha256':e.sha(p),'analysis_version':x['analysis_version'],'receiver_sha256':x['v2_receiver_sha256']};return r
def vals(r):
 m=r['metrics'];rx=m['receiver'];return [m['total_energy']['positive_pJ_per_payload_bit'],m['total_energy']['net_pJ_per_payload_bit'],rx['validation']['bit_errors'],rx['validation']['decision_distance_min_uA'],rx['horizontal_margin']['min_ps']]
def main():
 DEST.mkdir(parents=True,exist_ok=True);(DEST/'figures').mkdir(exist_ok=True)
 final_index=json.loads((EV/'rx-equal-latency-v2-index.json').read_text());assert final_index['complete'],'Wait for all45+11 canonical v2 analyses before final report'
 records=[use_v2(json.loads(p.read_text()),'baseline') for p in sorted((WORK/'cases').glob('*/result.json'))]
 selected={}
 for r in records:
  key=r['case'].get('retry_of',r['case']['name'])
  if key not in selected or r.get('metrics'):selected[key]=r
 good=[r for r in selected.values() if r.get('metrics')];dc=[r for r in good if r['case'].get('kind')=='dc'];rx=[r for r in good if r['case'].get('kind')!='dc'];look={r['case'].get('retry_of',r['case']['name']):r for r in good}
 e.emit(EV/'summary.json',{'status':'complete' if len(dc)==24 and len(rx)==45 else 'partial','scope':'24DC+45full-frame transients, new schematic candidates; no route preselection. Energy denominator4096 offered payload bits; failed points are not qualified goodput.','work':str(WORK.relative_to(ROOT)),'manifest_sha256':e.sha(WORK/'manifest.json'),'selected_case_map':{k:v['case']['name'] for k,v in selected.items()},'cases':[compact(r) for r in records]})
 # DC plot: target matching and corner drift, independent of receiver.
 fig,axs=plt.subplots(1,3,figsize=(12,3.6))
 for ax,route in zip(axs,'ABC'):
  for label,style in [('TT','o-'),('SS','s--'),('FF','^:')]:
   rr=sorted([r for r in dc if r['case']['route']==route and label in r['case']['name']],key=lambda r:r['case']['level'])
   ax.plot([r['case']['level'] for r in rr],[r['metrics']['i_led_A']*1e6 for r in rr],style,label=label)
  targets=[25,50,75,100] if route=='C' else [25,100]
  ax.scatter(range(len(targets)),targets,marker='x',s=70,color='black',label='目标')
  ax.set(title=f'路线{route}：固定TT校准参数',xlabel='码位',ylabel='LED直流电流 / µA',xticks=range(len(targets)));ax.legend(fontsize=8)
 fig.tight_layout();figsave(fig,'dc-corners')
 # Paired energy curves. Crosses mark the communication acceptance failure.
 fig,axs=plt.subplots(1,3,figsize=(12,3.6),sharey=True)
 for ax,label in zip(axs,['TT','SS','FF']):
  for route in 'ABC':
   rr=sorted([r for r in rx if r['case']['route']==route and '-'+label+'-' in r['case']['name']],key=lambda r:r['case']['net_rate_Gbps'])
   x=[r['case']['net_rate_Gbps'] for r in rr];y=[vals(r)[0] for r in rr];dc_failed=route=='A' and label!='TT';ax.plot(x,y,'o--' if dc_failed else 'o-',color=COLORS[route],label=route+(' DC未达' if dc_failed else ''),markerfacecolor='white' if dc_failed else COLORS[route])
   bad=[r for r in rr if not r['metrics']['passed']];ax.scatter([r['case']['net_rate_Gbps'] for r in bad],[vals(r)[0] for r in bad],marker='x',s=100,c='black',zorder=5)
  ax.set(xscale='log',xlabel='计划净吞吐 / Gb/s',title=label);ax.legend();ax.set_xticks([.1,.25,.5,1,2],['.1','.25','.5','1','2'])
 axs[0].set_ylabel('输入端口正向能量 / pJ / payload bit');fig.tight_layout();figsave(fig,'energy-rates')
 # Worst corner receiver margins.
 fig,axs=plt.subplots(1,2,figsize=(11,3.7))
 for route in 'ABC':
  points=[]
  for rate in [.1,.25,.5,1,2]:
   rr=[r for r in rx if r['case']['route']==route and r['case']['net_rate_Gbps']==rate]
   if len(rr)==3:points.append((rate,min(vals(r)[3] for r in rr),min(vals(r)[4] for r in rr)))
  for ax,col in zip(axs,[1,2]):ax.plot([p[0] for p in points],[p[col] for p in points],'o-',label=route,color=COLORS[route])
 axs[0].axhline(7.5,c='grey',ls='--');axs[1].axhline(100,c='grey',ls='--')
 axs[0].set_ylabel('三角落最小判决距离 / µA');axs[1].set_ylabel('三角落最小时序余量 / ps')
 for ax in axs:ax.set(xlabel='计划净吞吐 / Gb/s',xscale='log');ax.set_xticks([.1,.25,.5,1,2],['.1','.25','.5','1','2']);ax.legend()
 fig.tight_layout();figsave(fig,'receiver-margins')
 # Representative TT 0.5G eyes using full native conduction traces.
 if all(f'RX-TT-{route}-0.5G' in look for route in 'ABC'):
  filtermod=e.module(e.BUILD/'rx-equal-latency-v2-final-r1/receiver.py','fair_report_rx')
  fig,axs=plt.subplots(1,3,figsize=(12,3.7),sharey=True)
  for route,ax in zip('ABC',axs):
   r=look[f'RX-TT-{route}-0.5G'];a=np.loadtxt(WORK/'cases'/r['case']['name']/'waveform.dat.gz',skiprows=1);t=a[:,0];i=a[:,1];opt,y=filtermod.filter_trace(t,i);receiver=r['metrics']['receiver'];ui=receiver['rates']['symbol_UI_s'];delay=receiver['sampling']['delay_symbol_UI'];start=576//(2 if route=='C' else 1)
   for k in range(start,start+160):
    center=(k+delay)*ui;xx=np.linspace(-.5,.5,160);yy=np.interp(center+xx*ui,t,y)*1e6;ax.plot(xx,yy,c=COLORS[route],alpha=.12,lw=.7)
   for threshold in ([37.5,62.5,87.5] if route=='C' else [62.5]):ax.axhline(threshold,c='grey',lw=.7,ls='--')
   ax.axvline(0,c='black',lw=.7);ax.set(title=f'{route} | {1e-9/ui:.4f} GBd',xlabel='相对冻结采样时刻 / symbol UI',ylim=(5,120))
  axs[0].set_ylabel('接收代理等效电流 / µA');fig.tight_layout();figsave(fig,'eyes-tt-0p5G')
 # At equal net target all source inputs are accounted.
 if all(f'RX-TT-{route}-0.5G' in look for route in 'ABC'):
  fig,ax=plt.subplots(figsize=(8,3.6));bottom=np.zeros(3)
  for source in ['VLED','VIN','VDD','VREF','VD0','VD1','VDISABLE']:
   energies=np.array([look[f'RX-TT-{route}-0.5G']['metrics']['energy'][source]['positive_J']/4096*1e12 for route in 'ABC']);ax.bar(list('ABC'),energies,bottom=bottom,label=source,color={'VLED':'#3b7590','VIN':'#427d78','VDD':'#8dbaa9','VREF':'#a1abb3','VD0':'#b89572','VD1':'#d0bba0','VDISABLE':'#d8dfde'}[source]);bottom+=energies
  ax.set(ylabel='输入端口正向能量 / pJ / payload bit',title='TT、相同计划净吞吐0.5 Gb/s，含整帧开销');ax.legend(ncol=4,fontsize=8);fig.tight_layout();figsave(fig,'energy-ports')
 # Tables from actual completed records only.
 dcrows=[]
 for label in ['TT','SS','FF']:
  for route in 'ABC':
   rr=sorted([r for r in dc if r['case']['route']==route and '-'+label+'-' in r['case']['name']],key=lambda r:r['case']['level'])
   dcrows.append([label,route,' / '.join(f"{r['metrics']['i_led_A']*1e6:.3f}" for r in rr),' / '.join(f"{r['metrics']['current_error_percent']:+.3f}%" for r in rr),'通过' if rr and all(abs(r['metrics']['current_error_percent'])<=5 for r in rr) else '未通过'])
 meanrows=[[route,f"{look[f'RX-TT-{route}-0.5G']['metrics']['mean_LED_current_A']*1e6:.3f}"] for route in 'ABC' if f'RX-TT-{route}-0.5G' in look]
 rows=[]
 for label in ['TT','SS','FF']:
  for route in 'ABC':
   name=f'RX-{label}-{route}-0.5G'
   if name in look:
    r=look[name];v=vals(r);rows.append([label,route,f'{v[0]:.4f}',f'{v[1]:.4f}',f'{v[2]}/4096',f'{v[3]:.3f}',f'{v[4]:.1f}',f"{r['metrics']['max_body_forward_V']:.3f}",'通过' if r['metrics']['passed'] else '未通过'])
 allrows=[]
 for r in sorted(rx,key=lambda r:(r['case']['net_rate_Gbps'],r['case']['corner'],r['case']['route'])):
  c=r['case'];v=vals(r);allrows.append([c['name'],f'{v[0]:.4f}',f'{v[2]}',f'{v[3]:.3f}',f'{v[4]:.1f}','通过' if r['metrics']['passed'] else '未通过'])
 sampled=[]
 for route in 'ABC':
  passrates=[]
  for rate in [.1,.25,.5,1,2]:
   rr=[r for r in rx if r['case']['route']==route and r['case']['net_rate_Gbps']==rate]
   if len(rr)==3 and all(r['metrics']['passed'] for r in rr):passrates.append(rate)
  sampled.append([route,'、'.join(f'{x:g}' for x in passrates) or '无已通过点','稀疏网格，不是连续Fmax；另看DC精度和启动'])
 # PAM4 static linearity relative to the declared ideal25uA step.
 pamrows=[]
 for label in ['TT','SS','FF']:
  rr=sorted([r for r in dc if r['case']['route']=='C' and '-'+label+'-' in r['case']['name']],key=lambda r:r['case']['level'])
  if len(rr)==4:
   y=np.array([r['metrics']['i_led_A']*1e6 for r in rr]);dnl=np.diff(y)/25-1;inl=(y-np.array([25,50,75,100]))/25
   pamrows.append([label,' / '.join(f'{x:+.5f}' for x in dnl),' / '.join(f'{x:+.5f}' for x in inl)])
 # Separate selected controls; never mix them into the45-point baseline count.
 controlwork=e.BUILD/'controls-r1';controls=[use_v2(json.loads(p.read_text()),'controls') for p in sorted((controlwork/'cases').glob('*/result.json'))] if controlwork.exists() else []
 controlrows=[];dctol=[];numerics=[]
 for r in controls:
  c=r['case'];m=r.get('metrics',{})
  if not m:continue
  if c.get('kind')=='dc':dctol.append([c['name'],f"{m['i_led_A']*1e6:.4f}",f"{m['current_error_percent']:+.4f}%"])
  else:
   x=vals(r);controlrows.append([c['name'],f'{x[0]:.4f}',f"{m['total_energy']['returned_pJ_per_payload_bit']:.4f}",f'{x[1]:.4f}',x[2],f'{x[3]:.3f}',f'{x[4]:.2f}','通过' if m['passed'] else '未通过'])
   if 'step80' in c['name']:
    base=look[f"RX-TT-{c['route']}-0.5G"];b=vals(base);body_delta=(m['max_body_forward_V']-base['metrics']['max_body_forward_V'])*1e3
    row={'route':c['route'],'case':c['name'],'source_result_sha256':e.sha(controlwork/'cases'/c['name']/'result.json'),'energy_percent':100*(x[0]/b[0]-1),'decision_distance_uA':x[3]-b[3],'time_ps':x[4]-b[4],'body_mV':body_delta,'bit_errors_equal':x[2]==b[2]}
    row['numerical_control_passed']=abs(row['energy_percent'])<=.2 and abs(row['decision_distance_uA'])<=.2 and abs(row['time_ps'])<=20 and abs(row['body_mV'])<=5 and row['bit_errors_equal'];numerics.append(row)
 e.emit(EV/'controls-summary.json',{'cases':[compact(r,controlwork) for r in controls],'numerical_comparison':numerics,'numerical_contract_sha256':e.sha(EV/'numerics-contract.json'),'scope':'Selected one-factor controls, not full Cartesian PVT/tolerance qualification.'})
 numericrows=[[r['route'],f"{r['energy_percent']:+.6f}%",f"{r['decision_distance_uA']:+.6f}",f"{r['time_ps']:+.3f}",f"{r['body_mV']:+.3f}",'一致' if r['numerical_control_passed'] else '待排查'] for r in numerics]
 load=json.loads((EV/'load-dynamics.json').read_text());loadrows=[[f"{x['I_uA']:.0f}",f"{x['VF_V']:.6f}",f"{x['local_r_d_ohm']/1e3:.3f}",f"{x['tau_rdC_ns']:.3f}"] for x in load['levels']]
 bias=[]
 for route in 'BC':
  name=f'DC-TT-{route}-L0';r=look[name];p=WORK/'cases'/name;data=np.loadtxt(p/'waveform.dat.gz',skiprows=1,ndmin=2);vec=r['metadata']['vectors'];sense=float(data[-1,vec['xdrv.sense']]);rset=r['metadata']['parameters']['RSET'];bias.append({'route':route,'case_sha256':e.sha(p/'result.json'),'SENSE_V':sense,'RSET_ohm':rset,'ISET_uA':sense/rset*1e6,'LED_uA':r['metrics']['i_led_A']*1e6})
 e.emit(EV/'bias-operating-point.json',{'definition':'ISET=SENSE/RSET; measured within simulation, not assumed equal to mirrored LED current','rows':bias})
 meta=json.loads((WORK/'manifest.json').read_text());nfail=sum(not r['metrics']['passed'] for r in rx)
 text=f'''# MicroLED高速驱动：A/B/C同条件晶体管比较

**研究阶段：原理图级（SCHEM），2026-10-25研究批次，2026-10-26完成整理。** 本轮从共同负载、共同电流目标和共同输入能量边界重新建立比较。已完成 **{len(dc)}/24 个直流点、{len(rx)}/45 个完整帧瞬态**。通信筛查失败 {nfail} 点均保留，并完成统一绝对延迟v2接收重分析，未据此预选架构。{'' if len(rx)==45 else '**当前页面仍为构建中快照。**'}

初版v1按0.5～2symbol搜索，给NRZ/PAM4不同绝对预算，会把搜索上限混入高速限制。原v1源/结果全部保留；本报告性能表统一使用v2，对同一原生波形重分析，不重调电路、不重跑供电能量。

这份报告回答三个问题：加入实际辅助供电后A的能量是多少；真实参考下B与A的电流目标是否相同；把C变成MOS译码与四电平电路后，符号率减半能否换来可用的接收余量。所有结论只适用于本次尺寸与偏置的候选，不能代表这些拓扑的性能极限。

## 1．先看比较对象与边界

| 路线 | 本轮真实电路 | 完整MOS数量 | 数据如何控制LED |
|---|---|---|---|
| A：电压输出NRZ | 两级缓冲、互补输出、两路实际shunt辅助轨 | 20（6核心＋14辅助轨） | 改变OUT电位，以LED的I–V曲线形成两档电流 |
| B：电流转向NRZ | 9MOS核心＋12MOS真实V-to-I参考/禁止/keeper | 21 | 基础电流保持，额外电流在LED/dummy间转向 |
| C：电流DAC/PAM4 | 14MOS真实Gray译码、三路7MOS单元、REF/BASE与12MOS参考 | 49 | 每符号2bit，开启0/1/2/3个单位电流，形成四档 |

PAM4是调制格式，不是独立的输出电路拓扑。本轮C是在电流转向上增加DAC和四电平调制。MOS数量只是器件账本，不能替代芯片面积、版图面积、成本或完整收发器能效。

### 共同条件

{table(['项目','本轮固定条件'],[
 ['MicroLED','Lin2026 yellow20µm静态I–V；同一冻结SPICE文件，LED温度、L–I与动态尚未测量'],
 ['负载寄生','CLED200fF；RPKG1Ω、LPKG0.5nH；VLED5V经0.25Ω'],
 ['输出目标','A/B：25/100µA；C：25/50/75/100µA；每路线仅TT校准两个自由度'],
 ['电源','VIN5V：0.25Ω/0.5nH；VDD：1Ω/2nH；均100nF与0.2ΩESR；VREF2.5V经0.2Ω'],
 ['数据输入','D0/D1端口20ps边沿、100Ω输出阻抗；RIN统一8µm×1µm PDK电阻'],
 ['MOS模型','GF180公开模型子集；03v3/06v0；结面积/周长统一公式估计，并非PEX'],
 ['角落','TT27°C/3.3V、SS125°C/2.95V、FF−40°C/3.65V；仅PDK输入RIN的电阻角随MOS配对；其他理想R/C暂不含容差/温漂'],
 ['接收代理','电流→200ps光学一阶代理→1GHz接收一阶；无实体PD/TIA/时钟恢复电路'],
 ['接收门槛','NRZ62.5µA；PAM4 37.5/62.5/87.5µA；最小判决距离7.5µA、单侧时序余量100ps'],
 ])}

{image('common-testbench','共同负载、供电和输入端口；所有路线使用同一电气测试台')}

**已计入能量：** VIN、VDD、VREF、VLED、D0、D1、DISABLE七个输入端口，包含实际实例化的参考源、shunt、dummy、译码与R/C。分别记录正向取能、回流和净能量。流入A辅助轨的LED电流由真实shunt耗散；另有瞬态能量返回上游端口，独立列示。净额只是带符号端口账本，不代表上游能无损回收。

**尚未计入：** 上游5V/3.3V转换器和精密2.5V基准IC自身的静态电流/效率、时钟/主机、实体接收器及FEC；D0/D1端口计入其对输入网络的充放电，但不包含外部数据发生/串行器IC的内部耗电；上电充电/启动与空闲也未纳入本次已建立OP的正常通信帧。它们仍是端口边界之外的理想源，电源阻抗与去耦只是明确的电气模型；因此本文的pJ/bit称“输入端口能量”，不能称完整TX或完整光链路能量。

## 2．相同净吞吐怎样定义

测试帧共4736bits：64预热＋512训练＋4096验证＋64尾部。η=4096/4736≈0.864865。最终v2仅用其中448bits（bit64～511）评分，末64bits作共同隔离保护；在最高已扫2Gb/s下仍足以隔离8ns最大延迟。输入数据、训练总开销、验证4096bits和能耗分母都不变。

`Rline=Rnet/η`；NRZ的`Rs=Rline`，PAM4的`Rs=Rline/2`。例如计划净吞吐0.5Gb/s时，两者线路比特率均0.578125Gb/s，NRZ0.578125GBd，PAM40.2890625GBd。整帧时长8.192µs，两者均提供4096个验证比特。这个帧开销是实验定义，未实现产品协议或FEC。

最终v2训练阶段在共同0～8ns、5ps绝对网格内选采样延迟，随后冻结。8ns和5ps是本项目实验假设，不是已实现CDR/时钟精度，也不是行业规格。这个窗口在相同净率下给三条路线相同的绝对时延预算和搜索分辨率。目标是最大化训练段最小有符号判决距离；1pA内的幅度等价平台，按训练段最小时序余量破同分，再取最早延迟。阈值和验证标签不参与调参。部分低速点的所选延迟落在8ns边界，只能解释为该共同预算内的最优点，不冒称无时延约束的极限。时序门槛统一用**100ps绝对时间**，同时保留symbol UI与bit UI。

能量按`E+=Σ∫max(−Vsrc·Isrc,0)dt / 4096`计算，回流另报。积分覆盖整个4736-bit帧。**失败点的pJ/bit只是每个计划payload bit的取能，不是已可靠交付比特的能量**，不进入达标性能排序。零错也仅指这4096个确定性验证比特，不是BER资格证明。

## 3．直流目标是否对齐：与接收结果分别验收

A校准RH/RL，B校准RSET/WTAIL，C校准RSET/WUNIT；各两个自由度，之后所有角落固定。B的WTAIL和C的WUNIT按5nm尺寸网格取值。C中间两档没有独立修正。

{table(['角落','路线','LED DC电流 / µA','相对各自目标误差','全部电平±5%'],dcrows)}

{image('dc-corners','同一TT校准参数跨角落的直流漂移，黑叉为预先声明目标')}

**A的跨角落电流精度尚未通过。** SS高档约75.59µA（目标100µA，−24.41%），FF高档约111.40µA（＋11.40%）。它靠电压与MOS导通电阻形成电流，电路PVT改变后，不会自动维持目标电流。B的高档变化约−2.98%～＋3.06%；C本轮四档在三角落均接近目标。这里仍固定LED静态曲线，不能据此声称真实LED跨温度光功率稳定。

## 4．电路逐层展开

### A：实际辅助轨承担了什么

D0经RIN与两级反相器形成CTRL。CTRL低时XPOUT导通，将OUT连接至较高VH，LED压差较小、电流约25µA；CTRL高时XNOUT导通，将OUT连接至较低VL，LED压差增大、电流约100µA。两只输出管的体端分别接VH和VSS，不能随意省略。

{image('a-core','A的六MOS输出核心：每只D/G/S/B、尺寸和网络明确')}
{image('a-rails','两路真实辅助电源：反馈shunt吸收回流，外接10nF去耦')}

每路辅助轨包含7MOS反馈shunt、100kΩ从VIN馈电与10nF片外去耦；VREF分压给HSET/LSET。它是可运行的耗散式实验实现，并非A拓扑的最低功耗设计。正常OP通信测试与冷启动测试分开；A没有实现DISABLE或自主上电保护。

### B：真实参考、基础电流和75µA转向

VREF经200k/50k分压约0.5V，V-to-I环路驱动SENSE/RSET形成参考电流。理想关系是ISET≈VSET/RSET；本次B的实际SENSE约0.5004996V、RSET20.126535kΩ，故ISET约24.8677µA，对应LED基础电流25.0007µA。真实环路与镜像条件下两者有偏差，使用实际仿真数值校准，不能把理想等式当作已实现精度。XREF把它转换成BIAS，XBASE形成约25µA基础LED电流，XTAIL提供额外约75µA；互补栅极GP/GB把尾电流转到LED或dummy。dummy不是免费路径，VIN持续为它供电。

{image('b-core','B的9MOS核心与真实参考接口，RSET/补偿/dummy/keeper均纳入端口能量')}
{image('common-reference','B/C共用的12MOS参考模块；包含真实放大与输出器件及禁止/keeper')}

### C：Gray数据如何成为四档电流

D1D0=00/01/11/10依次对应0/1/2/3个开启单元。真实静态CMOS产生`T1=D1 OR D0`、`T2=D1`、`T3=D1 AND NOT D0`。三单元各增加约25µA，与基础25µA叠加；单元开关/缓冲沿用同一组06v0尺寸作为可运行起点，尚未针对25µA单位优化，故本轮能量不是PAM4的理论下界。未送LED的电流走各自dummy。PAM4较低符号率来自每符号2bit，但相邻目标间距只有25µA，不能假定比NRZ更抗噪。

{image('c-overview','C的49MOS账本与三路实际网络映射：12＋2＋14＋3×7')}
{image('c-decoder','C的14MOS真实Gray到温度计码译码；没有理想逻辑源隐藏能量')}
{image('c-unit','C的7MOS标准单位电流单元，重复三次并明确D/G/S/B')}

下表按声明25µA理想步长计算：`DNLk=(Ik+1−Ik)/25µA−1`，`INLk=(Ik−Iideal,k)/25µA`。单位均为LSB；它是本次无失配DC模型的线性度，不是量产DAC规格。

{table(['角落','三个步长DNL / LSB','四档INL / LSB'],pamrows)}

## 5．相同0.5Gb/s目标下的接收与能量

固定的是稳态电流目标和共同激励/负载，动态平均电流按实际波形报告，没有为任一路线再单独调平均值。TT本组整帧导电均值如下；它不是测得光功率，也不证明三者实际光OMA、平均光功率或真实噪声相同。

{table(['路线','整帧平均LED导电电流 / µA'],meanrows)}

{table(['角落','路线','正向pJ/bit','净pJ/bit','错误数','最小判决距离µA','最小时间ps','最大体结正偏V','通信/端压筛查'],rows)}

通信筛查要求训练/验证零错、最小判决距离≥7.5µA、时序余量≥100ps、全部有向转换覆盖，并通过逐型号六对端压筛查。**表中通过不包含DC±5%、启动、真实噪声或光学测量通过。** A的DC失败不能被零错接收掩盖。C在TT本组内部体结正偏约0.858V；这个独立风险也不能被绝对端压小于6V掩盖。

{image('eyes-tt-0p5G','TT同净吞吐接收眼图：固定取首160个验证symbol叠加示意；判据使用全部4096bits。横轴为各自symbol UI，标题保留绝对符号率')}
{image('energy-ports','七个源端口分项能量；VIN同时包含各自参考、辅助或dummy，不能把全部VIN取能都归为参考功耗')}

### 5.1．为什么C零错仍没有足够余量

完整帧统计发现：TT、0.5Gb/s时，C有261/2048个符号的判决距离不足7.5µA，全部来自2→0（131次）和3→0（130次）。最差3→0是Gray10→00，仅D1变化，不能直接归咎于两bit同时变化。详见[逐转换统计](../../../evidence/fair-driver-v1/transition-review-v2.json)。

为区分栅极传播与负载建立，另做112symbol的短诊断：12种有向转换逐一保持4symbol前/4symbol后。这是独立诊断，未冒充4096bit随机帧。3→0后，GP2/3/1穿过固定1.65V（名义半VDD）分别约304/537/567ps；半电平时刻不等于完整关断。在用于这份短诊断的v1观测延迟3.8919ns处（与最终v2性能表分开），实际支路sink=25.265µA，而LED导电仍31.177µA。

{image('c-current-tail','从数据、MOS栅极、实际sink到LED导电/接收代理；竖线是短诊断借用的v1延迟，最终性能表已统一v2；短序列上下文另列')}

关键方程是并联负载的KCL：`I_sink = I_LED(VF) + C_LED × dVF/dt`。此时差值约−5.912µA，表示电容电压正在下降；3→0的电流差积分约−80.944fC，与`C×ΔVF≈−80.980fC`相差0.0443%，12转换最大相对差0.1366%。驱动已接近新电流，不代表发光支路的导电电流已到位；早期sink在1ns仍约29.31µA，也显示实际驱动建立参与了过程。

用同一静态PWL曲线计算局部动态电阻`r_d=dVF/dI`，再乘本轮**假设**的200fF（这不是测得的载流子寿命；常数C与另加的光学一阶均待同一器件动态数据拟合）：

{table(['电流µA','VF / V','局部r_d / kΩ','r_d×200fF / ns'],loadrows)}

即使理想sink立刻由100降到25µA，仅此PWL＋电容的解析对照，到32.5µA也需约2.807ns，到30µA需约3.586ns；这里30µA正是最低眼达到7.5µA判决距离的上界。这个对照排除了实际驱动/封装/光学/RX，**只隔离电气负载作用，不进入三路线能耗比较，也不证明真实LED有该时间常数**。原始电流还要再经过共同200ps光学代理和1GHz接收代理。四电平虽降低符号率，窄眼仍要求更充分的建立；NRZ拥有更宽的两电平间距。这是本次候选差异的具体机制，不能推广为所有PAM4都会较差。

{image('c-body-forward','另一个独立限制：真实CMOS译码内部节点的瞬态体结正偏，不能用六对绝对端压通过来覆盖')}

短波形还复现P_OR相对VDD约＋0.858V、N_OR相对地约−0.604V、N_AND约−0.527V。这是节点电压层面的体结风险证据；尚未分离内部Miller耦合/浮置节点的各自贡献，也未以体端电流或工艺可靠性数据闭合。应继续做输入缓冲/内部节点控制的单因素设计与验证。参见[负载解析计算](../../../evidence/fair-driver-v1/load-dynamics.json)、[短诊断原始摘要](../../../build/fair-driver-v1/c-transition-probe/diagnostic-summary.json)与[图来源哈希](../../../evidence/fair-driver-v1/load-diagnostic-figures.json)。

## 6．速率扫描与局限：只报告已采样的可行点

{table(['路线','三角落通信筛查均通过的已采样净速率 / Gb/s','解释'],sampled)}

{image('energy-rates','相同净目标的端口能量：黑叉为通信失败，虚线为DC电流精度未达；C体结风险另列，图不构成安全合格能效排名')}
{image('receiver-margins','每个净速率取三角落最差幅度和时序余量；虚线为共同门槛')}

<details><summary>展开全部45点数值（包括失败点）</summary>

{disclosure_table(['case','正向pJ/bit','错误bits','最小距离µA','最小时间ps','通信筛查'],allrows)}
</details>

A在SS/FF即使接收通过，DC电流目标也未达到；尤其SS高档电流更小，不能把由此降低的能量称为同输出性能优势。C的内部体结风险尚未闭合，也不能将低速接收通过写成完整安全合格。

能量随速率提高而降低的一部分原因，是固定参考/辅助电源功率被更多比特分摊；不能只看更低pJ/bit，而忽略该点已经闭眼、出错或违反时序门槛。C的符号率减半并不消除译码路径差异、瞬间误码和三个眼的最小间距约束。

## 7．数值审查、失败与待闭合项目

所有通信从已建立的DC工作点开始，等效光学与接收状态也从初始电流开始。本轮不借此声称上电已经稳定。A独立探针（VIN同时给LED供电，与正式七端口测试台分开）在1µs共同供电斜坡诊断中，两档峰值约449.6µA和1319.3µA；电源全幅后约117µs/41.3µs仍最后一次位于目标±5%区间之外（随后保持在区间内至1ms终点），且XPOUT体结正偏约0.823/0.792V。**A启动未闭合。** 原始失败保留在`build/fair-driver-v1-a-probe/`，定义和精确窗口见A设计说明。

B/C有真实DISABLE/keeper器件，但本轮正常通信固定DISABLE=0，未实现自主POR，也不能把历史受控启动结果移植为当前新网表的通过。逐型号端压通过只是一项模型内筛查，不代表体结注入、ESD、可靠性和流片签核通过。全部45个基线点中，最大已观察体结正偏约0.935V；各实例/角落的具体值保留在summary.json的stress列表中。

为控制存储量，最终矩阵保留**全部原始自适应求解时刻和LED导通电流**，直接送入共同接收器，不作等间隔抽样。七端口能量和全部MOS应力在求解器原始网格计算；正/负功率积分都扣除线性过零的三角形修正。完整内部节点B波形另留作独立对照。曾试用的均匀导出原型保留，但不进入最终矩阵，避免C在同净率下被更粗的导出步长影响。

计算超时属于执行资源限制，不直接判电路失败；原超时日志/回执保留，重跑只延长wall-clock到900s，使用带retry900后缀的新case且不改电路/精度/接收条件。结果表优先引用已完成重跑，并保留执行名称。

源文件、数据帧、模型与接收器均哈希冻结。参数变更或容差控制另起case，不覆盖原结果。能量、接收和步长细化的独立复核与全局v2重分析身份见下方证据文件；分析器通过与电路通过是不同事项。

仍待确认：真实LED的L–I、偏置/温度/电容/载流子寿命；PD/TIA噪声、shot noise、时钟抖动和FEC；DAC/电流镜失配及阵列串扰；上游电源效率和实际可共享参考比例；配对版图的互连、封装、PEX及启动/关断安全。本文不把这些未建模项默认为相同或为零。

### 单因素容差、供电与数值控制

下列结果与45点基线分开：32个TT直流点覆盖VREF±0.2%，B/C的RSET±0.1%，A两只分压下电阻同向±0.1%；未枚举所有电阻的独立组合、温漂或PVT组合。瞬态控制保持原LED/RX：每symbol最大步长40→80、PDK RIN单独res_ss、上游VDD＋50mV周期扰动，以及C的D1相对D0±20ps偏斜。VDD源扰动从200ns起、2ns边沿、20ns宽、800ns周期，经过相同1Ω/2nH和100nF/0.2Ω网络，覆盖训练与验证。每case仍采用同一训练预算，不用验证数据调相。扰动case的端口账本还包含共同100nF去耦的往返充放电，因此必须同时看返回和净能量；它用于扰动响应，不进入稳定供电下的正常通信能效排名。

{table(['控制case','正向pJ/bit','返回pJ/bit','净pJ/bit','错误bits','最小距离µA','最小时间ps','通信筛查'],controlrows)}

数值对照差值均为80相对40；事先设定能量≤0.2%、判决距离≤0.2µA、时间≤20ps、体结峰≤5mV且错误数一致的复核门槛。它检验所报指标的离散敏感性，不新增物理资格。三个数值控制均一致，C在该点仍未达到电流判决余量，不能将数值一致写成电路通过。

{table(['路线','能量变化','距离变化µA','时间变化ps','体结峰变化mV','数值检查'],numericrows)}

<details><summary>展开32个参考/电阻容差DC结果</summary>

{disclosure_table(['case','LED电流µA','相对目标误差'],dctol)}
</details>

完整控制与实际执行身份见[controls-summary.json](../../../evidence/fair-driver-v1/controls-summary.json)。本组测试也未包含真实电源IC效率、噪声、实体接收器或完整容差签核。

## 8．下一步怎样决定架构

先把“目标吞吐＋误差/噪声要求＋电流精度＋启动安全＋面积/电源预算”同时固定，再比较满足约束的端口能量。本轮没有把B选为默认优胜者，也没有把C的较低符号率当作必然优势。A的当前实现需先补跨角落电流控制和启动；B需降低真实参考/dummy开销并检验布局寄生；C需降低内部节点体结正偏、量化负载电容/低电平建立，再验证失配、光学非线性与实体三阈值接收代价。共同方向包括获得偏置相关C与L–I测量；若研究预加重，应先同时限定峰值/平均电流和能量，不能只给某一路线额外驱动预算。

下一阶段应保留这三份独立候选，先按暴露出的限制做单因素修改，随后进行**同等级实际布局与PEX**。已有历史B版图不等于本轮B或C的版图；本轮没有新增GDS、DRC/LVS、PEX、硅或实测光链路。

## 9．来源、证据与复现

LED数值来自[Lin等公开源数据，Zenodo DOI](https://doi.org/10.5281/zenodo.20034288)的I-V.xlsx、Sheet1 A3:B102；本项目冻结的是该曲线的PWL电气模型，见[模型卡与未支持项目](../../../analog/models/measured-led/model-card.json)、[数据署名/许可](../../../analog/models/measured-led/NOTICE.md)和[模型来源锁定](../../../analog/models/measured-led/source-lock.json)。本轮网页访问源数据返回429，未用网页可达性替代已有归档哈希证据。

GF180模型种类参见[GlobalFoundries官方0.18µm、3.3V/6V模型说明](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_1.html)，本轮具体版本以冻结文件SHA为准。03v3按3.63V、06v0按6V的六对绝对端差是本项目筛查规则，不能替代工艺完整SOA/可靠性规范。

- [冻结规格](../../superpowers/specs/2026-10-25-fair-driver-v1.md)；[执行计划](../../superpowers/plans/2026-10-25-fair-driver-v1.md)。
- [当前共同结果JSON](../../../evidence/fair-driver-v1/summary.json)；[A说明](../../../evidence/fair-driver-v1/a-design.md)；[C说明](../../../evidence/fair-driver-v1/c-design.md)。
- [接收合同](../../../evidence/fair-driver-v1/rx-contract.md)；[独立能量/应力审计](../../../evidence/fair-driver-v1/independent-audit.json)；[v1三点独立解析滤波审计](../../../evidence/fair-driver-v1/rx-audit.json)；[最终共同延迟v2合同](../../../evidence/fair-driver-v1/rx-equal-latency-v2-contract.md)；[v2全数据索引](../../../evidence/fair-driver-v1/rx-equal-latency-v2-index.json)；[v2三点独立解析滤波审计](../../../evidence/fair-driver-v1/rx-audit-v2.json)。
- [备份与小输入恢复说明](../../../scripts/backup/fair-driver-20261025/README.md)；[项目交接与验收回执](../../development-handoff.md)。
- [源网表](../../../analog/fair_driver_v1/)；[运行器](../../../scripts/fair_driver_v1/run.py)；[矩阵](../../../scripts/fair_driver_v1/suite.py)；[图/器件哈希清单](../../../evidence/fair-driver-v1/circuit-figure-manifest.json)。

完整矩阵目录：`build/fair-driver-v1/matched-r2`。冻结输入manifest SHA-256：`{e.sha(WORK/'manifest.json')}`。冻结manifest中的source_commit是实验启动时的checkout基线；新增工作源以inputs/execution-sources的SHA为准。最终GitHub交付标签另绑定包含这些源的公开提交，不混为同一身份。每个case保留实际deck、ngspice退出状态/日志、执行器源身份、原始波形与gzip哈希；新压缩波形经解压哈希核对后才移除未压缩副本。

以下命令是**全量归档恢复后**的缓存检查/报告重建；需要inputs、results、waveforms三个分组及report-font，已有case会被跳过，不代表新的独立仿真。只恢复小输入/结果时，应使用备份说明中的独立新work DC smoke，不直接执行全矩阵重分析。

```sh
build/layout/venv/bin/python -m unittest discover -s scripts/fair_driver_v1 -p 'test_*.py' -v
build/layout/venv/bin/python scripts/fair_driver_v1/suite.py --jobs 2 --timeout-s 900
build/layout/venv/bin/python scripts/fair_driver_v1/controls.py --jobs 1
build/layout/venv/bin/python scripts/fair_driver_v1/reanalyze_equal_latency_v2.py --jobs 2 --finalize
build/layout/venv/bin/python scripts/fair_driver_v1/report.py
```

若要从输入产生新的全量实验，应另建版本化work并重新冻结电路/计划/分析分母；不能把复用旧result的命令称为新仿真。本次交付会另做新检出目录的单DC复跑，未承诺第二套全矩阵重跑。

执行前须恢复冻结模型输入与本项目Python环境，`analog/models/pdk-lock.json`仅是模型子集。恢复与远端备份回执另附，不宣称完整物理PDK或跨操作系统签核。
'''
 (DEST/'README.md').write_text(text)
 content=markdown.markdown(text,extensions=['tables','fenced_code','toc'])
 css='''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f7f8f6;color:#203440;font-family:"PingFang SC","Noto Sans CJK SC",sans-serif;font-size:16px;line-height:1.75}main{max-width:1180px;margin:auto;padding:48px 28px 80px}h1,h2,h3{line-height:1.35;font-family:"Tw Cen MT","PingFang SC",sans-serif}h1{font-size:36px;color:#183d48}h2{font-size:25px;margin:48px 0 18px;border-bottom:1px solid #cbd8d8;padding-bottom:12px}h3{font-size:20px;margin-top:30px}p{max-width:94ch}a{color:#147b78;text-underline-offset:3px}strong{font-weight:600}table{border-collapse:collapse;width:100%;font-size:14px;margin:24px 0;line-height:1.65}th{background:#e8efee;text-align:left;color:#174d53}td,th{border-bottom:1px solid #d5dfe0;padding:10px 12px;vertical-align:top}tr:nth-child(even){background:#fff}figure{margin:28px 0;padding:14px;background:#fff;border:1px solid #dce5e4;border-radius:8px}img{width:100%;height:auto;display:block}figcaption{font-size:13px;color:#526a75;margin-top:10px}code{font-family:inherit;font-variant-numeric:tabular-nums;font-size:.91em;background:#eaf0ef;padding:2px 5px;border-radius:3px;overflow-wrap:anywhere}pre{overflow:auto;padding:18px;background:#edf2f1;font-size:14px}summary{cursor:pointer;color:#176b70;font-weight:600;padding:14px;background:#e5eeec}details{margin:24px 0}nav{display:flex;gap:16px;font-size:14px}ul{padding-left:24px} @media(max-width:700px){main{padding:24px 16px}h1{font-size:28px}h2{font-size:22px}table{display:block;overflow:auto;white-space:normal;font-size:13px}td,th{min-width:90px;padding:8px}figure{padding:6px}}@media print{body{background:white;font-size:10.5pt}main{padding:0;max-width:none}h1{font-size:25pt}h2{font-size:15pt}figure{break-inside:avoid}a{color:inherit}details{display:block}nav{display:none}}'''
 (DEST/'index.html').write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>A/B/C同条件MicroLED驱动研究</title><style>'+css+'</style></head><body><main><nav><a href="../architecture-decision-review-20261025/index.html">前一轮证据复盘</a><a href="README.md">Markdown源</a><a href="../../../evidence/fair-driver-v1/summary.json">数值证据</a></nav>'+content+'</main></body></html>')
 print(json.dumps({'DC':len(dc),'RX':len(rx),'failed_communication':nfail,'report':str(DEST/'index.html')},ensure_ascii=False))
if __name__=='__main__':main()
