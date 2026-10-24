#!/usr/bin/env python3
"""Create the PWM reader summary only after its frozen final acceptance exists."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'evidence/pwm-reference-v2/20261024';OUT=ROOT/'docs/research/pwm-reference-startup-20261024'
def read(n):return json.loads((E/(n+'.json')).read_text())
def table(headers, rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def main():
 s=read('final-summary');v=read('validation');assert s['selected_acceptance'] and v['selected_acceptance']
 prefix=s['selected_prefix'];cf=s['selected_filter_c_nf'];get=lambda suffix:read(prefix+'_'+suffix)
 step=get('step');gear=get('startup_fullmesh');trap=get('startup_fullmesh_trap');slow=get('startup_ss_slow');oldslow=read('damped_startup_ss_slow');midstart=read('c47_startup_ss_slow');fault=get('fault');pwm=get('pwm');num=next(x for x in v['numerical_comparisons'] if 'startup' in x['pair'][0]);dc=s['dc_matrix'];dy=s['dynamic_matrix'];n=s['selected_case_count']
 oldp=ROOT/'evidence/pwm-robustness/20261024/step_ref_10ns_board100n.json';old=json.loads(oldp.read_text())
 loops=[]
 for r in s['final_local_loops']:
  cross=r['crossings'];loops.append([r['corner'],json.dumps(cross,ensure_ascii=False)])
 checks=[['TT 名义供电 10% / 10 ns 阶跃',f"{step['excursion_pct']:.4f}% 最大偏差",'≤20%'],['TT 名义恢复到基线 ±0.5%', f"{step['settle_s']*1e6:.3f} µs",'≤5 µs'],['TT 名义启动近零保持窗',f"{max(gear['held_peak_a'],trap['held_peak_a'])*1e12:.3f} pA 数值峰值",'≤1 nA'],['慢热启动恢复平均',f"{slow['recovered_a']*1e6:.4f} µA，30–40 µs",'100 µA ±5%'],['独立故障到安全',f"{fault['fault_to_safe_s']*1e9:.2f} ns",'≤1 µs'],['故障正 / 负电荷',f"+{fault['fault_charge']['positive_c']*1e12:.4f} / {fault['fault_charge']['negative_c']*1e12:.4f} pC",'Q+ ≤10 pC；Q− 幅值 ≤20 pC'],['最短 PWM 码积分误差',f"{pwm['d1_charge_error_pct']:+.4f}%",'±2%']]
 text=f'''## 本轮结论与决策

**在保留的负载、时序和研究门槛下，参考恢复与严格启动数值一致性已通过本轮限定验证。** 芯片仍是原 39 MOS 实际 PEX；修订在外部补偿和供电/控制边界：N2 对 PCB 地 150 pF、补偿引脚 R/L 与 10 Ω 阻尼、参考供电 100 Ω / {cf:g} nF，以及三个外部控制端各 10 Ω 输出阻抗。

最终 {n} 个选定电气 case 已完成并通过，另有三个局部环路工作点；它们包括 DC 等效复核、供电、启动、故障、最低 PWM 码和有限 R/C 容差。原 144 点 DC 独立电阻矩阵保留，通过电容 DC 开路等效及极值重测复用，不写成全部以 {cf:g} nF 重跑。外部参考与 FAULT/PERMIT 仍是接口前提，尚未完成自主上电复位。

{table(['验证项目','最终结果','保留门槛'],checks)}

下一步应把“外部保证参考建立后再许可”做成实际 reference-ready / 欠压互锁，再决定是否增加阵列规模；当前优先事项不是增加像素数。

## 修改前后：恢复变快，但不隐藏新的慢角失败

上一阶段的 PCB 侧 100 Ω / 100 nF + Miller 补偿，在同样 10% / 10 ns 参考供电阶跃中，最大电流偏差 **{old['excursion_pct_of_pre_step']:.3f}%**，恢复 **{old['settle_after_restore_0p5pct_s']*1e6:.3f} µs**，超过 5 µs。最终网络的最大偏差为 **{step['excursion_pct']:.3f}%**，恢复后 **{step['settle_s']*1e6:.3f} µs** 进入并保持在原电流 ±0.5% 误差带内。减小滤波电容会减少抑制快速扰动的能力，同时缩短充电尾部；当前选型按两项门槛一起判定。

<figure><a href="figures/matched-board-step.svg"><img src="figures/matched-board-step.svg" alt="相同100微秒供电阶跃下旧板侧滤波与最终网络的LED电流和局部电压"></a><figcaption>相同 LED 模型、10% / 10 ns 激励和 100 µs 窗口。两条是整个修订前后的对照；其中补偿拓扑、滤波电容与控制阻抗都有明确变化，不伪称单因素实验。SENSE 与参考轨都以各自芯片地为电压参考。</figcaption></figure>

改补偿后曾保留 100 nF，其名义结果很好，却在 **SS / 85°C、逻辑及参考 2.97 V、LED 4.5 V、105 Ω / 110 nF、补偿 165 pF** 的慢角，30–40 µs 平均仅 **{oldslow['recovered_a']*1e6:.4f} µA**，未通过 ±5%。这是实际充电和低压余量问题，不是求解器失败。

只把滤波电容标称改为 47 nF（同慢角 51.7 nF），其余条件及 FAULT 20 µs 释放不变，平均改善为 **{midstart['recovered_a']*1e6:.4f} µA**。最慢 RC 时间常数从 11.55 µs 降到 5.4285 µs；单 RC 的 30 µs 建立比例估计从 92.55% 升到 99.60%。完整晶体管电流并不简单等于这个比例，因此仍以实际波形验收。

但 47 nF 的最终 SS 动态矩阵随后失败：快 RC 恢复约 8.057 µs，慢 RC 约 10.989 µs，超过同一个 5 µs 门槛。2.97 V 再下降 10% 后接近参考源的供电余量边界，充电尾部被转换成较大的电流误差。因此继续仅把滤波电容标称缩小至 **{cf:g} nF**，其它器件和判据不变，并重跑必要的动态、启动与故障验证；最终慢热启动的 30–40 µs 平均为 **{slow['recovered_a']*1e6:.4f} µA**。下面保留 100→47 nF 的诊断图，不能把这张阶段性图当成最终全部通过。

<figure><a href="figures/slow-start-filter-control.svg"><img src="figures/slow-start-filter-control.svg" alt="仅改变滤波电容的慢热启动对照"></a><figcaption>这个对照才是单因素：110 nF → 51.7 nF，保持同一 SS、低供电、补偿、FAULT/PERMIT 和 40 µs 窗口。没有延长等待时间来遮住失败。</figcaption></figure>

## 启动：求解完成还要检查数值一致性

原理想控制输入、原 Miller 补偿在严格设置下曾于约 61 ps / 273 ps 失败。报错节点 `vpermit#branch` 当时并未切换，因此不把它当作 PERMIT 的物理根因证据。新模型明确加入控制驱动阻抗和补偿外引阻尼；严格容差仍为 `reltol=1e-7、abstol=1e-14、vntol=1e-9`。

完整 0–40 µs 启动分别采用 Gear2 / 2 ns 最大步长和 trapezoidal / 1 ns 最大步长；电源边沿附近保持 0.1 ps 细网格。两者保持峰值为 **{gear['held_peak_a']*1e12:.4f} / {trap['held_peak_a']*1e12:.4f} pA**，差 **{num['held_peak_delta_a']*1e12:.5f} pA**；保持电荷最大差 **{num['held_charge_max_delta_c']:.3g} C**，恢复电流相对差 **{num['recovered_current_relative_delta']:.3g}**，均在事先声明的 2 pA、4×10⁻¹⁷ C、0.2% 一致性预算内。

这些 pA 是 SPICE 近零窗口的支路数值，包含浮点与结电容导数影响；它们支持“低于 1 nA 门槛且两方法一致”，不代表已经预测或测量了 pA 级硅片漏电。启动中安全、缓冲及 LED 电源预先供好，只有参考轨按 100 ns 上升；没有覆盖任意同时上电顺序。

<figure><img src="electrical-figures/启动保持与许可.svg" alt="严格启动中的参考轨保持电流与RTL许可"><figcaption>FAULT 在 20 µs 释放，RTL 的许可在后续时钟边沿建立。上图看电源，中图看近零保持窗，下图看正常电流恢复；总支路电流与二极管导电分量分开。</figcaption></figure>

含寄生电容的支路在开关瞬间可以出现负电流，它可能来自储存电荷的释放。不能把它解释为“负光输出”，也不能仅用平均电流掩盖它；本轮仍单独积分正、负电荷并检查峰值和时序。故障在 50.125 µs 施加、时钟已于 47.7 µs 停止，独立保护仍在 {fault['fault_to_safe_s']*1e9:.2f} ns 内达到安全条件。

最低 PWM 码的导通目标为一个 1 µs 时隙，在固定 258.5–514.5 µs 的完整灰度周期内积分。实得电荷 **{pwm['d1_charge_c']*1e12:.4f} pC**，对同一网络的 DC 电流×1 µs 误差为 **{pwm['d1_charge_error_pct']:+.4f}%**。这里比较电荷，不只是比较脉冲看起来是否有相同宽度。

## PVT、元件容差与反馈范围

原 144 点矩阵覆盖三个 MOS 角 × 三个温度 × 四只外部电阻的 16 个独立顶点。RSET 5 kΩ、RBIAS 100 kΩ、RRELEASE 100 kΩ、RBLEED 10 MΩ 保持标称；DC 电流误差为 **{dc['min_error_pct']:+.5f}%～{dc['max_error_pct']:+.5f}%**。电容在 DC 开路，补偿支路串联电感在 DC 为短路且无电流，因此本轮通过 DC 等效与极值重跑确认可复用原矩阵；不把历史矩阵的每个点算成新的瞬态通过。

<figure><img src="electrical-figures/直流PVT与独立电阻角落.svg" alt="单像素四只独立电阻的直流PVT误差范围"><figcaption>每组竖线表示相应温度与 MOS 角的 16 个独立电阻顶点范围，不是统计误差条，也不是良率估计。</figcaption></figure>

叠加通用外部 VSET ±0.2% / 100 Ω 源阻抗的两个极端控制，误差为 {get('dc_extref_min')['error_pct']:+.5f}% / {get('dc_extref_max')['error_pct']:+.5f}%。这仍是外部基准边界敏感性，不是已经验证某款基准芯片。它与高速 B 的 2.5 V 分压方案分别记录，不能互换。

最终动态矩阵为 TT 的 8 个独立 Rfilter ±5%、Cfilter ±10%、Ccomp ±10% 顶点，加 SS/FF 各两个快慢端点，共 **{dy['count']} 点**。最大电流偏差 **{dy['max_excursion_pct']:.4f}%**，最长恢复到 ±0.5% 带为 **{dy['max_restore_s']*1e6:.4f} µs**；不等于所有供电、温度、封装与无源容差的完整联合覆盖。

<figure><img src="electrical-figures/供电动态容差.svg" alt="最终网络限定RC角落的供电响应"></figure>
<figure><img src="electrical-figures/局部环路对照.svg" alt="原补偿被拒绝前馈及最终三个工艺角的局部环路响应"><figcaption>局部双注入估计需要与启动、阶跃同时阅读；没有把局部相位裕量当成全多环路稳定性签核。</figcaption></figure>

全部选定条件、求解身份、数值比较和保留失败见[最终摘要](../../../evidence/pwm-reference-v2/20261024/final-summary.json)及[验证记录](../../../evidence/pwm-reference-v2/20261024/validation.json)。所有 39 MOS 的六对端压峰值在指定扰动/故障点留存；这不是 foundry 可靠性、SOA、ESD 或光学验证。
'''
 (OUT/'results.md').write_text(text)
 paths=[E/'final-summary.json',E/'validation.json',oldp]
 (OUT/'figures/results-data.json').write_text(json.dumps({'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'inputs':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'selected_acceptance':True,'selected_cases':n},indent=2)+'\n')
 print(f'PWM summary: {n} selected cases; bounded acceptance passed')
if __name__=='__main__':main()
