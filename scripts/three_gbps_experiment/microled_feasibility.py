#!/usr/bin/env python3
"""Read-only training-grid feasibility audit; never alters the v2 receiver."""
from pathlib import Path
import hashlib, importlib.util, json
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'build/three-gbps-experiment-20261027/microled/run-r1'
DEST=ROOT/'evidence/three-gbps-experiment-20261027'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    source=DEST/'microled-summary.json';summary=json.loads(source.read_text())
    assert not summary['missing'] and not summary['failures'] and len(summary['records'])==12
    rows=[]
    for case in summary['records']:
        for stage in ['electrical','optical_only','rx_only','full']:
            p=WORK/'layer-analysis'/case['name']/(stage+'.json');r=json.loads(p.read_text())
            scan=r['sampling']['training_scan']
            row=dict(case=case['name'],stage=stage,candidates=len(scan),
                             max_training_min_signed_margin_uA=max(x['min_signed_decision_distance_uA'] for x in scan),
                             minimum_training_bit_errors=min(x['bit_errors'] for x in scan),
                             training_error_free_candidates=sum(x['bit_errors']==0 for x in scan),
                             amplitude_7p5uA_feasible_candidates=sum(x['min_signed_decision_distance_uA']>=7.5 for x in scan),
                             stage_result_sha256=sha(p))
            if row['amplitude_7p5uA_feasible_candidates']:
                # No validation access: check all amplitude-eligible training delays
                # for simultaneous timing feasibility without changing the receiver.
                spec=importlib.util.spec_from_file_location('rx_grid_audit',ROOT/'scripts/fair_driver_v1/receiver_equal_latency_v2.py')
                rx=importlib.util.module_from_spec(spec);spec.loader.exec_module(rx)
                data=np.loadtxt(WORK/'cases'/case['name']/'waveform.dat.gz',skiprows=1)
                t,y=data[:,0],data[:,1]
                if stage=='rx_only':
                    helper_spec=importlib.util.spec_from_file_location('microled_filter_helper',Path(__file__).with_name('microled_diagnosis.py'))
                    helper=importlib.util.module_from_spec(helper_spec);helper_spec.loader.exec_module(helper)
                    y=helper.first_order(t,y,rx.TAU_RX_S)
                elif stage in ['optical_only','full']:
                    opt,full_y=rx.filter_trace(t,y);y=opt if stage=='optical_only' else full_y
                else:assert stage=='electrical'
                bits_per=2 if case['route']=='C' else 1;bit_ui=1/3.7e9;ui=bits_per*bit_ui
                prefix=t<576*bit_ui;pt,py=t[prefix],y[prefix]*1e6
                train_idx=np.arange(64//bits_per,512//bits_per)
                st=rx.make_stimulus();expected=np.array(st['symbols_C' if bits_per==2 else 'symbols_N'])[train_idx]
                thresholds=np.array([37.5,62.5,87.5] if bits_per==2 else [62.5])
                events=rx._crossing_events(pt,py,thresholds);feasible=[]
                best_time=0.
                for candidate in scan:
                    if candidate['min_signed_decision_distance_uA']<7.5:continue
                    when=train_idx*ui+candidate['delay_s'];samples=np.interp(when,pt,py)
                    hm=rx._horizontal(pt,py,when,samples,expected,thresholds,64*bit_ui,float(pt[-1]),ui,bit_ui,events_by_level=events)
                    best_time=max(best_time,hm['min_ps'])
                    if hm['min_ps']>=100:feasible.append(dict(delay_ps=candidate['delay_s']*1e12,training_margin_uA=candidate['min_signed_decision_distance_uA'],training_time_ps=hm['min_ps']))
                row['training_only_joint_feasibility']=dict(feasible_candidates=len(feasible),best_training_time_at_amplitude_eligible_ps=best_time,candidates=feasible,
                    status='Diagnostic only; no validation score or receiver change')
            rows.append(row)
    full=[x for x in rows if x['stage']=='full']
    no_joint_candidate=all(x['amplitude_7p5uA_feasible_candidates']==0 for x in full)
    result=dict(level='Frozen discrete training-grid diagnostic; not a new receiver or continuous phase proof',
                receiver='immutable equal_absolute_latency_v2',delay_grid_ps=5,delay_budget_ps=8000,
                summary_sha256=sha(source),script_sha256=sha(Path(__file__)),records=rows,
                all_12_full_stages_have_no_training_amplitude_gate_candidate=no_joint_candidate,
                resolved_audit_implementation_failure='build/three-gbps-experiment-20261027/microled/run-r1/audit-failures/training-feasibility-r1.json',
                limits=['Only fixed0..8ns/5ps training grid and fixed thresholds are covered.',
                        'Validation labels are never used to train or select a new delay.',
                        'A joint time/amplitude selector on this same grid cannot rescue a stage with no7.5uA amplitude candidate.',
                        'No alternative MicroLED receiver is introduced; do not directly rank against differently trained VCSEL results.'])
    (DEST/'microled-training-feasibility.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    caps=[x for x in summary['records'] if x['group']=='zero_cap_diagnostic']
    baseline=[x for x in summary['records'] if x['group']=='baseline']
    lines=['# MicroLED 3.2 Gb/s 诊断解释','',
           f"完成 {len(baseline)} 个原条件 TT/SS/FF 晶体管点，全部未通过原 v2 完整接收 screen；另有 3 个 TT 零电容对照、16 个 DC 检查、3 个细步长复核和 4 个 ngspice 理想 sink 负载对照。所有求解正常结束；接收失败保留原值，没有放宽门槛。",'',
           '1. **负载储能有独立影响。** 理想电流 sink、同一静态 LED PWL 和封装、200 fF 下，NRZ/PAM4 的电气层分别出现 863/1199 个错误；只把外接电容改为 0，电气层均无错误且通过原幅度/时序门槛。这隔离了静态 rd 与外接 C 的耦合影响，但不能把理想 sink 结果等同于电压输出路线 A。',
           '2. **驱动端与训练算法必须分开解释。** 保留真实晶体管与同一静态 LED，去掉外接 C 后，A/C 电气层仍有错误；B 电气层已经零错误，但原 v2 幅度优先选相的时序裕量仅约 17 ps。下面保留原判据；不能据 B 的这个选相点宣称其驱动本身绝对不可能通过。训练区联合幅度/时序可行性另列在 JSON 中，不修改接收机。',
           '', '| 路线 | 零 C 电气错误 / 4096 | 最小裕量 µA | 时序 ps |', '|---|---:|---:|---:|']
    for x in caps:
        e=x['stages']['electrical'];lines.append(f"| {x['route']} | {e['bit_errors']} | {e['min_signed_margin_uA']:.3f} | {e['min_time_margin_ps']:.3f} |")
    lines+=['','3. **下游代理也有限制。** 直接输入理想的 20 ps 边沿、固定标称电平，最细 1.25 ps 网格下 NRZ 完整代理为 0 错误但只有 0.499 µA / 26.06 ps；PAM4 为 215 个错误、−1.555 µA / 0 ps。两者均达不到原 7.5 µA / 100 ps 门槛。这里没有证明所有整形波形或所有接收结构都不可能通过。',
            '', '三个机制不能按上述控制结果相加。滤波、非线性负载、驱动脉冲与训练选择存在相互作用；有的阶段错误数下降也不意味着整个链路已通过。应在电流峰值/平均值、体结/端压、同一发光器件和同一接收条件下验证改动，暂时不能选出可行赢家。',
            '', '## 接收训练可行性核查','',
            '所有 12 个晶体管完整代理点，在冻结 1601 个训练延迟候选中，最大“最小判决裕量”均为负值，且最少训练错误也大于 0。因此保持本组波形、门槛与延迟网格时，换成联合幅度/时序选相算法仍不能通过。这不是对任意连续相位、均衡器或不同接收机的不可行证明。',
            '', 'B 零 C 的电气层，在所有幅度至少 7.5 µA 的训练延迟中，最大训练时序裕量为 92.343 ps；仅 RX 层为 42.672 ps，均没有同时达到 100 ps 的候选。原幅度优先选相的约 17 ps 确实保守，但冻结网格下联合选相仍未找到合格点。',
            '', '## 数值与电压边界','',
            '- 三条 TT 原条件点的 symbol/40→symbol/80 复核全部满足既有数值门槛，错误数均保持 A=844、B=1440、C=1399。',
            '- 16 个 DC 检查显示外接 200 fF 与 0 fF 的相应 DC 电流完全一致；原校准参数未重新优化。',
            '- 端间最大电压 screen 不是 body-junction 或可靠性签核：TT C 的最大体结正向电压约 0.858 V，零 C 的 A 约 0.731 V。没有新设或放宽体结门槛，也不声称这些波形是安全工作点。',
            '- 失败点的 pJ/net-bit 只表示七个输入端口的正向能量；不能据此宣称合格 3.2 Gb/s 链路的能效或跨 VCSEL/MicroLED 排名。',
            '- 训练审计脚本初版因 RX-only 也存在幅度可行候选而触发保护断言；补入对应的精确因果滤波后复核成功。初版源码、失败原因和修复边界保留在 build/.../audit-failures/，未影响原始仿真或接收结果。',
            '', '主数据见 microled-summary.json，数值核查见 microled-validation.json，全部阶段训练网格核查见 microled-training-feasibility.json。原始波形、日志与逐阶段判决在 build/three-gbps-experiment-20261027/microled/run-r1/。',
            '', '重现此解释与训练核查：', '', '```sh',
            'build/layout/venv/bin/python scripts/three_gbps_experiment/microled_feasibility.py','```','',
            f"summary SHA-256: `{sha(source)}`；本核查脚本 SHA-256: `{sha(Path(__file__))}`。"]
    (DEST/'microled-interpretation.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(stage_records=len(rows),full_no_candidate=no_joint_candidate,full=full),ensure_ascii=False))

if __name__=='__main__':main()
