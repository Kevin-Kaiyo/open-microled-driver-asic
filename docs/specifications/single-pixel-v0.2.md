# 单像素 v0.2 研究指标

日期：2026-10-04。用途为开源 ASIC/PWM 调光教学。下列门槛是本项目预先设定的研究目标，不是某商业器件的规格，也不是由已经通过的结果反推的参数。

## 电路和负载

保留 GF180MCU 六 MOS、100 µA 峰值目标、5 V nominal LED rail、3.3 V nominal logic、1 MHz clock、256 slots。数字输出应通过寄存器产生；duty 的 0/256、256/256 和帧边界更新语义不变。

合成 LED 保留为教学/回归基准；另以许可清楚的公开实测 I–V 建立独立 static model card。测量没有报告的温度、样品编号和动态特性以 unknown/null 记录，不用 simulator 的默认值填补实物属性。实测 static model 的 PVT 外推与电容/光学性能不在数据支持范围内。

## 预设验收门槛

| 指标 | v0.2 研究目标 | 验证范围 |
|---|---|---|
| Absolute full-on current | 相对 100 µA ≤±5% | 声明的负载/PDK/reference 条件；fixed-corner 与 Monte Carlo 分开报告 |
| Lowest-code area | `Q1 / (Ifull × 1 µs) − 1` 的绝对值 ≤2% | 周期稳态、实际执行 RTL 事件、10 ns nominal input slew；步长细化 |
| Frame timing | 每 frame 256 个 slots，合法/越界/enable/reset 行为正确 | 现有 exhaustive RTL 检查；mapped gate-level 另记分母 |
| PWM 输出 | 只由 output flip-flop 驱动 | 综合网表检查；有延迟模型时另行验证毛刺与最短脉冲 |
| Headroom | 在允许电流误差下求边界 | 以电流误差定义，不只看 saturation |
| Off current | 现有模型 guard <1 nA | 仅数值回归；不作为物理 leakage 规格 |
| Power | 分别报告 LED rail、reference/logic 和数字部分 | 先量化，未先承诺系统 standby 上限 |
| Analog physical | 严格 LVS、DRC 和可复现 extraction | 对所用公开规则；独立 KLayout 结果另记 |
| Digital physical | synthesis、STA、CTS/routing、GDS/LEF 与检查报告 | 工具运行成功才升级证据；macro 不包含 pad/ESD |

MOS/reference 组合探针采用 Vlogic=2.97/3.3/3.63 V、VLED=4.5/5/5.5 V、T=0/27/85 °C 与 5 fixed corners。该范围是教学研究 envelope。实测 LED 仅在原始数据覆盖的静态条件检验；未知的实物温漂不能被本 envelope 消除。

External reference 的误差和温漂行为模型单独说明设定、来源与校准点。它用于分配误差预算，不等于片上 reference generator 已完成。随机样本需要固定种子、样本数、开关对照和重复性；报告观察到的比例及条件，不宣称完整制造良率。

完成这个单像素的声明指标和数字/模拟物理流程后，再定义 4×4 的共享 reference、接口、供电和一致性预算。最终 MPW 仍需要指定 provider 的 pad/ESD、fill/density/antenna、完整芯片与接受检查。
