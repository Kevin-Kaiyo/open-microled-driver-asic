# A / B / C 的公平比较合同

审查日期：2026-10-25。审查时 HEAD：`24407f2a350d3aefce5f6125835fc75647ad0c24`。
本次只读现有源与证据、核对公开一手资料，没有运行新 EDA、仿真或修改既有结论。
项目目标仍是实验方法验证，不是商业产品对标。

**结论：目前可以比较证据完成程度，不能据此宣布 B 的性能优于 A 或 C。**
先明确目标和共同约束，再作配对实验。A/B 是输出驱动拓扑，C 则同时引入了多电平 DAC 与 PAM4 调制；三者不是完全正交的选项。电流转向也可以用于多电平 DAC，PAM4 本身并不限定必须采用某一种输出拓扑。

## 1. 本项目实际完成了什么

| 路线 | 当前可核实的工程事实 | 不能据此声称什么 |
|---|---|---|
| A：受限摆幅电压驱动 | 6 MOS + RIN8 核心已有实际 GDS/寄生模型；MOS 的源/体端分别接到 VH/VL 等网络。实际几何合同把 VH、VL 明确列为 `ideal bidirectional rail`，runner 直接建立理想电压源。 | VH/VL 发生器已经实现，或已计入其静态功耗、吸收回流能力、转换损耗及稳态/启动动态。核心面积不能当成完整驱动器面积。 |
| B：电流转向 NRZ | 最终 9 MOS 核心与 12 MOS 参考/禁止/条件 keeper 真实相连，21 MOS + RIN 的 GDS/fullRC 已进入冻结回归。 | 完整电源系统、片内 bandgap、自主 POR、可靠性或光链路已经闭合。外部精密电压基准、5 V/VDD、板级 R/C、DISABLE 时序仍是明确边界。 |
| C：分段电流 DAC / PAM4 | 找到三等权电流单元的原创概念图、概念 floorplan 和教学预算。生成器直接标注无电路仿真；路线 README 明示无 W/L、高速 SPICE，floorplan 非 GDS。 | 已有本项目的四电平晶体管仿真、DAC 电平精度/失配验证、PAM4 接收器、实际布局 PEX 或 PAM4 BER。 |

本次检查了 `analog/`、`rtl/`、`scripts/`、`evidence/` 中的 PAM4/current-DAC 相关路径、文本及现有路线文档，没有找到 C 的可执行晶体管网表/仿真流程。旧构建目录中的论文 PAM4 波形图片属于外部文献，不是本项目实现。特别注意：`highspeed_nrz_robustness/run.py` 的 **`variant='C'` 是仅电容寄生的 PEX 条件，不是路线 C/PAM4**。

可复查位置：

- [路线图生成器](../../scripts/highspeed_routes/circuits.py)：文件头、`route_c()`、`metadata.evidence_level`；[路线说明](../../docs/research/highspeed-driver-routes-20261019/README.md)：证据表与研究顺序；[教学预算](../../scripts/highspeed_routes/tradeoffs.py)：文件头、假设与能耗范围。
- [A 源网表](../../analog/highspeed_nrz_robustness/voltage_hv_candidate.spice)、[实际几何合同](../highspeed-nrz-robustness-layout/visuals-A8-ties/geometry.json)：`A.contract.external_components`；[A/B runner](../../scripts/highspeed_nrz_robustness/run.py)：`build_deck` 中的 `rails`/`rail_lines`。
- [B 最终参考网表](../../analog/nrz_reference_v2/vi_reference_switched_keeper.spice)、[B 供电边界](../../docs/research/nrz-b-reference-power-20261024/architecture.md)、[最终独立复审](../reference-v2-audit/review-final.md)。B 保留四项宽容差电流精度失败、提前释放的过压负控，以及残余供电重启的体结正偏风险；有限通信样本也不是 BER 资格证明。

旧报告“以 B 为研究基线”表达的是当时的研究顺序，不是完成公平比较后的优胜结论。其假设功耗预算也不能替代现在的真实供电、相同光路与接收条件实验。

## 2. 在运行比较前冻结的条件

下表是本项目建议采用的**工程实验合同**，不是已完成的测量结果。

| 项目 | 公平比较条件 |
|---|---|
| 净吞吐与时延 | 使用 `Rnet = Rs × log2(M) × η`，η 包含线路编码、帧、训练及 FEC 开销；同时限定目标错误率、时延和重传策略。相同 η 下，PAM4 的符号率是 NRZ 的一半；例如净 1 Gb/s、无开销时分别为 0.5 GBd 和 1 GBd。不能同符号率比较后称净吞吐相同。[S1] |
| LED 与光路 | 使用同一可追溯 LED、温度/偏置相关 I–V、L–I、结电容与动态模型，相同光耦合、距离、损耗、探测器及环境条件。现有静态 I–V 拟合、假设电容/光学时间常数不等于完整测量模型。先约定平均光功率、外层 OMA、峰值电流与热预算中哪些固定、哪些只给上限；不能默认这些约束能同时独立相等。 |
| 电平、线性和噪声 | 四档等电流间距不保证四档等光功率间距。需要检查 DAC INL/DNL、单元失配、切换毛刺/偏斜，以及 LED L–I 非线性、压缩和动态记忆。三只眼分别考察电平相关噪声、ISI、抖动与最差眼；光电流相关 shot noise、暗电流/TIA 噪声等须明确模型来源。固定外层光幅度时等间距 PAM4 的相邻间距为总幅度的 1/3，但不能脱离功率和噪声定义直接套用一个通用 dB 代价。[S2] |
| 接收器与校准 | 固定光路/PD 后，分别给出可实现的 NRZ 与 PAM4 接收器。PAM4 可以使用三个判决阈值，也可采用 ADC + DSP；不预设必须使用高分辨率 ADC。计入 TIA 的线性范围、阈值参考/DAC、比较器或 ADC、时钟恢复、均衡及 FEC 的功耗和时延。现有二电平 frozen RX 不能直接充当四电平 RX。两方案的训练数据、校准预算和独立验证集要有共同规则。 |
| 电源与能耗范围 | 分别报告驱动核心、完整 TX、完整链路的能耗，分母统一为成功交付的净有效比特。计入 LED、dummy、参考/偏置、VH/VL 或稳压器、DAC/译码/时钟、接收器及上游转换损耗；共享模块按同样方法分摊。全部电源端口分别保存正向取能、回流和净能量，不能把理想电源吸收回流视为实际上游可无损回收。稳态、启动、空闲占空比采用一致统计窗口。 |
| 激励与判断 | NRZ 与 PAM4 使用等量有效数据与可复现映射/种子；覆盖 PAM4 的 12 种非保持有向转换、连续同码、极端跃迁及相应概率。[S2] 记录 Gray 等映射，分别报告 SER/BER，训练与验收分开。有限无噪声波形的零错误不等于统计 BER；统计长度、置信度、噪声及 FEC 门槛必须预先声明。 |
| 物理与器件边界 | 比较同等级的模型：先配对原理级，随后配对实际 GDS/fullRC。使用相同 PVT/容差/失配/封装条件及器件端压、体结、启动/关断判据。分别报核心、支持电路和整片面积；不能用 A 的裸核心与 B 的参考集成宏面积作完整方案排名。 |

其中 symbol rate 减半是 PAM4 的信息映射性质，不是保证带宽、功耗、可靠吞吐都会提高一倍。实际收发器带宽还受脉冲整形、均衡、ISI 和所需眼开度影响。

## 3. A 要与 B 的真实参考实现程度对齐，还缺什么

1. **冻结 VH/VL 的真实电源合同。**从已有核心波形取每条电源的正/反向电流、峰值、平均值与负载阶跃，选择可实现的电压基准/缓冲/稳压方案。明确 source/sink 能力、回流去向、压差和耗散；不能只用两个电压值替代发生器。
2. **建有限动态和启动模型。**包含输出阻抗、环路/PSRR、噪声、去耦 ESR、封装与地回路；检查 VH/VL/VLED/VDD 的上电、关断、残余电压和故障顺序。MOS 端压、体结与 LED 应力独立判定，不用接收正确覆盖器件风险。
3. **完成同等级证据。**若片内实现，需冻结 MOS 网表并完成实际 GDS、DRC/LVS/PEX 与核心联合回归；若板级实现，应明确器件模型/测量依据及片外边界。统一 LED 目标、电平校准和不逐角调参规则，计入支持电路能耗与面积。

同等级不要求 A 照抄 B 的 12 MOS 电路。B 本身也仍需外部电压基准/电源和受控启动；可以先约定双方同样明确的板级边界，不能一方免费理想供电、另一方承担全部实现代价。

## 4. C 最小可比实验与目标依赖的选择

C 进入性能比较前至少需要独立的 W/L/连接网表、四码 DC 与光电平校准、全部有向转换/毛刺/失配实验，以及一个声明开销的 PAM4 接收器。先在共同 LED/光路和净吞吐下做配对原理级实验，再推进实际布局与 fullRC；概念图不能跳过这些阶段。

可以提出下列待验证假设，但目前不据此排序：

- 若主要限制来自通道带宽且光功率/噪声余量充足，PAM4 的较低符号率值得研究；若受噪声或电平非线性限制，增加电平可能得不偿失。
- 若目标优先减少持续偏置/dummy 功耗，A 值得在真实 VH/VL 条件下验证；其电平对 LED 特性和供电误差的敏感性也必须计入。
- 若目标优先稳定电流、减小切换引起的电流变化，B 或多级电流转向 DAC 是候选；代价是参考、压差、持续电流与支持电路。

最终应给出满足同一吞吐/错误率/应力约束的能耗、面积、延迟与稳健性比较，而不是把“当前做得更完整”写成“先验更优”。

## 公开一手来源

- **[S1] Keysight，FlexDCA User Guide，Understanding Signal Parameters**：`Bits and Symbols` 与 `Examples Properties for 10 GBd Signals` 两表给出 NRZ 每符号 1 bit、PAM4 每符号 2 bits。这里据此定义符号率，不采用页面个别段落的单位笔误，也不把示波器说明当作本项目性能验证。访问日期 2026-10-25。[官方页面](https://helpfiles.keysight.com/scopes/FlexDCA-UG/Content/Topics/Quick-Start/FlexDCA-fact-6.htm)
- **[S2] Tektronix，Analyzing 26 to 53 GBd PAM4 Optical and Electrical Signals，Introduction**：列出 PAM4 的 12 种转换及四电平信号测量复杂性。本项目只引用这些调制/测量事实，不移用其 26–53 GBd 性能、标准测试条件或固定 SNR 数值。访问日期 2026-10-25。[官方应用说明](https://www.tek.com/en/documents/application-note/analyzing-26-53-gbd-pam4-optical-and-electrical-signals)
