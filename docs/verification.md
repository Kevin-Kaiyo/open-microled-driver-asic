# Phase 1 验证与证据读取

状态日期：2026-10-05，v0.4。机器可读基本回归见[`summary.json`](../evidence/phase1/summary.json)，逐case指标见[`metrics.csv`](../evidence/phase1/metrics.csv)。下表仍描述20/4、registered PWM的synthetic baseline；[分层研究报告](research/research-report.md)另记录真实静态LED、reference/PVT、mismatch、digital physical、v0.3共同top及v0.4联合signal PEX／电气边界。旧[全面检阅](review/README.md)保留为10/2历史快照。

## 已执行的检查

| 层次 | 检查内容 | 当前证据 |
|---|---|---|
| RTL | 0…256 全部 duty、257…511 clamp；frame-boundary update、enable、同步 reset、256→0→256 | 518 完整 frame，133,159 checks；[`rtl-selfcheck.log`](../evidence/phase1/rtl-selfcheck.log) |
| Bridge | 实际 RTL timestamp → 10 ns PWL、边界状态、非均匀时间积分、缺失区间、重叠 ramp、RTL window drift | 7 个 Python unittest，含 source provenance 排除检查 |
| LED calibration | 独立 100 μA current source、27 °C、目标 Vf=2.4/2.8/3.2 V、误差 <0.1 mV | [`led-calibration.json`](../evidence/phase1/led-calibration.json) |
| Coupled transistor simulation | 7 个 nominal duty 点、disable、2 个 Vf variants、3 个低供电点、FF/SS、0/85 °C、2 个 convergence reruns | 19 个 runs，外加 3 个独立 LED runs |
| Analog assertions | 7 个 current/duty 误差、2 个 off、Vf regulation、3 个 coupled Vf、headroom negative control、2 个 timestep checks、3 个独立 LED calibration | 19 checks，全部通过 |
| Standalone analog layout | Magic DRC、Netgen LVS、GDS 回读、RC 抽取 | DRC=0；LVS 唯一匹配；7/7 nets；59 R / 43 C，见 [版图证据](../evidence/layout/summary.json) |
| Paired post-layout | 完整 PDK 下 schematic / RC 两版，17 条件 + RC 两次 timestep refinement | 36 transient + 3 LED DC；19 guards 全通过，见 [版图说明](layout/README.md) |
| Digital mapping / physical | Registered PWM mapping、CTS/routing、STA、SDF、GDS/LEF | 实际数字结果和工具限制见[digital physical](digital/physical.md)；不以analog checks代替 |
| Silicon / optics | 制造与本项目光测量 | 尚未执行 |

RTL exhaustive coverage 不代表模拟电路已在全部 duty / PVT 组合下验证。本页baseline的FF/SS和temperature为少量pilot cases、统计关闭、理想reference。独立[actual RC研究](research/reference-and-matching.md)另完成1080点reference/PVT及五组各256MC；[实测静态负载](research/measured-led.md)另有135点固定MOS温度网格，均记录自己的条件和分母。

Paired post-layout 的小差异只约束两套网表之间的相对变化，不能替代相对 `IREF=100 μA` 的绝对误差。当前 schematic 与 extracted 网表除了 wire RC，也存在 diffusion area / perimeter 参数的差别，影响器件结电容等项；两者 transient 差异不能全部归因于布线 RC。研究纯布线影响时，需要先建立相同 diffusion geometry 的 schematic 对照。

## 测量定义与门限

- Clock period 1 μs，首个 frame 从 2.5 μs 开始；预热 2 frame 后测量 `[514.5, 1538.5] μs`，共 4 个完整 256 μs frame。Runner 验证 TB 报告的 TRACE 时间窗，阻止未来改时钟/预热后静默使用旧窗口。
- RTL logical edge 从其 timestamp 开始变成 10 ns 的 0↔3.3 V ramp。这是输出 buffer 的假设；不包含标准单元、电平转换、pad / ESD、封装或走线寄生。
- `VSENSE` 的正电流从 supply 流入 LED；它含 diode conduction 与 charge/displacement 部分。报告保留 peak / minimum branch current；完整稳定 frame 上的积分是 current-based brightness proxy，不是光功率或发光峰值。
- Adaptive SPICE samples 按时间做 trapezoidal integration，并对窗口两端插值。禁止简单平均 samples。Plateau 是 PWM 高时排除 edge 后 100 ns 的 current 中位数，不能代替全 pulse area。
- Nominal 平均 current 与 `D × Iavg(full-on)` 的差必须 ≤`max(0.01 μA, expected × 3%)`；off / disable 的绝对平均 current <1 nA。
- 关断的约 3.6 pA 是指定求解设置下的结果，不能作为已验证的物理 leakage。独立 GMIN sweep 在同一 RC 网表上得到明显不同的 pA 数值，说明默认数值电导主导这一量级；可保留上述 <1 nA 的模型回归结论，真实 leakage 需器件模型和测量支持，详见 [数值检阅](review/numeric-audit.md)。
- Vf=2.4…3.2 V 三点 current spread < nominal full-on 的 10%；独立 LED calibration 另用 0.1 mV 严格校验。Coupled full-on actual Vf 与 100 μA reference target 比较时采用 10 mV 门限，容纳实际 mirror current 与 100 μA 的小偏差。
- 2.9 V supply 的 headroom negative control 必须降到 nominal full-on 的 90% 以下；当前尺寸约48.83 µA（pre-layout、synthetic Vf=2.8 V）。保留失败余量点，真实静态LED的供电扫描另计。
- Duty=1、64 的最大 timestep 从 200 ns 缩到 20 ns，积分的相对变化必须 <0.5%。这是积分 convergence；不等同于所有 transient peak 或电气应力已收敛。
- 独立积分重算与收紧容差/切换积分方法支持当前平均电流结果，但 full-on 小纹波随 trapezoidal / Gear 和 timestep 明显变化。`peak` / `minimum` 暂属原始求解输出，不能据此确立物理 ripple、settling、rise/fall time 或 bandwidth；这些指标需要各自的收敛与模型适用性检查。

## 模型校准故障与修正

早期以 N=2.2 构造高 Vf 时，计算出的 IS 过小。ngspice 47 将其静默钳到默认 floor；Vf=3.2/4.8 V 两个 target 给出相同实际曲线，干净 log 没有揭示问题。[ngspice 官方 diode setup 源码](https://sourceforge.net/p/ngspice/ngspice/ci/master/tree/src/spicelib/devices/dio/diosetup.c?format=raw) 明确这项下限处理。

最终采用 **synthetic effective N=3**，限定校准范围 2.4–3.2 V，并加入独立 DC 检查。当前三点实际 Vf 误差约 1 μV，低于 0.1 mV 门限。Headroom 检查改为降低 supply。这个修正解决模型与目标不一致的问题，没有获得实际 MicroLED 的物理参数；N=3 仍是教学假设。

## 证据文件与复现

- `build/phase1/<case>/` 保存实际 RTL event CSV、testbench SPICE、ngspice log 和原始 adaptive `waveform.dat`。模型文件通过 relative symlink 引用 hash-checked cache；从其他工作目录也可调用 runner。
- 版本控制中的 `waveform-duty064.csv` 是两个 measured frame 的 **200 ns uniform interpolation**，用于低频波形复核，不能从它重建 10 ns edge peak。
- `edge-duty064.csv` 保留同一 case 一个 turn-on 周围的原始 solver samples。PNG 图由原始 adaptive samples 绘制；可编辑 SVG 在本地 build 中生成。
- `source-hashes.json` 对本次 RTL、testbench、analog source、runner 与 model lock 记录 SHA256。工具版本、host、参数、窗口、分母与每一项检查均保存在 summary 中。
- Model downloads 逐文件校验 SHA256。SPICE run 前移除该 case 的旧 waveform，失败不能复用 stale data；若缺少完整、有限、单调的输出，则 runner 失败。全部检查通过后才能 `make evidence` 覆盖精简 evidence。
- Python dependencies在`uv.lock`；native EDA版本记录在summary。升级tool／PDK后需重跑并保存新证据。GitHub CI template尚未启用，本页基本回归未在Linux CI执行；已经执行的Linux数字／共同top physical flow有独立证据，不能由软件CI互相替代。

当前 reference current、MOS 尺寸、合成 LED、有限边沿和测试电压都是公开可检查的设计假设。此基本回归未包含统计 mismatch、完整 PVT、真实动态与光学、非理想供电或制造接受；独立 MC / 静态数据 / 数字物理研究有各自证据，不能由本页 pilot cases 代替。

## v0.3 的历史集成证据

[共同 top](../evidence/integration/summary.json)记录实际 PWM / PG routing、完整 GDS extraction、数字保留 leaf 内部 MOS / analog / hierarchy LVS、Magic / KLayout DRC，以及真实物理开路和短路的拒绝结果。规则覆盖、忽略 cells/properties 与 substrate 边界在[集成说明](../layout/integration/README.md)公开。

[真实输出级](../evidence/interface/summary.json)包括54组主瞬态、DC／AC／电荷研究，另有[六组输入slew stress](../evidence/interface/slew-budget-summary.json)。原as-run snapshots与current RC等价映射保留；[独立复算](../evidence/research/interface-review.json)及[集成审查](../evidence/research/integration-review.json)核查数值和失败检测。它们描述v0.3分块模型；输出cell实际结几何与联合signal寄生在下一节另验证，不改写旧输入hash。

## v0.4：联合signal PEX与边界验证

[预设抽取条件](specifications/joint-pex-v0.4.md)和[电气门槛](specifications/electrical-v0.4.md)在新增结果前声明。实际从冻结共同GDS提取末级六MOS加模拟六MOS，nominal导出45个signal R、77个显式C、34邻居端口；另外四种RCstyle也执行真实提取。完整PG／body电阻及PG-only电容仍投影到ideal rails；它不是full-chip PEX或PG signoff。

| 检查 | 实际证据及结果 | 不能推出的结论 |
|---|---|---|
| 抽取／端口／geometry | 五种style；实际M3右侧接入；MOS junction、ordered ports、R/C multiset与signed-cap ledger见[joint PEX](research/joint-pex.md) | 不能再叠加旧buf／SPEF／link／analog RC，也不能把语义复现叫字节一致 |
| 同条件pre/post | 主研究37 transient／12 DC，146项工程guards通过；nominal RC三包络及SS×HRHC、FF×LRLC补充点，见[main](../evidence/robustness/main-summary.json) | 非所有MOS×RC×温度×供电组合穷举；synthetic LED不是实测动态模型 |
| 启动／reference／控制／供电边界 | 19 transient／4 DC数值完成；明确保留理想reference越界、frame-latched enable延迟与实测静态LED series-R失效，见[boundary](../evidence/robustness/boundary-summary.json) | 数值完成不是system startup qualification；branch peak含位移电流，signed source energy不是全芯片能耗 |
| 合计与独立复核 | 三批合计66 transient／28 circuit DC，另3组独立synthetic LED calibration；[summary](../evidence/robustness/summary.json)记录运行范围；[独立review](../evidence/research/v04-review.json)的13个复核阶段通过，包含18个实际错误负对照 | 不能把66个run称为66项功能验收，也不能以复算精度代替物理不确定度 |

在声明的MOS包络、ideal供电／reference及邻居clamp下，nominal post full-on为100.752788／100.112984／101.423393µA（TT／SS／FF），最低码面积误差为−0.251524／−0.681304／−0.188819%；补充SS×HRHC最低码为−0.700133%，满足原±2%门槛。三个MOS条件分别为TT27°C3.3/5V、SS85°C2.97/4.5V、FF0°C3.63/5.5V，电源顺序Vlogic/VLED；不混称数字Liberty角落。

边界结果与main pass并列保存：实测静态LED加假设RLED=10kΩ时电流88.265992µA，超出±5%；它是有意寻找headroom边界的假设阻抗，不是实际PDN值。实际RTL在20µs拉低enable，到258.5µs才提交PWM low；reset在20µs置高，20.5µs同步响应。若系统需要立即紧急关断，现有frame-latched enable不足，需另立控制/安全需求。

启动时ideal IREF可在零供电下主动送能，使bias高于live rail；这揭示理想源前提，而不是证明真实电源会如此工作。外部compliance模型/较晚reference只是在声明边界下缓解异常，没有新增real reference／POR。功耗积分仅覆盖selected十二MOS signal模型和明确外部R/C，真实PG charging、preceding logic、pads、package与optics未建立。[完整边界解释](research/robustness.md)、[bench验证计划](research/bench-validation-plan.md)和[方向门槛](research/technical-value-market.md)给出下一步。
