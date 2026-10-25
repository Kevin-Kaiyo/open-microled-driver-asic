# A / B / C 高速驱动路线：2026-10-25 只读技术复盘

> **2026-10-25 修订注：** 下文“B优先”是本轮用户纠正之前的开发建议，现作为历史保留，不再代表当前路线决策。用户要求先按性能与限制进行公平比较；高速路线尚未确定，不能因B的实现更完整而预选B。当前结论以[主报告](../../docs/research/architecture-decision-review-20261025/report.md)与[公平比较合同](comparison-contract.md)为准。同0.4 Gb/s六点的数据、原始能量独立复算及失败索引见[来源锁定比较表](route-comparison-reviewed.json)。

**当前建议继续以 B 电流转向 + 真实参考作为单通道研究主线；A 保留为低取能对照；C/PAM4 暂不作为已验证性能路线。** 这个选择基于 B 对已测供电/温度条件的接收稳健性及已实现的参考反馈，而非宣称 B 已完成产品资格验证。B 的残余电源重启体结问题仍需优先解决，最新 0.5 Gb/s 也是固定测试点，不是最大速率。

本复盘只读现有 JSON、网表、报告与公开 PDK 文档，不运行 SPICE/EDA，不改历史证据。审查工作树 HEAD 为 `24407f2a350d3aefce5f6125835fc75647ad0c24`。本轮新电路源提交为 `29266d9758894e87bc08a77a3ddf4f86f7b502e1`，相应 Release 为 `reference-v2-20261024`。以下路径以仓库根目录为基准；“通过”均受各行明示的仿真条件与判据限制。

## 1. 三条路线到底改变什么

| 路线 | 数据如何改变 LED | 当前实际实现 | 主要收益与代价 |
|---|---|---|---|
| A：受限摆幅电压驱动 NRZ | 两级前驱动控制推挽输出，在 VH/VL 之间切换 LED 阴极电压；LED 非线性 I–V 将电压变为电流 | 选定真实 `hv-A8-r3/A`：6 MOS + 1 个 PDK RIN；VH=1.611025 V、VL=1.172154 V 仍由理想可供/吸电源提供 | 核心较小、固定辅助电源下取能较低；电流受 VLED−OUT 差值、LED I–V、MOS 导通压降影响，辅助电源生成与吸收回灌尚未实现 |
| B：连续偏置电流转向 NRZ | 基础支路约 25 µA 常开，约 75 µA 尾电流在 LED 与 dummy 间转向；目标 LED 电流约 25/100 µA | 旧 9 MOS + RIN 核心；最新加 10 MOS VI 反馈参考、2 MOS 受控关断/keeper，实际联通为 21 MOS + RIN | 电流对电源差值较不敏感，仍受 compliance、镜像误差和参考误差限制；尾电流/dummy 与参考带来持续功耗 |
| C：分段电流 DAC / PAM4 | 多个单位电流单元相加，形成四个电平，每符号可映射 2 个原始比特 | 2026-10-19 原创概念电路：3 个等权转向单元与等效 IREF；无冻结 W/L、PAM4 SPICE、对应 GDS/PEX 或三眼接收实验 | 可用较低符号率承载同一毛比特率；相邻电平距离缩小，新增译码、时钟、匹配、动态毛刺、光学线性与多阈值接收要求 |

实际 A 源：[voltage_hv_selected_geometry.spice](../../analog/highspeed_nrz_robustness/voltage_hv_selected_geometry.spice)。实际 B 总网表：[selected_integrated_geometry.spice](../../analog/nrz_reference_v2/selected_integrated_geometry.spice)。C 的原概念与边界：[highspeed-driver-routes-20261019/README.md](../../docs/research/highspeed-driver-routes-20261019/README.md)、[route-c.svg](../../docs/research/highspeed-driver-routes-20261019/figures/route-c.svg)，生成连接位于 `scripts/highspeed_routes/circuits.py:234` 起。

最新 B 已取消未通过启动/长时振铃验收的 9 MOS LDO。实际结构为独立 RAW 5 V 供给参考与 50 kΩ dummy；逻辑 VDD 仍独立。外部 2.5 V 精密电压基准经 200 kΩ/50 kΩ 分压为约 0.5 V，10 MOS 反馈电路调节 RSET=20 kΩ 上的电压，形成约 25 µA 参考，再经镜像设定原核心电流。RSET、分压、偏置电阻、150 pF IN2 补偿、100 nF 输入去耦及其 ESR、GPIO 仍是明确的片外接口/工程模型。片内 bandgap、实际外部参考 IC 内部功耗和自主 POR/ready 未完成。[最新架构说明](../../docs/research/nrz-b-reference-power-20261024/architecture.md)

## 2. MOS 材料、工艺与“耐压”的准确含义

三路线的研究载体是**硅 CMOS**；A/B 实际网表使用 GF180MCU D，而不是 GaN 功率管、SiGe HBT 或 InGaN MOS。InGaN 是当前外部黄色 MicroLED 的材料，不应与驱动 MOS 混称。GF180 公开工艺为 0.18 µm 的 3.3 V / 5–6 V 平台；工艺名中的 0.18 µm 不代表这里每只模拟 MOS 的实际沟道都是 0.18 µm。[GF180 官方入口](https://gf180mcu-pdk.readthedocs.io/en/latest/)

| 版本 | 实际器件 | 长度与研究端压判据 |
|---|---|---|
| 10/19–10/23 历史 A/B | 03v3 NMOS/PMOS | 最小实际 L=0.28 µm；历史统一 3.63 V 六端对筛查 |
| 10/24 选定 A | 6 只全部 06v0 | 6 V NMOS 最小 L=0.70 µm，PMOS 最小 L=0.55 µm；逐器件 6.0 V 六端对筛查 |
| 10/24 robustness B | 四只反相器管和两只转向管为 06v0；三只低电压偏置/基础/尾电流管仍为 03v3 | 按实际型号分别用 6.0/3.63 V；不能把全电路最大电压直接从 6 V 相减 |
| 最新 reference-v2 B | 原核心不变，12 只新增参考/保护 MOS 均 06v0，总计 18 只 06v0 + 3 只 03v3 | 参考差分/镜像器件采用更长沟道，部分 W/L=100/10 µm；实际型号与 D/G/S/B 映射在物理 contract 中逐只保留 |

公开 [DRM 7.7 Poly2](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_07_08.html) 给出上述最小长度；5 V 器件的 0.60/0.50 µm 规则不能当作 6 V 最小长度。真实 06v0 更换包含 PCell、Dualgate 层、尺寸、DRC/LVS 和重新提取，不是把网表型号或筛查门限改名。

公开 [DRM 14.1.4.2](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html) 的栅氧规则针对 gate-to-any-node **绝对 DC 电压**：薄氧为 3.63 V，5 V/6 V 厚氧分别为 6.5 V/6 V；周期超额还依赖 duty、TDDB 等条件。项目将 03v3=3.63 V、06v0=6.0 V 用于全部六组端对的瞬态筛查，这是更便于暴露风险的研究判据，**不是由该条规则推导出的完整 VDS、体结、SOA、HCI、TDDB、ESD 或寿命合格证**。不采用“6 V 器件所以统一允许 6.6 V”的推断。

旧 FF/−40°C/3.6 V 的 A/B 最大端差 3.620623/3.618943 V，仅余 9.377/11.057 mV。+50 mV 稳态逻辑轨已使旧核心超限；仅在供电与回地各加 1 Ω/2 nH，旧 A 即达 3.721199 V，最大 gate-pair 为 3.687489 V，同时仍然 0/511。新厚氧版修复的是相对实际型号限值的余量，不代表消除了过冲；也不能把这个项目筛查失败表述为已经观测到物理击穿。[robustness 报告第 1–3 节](../../docs/research/driver-robustness-20261024/report.md)

## 3. 共同 LED / RX 合同，以及“余量”和时间的定义

后述 A/B 比较均保留 Lin 等 2026 年公开 **20 µm 方形黄色 InGaN LED 的静态 I–V** 拟合，原文件定位为 Zenodo `10.5281/zenodo.20034288`、`I-V.xlsx` Sheet1 A3:B102。测量温度未注明。CLED=200 fF、LED 串联 R/L=1 Ω/0.5 nH、光学一阶 τ=200 ps、RX 一阶带宽 1 GHz 都是声明模型；不是该 LED 的动态或温度实测证明。温度扫描作用于有对应模型的 MOS/电阻，不把静态 LED 曲线扩写成热光模型。[LED source-lock](../../analog/models/measured-led/source-lock.json)

接收输入取 **LED 导电电流**，排除结电容位移电流，再串联两个线性一阶代理，增益按等效电流定义，没有 PD/TIA 噪声。发送 32 bit 预热、254 bit PRBS7 训练、511 bit PRBS9 验证及 32 bit 尾部，DATA 边沿 20 ps；阈值固定 62.5 µA，归一化跨度固定 75 µA。每个条件仅用训练段选择采样延迟，验证段不重新调阈值/幅度/采样点。

- **接收阈值余量**：`min(min(I1_sample)−62.5 µA, 62.5 µA−max(I0_sample)) / 75 µA`，不是眼开口，也不是噪声 SNR。门槛 ≥0.1 即距离阈值至少 7.5 µA。
- **时序余量**：围绕已冻结采样点，在 ±0.5 UI 诊断扫描内，包含该点的连续零错误区间左右较小值。门槛 ≥0.1 UI；它不是实测随机抖动容限或 BER bathtub。
- **端压余量**：每只 MOS 用自己的型号限值减该器件六端对最大绝对值，再取所有器件最小值。旧 metadata 中 `above_3p63V_screen` 不能当作新混合型号电路的最终判据。

算法原件为 `build/nrz-reference-v2/selected-final-r2/inputs/legacy/metrics.py` 的 `receiver_proxy`、`train_sampler`、`evaluate_validation`；当前公共对应实现见 [scripts/highspeed_nrz/metrics.py](../../scripts/highspeed_nrz/metrics.py)。联合接收与器件通过要求 0/511、阈值余量≥0.1、时序余量≥0.1 UI、逐器件端压通过。

**0/511 不能推出 BER=0 或 BER<某产品指标。** 这是固定有限码型、确定性且无噪声的模拟观察；没有统计独立的长时间错误试验，没有实测光功率/耦合/接收器噪声和随机抖动。换一个 PRBS 种子、长连码、ISI 历史、采样相位或噪声实现都可能改变结果。即使额外假设独立 Bernoulli 试验，511 个零错误样本也远不足以证明低 BER，而本实验本身并不满足那套统计前提。训练正确、DRC/LVS 通过和版图存在，都不会补上这层证据。

## 4. A 的 2 / 1 / 0.4 Gb/s 是不同版本和条件

下表是历史事实，不能挑不同版本最好的速率与能耗拼成一个规格。

| 日期/版本 | A 的观察 | 可支持的结论 |
|---|---|---|
| 10/19 原理图、03v3 | TT 2 Gb/s：0/511，阈值余量 0.139761、时序 0.320313 UI；SS 2 Gb/s：64/511 | 早期名义原理图曾通过 2 Gb/s 接收筛查；不是 PVT 完整通过 |
| 10/20 初始 RC、03v3 | TT 2 Gb/s：0/511，0.115567、0.289063 UI；SS 2 Gb/s：64/511；FF 虽 0/511，但最大端差 3.725269 V | 初始实际 RC 的名义 2 Gb/s 通过也存在；快冷端压与慢热接收并未闭合 |
| 10/23 `final-r4`，03v3+RIN48 与布局修订 | TT/SS/FF 的 1 Gb/s 均通过联合筛查；2 Gb/s 分别 75/100/32 错误 | 七档离散测试中，这三组指定条件共同通过的最高点为 1 Gb/s；没有修好 2 Gb/s，且快冷只剩约 9 mV 电压余量 |
| 10/24 `hv-A8-r3`，真实 06v0+RIN8 | 固定辅助电源时 TT/SS2.95 V/FF3.65 V 的 0.4 Gb/s 离散点通过；SS2.95 V 的 0.5 Gb/s 0/511 但阈值余量 0.097873，仍失败；SS3.0 V 的 1 Gb/s 为 75/511 | 当前 A 可引用的是声明条件下的 0.4 Gb/s 点，不能继续沿用旧版“三角点 1 Gb/s” |
| 同一新 A 的快冷特定点 | FF3.65 V/1 Gb/s 为 0/511、0.417053、0.28125 UI，通过；同 FF3.6 V 加供电/回地各 1 Ω/2 nH 的 1 Gb/s 也通过 | 只证明这两个快冷点，不能外推到慢热 1 Gb/s |

来源：`evidence/highspeed-nrz/summary.json` 的 `A-nominal/slow_hot-2G`；`evidence/highspeed-nrz-pex/summary.json` 的 `RC-A-*-2G`；`evidence/highspeed-nrz-pvt/summary.json` 的 `variant=AFTER`；`evidence/highspeed-nrz-robustness/summary-verified.json` 的 `selected.rows`。

新 A 的 SS/0.25 Gb/s 为 0/511，却仅有 0.078125 UI 时序余量；0.4 Gb/s 为 0.125 UI。冻结训练算法优化最坏垂直判决距离，没有联合最大化水平余量；这两个点的右侧零错窗口约同为 312.5 ps，除以不同 UI 后判定不同。因此 **0.25/0.4/0.5 Gb/s 不呈单调通过关系，不能拟合“带宽截止”或连续最大速率**。[sampler-diagnostic.json](../highspeed-nrz-robustness/sampler-diagnostic.json)

更严重的是 A 的辅助电源包络：FF3.65 V、0.4 Gb/s 下，VLED 单独 +50 mV 或 VH/VL 同时 −50 mV，均 0/511 但仅 0.09375 UI；SS2.95 V、VLED4.95 V、VH/VL 同时 +50 mV 时为 256/511。后一条件 DC 的 I1 只有 57.196 µA，已低于 62.5 µA 阈值，I0=16.541 µA。**这是电流幅度条件失败，单纯降速无效。** 同类旧 B 联合条件 I0/I1=23.148/89.960 µA，0.5 Gb/s 仍通过，阈值余量 0.164747、时序 0.242188 UI。[joint_supply_boundary](../highspeed-nrz-robustness/summary-verified.json)

## 5. 真正可比较的能量：先同速率，再同实现边界

### 5.1 旧 robustness A/B：同为 0.4 Gb/s

以下为 `summary-verified.json → same_rate_energy` 的直接表格摘录；同 LED/RX、同 MOS 角/温度/逻辑电源，固定各自辅助电源。能量为全部供电与 DATA **正向取能**，单位 pJ/gross bit。

| 条件 | A 能量 | B 能量 | A/B 阈值余量 | A/B 时序余量 UI | A/B 时间余量 ps |
|---|---:|---:|---|---|---|
| TT / 27°C / 3.3 V | 1.308233 | 1.540521 | 0.470248 / 0.325777 | 0.148438 / 0.281250 | 371.094 / 703.125 |
| SS / 125°C / 2.95 V | 0.986320 | 1.354735 | 0.140157 / 0.289982 | 0.125000 / 0.281250 | 312.500 / 703.125 |
| FF / −40°C / 3.65 V | 1.547282 | 1.796334 | 0.494982 / 0.310514 | 0.125000 / 0.273438 | 312.500 / 683.594 |

这六点均联合通过。A 在这些点取能低，B 水平余量大；A 的高垂直余量不能覆盖辅助电源失效。两者都尚未计入真实电源生成器：A 的 VH/VL 为理想可吸电源，旧 B 的 3.3 V VDUMMY 和 RREF 偏置也理想。实际平均 LED 电流并不完全相同，例如 TT A/B 约 61.20/65.00 µA，所以它也不是“相同实测光输出”的最终能效排名。

### 5.2 B 参考修改前后：同为 0.5 Gb/s

旧 B 是 `hv-r2/B` + RREF=88.386106 kΩ/VDUMMY=3.3 V/RDUMMY=28 kΩ；新 B 是真实联通 21 MOS + RAW5 V/RSET20 kΩ/RDUMMY50 kΩ/外部精密电压接口。两版核心负载、数据、RX 与各行 PVT 条件对应，实际参考/供电结构不同，正是这组对照要暴露的代价。

| 条件 | 旧 B 正向能量 | 新 B 正向能量 | 新−旧 pJ/bit | 旧 B I0/I1 µA | 新 B I0/I1 µA |
|---|---:|---:|---:|---|---|
| TT / 27°C / 3.3 V | 1.279092 | 2.688271 | 1.409179 | 24.986 / 99.707 | 25.154 / 100.395 |
| SS / 125°C / 2.95 V | 1.110793 | 2.519358 | 1.408565 | 23.656 / 91.945 | 25.065 / 97.448 |
| FF / −40°C / 3.65 V | 1.516009 | 2.917437 | 1.401427 | 26.343 / 107.714 | 25.261 / 103.372 |

新 B 高电流误差三点由旧约 −8.06%～+7.71% 缩至 −2.55%～+3.37%。这是真实参考带来的收益，也显示旧“接收通过”不等于高低电流准确度满足 ±5%。当前没有新 B 的 0.4 Gb/s 数据，不能拿本表新 B 0.5 Gb/s 与上表 A 0.4 Gb/s 排序为公平能效比较。

能量统一定义为 `P_k(t)=−V_k(t)I_source,k(t)`，逐源积分正向、返还与净额，统计窗口为验证段对应的 **511 个输入 UI**。0.5 Gb/s 对应 1.022 µs；训练/启动 100 µs 不被偷偷混入正常每位能量。电源封装有阻抗时从源侧采样，包含声明的 R/L 损耗；DATA 的实际端口功率也计入。分母是发送 gross bits，不是解码后 net payload，也不是成功收到的比特数。失败点的低取能不能作为可用节能点。

边界仍不含外部精密参考 IC 内部 Iq、上游转换效率、串行器/时钟/CDR、编码/FEC、真实 PD/TIA/RX、光耦合与墙插效率。返还给理想源的能量不保证能在实际电源中回收。`P≈CΔV²f` 可解释趋势，不能代替这些多电源、非线性、持续偏置电路的逐端口积分。

## 6. 最新 B：0.5 Gb/s 的证据、失败与时间尺度

最终 PEX：`build/reference-v2-layout/nrz-switched-keeper-joint-r1/J/full-rc/nrz_reference_integrated_rc.spice`，SHA-256 `925b0e98ede116b7d3dc0c0f326aa1704fd08b84dd8cabe39cf03ae4ac4f3d6a`。21 MOS + 1 PDK RIN，638 个寄生 R、322 个 C、20 个网络。compact 原件在 [evidence/reference-v2-layout/nrz-switched-keeper-joint-r1](../reference-v2-layout/nrz-switched-keeper-joint-r1)。实际 GDS 两套 DRC、LVS/readback/RC-collapse、几何及真实开短路负控通过；它仍是实验宏，约 348.99×340.06 µm，不含完整 pad/ESD/芯片供电签核。

### 6.1 十个固定速率通信点

原始数值入口：[selected-final-r2-nrz.json](../nrz-reference-v2/selected-final-r2-nrz.json)，逐行给出原 `result_json/analysis_json`。所有行均 0/511 且逐型号端压通过。

| 0.5 Gb/s 条件 | 阈值余量 | 时序余量 UI | 时间余量 ps | 正向 pJ/bit | 最小器件端压余量 V |
|---|---:|---:|---:|---:|---:|
| TT 名义 | 0.243533 | 0.289063 | 578.125 | 2.688271 | 0.872820 |
| SS 慢热 | 0.233244 | 0.273438 | 546.875 | 2.519358 | 0.913690 |
| FF 快冷 | 0.247627 | 0.320313 | 640.625 | 2.917437 | 0.831412 |
| SS 精密 RSET 联合 | 0.229330 | 0.265625 | 531.250 | 2.382923 | 1.161575 |
| FF 精密 RSET 联合 | 0.246229 | 0.312500 | 625.000 | 3.064381 | 0.584068 |
| FF RAW +250 mV pulse | 0.228608 | 0.304688 | 609.375 | 786.670185 | 0.616155 |
| FF VLED +50 mV pulse | 0.247685 | 0.312500 | 625.000 | 2.919258 | 0.831285 |
| FF VDD +50 mV pulse | 0.247218 | 0.320313 | 640.625 | 2.922166 | 0.829000 |
| FF 供电/回地及 LED 封装组合 | 0.248129 | 0.312500 | 625.000 | 2.916568 | 0.834227 |
| FF 更紧数值设置 | 0.247541 | 0.320313 | 640.625 | 2.917458 | 0.830864 |

共同 TT/SS/FF 指 MOS/PDK 电阻角为 typical/ss/ff，温度 27/125/−40°C，逻辑 VDD=3.3/2.95/3.65 V；普通行 VLED=RAW=5 V。联合 SS/FF 使用 RAW4.75/5.25 V、RSET±0.1%及+25 ppm/°C、RDUMMY±1%及+100 ppm/°C、外部基准±0.05%及声明的−30 ppm/°C线性敏感度。这个基准 TC 扫描是 generic stress，不是某商业器件 box-method TC 的保证。供电封装行在 VDD/VSS 各用 1 Ω/2 nH，并把 LED 路径改为 4 Ω/2 nH；RAW 原有 0.25 Ω/0.5 nH 与 100 nF 去耦仍保留。它不是完整封装场提取。

最小阈值余量 0.228608 对应 17.146 µA；最小时序余量 0.265625 UI 对应 531.25 ps。两项最小值来自不同案例，不合成为一个未运行的角点。

**RAW pulse 行不能作正常通信能耗。** 5→5.25 V、2 ns 边沿、每 254 ns 重复、高态 64 ns，反复对 100 nF 去耦充放电：正向 786.67、返还 741.95、净额 44.72 pJ/bit。它说明供电扰动能量窗口的实际代价，不意味着正常 0.5 Gb/s 每位需要 786 pJ，也不保证外部电源回收全部返回能量。[逐源能量表](../nrz-reference-v2/final-tables/nrz-source-energy.csv)

### 6.2 DC、参考稳定性和启动没有被通信通过覆盖

- **112 个 DC 点**全部求解、器件绝对端压筛查全部通过；其中 **4 点电流精度失败**。FF 的 RSET −1%/+100 ppm/°C 为 +5.0747%；FF 宽容差联合为 +5.2465%；RSET −5% 负控的 bit0/bit1 为 +5.8408%/+5.5942%。固定 20 kΩ 未逐 PVT 校准，选定 ±0.1%/±25 ppm/°C 研究规格的联合点通过。不是统计良率或量产保证。[DC 数据](../nrz-reference-v2/selected-final-r2-dc.json)
- **慢反馈与快数据分开**：最终实际 PEX 的局部双注入估计 TT/SS/FF 约 450.4/283.5/668.7 kHz，局部相位裕量约 72.96°/78.34°/66.25°，结合 100 µs 长时波形支持选定补偿；不称严格 Tian 全多环路签核。参考不需跟随每 2 ns 一位的数据，转向开关承担快切换。[参考结果](../../docs/research/nrz-b-reference-power-20261024/results.md)
- **正常启动的合同**：1 µs 外部电源/参考斜坡，DISABLE 保持到 20 µs；保持导电电流约 1.3 µA，预算 ≤2 µA，非完全熄灭。TT/SS/FF 释放后约 89.06/93.59/88.75 ns 进入并保持 100 µA±5%；完整峰值约 100.670/97.657/103.710 µA，低于 125 µA 合同。20 µs 外部等待才是系统启动延迟的一部分，不能只宣传“约 90 ns 启动”。
- **提前释放负控失败**：参考在 30 µs 才开始，却仍 20 µs 释放，03v3 最大端差 4.86194 V，释放至稳定约 13.5297 µs；正确迟到控制改为 50 µs 释放。这不是同一时序的两个重复实验。11 个 startup/restart 点中 10 个满足原功能与六对绝对端压条件，不能据此称 10 个均已可靠性闭合。[启动数据](../nrz-reference-v2/selected-final-r2-startup.json)
- **残余电源重启未闭合**：LED 与基准仍在、RAW 掉电时，IN2 未主动复位。原 XR_IPD2（PEX x7）的扩散区 0.749006 V、nwell 0.002357 V，峰值正向结压 0.746649 V，约 21.173660 µs 出现；超过 0.7 V 的插值持续约 1.400 µs。0.7 V 仅是描述阈值，不是新许可。未保存结电流，不能量化注入电荷或证明无闩锁。此点功能/绝对端压通过，不等于重启安全。[restart-body-review.json](../nrz-reference-v2/restart-body-review.json)

通信从已建立工作点开始，启动用固定 DATA；尚未在同一实际波形中闭合“上电→ready→第一包数据→接收重新训练”。最终正式矩阵是 112 DC + 10 NRZ + 11 startup + 5 slow = 138 条；7 个局部 AC、6 个功耗观测 DC 与跨目录复现另列，不能混加成独立统计样本。

## 7. 静态参考为何昂贵，阵列共享能解决多少

六个同工作点电流观测 DC 与原 LED 电流差为 0 A。TT 的 RAW5 V 支路分配为：OTA 控制约 451.26 µW、检测参考约 124.97 µW、输出参考约 124.53 µW，合计约 **700.76 µW**；源侧闭合残差约 0.128 µW。仅这三项在 0.5 Gb/s 已约 **1.4015 pJ/bit**。DATA=0 时 dummy 另取约 377.10 µW，DATA=1 时接近零；LED 与其他供电当然还要算。[power-dc-r2.json](../nrz-reference-v2/power-dc-r2.json)

因此降低位率不会按比例降低这些静态支路功耗，反而提高每位分摊。上面新旧 B 增量约 1.40–1.41 pJ/bit 与此代价同量级；这不是证明所有差额严格只由 OTA 构成，因为 RDUMMY/供电/实际 LED 电流也改变了。

共享参考是合理下一步，但**不能把现有整块 700.76 µW 直接除以 lane 数**。若共享 OTA 与检测支路，而各 lane 保留输出镜像/缓冲，则共享项约 451.26+124.97 µW，输出参考约 124.53 µW/路仍可能随 lane 数增长；具体能否保留这些数值取决于全新负载和稳定性。把一个 25 µA 输出直接并到 N 个 BIAS 二极管负载会改变分流，不能自动得到 N 路同样的 100 µA LED 电流。

阵列估算应至少写为 `E/gross bit=(P_shared + N·P_lane + P_distribution + P_clock/control)/(N·R_lane)`，再明确活动率与有效载荷。参考扇出电容、局部镜像失配、IR drop、基准噪声相关性、启动充电量、单 lane 故障拖拽共享 BIAS、独立关断、温度梯度都需纳入。现有 150 pF IN2 和板侧 100 nF 不是可无成本复制到每像素的片内电容；它们还需要 pad/走线/ESD 和共享/局部去耦选择。

并行 NRZ 可以在不提高每路 0.5 Gb/s 的前提下增加毛吞吐量，但不能从单路结果推出阵列可用速率。例如 16×0.5=8 Gb/s 只是算术；同步切换引起的 VDD/VSS bounce、共享封装电感、光学串扰、串行器/时钟 skew、数据分配和接收阵列均未验证。已有 package 点是单 lane 集总敏感度，不是 N lane 的独立保证。最新大参考宏也不能与 A 的裸 6 MOS 核心面积直接比较为产品面积优劣。

## 8. C/PAM4 的合理研究位置

若四电平可靠区分，理想毛比特率为 2×symbol rate；因此 0.5 Gbaud 可以在编码前表示 1 Gb/s。但**B 的 0.5 Gb/s NRZ 通过不证明 C 在 0.5 Gbaud PAM4 通过**。C 至少需重新定义 3 个阈值、符号/比特映射和三只眼的判据，不能沿用当前单阈值 RX 后简单把数字翻倍。

原 C 图电平为 0/Iu/2Iu/3Iu，没有 B 的 25 µA 非零基线。若未来改为示例 25/50/75/100 µA，在同 75 µA 总跨度内，相邻电平只隔 25 µA，理想阈值距离 12.5 µA，而二电平 25/100 µA 理想中点距离是 37.5 µA；这是解析预算，非本项目 PAM4 仿真结果。实际 LED 的 L–I 非线性、带宽随偏置变化和热效应可能进一步改变等光间隔，不能由静态 I–V 推出。

进入 C 的门槛应是单 lane 已取得可信 L–I/频响/噪声与抖动数据，B 的参考/掉电风险闭合，并有系统收益目标。随后再验证单位电流匹配、切换毛刺、码间 skew、compliance、三眼/电平失真、Gray 映射与 BER/FEC 预算，比较同净吞吐量、同实测接收目标下的总能耗。PAM4、FFE 和并行是不同的系统选择，当前证据还不能宣布其中任意一个一定更省电。

## 9. 当前路线选择与最有决定性的三组后续实验

| 优先级 | 要改变的判断 | 建议实验与通过证据；本复盘未执行 |
|---|---|---|
| 1：先补 B 的系统安全边界 | B 能否从受控实验点成为可重复启动/掉电的单 lane 基线 | 实现真实参考 ready、IN2/相关补偿节点复位或掉电隔离；保存结电流与注入电荷，扫 RAW/VLED/VSET/VDD 的先后、慢坡、brownout、残压快速重启；实际新布局/PEX 后联合验证启动→第一包通信，保留当前早释与体结负控 |
| 2：做公平、能改变 A/B 选择的电源实验 | A 的低取能是否在实际辅助电源代价下仍成立；B 能否降低静态代价 | A 实现 VH/VL 的真实调节/跟踪与吸收回灌，先修复 SS 联合供电下 I1<阈值；B 对 OTA 偏置或共享参考做单变量候选。两者用同 LED/RX/电流准确度目标、相同 0.4/0.5 Gb/s 点、同扰动/输出阻抗和数值控制比较，统计所有生成器输入能量；不逐角点重调参数、不改 RX 掩盖失败 |
| 3：建立从模型到链路/阵列的证据 | 是增加并行 NRZ 还是值得进入 PAM4 | 先测所选 LED 的 I–V/L–I/频响/温度与封装网络，接真实 PD/TIA/RX 噪声/抖动并做长序列错误实验；再从 2/4 lane 同时切换、共享参考和单路故障隔离开始。只有在同净吞吐量系统预算中显示收益时，才推进 C 的晶体管/PAM4 三眼及真实布局验证 |

选择 B 是目前证据支持的研发顺序，不是“B 已最省电或可流片”的产品结论。A 的名义高速与较低核心取能值得保留，但需要真实辅助电源闭合后才有公平决策基础；C 目前没有足以与 A/B 数值排名的性能证据。

## 10. 主要原始证据索引

| 证据 | 精确入口 | 支持范围 / 不支持范围 |
|---|---|---|
| 初始 A 2 Gb/s | `evidence/highspeed-nrz/summary.json`，`A-nominal-2G-typical-27C-3.3V-C200-L0.5-e20-s40` | 原理图名义接收；非慢热/全 PVT |
| 初始实际 RC | `evidence/highspeed-nrz-pex/summary.json`，`variant=RC` | 真实核心提取的指定条件；其 `variant=C` 是 C-only 寄生控制，**不是 C/PAM4 架构** |
| 03v3 修订后 1 Gb/s | `evidence/highspeed-nrz-pvt/summary.json`，`variant=AFTER` | 三条件离散 1 Gb/s 与保留 2 Gb/s 失败；非扰动包络 |
| 厚氧 A/B robustness | `evidence/highspeed-nrz-robustness/summary-verified.json`：`same_rate_energy`、`joint_supply_boundary`、`selected.rows` | 同 0.4 Gb/s 对照和供电失败；旧 B 尚无本轮参考容差/功耗 |
| 新 B 完整矩阵 | `evidence/nrz-reference-v2/selected-final-r2-summary-verified.json`，SHA `613a673fd3aa5b648c6e46bc9840469df22bfe1a8c0fef2f7605d789603f6951` | 138 条有界实验及分层失败；不代表全角穷举、统计良率或 BER |
| 新 B 端口功耗、重启结偏置 | `evidence/nrz-reference-v2/power-dc-r2.json`、`restart-body-review.json` | 同工作点新增观测和原波形复核；未保存结电流，不推断锁存/寿命 |
| 新 B 真实物理 | `evidence/reference-v2-layout/nrz-switched-keeper-summary.json` 与对应 compact 目录 | 实际 GDS/DRC/LVS/声明 PEX；不是完整芯片、封装、EM/IR、ESD 或硅后测量 |
| PDK 与模型身份 | `layout/pdk-lock.json`、每批 `manifest.json/source_hashes` | 固定依赖与执行输入；模型 subset 不替代完整物理 PDK |
| 三路线概念 | `docs/research/highspeed-driver-routes-20261019/README.md`、`scripts/highspeed_routes/circuits.py` | C 连接/解析概念，不是高速 SPICE 或对应 GDS |

方法采用研究证据提取标准：保留同条件表、失败与未知，区分公开规则、模型假设、确定性仿真、实际物理证据和本复盘的工程判断。未新增实验数据。
