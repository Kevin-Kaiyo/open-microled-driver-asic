#!/usr/bin/env python3
"""Summarize completed r10 evidence and outstanding checks without changing it."""
from pathlib import Path
import json
from run import ROOT, BUILD, EV, CIR, sha, emit


def main():
    rows=[]
    for p in sorted(BUILD.glob('*/result.json')):
        if not (p.parent/'manifest.json').exists():continue
        r=json.loads(p.read_text());m=json.loads((p.parent/'manifest.json').read_text());c=m['config']
        if c.get('revision')!='r10':continue
        if c['mode']!='frame' or not r.get('simulation_ok'):continue
        for ap in sorted(p.parent.glob('analysis-*/result.json')):
            a=json.loads(ap.read_text());plan=json.loads((ap.parent/'plan.json').read_text())
            cap=r.get('explicit_capacitor_energy');delta=cap['change_J']/4096*1e12 if cap else None
            rows.append(dict(case=r['case'],label=ap.parent.name.removeprefix('analysis-'),config=c,
                             optical_grid_ps=plan['grid_ps'],passed=a['combined_screen_passed'],
                             errors=a['errors'],time_margin_ps=a['time_margin_ps'],margin_uAeq=a['min_signed_margin_uAeq'],
                             positive_pJ_per_offered_payload_bit=a['energy']['positive_pJ_per_offered_payload_bit'],
                             explicit_delta_U_pJ_per_offered_payload_bit=delta,stress_max_V=a['stress_max_V'],
                             current_range_mA=a['current_range_mA'],result=str(p.relative_to(ROOT)),result_sha256=sha(p),
                             analysis=str(ap.relative_to(ROOT)),analysis_sha256=sha(ap),continuous_run=r.get('continuous_run')))
    def exact(name,label='fixed-v3-r2'):
        return [x for x in rows if x['case']==name and x['label']==label]
    groups={f'nominal_{c}':exact(f'frame-{c}-r10') for c in ['TT','SS','FF']}
    for name in ['frame-TT-supply-minus-r10','frame-TT-supply-plus-r10','frame-SS-supply-minus-r10',
                 'frame-SS-Rsense-plus-r10','frame-FF-Rsense-minus-r10','frame-TT-supply-minus-ESL0p5n-r10']:
        groups[name]=exact(name)
    groups['confirmation_seed_7B43']=[x for x in rows if x['config']['seed']==0x7B43 and x['label']=='fixed-v3-r2']
    groups['TT_native_UI_div80']=[x for x in rows if x['config']['corner']=='typical' and x['config']['steps']==80 and x['label']=='fixed-v3-r2']
    groups['TT_optical_grid1p25ps']=[x for x in rows if x['case']=='frame-TT-r10' and x['optical_grid_ps']==1.25]
    for c in ['TT','SS','FF']:
        groups[f'continuous_{c}']=exact(f'continuous-{c}-r10-restored-frame','continuous-v3-r1')
    status={k:dict(complete=bool(v),all_numerical_gates_passed=bool(v) and all(x['passed'] for x in v),
                   records=[dict(case=x['case'],analysis_label=x['label']) for x in v]) for k,v in groups.items()}
    missing=[k for k,v in status.items() if not v['complete']]
    failed=[k for k,v in status.items() if v['complete'] and not v['all_numerical_gates_passed']]
    startup=[]
    for p in sorted(BUILD.glob('startup-*-r10/result.json')):
        r=json.loads(p.read_text())
        if not r.get('simulation_ok'):continue
        startup.append(dict(case=r['case'],ramp_ns=r['config']['ramp_ns'],duration_ns=r['config']['duration_ns'],
                            device_screen_passed=r['device_screen_passed'],max_terminal_V=r['max_terminal_V'],
                            over_terminal_screen_mV=max(0.,(r['max_terminal_V']-3.63)*1e3),result=str(p.relative_to(ROOT)),result_sha256=sha(p)))
    unresolved_startup=[x for x in startup if not x['device_screen_passed']]
    result=dict(schema_version=1,scope='Finite schematic-level r10 research checks; status does not assert hardware, optical BER, physical PVT, full-loop stability or PEX qualification',
                frozen_source=dict(path=str((CIR/'regulated-r10.spice').relative_to(ROOT)),sha256=sha(CIR/'regulated-r10.spice')),
                required_checks=status,missing_checks=missing,failed_checks=failed,all_listed_frame_checks_completed_and_passed=not missing and not failed,
                startup_diagnostics=startup,unresolved_startup_terminal_screen_cases=unresolved_startup,
                frame_records=rows,source_script_sha256=sha(Path(__file__)))
    emit(EV/'final-r10-index.json',result)
    lines=['# r10 实现收尾与工程说明','',
           '本文件由完成记录生成；原始网表、仿真结果和分析不覆盖。它是报告编写与跨电脑接续的实现记录，不代替独立审查。','',
           '## 当前验证清单','',
           '| 检查 | 完成 | 数值联合筛查 |','|---|---|---|']
    for k,v in status.items():lines.append(f"| {k} | {'是' if v['complete'] else '待完成'} | {'通过' if v['all_numerical_gates_passed'] else ('未通过' if v['complete'] else '未判定')} |")
    lines+=['','## 修改与边界','',
            '- r10 相对 r8 只把激光稳压输出电容从 1 nF 改为 10 nF，激光 Miller 串联电阻从 10 kΩ 改为 100 kΩ；73 个 MOS 连接和尺寸未改变。',
            '- 10 nF 是外部理想去耦假设，ESR 为 0.1 Ω，基线没有 ESL。另做 0.5 nH 控制实验；这不是实际封装或 PCB 提取。缓冲轨仍为 1 nF。',
            '- 数据目标、150 fF VCSEL 电容假设、原光学代理及 5 GHz 接收代理保持不变。0/4096 是短确定性测试观察值，不是实测 BER。',
            '- SS 两条稳压支路工作于 dropout；没有低频向下单位增益交点不代表相位余量足够。旧 AC 助手只枚举向下交越，r10 六曲线在约 8.83–10.45 MHz 还会向上交越；输入电容加载在没有有源反馈的电路里也能产生这一项。',
            '- 因此保留的首个 180+phase 数字只是历史算术量，不能作为真实 return ratio、相位余量或稳定性证据。保留全 1 Hz–1 GHz 复数曲线；这也不等于已经证明高频振荡。r10 当前支持范围仅为完成的有限时域实验，详见 audit-ac-all-crossings.json。',
            '', '## 尚未闭合的启动应力','',
            '正常数据帧的联合通过不等于任意上电时序可用。FF 的 20 ns 同步上电在 50 ps 短窗对照中仍超过 3.63 V 端压筛查线；应保留失败，后续需要电源时序/钳位方案。0.5 µs 短窗用于峰值数值复核，不用于判断几十微秒后的稳态建立。','',
            '| 启动案例 | 上升时间 / ns | 窗口 / ns | 最大端压 / V | 超过3.63V / mV |',
            '|---|---|---|---|---|']
    for x in startup:
        lines.append(f"| {x['case']} | {x['ramp_ns']:.0f} | {x['duration_ns']:.0f} | {x['max_terminal_V']:.9f} | {x['over_terminal_screen_mV']:.6f} |")
    lines+=['', '## 能量与电容储能','',
            '下面的端口能量只覆盖 4736 bit / 1.28 µs 数据帧，并除以 4096 个尝试净位。启动、预充和发码前等待另记。ΔU 为所列显式电源与补偿电容的终值储能减初值储能：负数表示帧中释放了原有储能。它未覆盖 MOS 内部电荷、负载及封装全部储能，不是完整能量守恒核算，也不能直接修正成光链路能效。','',
            '| 案例 / 分析 | E+ / pJ每尝试净位 | 显式 ΔU / pJ每尝试净位 | 单侧时间 / ps | 联合筛查 |',
            '|---|---|---|---|---|']
    for x in rows:
        if x['config']['revision']!='r10':continue
        delta='未记录' if x['explicit_delta_U_pJ_per_offered_payload_bit'] is None else f"{x['explicit_delta_U_pJ_per_offered_payload_bit']:+.6f}"
        lines.append(f"| {x['case']} / {x['label']} | {x['positive_pJ_per_offered_payload_bit']:.6f} | {delta} | {x['time_margin_ps']:.3f} | {'通过' if x['passed'] else '未通过'} |")
    lines+=['','对于从零上电后只发送一帧的使用方式，应另加启动及等待的输入能量；连续帧的统计不能替代这一预算。外部基准芯片内部、串行器、时钟和真实光接收器的功耗仍未实现。','',
            '## 连续运行恢复','',
            '原 continuous-TT-r10 在 360 秒进程上限被中止，日志已接近 61.28 µs 终点；失败记录保留。run_continuous_restored_r10.py 只把运行时限改为 900 秒，电路和求解设置不变。恢复名添加 -restored，使用同一次上电轨迹接续数据，提取前保留 20 ns 状态预历史，不重新建立 DC。','',
            '冻结 r10 原 runner 不变；恢复来源见 recovery-runtime-contract.json。loop_ac_r10.py 可重构六条 AC deck 并核对原始复数数据；默认不重跑已有结果。','',
            '## 可复现命令','',
            '```sh','build/layout/venv/bin/python scripts/vcsel_robustness_20261029/complete_frames_r10.py',
            'build/layout/venv/bin/python scripts/vcsel_robustness_20261029/complete_continuous_r10.py',
            'build/layout/venv/bin/python scripts/vcsel_robustness_20261029/loop_ac_r10.py',
            'build/layout/venv/bin/python scripts/vcsel_robustness_20261029/summarize.py',
            'build/layout/venv/bin/python scripts/vcsel_robustness_20261029/engineer_notes_r10.py','```','',
            '在新电脑上需先恢复对应 build 原始输入及锁定的公开 PDK 模型；本文件不下载或更换依赖。上面 continuous 命令复用已完成结果；不覆盖失败 case。']
    (EV/'engineer-notes.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(missing=missing,failed=failed,frame_records=len(rows)),ensure_ascii=False))


if __name__=='__main__':main()
