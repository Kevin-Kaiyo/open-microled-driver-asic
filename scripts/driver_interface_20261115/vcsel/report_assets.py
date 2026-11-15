#!/usr/bin/env python3
"""Source-bound compact comparison and figures; never modify simulation results."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.dont_write_bytecode=True
import run
ROOT=run.ROOT;OUT=ROOT/'docs/research/driver-interface-20261115/assets';EV=run.EV
plt.rcParams.update({'font.family':['Arial Unicode MS'],'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','axes.unicode_minus':False})
NAMES={'ideal69':'原69MOS / 理想源','ideal73':'原73MOS / 理想源','single-phy4':'有限CMOS 4/8µm','single-phy12':'有限CMOS 12/24µm','single-phy4-r25k':'4/8µm + 下拉25kΩ','double-phy4':'原两级 + 有限CMOS*'}
COLORS={'ideal69':'#738597','ideal73':'#b5bdc4','single-phy4':'#b97840','single-phy12':'#416da1','single-phy4-r25k':'#148477','double-phy4':'#976a92'}
def row(p,name):
 a=run.read(p/'analysis.json');m=run.read(p/'manifest.json');f=a['pathways']['actual_graph_5GHzRX'];r=run.read(p/'result.json')
 o=dict(candidate=name,label=NAMES[name],case=str(p.relative_to(ROOT)),net_Gbps=a['net_Gbps'],steps_per_UI=a['steps_per_UI'],holdout=a.get('config',{}).get('holdout',False),MOS=len(m['devices']),receiver_errors=f['errors'],amplitude_uAeq=f['worst_signed_margin_uAeq'],timing_UI=f['one_sided_margin_UI'],timing_ps=f['one_sided_margin_ps'],receiver_delay_UI=f['delay_UI'],receiver_delay_ps=f['delay_ps'],screen_pass=a['combined_screen_pass'],I_range_mA=a['observed']['electrical_current_range_mA'],terminal_peak=a['observed']['terminal_peak'],max_body_forward_V=a['observed']['max_body_forward_V'],energy_pJ=a['source_energy_pJ_per_attempted_net_bit'],energy_by_source=a['energy_by_source_pJ_per_attempted_net_bit'],stages=a['stages'],analysis_sha256=run.sha(p/'analysis.json'),manifest_sha256=run.sha(p/'manifest.json'),waveform=r['waveform'])
 o['within_current_domain']=a['observed']['within_calibrated_electrical_and_optical_current_range'];o['receiver_result_validity']='Within declared model current domain' if o['within_current_domain'] else 'Diagnostic only: current exceeded calibrated model domain; do not interpret as validated optical performance'
 if 'interface_observed' in a:
  o['interface_observed']=a['interface_observed'];dcs=[run.read(p.parent/f'DC-L{i}/result.json') for i in [0,1]]
  pdc=np.mean([d['source_power_W']['VPHY'] for d in dcs]);pv=a['energy_by_source_pJ_per_attempted_net_bit']['VPHY']['net']*a['net_Gbps']*1e-3
  o['VPHY_static_dynamic_W']={'mean_two_DC_states_W':float(pdc),'frame_average_net_W':pv,'frame_average_minus_DC_W':float(pv-pdc),'scope':'DC-state mean is a reference partition, not exact per-device dissipation. Finite frame begins in OP; no continuous steady-state claim.'}
  o['DC_high_nodes_V']={k:dcs[1]['nodes_final_V'][k] for k in ['v(d_src)','v(xdrv.di)','v(vphy)']}
 return o
def collect():
 rows=[]
 for name,folder in [('ideal69',ROOT/'build/driver-methods-20261111/VCSEL/vc-single-r150'),('ideal73',ROOT/'build/ab-improvement-20261111/VCSEL/vc-atten50-steer20')]:
  for rate in [6.4,8.8]:
   p=folder/(f'net{rate:g}-edge20-s40' if name=='ideal73' else f'net{rate:g}-s40')
   if (p/'analysis.json').exists():rows.append(row(p,name))
 for p in sorted(run.BUILD.glob('*/*/analysis.json')):rows.append(row(p.parent,p.parent.parent.name))
 return rows
def finish(fig,name):
 OUT.mkdir(parents=True,exist_ok=True);fig.savefig(OUT/(name+'.svg'),bbox_inches='tight');fig.savefig(OUT/(name+'.png'),bbox_inches='tight',dpi=170);plt.close(fig)
def comparison(rows):
 selected=[r for r in rows if r['steps_per_UI']==40 and not r['holdout'] and r['net_Gbps'] in [6.4,8.8]]
 fig,axs=plt.subplots(1,3,figsize=(13,4.4));metrics=[('timing_UI','单侧时间余量 / UI',.37),('amplitude_uAeq','最差幅度距离 / µAeq',7.5),('energy_pJ','全源供出能量 / pJ·bit⁻¹',None)]
 for ax,(key,label,limit) in zip(axs,metrics):
  for name in NAMES:
   rs=sorted([r for r in selected if r['candidate']==name],key=lambda q:q['net_Gbps'])
   if rs:ax.plot([r['net_Gbps'] for r in rs],[r[key]['positive'] if key=='energy_pJ' else r[key] for r in rs],marker='o',label=NAMES[name],color=COLORS[name])
  if limit is not None:ax.axhline(limit,color='#a64d41',ls='--',lw=1);ax.text(6.42,limit,'门槛',fontsize=9,color='#a64d41',va='bottom')
  ax.set(xlabel='净吞吐目标 / Gb·s⁻¹',ylabel=label);ax.grid(alpha=.15)
 axs[0].legend(fontsize=8,loc='lower left');fig.suptitle('固定 VCSEL 负载、3/7mA 与 5GHz RX：有限输入级改变余量和能量',y=1.02)
 fig.text(.5,-.035,'未过门槛的 pJ/b 仅为尝试发送能量；0/4096 错误不等于满足余量，更不是实测 BER。',ha='center',fontsize=10)
 fig.text(.5,-.09,'* 紫色点超过光源 7.5mA 模型域，仅作诊断。连线仅引导阅读，中间速率未验证。',ha='center',fontsize=9)
 fig.tight_layout();finish(fig,'vcsel-interface-comparison')
def energy(rows):
 rs=[r for r in rows if r['net_Gbps']==6.4 and r['steps_per_UI']==40 and not r['holdout']]
 fig,(ax,bx)=plt.subplots(1,2,figsize=(12,4.8),gridspec_kw={'width_ratios':[1.65,1]})
 groups=[('VLASER',['VLASER'],'#314c60'),('内部缓冲 VDD',['VDD'],'#54799a'),('参考边界',['VREF','VSET','VREGSET'],'#a9bdca'),('上游 VPHY',['VPHY'],'#148477'),('命令 VD+VDB',['VD','VDB'],'#cf915a')]
 bottom=np.zeros(len(rs));x=np.arange(len(rs))
 for label,ports,color in groups:
  v=np.array([sum(r['energy_by_source'].get(p,{}).get('positive',0) for p in ports) for r in rs]);ax.bar(x,v,bottom=bottom,label=label,color=color);bottom+=v
 ax.set_xticks(x,[r['label'].replace(' / ','\n') for r in rs],fontsize=9,rotation=15);ax.set_ylabel('供出能量 / pJ·bit⁻¹');ax.legend(fontsize=9,ncol=2);ax.grid(axis='y',alpha=.15)
 finite=[r for r in rs if 'VPHY_static_dynamic_W' in r];x=np.arange(len(finite))
 dc=[r['VPHY_static_dynamic_W']['mean_two_DC_states_W']*1e3 for r in finite];dyn=[r['VPHY_static_dynamic_W']['frame_average_minus_DC_W']*1e3 for r in finite]
 bx.bar(x,dc,label='DC 两状态均值',color='#7c9c9a');bx.bar(x,dyn,bottom=dc,label='帧平均 − DC',color='#148477');bx.set_xticks(x,[r['label'] for r in finite],rotation=20,fontsize=9);bx.set_ylabel('上游 VPHY 净功率 / mW');bx.legend(fontsize=9);bx.grid(axis='y',alpha=.15)
 fig.suptitle('6.4Gb/s：把上游供电与命令栅充电一起计入');fig.tight_layout();fig.text(.5,-.035,'* 旧双级接有限输入后电流超模型域。所有柱形均为尝试发送；帧平均减DC不是完整热耗散。',ha='center',fontsize=9);finish(fig,'vcsel-interface-energy')
def waveforms(rows,rate=8.8):
 rs=[r for r in rows if r['candidate'] in ['ideal69','single-phy4','single-phy12','single-phy4-r25k'] and r['net_Gbps']==rate and r['steps_per_UI']==40 and not r['holdout']]
 fig,allaxs=plt.subplots(5,1,figsize=(12,9.6),sharex=True,gridspec_kw={'height_ratios':[.45,1,1,1,1]});cmd=allaxs[0];axs=allaxs[1:]
 for r in rs:
  p=ROOT/r['case'];e=run.read(p/'excerpt.json');x=np.asarray(e['time_UI']);color=COLORS[r['candidate']]
  if r==rs[0]:cmd.step(np.arange(17),e['bits']+[e['bits'][-1]],where='post',color='#233e4e');cmd.set(yticks=[0,1],ylabel='命令位',ylim=(-.15,1.15));cmd.grid(alpha=.15)
  for ax,k in zip(axs,['pin_V','gate_V','i_mA','actual_graph_5GHzRX']):ax.plot(x,e[k],color=color,lw=1.4,label=r['label'])
 for ax,label in zip(axs,['DI−DBI / V','GP−GN / V','光源电流 / mA','固定光模型 + RX / µAeq']):ax.set_ylabel(label);ax.grid(alpha=.2);ax.set_xlim(0,10)
 axs[0].legend(fontsize=9,ncol=2);axs[3].axhline(62.5,color='#a64d41',ls='--',lw=1)
 axs[2].axhline(7.5,color='#a64d41',ls='--',lw=1);axs[3].set_xlabel('验证位 576 开始的时间 / UI（未经波形平移）')
 fig.suptitle(f'净 {rate:g}Gb/s 的输入、换流栅、光源电流与接收波形');fig.tight_layout();finish(fig,'vcsel-interface-waveforms')
def input_burden(rows):
 ep=EV/'vcsel-interface-edges.json'
 if not ep.exists():return
 edges=run.read(ep)['rows'];names=['single-phy4','single-phy12','single-phy4-r25k'];rs=[next(r for r in rows if r['candidate']==n and r['net_Gbps']==8.8 and r['steps_per_UI']==40 and not r['holdout']) for n in names]
 fig,axs=plt.subplots(1,3,figsize=(13,4.5));x=np.arange(3);w=.32;labels=['4/8 µm\n2.5kΩ','12/24 µm\n2.5kΩ','4/8 µm\n25kΩ']
 for off,node,label,c in [(-w/2,'v(d_src)','d_src','#54799a'),(w/2,'v(xdrv.di)','DI','#148477')]:axs[0].bar(x+off,[r['DC_high_nodes_V'][node] for r in rs],width=w,label=label,color=c)
 axs[0].set(ylabel='DC 高电平 / V',ylim=(0,3.6));axs[0].axhline(3.3,color='#738597',ls='--',lw=1);axs[0].legend(fontsize=10)
 for off,direction,label,c in [(-w/2,'data_rise','10–90% 上升','#54799a'),(w/2,'data_fall','90–10% 下降','#148477')]:
  values=[]
  for n in names:
   r=next(e for e in edges if e['candidate']==n and e['net_Gbps']==8.8);node=next(z for z in r['nodes'] if z['node']=='v(xdrv.di)');values.append(node['edges'][direction]['edge_ps_quantiles']['median'])
  axs[1].bar(x+off,values,width=w,label=label,color=c)
 axs[1].axhline(1e3/10.175,color='#a64d41',ls='--',lw=1);axs[1].text(-.4,1e3/10.175+3,'8.8Gb/s: UI = 98.28ps',color='#a64d41',fontsize=9);axs[1].set_ylabel('DI 原生边沿 / ps');axs[1].legend(fontsize=9)
 values=[r['interface_observed']['source_currents']['VD']['source_peak_mA'] for r in rs];axs[2].bar(x,values,color=[COLORS[n] for n in names]);axs[2].set_ylabel('理想命令 VD 峰值供出 / mA')
 for i,v in enumerate(values):axs[2].text(i,v+.1,f'{v:.3f}',ha='center',fontsize=10)
 for ax in axs:ax.set_xticks(x,labels,fontsize=10);ax.grid(axis='y',alpha=.15)
 fig.suptitle('更强的上游恢复短脉冲，但把更大的栅充电负担交给命令端');fig.tight_layout();finish(fig,'vcsel-interface-input-burden')
def main():
 rows=collect();run.emit(EV/'vcsel-interface-comparison.json',{'schema':'vcsel-interface-comparison-v1','rows':rows,'metadata_note':'Historical case/method_config keys in cloned manifests retain baseline provenance. Current interface_config and candidate_spec, deck bytes, execution snapshots and hashes govern each new case. source_currents.sink_peak_mA is signed max(-I); negative means no sink current, not negative returned energy. Positive/returned energy is separately clipped and integrated.','limits':['Finite CMOS engineering model, not FPGA/LVDS/CML/PAD/ESD compliance.','Energies refer to a finite OP-initialized4736bit frame/4096attempted payload bits; no VCSEL continuous-operation closure.','Current range2–7.5mA and all MOS terminal/body screens remain binding; no threshold tuning.','No new VCSEL layout/PVT/EM/IR/PEX/physicalBER/silicon.']})
 comparison(rows);energy(rows);waveforms(rows);input_burden(rows)
 print('Rendered',len(rows),'cases')
if __name__=='__main__':main()
