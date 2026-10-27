# VCSEL 模型与接收分析独立复核（2026-10-27）

复核范围：`vcsel_driver_run.py`、`vcsel_driver_analyze.py`、冻结的 v2 receiver、TT 3.2 Gb/s 原始波形与模型快照；只读复核，没有重跑驱动 SPICE，也没有改写电路代理的代码。模型代理由本次复核者编写，因此这里的“独立”专指对另一代理的电路和接收分析实施交叉检查，不是对整个模型的第三方独立验证。

**结果：没有发现会改变已报 TT 结论的归一化、训练隔离或五端口能量计算错误。原 v2 的 TT 在固定 100 ps 判据下失败的判断成立。**

| 复核项 | 结果与证据 |
|---|---|
| 线路 / 净载荷 | `4736 / 4096 = 37 / 32`；3.2 Gb/s net 对应 3.7 Gb/s line、UI≈270.270 ps。没有把 raw rate 当 net rate |
| 输入物理量 | 第一输出向量是 `v(jmon)`，表示 VCSEL 导电电流，排除 CJ 位移电流；晶体管、缓冲、参考与 dummy branch 都在实际 SPICE 内 |
| 冻结模型一致性 | TT 电学模型、Python 光学模块、参数 JSON 的运行快照 SHA-256 均与交付版本一致 |
| 光学 / RX baseline | 实际调用 `figure3mA_proxy`，随后 5 GHz RX pole；plan、result、模块调用一致。8 GHz 单极点与 1 GHz RX 均另列 control |
| 归一化 | P(3 mA)=1.431145 mW→25 µAeq；P(7 mA)=3.670528 mW→100 µAeq；固定 62.5 µAeq threshold 与 7.5 µAeq margin，没有用验证波形重拟合幅度。µAeq 不是光电流 |
| 训练与验证隔离 | scored training 为 bits[64:512]，validation 为 bits[576:4672]；8 ns delay search 后仍留约 9.568 ns guard slack。幅度评分只读训练标签；时间 tie-break 的波形前缀严格截止 validation 起点之前 |
| 五端口能量 | 重新读取压缩原始波形，按 `−Vport×Iport` 对 VLASER / VDD / VREF / VD / VDB 各自积分；与原 ledger 的最大差值 0 J；`positive−returned=net` 一致 |
| TT 能量数值 | 8.554852 pJ / offered payload bit（positive），8.500390 pJ / offered payload bit（net），分母 4096，包含整帧 overhead。不能称接收成功 bit 能耗或完整链路能耗 |
| TT 图读域 | 原始导电电流 2.730699–7.061765 mA，落在 2–7.5 mA 联合图读域。负光学代理功率比例 0；baseline domain gate 正确通过 |

`vcsel-model/independent-driver-recheck.json` 保存了重新计算与快照比对值。

关键结果交叉检查：

| 条件 | 验证错误 / 4096 bits | 最小单侧时间余量 | 结论 |
|---|---:|---:|---|
| TT 3.2 Gb/s，baseline | 0 | 87.312 ps | 小于固定 100 ps；通信筛选失败 |
| TT 3.2 Gb/s，1.25 ps 重采样 | 0 | 86.678 ps | 与 baseline 同一失败结论；不是靠网格边界勉强失败 |
| TT 3.2 Gb/s，8 GHz optical control | 0 | 61.967 ps | 失败 |
| TT 3.2 Gb/s，1 GHz RX control | 0 | 81.563 ps | 失败 |
| SS / hot circuit，3.2 Gb/s | 2061 | 0 ps | 失败；VCSEL 静态曲线仍是 25°C，不构成完整光学 PVT |
| FF / cold circuit，3.2 Gb/s | 0 | 105.887 ps | 接收筛选通过，但 P–I 超域时间约 48.94%，不能宣布组合通过 |
| TT 0.8 Gb/s，baseline | 0 | 53.614 ps | 同样因 100 ps 门槛失败；不能作为物理速率上限证据 |

需在主报告保留的三个解释边界：

1. **训练规则会影响失败机制。**现有 v2 先最大化最差训练幅度，仅在近等幅平台内最大化训练时间余量。共振/过冲波形可能使最大幅度采样点靠近边沿。TT 0.8 Gb/s 反而时间余量较小，说明该规则与波形形状的相互作用不可省略。这是固定合同下的筛选失败，不足以推断“电路物理上无法到 3.2 Gb/s”。改变训练目标应另开协议版本，不能事后移动本轮 gate。
2. **模型成熟度有限。**幅度图读不提供相位验证；固定 3 mA S21 形状用于大信号且未去嵌，与假设 CJ 联用可重复计入电学滚降。该 limitation 不因快照、数值检查或错误数为零而消失。
3. **能量边界明确。**五个已建模理想源端口的正向/返还能量完整；上游源损耗、serializer/CDR、真实 PD/TIA 与 RX 功耗均未计入。零错误的单帧不提供低 BER 置信界限。

复核建议：本轮可发布为失败与敏感性证据。若继续追求目标，优先独立评估训练目标对时间余量的影响、温度稳定电流参考，以及同器件复数 S11/S21 与大信号数据；不要把现有失败点解释成工艺或发光器件的理论极限。


## 后续独立 v3 诊断复核

父任务在观察 v2 的 amplitude-first 采样行为后，另立 `receiver-feasibility-v3-diagnostic`。复核确认：源 diff 只改变训练目标与相关元数据；所有 1601 个 delay 都按 `min(training signed margin / 7.5 µAeq, training minimum time margin / 100 ps)` 排序，严格 `>` 更新使最早完全同分候选胜出；固定门槛、64-bit guard、4736-bit frame 与验证区间未改变。v2 文件 SHA 与 contract 一致、未修改；v3 contract 的源 SHA 与实际文件一致。每组 plan 在读取与处理 raw transient 前写入，输出是独立目录。

另做了独立的 synthetic 检查（`vcsel-model/independent-v3-recheck.json`）：将 validation 起点后的全部波形翻转，448-bit 训练扫描的所有分数与最终 delay 完全不变，验证错误变为 4096；选择结果也等于训练分数首次最大值的位置。此检查仅验证算法隔离，不验证物理链路。

| v3 条件 | 错误 / 4096 | 时间余量 | 组合 screen |
|---|---:|---:|---|
| TT 3.2 Gb/s，默认 | 0 | 127.757 ps | 通过限定条件 |
| TT 3.2 Gb/s，SPICE step80 | 0 | 127.757 ps | 同一结论 |
| TT 3.2 Gb/s，CJ=500 fF | 0 | 129.738 ps | 通过该假设条件 |
| TT 3.2 Gb/s，8 GHz optical control | 0 | 129.001 ps | 通过该假设条件 |
| TT 3.2 Gb/s，1 GHz RX control | 0 | 109.901 ps | 通过该假设条件 |
| TT 0.8 Gb/s，默认 | 0 | 488.614 ps | 通过限定条件 |
| SS / hot circuit，3.2 Gb/s | 2061 | 0 ps | 失败 |
| FF / cold circuit，3.2 Gb/s | 0 | 115.887 ps | 模型域 / 器件等组合 gate 仍不通过 |

v3 支持的窄结论是：**在相同电路波形和代理假设下，改变训练目标即可找到同时满足现有幅度与时间门槛的 TT 采样点；v2 失败包含训练目标与共振波形的相互作用。**它不能反向改写 v2 结果，也不能升级为实际 CDR、全角落、真实 VCSEL 或低 BER 验证。

这还是一次 post-hoc 探索：v3 方法因已观察到的 v2 结果而提出，并复用了同一 validation 帧。代码层面的训练隔离并不等于全研究流程的预注册独立确认；若继续正式确认，应以新 seed / 独立 pattern 检验，并保留本次诊断身份。v3 输出还继承 `amplitude_plateau_tolerance_uA` 字段，但该字段在 v3 目标中未被使用；实际生效规则以 contract 和 `training_selection` 为准。


## 能量积分补充复核

初始原始 `result.json` 保留的是对 `max(P,0)` / `max(-P,0)` 作梯形积分的值。最终汇总新增 `energy-exact.json`，在原生时间网格上把线性功率段的零交点拆分，再分别积分正向与返还能量；原 result 未覆盖。复核者用另一套三角面积公式独立重算，五端口与最终 ledger 最大差为 2.59×10⁻²⁶ J。最终 TT 正向能量为 **8.554851646 pJ / offered payload bit**，相比原值只改变 −0.091489 ppm，net 仍为 8.500389735 pJ / offered payload bit。最终报告应采用 exact 汇总；此前本页的 8.554852 是初始结果的六位小数读数。详见 `vcsel-model/independent-exact-energy-recheck.json`。

## PRBS seed / 周期窗口审计

完整枚举确认该 PRBS15 recurrence 有 32767 个不同非零状态后回到原 seed。`0x1ACE` 相对原 `0x5ACE` 的周期偏移为 30253 bit，因此其 4736-bit 帧跨周期边界后与旧帧重叠 2222 bit，validation 区间重叠 1582 bit。它只能作为不同 seed 的相移对照，不能称为完全不重叠 holdout；原仿真与 contract 均应保留。

真正不重叠的下一窗口使用 offset=8192 对应 **seed `0x57AE`（22446）**。旧完整帧周期坐标为 [0,4735]、旧 validation 为 [576,4671]；新完整帧为 [8192,12927]、新 validation 为 [8768,12863]，上述窗口交集均为零。该检查和 seed 推导保存在 `vcsel-model/seed-overlap-audit.json`。不同周期窗口仍然属于同一个确定性 PRBS 序列，不能升级为独立随机 BER 证据。


不重叠窗口 `frame-TT-3p2-nonoverlap1` 已完成后续复核：contract 时间早于运行 manifest；9 项冻结源 SHA-256 仍匹配；运行 stimulus 同时匹配预声明 contract 与运行 manifest，我独立计算的 PRBS recurrence 与全部 4736 bit 一致。除 seed/name 外，电路、PDK、静态/动态模型、偏置、滤波、速率、步长及 gate 均保持原值。

| 新不重叠窗口 | 错误 /4096 | 最小幅度距离 | 单侧时间余量 | 组合 screen |
|---|---:|---:|---:|---|
| v2 | 0 | 36.315763 µAeq | 82.294293 ps | 失败 |
| 冻结 v3 | 0 | 35.061244 µAeq | 127.749485 ps | 条件性通过 |

新帧电流范围 2.730532–7.061765 mA，端压和联合静态图读域筛查通过。证据见 `vcsel-model/independent-holdout-recheck.json`。这降低了“结果仅来自原 validation 窗口”的疑虑，仍只增加一个确定性 PRBS 周期窗口的条件性证据，不消除代理模型、噪声、角落或物理实现的未验证项。


## 最终报告文本对表

已将主报告 README 的 VCSEL 段和结论与最终 summary 对表：不重叠帧 127.75 ps、1.0469 mW、8.5607 pJ / 尝试 payload bit，以及对应 v2 的 82.29 ps，四舍五入正确；0x57AE / offset8192 与 0x1ACE 的 1582-bit validation 重叠解释一致。报告保留了 v3 事后诊断、幅度图未验证相位/去嵌、静态 25°C 模型、SS/FF 失败和短帧非 BER 等边界。未发现本复核范围内的未解决阻断问题；本项是文本与数值复核，不是额外浏览器视觉检查。审阅快照 SHA 见 `vcsel-model/final-report-review.json`。
