#!/usr/bin/env python3
"""Generate concise interpretation text from the frozen measured simulation rows."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'docs/research/highspeed-nrz-pex-20261020'
s=json.loads((ROOT/'evidence/highspeed-nrz-pex/summary.json').read_text())
assert s['completion']['status']=='declared_case_lists_complete'
p=OUT/'report-content.json';v=json.loads(p.read_text());rows=s['rows'];nom=[r for r in rows if r['kind']=='nominal' and r['analysis_ok']]
def pick(route,variant,rate):return next(r for r in nom if r['route']==route and r['variant']==variant and r['rate_Gbps']==rate)
def pointset(rt,var):return sorted(r['rate_Gbps']for r in nom if r['route']==rt and r['variant']==var and r['comparison_screen_passed'])
def table(head,rows):return '<div class="scroll"><table><tr>'+''.join('<th>'+str(x)+'</th>'for x in head)+'</tr>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>'for x in row)+'</tr>'for row in rows)+'</table></div>'
k='rail_plus_DATA_positive_draw_fJ_per_gross_bit'
v['RESULT_NARRATIVE']='完成两版核心几何与连接检查、全网电阻提取和经过独立审计的电容组装。名义条件下，加入 RC 后最高离散通过点分别为 '+ '；'.join(f"{rt}：{max(pointset(rt,'RC'),default=0):g} Gb/s"for rt in 'AB')+'。这些点在固定负载与接收代理下取得；需结合电源实现、角落、应力与数值控制判断可用范围。'
v['DECISION_NARRATIVE']='目前尚不能把名义最高点定为产品规格：SS / 125°C / 3.0 V 时，A 的 2 Gb/s 出现 64/511 比特错误，B 的 0.5 Gb/s 出现 2/511 比特错误；FF / −40°C / 3.6 V 时存在超过项目端差筛查线的过冲。当前的路线选择应同时看电流波形和完整实现成本：A 的输出驱动比较直接，但依赖可吸收回流的 VH/VL；B 保留连续尾电流和 dummy 支路，需要改进互补驱动时序与偏置稳定性。两者都还要补上实际电源、pad/ESD 和封装，才能比较完整芯片。'
v['RATE_NARRATIVE']='RC 通过集合为 '+ '；'.join(rt+' = {'+', '.join(f'{x:g}'for x in pointset(rt,'RC'))+'} Gb/s'for rt in 'AB')+'。不能把最高点写成其以下全部速率必然通过。尤其 B 在 0.1 Gb/s 的 RC 结果是 0/511 比特错误，但右侧时序余量只有 0.09375 UI，小于 0.1 UI；原理图基线也有此现象。冻结训练规则先最小化比特错误、再最大化竖向门限余量，并未优先居中水平眼图，因此不能把这项低速失败归因于器件带宽。下一轮应把水平余量纳入独立接收训练实验，保持本轮合同不变。'
parts=[]
for rt,rate in [('A',2),('B',.5)]:
 q,g,c=pick(rt,'RC',rate),pick(rt,'GEOM',rate),pick(rt,'C',rate)
 parts.append(f"{rt} 在 {rate:g} Gb/s：GEOM、C、RC 的正向取能依次为 {g[k]:.2f}、{c[k]:.2f}、{q[k]:.2f} fJ/毛bit；单独增加 C 相对 GEOM 改变 {100*(c[k]/g[k]-1):+.2f}%，继续加入 R 相对 C 改变 {100*(q[k]/c[k]-1):+.2f}%。")
v['RATE_NARRATIVE']+=' '.join(parts)+' A 的 RC 2 Gb/s 幅度余量为 '+f"{pick('A','RC',2)['threshold_margin_normalized']:.6f}"+'，已接近 0.1 筛查门槛，最高通过点仍需要增加设计余量。RC 能耗略低于 C-only 不能直接解释为电阻改善效率：它与 DC 电流下降和瞬态波形变化同时发生，仍应按信号质量一起评估。'
nomstress=max(r['max_abs_terminal_V']for r in nom if r['variant']=='RC')
pvt=[r for r in rows if r['variant']=='RC' and r['kind']in ['slow_hot','fast_cold']]
v['STRESS_NARRATIVE']=f"RC 名义七速率扫描的全窗口最大端差为 {nomstress:.5f} V。所选 SS/FF 瞬态控制中最大值为 {max(r['max_abs_terminal_V']for r in pvt):.5f} V，其中 {sum(r['above_3p63V_screen']for r in pvt)}/{len(pvt)} 点超过项目 3.63 V 筛查线。该筛查与接收通过判据分开记录；不能因无采样比特错误就忽略过冲。它也不能替代厂方的氧化层、电流密度、体结注入和寿命规则。"
ctrl=[r for r in s['numerical_controls']if r['available'] and r['variant']!='SCHEM']
v['CONVERGENCE_NARRATIVE']=f"新提取模型共 {len(ctrl)} 个步长/积分方法对照。相对对应主运行，正向能耗最大相对变化 {max(abs(r['energy_change_percent'])for r in ctrl):.5f}%；幅度余量最大绝对变化 {max(abs(r['threshold_margin_change'])for r in ctrl):.6f}。其中 {sum(r['errors_changed']for r in ctrl)} 点的比特错误数改变，{sum(r['screen_changed']for r in ctrl)} 点的筛查结论改变。若结论随数值设置变化，该点应保留为边界条件，不能报成稳定性能规格。"
method=json.loads((ROOT/'evidence/highspeed-nrz-pex/integration-method-audit.json').read_text())
v['CONVERGENCE_NARRATIVE']+=' 在 1 Gb/s 的 RC 控制中，从 Gear2 / UI40 改为 trap / UI200 后：'+'；'.join(
 f"{r['route']} 正向取能改变 {r['totals']['positive_draw']['delta_fJ_per_gross_bit']:.3f} fJ/bit，其中理想 DATA 端贡献 {r['ports']['ideal_DATA']['delta_positive_fJ_per_gross_bit']:.3f} fJ/bit，净能量变化仅 {r['totals']['net']['change_percent']:.5f}%"
 for r in method['rows'])+'。这是正向取能与回灌分解的数值方法敏感性，不能用来证明真实振铃。当前约 1.2% 的方法敏感性也高于 RC 相对 C-only 的微小能耗下降，以及前述对地电容位置控制的变化，后二者不能宣称为已验证的节能优化。逐端计算见<a href="../../../evidence/highspeed-nrz-pex/integration-method-audit.json">积分方法审计</a>。'
loc=[r for r in rows if r['variant']=='RCLUMP' and r['kind']=='cap_placement_control'];lr=[]
for r in loc:
 b=pick(r['route'],'RC',r['rate_Gbps'])
 lr.append([r['route'],r['rate_Gbps'],f"{100*(r[k]/b[k]-1):+.5f}%",f"{r['threshold_margin_normalized']-b['threshold_margin_normalized']:+.6f}",f"{r['timing_min_margin_ui']-b['timing_min_margin_ui']:+.6f}",'改变'if r['comparison_screen_passed']!=b['comparison_screen_passed']else'不变'])
v['LOCATION_TABLE']=table(['路线','Gb/s','RCLUMP相对RC能耗','幅度余量差','时序余量差/UI','筛查结论'],lr)
changes=sum(r['comparison_screen_passed']!=pick(r['route'],'RC',r['rate_Gbps'])['comparison_screen_passed']for r in loc)
v['LOCATION_NARRATIVE']=f"六个控制点中 {changes} 个筛查结论改变。这个实验只改变对地电容落点，耦合电容仍放在原逻辑节点；即使结果接近，也只支持本核心、这些速率点对这一种位置近似不敏感，不能作为三维电容分布正确的证明。"
v['NEXT_NARRATIVE']='下一阶段应优先缩小已暴露的不确定性，而不是立即扩展通道数。先定位慢热接收失败与快冷过冲，再用关键网络更短、驱动级更靠近负载的候选版图复做同一对照；同时补齐电源和接口边界。当前有限序列、固定采样规则和无噪声接收代理还不能支持产品速率承诺。'
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({key:v[key]for key in ['RESULT_NARRATIVE','RATE_NARRATIVE','STRESS_NARRATIVE','CONVERGENCE_NARRATIVE','LOCATION_NARRATIVE']},ensure_ascii=False,indent=2))
