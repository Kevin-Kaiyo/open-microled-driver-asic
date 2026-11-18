"""Make a compact per-window comparison, explicitly marking shared historical evidence."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BUILD=ROOT/'build/driver-ab-20261118/b'
OLD=ROOT/'build/driver-pvt-20261117/b/clamp5v_buffer_soft'
EV=ROOT/'evidence/driver-ab-20261118/b'
CASES=[
    ('历史 44 MOS',OLD/'tt-normal1-s40'),
    ('W4/L2 / R200',BUILD/'merged220c10/tt-normal1-s40'),
    ('W4/L2 / R260',BUILD/'merged220c10r260/tt-normal1-s40'),
    ('历史 44 MOS',OLD/'ss_hot_low-full-s40'),
    ('W4/L2 / R200',BUILD/'merged220c10/ss_hot_low-full-s40'),
    ('W4/L2 / R260',BUILD/'merged220c10r260/ss_hot_low-full-s40'),
    ('W4 / N4',BUILD/'merged220c10r260n4/ss_hot_low-full-s40'),
    ('W4 / CIB1 4 fF',BUILD/'merged220c4r260/ss_hot_low-normal1-s40'),
    ('W4 / CFF 36 fF',BUILD/'merged220c10r260ff36/ss_hot_low-normal1-s40'),
    ('W4 / N4',BUILD/'merged220c10r260n4/ss_hot_low-normal1-s40'),
    ('W4 / N4 + CFF 36 fF',BUILD/'merged220c10r260n4ff36/ss_hot_low-normal1-s40'),
    ('历史 44 MOS，本轮重跑',ROOT/'build/driver-ab-20261118/b_review/reference/clamp5v_buffer_soft/ff_cold_high-full-s40'),
    ('W4/L2 / R200',BUILD/'merged220c10/ff_cold_high-full-s40'),
    ('W4/L2 / R260',BUILD/'merged220c10r260/ff_cold_high-full-s40'),
]
def main():
    rows=[
      '# B 各完整协议的结果',
      '',
      '仅同一工况、同一帧窗可直接比较能耗。TT 普通帧为 2.56 µs，SS 与 FF 的故障帧记录为 5.12 µs。关断指标和器件应力取完整故障记录，接收、能耗取恢复后的第二帧。单独的 SS 普通帧列也只使用首帧。表内 R200/R260 表示 200/260 kΩ 的钳位门电阻。W4 集成版的 PISO 门电阻为 220 kΩ，CIB1 默认为 10 fF，原 CFF 为 31.275 fF。N4 仅加宽 XINV2N 至 4 µm。',
      '',
      '| 电路 | 工况 / 帧 | 训练 / 验证错位 | 幅度 (µAeq) | 单侧 (UI) | E+ (pJ/b) | 20 ns 后关断 (µA) | 恢复上界 (ns) | MOS 应力 |',
      '|---|---|---:|---:|---:|---:|---:|---:|---|'
    ]
    for label,p in CASES:
        r=json.loads((p/'result.json').read_text())
        f=r['frames'][-1];rx=f['full_receiver'];off=r.get('shutdown',{})
        guard=off.get('max_abs_current_uA');bound=off.get('recovery_screen',{}).get('upper_bound_ns')
        scope={'ss_hot_low':'SS 热低压','ff_cold_high':'FF 冷高压','tt':'TT 名义'}[r['case']['pvt_key']]
        window=f'故障后 F{f["frame"]}' if off else '普通 F1'
        data=[label,scope+' '+window,f"{rx['train_errors']} / {rx['errors']}",f"{rx['worst_signed_margin_uAeq']:.4f}",f"{rx['one_sided_margin_bit_UI']:.6f}",f"{f['energy_pJ_per_attempted_payload_bit']['positive']:.6f}",'—' if guard is None else f'{guard:.5f}','—' if bound is None else f'{bound:.2f}','通过' if r['terminal_pass'] and r['body_pass'] else '超限']
        rows.append('| '+' | '.join(data)+' |')
    rows.extend(['','0.37 UI 相当于 200 ps，单侧时间余量、幅度 7.5 µAeq、训练与验证零错需同时满足。恢复上界按首次训练后冻结的采样相位计算，其中要求余下整段都保持幅度和时间余量。此处没有对硬件作 BER、稳态热或可靠性资格判定。',''])
    (EV/'full-frames.md').write_text('\n'.join(rows))
if __name__=='__main__':main()
