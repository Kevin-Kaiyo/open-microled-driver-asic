# Driver robustness implementation plan

**Goal:** 用可复现仿真评估供电、电阻角、封装扰动，修正发现的问题，分别说明 PWM 与 NRZ 的实际证据。

**Architecture:** 保留旧版输入与证据，两个独立实验流程调用现有冻结模型和分析工具。NRZ 电路候选通过真实版图重新提取，报告从完成的结果表生成。

**Tech Stack:** pinned GF180MCU / ngspice / Magic / Netgen / KLayout / Python / SVG / HTML。

**Spec:** `docs/research/driver-robustness-20261024/experiment-design.md`；本轮用户已授权继续实验、发现失败后修改与更新报告。

## 任务和完成条件

- [x] NRZ：`scripts/highspeed_nrz_robustness/` 固定负载和 RX，添加独立电阻角、真实动态电源功率、封装案例，保存失败复现及输入哈希。检查稳定电源能量与旧算法一致、角选择独立、动态积分正确。
- [x] PWM：`scripts/pwm_robustness/` 审计39MOS基线，区分片外电阻容差与PDK角；验证供电、启动、保护、封装和候选修复。报告原负载与新测试覆盖。
- [x] 物理：`scripts/highspeed_nrz_robustness_layout/` 对选定候选产生真实GDS、DRC/LVS/PEX与几何映射。旧PEX不允许冒充新器件版图。
- [x] 回归：用实际新PEX重复失败条件及正常对照；目标点和邻近速率采用同一RX规则；对最差点增加数值收敛对照。
- [x] 报告：`docs/research/driver-robustness-20261024/` 分应用解释电路、版图、原因、取舍、数据和未完成项，修正旧文档不完整的可靠性依据。
- [x] 独立审计：检查输入身份、DC、电压端对、接收余量、能量、角覆盖、报告数据与图形。任何未完成检查明确列出。
- [x] 备份：审阅公共源和紧凑证据后提交/推送；原始证据Release归档、SHA回读、恢复说明，保留工作输入与失败证据。

## 审阅重点

1. 电源高于器件筛查线时，不能把增大RIN称为解决静态应力。
2. 电源波形变化后，不能继续按常数电压乘电流计算能量。
3. 封装R/L和PDK互连RC来源、回路及单位必须区分。
4. 修改后速率下降或仍失败的条件必须保留，不能调RX或LED获得通过。
5. PWM采用厚栅氧器件及不同LED模型，不能机械套用NRZ薄栅氧3.63V或BER指标。

研究阶段已形成可核查结果，仍保留A辅助电源接收失败和PWM启动数值一致性未闭合。勾选表示相应实验、审计和报告工作已执行，不表示电路全部指标通过。
