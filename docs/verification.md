# Phase 1 验证与证据读取

状态日期：2026-10-03。机器可读结果见 [`summary.json`](../evidence/phase1/summary.json)，逐 case 指标见 [`metrics.csv`](../evidence/phase1/metrics.csv)。数字、模拟和物理证据必须分别描述。

## 已执行的检查

| 层次 | 检查内容 | 当前证据 |
|---|---|---|
| RTL | 0…256 全部 duty、257…511 clamp；frame-boundary update、enable、同步 reset、256→0→256 | 518 完整 frame，133,159 checks；[`rtl-selfcheck.log`](../evidence/phase1/rtl-selfcheck.log) |
| Bridge | 实际 RTL timestamp → 10 ns PWL、边界状态、非均匀时间积分、缺失区间、重叠 ramp、RTL window drift | 6 个 Python unittest |
| LED calibration | 独立 100 μA current source、27 °C、目标 Vf=2.4/2.8/3.2 V、误差 <0.1 mV | [`led-calibration.json`](../evidence/phase1/led-calibration.json) |
| Coupled transistor simulation | 7 个 nominal duty 点、disable、2 个 Vf variants、3 个低供电点、FF/SS、0/85 °C、2 个 convergence reruns | 19 个 runs，外加 3 个独立 LED runs |
| Analog assertions | 7 个 current/duty 误差、2 个 off、Vf regulation、3 个 coupled Vf、headroom negative control、2 个 timestep checks、3 个独立 LED calibration | 19 checks，全部通过 |
| Layout / silicon / optics | DRC、LVS、PEX、GDS、测量 | 尚未执行 |

RTL exhaustive coverage 不代表模拟电路已在全部 duty / PVT 组合下验证。FF、SS 在 27 °C / 5 V / full-on 单点运行；temperature 在 typical / 5 V / full-on 单点运行。当前不开启 global variation / mismatch，reference 仍理想。测试标准是教学 baseline 的回归门限，不是商业精度要求。

## 测量定义与门限

- Clock period 1 μs，首个 frame 从 2.5 μs 开始；预热 2 frame 后测量 `[514.5, 1538.5] μs`，共 4 个完整 256 μs frame。Runner 验证 TB 报告的 TRACE 时间窗，阻止未来改时钟/预热后静默使用旧窗口。
- RTL logical edge 从其 timestamp 开始变成 10 ns 的 0↔3.3 V ramp。这是输出 buffer 的假设；不包含标准单元、电平转换、pad / ESD、封装或走线寄生。
- `VSENSE` 的正电流从 supply 流入 LED；它含 diode conduction 与 charge/displacement 部分。报告保留 peak / minimum branch current；完整稳定 frame 上的积分是 current-based brightness proxy，不是光功率或发光峰值。
- Adaptive SPICE samples 按时间做 trapezoidal integration，并对窗口两端插值。禁止简单平均 samples。Plateau 是 PWM 高时排除 edge 后 100 ns 的 current 中位数，不能代替全 pulse area。
- Nominal 平均 current 与 `D × Iavg(full-on)` 的差必须 ≤`max(0.01 μA, expected × 3%)`；off / disable 的绝对平均 current <1 nA。
- Vf=2.4…3.2 V 三点 current spread < nominal full-on 的 10%；独立 LED calibration 另用 0.1 mV 严格校验。Coupled full-on actual Vf 与 100 μA reference target 比较时采用 10 mV 门限，容纳实际 mirror current 与 100 μA 的小偏差。
- 2.9 V supply 的 headroom negative control 必须降到 nominal full-on 的 90% 以下。实际结果约 49.39 μA；保留这个失败余量点，避免只展示高余量 nominal 点。
- Duty=1、64 的最大 timestep 从 200 ns 缩到 20 ns，积分的相对变化必须 <0.5%。这是积分 convergence；不等同于所有 transient peak 或电气应力已收敛。

## 模型校准故障与修正

早期以 N=2.2 构造高 Vf 时，计算出的 IS 过小。ngspice 47 将其静默钳到默认 floor；Vf=3.2/4.8 V 两个 target 给出相同实际曲线，干净 log 没有揭示问题。[ngspice 官方 diode setup 源码](https://sourceforge.net/p/ngspice/ngspice/ci/master/tree/src/spicelib/devices/dio/diosetup.c?format=raw) 明确这项下限处理。

最终采用 **synthetic effective N=3**，限定校准范围 2.4–3.2 V，并加入独立 DC 检查。当前三点实际 Vf 误差约 1 μV，低于 0.1 mV 门限。Headroom 检查改为降低 supply。这个修正解决模型与目标不一致的问题，没有获得实际 MicroLED 的物理参数；N=3 仍是教学假设。

## 证据文件与复现

- `build/phase1/<case>/` 保存实际 RTL event CSV、testbench SPICE、ngspice log 和原始 adaptive `waveform.dat`。模型文件通过 relative symlink 引用 hash-checked cache；从其他工作目录也可调用 runner。
- 版本控制中的 `waveform-duty064.csv` 是两个 measured frame 的 **200 ns uniform interpolation**，用于低频波形复核，不能从它重建 10 ns edge peak。
- `edge-duty064.csv` 保留同一 case 一个 turn-on 周围的原始 solver samples。PNG 图由原始 adaptive samples 绘制；可编辑 SVG 在本地 build 中生成。
- `source-hashes.json` 对本次 RTL、testbench、analog source、runner 与 model lock 记录 SHA256。工具版本、host、参数、窗口、分母与每一项检查均保存在 summary 中。
- Model downloads 逐文件校验 SHA256。SPICE run 前移除该 case 的旧 waveform，失败不能复用 stale data；若缺少完整、有限、单调的输出，则 runner 失败。全部检查通过后才能 `make evidence` 覆盖精简 evidence。
- Python dependencies 在 `uv.lock`；native EDA 版本记录在 summary。未来升级 tool / PDK 后必须重跑并保存新证据，旧结果不自动适用。GitHub CI 是 Linux regression，不能代替 Mac 或 physical validation。

当前 reference current、MOS 尺寸、合成 LED、有限边沿和测试电压都是公开可检查的设计假设。未验证项包括真实 LED I-V / temperature / optical response、noise、mismatch / Monte Carlo、全 PVT、电压 stress、reference generation、array fanout、physical timing / glitches、IR drop、pads / ESD 和 MPW acceptance。
