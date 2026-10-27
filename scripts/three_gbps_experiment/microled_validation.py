#!/usr/bin/env python3
"""Numerical controls and compact Chinese note for the append-only MicroLED run."""
from pathlib import Path
import argparse, concurrent.futures, importlib.util, json, math, shutil
import numpy as np

SOURCE=Path(__file__).with_name('microled_diagnosis.py')
spec=importlib.util.spec_from_file_location('microled_diagnosis',SOURCE)
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)

def refine(jobs):
    d.initialize()
    snap=d.WORK/'execution-sources'/('microled_validation-'+d.e.sha(Path(__file__))+'.py')
    if not snap.exists():shutil.copy2(Path(__file__),snap)
    cases=[dict(name=f'REFINE80-TT-{route}-3p2G',route=route,net_rate_Gbps=3.2,
                group='numerical_refinement',steps_per_symbol=80,timeout_s=900) for route in 'ABC']
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for r in pool.map(d.run_one,cases):
            print(json.dumps(dict(name=r['case']['name'],simulation_ok=r['simulation_ok'],
                                  elapsed_s=r['elapsed_s'],analysis_error=r.get('analysis_error'))),flush=True)

def validate():
    d.initialize();checks={}
    # Independent exact ramp response y(t)=t-tau+tau*exp(-t/tau).
    t=np.linspace(0.,4.,4001);tau=.7
    analytical=t-tau+tau*np.exp(-t/tau)
    error=float(np.max(abs(d.first_order(t,t,tau)-analytical)))
    checks['first_order_ramp_max_absolute_error']=error
    assert error<2e-12
    # The separate one-pole implementation must agree with v2's optical state.
    t,y=d.ideal_trace('C',5)
    first,_=d.rx.filter_trace(t,y)
    delta=float(np.max(abs(first-d.first_order(t,y,d.rx.TAU_OPTICAL_S))))
    checks['independent_optical_filter_max_delta_A']=delta
    assert delta<1e-12
    floors=[]
    bypass=d.module(d.RXSOURCE,'microled_validate_bypass');bypass.filter_trace=lambda t,y:(y,y)
    for route in ['A','C']:
        for step in [5.,2.5,1.25]:
            t,y=d.ideal_trace(route,step);_,full=d.rx.filter_trace(t,y)
            r=bypass.analyze(t,full,d.rx.make_stimulus(),route,3.2)
            floors.append(dict(route=route,step_ps=step,**d.compact_rx(r)))
    comparisons=[]
    contract=json.loads((d.ROOT/'evidence/fair-driver-v1/numerics-contract.json').read_text())
    for route in 'ABC':
        p40=d.WORK/'cases'/f'BASE-TT-{route}-3p2G'/'result.json'
        p80=d.WORK/'cases'/f'REFINE80-TT-{route}-3p2G'/'result.json'
        if not p80.exists():continue
        a=json.loads(p40.read_text());b=json.loads(p80.read_text())
        if not b['simulation_ok'] or 'analysis_error' in b:
            comparisons.append(dict(route=route,refinement_success=False,result=str(p80.relative_to(d.ROOT))));continue
        ma,mb=a['metrics'],b['metrics'];ra,rb=d.compact_rx(ma['receiver']),d.compact_rx(mb['receiver'])
        delta=dict(energy_relative_percent=100*(mb['total_energy']['positive_pJ_per_payload_bit']/ma['total_energy']['positive_pJ_per_payload_bit']-1),
                   margin_uA=rb['min_signed_margin_uA']-ra['min_signed_margin_uA'],
                   time_ps=rb['min_time_margin_ps']-ra['min_time_margin_ps'],
                   body_forward_mV=1000*(mb['max_body_forward_V']-ma['max_body_forward_V']),
                   bit_errors=rb['bit_errors']-ra['bit_errors'])
        gates=dict(energy=abs(delta['energy_relative_percent'])<=.2,margin=abs(delta['margin_uA'])<=.2,
                   time=abs(delta['time_ps'])<=20,body=abs(delta['body_forward_mV'])<=5,
                   same_bit_errors=delta['bit_errors']==0)
        comparisons.append(dict(route=route,refinement_success=True,base=ra,refined=rb,delta=delta,
                                historical_numerical_gates=gates,all_gates_passed=all(gates.values()),
                                screen_failure_unchanged=not ra['passed'] and not rb['passed'],
                                refined_result=str(p80.relative_to(d.ROOT)),refined_result_sha256=d.e.sha(p80)))
    checks.update(ideal_receiver_refinement=floors,transistor_refinement=comparisons,
                  historical_numerics_contract_sha256=d.e.sha(d.ROOT/'evidence/fair-driver-v1/numerics-contract.json'),
                  numerical_tolerances=contract['tolerances'],script_sha256=d.e.sha(Path(__file__)),
                  bound_runner_sha256=d.e.sha(SOURCE),legacy_sources_unchanged=True)
    d.e.emit(d.EVIDENCE/'microled-validation.json',checks)
    print(json.dumps(checks,ensure_ascii=False),flush=True)

def note():
    p=d.EVIDENCE/'microled-summary.json';r=json.loads(p.read_text())
    q=d.EVIDENCE/'microled-validation.json';v=json.loads(q.read_text())
    lines=['# MicroLED 单通道净 3.2 Gb/s：原理级分层诊断','',
           '证据层级：新 SCHEM ngspice 仿真与离线接收代理；没有新增布局、DRC/LVS/PEX、硅片或光学测量。',
           '', '## 冻结定义','',
           '- 帧效率 4096/4736 = 32/37；净 3.2 Gb/s、线路 3.7 Gb/s；A/B NRZ 为 3.7 GBd，C PAM4 为 1.85 GBd。',
           '- 保留原 TT 校准参数、静态 LED PWL、200 fF、1 Ω/0.5 nH 封装、20 ps 数据边沿和全部七端口计能。',
           '- 接收机保持 v2：0–8 ns、5 ps 网格，只在训练区选延迟；固定 7.5 µA 与 100 ps 门槛。各隔离阶段分别训练，不能把多个阶段的结果串接成已实现链路。',
           '- 电气层使用 LED conduction current，排除外接电容位移电流；光学代理为 200 ps 一阶极点，RX 为 1 GHz 一阶极点。所有光学/RX 输出仍是等效电流，非测得光功率。',
           '', '## 原条件角落结果','',
           '| 路线/角落 | 错误 bit / 4096 | 最小判决裕量 µA | 最小时序裕量 ps | 七端口正向 pJ/net-bit | 电压 screen |',
           '|---|---:|---:|---:|---:|---|']
    for x in r['records']:
        if x['group']!='baseline':continue
        f=x['stages']['full'];lines.append(f"| {x['route']}/{x['corner']} | {f['bit_errors']} | {f['min_signed_margin_uA']:.3f} | {f['min_time_margin_ps']:.3f} | {x['energy_pJ_netbit']:.6f} | {x['device_voltage_pass']} |")
    lines+=['','能量是失败工作点的电气计能，不是合格 3.2 Gb/s 链路能效；未计源 IC 内耗、RX、时钟、主机。完整七端口分项、返回能量、body-forward 峰值见 JSON。',
            '', '## TT 分层与零电容对照','',
            '| 条件 | 电气错误 / 裕量 µA | 仅光学错误 / 裕量 µA | 仅 RX 错误 / 裕量 µA | 完整代理错误 / 裕量 µA |',
            '|---|---:|---:|---:|---:|']
    for x in r['records']:
        if x['corner']!='typical':continue
        cols=[f"{x['stages'][s]['bit_errors']} / {x['stages'][s]['min_signed_margin_uA']:.3f}" for s in ['electrical','optical_only','rx_only','full']]
        lines.append('| '+x['name']+' | '+' | '.join(cols)+' |')
    lines+=['','CAP0 只移除外接 200 fF，不改变静态 I–V、驱动参数或接收判据。它是负载动态的反事实隔离，不能充当真实 LED 产品假设。',
            '', '## 独立理想源对照','',
            '| 输入/负载 | 格式 | 电气错误 | 完整代理错误 | 完整裕量 µA / 时序 ps |',
            '|---|---|---:|---:|---:|']
    for x in r['ideal_controls']:
        f=x['stages']['full'];a=x['stages']['electrical']
        label='理想 conduction 电流' if x['kind']=='ideal_conduction_waveform' else f"ngspice 理想 sink，C={x['capacitance_F']*1e15:g} fF"
        lines.append(f"| {label} | {x['route']} | {a['bit_errors']} | {f['bit_errors']} | {f['min_signed_margin_uA']:.3f} / {f['min_time_margin_ps']:.3f} |")
    lines+=['','理想源不是某个真实拓扑的严格性能上界；它只是 25/100 µA NRZ 或 25/50/75/100 µA PAM4、20 ps 边沿在既有代理中的参考点。预加重/均衡可能改变输入形状，必须另立电流/能量/接收预算验证。',
            '', '## 校准、数值与局限','',
            f"- 新增 {len(r['dc'])} 个 TT DC 检查；相同路线/电平的 200 fF 与 0 fF DC 电流最大差为 {max(abs(x['capacitance_DC_delta_uA']) for x in r['dc_capacitance_checks']):.6g} µA。未进行按速率重新调参。",
            '- 理想源时间网格从 5 ps 收紧到 2.5/1.25 ps；完整代理的 NRZ 错误保持 0，PAM4 保持 215。最细网格 NRZ 裕量约 0.499 µA、26.06 ps；PAM4 约 −1.555 µA、0 ps。',
            '- 晶体管 max-step 从 symbol/40 收紧到 symbol/80；所有原数值门槛保留，不能用失败结论稳定替代数值完全收敛。',
            '', '| 路线 | Δ能量 % | Δ裕量 µA | Δ错误 bit | 历史数值门槛全部满足 | 完整 screen 仍失败 |',
            '|---|---:|---:|---:|---|---|']
    for x in v['transistor_refinement']:
        if x.get('refinement_success'):
            z=x['delta'];lines.append(f"| {x['route']} | {z['energy_relative_percent']:.6f} | {z['margin_uA']:.6f} | {z['bit_errors']} | {x['all_gates_passed']} | {x['screen_failure_unchanged']} |")
    lines+=['',f"仿真/分析失败：{json.dumps(r['failures'],ensure_ascii=False)}；未执行：{json.dumps(r['missing'],ensure_ascii=False)}。",
            '','静态曲线、C、光学寿命与接收噪声未组成同器件测量闭环。确定性有限帧错误率不是测得 BER；通道、温度、封装、失配、噪声与可靠性尚未完整闭合。',
            '', '## 重现命令与身份','',
            '在仓库根目录执行；已有 case 只复核/读取，不覆盖：','',
            '```sh','build/layout/venv/bin/python scripts/three_gbps_experiment/microled_diagnosis.py --phase run --jobs 2',
            'build/layout/venv/bin/python scripts/three_gbps_experiment/microled_validation.py --phase refine --jobs 1',
            'build/layout/venv/bin/python scripts/three_gbps_experiment/microled_diagnosis.py --phase analyze',
            'build/layout/venv/bin/python scripts/three_gbps_experiment/microled_validation.py --phase validate',
            'build/layout/venv/bin/python scripts/three_gbps_experiment/microled_validation.py --phase note','```','',
            f"- legacy runner SHA-256：`{r['legacy_engine_sha256']}`",
            f"- v2 receiver SHA-256：`{r['receiver_v2_sha256']}`",
            f"- frozen manifest SHA-256：`{r['manifest_sha256']}`",
            f"- summary SHA-256：`{d.e.sha(p)}`",
            f"- validation SHA-256：`{d.e.sha(q)}`",
            '- 所有 deck/result/raw/gzip hashes 见 microled-summary.json；原始波形、完整逐阶段判决和 ngspice log 在 build/three-gbps-experiment-20261027/microled/run-r1/。']
    (d.EVIDENCE/'microled-note.md').write_text('\n'.join(lines)+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['refine','validate','note'],required=True);p.add_argument('--jobs',type=int,default=1);a=p.parse_args()
    if a.phase=='refine':refine(a.jobs)
    elif a.phase=='validate':validate()
    else:note()

if __name__=='__main__':main()
