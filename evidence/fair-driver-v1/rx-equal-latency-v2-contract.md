# RX v2：共同绝对延迟预算

状态：2026-10-25 已冻结源码与测试，通过只读数学复核。v2 用于对原有 native 波形统一重分析；本工作未运行新 SPICE，未修改旧 `receiver.py`、正式冻结 inputs 或原始 result。

## 修正原因与固定边界

v1 将候选延迟限制为每路 0.5–2 symbol、每 symbol 128 格。在相同净 bit 率下，PAM4 的 symbol UI 是 NRZ 的两倍，因此 v1 给 C 的绝对延迟预算与网格间隔也是 NRZ 的两倍；高率 NRZ 的电路群延迟还可能被 2-symbol 上限截断。这是接收分析比较方法的缺口，不能归结为被测电路本身失败。

v2 对 A/B/C 和所有速率采用同一个 **0–8 ns（含端点）、5 ps 间隔、共 1,601 点**的绝对延迟网格。整数 ps 生成网格后换算为秒，实际评分与采样使用绝对秒；symbol UI 值只作派生说明。这是本项目的离线测试假设，不是已实现 CDR、时钟恢复或产品延迟能力。

保持原 PRBS15、seed `0x5ACE`、4,736 个原始 bit、Gray 映射、目标 25/50/75/100 µA、净吞吐定义、输入导电电流、光学代理 τ=200 ps、RX 一阶 1 GHz、DC 初态、固定阈值以及 **7.5 µA / 100 ps** 门槛。v2 不改 LED、驱动电路、电流源、SPICE 网格或模型。

## 训练区与防泄漏

所有范围均按 bit 下标，左闭右开。

| 分段 | 范围 | 含义 |
|---|---|---|
| warmup | `[0,64)` | 64 bit，非 payload |
| training | `[64,576)` | 512 bit 全部计入开销 |
| training_scoring | **`[64,512)`** | 448 bit；NRZ 448 symbol / PAM4 224 symbol |
| training guard | **`[512,576)`** | 末 64 bit 共同保护区 |
| validation | `[576,4672)` | 4,096 payload bit |
| tail | `[4672,4736)` | 64 bit，非 payload |

`make_stimulus()` 的 `bits`、`symbols_N`、`symbols_C`、`eta`、seed 与 Gray 映射和 v1 完全相同；帧内唯一的评分范围变更是 `training_scoring`。schema 与说明文字标为 v2。发送 bit 与电气激励不变，全部 512 training bit 仍计入开销，`eta=4096/4736=32/37` 不变。

在本轮最高净 2 Gb/s 下，bit UI 为 0.432432 ns，64-bit guard 为 27.675676 ns。保守扣除 8 ns 搜索预算仍有 19.675676 ns；按最后一个实际训练样本计算，到验证起点的余量为 NRZ 20.108108 ns、PAM4 20.540541 ns。验证末样本到整帧末端的余量相同。若未来传入的速率高到训练保护区或帧尾不足，函数会报错，不以波形外推或读取验证段来补足训练。

训练候选首先最大化最小有符号判决电流余量；与最大值差不超过 **1 pA = 10⁻⁶ µA** 的候选，再最大化训练样本的最小绝对时间余量；完全同分时选最早绝对延迟。验证段的标签、样本和时间余量都不参与此选择。

训练时间边界缓存只使用 `t < origin + 576 bit UI` 的波形；左边界夹在 `origin + 64 bit UI`，右边界夹在验证起点前最后一个观测时间点。即使缓存中包含 warmup 的早期交叉，余量也不能越过训练左边界。验证开始及之后的波形、bit 和符号标签改变，完整 `sampling` 结果必须不变。

## 时间余量与计算方式

滤波递推与 v1 源码一致，保留原始 native 时间点并采用分段线性输入。阈值穿越先按每个阈值计算，再组合为各期望判决区间的边界缓存；1,601 次候选评分复用训练缓存，不反复扫描百万级波形。验证时间余量使用验证指标自己的完整波形边界缓存，不反馈训练。

v2 额外修正了一个精确阈值平台的边界处理：严格跨阈值的插值交叉、恰等于阈值的平台首尾、孤立接触点都作为边界。v1 只保留平台进入点时，会把平台之后的时间余量算得过大。例如平台为 1–2 ns，3 ns 采样，最近边界应是 2 ns，余量 1 ns；修正前错误地得到 2 ns。本修正没有移动阈值或增加任何容差。

时间余量仍定义为冻结采样点到正确判决区间最近边界的**最小单边容许偏移**，不是 peak-to-peak 眼宽。错误或恰在阈值的样本时间余量为零。验收使用绝对 100 ps，不用 PAM4 较长的 symbol UI 抵扣。

## API 与结果兼容

```python
from scripts.fair_driver_v1.receiver_equal_latency_v2 import make_stimulus, analyze

stimulus_v2 = make_stimulus()
result_v2 = analyze(t_s, i_led_A, stimulus_v2, route="A", net_rate_Gbps=1.0)
```

结果保留 `rates`、`ranges_bits`、`proxy`、`sampling`、`validation`、`horizontal_margin`、`conditional_noise_BER`、`checks`、`passed` 等既有层级，schema 为 2。主要新增或明确的 `sampling` 字段：

| 字段 | v2 值或含义 |
|---|---|
| `delay_s` | 选定的绝对延迟，主表示 |
| `delay_symbol_UI` | `delay_s / symbol_UI`，派生表示 |
| `search_delay_s` | `[0, 8e-9]` |
| `absolute_delay_budget_ns` | `8.0` |
| `absolute_delay_grid_ps` | `5` |
| `delay_candidate_count` | `1601` |
| `phase_grid_per_symbol` | `null`，不再暗示固定 UI 网格 |
| `effective_grid_per_symbol` | 当前 `symbol_UI / 5 ps`，可为非整数 |
| `search_delay_symbol_UI` | 当前 `[0, 8 ns / symbol_UI]`，仅供说明 |
| `training_scored_bits` / `training_guard_bits` | `448` / `64` |
| `training_time_margin_bounds_s` | 实际训练时间余量的左右夹取边界 |
| `training_to_validation_slack_s` | 最大延迟下末训练样本距验证起点余量 |
| `validation_to_frame_end_slack_s` | 最大延迟下末验证样本距帧尾余量 |
| `training_scan` | 全部 1,601 候选的延迟、评分、错误及平台诊断 |

`validation.bit_errors` 仍为 4,096 payload bit 的原始错误数；Gray bit 还原、SER、全部转换统计、最小/平均有符号电流余量和 Gaussian 条件噪声估计的定义均不变。旧 v1 stimulus 的评分范围不符合 v2，调用方应生成并冻结 v2 stimulus，并确认原始 bits 与旧输入相同。

## 校验与独立复核

```sh
.venv/bin/python -m unittest scripts.fair_driver_v1.test_receiver_v2 -v
.venv/bin/python -m unittest scripts.fair_driver_v1.test_receiver -v
.venv/bin/python scripts/fair_driver_v1/test_harness.py
.venv/bin/python -m unittest discover -s tests -v
```

- v2 **9/9**：理想 NRZ/PAM4、相同绝对候选网格、超过 2-symbol 的 NRZ 延迟恢复、最高速率保护区、验证波形及一致 bit/Gray 标签扰动、平台规则、阈值平台退出边界、独立部分分式滤波对照、错误与幅度不足负控。
- v1 **13/13**、harness **4/4**、仓库既有纯 Python **38/38** 通过。harness 最初经包模块入口调用遇到其 `import run` 路径错误，使用原脚本入口后通过；未修改 harness。
- 独立只读审查确认训练边界与标签隔离；另用逐段 PWL 零集合/零区间距离算法检查 200 组含平台样例，与缓存时间余量差为 0 ps。没有剩余阻断项。

合成长延迟负控：理想 NRZ、净 1 Gb/s，额外纯传输延迟 2.5 ns。v1 搜索被截断，验证得到 2,073 bit 错误；v2 选定 3.37 ns（3.89656 symbol UI），零错误、最小电流余量 33.9422 µA、时间余量 291.031 ps。此结果只验证接收算法和预算修正，不是新晶体管性能结果。

| 冻结文件 | SHA-256 |
|---|---|
| `scripts/fair_driver_v1/receiver_equal_latency_v2.py` | `54e016be473be37a32d2da84956009e6cab78942c6206f3f3c16a086d80195e0` |
| `scripts/fair_driver_v1/test_receiver_v2.py` | `cf0d2738d5a125c64998edebf778fc5b0b87a212a019d17087f339afb70b6445` |
| 保留的 `scripts/fair_driver_v1/receiver.py` | `f7d815223c190a9e0803f672523754006670a0cfe9738c57462510cce5049cc9` |

## 证据版本边界

全部旧 SPICE 波形、输入和 v1 result 保留；v2 结果须存为新重分析身份，不能覆盖旧结果。此前 `rx-audit.json` 是 v1 三点独立审计；C 短内部节点诊断采用的 3.891891892 ns 采样时刻来自 v1，不能改称 v2 最优时刻。

最终 A/B/C 比较应统一采用 v2 重分析结果，不混用两版接收器选取各自更好的点。v2 修正不能替代实际时钟实现、器件电压/体结检查、数值步长对照、物理实现、真实光学模型或实测 BER。
