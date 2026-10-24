#!/usr/bin/env python3
"""Compact source-backed evidence index; original and failed records retained."""
import csv,json
from pathlib import Path
import run as r
import validate as v
base=r.ROOT/'build/highspeed-nrz-robustness';final=base/'selected-a8-b58-r4'
worknames=['baseline-r1','hv-r1','hv-short-r2','final-hv-r1','final-hv-a8-b58-r2','final-hv-ties-r3','selected-a8-b58-r4']
summaries={}
for name in worknames:
 w=base/name
 if (w/'manifest.json').exists():summaries[name]=v.summarize(w)
rows=summaries['selected-a8-b58-r4']['rows'];old=summaries['baseline-r1']['rows']
def pick(route,rate,corner,vdd,kind=None):
 found=[x for x in rows if x['route']==route and x['rate_Gbps']==rate and x['corner']==corner and abs(x['vdd_V']-vdd)<1e-9 and not x.get('rail_offsets_V') and not x.get('rail_profiles') and not x.get('supply_package') and 'dc_bit' not in x and x.get('steps_per_ui')==40 and (not kind or x['kind']==kind)]
 return found[0] if found else None
same=[]
for label,co,vd in [('TT','typical',3.3),('SSminus50','ss',2.95),('FFplus50','ff',3.65)]:
 a=pick('A',.4,co,vd);b=pick('B',.4,co,vd)
 same.append({'condition':label,'A':a,'B':b,'same_rate_Gbps':.4,'both_comparison_and_device_screens_passed':bool(a and b and a.get('combined_screen_passed') and b.get('combined_screen_passed'))})
boundary=[x|({'dc_threshold_feasible': (x['LED_current_A']>62.5e-6 if x['dc_bit']==1 else x['LED_current_A']<62.5e-6),'dc_functional_claim':'Static threshold feasibility only; not transient receiver pass'} if 'dc_bit' in x else {}) for x in rows if 'joint_SSmin' in x['kind']]
package=[x for x in old+rows if x.get('supply_package')]
record={'scope':'FrozenLED/RX electrical-proxy experiments; no optical BER, foundry reliability, 3D substrate or tapeout closure.','baseline':summaries['baseline-r1'],'selected':summaries['selected-a8-b58-r4'],'selected_layout_sources':json.loads((final/'manifest.json').read_text())['variants'],'same_rate_energy':same,'joint_supply_boundary':boundary,'supply_return_package':package,'iteration_inventory':{k:{kk:s[kk] for kk in ['work','count','missing','failed_simulations','screen_failures','administrative_interrupted_cases','superseded_plan_files']} for k,s in summaries.items()},'sampler_diagnostic':'evidence/highspeed-nrz-robustness/sampler-diagnostic.json','administrative_and_storage_records':['evidence/highspeed-nrz-robustness/lock-policy-change.json','evidence/highspeed-nrz-robustness/storage-budget-extension-8g.json'],'provenance_correction':'Baseline early on-disk analyzer-hash weakness corrected by retained-raw analysis-verified.json readback; original analyses retained.'}
r.emit(r.EVIDENCE/'summary.json',record)
allrows=[x|{'work_variant':name} for name,s in summaries.items() for x in s['rows']]
with (r.EVIDENCE/'all-cases.csv').open('w',newline='') as f:
 fields=list(dict.fromkeys(k for x in allrows for k in x));writer=csv.DictWriter(f,fields);writer.writeheader();writer.writerows({k:json.dumps(z,ensure_ascii=False,sort_keys=True) if isinstance(z,(dict,list)) else z for k,z in x.items()} for x in allrows)
lines=['# NRZ电源、独立电阻角与封装：验证记录','', '本轮真实改变MOS电压类别并重新生成GDS/DRC/LVS/PEX，MicroLED、RX、固定阈值与训练方法保持冻结。所有通过结论都是声明条件下的离散点；失败和管理中止记录保留。','', '## 最重要的边界','', '- 旧03v3电路的9–11mV端压余量不足以覆盖+25/+50mV供电扰动；外源保持3.6V时，VDD/VSS各1Ω+2nH也触发项目端压筛查失败。0/511误码不代替器件筛查。','- 新A采用06v0及8µm输入poly，B将inverter/steering改06v0而保留03v3电流参考/镜像。A48、A8与bodytie真实提取的前后记录均保留；bodytie没有改善已观察到的SS .5Gb/s临界点。','- A .25/.4/.5Gb/s在冻结sampler下不单调：.25可因归一化水平裕量失败，.5可因垂直裕量失败。报告.4Gb/s是选定离散点，不声称连续速率上界。','', '- A .4Gb/s的独立VLED+50mV或VH/VL共同−50mV在FF仍有timing=.09375UI失败；联合SS负控进一步出现静态high低于RX阈值。因此本轮没有闭合A的完整独立辅助电源包络。', '', '## 执行与判定分开', '', '旧基线有效计划42/42完成：求解/分析失败0，功能筛查失败0，器件筛查失败12。最终有效计划65/65完成：求解/分析失败0，器件筛查失败0，功能筛查失败7（均为保留的A诊断／边界案例）。全部身份审计通过不等于全部电路通过。', '', '## 同速率能量（所有电源＋DATA正向供能）','', '| 条件 | A .4Gb/s fJ/gross bit | B .4Gb/s fJ/gross bit | 两路筛查均通过 |','|---|---:|---:|---|']
for x in same:
 a,b=x['A'],x['B'];lines.append(f"|{x['condition']}|{a['rail_plus_DATA_positive_draw_fJ_per_gross_bit']:.3f}|{b['rail_plus_DATA_positive_draw_fJ_per_gross_bit']:.3f}|{x['both_comparison_and_device_screens_passed']}|" if a and b else f"|{x['condition']}|待完成|待完成|False|")
lines+=['','## 联合低压负控','', '| 路线/状态 | 值（DC为µA，否则为错误数） | threshold margin | timing UI | 结论 |','|---|---:|---:|---:|---|']
for x in boundary:
 lines.append(f"|{x['route']} / {('DC'+str(x['dc_bit'])) if 'dc_bit' in x else str(x['rate_Gbps'])+'G'}|{round(x['LED_current_A']*1e6,3) if 'dc_bit' in x else x.get('errors')}|{x.get('threshold_margin_normalized','—')}|{x.get('timing_min_margin_ui','—')}|{('DC threshold feasible='+str(x['dc_threshold_feasible'])) if 'dc_bit' in x else x.get('combined_screen_passed')}|")
lines+=['','联合负控A为SS125°C、VDD2.95V、VLED4.95V、VH/VL各+50mV；B为同VDD/VLED条件且VDUMMY−50mV。DC high若低于62.5µA，降低数据速率不能解决静态阈值不足。该测试不代表所有独立电源角的穷举。','','## 可追溯文件','', '- 总索引：`evidence/highspeed-nrz-robustness/summary.json` 与 `all-cases.csv`。','- 最终真实full-RC输入：`build/highspeed-nrz-robustness/selected-a8-b58-r4/manifest.json`。','- Sampler证据：`sampler-diagnostic.json`；数值控制：`numerical-audit.json`。','- 电源/回地窗口：`baseline-A-supply-return-window-global.csv`与`final-A-supply-return-window-matched.csv`（同FF3.6V、1Gb/s、同149.040736ns中心），JSON内记录原raw/deck/result SHA与精确器件。','- 已声明矩阵及管理范围调整均保留在每个run的plan/selection/superseded记录；不能把管理中止等同于SPICE数值失败。','', '03v3保持3.63V六对端压筛查，06v0使用保守6.0V六对筛查，同时单列gate-specific peak。它们不是foundry全可靠性签核；静态LED拟合没有温度模型，动态LED/optical/RX及封装R/L为假设，substrate RC不等于独立验证的3D衬底模型。']
(r.EVIDENCE/'REPORT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'work_counts':{k:s['count'] for k,s in summaries.items()},'final_missing':summaries['selected-a8-b58-r4']['missing'],'final_failed_simulations':summaries['selected-a8-b58-r4']['failed_simulations']}))
