#!/usr/bin/env python3
"""Render bounded final NRZ tables and charts from frozen compact evidence."""
from pathlib import Path
import csv, hashlib, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/nrz-b-reference-power-20261024'
E=ROOT/'evidence/nrz-reference-v2'
FONT=ROOT/'build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf'
font_manager.fontManager.addfont(str(FONT))
plt.rcParams.update({'font.family':'Noto Sans CJK SC','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,'svg.fonttype':'path'})
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(headers, rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def get(rows,kind,bit=None):
 found=[r for r in rows if r['kind']==kind and (bit is None or r.get('dc_bit')==bit)]
 assert len(found)==1,(kind,bit,len(found));return found[0]
def main():
 paths=[E/f'selected-final-r2-{s}.json' for s in ['dc','startup','slow','nrz']]
 dc,st,slow,nrz=[json.loads(p.read_text())['rows'] for p in paths]
 assert [len(x) for x in [dc,st,slow,nrz]]==[112,11,5,10]
 assert all(r['simulation_ok'] and r['analysis_ok'] for r in dc+st+slow+nrz)
 failed_dc=[r for r in dc if abs(r['LED_current_error_percent'])>5]
 final_rows=[]
 for k,label in [('DC_TT','TT / 27°C'),('DC_SS','SS / 125°C'),('DC_FF','FF / −40°C'),('DC_SS_joint','SS 宽容差联合'),('DC_FF_joint','FF 宽容差联合'),('DC_SS_precision_joint','SS 精密 RSET 联合'),('DC_FF_precision_joint','FF 精密 RSET 联合')]:
  lo,hi=get(dc,k,0),get(dc,k,1)
  final_rows.append([label,f"{lo['LED_current_A']*1e6:.3f}",f"{hi['LED_current_A']*1e6:.3f}",f"{lo['LED_current_error_percent']:+.3f}% / {hi['LED_current_error_percent']:+.3f}%",'通过' if max(abs(lo['LED_current_error_percent']),abs(hi['LED_current_error_percent']))<=5 else '未通过'])
 selected=[('DC_TT','TT'),('DC_SS','SS'),('DC_FF','FF'),('DC_SS_joint','SS 宽容差'),('DC_FF_joint','FF 宽容差'),('DC_SS_precision_joint','SS 精密 RSET'),('DC_FF_precision_joint','FF 精密 RSET')]
 fig,ax=plt.subplots(figsize=(10,4.7),layout='constrained');x=np.arange(len(selected))
 for bit,color,label in [(0,'#247a7b','低电流 I0，目标 25 µA'),(1,'#ad713d','高电流 I1，目标 100 µA')]:
  bars=ax.bar(x+(bit-.5)*.36,[get(dc,k,bit)['LED_current_error_percent'] for k,_ in selected],.36,color=color,label=label)
  ax.bar_label(bars,fmt='%.2f',fontsize=8,padding=3)
 ax.axhspan(-5,5,color='#c5d8d0',alpha=.20);ax.axhline(5,c='#a83e43',ls='--');ax.axhline(-5,c='#a83e43',ls='--');ax.set_xticks(x,[l for _,l in selected]);ax.set_ylabel('相对目标电流的误差 (%)');ax.set_ylim(-7,8);ax.legend(frameon=False,ncol=2);ax.set_title('最终 21 MOS 实际 PEX：端压通过 ≠ 电流精度通过');ax.grid(axis='y',alpha=.2)
 for ext in ['png','svg']:fig.savefig(OUT/'figures'/('rset-tolerance.'+ext),dpi=160)
 plt.close(fig)
 oldp=ROOT/'evidence/highspeed-nrz-robustness/summary-verified.json';r1p=E/'selected-r1-summary.json'
 old=json.loads(oldp.read_text())['selected']['rows'];r1=json.loads(r1p.read_text())['rows'];ek='rail_plus_DATA_positive_draw_fJ_per_gross_bit';comparisons=[]
 for lab,oldkind in [('TT','TT'),('SS','SSminus50'),('FF','FFplus50')]:
  a=next(r for r in old if r['route']=='B' and r['kind']==oldkind and r['rate_Gbps']==.5);b=get(r1,lab+'_nrz');c=get(nrz,'NRZ_'+lab)
  assert a['corner']==b['corner']==c['corner'] and a['temp_C']==b['temp_C']==c['temp_C'] and a['vdd_V']==b['vdd_V']==c['vdd_V']
  for rev,r in [('旧理想 VDUMMY',a),('首版参考 + LDO（启动失败）',b),('选定参考 + RAW 供电',c)]:comparisons.append({'condition':lab,'revision':rev,'energy_pJ_per_bit':r[ek]/1000,'vertical_margin':r['threshold_margin_normalized'],'timing_margin_UI':r['timing_min_margin_ui'],'errors':r['errors'],'result_json':r['result_json']})
 fig,axes=plt.subplots(1,2,figsize=(11,4.7),layout='constrained');x=np.arange(3);w=.25
 for j,(label,col) in enumerate([('旧理想 VDUMMY','#98a7b0'),('首版参考 + LDO（启动失败）','#bd8b62'),('选定参考 + RAW 供电','#247a7b')]):
  rows=[r for r in comparisons if r['revision']==label]
  for a,key in zip(axes,['energy_pJ_per_bit','vertical_margin']):
   bars=a.bar(x+(j-1)*w,[r[key] for r in rows],w,color=col,label=label);a.bar_label(bars,fmt='%.2f',padding=3,fontsize=8)
 for a in axes:a.set_xticks(x,['TT / 27°C','SS / 125°C','FF / −40°C']);a.grid(axis='y',alpha=.18);a.set_axisbelow(True)
 axes[0].set_ylabel('全电源端口 + DATA 正向能量 (pJ/bit)');axes[1].set_ylabel('归一化接收阈值余量');axes[0].set_ylim(0,7.5);axes[1].set_ylim(0,.34);axes[0].legend(frameon=False,fontsize=8);fig.suptitle('相同 0.5 Gb/s、MicroLED 与接收条件；能量不含外部参考内部 Iq')
 for ext in ['png','svg']:fig.savefig(OUT/'figures'/('energy-comparison.'+ext),dpi=160)
 plt.close(fig)
 with (OUT/'figures/energy-comparison.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=comparisons[0]);w.writeheader();w.writerows(comparisons)
 olddctable=table(['同条件','旧理想 VDUMMY + RREF，I0 / I1 µA','新实际参考，I0 / I1 µA'],[[lab,' / '.join(f"{get(r1,'old_'+lab,b)['LED_current_A']*1e6:.3f}" for b in [0,1]),' / '.join(f"{get(dc,'DC_'+lab,b)['LED_current_A']*1e6:.3f}" for b in [0,1])] for lab in ['TT','SS','FF']])
 labels={'NRZ_TT':'TT 名义','NRZ_SS':'SS 慢热','NRZ_FF':'FF 快冷','NRZ_SS_precision_joint':'SS 精密 RSET 联合','NRZ_FF_precision_joint':'FF 精密 RSET 联合','NRZ_FF_VRAWpulse':'FF：RAW +250 mV 脉冲','NRZ_FF_VLEDpulse':'FF：VLED +50 mV 脉冲','NRZ_FF_VDDpulse':'FF：VDD +50 mV 脉冲','NRZ_FF_supply_package':'FF：供电与 LED 封装组合','NRZ_FF_numerical':'FF：更紧数值配置'}
 nrztable=table(['实际 PEX 测试点','错码 / 511','接收阈值余量','时序余量 UI','正向能量 pJ/bit','型号端压最小余量 V'],[[labels[r['kind']],r['errors'],f"{r['threshold_margin_normalized']:.4f}",f"{r['timing_min_margin_ui']:.4f}",f"{r[ek]/1000:.4f}",f"{r['minimum_device_specific_margin_V']:.4f}"] for r in nrz])
 powerpath=E/'power-dc-r2.json';power=json.loads(powerpath.read_text())['rows'];pw=next(r for r in power if r['corner']=='typical' and r['bit']==1)['source5V_allocated_power_W']
 pulse=get(nrz,'NRZ_FF_VRAWpulse');pulsepath=ROOT/pulse['analysis_json'];pulseenergy=json.loads(pulsepath.read_text())['transient']['energy']['rail_plus_ideal_DATA_total']
 startlabels={'startup_TT':'TT 正常启动','startup_SS':'SS 正常启动','startup_FF':'FF 正常启动','startup_late_anchor':'基准迟到，正确延迟释放','startup_early_release_NEG':'基准迟到，错误提前释放','startup_FF_comp0.8':'FF：补偿 -20%','startup_FF_comp1.2':'FF：补偿 +20%','startup_FF_passive_extreme':'FF：去耦与 keeper 应力','restart_FF_residual_LED_anchor':'FF：保留 LED 电源的重启','startup_FF_numerical':'FF：更紧数值配置','startup_FF_comp_package':'FF：补偿外引 R/L'}
 starttable=table(['启动条件','保持峰值 µA','完整峰值 µA','释放到稳定 ns','型号端压余量 V','原判据及补充检查'],[[startlabels[r['name'].split('-0.5G')[0].removeprefix('REFERENCE-B-')],f"{r['hold_peak_A']*1e6:.4f}",f"{r['current_peak_A']*1e6:.3f}",f"{r['release_to_settled_s']*1e9:.2f}",f"{r['minimum_device_margin_V']:.4f}",('功能/绝对端压满足，体结未闭合' if 'restart_FF' in r['name'] else '原判据通过') if r['startup_passed'] else '失败：负控制'] for r in st])
 dcfailed=table(['失败 DC 条件','逻辑位','电流误差'],[[r['kind'],r['dc_bit'],f"{r['LED_current_error_percent']:+.4f}%"] for r in failed_dc])
 # Acceptance counts deliberately preserve failures. Device screening is not current accuracy.
 metrics={'dc_cases':len(dc),'dc_current_failures':len(failed_dc),'dc_device_failures':sum(not r['device_specific_screen_passed'] for r in dc),'startup_passed':sum(r['startup_passed'] for r in st),'startup_negative_failures':sum(not r['startup_passed'] for r in st),'slow_passed':sum(r['slow_passed'] for r in slow),'nrz_passed':sum(r['combined_screen_passed'] for r in nrz),'nrz_cases':len(nrz),'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in paths+[oldp,r1p,powerpath,pulsepath]},'generator_sha256':sha(Path(__file__))}
 (OUT/'figures/results-data.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n')
 text=f'''## 本轮结论与决策

**晶体管参考、受控启动和真实联通版图已经接上原 B 数据通路。** 0.5 Gb/s 是本轮固定验证点；本轮没有重新搜索最大速率。采用 10 MOS 电流反馈参考、两只受外部 DISABLE 控制的保护管与 RAW 5 V dummy 供电。外部精密电压基准尚未片内实现。

112 个 DC 点全部求解，器件端压筛查全部通过，但 **{len(failed_dc)} 个电流精度点失败**，包括宽容差联合角和 ±5% 负控制。11 个启动/重启点中 {metrics['startup_passed']} 个满足原功能与绝对端压条件；其中残余电源重启仍有 **0.747 V 体结正向偏置，尚未闭合**。提前解除关断负控制同时违反准备时间与 03v3 端压条件；5 个慢时标控制通过。10 个固定速率通信测试点中 **{metrics['nrz_passed']} 个通过** 接收与端压联合筛查。详细数据如下，失败没有从分母中删除。

目前的工程决策是：保留 RAW 供电与 150 pF 补偿作为正常启动及通信研究基线，RSET 采用 ±0.1% / ±25 ppm/°C 的研究规格，外部控制必须在参考建立后才解除 DISABLE。下一步优先实现参考就绪检测、掉电时内部补偿节点的复位/隔离并检查结电流；当前不能宣布残余电源重启已经可靠。

## DC：电阻规格如何改变实际 LED 电流

先看参考架构修改的实际收益：旧参考电阻从理想 3.3 V 供电，电流随 BIAS MOS 的 VGS 改变；新参考对 RSET 电压闭环控制。下面保持对应 MOS 角、温度、数字电源与 LED 负载。三条件下，高电流的误差范围由约 −8.06%～+7.71%，缩小到 −2.55%～+3.37%，代价是后文所列真实参考静态功耗。

{olddctable}

目标 I0/I1 为 25/100 µA，误差预算均为 ±5%。联合条件同时改变 RSET、RDUMMY、外部基准与 RAW；SS/FF 是指定组合，不是完整笛卡尔积。VSET 分压误差、100 Ω 源阻抗等另作独立控制，未声称全部极值已经同时叠加。

{table(['条件','I0 µA','I1 µA','相对目标误差 I0 / I1','±5% 判定'],final_rows)}

<figure><a href="figures/rset-tolerance.svg"><img src="figures/rset-tolerance.svg" alt="精密与宽容差设定电阻下的高低电流误差"></a><figcaption>阴影是 ±5% 研究预算。FF 宽容差联合点越界；收紧 RSET 后回到预算内。各角点使用同一标称 20 kΩ，没有逐点校准。</figcaption></figure>

<details><summary>查看全部 4 个未通过电流精度的 DC 点</summary>

{dcfailed}

</details>

完整数据：[112 点 DC](../../../evidence/nrz-reference-v2/selected-final-r2-dc.json)。旧分析字段 `combined_screen_passed` 在 DC 中只代表器件端压；本报告另算电流误差，避免把两个判据混淆。

## 启动：保护作用、代价与失败边界

DISABLE 高时，MDIS 把 BIAS 钳到地，MK 接通 1.8 MΩ 泄放，避免 OUT 悬空；低时，两管关闭，正常低电平不再附加约 1 µA 的 keeper 电流。启动保持仍有约 1.3 µA 电流，合同为 ≤2 µA，**不是零电流关断**。正常释放后须在 2 µs 内进入 100 µA ±5%，完整峰值须 ≤125 µA。

正常冷启动：外部电源与参考用 1 µs 斜坡建立，20 µs 后释放。迟到参考在 30 µs 开始时，释放也推迟到 50 µs。若仍在 20 µs 提前释放，实际 21 MOS PEX 中最大 03v3 端差约 **4.862 V**，超过 3.63 V 项目筛查，并延迟约 13.53 µs 才进入目标带。这是尚未实现自主 POR/ready 检测的实际风险，不能写成任意上电顺序安全。

{starttable}

<figure><img src="electrical-figures/selected-startup.svg" alt="最终21MOS实际PEX的三个角点完整启动及释放局部波形"><figcaption>上图为 100 µs 完整窗口，下图放大释放附近。波形来自全分辨率结果；本轮的 20 µs 外部等待是一项明确接口条件。</figcaption></figure>

<figure><img src="electrical-figures/startup-sequencing-control.svg" alt="参考迟到时正确延迟释放和错误提前释放的端电压及电流"><figcaption>左：参考 30 µs 到、50 µs 释放；右：参考仍在 30 µs 到，却提前于 20 µs 释放。右图 OUT 悬空期间 03v3 端压越界。图中 anchor 为外部电压基准，DISABLE 为外部禁止信号；这两种时序故意不同。</figcaption></figure>

最后两行分别检查更紧数值配置、补偿外引 1 Ω / 5 nH 与 0.5 Ω ESR；不能外推为全部启动与通信矩阵都覆盖了补偿引脚寄生。完整数据：[启动/重启](../../../evidence/nrz-reference-v2/selected-final-r2-startup.json)。

### 补充复审：残余电源重启尚未闭合

当 VLED 与外部基准仍供电、RAW 在 20–21 µs 从 5 V 降到 0 V 时，DISABLE 已经置高，但它只处理 BIAS 与 OUT，没有主动复位内部 IN2。原 IPD2 的扩散区在约 21.174 µs 仍为 0.749006 V，nwell 仅为 0.002357 V，形成 **0.746649 V 正向结压**。超过 0.7 V 的插值持续时间约 1.400 µs；0.7 V 仅用于描述波形，不是新声明的 foundry 允许值。

<figure><img src="figures/body-junction-powerdown.svg" alt="外部补偿储能在供电掉电时使PMOS扩散区阱结正向偏置的局部等效图"><figcaption>图示是对已观察波形的机制解释。扩散区与阱电压已直接核对；储能路径的完整电流分解仍待专门实验。</figcaption></figure>

这里原功能/六对绝对端压判据通过，仍不能排除衬底/阱注入风险。原始波形没有保存该结电流，不能由电压单独宣称具体注入电荷、闩锁或寿命结果。本轮把它列为独立未闭合项；不能用“最后电流恢复了”覆盖这个问题。[带时间与节点定位的补充审查](../../../evidence/nrz-reference-v2/restart-body-review.json)

## 慢时标反馈与快数据通路分别验收

最终实际 PEX 的局部双注入估计，TT/SS/FF 的交越频率约 450.4/283.5/668.7 kHz，相位裕量约 72.96°/78.34°/66.25°；闭环与注入工作点最大差约 3.59×10⁻¹¹。它是局部环路估计，需结合 100 µs 启动与阶跃波形理解。

<figure><img src="electrical-figures/selected-loop.svg" alt="最终实际PEX三个工艺温度角的局部反馈频率响应"><figcaption>实际 21 MOS PEX，DATA 高低分别检查。该估计不是严格多环路稳定性或 foundry 签核。</figcaption></figure>

<figure><img src="electrical-figures/compensation-control.svg" alt="相同前布局电路仅改变补偿的振荡对照"><figcaption>用于解释机理的单因素控制：同一 11 MOS 前布局候选、同一 10 MΩ keeper，仅改补偿。它支持修正方向，不冒充最终 21 MOS PEX 结果。</figcaption></figure>

FF 的 RAW 5→4.75→5 V、10 ns 边沿测试中，LED 电流范围为 98.01–108.81 µA，2 µs 后相对 100 µA 的误差不超过 3.413%。RAW 端扰动首先改变供电侧端压，反馈随后恢复；这与数据通路每 2 ns 转向一次是不同时间尺度。[5 点慢时标数据](../../../evidence/nrz-reference-v2/selected-final-r2-slow.json)保留每项峰值与晚期波动。

## 相同接收条件下，能量和余量怎样变化

<figure><a href="figures/energy-comparison.svg"><img src="figures/energy-comparison.svg" alt="相同速率及接收条件下原理想供电首版LDO及最终RAW供电的能量比较"></a><figcaption>旧版理想偏置不含真实参考内部代价；首版 LDO 即使短通信窗口零错码，仍因启动及长时波动被拒绝。完整端口能量逐源积分，不能据此宣布系统能效最优。</figcaption></figure>

新增能量主要花在哪里？另外对六个相同 DC 工作点增加内部电流观测，LED 电流与原结果差为 0 A。TT 的 RAW 5 V 分配中，OTA 控制支路约 **{pw['OTA_control']*1e6:.2f} µW**，检测参考支路约 **{pw['sense_reference']*1e6:.2f} µW**，输出参考支路约 **{pw['output_reference']*1e6:.2f} µW**；三者合计约 **{sum(pw[k] for k in ['OTA_control','sense_reference','output_reference'])*1e6:.2f} µW**，在 0.5 Gb/s 下约 1.40 pJ/bit。因而下一轮降低参考 OTA 偏置电流值得研究，但每次都要重新检查稳定性和启动。这里按电源侧 MOS 漏电流分配预算，模型体端电流等造成约 0.09–0.17 µW 闭合残差，已明列；没有强迫分支和相等。[观测原始数据](../../../evidence/nrz-reference-v2/power-dc-r2.json)

{nrztable}

**扰动行的能量不能作为正常通信能耗。** RAW pulse 是 5→5.25 V、2 ns 边沿、每 254 ns 重复且高态 64 ns 的供电应力，会反复给 100 nF 输入电容充放电。这个窗口的全源正向取能 **{pulseenergy['positive_draw_J_per_gross_bit']*1e12:.2f} pJ/bit**、返还 **{pulseenergy['returned_J_per_gross_bit']*1e12:.2f} pJ/bit**、净取能 **{pulseenergy['net_J_per_gross_bit']*1e12:.2f} pJ/bit**；返还给理想端口的能量不代表实际电源能全部回收。正常三 PVT 的能量对照图仅用没有该扰动的案例。

接收阈值余量以固定 75 µA 高低电流跨度归一化；时序余量单位 UI，0.5 Gb/s 时 1 UI = 2 ns。阈值 62.5 µA、200 ps 光学一阶响应、1 GHz RX、训练与 511 位验证序列保持。供电 pulse 是预声明的局部端口扰动，package 行叠加指定供电/回流/LED R/L；不是完整封装场解。0/511 仅是该有限序列的观察，不是 BER 或最大速率保证。

完整记录：[10 点 NRZ](../../../evidence/nrz-reference-v2/selected-final-r2-nrz.json)、[绘图及汇总输入 SHA](figures/results-data.json)。器件端压按 03v3 的 3.63 V、06v0 的 6.0 V 分开筛查，都是项目研究门槛；未完成寿命、SOA 或 ESD 资格验证。
'''
 (OUT/'results.md').write_text(text)
 print(json.dumps(metrics,ensure_ascii=False))
if __name__=='__main__':main()
