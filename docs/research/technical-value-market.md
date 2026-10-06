# 实验方法与研究价值：用单像素建立可复现的验证链

定位更新：2026-10-06。工程结果按各自冻结版本读取；本页4×4预算沿用v0.3输入，当前单像素验证进展见[研究报告](research-report.md)。本项目以开放教学和实验性研发方法验证为目的，公开问题、假设、输入、误差与失败对照，便于独立复算和继续研究。

**优先验证 MicroLED 器件建模、驱动设计与物理实现之间的方法链。** 以一个灰阶命令为起点，检查PWM、电流镜、器件数据、金属连接和误差，再确定哪些结论仍依赖测量。单像素规模便于把问题逐层解释清楚；只有当新增路数能够回答明确的共享偏置、相互耦合或同步控制问题时，才扩展阵列。

## 1. 入门：方法、证据与研究价值分别回答什么

**方法**回答“怎样提出和检验问题”：例如固定供电与LED条件，检查约100 µA电流怎样受到PWM或参考源影响。**证据**回答“哪些数据支撑结论”：例如原始波形、测量条件、布局连接和独立错误对照。**研究价值**回答“是否增加了可复现的理解”：例如能否区分低灰阶误差来自LED、参考源、寄生还是时序。

一个可以运行的电路是起点。教学还需让读者理解前提、独立运行和发现错误；器件研究还需可追溯的真实数据、测量不确定度与模型适用边界；实物验证还需供电、封装、探针与温度条件。这些阶段需要各自的证据。

冻结v0.3的约100 µA电流、1 µs最短PWM slot、共同routed macro top与有条件的DRC/LVS构成可检查的设计记录；v0.4进一步加入联合PEX和边界研究，见[联合PEX](joint-pex.md)与[电气验证](robustness.md)。真实LED的I–V来自公开测量数据，仍缺少完整C–V、I–V(T)、反向区和光学模型。每个结论应保持其来源条件与验证层级。

## 2. 工艺为什么适合当前学习目标

GF180MCU官方材料把它称为 **0.18 µm、3.3 V/6 V MCU process**；公开文档还列出其他器件族。较高电压和公开模型有利于从晶体管、电流镜到LED headroom的教学。当前采用的长沟道匹配器件和高压数字单元，便于观察面积、驱动能力和精度之间的取舍。器件能力必须按实际使用的model和rule deck读取。[GF180MCU官方README](https://github.com/google/gf180mcu-pdk/blob/main/README.rst)、[PDK官方文档](https://gf180mcu-pdk.readthedocs.io/en/latest/)。

工艺名称本身不保证某种电路一定可行。研究中应记录器件类型、W/L、电压、body连接、模型版本与规则版本，再检查目标电流、headroom、寄生和面积。缩小器件会改变失配、输出电阻、寄生和接触结构，需要新的误差预算与真实版图证据。

维护与制造资格也要分开。2026-10-05浏览时，Google的GF180MCU原仓库标记于2026-09-23 archived，README仍写experimental preview / alpha、test-chip使用不作保证。这不自动否定锁定文件的模拟结果，但实物阶段必须确认实际维护分支、完整PDK、规则与候选制造服务的匹配。公开模型、开放许可证与生产接受是不同条件。[官方仓库状态与README](https://github.com/google/gf180mcu-pdk/blob/main/README.rst)。

## 3. 三类实验问题及其证据缺口

研究范围按“需要回答什么问题”定义，具体实验条件应在运行前写清。

| 实验方向 | 要回答的问题 | 当前基础 | 下一项证据 | 当前安排 |
|---|---|---|---|---|
| 单像素模型与电气行为 | 电流、headroom和短脉冲误差来自哪里 | 一像素RTL、晶体管与物理连接可检查 | 实际reference、LED动态/温度和bench数据 | 优先补齐 |
| 1→16路的缩放假设 | 共享bias与同时切换怎样改变功耗、精度与时序 | 已有可复算面积/功耗/数据预算 | 单像素闭环后独立定义阵列、packet与同步实验 | 先保留预算，再按问题实现 |
| 独立教学复现 | 读者能否从输入开始运行并解释一个失败 | 公开网表、脚本、报告与负向对照 | 外部运行记录、环境差异、错误解释和文档反馈 | 与工程修正同步推进 |

小阵列研究不要求驱动电路和发光mesa具有相同pitch。可以先使用测试芯片或板级载体，把外接LED的电流与时间误差测清楚。如果将来研究几微米级pixel site，则需重新定义pixel architecture、存储位置、器件选择与互连方式；当前macro的复制预算不能回答这些问题。

## 4. 比较实验结果：先对齐条件与误差定义

有意义的比较来自相同问题下的受控变化。对照实验先固定输入和计算窗口，再更换一个模型、电路参数或测量条件，并说明其余量是否保持一致。

| 对照维度 | 应固定或记录的内容 | 能回答的问题 | 仍需注意的边界 |
|---|---|---|---|
| 理想reference与非理想reference | LED身份、目标电流、供电和启动顺序 | 参考源顺应电压及输出电阻是否改变首脉冲或稳态电流 | 行为源仍需实际电路与测量验证 |
| Schematic与局部PEX | 相同MOS模型、刺激、测量窗口和端口 | 选定物理连接的R/C怎样改变电荷和时序 | 局部提取不能覆盖省略的PG与邻近活动 |
| 模型预测与测量 | 器件批次、温度、供电、脉冲宽度、仪器与探针 | 模型在哪些条件下有系统性残差 | 仪器误差、探针负载和数据拟合范围需分开记录 |
| 基线与故意错误 | 预先声明的检查规则、输入变更与预期失败项 | 检查能否发现错误连接、参数或计算 | 通过有限错误对照不等于覆盖所有失效模式 |

本项目主验证中的±5%是单支路电流相对100 µA目标的检查，±2%是已定义窗口中的最低码电荷检查。改变分母、时间窗口或温度范围后，应重新注明指标；不能把单次模拟样本扩展成对所有器件与条件的保证。

科学文献提供实验方法与边界的参考。Hsiao等在Scientific Reports于2024-03-25发表的yellow array研究报告NRZ-OOK超过1 Gbit/s、OFDM 1.5 Gbit/s。这些是不同器件、驱动与接收条件下的光学实验；本项目没有optical link或BER测量，1 µs亮度PWM slot不能推导通信速率。既有检索采用作者/出版社摘要级结论，未补造bias、距离和接收条件。[原论文](https://doi.org/10.1038/s41598-024-57132-9)、[作者所在大学摘要](https://scholar.nycu.edu.tw/en/publications/advancing-high-performance-visible-light-communication-with-long-/)、[出版社Crossmark日期](https://crossmark.crossref.org/dialog/?doi=10.1038%2Fs41598-024-57132-9)。

## 5. 从一像素到 4×4：先做四本账

以下都是可复算的**预算场景**，不是已完成阵列。原始量来自冻结 v0.3 的 [analog GDS area](../../evidence/characterization/actual-w20-l4-area.json)、[measured static load](../../evidence/characterization/measured-load-summary.json)、[PWM RTL](../../rtl/pixel_pwm.v)。运行 `scripts/strategy/budget.py` 生成 [JSON](../../evidence/strategy/budget.json) 与 [CSV](../../evidence/strategy/budget.csv)，其中保留输入 hash 和所有排除项。

### 5.1 面积账：不能把集成 macro span 当作 pixel pitch

当前共同 top 的 305×180 µm 是两个 macro 加顶层布线的**跨度**，不是 pad ring、die size 或一个可线性复制的像素单元。当前模拟 cell bbox 为 95×37.66=3577.7 µm²；16 个冻结副本的面积和是 **0.0572432 mm²**。这只包含模拟 cell 的副本边界，没有数字存储/控制、通信、参考分配、routing、pads/ESD、fill 和电源网。因此它既不是完整 4×4 面积的预测，也不意味着16倍共同 top 是合理布局。

4 µm 方形 pixel site 的面积为16 µm²。当前模拟 cell bbox 是其223.606倍；单个 MOUT 的 gate 几何20×4=80 µm²也已超过该 site。这只证明**冻结的当前电路不适合原样塞进4 µm site**，不证明所有 GF180 电路或所有 MicroLED 架构都不可能小型化。共享 reference、较小器件和校准可能换面积，但需要新误差预算和真实版图。

### 5.2 功耗账：变暗不等于全部电路都省电

在公开静态 I–V、MOS 27°C、Vlogic=3.3 V、VLED=5 V、理想 IREF=100 µA 条件下，IOUT=99.788467 µA。单路 LED rail 输入498.942337 µW，加 analog/control/reference rail 330.000012 µW，共828.942349 µW。它不含数字宏和实际 reference generator；也不是光输出。

若16路各保留一个持续100 µA reference支路，则仅这部分电源输入就是：

\[
P_{bias}=N V_{logic} I_{ref}=16\times3.3\times100\,\mu A=5.28\,mW.
\]

以静态电流乘 duty 作一级近似：

\[
P_{analog+LED}\approx N V_{logic}I_{ref}
                       +V_{LED}I_{full}\sum_{i=1}^{N}D_i.
\]

16路全开约 **13.2631 mW**；全为duty=1/256时约 **5.3112 mW**；全为25%时约 **7.2758 mW**。关灯但保持bias仍有5.28 mW reference floor，其他泄漏、切换和实际reference功耗需另加。此近似没有真实LED动态/温漂，不替代 transient 或实测能耗。

若未来只保留一个共享100 µA reference，数学上的这一项可由5.28降至0.33 mW；其16路全开预算约8.3131 mW，最低码约0.3612 mW。这是**架构假设**，不是已验证省电结果：共同bias的fanout、startup、noise、gate charge、失配、routing RC和跨通道耦合都要重新验证。优先研究共享reference，理由是它瞄准了低灰阶时显著的固定成本，而不是为了增加功能数量。

### 5.3 数据账：视频更新、PWM与通信是三个速度

目前每帧256个slot，1 MHz slot clock对应3906.25 Hz PWM。9-bit duty包含0…256，共257个精确命令；代码257…511会clamp。未来若用常见8-bit图像数据，需要先定义它怎样映射到这个命令范围。

若16路每路保存一个9-bit命令，单buffer144bit=18byte；double-buffer288bit=36byte。这是**有效数据量**，还没计enable、错误状态、计数器、地址、协议逻辑，也不是已经实现的SRAM。

\[
B_{payload}=N\,b\,f_{update};\quad
B_{wire}=f_{update}(H+N\,b_{wire}).
\]

| 4×4 场景 | 更新频率 | 每次有效数据 | raw payload | 提议packet的wire预算 |
|---|---:|---:|---:|---:|
| 单色视频/测量图案 | 60 Hz | 16×9=144 bit | 8.64 kbit/s | 17.28 kbit/s |
| 每个PWM帧更新 | 3906.25 Hz | 144 bit | 562.5 kbit/s | 1.125 Mbit/s |

Packet仅为独立提议：4byte头/校验+每像素2byte，总288bit，尚未实现。若未来SPI为1MHz，一包需288µs，大于256µs PWM帧，因此不能保证每PWM帧更新；60Hz更新则有很大带宽余量。这里的SPI速度与当前1MHz PWM clock不是同一个接口。正式协议还要计片选间隔、时钟偏差、frame boundary提交和错误处理。

以VGA作不同规模的独立预算：640×480、8bit单色、60Hz的raw payload为147.456Mbit/s；RGB各8bit则442.368Mbit/s。两者都没有包括blanking、编码或协议开销。这解释为什么微显示需要不同的存储与高速接口架构；它不证明本项目达到这些速率。

### 5.4 尺寸与光学账：电流相同，物理条件未必相同

20×20 µm² mesa在100 µA时，按完整方形面积算的平均电流密度为25 A/cm²。如果假设缩到4×4 µm²并保持同样100 µA，则密度会变为625 A/cm²，增加25倍。后一项仅为几何假设，不对应任何指定器件的实际电流条件。实际有效发光面积、电流拥挤、温升、sidewall损失与EQE都会改变结果，不能沿用同一个LED电气模型来预测小像素亮度。

## 6. 研究价值：验证一条可以解释误差的工作流

本项目要验证的工作流是：**取得可公开的LED测量数据 → 建立有边界的model card → 连接可检查的ASIC驱动 → 从原始结果定位reference、mirror、PWM、寄生或LED误差 → 用独立实验检查解释。** 公开输入、模型和失败对照，使别人能够复算结论并发现方法的不足。

| 研究任务 | 需要验证的问题 | 最小交付 | 评价证据 |
|---|---|---|---|
| 入门教学 | 能否理解并独立复现从spec到DRC/LVS/电流误差的链路 | 分层讲义、一像素baseline、错误连接/属性例子 | 外部读者成功复现并解释至少一个失败；记录卡点和耗时 |
| 器件建模 | 动态与温度模型能否预测未参与拟合的数据 | 单器件measurement schema、model card、拟合与边界检查 | 真实数据和测量不确定度；同条件预测与holdout测量误差 |
| 驱动与物理实现 | 100 µA附近的reference、寄生和短脉冲预算能否解释观察差异 | 固定条件的schematic/PEX/bench实验与误差分解 | 改变一个因素后的残差变化；计算与波形可独立复核 |

“能教学”以独立复现和错误解释为证据；“模型有效”以有条件的预测误差为证据；“设计改进有效”以事先定义的对照实验为证据。仿真通过、图表完整与外部复现属于不同结论。当前仍需记录实际外部运行与bench测量。

## 7. 可执行的实验推进门槛

以下是下一轮实验判据，尚未宣称满足。先固定问题、控制变量、测量量与接受条件，再开始实现和运行。

| 决策 | 所需证据 | 应缩窄或修正的情形 | 下一步 |
|---|---|---|---|
| 完成单像素平台 | 补充供电/启动、非理想reference与完整PG预算；至少一组traceable LED动态与温度数据；维持既定±5% current/±2% lowest-code目标或透明重定spec | 模型没有目标pulse/voltage/temperature范围的数据；误差无法定位 | 缩窄声明范围，先测量或修模型 |
| 进入4×4研究芯片 | 单像素条件闭环；16路实验条件、packet/commit/reset定义；shared bias、simultaneous switching、功耗与面积预算；按同规则做array验证 | 单像素尚未闭环；供电或固定bias功耗已超实验预算 | 保留一像素/分立测试载体，修改reference与架构 |
| 检查教学与可复现性 | 至少1名外部入门读者从锁定输入复现baseline，并解释至少一个负向对照；记录环境差异和步骤卡点 | 只能读取输出，无法独立运行或解释失败 | 先修复运行入口、说明和错误检查 |
| 评估MPW实验 | 候选provider明确接受exact variant/decks/pins/voltage；取得报价、封装/测试责任；总预算≤自行确定B；silicon测量能回答明确问题 | provider不接受、5V/analog访问不匹配、无bring-up/measurement方案或超B | 继续模拟或先做board-level电测 |

每次实验记录至少包括：研究问题；被改变的因素与保持不变的条件；路数/电流/脉冲/电源/温度；数据与工具版本；测量不确定度；运行前确定的判据；实际结果与失败解释。若结果不符，应保留原始失败与修改理由，再运行新版本。

## 8. 实物实验预算与开放制造入口

公开GF180社区shuttle存在；Tiny Tapeout官方[芯片列表](https://www.tinytapeout.com/chips/)在2026-10-05访问时列出GF系列run。其[Analog Specs](https://tinytapeout.com/specs/analog/)的一些限制和报价段落明确标成sky130A，不能套成本项目的GF180、Metal5、5V LED rail或19-port top。Analog page列出的通用PDK名称也不能替代GF run的模板、rails、pin path RC和接受条件。公共入口本身不构成可提交资格。

当前没有匹配本设计的有效制造报价。实物实验预算应包含：

\[
C_{project}=C_{design\ effort}+C_{MPW}+C_{package/PCB}
            +C_{measurement}+C_{logistics}+C_{rework}.
\]

MPW报价需要注明area/tile、模拟pin、工艺、截止日期和交付数量；measurement要包含电流/脉冲、温度与光学所需设备或使用费。预算应服务于明确的研究问题，并记录实际可用样片、可测端口和返工范围。有限MC样本的零超限不能推得制造良率，一轮shuttle费用也不能代表完整实物实验费用。

推进顺序为：**完成一像素的真实负载与供电闭环 → 让一位外部初学者独立复现 → 固定下一轮器件与测量条件 → 决定4×4与共享reference实验 → 最后评估带明确测量目的的MPW。** 每次扩大范围都应增加可检验的问题与相应证据。

## 9. 证据包与复算

- [研究报告](research-report.md)、[联合PEX](joint-pex.md)与[电气验证](robustness.md)：当前单像素结果、模型与检查范围。
- [LED model card](measured-led.md)与[bench计划](bench-validation-plan.md)：科学数据来源、许可、适用条件和待测量项目。
- [budget.json](../../evidence/strategy/budget.json) / [budget.csv](../../evidence/strategy/budget.csv)：冻结输入hash、精确几何、数据/功耗预算；所有array项均为未实现场景。
- [budget.py](../../scripts/strategy/budget.py)：用标准库Decimal复算，不修改任何模型或已有电气结果。

预算保持原有输入与计算版本；本次定位调整不重写已经运行的电气证据。可公开复用的LED数值曲线遵循原NOTICE；独立说明图和计算应标出原始数据、假设与来源。
